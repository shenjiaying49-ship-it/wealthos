"""Education Agent v2：强化优先排程 + 难度梯度 + 知识图谱进度。

设计（修复"做题后熟练度不涨"的两个根因）：
1. 排程：weak > learning(未掌握) > unknown 优先练习——同一概念可连续多天重练，
   直到 mastery ≥ 0.8 进入 known；known 超过 14 天未复习进入复习队列（有衰减）。
2. 梯度：mastery ≥ 0.3 且课程有 quiz_hard 时自动出进阶题；
   简单答对 +0.3 / 进阶答对 +0.5 / 进阶答错 -0.1 / 简单答错 -0.15。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

KNOWN_AT = 0.8
REVIEW_AFTER_DAYS = 14
DELTA = {("easy", True): 0.30, ("hard", True): 0.50,
         ("easy", False): -0.15, ("hard", False): -0.10}


def _load_cfg() -> dict:
    import yaml

    from ..config import CONFIG_DIR

    return yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())


def pick_lesson(db: sqlite3.Connection, today: str | None = None) -> dict | None:
    """选择今日概念（强化优先）+ 按掌握度决定难度。"""
    cfg = _load_cfg()
    by_concept = {l["concept"]: l for l in cfg.get("lessons", [])}
    nodes = {r["concept"]: dict(r) for r in db.execute("SELECT * FROM knowledge_nodes")}
    today = today or date.today().isoformat()
    done_today = {r["concept"] for r in db.execute(
        "SELECT concept FROM lessons WHERE date=?", (today,))}

    def days_since(s: str | None) -> int:
        if not s:
            return 999
        return (datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(s, "%Y-%m-%d")).days

    best, best_score = None, -1.0
    for concept, node in nodes.items():
        if concept in done_today or concept not in by_concept:
            continue
        m = node["mastery_score"] or 0.0
        status = node["status"] or "unknown"
        importance = node["importance"] or 3
        # 前置未学的新概念降权（先学前置）
        prereq_penalty = 1.0
        for p in json.loads(node["prereq_json"] or "[]"):
            if nodes.get(p, {}).get("status") != "known":
                prereq_penalty = 0.5
        if status == "weak":
            gap = 4.0
        elif 0 < m < KNOWN_AT:            # learning：强化直到掌握
            gap = 3.6
        elif status == "known":
            if days_since(node.get("last_reviewed")) < REVIEW_AFTER_DAYS:
                gap = 0.3                  # 刚掌握，先学别的
            else:
                gap = 1.6                  # 复习队列（有衰减感知）
        else:                              # unknown
            gap = 3.0
        score = gap * importance * prereq_penalty
        if score > best_score:
            best, best_score = concept, score
    if not best:
        return None
    node = nodes[best]
    lesson = dict(by_concept[best])
    lesson["status"] = node["status"]
    m = node["mastery_score"] or 0.0
    hard = lesson.get("quiz_hard")
    level = "hard" if (m >= 0.3 and hard) else "easy"
    lesson["quiz_level"] = level
    if level == "hard":
        lesson["quiz"] = hard
    return lesson


def record_lesson(db: sqlite3.Connection, lesson: dict, today: str,
                  answer_correct: bool | None = None, level: str = "easy") -> dict:
    db.execute(
        "INSERT OR REPLACE INTO lessons(concept,date,content_json,result) VALUES(?,?,?,?)",
        (lesson["concept"], today, json.dumps(lesson, ensure_ascii=False)[:2000],
         "correct" if answer_correct else ("wrong" if answer_correct is False else "read")),
    )
    node = db.execute("SELECT * FROM knowledge_nodes WHERE concept=?",
                      (lesson["concept"],)).fetchone()
    if not node:
        return {"mastery": 0.0, "status": "unknown"}
    m = node["mastery_score"] or 0.0
    if answer_correct is None:
        m = min(1.0, m + 0.1)  # 阅读（晨报联动）
        status = "known" if m >= KNOWN_AT else "learning"
    else:
        m = max(0.0, min(1.0, m + DELTA[(level, bool(answer_correct))]))
        if m >= KNOWN_AT:
            status = "known"
        elif answer_correct:
            status = "learning"
        else:
            status = "weak" if m < 0.4 else "learning"
    db.execute("UPDATE knowledge_nodes SET status=?, mastery_score=?, last_reviewed=? "
               "WHERE concept=?", (status, round(m, 2), today, lesson["concept"]))
    return {"mastery": round(m, 2), "status": status,
            "known": status == "known", "level": level}


def progress(db: sqlite3.Connection) -> dict:
    """知识图谱进度（Learn 页可视化用）。"""
    rows = [dict(r) for r in db.execute(
        """SELECT concept, domain, status, mastery_score, last_reviewed
           FROM knowledge_nodes ORDER BY domain, concept""")]
    known = sum(1 for r in rows if r["status"] == "known")
    learning = sum(1 for r in rows if r["status"] in ("learning", "weak"))
    avg = round(sum(r["mastery_score"] or 0 for r in rows) / len(rows), 2) if rows else 0
    return {"nodes": rows, "total": len(rows), "known": known, "learning": learning,
            "avg_mastery": avg}


def relation_to_portfolio(db: sqlite3.Connection, concept: str) -> str:
    """课程与我的资产的连接（I4 第 4 段）：确定性映射。"""
    exp_day = db.execute("SELECT MAX(as_of) d FROM exposures").fetchone()["d"]
    if not exp_day:
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

    def top(dim: str, n: int = 4, exclude_cash: bool = False):
        rows = [dict(r) for r in db.execute(
            f"SELECT key,pct FROM exposures WHERE as_of=? AND dimension='{dim}' "
            + ("AND key NOT LIKE 'CASH:%' " if exclude_cash else "")
            + "ORDER BY pct DESC LIMIT ?", (exp_day, n))]
        return " / ".join(f"{r['key']} {r['pct']}%" for r in rows)

    mapping = {
        "etf": lambda: f"你的组合中 ETF 类资产占 {pct('asset_class', 'etf') or 0}%。",
        "compound_interest": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，"
                                     "是复利策略的弹药库。",
        "asset_allocation": lambda: "你当前的股/债/现金：" + top("asset_class"),
        "diversification": lambda: "你的国家敞口：" + top("country"),
        "duration": lambda: f"你的债券类资产占 {pct('asset_class', 'bond') or 0}%（久期数据待接入）。",
        "fx_and_returns": lambda: "你的币种敞口：" + top("currency"),
        "money_market_fund": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，"
                                     "货基是现金收益率的常见升级选项之一。",
        "tbill": lambda: f"你的 USD 敞口 {pct('currency', 'USD') or 0}%，"
                         "T-Bill 是美元现金管理的常见工具之一。",
        "inflation": lambda: f"你的现金占 {pct('asset_class', 'cash') or 0}%，通胀直接侵蚀其购买力。",
        "liquidity": lambda: "检查紧急备用金：建议覆盖 3-6 个月支出（Roadmap 第 1 步）。",
        "risk_return": lambda: "你的单一标的 Top3：" + top("single_symbol", 3, exclude_cash=True),
        "rebalancing": lambda: "资产类别偏离目标比例时，再平衡提示会出现在机会卡片中。",
        # 微观/宏观：与组合的连接
        "market_structure": lambda: "你持仓的行业集中度：" + top("sector", 3) +
                                    "（竞争结构决定谁能长期维持高毛利）",
        "monetary_transmission": lambda: "利率传导的终点是你的组合——币种敞口：" + top("currency"),
        "gdp_cycle": lambda: "股票敞口 " + str(pct("asset_class", "equity") or 0) +
                             "% / ETF " + str(pct("asset_class", "etf") or 0) +
                             "% 会随经济周期波动。",
        "supply_demand": lambda: "大宗与汇率由供需定价——你的币种敞口：" + top("currency"),
        "opportunity_cost": lambda: f"你 {pct('asset_class', 'cash') or 0}% 的现金每天的机会成本是"
                                    "它本可赚取的货基/国债收益。",
        "jobs_data": lambda: "就业数据驱动央行政策 → 你的股票/ETF 敞口 " +
                             str((pct('asset_class', 'equity') or 0)
                                 + (pct('asset_class', 'etf') or 0)) + "%。",
    }
    fn = mapping.get(concept)
    return fn() if fn else "（此概念的组合关联待补充。）"
