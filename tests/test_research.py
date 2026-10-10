"""Research Agent 测试：EDGAR mock → 精读结构 → 知识图谱登记。"""
import httpx
import pytest

from wealthos import db as dbm
from wealthos.agents import research as rs


def _concept(rows):
    return {"units": {"USD": rows}}


def _edgar_payloads():
    """构造两年八个季度的营收/EPS/毛利 XBRL 条目。"""
    rev, eps, gp = [], [], []
    quarters = []
    for year in (2025, 2026):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            quarters.append(f"{year}-{m:02d}-{d:02d}")
    for i, end in enumerate(quarters):
        start = f"{int(end[:4]) - 1 if end[5:7] == '12' else int(end[:4])}-{'01' if end[5:7] != '12' else '10'}-01"
        # 简化：起止相差一个季度即可（80-105 天判定放宽为构造值）
        rev_v = 80e9 + i * 5e9
        eps_v = 1.2 + i * 0.1
        gp_v = rev_v * 0.45
        common = {"form": "10-Q" if end[5:7] != "12" else "10-K",
                  "filed": end, "start": _qstart(end), "end": end, "accn": f"a{i}"}
        rev.append({**common, "val": rev_v})
        eps.append({**common, "val": eps_v})
        gp.append({**common, "val": gp_v})
    return {"revenue": _concept(rev), "eps": _concept(eps), "gross_profit": _concept(gp)}


def _qstart(end: str) -> str:
    y, m = int(end[:4]), int(end[5:7])
    sy, sm = (y - 1, 10) if m == 12 else (y if m > 3 else y - 1, {3: 1, 6: 4, 9: 7}[m])
    return f"{sy}-{sm:02d}-01"


def test_build_brief_edgar_flow(seeded_holdings):
    db = seeded_holdings
    payloads = _edgar_payloads()
    hits = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        hits["n"] += 1
        if "Revenues" in url or "OperatingIncomeLoss" in url or "NetIncomeLoss" in url:
            return httpx.Response(404)
        for tag, data in (("RevenueFromContractWithCustomerExcludingAssessedTax", payloads["revenue"]),
                          ("EarningsPerShareDiluted", payloads["eps"]),
                          ("GrossProfit", payloads["gross_profit"])):
            if tag in url:
                return httpx.Response(200, json=data)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    # EDGAR EPS 单位是 USD/shares
    orig_units = rs.UNITS
    brief = rs.build_brief(db, "AAPL", client=client)

    assert brief["symbol"] == "AAPL" and brief["name"] == "苹果"
    assert brief["data_source"].startswith("SEC EDGAR")
    assert len(brief["sections"]) == 8
    ids = [s["id"] for s in brief["sections"]]
    assert ids[0] == "revenue" and "valuation" in ids and "changed" in ids
    # 数字全部带来源
    for s in brief["sections"]:
        for d in s.get("data") or []:
            assert d.get("source"), f"{s['id']}/{d.get('label')} 缺来源"
    rev_sec = brief["sections"][0]
    yoy_row = next(d for d in rev_sec["data"] if "同比" in d["label"])
    assert "+" in yoy_row["value"]  # 构造数据递增 → 正增长
    # P/E 用了行情表里的价格（seeded_holdings 无 AAPL price_latest → 用持仓价不算）
    # TTM EPS = 最近四季之和
    eps_sec = next(s for s in brief["sections"] if s["id"] == "eps")
    ttm = next(d for d in eps_sec["data"] if "TTM" in d["label"])
    assert float(tm := ttm["value"]) > 0
    # 落库 + 知识图谱登记
    assert db.execute("SELECT COUNT(*) c FROM reports WHERE kind='earnings_brief'").fetchone()["c"] == 1
    kn = {r["concept"]: r["status"] for r in
          db.execute("SELECT concept,status FROM knowledge_nodes WHERE domain='research'")}
    assert "gross_margin" in kn and kn["gross_margin"] == "learning"


def test_build_brief_no_edgar_hk(seeded_holdings):
    db = seeded_holdings
    client = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(404)))
    brief = rs.build_brief(db, "0700.HK", client=client)
    assert brief["data_source"].startswith("行情")  # 降级模式，fail loud 声明边界
    assert len(brief["sections"]) == 8
    assert "数据边界" in json_dumps(brief)


def json_dumps(b):
    import json

    return json.dumps(b, ensure_ascii=False)


def test_unknown_symbol(seeded_holdings):
    with pytest.raises(ValueError):
        rs.build_brief(seeded_holdings, "NOPE")


def test_notify_not_configured():
    from wealthos.providers import notify

    assert notify.configured() is False
    assert notify.send("hi") is False


def test_api_research(seeded_holdings, monkeypatch, tmp_path):
    db_file = tmp_path / "r.db"
    dbm.init_db(db_file)
    monkeypatch.setattr(dbm, "DB_PATH", db_file)
    from fastapi.testclient import TestClient

    from wealthos.api.app import create_app

    client = TestClient(create_app())
    r = client.get("/api/research").json()
    assert len(r["watchlist"]) >= 6
    assert any(c["symbol"] == "0700.HK" for c in r["watchlist"])
    # 生成 0700.HK（走降级路径，无外网依赖）
    one = client.get("/api/research/0700.HK")
    assert one.status_code == 200
    assert one.json()["symbol"] == "0700.HK"
    assert client.get("/api/research/NOPE").status_code == 404
