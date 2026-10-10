"""导入器与 schema 测试。"""
from pathlib import Path

import pytest

from wealthos.importers.csv_import import import_csv, sniff_kind

REPO = Path(__file__).resolve().parent.parent
S = REPO / "samples"


def test_schema_tables(db):
    names = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ["accounts", "instruments", "activities", "holdings", "valuations", "fx_rates",
              "price_daily", "sources", "items", "events", "entities", "entity_edges",
              "exposures", "opportunities", "reports", "knowledge_nodes", "lessons",
              "fetch_log", "llm_calls", "audit_log"]:
        assert t in names, f"缺表 {t}"


def test_seed_sources_and_graph(db):
    assert db.execute("SELECT COUNT(*) c FROM sources").fetchone()["c"] >= 8
    assert db.execute("SELECT COUNT(*) c FROM entities").fetchone()["c"] >= 20
    assert db.execute("SELECT COUNT(*) c FROM entity_edges").fetchone()["c"] >= 20
    assert db.execute("SELECT COUNT(*) c FROM knowledge_nodes").fetchone()["c"] >= 10


def test_sniff_kind():
    assert sniff_kind(S / "accounts.csv") == "accounts"
    assert sniff_kind(S / "holdings_2026-10-02.csv") == "holdings"
    assert sniff_kind(S / "activities.csv") == "activities"
    with open(S / "whatever.txt", "w") as f:
        f.write("a,b\n1,2\n")
    with pytest.raises(ValueError):
        sniff_kind(S / "whatever.txt")
    (S / "whatever.txt").unlink()


def test_csv_import_roundtrip(seeded_holdings):
    db = seeded_holdings
    assert db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"] == 4
    assert db.execute("SELECT COUNT(*) c FROM holdings").fetchone()["c"] == 16  # 8×2 天
    assert db.execute("SELECT COUNT(*) c FROM activities").fetchone()["c"] >= 6
    # 两个快照日各有 4 条 valuations
    for d in ("2026-09-30", "2026-10-02"):
        assert db.execute("SELECT COUNT(*) c FROM valuations WHERE as_of=?", (d,)).fetchone()["c"] == 4
    # instruments 自动补全（AAPL 不在种子里——实际在，用未知标的验证）
    db.execute("DELETE FROM instruments WHERE symbol='0700.HK'")
    import_csv(S / "holdings_2026-10-02.csv", db)
    ins = db.execute("SELECT stooq_symbol FROM instruments WHERE symbol='0700.HK'").fetchone()
    assert ins and ins["stooq_symbol"] == "0700.hk"


def test_flex_import(db):
    from wealthos.importers.flex import import_flex, parse_flex

    parsed = parse_flex(S / "flex_sample.xml")
    st = parsed["statements"][0]
    assert st["account_id"] == "U1234567"
    assert st["as_of"] == "2026-10-01"
    assert {c["currency"] for c in st["cash"]} == {"USD", "JPY"}
    assert len(st["positions"]) == 2
    assert st["positions"][0]["symbol"] == "MSFT"
    assert len(st["trades"]) == 2
    assert len(st["dividends"]) == 1

    r = import_flex(S / "flex_sample.xml", db)
    assert r == {"kind": "flex", "cash": 2, "positions": 2, "trades": 2}
    assert db.execute(
        "SELECT quantity FROM holdings WHERE symbol='CASH:JPY'").fetchone()["quantity"] == 412000.0
    assert db.execute("SELECT COUNT(*) c FROM activities WHERE source='flex'").fetchone()["c"] == 3
    # DIVIDEND 类型正确落库
    assert db.execute(
        "SELECT COUNT(*) c FROM activities WHERE activity_type='DIVIDEND'").fetchone()["c"] == 1
    # 多币种估值：无汇率时 JPY 现金被跳过（partial，fail loud）
    v = db.execute("SELECT * FROM valuations WHERE as_of='2026-10-01'").fetchone()
    assert v["method"] == "partial"
    assert abs(v["market_value"] - (9860.35 + 35 * 415.20 + 20 * 549.80)) < 0.01  # 仅 USD 部分
    assert db.execute(
        "SELECT COUNT(*) c FROM fetch_log WHERE job='valuation' AND status='partial'"
    ).fetchone()["c"] >= 1
    # 补上汇率后重算 → JPY 现金按 150 正确折算
    db.execute("INSERT OR REPLACE INTO fx_rates VALUES('2026-10-01','USD','JPY',150.0,'fixture')")
    from wealthos.engine.networth import recompute_valuations

    recompute_valuations(db, "2026-10-01")
    v2 = db.execute("SELECT * FROM valuations WHERE as_of='2026-10-01'").fetchone()
    assert v2["method"] == "auto"
    assert abs(v2["market_value"] - (9860.35 + 14532.0 + 10996.0 + 412000 / 150)) < 0.01
