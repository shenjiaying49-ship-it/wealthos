"""Brief / 审计器 / 教育引擎 / Provider（MockTransport）测试。"""
import httpx

from wealthos.agents import auditor, brief, education


def _fake_news(db, title, url, summary=""):
    db.execute(
        "INSERT OR IGNORE INTO items(source_id,ext_id,title,summary,url,published_at,fetched_at,"
        "dedup_key,content_hash,label) VALUES('fed_press','x',?,?,?,?,?,?,?,'fact')",
        (title, summary, url, "2026-10-02T08:00:00+00:00", "2026-10-02T09:00:00+00:00",
         f"url:{url}", f"url:{url}"))


def test_brief_deterministic_full_flow(seeded_holdings):
    db = seeded_holdings
    _fake_news(db, "Bank of Japan holds rates steady",
               "https://www.boj.or.jp/en/news/2026/a.html")
    _fake_news(db, "Fed signals patience on rate cuts",
               "https://example.com/fed")
    result = brief.generate(db, today="2026-10-03")
    c = result["content"]

    # 结构完整性
    for section in ["YOUR WEALTH", "今天值得你知道", "与你有关的一件事",
                    "值得研究的机会", "今日金融课", "免责"]:
        assert section in c, f"缺板块: {section}"
    # 五类标签纪律 + 计算标记
    assert "[计算]" in c
    assert any(f"[{x}]" in c for x in ["事实", "分析", "观点"])
    # 快照哈希绑定
    assert result["snapshot_hash"]
    row = db.execute("SELECT * FROM reports WHERE id=?", (result["report_id"],)).fetchone()
    assert row["data_snapshot_hash"] == result["snapshot_hash"]
    # 与你有关：应选中相关性最高的事件（USD 敞口 36.9% > JPY 26.5% → Fed 新闻），
    # 路径必须到达真实敞口节点
    cj = result["content_json"]
    assert cj["personal_story"] is not None
    story = cj["personal_story"]
    assert set(story["entities"]) & {"CB:BOJ", "CB:FED", "MC:RATE", "CCY:JPY", "CCY:USD"}
    assert "EXPO:currency:" in story["path"] and story["exposure_dim"] == "currency"
    assert float(story["exposure_pct"].rstrip("%")) > 0
    # 确定性模式声明
    assert "LLM 增强：关闭" in c
    # 审计通过（无禁语、无未溯源数字）
    assert result["audit_failures"] == []


def test_brief_no_data_fail_loud(db):
    result = brief.generate(db, today="2026-10-03")
    assert "暂无数据" in result["content"]
    assert "暂无新闻" in result["content"]


def test_auditor_banned_phrases():
    bad = "你应该马上去香港开户，这是最好的资产配置，一定会涨"
    hits = auditor.check_banned_phrases(bad)
    assert any("应该" in h for h in hits)
    assert any("配置" in h for h in hits)
    assert auditor.check_banned_phrases("值得研究多币种账户的持有成本") == []


def test_auditor_numbers_grounded():
    computed = {"total": 2115444.0, "pct": 0.42}
    ok = "你的净值 2,115,444 HKD，日变动 0.42%"
    assert auditor.check_numbers_grounded(ok, computed) == []
    bad = "你的净值 3,000,000 HKD"
    assert auditor.check_numbers_grounded(bad, computed)  # 3000000 未溯源 → 拦截
    # 日期豁免
    assert auditor.check_numbers_grounded("2026-10-03 的简报", computed) == []


def test_auditor_evidence_urls():
    assert auditor.check_evidence_urls([{"title": "x", "url": "https://a"}]) == []
    assert auditor.check_evidence_urls([{"title": "x", "url": ""}]) == ["x"]


def test_lesson_picker_and_mastery(seeded_holdings):
    db = seeded_holdings
    lesson = education.pick_lesson(db, "2026-10-03")
    assert lesson is not None
    # 无前置缺口时 importance 高的优先
    assert lesson["importance"] >= 4
    # 关系段（确定性映射）
    rel_text = education.relation_to_portfolio(db, "fx_and_returns")
    assert "币种敞口" in rel_text and "USD" in rel_text
    # 答对 → 掌握度上升、状态流转
    education.record_lesson(db, lesson, "2026-10-03", True)
    node = db.execute("SELECT * FROM knowledge_nodes WHERE concept=?",
                      (lesson["concept"],)).fetchone()
    assert node["mastery_score"] > 0
    assert node["status"] in ("learning", "known")
    # 答错 → weak
    education.record_lesson(db, lesson, "2026-10-04", False)
    node = db.execute("SELECT * FROM knowledge_nodes WHERE concept=?",
                      (lesson["concept"],)).fetchone()
    assert node["status"] == "weak"
    # 已读概念 14 天内不重复
    assert education.pick_lesson(db, "2026-10-04")["concept"] != lesson["concept"]


