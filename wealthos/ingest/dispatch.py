"""摄取调度：按 sources.kind 分发到各抓取器（RSS / WSCN / …）。"""
from __future__ import annotations

import sqlite3


def fetch_all(db: sqlite3.Connection) -> dict:
    from . import rss, wscn

    results = {"new": 0, "ok": 0, "failed": []}
    rss_r = rss.fetch_all(db)  # 现有 RSS 源
    results["new"] += rss_r.get("new", 0)
    results["ok"] += rss_r.get("ok", 0)
    results["failed"] += rss_r.get("failed", [])
    w = wscn.fetch(db)
    if w["status"] in ("ok", "empty"):
        results["ok"] += 1
    else:
        results["failed"].append(f"{w['source']}:{w['status']}")
    results["new"] += w.get("new", 0)
    return results
