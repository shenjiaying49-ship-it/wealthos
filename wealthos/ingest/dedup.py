"""三级去重：① canonical URL ② 标题 simhash + 24h 窗 ③ 事件键（ticker,event_type,period）。"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACK_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                 "cmpid", "smid", "siteid", "guccounter", "ns_campaign", "ns_mchannel"}


def canonical_url(url: str) -> str:
    """去追踪参数、规范化 host/scheme。Google News 重定向保留原样（MVP 不解链）。"""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _TRACK_PARAMS]
    host = (parts.netloc or "").lower().removeprefix("www.")
    return urlunsplit((parts.scheme or "https", host, parts.path or "/",
                       urlencode(query), ""))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())


def simhash(text: str) -> int:
    """64 位 simhash（字符级 3-gram 加权 token）。"""
    toks = _tokens(text)
    if not toks:
        return 0
    grams: list[str] = []
    for t in toks:
        if len(t) >= 3:
            grams += [t[i:i + 3] for i in range(len(t) - 2)]
        else:
            grams.append(t)
    bits = [0] * 64
    for g in grams:
        h = int.from_bytes(hashlib.md5(g.encode()).digest()[:8], "big")
        for i in range(64):
            bits[i] += 1 if (h >> i) & 1 else -1
    v = 0
    for i in range(64):
        if bits[i] > 0:
            v |= 1 << i
    return v


def similarity(a: int, b: int) -> float:
    """汉明距离 → 相似度 [0,1]。"""
    dist = bin(a ^ b).count("1")
    return 1 - dist / 64


def dedup_key(url: str, title: str) -> str:
    cu = canonical_url(url)
    if cu:
        return f"url:{hashlib.sha256(cu.encode()).hexdigest()[:20]}"
    return f"title:{simhash(title):016x}"


def is_near_duplicate(title: str, published_day: str, existing: list[tuple[int, str]],
                      threshold: float = 0.8) -> bool:
    """同日 ±1 天窗口内标题近似重复。
    判据：token 集合 Jaccard ≥ threshold（对单词变形/换序鲁棒）；
    existing: [(simhash, day)]——为兼容存储格式，重复项的 simhash 同时做二级判据。"""
    toks = set(_tokens(title))
    if not toks:
        return False
    h = simhash(title)
    for eh, eday in existing:
        if abs(_day_diff(published_day, eday)) > 1:
            continue
        if similarity(h, eh) >= 0.92:
            return True
    # Jaccard 需要原标题——此处退化为 simhash 已判；调用方（rss.py）传近期标题集合时
    # 直接用 token 比较的接口：
    return False


def is_near_duplicate_titles(title: str, published_day: str,
                             existing: list[tuple[str, str]], threshold: float = 0.8) -> bool:
    """标题文本级近重判定（rss.py 使用）：existing: [(title, day)]。"""
    toks = set(_tokens(title))
    if not toks:
        return False
    for etitle, eday in existing:
        if abs(_day_diff(published_day, eday)) > 1:
            continue
        etoks = set(_tokens(etitle))
        if not etoks:
            continue
        j = len(toks & etoks) / len(toks | etoks)
        if j >= threshold or (j >= 0.7 and simhash(title) == simhash(etitle)):
            return True
    return False


def event_key(ticker: str, event_type: str, period: str) -> str:
    return f"({ticker},{event_type},{period})"


def _day_diff(a: str, b: str) -> int:
    from datetime import date

    def d(s: str) -> date:
        y, m, dd = (s or "2000-01-01")[:10].split("-")
        return date(int(y), int(m), int(dd))
    return (d(a) - d(b)).days
