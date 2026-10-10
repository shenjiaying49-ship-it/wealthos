"""Roadmap Agent：新手路线图（阶段内容 + 与真实数据联动的完成状态）。"""
from __future__ import annotations

import json
import sqlite3

from ..config import CONFIG_DIR, PROFILE


def _load_stages() -> list[dict]:
    import yaml

    cfg = yaml.safe_load((CONFIG_DIR / "roadmap.yaml").read_text())
    return cfg.get("stages", [])


def _manual_done(db: sqlite3.Connection) -> set[str]:
    row = db.execute("SELECT value FROM meta WHERE key='roadmap_done'").fetchone()
    return set(json.loads(row["value"])) if row and row["value"] else set()


def _set_manual_done(db: sqlite3.Connection, done: set[str]) -> None:
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('roadmap_done',?)",
               (json.dumps(sorted(done)),))


def _auto_checks(db: sqlite3.Connection) -> dict:
    """基于真实账户（排除示例）的自动判定 + 上下文数字。"""
    real = "SELECT id FROM accounts WHERE is_demo=0"
    ids = [r["id"] for r in db.execute(real)]
    ids_q = ",".join(str(i) for i in ids) or "-1"

    def one(sql: str) -> float:
        return db.execute(sql).fetchone()[0] or 0

    cash_rows = list(db.execute(
        f"""SELECT h.quantity, h.currency FROM holdings h
            WHERE h.account_id IN ({ids_q}) AND h.symbol LIKE 'CASH:%'"""))
    invested = one(f"SELECT COUNT(*) FROM holdings h WHERE h.account_id IN ({ids_q}) "
                   f"AND h.symbol NOT LIKE 'CASH:%'")
    from ..engine.networth import _nearest_rate

    base = PROFILE.base_currency
    cash_total = 0.0
    for h in cash_rows:
        got = _nearest_rate(db, _latest_day(db), h["currency"], base) \
            if h["currency"].upper() != base else (1.0, "")
        if got:
            cash_total += h["quantity"] * got[0]
    lessons = one("SELECT COUNT(*) FROM lessons")
    return {
        "cash_recorded": len(cash_rows) > 0,
        "investment_started": invested > 0,
        "_ctx": {
            "real_accounts": len(ids),
            "cash_total_base": round(cash_total, 2),
            "lessons_learned": int(lessons),
            "base": base,
        },
    }


def _latest_day(db: sqlite3.Connection) -> str:
    return db.execute("SELECT MAX(as_of) d FROM holdings").fetchone()["d"] \
        or "2000-01-01"


def get_roadmap(db: sqlite3.Connection) -> dict:
    stages = _load_stages()
    auto = _auto_checks(db)
    manual = _manual_done(db)
    ctx = auto.pop("_ctx")
    out = []
    for st in stages:
        auto_ok = bool(auto.get(st.get("auto_check", ""))) if st.get("auto_check") != "manual" \
            else False
        done = auto_ok or st["id"] in manual
        out.append({
            "id": st["id"], "title": st["title"], "goal": st.get("goal", ""),
            "prereq_note": st.get("prereq_note"),
            "auto_check": st.get("auto_check", "manual"),
            "auto_done": auto_ok, "manual_done": st["id"] in manual,
            "done": done,
            "cards": [
                {k: v for k, v in card.items()
                 if k in ("id", "title", "why", "how", "prereq", "cost", "risk",
                          "fits", "not_fits", "alternatives", "evidence")}
                for card in st.get("cards", [])
            ],
        })
    return {"stages": out, "context": ctx}


def toggle_manual(db: sqlite3.Connection, stage_id: str) -> dict:
    stages = {s["id"] for s in _load_stages()}
    if stage_id not in stages:
        raise ValueError(f"未知阶段: {stage_id}")
    done = _manual_done(db)
    if stage_id in done:
        done.discard(stage_id)
    else:
        done.add(stage_id)
    _set_manual_done(db, done)
    return {"stage_id": stage_id, "manual_done": stage_id in done}
