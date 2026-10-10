"""示例数据（演示模式）：一键载入 / 一键清除。

为"从零开始"的用户设计：先看示例理解产品能做什么，
开始记录真实资产时一键清除，绝不与真实数据混淆。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import db as dbm

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "samples"


def load_demo(db: sqlite3.Connection) -> dict:
    if db.execute("SELECT 1 FROM accounts WHERE is_demo=1").fetchone():
        return {"loaded": False, "note": "示例数据已存在"}
    from .importers.csv_import import import_csv
    from .importers.flex import import_flex

    import_csv(SAMPLES / "accounts.csv", db)
    import_csv(SAMPLES / "activities.csv", db)
    import_csv(SAMPLES / "holdings_2026-09-30.csv", db)
    import_csv(SAMPLES / "holdings_2026-10-02.csv", db)
    import_flex(SAMPLES / "flex_sample.xml", db)
    # 标记为示例 + 名称加前缀，任何界面一眼可辨
    db.execute("UPDATE accounts SET is_demo=1, name='示例·' || name")
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('demo_mode','1')")
    return {"loaded": True}


def clear_demo(db: sqlite3.Connection) -> dict:
    demo_ids = [r["id"] for r in db.execute("SELECT id FROM accounts WHERE is_demo=1")]
    if not demo_ids:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('demo_mode','0')")
        return {"cleared": 0, "note": "没有示例数据"}
    qmarks = ",".join("?" * len(demo_ids))
    for table in ("holdings", "valuations", "activities"):
        db.execute(f"DELETE FROM {table} WHERE account_id IN ({qmarks})", demo_ids)
    db.execute(f"DELETE FROM accounts WHERE id IN ({qmarks})", demo_ids)
    db.execute("DELETE FROM exposures")
    db.execute("DELETE FROM entity_edges WHERE edge_type IN ('exposure','has_exposure')")
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('demo_mode','0')")
    return {"cleared": len(demo_ids)}


def is_demo_mode(db: sqlite3.Connection) -> bool:
    row = db.execute("SELECT value FROM meta WHERE key='demo_mode'").fetchone()
    return bool(row and row["value"] == "1")


def counts(db: sqlite3.Connection) -> dict:
    return {
        "accounts": db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"],
        "demo_accounts": db.execute(
            "SELECT COUNT(*) c FROM accounts WHERE is_demo=1").fetchone()["c"],
        "real_accounts": db.execute(
            "SELECT COUNT(*) c FROM accounts WHERE is_demo=0").fetchone()["c"],
    }


def reset_database() -> None:
    """危险操作：清空整个库重建（仅 CLI 显式调用）。"""
    from .config import DB_PATH

    for suffix in ("", "-wal", "-shm"):
        p = Path(str(DB_PATH) + suffix)
        if p.exists():
            p.unlink()
    dbm.init_db()
