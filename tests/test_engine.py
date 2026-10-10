"""净值与敞口引擎测试（固定汇率，确定性）。"""
from wealthos.engine import exposures as exp_mod
from wealthos.engine import networth as nw_mod


def _holdings_rows(db, as_of):
    return [dict(r) for r in db.execute(
        "SELECT h.symbol symbol, h.quantity qty, h.price, a.name acct, a.institution "
        "FROM holdings h JOIN accounts a ON a.id=h.account_id WHERE h.as_of=?", (as_of,))]


def test_fx_lookup_direct_inverse_bridge(seeded_holdings):
    db = seeded_holdings
    assert nw_mod.fx_rate(db, "2026-10-02", "USD", "HKD") == 7.80
    assert abs(nw_mod.fx_rate(db, "2026-10-02", "HKD", "USD") - 1 / 7.80) < 1e-9
    # HKD→JPY 走 USD 桥
    assert abs(nw_mod.fx_rate(db, "2026-10-02", "HKD", "JPY") - 150.0 / 7.80) < 1e-6
    assert nw_mod.fx_rate(db, "2026-10-02", "USD", "USD") == 1.0
    assert nw_mod.fx_rate(db, "2026-10-02", "USD", "EUR") is None  # 缺 EUR → None（不编造）


def test_net_worth_series_and_delta(seeded_holdings):
    db = seeded_holdings
    series = nw_mod.net_worth_series(db)  # base 默认 HKD
    assert [s["as_of"] for s in series] == ["2026-09-30", "2026-10-02"]
    d1, d2 = series
    # 手算 9-30（HKD base）：
    # IBKR: (42000 + 120*258.5 + 50*545.2) USD = 100280 → ×7.8 = 782,184
    ibkr = next(d for d in d1["detail"] if d["account_id"] == 1)
    assert abs(ibkr["value_base"] - 782184.0) < 1.0
    assert ibkr["fx_rate"] == 7.80
    # 长桥: 150000 + 400*610 = 394,000 HKD；本地银行: 380,000 HKD
    # 日本: (1800000 + 300*29850) JPY = 10,755,000 → /150×7.8 = 559,260
    total1 = 782184.0 + 394000.0 + 380000.0 + 559260.0
    assert abs(d1["total_base"] - total1) < 2.0
    assert d2["total_base"] > d1["total_base"]  # 样例里 10-02 全线上涨

    summary = nw_mod.net_worth_summary(db)
    assert summary["as_of"] == "2026-10-02"
    assert summary["delta"]["prev_as_of"] == "2026-09-30"
    assert summary["delta"]["pct"] > 0
    assert summary["by_asset_class"]["cash"] > 0
    # 回归：嵌套游标跳行 bug 曾导致 by_class 只剩各账户最后一行
    class_sum = sum(summary["by_asset_class"].values())
    assert abs(class_sum - summary["total"]) / summary["total"] < 0.01
    assert set(summary["by_asset_class"]) >= {"cash", "equity", "etf"}


def test_missing_fx_fail_loud(seeded_holdings):
    db = seeded_holdings
    db.execute("DELETE FROM fx_rates WHERE quote_ccy='JPY'")
    series = nw_mod.net_worth_series(db)
    latest = series[-1]
    # 7 天回看仍找不到 → 日本账户被剔除并显式记录 missing
    assert any(m["currency"] == "JPY" for m in latest["missing_fx"])
    # 回看窗口命中 9-30 的 JPY 汇率?——10-02 往前找 8 天含 9-30 但那天的 JPY 也被删了
    assert latest["total_base"] < nw_mod.net_worth_series(db)[0]["total_base"] * 2  # sanity


def test_valuation_carry_forward(seeded_holdings):
    """账户快照频率不齐时：缺快照的账户沿用最近估值并标注 stale（口径一致才可比）。"""
    db = seeded_holdings
    # 模拟：日本账户 10-02 没有更新（如手动 CSV 周更）
    db.execute("DELETE FROM holdings WHERE as_of='2026-10-02' AND account_id=4")
    db.execute("DELETE FROM valuations WHERE as_of='2026-10-02' AND account_id=4")
    series = nw_mod.net_worth_series(db)
    d2 = series[-1]
    jpn = next(d for d in d2["detail"] if d["account_id"] == 4)
    assert jpn["as_of"] == "2026-09-30" and jpn["stale_days"] == 2
    assert 4 in d2["stale_accounts"]
    # 其他账户不受影响
    ibkr = next(d for d in d2["detail"] if d["account_id"] == 1)
    assert ibkr["as_of"] == "2026-10-02" and "stale_days" not in ibkr
    # 9-30 当天：日本账户不 stale
    d1 = series[0]
    jpn1 = next(d for d in d1["detail"] if d["account_id"] == 4)
    assert "stale_days" not in jpn1


def test_exposures_five_dimensions(seeded_holdings):
    db = seeded_holdings
    exp = exp_mod.compute_exposures(db)
    assert exp["as_of"] == "2026-10-02"
    assert abs(sum(r["pct"] for r in exp["currency"]) - 100.0) < 0.5
    assert abs(sum(r["pct"] for r in exp["institution"]) - 100.0) < 0.5
    ccy = {r["key"]: r["pct"] for r in exp["currency"]}
    # 手算：总 = 100280*7.8(USD) + 394000+380000(HKD) + 10755000/150*7.8... 简化断言：
    assert ccy["USD"] > 30 and ccy["HKD"] > 25 and ccy["JPY"] > 10
    inst = {r["key"]: r["pct"] for r in exp["institution"]}
    assert set(inst) == {"Interactive Brokers", "LongPort", "Bank of East Asia", "Japan Net Bank"}
    # 单一标的（排除现金行）top1 是 1321.T：300×30,120 JPY ≈ 469,872 HKD，最大单仓
    top = next(r for r in exp["single_symbol"] if not r["key"].startswith("CASH:"))
    assert top["key"] == "1321.T"
    exp_mod.persist_exposures(db, exp)
    assert db.execute("SELECT COUNT(*) c FROM exposures WHERE as_of='2026-10-02'").fetchone()["c"] > 10
