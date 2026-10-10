"""Source Graph 相关性：实体抽取 + 图路径 × 敞口权重 → relevance 分。

对应架构文档 H2-H4：持仓导入后把 MY:* 敞口节点挂进图，
新闻命中实体后做 ≤3 跳 BFS，relevance = Σ path_weight × exposure_pct。
"""
from __future__ import annotations

import json
import sqlite3


def attach_my_exposure_nodes(db: sqlite3.Connection, as_of: str) -> int:
    """把当日敞口挂进图：
    ① EXPO:dim:key --exposure(pct)--> MY:WEALTH
    ② 领域实体 --has_exposure(1.0)--> EXPO 节点（打通 BFS 断链）
       CCY:X→EXPO:currency:X, RGN:X→EXPO:country:X, MC:*→EXPO:asset_class:*,
       SYM:<symbol>→EXPO:single_symbol:<symbol>
    """
    from ..engine.exposures import DIMENSIONS

    db.execute("DELETE FROM entity_edges WHERE to_entity='MY:WEALTH' AND edge_type='exposure'")
    db.execute("DELETE FROM entity_edges WHERE edge_type='has_exposure'")

    _CLASS_LINK = {"equity": "MC:EQUITY", "etf": "MC:EQUITY",
                   "bond": "MC:BOND", "crypto": "MC:CRYPTO"}
    n = 0
    for dim in DIMENSIONS + ["single_symbol"]:
        for r in db.execute(
                "SELECT key, pct FROM exposures WHERE as_of=? AND dimension=?", (as_of, dim)):
            key = r["key"]
            expo = f"EXPO:{dim}:{key}"
            db.execute(
                "INSERT OR REPLACE INTO entity_edges(from_entity,edge_type,to_entity,weight) "
                "VALUES(?, 'exposure', 'MY:WEALTH', ?)",
                (expo, (r["pct"] or 0) / 100.0),
            )
            n += 1
            # 领域实体 → 敞口节点 的连接边
            links: list[tuple[str, float]] = []
            if dim == "currency":
                links.append((f"CCY:{key}", 1.0))
            elif dim == "country" and key != "unknown":
                links.append((f"RGN:{key}", 1.0))
            elif dim == "asset_class" and key in _CLASS_LINK:
                links.append((_CLASS_LINK[key], 1.0))
            elif dim == "single_symbol" and not key.startswith("CASH:"):
                links.append((f"SYM:{key}", 1.0))
                # 确保持仓标的存在为图实体（可被新闻抽取命中）
                ins = db.execute(
                    "SELECT name FROM instruments WHERE symbol=?", (key,)).fetchone()
                import json as _json

                db.execute(
                    "INSERT OR IGNORE INTO entities(id,type,name,aliases_json) VALUES(?,?,?,?)",
                    (f"SYM:{key}", "instrument", key,
                     _json.dumps([key] + ([ins["name"]] if ins and ins["name"] else []),
                                 ensure_ascii=False)))
            for src, w in links:
                db.execute(
                    "INSERT OR REPLACE INTO entity_edges(from_entity,edge_type,to_entity,weight) "
                    "VALUES(?, 'has_exposure', ?, ?)",
                    (src, expo, w),
                )
    return n


def _load_aliases(db: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """[(entity_id, alias, lang)] lang: en/zh（避免中英混合误配）。"""
    out = []
    for row in db.execute("SELECT id, aliases_json FROM entities"):
        for a in json.loads(row["aliases_json"] or "[]"):
            if a and len(a) >= 2:
                out.append((row["id"], a, "zh" if any("\u4e00" <= c <= "\u9fff" for c in a) else "en"))
    return sorted(out, key=lambda x: -len(x[1]))  # 长词优先


def extract_entities(text: str, aliases: list[tuple[str, str, str]],
                     max_hits: int = 8) -> list[str]:
    """简单关键词匹配（确定性；LLM 增强可选）。长别名优先避免 'Fed' 吃掉 'Federal Reserve'。"""
    text_l = (text or "").lower()
    hits: list[str] = []
    for eid, alias, _lang in aliases:
        if alias.lower() in text_l and eid not in hits:
            hits.append(eid)
            if len(hits) >= max_hits:
                break
    return hits


def _adjacency(db: sqlite3.Connection) -> dict[str, list[tuple[str, float]]]:
    adj: dict[str, list[tuple[str, float]]] = {}
    for e in db.execute("SELECT from_entity, to_entity, weight FROM entity_edges"):
        adj.setdefault(e["from_entity"], []).append((e["to_entity"], e["weight"]))
    return adj


def relevance_for_entities(entities: list[str], adj: dict[str, list[tuple[str, float]]],
                           max_hops: int = 3) -> float:
    """从命中实体出发 BFS（≤3 跳）到 MY:WEALTH：
    relevance = Σ(到达敞口节点的路径权重 × 敞口比例)，封顶 1.0。
    中间节点权重只做剪枝去重，不参与求和。"""
    if not entities:
        return 0.0
    exposures: dict[str, float] = {}
    best_w: dict[str, float] = {e: 1.0 for e in entities}
    frontier = [(e, 1.0) for e in entities]
    for _ in range(max_hops):
        nxt: list[tuple[str, float]] = []
        for node, w in frontier:
            for to, ew in adj.get(node, []):
                nw = w * ew
                if nw < 0.02:  # 剪枝
                    continue
                if to == "MY:WEALTH":
                    if nw > exposures.get(node, 0):
                        exposures[node] = nw
                    continue
                if nw > best_w.get(to, 0):
                    best_w[to] = nw
                    nxt.append((to, nw))
        frontier = nxt
        if not frontier:
            break
    return min(1.0, sum(exposures.values()))


def score_items(db: sqlite3.Connection) -> int:
    """对全部 items 重算 relevance 与 entities_json。返回更新行数。"""
    aliases = _load_aliases(db)
    adj = _adjacency(db)
    n = 0
    for item in list(db.execute("SELECT id, title, COALESCE(summary,'') s FROM items")):
        ents = extract_entities(f"{item['title']} {item['s']}", aliases)
        rel = relevance_for_entities(ents, adj)
        db.execute("UPDATE items SET entities_json=?, relevance=? WHERE id=?",
                   (json.dumps(ents, ensure_ascii=False), round(rel, 4), item["id"]))
        n += 1
    return n


def explain_relevance(db: sqlite3.Connection, entities: list[str]) -> list[dict]:
    """给 brief 用的敞口解释：命中实体 → 到达的敞口节点及比例。"""
    adj = _adjacency(db)
    out = []
    for e in entities:
        frontier = [(e, 1.0, [e])]
        best_w: dict[str, float] = {e: 1.0}
        for _ in range(3):
            nxt = []
            for node, w, path in frontier:
                for to, ew in adj.get(node, []):
                    nw = w * ew
                    if to == "MY:WEALTH":
                        if nw >= 0.01:
                            out.append({"entity": e, "expo_node": node,
                                        "path": " → ".join(path),
                                        "weight": round(nw, 4)})
                    elif nw > best_w.get(to, 0):
                        best_w[to] = nw
                        nxt.append((to, nw, path + [to]))
            frontier = nxt
            if not frontier:
                break
    # 去重（同一实体保留最大权重）
    seen: dict[str, dict] = {}
    for r in out:
        k = f"{r['entity']}|{r['expo_node']}"
        if k not in seen or r["weight"] > seen[k]["weight"]:
            seen[k] = r
    return sorted(seen.values(), key=lambda x: -x["weight"])
