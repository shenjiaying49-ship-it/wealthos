"""导入器：accounts / holdings / activities CSV（自动识别类型）。"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .. import db as dbm

ACTIVITY_TYPES = {
    "BUY", "SELL", "DIVIDEND", "FEE", "INTEREST",
    "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "CONVERSION",
}


def sniff_kind(path: Path) -> str:
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = [h.strip().lower() for h in next(csv.reader(f))]
    cols = set(header)
    if {"account", "institution"} <= cols or "institution" in cols:
        return "accounts"
    if "activity_type" in cols:
        return "activities"
    if "as_of" in cols and "symbol" in cols:
        return "holdings"
    raise ValueError(f"无法识别 CSV 类型（表头: {header}）——支持 accounts/holdings/activities")


def import_csv(path: str | Path, conn: sqlite3.Connection | None = None) -> dict:
    path = Path(path)
    kind = sniff_kind(path)
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    if conn is not None:
        return _apply(kind, rows, conn)
    with dbm.get_db() as db:
        return _apply(kind, rows, db)


def _apply(kind: str, rows: list[dict], db: sqlite3.Connection) -> dict:
    counts = {"accounts": 0, "holdings": 0, "activities": 0}
    if kind == "accounts":
        for r in rows:
            db.execute(
                """INSERT INTO accounts(name,institution,country,currency,account_type,is_asset,opened_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(name) DO UPDATE SET institution=excluded.institution,
                     country=excluded.country, currency=excluded.currency,
                     account_type=excluded.account_type""",
                (
                    r["name"].strip(), r["institution"].strip(), r.get("country", "").strip(),
                    r["currency"].strip().upper(), r.get("account_type", "bank").strip(),
                    1 if r.get("is_asset", "true").strip().lower() != "false" else 0,
                    r.get("opened_at", "").strip() or None,
                ),
            )
            counts["accounts"] += 1
    elif kind == "holdings":
        _import_holdings(rows, db, counts)
    else:
        _import_activities(rows, db, counts)
    return {"kind": kind, **counts}


def _import_holdings(rows: list[dict], db: sqlite3.Connection, counts: dict) -> None:
    for r in rows:
        acct = _account_id(db, r["account"].strip())
        symbol = r["symbol"].strip()
        as_of = _iso_date(r["as_of"].strip())
        price = float(r["price"]) if r.get("price") else None
        db.execute(
            """INSERT INTO holdings(account_id,as_of,symbol,quantity,currency,price,source)
               VALUES(?,?,?,?,?,?, 'csv')
               ON CONFLICT(account_id,as_of,symbol) DO UPDATE SET
                 quantity=excluded.quantity, price=excluded.price, currency=excluded.currency""",
            (acct, as_of, symbol, float(r["quantity"]), r["currency"].strip().upper(), price),
        )
        counts["holdings"] += 1
        _ensure_instrument(db, symbol, r["currency"].strip().upper())
    # 每个导入日重算 valuations
    for as_of in {r["as_of"].strip() for r in rows}:
        _recompute_valuation(db, _iso_date(as_of))


def _import_activities(rows: list[dict], db: sqlite3.Connection, counts: dict) -> None:
    for r in rows:
        t = r["activity_type"].strip().upper()
        if t not in ACTIVITY_TYPES:
            raise ValueError(f"未知 activity_type: {t}（合法: {sorted(ACTIVITY_TYPES)}）")
        acct = _account_id(db, r["account"].strip())
        db.execute(
            """INSERT INTO activities(account_id,symbol,activity_type,quantity,price,currency,
                                     fees,trade_date,source)
               VALUES(?,?,?,?,?,?,?,?, 'csv')
               ON CONFLICT(account_id,symbol,activity_type,quantity,price,trade_date) DO NOTHING""",
            (
                acct, r["symbol"].strip(), t, float(r["quantity"]),
                float(r["price"]) if r.get("price") else None,
                r["currency"].strip().upper(),
                float(r.get("fees") or 0), _iso_date(r["trade_date"].strip()),
            ),
        )
        counts["activities"] += 1
        _ensure_instrument(db, r["symbol"].strip(), r["currency"].strip().upper())


def _recompute_valuation(db: sqlite3.Connection, as_of: str) -> None:
    """按当日 holdings 重算各账户估值（币种感知，见 engine.networth.recompute_valuations）。"""
    from ..engine.networth import recompute_valuations

    recompute_valuations(db, as_of)


def _account_id(db: sqlite3.Connection, name: str) -> int:
    row = db.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    raise ValueError(f"账户不存在: {name}（请先导入 accounts.csv）")


def _ensure_instrument(db: sqlite3.Connection, symbol: str, currency: str) -> None:
    if symbol.startswith("CASH:"):
        return
    exists = db.execute("SELECT 1 FROM instruments WHERE symbol=?", (symbol,)).fetchone()
    if not exists:
        stooq = dbm._stooq_symbol(symbol)
        db.execute(
            """INSERT INTO instruments(symbol,asset_class,currency,stooq_symbol,yahoo_symbol,updated_at)
               VALUES(?,'equity',?,?,?,datetime('now'))""",
            (symbol, currency, stooq, symbol),
        )


def _iso_date(s: str) -> str:
    s = s.strip()
    if len(s) == 8 and s.isdigit():  # 20261002
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s
