"""通知接口：Telegram Bot 推送（可选，BYO token）。

配置（均为免费）：找 @BotFather 建 bot 拿 token；给 bot 发一条消息后
访问 https://api.telegram.org/bot<TOKEN>/getUpdates 拿 chat_id。
export WEALTHOS_TELEGRAM_TOKEN=... WEALTHOS_TELEGRAM_CHAT_ID=...
"""
from __future__ import annotations

import os

import httpx

API = "https://api.telegram.org"


def configured() -> bool:
    return bool(os.environ.get("WEALTHOS_TELEGRAM_TOKEN")
                and os.environ.get("WEALTHOS_TELEGRAM_CHAT_ID"))


def send(text: str, client: httpx.Client | None = None) -> bool:
    """发送文本（Telegram 上限 4096 字符，超长截断）。失败不抛错（通知是非关键路径）。"""
    if not configured():
        return False
    token = os.environ["WEALTHOS_TELEGRAM_TOKEN"]
    chat_id = os.environ["WEALTHOS_TELEGRAM_CHAT_ID"]
    own = client or httpx.Client(timeout=15)
    try:
        r = own.post(f"{API}/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": text[:4000]})
        return r.status_code == 200
    except httpx.HTTPError:
        return False
    finally:
        if client is None:
            own.close()
