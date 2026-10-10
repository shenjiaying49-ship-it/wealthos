"""摄取层测试：去重 / 实体抽取 / Source Graph 相关性（全离线）。"""
from wealthos.ingest import dedup
from wealthos.ingest import relevance as rel


def test_canonical_url_strips_tracking():
    u = "https://www.cnbc.com/2026/10/03/fed.html?utm_source=x&utm_campaign=y&id=7"
    assert dedup.canonical_url(u) == "https://cnbc.com/2026/10/03/fed.html?id=7"
    assert dedup.canonical_url("") == ""


def test_simhash_similarity():
    a = "Federal Reserve holds interest rates steady in October meeting"
    b = "Federal Reserve holds interest rates steady in October decision"
    c = "Japan trade surplus widens on chip exports"
    assert dedup.similarity(dedup.simhash(a), dedup.simhash(b)) > 0.85
    assert dedup.similarity(dedup.simhash(a), dedup.simhash(c)) < 0.6


def test_is_near_duplicate_titles():
    a = ("Bank of Japan raises rates by 25 basis points", "2026-10-02")
    # 单词变形 → Jaccard 高 → 近重
    assert dedup.is_near_duplicate_titles(
        "Bank of Japan raises rates by 25 basis points",
        "2026-10-02", [("Bank of Japan lifted rates by 25 basis points", "2026-10-02")])
    # 超出 ±1 天窗口不算重复
    assert not dedup.is_near_duplicate_titles(
        "Bank of Japan raises rates by 25 basis points",
        "2026-10-02", [("Bank of Japan raises rates by 25 basis points", "2026-09-20")])
    # 完全不同的标题
    assert not dedup.is_near_duplicate_titles(
        "Apple announces new product line in Cupertino",
        "2026-10-02", [a])


def test_rss_store_and_dedup(seeded_holdings):
    db = seeded_holdings
    from wealthos.ingest import rss

    class FakeResp:
        status_code = 200
        text = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Bank of Japan keeps rates unchanged</title>
          <link>https://www.boj.or.jp/en/news/2026/k101030.pdf?utm_source=rss</link>
          <description>The Bank of Japan decided to keep its policy rate unchanged.</description>
          <pubDate>Fri, 02 Oct 2026 08:00:00 GMT</pubDate></item>
        <item><title>Bank of Japan keeps rates unchanged</title>
          <link>https://www.boj.or.jp/en/news/2026/k101030.pdf</link>
          <pubDate>Fri, 02 Oct 2026 09:00:00 GMT</pubDate></item>
        </channel></rss>"""

    class FakeClient:
        def get(self, url):
            return FakeResp()

        def close(self):
            pass

    r = rss.fetch_source(db, "fed_press", client=FakeClient())
    assert r["new"] == 1  # 第二条被三级去重拦截
    row = db.execute("SELECT * FROM items").fetchone()
    assert row["url"] == "https://boj.or.jp/en/news/2026/k101030.pdf"  # canonical 化


def test_extract_entities(seeded_holdings):
    db = seeded_holdings
    aliases = rel._load_aliases(db)
    ents = rel.extract_entities("Federal Reserve signals slower rate cuts ahead", aliases)
    assert "CB:FED" in ents
    ents2 = rel.extract_entities("日本银行维持利率不变，日元走弱", aliases)
    assert "CB:BOJ" in ents2 and "CCY:JPY" in ents2


def test_relevance_bfs_to_exposure(seeded_holdings):
    db = seeded_holdings
    from wealthos.engine import exposures as exp_mod

    exp = exp_mod.compute_exposures(db)
    exp_mod.persist_exposures(db, exp)
    n = rel.attach_my_exposure_nodes(db, exp["as_of"])
    assert n >= 15  # 五维 + 单一标的的敞口节点都挂上了

    adj = rel._adjacency(db)
    # BoJ → CCY:JPY(0.9) → 我的 JPY 敞口
    rel_boj = rel.relevance_for_entities(["CB:BOJ"], adj)
    exp_pct = {r["key"]: r["pct"] for r in exp["currency"]}["JPY"] / 100
    assert abs(rel_boj - 0.9 * exp_pct) < 1e-6
    # Fed → USD 敞口
    rel_fed = rel.relevance_for_entities(["CB:FED"], adj)
    usd_pct = {r["key"]: r["pct"] for r in exp["currency"]}["USD"] / 100
    assert abs(rel_fed - 0.9 * usd_pct) < 1e-6
    # 无关节目相关性为 0
    assert rel.relevance_for_entities(["CB:MAS"], adj) == 0.0

    # explain：路径可解释
    paths = rel.explain_relevance(db, ["CB:BOJ"])
    assert paths and paths[0]["expo_node"].startswith("EXPO:currency:")
    assert "CB:BOJ" in paths[0]["path"] and "CCY:JPY" in paths[0]["path"]


def test_score_items(seeded_holdings):
    db = seeded_holdings
    from wealthos.engine import exposures as exp_mod
    from wealthos.ingest import rss

    exp = exp_mod.compute_exposures(db)
    exp_mod.persist_exposures(db, exp)
    rel.attach_my_exposure_nodes(db, exp["as_of"])

    class FakeResp:
        status_code = 200
        text = """<rss version="2.0"><channel>
        <item><title>Fed officials discuss inflation path</title>
          <link>https://example.com/a</link><pubDate>Fri, 02 Oct 2026 08:00:00 GMT</pubDate></item>
        <item><title>Local bakery wins award</title>
          <link>https://example.com/b</link><pubDate>Fri, 02 Oct 2026 08:00:00 GMT</pubDate></item>
        </channel></rss>"""

    class FakeClient:
        def get(self, url):
            return FakeResp()

        def close(self):
            pass

    rss.fetch_source(db, "fed_press", client=FakeClient())
    n = rel.score_items(db)
    assert n == 2
    rows = {r["title"]: r["relevance"] for r in db.execute("SELECT title, relevance FROM items")}
    assert rows["Fed officials discuss inflation path"] > 0
    assert rows["Local bakery wins award"] == 0
