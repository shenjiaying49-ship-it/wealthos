"""Education Agent：知识图谱 → 每日一课选择（架构文档 I3 的 MVP 版）。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date


def pick_lesson(db: sqlite3.Connection, today: str | None = None) -> dict | None:
    """选择今日概念：缺口优先 × 重要度 × 前置就绪 × 反重复。"""
    import yaml

    from ..config import CONFIG_DIR

    cfg = yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())
    by_concept = {l["concept"]: l for l in cfg.get("lessons", [])}
    nodes = {r["concept"]: dict(r) for r in db.execute("SELECT * FROM knowledge_nodes")}
    today = today or date.today().isoformat()
    recent = {r["concept"] for r in db.execute(
        "SELECT concept FROM lessons WHERE date >= date(?, '-14 day')", (today,))}

    gap = {"unknown": 3.0, "learning": 2.0, "weak": 2.0, "known": 1.0}

    def prereq_ready(concept: str) -> bool:
        node = nodes.get(concept)
        if not node:
            return False
        for p in json.loads(node["prereq_json"] or "[]"):
            if nodes.get(p, {}).get("status") != "known":
                return False
        return True

    best, best_score = None, -1.0
    for concept, node in nodes.items():
        if concept in recent:
            continue
        score = gap.get(node["status"], 1.5) * (node["importance"] or 3)
        if prereq_ready(concept):
            score *= 1.5
        # 弱知识点优先复习
        if node["status"] == "weak":
            score *= 1.3
        if score > best_score:
            best, best_score = concept, score
    if not best or best not in by_concept:
        return None
    lesson = dict(by_concept[best])
    lesson["status"] = nodes[best]["status"]
    return lesson


def record_lesson(db: sqlite3.Connection, lesson: dict, today: str,
                  answer_correct: bool | None = None) -> None:
    db.execute(
        "INSERT OR REPLACE INTO lessons(concept,date,content_json,result) VALUES(?,?,?,?)",
        (lesson["concept"], today, json.dumps(lesson, ensure_ascii=False),
         "correct" if answer_correct else ("wrong" if answer_correct is False else "read")),
    )
    node = db.execute("SELECT * FROM knowledge_nodes WHERE concept=?",
                      (lesson["concept"],)).fetchone()
    if not node:
        return
    mastery = node["mastery_score"] or 0
    if answer_correct:
        mastery = min(1.0, mastery + 0.3)
        status = "known" if mastery >= 0.8 else "learning"
    elif answer_correct is False:
        mastery = max(0.0, mastery - 0.2)
        status = "weak"
    else:
        mastery = min(1.0, mastery + 0.1)
        status = "learning" if mastery < 0.8 else "known"
    db.execute("UPDATE knowledge_nodes SET status=?, mastery_score=?, last_reviewed=? WHERE concept=?",
               (status, round(mastery, 2), today, lesson["concept"]))


def relation_to_portfolio(db: sqlite3.Connection, concept: str) -> str:
    """课程与我的资产的连接（I4 第 4 段）：确定性映射。"""
    exp_day = db.execute("SELECT MAX(as_of) d FROM exposures").fetchone()["d"]
    if not exp_day:
        # 尚未持久化时现场计算并落库（确定性、幂等）
        from ..engine.exposures import compute_exposures, persist_exposures

        exp = compute_exposures(db)
        exp_day = exp.get("as_of")
        if not exp_day:
            return "（导入持仓后，这里会显示本课概念与你资产的关系。）"
        persist_exposures(db, exp)

    def pct(dim: str, key: str) -> float | None:
        r = db.execute("SELECT pct FROM exposures WHERE as_of=? AND dimension=? AND key=?",
                       (exp_day, dim, key)).fetchone()
        return r["pct"] if r else None

    mapping = {
        "etf": lambda: f"你的组合中 ETF 类资产占 {pct('asset_class', 'etf') or 0}%。",
        "compound_interest": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，"
                                     "是复利策略的弹药库。",
        "asset_allocation": lambda: "你当前的股/债/现金比例："
                                    + " / ".join(f"{r['key']} {r['pct']}%" for r in db.execute(
                                        "SELECT key,pct FROM exposures WHERE as_of=? AND "
                                        "dimension='asset_class' ORDER BY pct DESC", (exp_day,))),
        "diversification": lambda: "你的国家敞口：" + " / ".join(
            f"{r['key']} {r['pct']}%" for r in db.execute(
                "SELECT key,pct FROM exposures WHERE as_of=? AND dimension='country' "
                "AND key != 'unknown' ORDER BY pct DESC LIMIT 4", (exp_day,))),
        "duration": lambda: f"你的债券类资产占 {pct('asset_class', 'bond') or 0}%（久期数据待接入）。",
        "fx_and_returns": lambda: "你的币种敞口：" + " / ".join(
            f"{r['key']} {r['pct']}%" for r in db.execute(
                "SELECT key,pct FROM exposures WHERE as_of=? AND dimension='currency' "
                "ORDER BY pct DESC LIMIT 4", (exp_day,))),
        "money_market_fund": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，"
                                     "货基是现金收益率的常见升级选项之一。",
        "tbill": lambda: f"你的 USD 敞口 {pct('currency', 'USD') or 0}%，"
                         "T-Bill 是美元现金管理的常见工具之一。",
        "inflation": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，通胀直接侵蚀其购买力。",
        "liquidity": lambda: "检查紧急备用金：建议覆盖 3-6 个月支出（可在 What-if 中模拟）。",
        "risk_return": lambda: "你的单一标的集中度 Top3：" + " / ".join(
            f"{r['key']} {r['pct']}%" for r in db.execute(
                "SELECT key,pct FROM exposures WHERE as_of=? AND dimension='single_symbol' "
                "AND key NOT LIKE 'CASH:%' ORDER BY pct DESC LIMIT 3", (exp_day,))),
        "rebalancing": lambda: "资产类别偏离目标比例时，再平衡提示会出现在机会卡片中。",
    }
    fn = mapping.get(concept)
    return fn() if fn else "（此概念的组合关联待补充。）"
