"""通用网页阅读器（Agent-Reach web.md 方法）：Jina Reader 优先，直连兜底。

用途：证据层抓取新闻原文、读 IR 页面、Chat 里"帮我读这篇文章 <url>"。
Jina 免费无 key（限流时可能为空）→ 直连 + HTML 剥离兜底；全部失败返回 None。
"""
from __future__ import annotations

import re

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wealthos/0.1"}


def read_url(url: str, timeout: int = 20,
             client: httpx.Client | None = None) -> str | None:
    if not url.startswith("http"):
        return None
    own = client or httpx.Client(timeout=timeout, headers=UA, follow_redirects=True)
    try:
        # ① Jina Reader（markdown，正文质量最好）
        try:
            r = own.get(f"https://r.jina.ai/{url}", timeout=timeout)
            if r.status_code == 200 and len(r.text.strip()) > 80:
                return r.text.strip()[:8000]
        except httpx.HTTPError:
            pass
        # ② 直连兜底：剥 HTML 标签
        r = own.get(url)
        if r.status_code == 200 and "<" in r.text:
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", r.text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000] if len(text) > 80 else None
        return None
    except httpx.HTTPError:
        return None
    finally:
        if client is None:
            own.close()
