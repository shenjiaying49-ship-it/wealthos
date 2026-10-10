"""Exa 语义搜索（Agent-Reach search.md 方法）：BYO key，按需深度研究用。

免费档：https://dashboard.exa.ai 注册（每千次 $10 内有免费额度，日常够用）。
"""
from __future__ import annotations

import os

import httpx

API = "https://api.exa.ai/search"


def configured() -> bool:
    return bool(os.environ.get("WEALTHOS_EXA_API_KEY"))


def search(query: str, num_results: int = 5,
           client: httpx.Client | None = None) -> list[dict] | None:
    """返回 [{title, url, text}]；未配置/失败返回 None（调用方降级）。"""
    key = os.environ.get("WEALTHOS_EXA_API_KEY", "")
    if not key:
        return None
    own = client or httpx.Client(timeout=20)
    try:
        r = own.post(API, headers={"x-api-key": key},
                     json={"query": query, "numResults": num_results,
                           "contents": {"text": {"maxCharacters": 1000}}})
        if r.status_code != 200:
            return None
        return [{"title": it.get("title", ""), "url": it.get("url", ""),
                 "text": (it.get("text") or "")[:1000]}
                for it in r.json().get("results", [])]
    except (ValueError, httpx.HTTPError):
        return None
    finally:
        if client is None:
            own.close()
