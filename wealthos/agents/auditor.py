"""Evidence Auditor：发布前的确定性检查（无 LLM）。

对应架构文档 E2 横切层 + 用户第三十节"禁止假确定性"：
1) 禁语检查：拦截"应该买/一定会/保证/最好的配置"类表述
2) 数字溯源：LLM 文本中出现的数字必须能在计算结果 JSON 里找到
3) 证据检查：结论必须带非空 URL
"""
from __future__ import annotations

import json
import re

BANNED_PATTERNS = [
    r"应该.{0,6}(?:买|卖|开户|转入|买入|卖出)",
    r"一定要(?:买|卖|加仓|减仓)",
    r"一定会(?:涨|跌|赚)",
    r"保证(?:收益|赚钱|不亏|回报)",
    r"(?:最好|最优)的?(?:资产)?配置",
    r"稳赚",
    r"无风险高收益",
]
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*%?")
# 先剔除日期/时间/比例式上下文，避免 "2026-10-03" 被拆成 -10/-03 当数字
_STRIP = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d{1,2}:\d{2}|\d+/\d+")


def check_banned_phrases(text: str) -> list[str]:
    hits = []
    for pat in BANNED_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append(m.group(0))
    return hits


def _collect_numbers(obj) -> set[float]:
    out: set[float] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _collect_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _collect_numbers(v)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        out.add(round(float(obj), 4))
    return out


def check_numbers_grounded(llm_text: str, computed: dict | list) -> list[str]:
    """LLM 文本里的每个数字应可在计算结果中找到（浮点值匹配，容许格式变体）。"""
    allowed = _collect_numbers(computed)
    ungrounded = []
    text = _STRIP.sub(" ", llm_text)
    for m in _NUMBER.finditer(text):
        tok = m.group(0).rstrip("%").replace(",", "")
        try:
            v = round(float(tok), 4)
        except ValueError:
            continue
        if v not in allowed:
            ungrounded.append(m.group(0))
    return ungrounded


def check_evidence_urls(conclusions: list[dict]) -> list[str]:
    """每条结论需带非空 url 证据。"""
    missing = []
    for c in conclusions:
        if not (c.get("url") or "").startswith("http"):
            missing.append(str(c.get("title", "<无标题>"))[:60])
    return missing


def audit_report(db, report_id: int, content: str, content_json: str,
                 computed: dict | list) -> list[dict]:
    """对一份 report 跑全套检查并写 audit_log；返回未通过项。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []

    hits = check_banned_phrases(content)
    results.append(("banned_phrases", not hits, ",".join(hits)))

    llm_parts = []
    try:
        cj = json.loads(content_json or "{}")
        for block in cj.get("blocks", []):
            if block.get("origin") == "llm":
                llm_parts.append(block.get("text", ""))
    except json.JSONDecodeError:
        pass
    if llm_parts:
        ungrounded = check_numbers_grounded("\n".join(llm_parts), computed)
        results.append(("numbers_grounded", not ungrounded, ",".join(ungrounded[:10])))

    urls_missing = []
    try:
        cj = json.loads(content_json or "{}")
        urls_missing = check_evidence_urls(cj.get("conclusions", []))
    except json.JSONDecodeError:
        pass
    if urls_missing or (content_json and "conclusions" in (content_json or "{}")):
        results.append(("evidence_urls", not urls_missing, ",".join(urls_missing[:10])))

    failures = []
    for name, passed, detail in results:
        db.execute("INSERT INTO audit_log(report_id,check_name,passed,detail,ts) VALUES(?,?,?,?,?)",
                   (report_id, name, 1 if passed else 0, detail, now))
        if not passed:
            failures.append({"check": name, "detail": detail})
    return failures
