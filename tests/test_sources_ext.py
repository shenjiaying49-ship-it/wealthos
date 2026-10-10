"""新信息源测试：华尔街见闻 / Jina 阅读器 / 雪球 / Exa（全 mock）。"""
import httpx

from wealthos.ingest import dispatch, wscn
from wealthos.providers import exa, reader, xueqiu


def _wscn_payload():
    return {"code": 20000, "data": {"items": [
        {"title": "美联储公布利率决议", "content": "<p>美联储维持利率不变，符合市场预期。</p>",
         "uri": "https://wallstreetcn.com/lives/1", "source_time": 1791000000},
        {"title": "", "content": "<p>日本央行官员发表鸽派讲话，日元短线走低。</p>",
         "uri": "https://wallstreetcn.com/lives/2", "source_time": 1791000600},
        {"title": "美联储公布利率决议", "content": "<p>重复条目</p>",
         "uri": "https://wallstreetcn.com/lives/1", "source_time": 1791001200},
    ]}}


def test_wscn_parse(seeded_holdings):
    items = wscn.parse_items(_wscn_payload())
    assert len(items) == 3
    assert items[0]["title"] == "美联储公布利率决议"
    assert "美联储维持" in items[0]["summary"]
    assert items[1]["title"].startswith("日本央行官员")  # 无标题时取正文头部
    assert items[0]["published_at"].startswith("2026-")


def test_wscn_fetch_dedup_and_relevance(seeded_holdings):
    db = seeded_holdings
    from wealthos.engine import exposures as exp_mod
    from wealthos.ingest import relevance as rel

    exp = exp_mod.compute_exposures(db)
    exp_mod.persist_exposures(db, exp)
    rel.attach_my_exposure_nodes(db, exp["as_of"])

    client = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json=_wscn_payload())))
    r = wscn.fetch(db, client=client)
    assert r["status"] == "ok" and r["new"] == 2  # 第三条近重被拦
    assert db.execute("SELECT COUNT(*) c FROM items WHERE source_id='wscn_global'"
                      ).fetchone()["c"] == 2
    rel.score_items(db)
    rows = {t: rel_ for t, rel_ in db.execute(
        "SELECT title, relevance FROM items WHERE source_id='wscn_global'")}
    assert rows["美联储公布利率决议"] > 0.05      # 命中 Fed/USD 敞口
    boj_rel = next(v for t, v in rows.items() if t.startswith("日本央行"))
    assert boj_rel > 0.05  # 命中 BoJ/JPY 敞口


def test_dispatch_includes_wscn(seeded_holdings, monkeypatch):
    db = seeded_holdings
    called = {"wscn": 0, "rss": 0}
    monkeypatch.setattr(wscn, "fetch", lambda d, **kw: (called.__setitem__("wscn", 1) or
                                                        {"source": "wscn_global", "status": "ok", "new": 2}))
    from wealthos.ingest import rss as rss_mod

    monkeypatch.setattr(rss_mod, "fetch_source",
                        lambda d, sid, client=None: (called.__setitem__("rss", 1) or
                                                     {"source": sid, "status": "ok", "new": 0}))
    r = dispatch.fetch_all(db)
    assert called["wscn"] == 1 and r["new"] >= 2


def test_reader_jina_then_direct_fallback():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if "r.jina.ai" in str(req.url):
            return httpx.Response(503)  # Jina 挂了
        return httpx.Response(200, text="<html><body>" + "美联储声明正文。" * 30 +
                                      "</body></html>")

    text = reader.read_url("https://example.com/fed",
                           client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert text and "美联储声明正文" in text  # 直连兜底成功

    def handler2(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Title\n\n正文内容足够长。" * 10)

    text2 = reader.read_url("https://example.com/x",
                            client=httpx.Client(transport=httpx.MockTransport(handler2)))
    assert "正文内容足够长" in text2  # Jina 成功路径
    assert reader.read_url("not-a-url") is None


def test_xueqiu_byo_cookie(monkeypatch):
    monkeypatch.delenv("WEALTHOS_XUEQIU_COOKIE", raising=False)
    assert xueqiu.configured() is False
    assert xueqiu.fetch_quotes(["AAPL"]) is None
    monkeypatch.setenv("WEALTHOS_XUEQIU_COOKIE", "abc123")  # 裸 token → 自动补前缀
    ck = xueqiu.cookie()
    assert ck == "xq_a_token=abc123"
    got = {}

    def handler(req: httpx.Request) -> httpx.Response:
        got["cookie"] = req.headers.get("cookie")
        return httpx.Response(200, json={"data": {"items": [
            {"symbol": "SH600519", "quote": {"current": 1500.0, "time": 1791000000,
                                             "currency": "CNY"}}]}})

    out = xueqiu.fetch_quotes(["SH600519"],
                              client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert got["cookie"] == "xq_a_token=abc123"  # 最小 cookie 带上
    assert out["SH600519"]["price"] == 1500.0


def test_exa_byo_key(monkeypatch):
    monkeypatch.delenv("WEALTHOS_EXA_API_KEY", raising=False)
    assert exa.configured() is False and exa.search("x") is None
    monkeypatch.setenv("WEALTHOS_EXA_API_KEY", "test-key")
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("x-api-key")
        seen["body"] = json_body(req)
        return httpx.Response(200, json={"results": [
            {"title": "Fed decision", "url": "https://example.com/f", "text": "…"}]})

    def json_body(req):
        import json as _j
        return _j.loads(req.content.decode())

    out = exa.search("fed decision", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert seen["auth"] == "test-key" and seen["body"]["numResults"] == 5
    assert out[0]["url"].startswith("https://")


def test_config_status_covers_new_sources(tmp_path, monkeypatch):
    from wealthos import config as cfg

    for k in ("WEALTHOS_XUEQIU_COOKIE", "WEALTHOS_EXA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    st = cfg.integrations_status()
    assert set(st) >= {"llm", "telegram", "fred", "xueqiu", "exa", "x"}
    assert st["xueqiu"]["configured"] is False and st["exa"]["configured"] is False
