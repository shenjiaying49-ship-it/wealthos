"""汇率 Provider：frankfurter（无 key、开源、可自托管）为首选，ECB 直连兜底。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

FRANKFURTER = "https://api.frankfurter.dev"  # 2026 版域名（.app 旧域 301 且路径错位）


def fetch_fx_latest(db: sqlite3.Connection, currencies: list[str], base: str = "USD",
                    client: httpx.Client | None = None) -> int:
    """拉当日（或最近交易日）USD 基准汇率并落库。返回写入行数。"""
    want = [c.upper() for c in currencies if c.upper() != base]
    if not want:
        return 0
    own = client or httpx.Client(timeout=15, headers={"User-Agent": "wealthos/0.1"},
                                 follow_redirects=True)
    try:
        # 尝试最近 5 个日历日（周末无 ECB 数据）
        d = datetime.now(timezone.utc).date()
        for _ in range(5):
            r = own.get(f"{FRANKFURTER}/v1/{d.isoformat()}",
                        params={"base": base, "symbols": ",".join(want)})
            if r.status_code == 200:
                return _store(db, r.json(), base)
            d -= timedelta(days=1)
        raise RuntimeError(f"frankfurter 连续 5 天无数据: HTTP {r.status_code}")
    finally:
        if client is None:
            own.close()


def _store(db: sqlite3.Connection, payload: dict, base: str) -> int:
    as_of, rates = payload["date"], payload.get("rates", {})
    n = 0
    for ccy, rate in rates.items():
        db.execute(
            "INSERT OR REPLACE INTO fx_rates(as_of,base_ccy,quote_ccy,rate,source) "
            "VALUES(?,?,?,?, 'frankfurter')",
            (as_of, base, ccy.upper(), float(rate)),
        )
        n += 1
    return n


def fx_for_dates(db: sqlite3.Connection, dates: list[str], currencies: list[str],
                 base: str = "USD") -> int:
    """为指定历史日期补汇率（净值回算用）。"""
    own = httpx.Client(timeout=15, headers={"User-Agent": "wealthos/0.1"},
                       follow_redirects=True)
    n = 0
    try:
        for d in dates:
            have = db.execute(
                "SELECT COUNT(*) c FROM fx_rates WHERE as_of=?", (d,)).fetchone()["c"]
            if have >= len(currencies):
                continue
            r = own.get(f"{FRANKFURTER}/v1/{d}",
                        params={"base": base, "symbols": ",".join(
                            [c for c in currencies if c != base])})
            if r.status_code == 200:
                n += _store(db, r.json(), base)
    finally:
        own.close()
    return n
