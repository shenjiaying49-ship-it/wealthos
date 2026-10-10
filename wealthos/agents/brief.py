"""Daily Brief 生成器：确定性模板为底，LLM 可选增强，审计器兜底。

输出契约（架构文档 H5）：
- 每个论断带五类标签之一：[事实]/[市场预期]/[分析]/[观点]/[AI 推断]
- 每个数字可溯源（计算式或数据源）
- 数据快照哈希绑定；缺数据显式声明（fail loud，ABSTAIN 不编造）
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone

from .. import db as dbm
from ..config import PROFILE
from ..engine import exposures as exp_mod
from ..engine import networth as nw_mod
from ..ingest import relevance as rel_mod
from . import auditor, education
from .llm import LLMUnavailable, available, chat_json

LABEL_FACT, LABEL_EXPECT, LABEL_ANALYSIS, LABEL_OPINION, LABEL_INFER = (
    "事实", "市场预期", "分析", "观点", "AI 推断")


def generate(db: sqlite3.Connection, today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    snap = dbm.snapshot_hash(db)

    # 1) 组合计算（确定性）
    nw = nw_mod.net_worth_summary(db)
    exp = exp_mod.compute_exposures(db)
    if exp.get("as_of"):
        exp_mod.persist_exposures(db, exp)
        rel_mod.attach_my_exposure_nodes(db, exp["as_of"])

    # 2) 新闻相关性重算 + Top3
    rel_mod.score_items(db)
    news = db.execute(
        """SELECT i.*, s.name src_name, s.reliability FROM items i
           JOIN sources s ON s.id=i.source_id
           ORDER BY i.relevance DESC, i.published_at DESC LIMIT 20""").fetchall()
    top_news, used_urls = [], set()
    for n in news:
        u = n["url"] or ""
        if u and u not in used_urls:
            top_news.append(dict(n))
            used_urls.add(u)
        if len(top_news) >= 3:
            break

    # 3) 与你有关的一件事（最高 relevance 且有敞口解释）
    mine = _pick_personal_story(db, news)

    # 4) 机会卡片（规则触发，架构文档 J/Should 级）
    opps = _opportunity_rules(exp, nw)

    # 5) 今日一课
    lesson = education.pick_lesson(db, today)
    lesson_block = None
    if lesson:
        lesson_block = {
            "concept": lesson["concept"], "title": lesson["title"],
            "body": lesson["body"].strip(),
            "relation": education.relation_to_portfolio(db, lesson["concept"]),
            "quiz": lesson.get("quiz"),
            "minutes": 3,
        }
        education.record_lesson(db, lesson, today)

    # 6) LLM 增强（可选）：新闻一句话 + 与我有关事件的 why-it-matters
    llm_enhanced = False
    if available():
        try:
            enh = _llm_enhance(db, nw, exp, top_news, mine)
            if enh:
                for i, one in enumerate(enh.get("news_oneliners", [])[:len(top_news)]):
                    if isinstance(one, str) and one and i < len(top_news):
                        top_news[i]["oneliner"] = one
                        top_news[i]["oneliner_label"] = LABEL_INFER
                if mine and enh.get("why_it_matters"):
                    mine["why_it_matters"] = enh["why_it_matters"]
                    mine["why_label"] = LABEL_INFER
                llm_enhanced = True
        except LLMUnavailable:
            llm_enhanced = False  # ABSTAIN：降级到确定性文本

    # 7) 组装 content_json（机器可读，UI/审计用）与 content（人读文本）
    content_json = {
        "date": today, "snapshot_hash": snap,
        "net_worth": nw, "exposures": {d: exp.get(d, []) for d in
                                       ["currency", "country", "sector", "asset_class",
                                        "institution", "single_symbol"]},
        "news": top_news, "personal_story": mine, "opportunities": opps,
        "lesson": lesson_block, "llm_enhanced": llm_enhanced,
        "conclusions": ([{"title": n["title"], "url": n["url"]} for n in top_news]
                        + ([{"title": mine["title"], "url": mine["url"]}] if mine else [])),
        "blocks": [
            {"id": "news", "origin": "mixed",
             "text": " ".join(n.get("oneliner") or n["title"] for n in top_news)},
            {"id": "personal", "origin": "llm" if mine and mine.get("why_label") == LABEL_INFER
             else "template", "text": (mine or {}).get("why_it_matters", "")},
        ],
    }
    content = _render_text(today, nw, exp, top_news, mine, opps, lesson_block, llm_enhanced)

    db.execute(
        "INSERT INTO reports(kind,as_of,data_snapshot_hash,content,content_json,model_meta_json,"
        "created_at) VALUES('daily',?,?,?,?,?,?)",
        (today, snap, content, json.dumps(content_json, ensure_ascii=False),
         json.dumps({"llm_enhanced": llm_enhanced}, ensure_ascii=False),
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    report_id = db.execute("SELECT last_insert_rowid() id").fetchone()["id"]

    # 8) 审计（禁语/数字溯源/证据 URL）
    failures = auditor.audit_report(db, report_id, content,
                                    json.dumps(content_json, ensure_ascii=False),
                                    {"net_worth": nw, "exposures": content_json["exposures"]})
    db.execute("UPDATE reports SET content_json=json_set(content_json,'$.audit_failures',?) "
               "WHERE id=?", (json.dumps(failures, ensure_ascii=False), report_id))
    return {"report_id": report_id, "snapshot_hash": snap, "audit_failures": failures,
            "content": content, "content_json": content_json}


def _pick_personal_story(db: sqlite3.Connection, news) -> dict | None:
    """最高相关性且能解释敞口路径的新闻。"""
    for n in news:
        if (n["relevance"] or 0) < 0.05:
            continue
        ents = json.loads(n["entities_json"] or "[]")
        if not ents:
            continue
        paths = rel_mod.explain_relevance(db, ents)
        if not paths:
            continue
        top = paths[0]
        dim, key = top["expo_node"].rsplit(":", 2)[1], top["expo_node"].rsplit(":", 2)[2].split(":")[-1]
        pct_str = f"{top['weight'] * 100:.0f}%"
        return {
            "title": n["title"], "url": n["url"], "source": n["src_name"],
            "published_at": n["published_at"], "reliability": n["reliability"],
            "entities": ents, "path": top["path"], "exposure_pct": pct_str,
            "exposure_dim": dim, "exposure_key": key,
            "why_it_matters": (f"该事件经传导路径 {top['path']} 与你的 {dim} 敞口（约 "
                               f"{pct_str} 量级）相关。可能影响方向与幅度需结合事件细节判断"
                               "（此处为确定性模板说明，启用 LLM 后会更具体）。"),
            "why_label": LABEL_ANALYSIS,
        }
    return None


def _opportunity_rules(exp: dict, nw: dict) -> list[dict]:
    """v1 规则扫描（无辩论版）：现金占比 / 机构集中 / 币种集中 / 单一标的。"""
    cards = []
    if not exp or exp.get("empty"):
        return cards
    base = PROFILE.base_currency

    def dim_pct(dim: str, key: str) -> float:
        for r in exp.get(dim, []):
            if r["key"] == key:
                return r["pct"] or 0
        return 0.0

    cash = dim_pct("asset_class", "cash")
    if cash > 40:
        cards.append({
            "title": f"现金管理：现金占组合 {cash:.0f}%", "category": "cash_mgmt",
            "why": "现金比例较高时，短端利率工具（货基/T-Bill/定存）之间的收益差值得了解。",
            "options": ["货币市场基金", "短期国债 T-Bill", "银行定期存款"],
            "note": f"以 {base} 计的现金敞口 {cash:.0f}%；各选项的收益/流动性/风险/门槛"
                    "对比见 Research 页（数据接入后）。",
            "fits": None, "label": LABEL_ANALYSIS,
        })
    insts = exp.get("institution", [])
    if insts and insts[0]["pct"] > 50:
        cards.append({
            "title": f"机构集中：{insts[0]['key']} 占 {insts[0]['pct']:.0f}%",
            "category": "brokerage_diversification",
            "why": "单一机构占比过半时，机构层面的运营/监管/服务风险值得纳入考虑。",
            "options": ["了解第二券商的开户条件", "了解资产转移的流程与成本",
                        "评估当前机构的服务与保障范围"],
            "note": "这不是行动建议，而是值得研究的事项清单。",
            "fits": None, "label": LABEL_ANALYSIS,
        })
    ccys = exp.get("currency", [])
    if ccys and ccys[0]["key"] != base and ccys[0]["pct"] > 60:
        cards.append({
            "title": f"币种集中：{ccys[0]['key']} 占 {ccys[0]['pct']:.0f}%",
            "category": "currency_diversification",
            "why": f"非本币（{base}）资产占比高时，汇率波动对你净值的影响值得研究。",
            "options": ["多币种账户的持有成本", "对冲工具的门槛与成本", "自然对冲（收入币种）"],
            "note": "汇率影响是双向的，本卡片仅提示研究方向。",
            "fits": None, "label": LABEL_ANALYSIS,
        })
    tops = [r for r in exp.get("single_symbol", []) if not r["key"].startswith("CASH:")]
    if tops and tops[0]["pct"] > 10:
        cards.append({
            "title": f"单一标的集中：{tops[0]['key']} 占 {tops[0]['pct']:.0f}%",
            "category": "single_symbol_concentration",
            "why": "单一持仓超过组合 10% 时，公司个体事件对净值的影响会放大。",
            "options": ["了解加仓的论据与反方观点", "设定检视触发条件（财报/关键指标）",
                        "了解分批调整的方式与税务影响"],
            "note": "是否调整取决于你的论据强度与风险容量，本系统不做买卖建议。",
            "fits": None, "label": LABEL_ANALYSIS,
        })
    return cards


def _llm_enhance(db, nw, exp, top_news, mine) -> dict | None:
    """让 LLM 写新闻一句话与 why-it-matters；输入只有已计算好的结构（防编数）。"""
    news_payload = [
        {"title": n["title"], "summary": (n["summary"] or "")[:200],
         "source": n["src_name"], "reliability": n["reliability"]}
        for n in top_news
    ]
    mine_payload = None
    if mine:
        mine_payload = {k: mine[k] for k in
                        ("title", "path", "exposure_pct", "exposure_dim")}
    prompt = (
        "你是个人财富简报编辑。基于以下已核实的数据生成 JSON（不要编造任何数字；"
        "数字只能来自输入）。输出格式："
        '{"news_oneliners": ["一句话中文摘要，≤40字", ...], '
        '"why_it_matters": "1-2 句中文说明与我敞口的关系"}\n\n'
        f"新闻：{json.dumps(news_oneliners_input(news_payload), ensure_ascii=False)}\n"
        f"我的关联事件：{json.dumps(mine_payload, ensure_ascii=False)}\n"
        "要求：每个摘要客观中性、不含买卖建议；why_it_matters 说明传导逻辑而非预测。"
    )
    return chat_json(db, prompt, system="你是严谨的金融简报编辑，拒绝任何投资建议式表述。")


def news_oneliners_input(news_payload):
    return news_payload


def _render_text(today, nw, exp, top_news, mine, opps, lesson, llm_enhanced) -> str:
    L = []
    L.append(f"GOOD MORNING · {today}")
    L.append("=" * 52)
    if nw.get("empty"):
        L.append(f"YOUR WEALTH：暂无数据（请先导入 accounts/holdings）[事实]")
    else:
        delta = nw.get("delta") or {}
        dstr = (f"{delta.get('abs', 0):+,.0f} ({delta.get('pct', 0):+.2f}%)"
                if delta else "首日快照")
        L.append(f"YOUR WEALTH：{nw['total']:,.0f} {nw['base']} · {dstr}  [计算]")
        L.append(f"数据截至 {nw['as_of']}" + (f"（对比 {delta.get('prev_as_of')}）"
                                             if delta else ""))
        if nw.get("missing_fx"):
            miss = "、".join(sorted({m['currency'] for m in nw['missing_fx']}))
            L.append(f"⚠ 缺汇率未计入：{miss}（运行 fetch 补汇率）[事实]")
        cls = " · ".join(f"{k} {v:,.0f}" for k, v in (nw.get("by_asset_class") or {}).items())
        if cls:
            L.append(f"资产层：{cls}  [计算]")
    L.append("-" * 52)
    L.append(f"今天值得你知道的 {len(top_news)} 件事")
    for i, n in enumerate(top_news, 1):
        label = n.get("oneliner_label") or ("事实" if n["reliability"] in ("Primary", "High")
                                            else "观点")
        one = n.get("oneliner") or n["title"]
        L.append(f"{i}. [{label}] {one}")
        L.append(f"   来源: {n['src_name']} · {n['reliability']} · "
                 f"{(n['published_at'] or '')[:10]} · {n['url']}")
    if not top_news:
        L.append("（暂无新闻——运行 wealthos fetch 拉取信息源）")
    L.append("-" * 52)
    L.append("🎯 与你有关的一件事")
    if mine:
        L.append(f"[{mine['why_label']}] {mine['title']}")
        L.append(f"传导路径：{mine['path']}  [计算]")
        L.append(f"你的敞口：{mine['exposure_dim']} ≈ {mine['exposure_pct']} 量级  [计算]")
        L.append(f"为什么重要：{mine['why_it_matters']}")
        L.append(f"证据: {mine['source']} ({mine['reliability']}) {mine['url']}")
        L.append("未确定部分：事件的实际影响取决于细节，以上是传导框架而非预测。")
    else:
        L.append("（今日没有相关性达标的事件——这本身是信息：你的组合今天不忙。）")
    L.append("-" * 52)
    L.append(f"💡 值得研究的机会（{len(opps)}）")
    for c in opps:
        L.append(f"[{c['label']}] {c['title']}")
        L.append(f"   为什么: {c['why']}")
        L.append(f"   可研究方向: {' / '.join(c['options'])}")
        L.append(f"   说明: {c['note']}")
    if not opps:
        L.append("（当前敞口未触发任何研究提示。）")
    L.append("-" * 52)
    L.append("📖 今日金融课（约 3 分钟）")
    if lesson:
        L.append(f"{lesson['title']}")
        L.append(lesson["body"])
        L.append(f"和我的资产的关系：{lesson['relation']}")
        q = lesson.get("quiz") or {}
        if q:
            L.append(f"小问题：{q.get('q')} 选项：{' / '.join(q.get('options', []))}")
    else:
        L.append("（课程库已学完一轮——月度测验即将安排。）")
    L.append("=" * 52)
    L.append(f"LLM 增强：{'开启' if llm_enhanced else '关闭（确定性模式，数字均来自本地计算）'}")
    L.append("免责：本简报为信息整理与研究辅助，不构成投资建议；最终决策由你做出。")
    return "\n".join(L)
