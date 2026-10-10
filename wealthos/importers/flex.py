"""IBKR Flex Query XML 解析器（MVP：CashBalance/Position/TradeConfirmation/CorporateAction 子集）。"""
from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import db as dbm

_DIV_MAP = {"DIV": "DIVIDEND", "DIVCASH": "DIVIDEND", "DIVACC": "DIVIDEND"}


def parse_flex(path: str | Path) -> dict:
    """解析但不落库，返回结构化 dict（便于测试）。"""
    root = ET.parse(path).getroot()
    stmts = []
    for stmt in root.iter("FlexStatement"):
        acct_info = stmt.find("AccountInformation")
        account_id = acct_info.get("accountId") if acct_info is not None else stmt.get("accountId")
        base_ccy = acct_info.get("currency", "USD") if acct_info is not None else "USD"
        when = stmt.get("whenGenerated", "")
        as_of = _flex_date(when[:8] if when else stmt.get("toDate", ""))

        cash = [
            {"currency": cb.get("currency", "USD"), "amount": float(cb.get("amount", "0"))}
            for cb in stmt.iter("CashBalance")
        ]
        positions = [
            {
                "symbol": p.get("symbol"), "quantity": float(p.get("quantity", "0")),
                "currency": p.get("currency", base_ccy),
                "price": float(p.get("markPrice")) if p.get("markPrice") else None,
                "cost_basis": float(p.get("costBasis")) if p.get("costBasis") else None,
            }
            for p in stmt.iter("Position") if p.get("securityType") in (None, "STK", "ETF")
        ]
        trades = [
            {
                "symbol": t.get("symbol"), "quantity": float(t.get("quantity", "0")),
                "price": float(t.get("tradePrice", "0")),
                "currency": t.get("currency", base_ccy),
                "fees": abs(float(t.get("ibCommission", "0"))),
                "date": _flex_date(t.get("tradeDate", "")),
            }
            for t in stmt.iter("TradeConfirmation")
        ]
        dividends = [
            {"symbol": ca.get("symbol"), "value": float(ca.get("value", "0")),
             "currency": ca.get("currency", base_ccy), "date": _flex_date(ca.get("exDate", ""))}
            for ca in stmt.iter("CorporateAction") if ca.get("type") in _DIV_MAP
        ]
        stmts.append({
            "account_id": account_id, "base_ccy": base_ccy, "as_of": as_of,
            "cash": cash, "positions": positions, "trades": trades, "dividends": dividends,
        })
    if not stmts:
        raise ValueError("Flex XML 中未找到 FlexStatement")
    return {"statements": stmts}


def import_flex(path: str | Path, conn: sqlite3.Connection | None = None) -> dict:
    parsed = parse_flex(path)
    if conn is not None:
        return _apply(parsed, conn)
    with dbm.get_db() as db:
        return _apply(parsed, db)


def _apply(parsed: dict, db: sqlite3.Connection) -> dict:
    n_cash = n_pos = n_tr = 0
    for st in parsed["statements"]:
        acct_name = f"IBKR {st['account_id']}"
        db.execute(
            """INSERT INTO accounts(name,institution,country,currency,account_type,is_asset)
               VALUES(?,?, 'US',?, 'brokerage',1)
               ON CONFLICT(name) DO UPDATE SET currency=excluded.currency""",
            (acct_name, "Interactive Brokers", st["base_ccy"]),
        )
        acct = db.execute("SELECT id FROM accounts WHERE name=?", (acct_name,)).fetchone()["id"]
        as_of = st["as_of"]

        for c in st["cash"]:
            db.execute(
                """INSERT INTO holdings(account_id,as_of,symbol,quantity,currency,price,source)
                   VALUES(?,?,?,?,?,1,'flex')
                   ON CONFLICT(account_id,as_of,symbol) DO UPDATE SET quantity=excluded.quantity""",
                (acct, as_of, f"CASH:{c['currency']}", c["amount"], c["currency"]),
            )
            n_cash += 1
        for p in st["positions"]:
            db.execute(
                """INSERT INTO holdings(account_id,as_of,symbol,quantity,currency,price,source)
                   VALUES(?,?,?,?,?,?,'flex')
                   ON CONFLICT(account_id,as_of,symbol) DO UPDATE SET
                     quantity=excluded.quantity, price=excluded.price""",
                (acct, as_of, p["symbol"], p["quantity"], p["currency"], p["price"]),
            )
            _ensure(db, p["symbol"], p["currency"])
            n_pos += 1
        for t in st["trades"]:
            qty, price = abs(t["quantity"]), t["price"]
            db.execute(
                """INSERT INTO activities(account_id,symbol,activity_type,quantity,price,currency,
                                          fees,trade_date,source)
                   VALUES(?,?,?,?,?,?,?,?,'flex')
                   ON CONFLICT(account_id,symbol,activity_type,quantity,price,trade_date) DO NOTHING""",
                (acct, t["symbol"], "BUY" if t["quantity"] >= 0 else "SELL",
                 qty, price, t["currency"], t["fees"], t["date"]),
            )
            _ensure(db, t["symbol"], t["currency"])
            n_tr += 1
        for d in st["dividends"]:
            db.execute(
                """INSERT INTO activities(account_id,symbol,activity_type,quantity,price,currency,
                                          fees,trade_date,source)
                   VALUES(?,?, 'DIVIDEND',1,?,?,0,?,'flex')
                   ON CONFLICT(account_id,symbol,activity_type,quantity,price,trade_date) DO NOTHING""",
                (acct, d["symbol"], d["value"], d["currency"], d["date"]),
            )
        # 重算该账户当日估值（币种感知：JPY 现金等按汇率换算入 USD 基准）
        from ..engine.networth import recompute_valuations

        recompute_valuations(db, as_of)
    return {"kind": "flex", "cash": n_cash, "positions": n_pos, "trades": n_tr}


def _ensure(db: sqlite3.Connection, symbol: str, currency: str) -> None:
    if db.execute("SELECT 1 FROM instruments WHERE symbol=?", (symbol,)).fetchone():
        return
    db.execute(
        """INSERT INTO instruments(symbol,asset_class,currency,stooq_symbol,yahoo_symbol,updated_at)
           VALUES(?,'equity',?,?,?,datetime('now'))""",
        (symbol, currency, dbm._stooq_symbol(symbol), symbol),
    )


def _flex_date(s: str) -> str:
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s
