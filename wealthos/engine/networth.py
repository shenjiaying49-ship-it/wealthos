"""净值引擎：多币种快照 → 基础币种净值序列 + 日变动。确定性计算，无 LLM。"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from ..config import PROFILE

# 桥接币：任意币对经 USD 换算（frankfurter/ECB 以 EUR 为基准亦可用，统一走 USD 桥）
BRIDGE = "USD"


def fx_rate(db: sqlite3.Connection, as_of: str, ccy: str, base: str) -> float | None:
    """查某日 ccy→base 汇率；先直连再走桥接；找不到返回 None（调用方必须显式处理）。"""
    ccy, base = ccy.upper(), base.upper()
    if ccy == base:
        return 1.0
    row = db.execute(
        "SELECT rate FROM fx_rates WHERE as_of=? AND base_ccy=? AND quote_ccy=?",
        (as_of, ccy, base),
    ).fetchone()
    if row:
        return row["rate"]
    if BRIDGE not in (ccy, base):
        a = db.execute(
            "SELECT rate FROM fx_rates WHERE as_of=? AND base_ccy=? AND quote_ccy=?",
            (as_of, BRIDGE, ccy),
        ).fetchone()
        b = db.execute(
            "SELECT rate FROM fx_rates WHERE as_of=? AND base_ccy=? AND quote_ccy=?",
            (as_of, BRIDGE, base),
        ).fetchone()
        if a and b:
            return b["rate"] / a["rate"]
    inv = db.execute(
        "SELECT rate FROM fx_rates WHERE as_of=? AND base_ccy=? AND quote_ccy=?",
        (as_of, base, ccy),
    ).fetchone()
    if inv and inv["rate"]:
        return 1.0 / inv["rate"]
    return None


def _nearest_rate(db: sqlite3.Connection, on_or_before: str, ccy: str, base: str) -> tuple[float, str] | None:
    """往前找最近可得汇率（≤7 天），返回 (rate, as_of_used)。"""
    d = datetime.strptime(on_or_before, "%Y-%m-%d")
    for _ in range(8):
        r = fx_rate(db, d.strftime("%Y-%m-%d"), ccy, base)
        if r:
            return r, d.strftime("%Y-%m-%d")
        d -= timedelta(days=1)
    return None


def recompute_valuations(db: sqlite3.Connection, as_of: str | None = None) -> dict:
    """按 holdings 重算某日各账户估值（币种感知：每条持仓按其币种→账户币种换算）。

    缺汇率的持仓跳过并写 fetch_log 告警（fail loud），绝不做币种盲加。
    """
    from datetime import datetime, timezone

    if as_of:
        days = [as_of]
    else:
        days = [r["as_of"] for r in db.execute(
            "SELECT DISTINCT as_of FROM holdings ORDER BY as_of")]
    warned = 0
    for day in days:
        for acct in list(db.execute("SELECT id, currency FROM accounts WHERE is_asset=1")):
            rows = db.execute(
                """SELECT symbol, quantity, currency, price FROM holdings
                   WHERE account_id=? AND as_of=?""", (acct["id"], day)).fetchall()
            if not rows:
                continue
            mv, skipped = 0.0, []
            for h in rows:
                if h["currency"].upper() != acct["currency"].upper():
                    got = _nearest_rate(db, day, h["currency"], acct["currency"])
                    rate = got[0] if got else None
                else:
                    rate = 1.0
                if rate is None:
                    skipped.append(f"{h['symbol']}({h['currency']})")
                    continue
                mv += h["quantity"] * (h["price"] or 1.0) * rate
            db.execute(
                """INSERT INTO valuations(account_id,as_of,market_value,currency,method)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(account_id,as_of) DO UPDATE SET
                     market_value=excluded.market_value, method=excluded.method""",
                (acct["id"], day, mv, acct["currency"], "partial" if skipped else "auto"))
            if skipped:
                warned += 1
                db.execute(
                    "INSERT INTO fetch_log(job,target,status,detail,items,ts) "
                    "VALUES('valuation',?,'partial',?,0,?)",
                    (f"account:{acct['id']}@{day}", "缺汇率跳过: " + ",".join(skipped[:5]),
                     datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return {"days": len(days), "warned_accounts": warned}


def net_worth_series(db: sqlite3.Connection, base: str | None = None) -> list[dict]:
    """每日总净值（基础币种），估值结转：账户无当日快照时沿用其最近一次快照并标注 staleness。

    不同账户的快照频率可能不同（券商日更 / 手动 CSV 周更），
    逐日对比只有在"同一账户集合"口径下才有意义——结转是标准做法。
    """
    from datetime import datetime

    base = base or PROFILE.base_currency
    days = [r["as_of"] for r in db.execute(
        "SELECT DISTINCT as_of FROM valuations ORDER BY as_of")]
    accounts = [dict(r) for r in db.execute("SELECT id, currency FROM accounts WHERE is_asset=1")]
    out = []
    for as_of in days:
        d0 = datetime.strptime(as_of, "%Y-%m-%d")
        total, detail, missing, stale = 0.0, [], [], []
        for acct in accounts:
            v = db.execute(
                "SELECT * FROM valuations WHERE account_id=? AND as_of<=? "
                "ORDER BY as_of DESC LIMIT 1", (acct["id"], as_of)).fetchone()
            if not v:
                continue  # 该账户尚无任何快照（例如中途新开户）
            stale_days = (d0 - datetime.strptime(v["as_of"], "%Y-%m-%d")).days
            if v["currency"].upper() == base:
                rate, used = 1.0, as_of
            else:
                got = _nearest_rate(db, as_of, v["currency"], base)
                if not got:
                    missing.append({"account_id": acct["id"], "currency": v["currency"]})
                    continue
                rate, used = got
            value_base = v["market_value"] * rate
            total += value_base
            entry = {
                "account_id": acct["id"], "as_of": v["as_of"],
                "value_ccy": v["market_value"], "currency": v["currency"],
                "fx_rate": rate, "fx_as_of": used, "value_base": round(value_base, 2),
                "method": v["method"],
            }
            if stale_days > 0:
                entry["stale_days"] = stale_days
                stale.append(acct["id"])
            detail.append(entry)
        out.append({"as_of": as_of, "total_base": round(total, 2), "detail": detail,
                    "missing_fx": missing, "stale_accounts": stale})
    return out


def net_worth_summary(db: sqlite3.Connection, base: str | None = None) -> dict:
    """最新净值 + 较上一快照日变动（含分账户与币种归因）。"""
    base = base or PROFILE.base_currency
    series = net_worth_series(db, base)
    if not series:
        return {"base": base, "empty": True}
    latest, prev = series[-1], (series[-2] if len(series) >= 2 else None)
    # 分资产层归因：按各账户"最新一次持仓快照"（与结转口径一致）
    # 注意：嵌套查询必须先物化（sqlite3 游标迭代中执行新语句会跳行）
    by_class = {}
    for acct in list(db.execute("SELECT id FROM accounts WHERE is_asset=1")):
        h_day = db.execute(
            "SELECT MAX(as_of) d FROM holdings WHERE account_id=?", (acct["id"],)).fetchone()["d"]
        if not h_day:
            continue
        for h in list(db.execute(
                "SELECT symbol, quantity, currency, price FROM holdings "
                "WHERE account_id=? AND as_of=?", (acct["id"], h_day))):
            got = _nearest_rate(db, h_day, h["currency"], base)
            if not got:
                continue
            value_base = h["quantity"] * (h["price"] or 1.0) * got[0]
            if h["symbol"].startswith("CASH:"):
                key = "cash"
            else:
                ins = db.execute(
                    "SELECT asset_class FROM instruments WHERE symbol=?", (h["symbol"],)
                ).fetchone()
                key = (ins["asset_class"] if ins and ins["asset_class"] else "other") or "other"
            by_class[key] = by_class.get(key, 0.0) + value_base
    delta = None
    if prev:
        delta = {
            "abs": round(latest["total_base"] - prev["total_base"], 2),
            "pct": round((latest["total_base"] / prev["total_base"] - 1) * 100, 2)
            if prev["total_base"] else None,
            "prev_as_of": prev["as_of"],
        }
    return {
        "base": base, "as_of": latest["as_of"], "total": latest["total_base"],
        "delta": delta, "by_asset_class": {k: round(v, 2) for k, v in
                                            sorted(by_class.items(), key=lambda x: -x[1])},
        "missing_fx": latest["missing_fx"], "series": [
            {"as_of": s["as_of"], "total": s["total_base"]} for s in series],
    }
