"""SQLite 连接与迁移。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH, PKG_DIR, ensure_dirs

SCHEMA = (PKG_DIR / "schema.sql").read_text()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    ensure_dirs()
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db(db_path: Path | str | None = None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """建表 + 灌种子（幂等）。"""
    with get_db(db_path) as db:
        db.executescript(SCHEMA)
        _seed_sources(db)
        _seed_graph(db)
        _seed_lessons(db)
        _seed_meta(db)


def _seed_meta(db: sqlite3.Connection) -> None:
    from .config import PROFILE

    db.execute(
        "INSERT OR IGNORE INTO meta(key,value) VALUES('base_currency',?)",
        (PROFILE.base_currency,),
    )


def _seed_sources(db: sqlite3.Connection) -> None:
    import yaml

    from .config import CONFIG_DIR

    cfg = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text())
    for s in cfg.get("sources", []):
        db.execute(
            """INSERT OR IGNORE INTO sources(id,name,kind,tier,reliability,url,interval_min,enabled)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                s["id"], s.get("name"), s.get("kind", "rss"), s.get("tier", "news"),
                s.get("reliability", "Medium"), s.get("url", ""),
                s.get("interval_min", 30), 1 if s.get("enabled", True) else 0,
            ),
        )


def _seed_graph(db: sqlite3.Connection) -> None:
    import json

    import yaml

    from .config import CONFIG_DIR

    cfg = yaml.safe_load((CONFIG_DIR / "entities.yaml").read_text())
    for e in cfg.get("entities", []):
        db.execute(
            "INSERT OR IGNORE INTO entities(id,type,name,aliases_json) VALUES(?,?,?,?)",
            (e["id"], e.get("type"), e.get("name"), json.dumps(e.get("aliases", []), ensure_ascii=False)),
        )
    for f, et, t, w in cfg.get("edges", []):
        db.execute(
            "INSERT OR IGNORE INTO entity_edges(from_entity,edge_type,to_entity,weight) VALUES(?,?,?,?)",
            (f, et, t, w),
        )
    for i in cfg.get("instruments", []):
        sym = i["symbol"]
        stooq = _stooq_symbol(sym)
        yahoo = sym if sym in ("AAPL", "MSFT", "NVDA", "VOO", "BTC") else sym
        db.execute(
            """INSERT OR IGNORE INTO instruments(symbol,name,asset_class,currency,country,sector,region,stooq_symbol,yahoo_symbol,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (sym, i.get("name"), i.get("asset_class"), i.get("currency"),
             _region_to_country(i.get("region")), i.get("sector"), i.get("region"), stooq, yahoo),
        )


def _region_to_country(region: str | None) -> str:
    return {"RGN:US": "US", "RGN:HK": "HK", "RGN:JP": "JP", "RGN:SG": "SG",
            "RGN:CN": "CN", "RGN:EU": "EU"}.get(region or "", "")


def _stooq_symbol(symbol: str) -> str:
    """标准符号 → stooq 符号（0700.HK→0700.hk, 1321.T→1321.jp, 其余小写.us）。"""
    if symbol.startswith("CASH:"):
        return ""
    if "." in symbol:
        base, suffix = symbol.rsplit(".", 1)
        suffix = {"T": "jp"}.get(suffix.upper(), suffix.lower())
        return f"{base}.{suffix}"
    if symbol == "BTC":
        return "btcusd"
    return f"{symbol.lower()}.us"


def _seed_lessons(db: sqlite3.Connection) -> None:
    import json

    import yaml

    from .config import CONFIG_DIR

    cfg = yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())
    for ls in cfg.get("lessons", []):
        db.execute(
            """INSERT OR IGNORE INTO knowledge_nodes(concept,domain,prereq_json,importance,status)
               VALUES(?,?,?,?, 'unknown')""",
            (ls["concept"], ls.get("domain"), json.dumps(ls.get("prereq", [])), ls.get("importance", 3)),
        )


def snapshot_hash(db: sqlite3.Connection) -> str:
    """数据快照哈希（FinSight-AI 模式）：关键表的行数+最大时间聚合。"""
    import hashlib

    parts = []
    for table, ts_col in [
        ("holdings", "as_of"), ("valuations", "as_of"), ("activities", "trade_date"),
        ("fx_rates", "as_of"), ("price_daily", "as_of"), ("items", "fetched_at"),
    ]:
        row = db.execute(
            f"SELECT COUNT(*) c, COALESCE(MAX({ts_col}),'') m FROM {table}"
        ).fetchone()
        parts.append(f"{table}:{row['c']}:{row['m']}")
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
