"""行情 Provider 链：Yahoo chart API（主）→ Stooq CSV（备）。

设计对应架构文档 D4：低频批量 + 本地缓存 + stale 标记。
- Yahoo v8 chart 端点无需登录/crumb，带浏览器 UA 即可（yfinance 同源）
- Stooq 免费但偶发反爬 JS 挑战（实测 2026-10），失败时静默降级
"""
from __future__ import annotations

import csv
import io
import sqlite3
import time
from datetime import datetime, timezone

import httpx

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
STOOQ_LATEST = "https://stooq.com/q/l/"
STOOQ_DAILY = "https://stooq.com/q/d/l/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) WealthOS/0.1"}


def _yahoo_symbol(db: sqlite3.Connection, symbol: str) -> str:
    row = db.execute("SELECT yahoo_symbol FROM instruments WHERE symbol=?", (symbol,)).fetchone()
    return (row["yahoo_symbol"] if row and row["yahoo_symbol"] else symbol)


def _yahoo_latest(client: httpx.Client, symbol: str) -> dict | None:
    r = client.get(f"{YAHOO}/{symbol}", params={"interval": "1d", "range": "5d"})
    if r.status_code != 200:
        return None
    try:
        meta = r.json()["chart"]["result"][0]["meta"]
        price, ts = meta["regularMarketPrice"], meta.get("regularMarketTime")
        if not price or not ts:
            return None
        as_of = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        return {"price": float(price), "as_of": as_of, "currency": meta.get("currency", "")}
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _stooq_latest_batch(client: httpx.Client, mapped: dict[str, str]) -> dict[str, dict]:
    """mapped: {stooq_sym: our_symbol}；失败（含反爬挑战）返回 {}。"""
    syms = " ".join(mapped.keys())
    r = client.get(STOOQ_LATEST, params={"s": syms, "f": "sd2t2ohlcv", "e": "csv"})
    if r.status_code != 200 or not r.text.strip().startswith("Symbol"):
        return {}
    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        sym = mapped.get(row.get("Symbol", ""), "")
        close = _f(row.get("Close"))
        as_of = _stooq_date(row.get("Date"))
        if sym and close and as_of:
            out[sym] = {"price": close, "as_of": as_of, "currency": ""}
    return out


def fetch_latest(db: sqlite3.Connection, symbols: list[str],
                 client: httpx.Client | None = None) -> dict[str, dict]:
    """拉最新报价写 price_latest；Yahoo 主 → Stooq 备。"""
    symbols = [s for s in set(symbols) if not s.startswith("CASH:")]
    if not symbols:
        return {}
    own = client or httpx.Client(timeout=15, headers=UA, follow_redirects=True)
    out: dict[str, dict] = {}
    try:
        stooq_map: dict[str, str] = {}
        for s in symbols:
            q = _yahoo_latest(own, _yahoo_symbol(db, s))
            if q:
                out[s] = q
            else:
                st = _stooq_symbol_of(db, s)
                if st:
                    stooq_map[st] = s
            time.sleep(0.3)  # 礼貌间隔
        if stooq_map:
            out.update(_stooq_latest_batch(own, stooq_map))
        # ③ 雪球兜底（需 BYO Cookie，A股/港美股中文场景）
        missing = [s for s in symbols if s not in out]
        if missing:
            from . import xueqiu as xq_mod

            if xq_mod.configured():
                xq = xq_mod.fetch_quotes(
                    [_yahoo_symbol(db, s) for s in missing], client=own)
                if xq:
                    for s in missing:
                        ysym = _yahoo_symbol(db, s)
                        if xq.get(ysym):
                            out[s] = xq[ysym]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for sym, q in out.items():
            db.execute(
                "INSERT OR REPLACE INTO price_latest(symbol,price,as_of,currency,source,"
                "fetched_at) VALUES(?,?,?,?,?,?)",
                (sym, q["price"], q["as_of"], q.get("currency") or None,
                 "yahoo" if q.get("currency") else "stooq", now),
            )
    finally:
        if client is None:
            own.close()
    return out


