"""雪球行情（Agent-Reach finance.md 方法）：BYO 最小 Cookie（仅 xq_a_token）。

雪球公开行情接口无 Cookie 返回 403（实测 2026-10）。合规路径与 Agent-Reach 一致：
用户显式授权自己的登录态，只取 xq_a_token 一项，绝不采集其他 Cookie。
获取方式（任选其一）：
  a) Chrome 登录雪球后运行：agent-reach configure --from-browser chrome --platform xueqiu
     再从 ~/.agent-reach 提取 xq_a_token（或直接把整段 cookie 值给 WEALTHOS_XUEQIU_COOKIE）
  b) 浏览器 F12 → Network → 任一 stock.xueqiu.com 请求 → Cookie 里复制 xq_a_token=… 的值
未配置时本 provider 静默关闭（行情走 Yahoo/Stooq）。
"""
from __future__ import annotations

import os
import sqlite3

import httpx

QUOTE_API = "https://stock.xueqiu.com/v5/stock/batch/quote.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wealthos/0.1"}


def cookie() -> str:
    v = os.environ.get("WEALTHOS_XUEQIU_COOKIE", "")
    return v if v.startswith("xq_a_token") else (f"xq_a_token={v}" if v else "")


def configured() -> bool:
    return bool(cookie())


def fetch_quotes(symbols: list[str],
                 client: httpx.Client | None = None) -> dict[str, dict] | None:
    """{symbol: {price, as_of}}；未配置 cookie 或失败返回 None。"""
    ck = cookie()
    if not ck or not symbols:
        return None
    own = client or httpx.Client(timeout=15, headers=UA)
    try:
        r = own.get(QUOTE_API, params={"symbol": ",".join(symbols)},
                    headers={"Cookie": ck})
        if r.status_code != 200:
            return None
        out = {}
        for item in (r.json().get("data") or {}).get("items") or []:
            q = item.get("quote") or {}
            if q.get("current"):
                from datetime import datetime, timezone

                ts = q.get("time")
                as_of = (datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
                         if isinstance(ts, (int, float)) else None)
                out[item.get("symbol", "")] = {
                    "price": float(q["current"]),
                    "as_of": as_of,
                    "currency": q.get("currency", ""),
                }
        return out or None
    except (ValueError, httpx.HTTPError):
        return None
    finally:
        if client is None:
            own.close()


def fetch_latest_into(db: sqlite3.Connection, symbols: list[str],
                      client: httpx.Client | None = None) -> dict:
    """拉报价写 price_latest（作为 Yahoo/Stooq 之后的中国市场兜底）。"""
    quotes = fetch_quotes(symbols, client)
    if not quotes:
        return {"updated": 0}
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for sym, q in quotes.items():
        if q["price"] and q["as_of"]:
            db.execute(
                "INSERT OR REPLACE INTO price_latest(symbol,price,as_of,currency,source,"
                "fetched_at) VALUES(?,?,?,?,?,?)",
                (sym, q["price"], q["as_of"], q.get("currency") or None, "xueqiu", now))
    return {"updated": len(quotes)}
