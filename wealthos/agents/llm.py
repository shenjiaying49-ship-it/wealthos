"""LLM 抽象层：OpenAI 兼容 / Anthropic / Ollama（BYOK）+ prompt 响应持久化 + 缓存。

设计（架构文档 E3/E4）：
- 相同 prompt_hash 的调用直接回放缓存（同一数据快照绝不二次付费）
- 失败必须显式抛出，调用方降级到确定性模板（ABSTAIN 而非编造）
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import httpx

from ..config import llm_settings


class LLMUnavailable(RuntimeError):
    """LLM 未配置或调用失败——调用方应走确定性降级路径。"""


def available() -> bool:
    return bool(llm_settings())


def _hash(prompt: str, system: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{system}|{prompt}".encode()).hexdigest()[:32]


def chat(db: sqlite3.Connection, prompt: str, system: str = "", use_cache: bool = True,
         client: httpx.Client | None = None, max_tokens: int = 1200) -> str:
    cfg = llm_settings()
    if not cfg:
        raise LLMUnavailable("未配置 LLM（WEALTHOS_LLM_PROVIDER/API_KEY）")
    ph = _hash(prompt, system, cfg["model"])
    if use_cache:
        row = db.execute(
            "SELECT response FROM llm_calls WHERE prompt_hash=? ORDER BY id DESC LIMIT 1",
            (ph,)).fetchone()
        if row and row["response"]:
            db.execute("INSERT INTO llm_calls(prompt_hash,provider,model,prompt,response,"
                       "cache_hit,created_at) VALUES(?,?,?,?,?,1,?)",
                       (ph, cfg["provider"], cfg["model"], prompt[:4000], row["response"],
                        datetime.now(timezone.utc).isoformat(timespec="seconds")))
            return row["response"]

    own = client or httpx.Client(timeout=120)
    try:
        if cfg["provider"] == "anthropic":
            r = own.post(f"{cfg['base_url']}/v1/messages",
                         headers={"x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01"},
                         json={"model": cfg["model"], "max_tokens": max_tokens,
                               "system": system or None, "messages": [{"role": "user",
                                                                       "content": prompt}]})
            r.raise_for_status()
            data = r.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            usage = data.get("usage", {})
        else:  # openai 兼容（含 ollama）
            r = own.post(f"{cfg['base_url']}/chat/completions",
                         headers={"Authorization": f"Bearer {cfg['api_key']}"},
                         json={"model": cfg["model"], "max_tokens": max_tokens,
                               "messages": ([{"role": "system", "content": system}] if system else [])
                               + [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {}) or {}
    except Exception as exc:  # noqa: BLE001 — 统一转成显式的不可用信号
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
    finally:
        if client is None:
            own.close()

    db.execute(
        "INSERT INTO llm_calls(prompt_hash,provider,model,prompt,response,input_tokens,"
        "output_tokens,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (ph, cfg["provider"], cfg["model"], prompt[:4000], text,
         usage.get("input_tokens") or usage.get("prompt_tokens"),
         usage.get("output_tokens") or usage.get("completion_tokens"),
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return text


def chat_json(db: sqlite3.Connection, prompt: str, system: str = "", **kw) -> dict | list | None:
    """要求 JSON 输出并解析；失败返回 None（ABSTAIN）。"""
    raw = chat(db, prompt, system=system, **kw)
    try:
        start = raw.index("{") if "{" in raw and ("[" not in raw or raw.index("{") < raw.index("[")) \
            else raw.index("[")
        return json.loads(raw[start:raw.rindex("]" if start == raw.index("[") else "}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