def fetch_daily_yahoo(symbol: str, days: int = 90,
                      client: httpx.Client | None = None) -> list[tuple]:
    """拉日 K（Yahoo），返回 [(as_of, close), ...]（不落库，供深研用）。"""
    import datetime as dt

    own = client or httpx.Client(timeout=15, headers=UA)
    try:
        r = own.get(f"{YAHOO}/{symbol}",
                    params={"interval": "1d", "range": f"{max(days, 5)}d"})
        if r.status_code != 200:
            return []
        res = r.json()["chart"]["result"][0]
        ts, closes = res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []
        return [(dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).strftime("%Y-%m-%d"), c)
                for t, c in zip(ts, closes) if c]
    except (KeyError, IndexError, TypeError, ValueError):
        return []
    finally:
        if client is None:
            own.close()


def refresh_holdings_prices(db: sqlite3.Connection, client: httpx.Client | None = None) -> dict:
    """用最新报价刷新最新 holdings 快照的价格（生成"今日"快照 + 重算估值）。"""
    latest = db.execute("SELECT MAX(as_of) d FROM holdings").fetchone()["d"]
    if not latest:
        return {"updated": 0}
    symbols = [r["symbol"] for r in db.execute(
        "SELECT DISTINCT symbol FROM holdings WHERE as_of=? AND symbol NOT LIKE 'CASH:%'",
        (latest,))]
    quotes = fetch_latest(db, symbols, client)
    if not quotes:
        return {"updated": 0, "note": "行情源均不可用，保留快照原价（fail loud，不冒充新数）"}
    today = max(q["as_of"] for q in quotes.values())
    rows = db.execute(
        """SELECT h.id, h.symbol, h.quantity, h.currency, a.currency acc_ccy
           FROM holdings h JOIN accounts a ON a.id=h.account_id WHERE h.as_of=?""",
        (latest,),
    ).fetchall()
    updated = 0
    for h in rows:
        if h["symbol"].startswith("CASH:"):
            db.execute(
                "INSERT OR IGNORE INTO holdings(account_id,as_of,symbol,quantity,currency,"
                "price,source) SELECT account_id,?,symbol,quantity,currency,1,'auto' "
                "FROM holdings WHERE id=?", (today, h["id"]),
            )
            continue
        q = quotes.get(h["symbol"])
        if not q:
            db.execute(
                "INSERT OR IGNORE INTO holdings(account_id,as_of,symbol,quantity,currency,"
                "price,source) SELECT account_id,?,symbol,quantity,currency,price,'carry' "
                "FROM holdings WHERE id=?", (today, h["id"]),
            )
            continue
        db.execute(
            """INSERT INTO holdings(account_id,as_of,symbol,quantity,currency,price,source)
               SELECT account_id,?,symbol,quantity,currency,?, 'auto' FROM holdings WHERE id=?
               ON CONFLICT(account_id,as_of,symbol) DO UPDATE SET price=excluded.price""",
            (today, q["price"], h["id"]),
        )
        updated += 1
    for acct in list(db.execute("SELECT DISTINCT account_id FROM holdings WHERE as_of=?", (today,))):
        mv = db.execute(
            "SELECT SUM(quantity*COALESCE(price,1)) mv FROM holdings "
            "WHERE account_id=? AND as_of=?", (acct["account_id"], today),
        ).fetchone()["mv"]
        cur = db.execute("SELECT currency FROM accounts WHERE id=?",
                         (acct["account_id"],)).fetchone()["currency"]
        db.execute(
            "INSERT OR REPLACE INTO valuations(account_id,as_of,market_value,currency,method) "
            "VALUES(?,?,?,?, 'auto')", (acct["account_id"], today, mv, cur),
        )
    # 币种感知重算（多币种账户按当日汇率归一到账户币种）
    from ..engine.networth import recompute_valuations

    recompute_valuations(db, today)
    return {"updated": updated, "as_of": today, "quotes": len(quotes)}


def _stooq_symbol_of(db: sqlite3.Connection, symbol: str) -> str:
    from .. import db as dbm

    row = db.execute("SELECT stooq_symbol FROM instruments WHERE symbol=?", (symbol,)).fetchone()
    return (row["stooq_symbol"] if row and row["stooq_symbol"] else dbm._stooq_symbol(symbol))


def _f(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "N/D") else None
    except (TypeError, ValueError):
        return None


def _stooq_date(v) -> str | None:
    if not v or v == "N/D":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
