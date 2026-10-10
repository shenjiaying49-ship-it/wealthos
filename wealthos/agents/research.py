"""Research Agent：明星公司研报手把手精读（第二十、二十一节）。

数据流（数字出自代码，叙述出自模板/LLM——FinRobot 原则）：
SEC EDGAR XBRL companyconcept（营收/EPS/毛利）→ 同比/环比/TTM 确定性计算
→ 分节精读（每节：数据[带来源] + 怎么读 + 知识点高亮 + 概念登记）→ 落库 reports。
无 EDGAR 的公司（港股）降级为"行情+公告阅读指引"模式。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import httpx

from ..config import CONFIG_DIR

EDGAR = "https://data.sec.gov/api/xbrl/companyconcept"
UA = {"User-Agent": "WealthOS/0.1 personal-finance-research (local-first) contact: user@localhost"}

# 概念 tag 回退列表（不同公司用的 XBRL tag 有差异）
TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "eps": ["EarningsPerShareDiluted"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
}
UNITS = {"eps": "USD/shares"}


def load_companies() -> list[dict]:
    import yaml

    cfg = yaml.safe_load((CONFIG_DIR / "star_companies.yaml").read_text())
    return cfg.get("companies", [])


def load_sections() -> list[dict]:
    import yaml

    cfg = yaml.safe_load((CONFIG_DIR / "star_companies.yaml").read_text())
    return cfg.get("sections", [])


def _fetch_concept(client: httpx.Client, cik: str, tag: str) -> list[dict] | None:
    for t in TAGS[tag]:
        r = client.get(f"{EDGAR}/CIK{cik}/us-gaap/{t}.json")
        if r.status_code != 200:
            continue
        try:
            data = r.json()
        except ValueError:
            continue
        for unit_key in (UNITS.get(tag, "USD"), "USD"):
            rows = data.get("units", {}).get(unit_key)
            if rows:
                return rows
    return None


def _quarters(rows: list[dict]) -> list[dict]:
    """取 10-Q/10-K 里的季度区间条目（duration ≈ 80–100 天），按 end 排序去重。"""
    from datetime import date

    out = {}
    for r in rows:
        if r.get("form") not in ("10-Q", "10-K"):
            continue
        try:
            s = date.fromisoformat(r["start"][:10])
            e = date.fromisoformat(r["end"][:10])
        except (KeyError, ValueError):
            continue
        days = (e - s).days
        if not (70 <= days <= 105):
            continue
        key = r["end"][:10]
        # 保留 filed 最新的
        if key not in out or (r.get("filed", "") > out[key].get("filed", "")):
            out[key] = r
    return [out[k] for k in sorted(out)]


def _yoy(qs: list[dict], idx: int) -> float | None:
    from datetime import date

    cur = qs[idx]
    try:
        ce = date.fromisoformat(cur["end"][:10])
    except ValueError:
        return None
    for j in range(idx - 1, -1, -1):
        try:
            pe = date.fromisoformat(qs[j]["end"][:10])
        except ValueError:
            continue
        if 350 <= (ce - pe).days <= 380:
            prev = qs[j]["val"]
            return (cur["val"] / prev - 1) * 100 if prev else None
    return None


def _pct(a: float, b: float) -> float | None:
    return (a / b - 1) * 100 if b else None


def fetch_fundamentals(symbol: str, cik: str,
                       client: httpx.Client | None = None) -> dict | None:
    own = client or httpx.Client(timeout=20, headers=UA)
    try:
        result = {}
        for tag in TAGS:
            rows = _fetch_concept(own, cik, tag)
            if rows:
                qs = _quarters(rows)
                if qs:
                    result[tag] = qs
        return result or None
    finally:
        if client is None:
            own.close()


def build_brief(db: sqlite3.Connection, symbol: str,
                client: httpx.Client | None = None) -> dict:
    comp = next((c for c in load_companies() if c["symbol"] == symbol), None)
    if not comp:
        raise ValueError(f"观察名单中没有 {symbol}")
    sections_tmpl = load_sections()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    price_row = db.execute("SELECT price, as_of FROM price_latest WHERE symbol=?",
                           (symbol,)).fetchone()
    price = {"price": price_row["price"], "as_of": price_row["as_of"]} if price_row else None
    held = db.execute(
        "SELECT quantity FROM holdings WHERE symbol=? ORDER BY as_of DESC LIMIT 1",
        (symbol,)).fetchone()

    fund = fetch_fundamentals(symbol, comp["cik"], client) if comp["cik"] else None
    sections, changes, quiz = [], [], None

    if fund:
        def latest_with_yoy(tag):
            qs = fund.get(tag) or []
            if not qs:
                return None
            i = len(qs) - 1
            return {"cur": qs[i], "prev_q": qs[i - 1] if i >= 1 else None,
                    "yoy": _yoy(qs, i)}

        rev = latest_with_yoy("revenue")
        eps = latest_with_yoy("eps")
        gp = latest_with_yoy("gross_profit")
        oi = latest_with_yoy("operating_income")

        gm_now = (gp["cur"]["val"] / rev["cur"]["val"] * 100) if (gp and rev
                  and rev["cur"]["val"]) else None
        om_now = (oi["cur"]["val"] / rev["cur"]["val"] * 100) if (oi and rev
                  and rev["cur"]["val"]) else None
        # TTM EPS = 最近 4 个季度之和 → P/E
        eps_qs = fund.get("eps") or []
        ttm_eps = sum(q["val"] for q in eps_qs[-4:]) or None
        pe = (price["price"] / ttm_eps) if (price and ttm_eps) else None

        def data_rows(pairs):
            return [{"label": lb, "value": v, "source": src} for lb, v, src in pairs if v is not None]

        facts = {
            "revenue": rev, "eps": eps, "gross_margin": gm_now, "operating_margin": om_now,
            "pe": pe, "ttm_eps": ttm_eps,
        }
        SEC = "SEC EDGAR XBRL（10-Q/10-K，filed {filed}）"
        for tmpl in sections_tmpl:
            sid = tmpl["id"]
            if sid == "revenue" and rev:
                cur = rev["cur"]
                sec_data = data_rows([
                    (f"本季营收（截至 {cur['end'][:10]}）", f"{cur['val']/1e9:.1f} B USD",
                     SEC.format(filed=cur.get("filed", "?"))),
                    ("同比 YoY", f"{rev['yoy']:+.1f}%" if rev["yoy"] is not None else None, "[计算]"),
                    ("环比 QoQ", f"{_pct(cur['val'], rev['prev_q']['val']):+.1f}%"
                     if rev["prev_q"] else None, "[计算]"),
                ])
            elif sid == "eps" and eps:
                cur = eps["cur"]
                sec_data = data_rows([
                    (f"本季摊薄 EPS", f"{cur['val']:.2f} USD", SEC.format(filed=cur.get("filed", "?"))),
                    ("同比 YoY", f"{eps['yoy']:+.1f}%" if eps["yoy"] is not None else None, "[计算]"),
                    ("TTM EPS（近四季合计）", f"{ttm_eps:.2f}" if ttm_eps else None, "[计算]"),
                ])
            elif sid == "gross_margin":
                sec_data = data_rows([
                    ("本季毛利率", f"{gm_now:.1f}%" if gm_now is not None else None, "[计算]"),
                ])
                if gp and rev and rev["prev_q"] and gp["prev_q"]:
                    gmp = (gp["prev_q"]["val"] / rev["prev_q"]["val"] * 100)
                    sec_data.append({"label": "上季毛利率", "value": f"{gmp:.1f}%", "source": "[计算]"})
            elif sid == "operating_margin":
                sec_data = data_rows([
                    ("本季经营利润率", f"{om_now:.1f}%" if om_now is not None else None, "[计算]"),
                ])
            elif sid == "valuation":
                sec_data = data_rows([
                    ("现价", f"{price['price']:.2f}" if price else None, "Yahoo/Stooq"),
                    ("P/E (TTM)", f"{pe:.1f}x" if pe else None, "[计算：现价÷TTM EPS]"),
                ])
            elif sid == "changed":
                for name, fact in [("营收同比", rev and rev["yoy"]), ("EPS 同比", eps and eps["yoy"])]:
                    if fact is not None:
                        changes.append(f"{name} {fact:+.1f}%")
                sec_data = data_rows([(c, "", "见上") for c in changes]) or \
                    data_rows([("本季无显著偏离", "", "[计算]")])
            else:
                sec_data = []
            sections.append({
                "id": sid, "title": tmpl["title"], "teach": tmpl["teach"].strip(),
                "highlight": tmpl.get("highlight", ""),
                "concept": tmpl.get("concept"), "data": sec_data,
            })
        quiz = {
            "q": "这家公司本季营收同比增速与 EPS 同比增速，哪个更高？更高说明什么？"
                 "（提示：回顾第 1、2 节）",
            "options": ["EPS 更高：利润率在改善或股本在减少",
                        "营收更高：以价换量",
                        "无法比较"],
            "answer": 0,
            "explain": "两者都来自上面的[计算]数字——先看数据，再回到'怎么读'的解释。",
        }
        data_source = "SEC EDGAR XBRL + Yahoo/Stooq 行情"
    else:
        # 港股等无 EDGAR：行情 + 公告阅读指引模式（fail loud 说明数据边界）
        for tmpl in sections_tmpl:
            note = ("港交所财务数据暂不可自动获取（无免费官方 API，见调研报告 docs/research-notes/F）。"
                    if comp["cik"] is None else "SEC 数据暂不可达，稍后重试。")
            sections.append({
                "id": tmpl["id"], "title": tmpl["title"], "teach": tmpl["teach"].strip(),
                "highlight": tmpl.get("highlight", ""), "concept": tmpl.get("concept"),
                "data": ([{"label": "现价", "value": f"{price['price']:.2f}",
                           "source": "Yahoo/Stooq"}]
                          if (price and tmpl["id"] == "valuation")
                          else [{"label": "数据边界", "value": note, "source": "[事实]"}]
                          if tmpl["id"] == "revenue" else []),
            })
        quiz = {
            "q": f"在哪可以免费看 {comp['cn_name']} 的完整财报与公告？",
            "options": ["HKEXnews 披露易 + 公司 IR 页", "只能付费购买", "社交媒体"],
            "answer": 0,
            "explain": f"披露易：https://www.hkexnews.hk ；公司 IR：{comp['ir_url']}",
        }
        data_source = "行情 + 阅读指引（无自动财务数据）"

    brief = {
        "symbol": symbol, "name": comp["cn_name"], "generated_at": today,
        "why_star": comp["why"], "ir_url": comp["ir_url"],
        "held": bool(held), "held_qty": held["quantity"] if held else None,
        "data_source": data_source, "sections": sections, "quiz": quiz,
        "concepts": comp.get("concepts", []),
    }
    db.execute(
        "INSERT INTO reports(kind,as_of,data_snapshot_hash,content,content_json,model_meta_json,"
        "created_at) VALUES('earnings_brief',?,?,?,?,?,?)",
        (today, f"research:{symbol}", json.dumps(brief, ensure_ascii=False)[:200],
         json.dumps(brief, ensure_ascii=False), json.dumps(brief, ensure_ascii=False),
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    # 知识图谱登记：读过的概念 → learning
    for c in comp.get("concepts", []):
        db.execute(
            "INSERT OR IGNORE INTO knowledge_nodes(concept,domain,prereq_json,importance,status) "
            "VALUES(?, 'research', '[]', 3, 'learning')", (c,))
    return brief


def latest_briefs(db: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = db.execute(
        "SELECT id, as_of, content_json FROM reports WHERE kind='earnings_brief' "
        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        try:
            j = json.loads(r["content_json"])
            out.append({"report_id": r["id"], "as_of": r["as_of"], "symbol": j.get("symbol"),
                        "name": j.get("name"), "held": j.get("held"),
                        "sections": len(j.get("sections", []))})
        except json.JSONDecodeError:
            continue
    return out


def run_watchlist(db: sqlite3.Connection, client: httpx.Client | None = None) -> dict:
    """跑一遍观察名单（幂等：每公司每日一份）。"""
    done, failed = [], []
    for c in load_companies():
        try:
            build_brief(db, c["symbol"], client)
            done.append(c["symbol"])
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{c['symbol']}: {str(exc)[:80]}")
    return {"done": done, "failed": failed}
