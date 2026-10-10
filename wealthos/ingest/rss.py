"""RSS 摄取：Collect → Filter（三级去重）→ 打标签 → 存 items。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import feedparser
import httpx

from .dedup import canonical_url, dedup_key, is_near_duplicate_titles

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wealthos/0.1"}
# 快讯类源给 [事实] 初标，评论类给 [观点]；后续 LLM/验证层可改写
_TIER_LABEL = {"official": "fact", "news": "fact", "newsletter": "analysis", "social": "signal"}


def fetch_source(db: sqlite3.Connection, source_id: str,
                 client: httpx.Client | None = None) -> dict:
    src = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if not src or not src["enabled"]:
        return {"source": source_id, "status": "disabled", "new": 0}
    own = client or httpx.Client(timeout=20, headers=UA, follow_redirects=True)
    status, new_items, err = "ok", 0, None
    try:
        r = own.get(src["url"])
        if r.status_code != 200:
            status = f"http_{r.status_code}"
        else:
            parsed = feedparser.parse(r.text)
            for e in parsed.entries:
                if _store_item(db, src, e):
                    new_items += 1
            if not parsed.entries:
                status = "empty"
    except Exception as exc:  # noqa: BLE001 — 摄取层必须吞错并留痕
        status, err = "error", str(exc)[:200]
    finally:
        if client is None:
            own.close()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("UPDATE sources SET last_fetch=?, last_status=? WHERE id=?",
               (now, status, source_id))
    db.execute("INSERT INTO fetch_log(job,target,status,detail,items,ts) VALUES(?,?,?,?,?,?)",
               ("rss", source_id, status, err, new_items, now))
    return {"source": source_id, "status": status, "new": new_items}


def _store_item(db: sqlite3.Connection, src, entry) -> bool:
    title = (entry.get("title") or "").strip()
    if not title:
        return False
    url = entry.get("link", "")
    published = _pub_datetime(entry)
    key = dedup_key(url, title)

    # 二级去重：同日窗口内标题近似（token Jaccard）
    day = published[:10]
    recent_titles = [
        (r["title"], (r["published_at"] or "")[:10])
        for r in db.execute(
            "SELECT title, published_at FROM items "
            "WHERE published_at >= date(?, '-1 day') ORDER BY id DESC LIMIT 200",
            (day or datetime.now(timezone.utc).date().isoformat(),),
        )
    ]
    if recent_titles and is_near_duplicate_titles(title, day or "2000-01-01", recent_titles):
        return False

    try:
        db.execute(
            """INSERT INTO items(source_id,ext_id,title,summary,url,published_at,fetched_at,
                                 dedup_key,content_hash,label)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                src["id"], entry.get("id", ""),
                title, _clean_summary(entry.get("summary", "")), canonical_url(url),
                published, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                key, key, _TIER_LABEL.get(src["tier"], "fact"),
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False  # dedup_key 撞车 = 一级去重生效


def _clean_summary(html: str, limit: int = 400) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _pub_datetime(entry) -> str:
    for attr in ("published", "updated"):
        v = entry.get(attr)
        if v:
            try:
                from time import mktime

                return datetime.fromtimestamp(mktime(entry.get(f"{attr}_parsed")),
                                              tz=timezone.utc).isoformat(timespec="seconds")
            except (KeyError, TypeError, ValueError):
                return v[:19]
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_all(db: sqlite3.Connection, client: httpx.Client | None = None) -> dict:
    ids = [r["id"] for r in db.execute("SELECT id FROM sources WHERE enabled=1 AND kind='rss'")]
    results = {"new": 0, "ok": 0, "failed": []}
    for sid in ids:
        r = fetch_source(db, sid, client)
        if r["status"] in ("ok", "empty"):
            results["ok"] += 1
        else:
            results["failed"].append(f"{sid}:{r['status']}")
        results["new"] += r.get("new", 0)
    return results
