"""敞口引擎：五维（币种/国家/行业/资产类别/机构）+ 单一标的集中度。每日确定性重算。"""
from __future__ import annotations

import sqlite3

from ..config import PROFILE
from .networth import _nearest_rate

DIMENSIONS = ["currency", "country", "sector", "asset_class", "institution"]


def compute_exposures(db: sqlite3.Connection, as_of: str | None = None, base: str | None = None) -> dict:
    base = base or PROFILE.base_currency
    if not as_of:
        row = db.execute("SELECT MAX(as_of) d FROM holdings").fetchone()
        as_of = row["d"] if row else None
    if not as_of:
        return {"as_of": None, "empty": True}

    buckets: dict[str, dict[str, float]] = {d: {} for d in DIMENSIONS}
    total = 0.0
    rows = []
    for h in list(db.execute(
            """SELECT h.*, a.currency acc_ccy, a.institution FROM holdings h
               JOIN accounts a ON a.id=h.account_id WHERE h.as_of=?""",
            (as_of,))):
        got = _nearest_rate(db, as_of, h["currency"], base)
        if not got:
            continue
        value = h["quantity"] * (h["price"] or 1.0) * got[0]
        total += value

        if h["symbol"].startswith("CASH:"):
            ins = {"asset_class": "cash", "currency": h["symbol"].split(":", 1)[1],
                   "country": "", "sector": "Cash"}
        else:
            r = db.execute(
                "SELECT asset_class,currency,country,sector FROM instruments WHERE symbol=?",
                (h["symbol"],),
            ).fetchone()
            ins = dict(r) if r else {}
        ccy = ins.get("currency") or h["currency"]
        buckets["currency"][ccy] = buckets["currency"].get(ccy, 0.0) + value
        buckets["country"][ins.get("country") or "unknown"] = \
            buckets["country"].get(ins.get("country") or "unknown", 0.0) + value
        buckets["sector"][ins.get("sector") or "unknown"] = \
            buckets["sector"].get(ins.get("sector") or "unknown", 0.0) + value
        ac = ins.get("asset_class") or "other"
        buckets["asset_class"]["cash" if h["symbol"].startswith("CASH:") else ac] = \
            buckets["asset_class"].get("cash" if h["symbol"].startswith("CASH:") else ac, 0.0) + value
        buckets["institution"][h["institution"]] = \
            buckets["institution"].get(h["institution"], 0.0) + value
        rows.append({"symbol": h["symbol"], "value_base": round(value, 2), "pct": None})

    if total <= 0:
        return {"as_of": as_of, "empty": True}

    result = {"as_of": as_of, "base": base, "total": round(total, 2)}
    for dim in DIMENSIONS:
        result[dim] = [
            {"key": k, "value_base": round(v, 2), "pct": round(v / total * 100, 2)}
            for k, v in sorted(buckets[dim].items(), key=lambda x: -x[1])
        ]
    # 单一标的集中度（非现金）
    sym_total = {}
    for r in rows:
        sym_total[r["symbol"]] = sym_total.get(r["symbol"], 0.0) + r["value_base"]
    result["single_symbol"] = [
        {"key": k, "value_base": round(v, 2), "pct": round(v / total * 100, 2)}
        for k, v in sorted(sym_total.items(), key=lambda x: -x[1])
    ]
    return result


def persist_exposures(db: sqlite3.Connection, exp: dict) -> None:
    for dim in DIMENSIONS + ["single_symbol"]:
        for row in exp.get(dim, []):
            db.execute(
                """INSERT INTO exposures(as_of,dimension,key,value_base,pct)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(as_of,dimension,key) DO UPDATE SET
                     value_base=excluded.value_base, pct=excluded.pct""",
                (exp["as_of"], dim, row["key"], row["value_base"], row["pct"]),
            )