def test_quotes_yahoo_primary_stooq_fallback(seeded_holdings):
    """Yahoo 成功的走 Yahoo；Yahoo 失败的走 Stooq 兜底。"""
    db = seeded_holdings

    def handler(req: httpx.Request) -> httpx.Response:
        if "finance.yahoo.com" in str(req.url):
            if "AAPL" in str(req.url):
                return httpx.Response(200, json={"chart": {"result": [{
                    "meta": {"currency": "USD", "regularMarketPrice": 263.1,
                             "regularMarketTime": 1791000000}}]}})
            return httpx.Response(429)  # 0700.HK 被 Yahoo 拒
        # Stooq 批量
        return httpx.Response(200, text=(
            "Symbol,Date,Time,Open,High,Low,Close,Volume\r\n"
            "0700.hk,2026-10-02,16:00:00,612.0,617.0,611.0,615.5,8100000\r\n"))

    from wealthos.providers import quotes

    out = quotes.fetch_latest(db, ["AAPL", "0700.HK"],
                              client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert out["AAPL"]["price"] == 263.1 and out["AAPL"]["currency"] == "USD"
    assert out["0700.HK"]["price"] == 615.5  # Stooq 兜底成功
    rows = {r["symbol"]: dict(r) for r in db.execute("SELECT * FROM price_latest")}
    assert rows["AAPL"]["source"] == "yahoo"
    assert rows["0700.HK"]["source"] == "stooq"


def test_quotes_all_sources_down(seeded_holdings):
    """全部行情源失败 → 空结果，绝不编造（fail loud）。"""
    db = seeded_holdings
    from wealthos.providers import quotes

    out = quotes.fetch_latest(
        db, ["AAPL"],
        client=httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(403, text="<html>challenge</html>"))))
    assert out == {}


def test_flex_symbol_mapping(db):
    from wealthos import db as dbm

    assert dbm._stooq_symbol("0700.HK") == "0700.hk"
    assert dbm._stooq_symbol("1321.T") == "1321.jp"
    assert dbm._stooq_symbol("AAPL") == "aapl.us"
    assert dbm._stooq_symbol("CASH:USD") == ""


def test_frankfurter_parsing(seeded_holdings):
    db = seeded_holdings
    payload = {"base": "USD", "date": "2026-10-02",
               "rates": {"HKD": 7.81, "JPY": 149.5, "CNY": 7.09}}
    client = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json=payload)))
    from wealthos.providers import fx

    n = fx.fetch_fx_latest(db, ["HKD", "JPY", "CNY"], client=client)
    assert n == 3
    r = db.execute("SELECT rate FROM fx_rates WHERE as_of='2026-10-02' AND "
                   "base_ccy='USD' AND quote_ccy='HKD'").fetchone()
    assert r["rate"] == 7.81


def test_llm_cache_hit(seeded_holdings):
    """同一 prompt 二次调用必须命中缓存（不重复计费）。"""
    db = seeded_holdings
    import os

    os.environ["WEALTHOS_LLM_PROVIDER"] = "openai"
    os.environ["WEALTHOS_LLM_API_KEY"] = "test-key"
    os.environ["WEALTHOS_LLM_MODEL"] = "test-model"
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"news_oneliners": ["测试摘要"], '
                                               '"why_it_matters": "测试解释"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from wealthos.agents import llm as llm_mod

    r1 = llm_mod.chat(db, "同一问题", system="s", client=client)
    r2 = llm_mod.chat(db, "同一问题", system="s", client=client)
    assert r1 == r2
    assert calls["n"] == 1  # 第二次走缓存
    hits = db.execute("SELECT COUNT(*) c FROM llm_calls WHERE cache_hit=1").fetchone()["c"]
    assert hits == 1
    for k in ("WEALTHOS_LLM_PROVIDER", "WEALTHOS_LLM_API_KEY", "WEALTHOS_LLM_MODEL"):
        os.environ.pop(k, None)


def test_brief_llm_enhanced(seeded_holdings):
    db = seeded_holdings
    import os

    os.environ["WEALTHOS_LLM_PROVIDER"] = "openai"
    os.environ["WEALTHOS_LLM_API_KEY"] = "test-key"
    os.environ["WEALTHOS_LLM_MODEL"] = "test-model"
    _fake_news(db, "Bank of Japan holds rates steady", "https://boj.example/a")
    client_holder = {"client": None}

    def handler(req):
        return httpx.Response(200, json={
            "choices": [{"message": {"content":
                '{"news_oneliners": ["日银按兵不动，符合市场预期"], '
                '"why_it_matters": "你的日元敞口约 12%，该决定降低了短期汇率波动的不确定性。"}'}}],
            "usage": {}})

    # 让 brief 内部的 chat 使用 mock client：monkeypatch httpx.Client 构造
    orig_client = httpx.Client

    class PatchedClient(orig_client):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    import wealthos.agents.llm as llm_mod

    llm_mod.httpx.Client = PatchedClient
    try:
        result = brief.generate(db, today="2026-10-03")
        assert result["content_json"]["llm_enhanced"] is True
        assert "日银按兵不动" in result["content"]
        assert "[AI 推断]" in result["content"]
    finally:
        llm_mod.httpx.Client = orig_client
        for k in ("WEALTHOS_LLM_PROVIDER", "WEALTHOS_LLM_API_KEY", "WEALTHOS_LLM_MODEL"):
            os.environ.pop(k, None)
