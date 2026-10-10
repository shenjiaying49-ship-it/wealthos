"""华尔街见闻（wallstreetcn）快讯摄取：公开 JSON API，免认证（Agent-Reach 方法论：平台公开通道）。

频道：global-channel 全球快讯（另可选 a-stock-channel / us-stock-channel / hk-channel / forex-channel）。
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

import httpx

from .dedup import canonical_url, dedup_key, is_near_duplicate_titles

API = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wealthos/0.1"}
SOURCE_ID = "wscn_global"


def _strip_html(html: str, limit: int = 400) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_items(payload: dict) -> list[dict]:
    out = []
    for it in (payload.get("data", {}) or {}).get("items", []) or []:
        title = (it.get("title") or "").strip()
        body_html = it.get("content") or it.get("content_text") or ""
        text = _strip_html(body_html)
        title = title or (text[:60] if text else "")
        if not title:
            continue
        ts = it.get("source_time") or it.get("display_time")
        try:
            published = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(
                timespec="seconds") if ts else ""
        except (TypeError, ValueError):
            published = ""
        out.append({
            "title": title, "summary": text,
            "url": canonical_url(it.get("uri") or f"wscn:{ts or title}"),
            "published_at": published,
        })
    return out


def fetch(db: sqlite3.Connection, channel: str = "global-channel", limit: int = 20,
          client: httpx.Client | None = None) -> dict:
    src = db.execute("SELECT * FROM sources WHERE id=?", (SOURCE_ID,)).fetchone()
    if not src or not src["enabled"]:
        return {"source": SOURCE_ID, "status": "disabled", "new": 0}
    own = client or httpx.Client(timeout=15, headers=UA)
    status, new_items, err = "ok", 0, None
    try:
        r = own.get(API, params={"channel": channel, "limit": limit})
        if r.status_code != 200:
            status = f"http_{r.status_code}"
        else:
            recent = [
                (row["title"], (row["published_at"] or "")[:10])
                for row in db.execute(
                    "SELECT title, published_at FROM items "
                    "WHERE published_at >= datetime('now','-1 day') ORDER BY id DESC LIMIT 200")]
            for e in parse_items(r.json()):
                if _store(db, e, recent):
                    new_items += 1
            if new_items == 0 and not parse_items(r.json()):
                status = "empty"
    except Exception as exc:  # noqa: BLE001
        status, err = "error", str(exc)[:200]
    finally:
        if client is None:
            own.close()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("UPDATE sources SET last_fetch=?, last_status=? WHERE id=?",
               (now, status, SOURCE_ID))
    db.execute("INSERT INTO fetch_log(job,target,status,detail,items,ts) VALUES(?,?,?,?,?,?)",
               ("wscn", SOURCE_ID, status, err, new_items, now))
    return {"source": SOURCE_ID, "status": status, "new": new_items}


def _store(db: sqlite3.Connection, item: dict, recent_titles: list[tuple[str, str]]) -> bool:
    title, url = item["title"], item["url"]
    day = item["published_at"][:10] or datetime.now(timezone.utc).date().isoformat()
    if recent_titles and is_near_duplicate_titles(title, day, recent_titles):
        return False
    key = dedup_key(url if url.startswith("http") else "", title)
    try:
        db.execute(
            """INSERT INTO items(source_id,ext_id,title,summary,url,published_at,fetched_at,
                                 dedup_key,content_hash,label)
               VALUES(?,?,?,?,?,?,?,?,?,'fact')""",
            (SOURCE_ID, "", title, item["summary"][:400], url or "",
             item["published_at"] or now_iso(), now_iso(), key, key))
        return True
    except sqlite3.IntegrityError:
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
