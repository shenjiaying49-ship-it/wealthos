"""Chat：基于本地组合/敞口/简报/新闻的问答（无 LLM 时给确定性摘要）。"""
from __future__ import annotations

import json
import sqlite3

from .llm import LLMUnavailable, available, chat


def _deterministic_answer(db: sqlite3.Connection, question: str) -> str:
    from ..engine import exposures as exp_mod
    from ..engine import networth as nw_mod

    nw = nw_mod.net_worth_summary(db)
    exp = exp_mod.compute_exposures(db)
    if nw.get("empty"):
        return "暂无组合数据：请先导入 accounts/holdings（wealthos import）。[事实]"
    parts = [f"净值 {nw['total']:,.0f} {nw['base']}（截至 {nw['as_of']}）[计算]"]
    if nw.get("delta"):
        parts.append(f"较上一快照 {nw['delta']['abs']:+,.0f} ({nw['delta']['pct']:+.2f}%)[计算]")
    if exp and not exp.get("empty"):
        parts.append("币种敞口: " + " / ".join(
            f"{r['key']} {r['pct']}%" for r in exp.get("currency", [])[:4]) + " [计算]")
        parts.append("单一标的 Top3: " + " / ".join(
            f"{r['key']} {r['pct']}%" for r in exp.get("single_symbol", [])[:3]) + " [计算]")
    parts.append("（确定性模式：配置 LLM key 后可获得针对问题的自然语言分析。）")
    return "\n".join(parts)


def answer(db: sqlite3.Connection, question: str) -> str:
    import re as _re

    url_match = _re.search(r"https?://\S+", question)
    page_text = None
    if url_match:
        from ..providers.reader import read_url

        page_text = read_url(url_match.group(0))
        if not page_text:
            return f"⚠ 这篇文章暂时读不到（网络限制或页面失效）：{url_match.group(0)}\n" \
                   "可以把标题发给我，或稍后再试。"
    if not available():
        if page_text:
            head = page_text[:600]
            return f"📄 已读取该页面（前 600 字）：\n\n{head}\n\n" \
                   "（配置 LLM key 后可获得这篇文章的完整摘要与分析。）"
        return _deterministic_answer(db, question)

    from ..engine import exposures as exp_mod
    from ..engine import networth as nw_mod

    nw = nw_mod.net_worth_summary(db)
    exp = exp_mod.compute_exposures(db)
    latest_brief = db.execute(
        "SELECT content FROM reports WHERE kind='daily' ORDER BY id DESC LIMIT 1").fetchone()
    keywords = question.lower()
    news_ctx = [
        dict(r) for r in db.execute(
            "SELECT title, url, relevance FROM items ORDER BY relevance DESC LIMIT 5")]
    ctx = {
        "net_worth": {k: nw.get(k) for k in ("total", "base", "as_of", "delta", "by_asset_class")},
        "exposures": {d: exp.get(d, [])[:5] for d in
                      ("currency", "country", "sector", "asset_class", "institution")},
        "top_news": news_ctx,
        "latest_brief_excerpt": (latest_brief["content"][:1500] if latest_brief else None),
        "user_provided_page": (page_text[:3000] if page_text else None),
    }
    system = (
        "你是用户的个人财富研究助手。规则：1) 只使用给定上下文中的数字，禁止编造或推算新数字；"
        "2) 每个论断标注 [事实]/[市场预期]/[分析]/[观点]/[AI 推断] 之一；"
        "3) 绝不给出买卖指令或'应该X'式建议，改而列出可选方案与其风险/成本/前提；"
        "4) 不确定就明说不确定。用中文回答。"
    )
    prompt = (f"问题：{question}\n\n本地上下文（JSON）：{json.dumps(ctx, ensure_ascii=False)}\n"
              "请按规则回答。")
    try:
        return chat(db, prompt, system=system)
    except LLMUnavailable:
        return _deterministic_answer(db, question)
