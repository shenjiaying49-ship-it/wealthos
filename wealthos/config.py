"""配置：路径、环境变量、profile。"""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent
DATA_DIR = Path(os.environ.get("WEALTHOS_HOME", str(Path.home() / ".wealthos")))
DB_PATH = Path(os.environ.get("WEALTHOS_DB", DATA_DIR / "wealth.db"))
RAW_DIR = DATA_DIR / "raw"
BACKUP_DIR = DATA_DIR / "backups"


def load_env_file(path: Path | None = None) -> dict:
    """读取 ~/.wealthos/env（KEY=VALUE 每行一条，# 注释）。

    保姆级设计：所有 key 只需要写进这一个文件，不用和 .zshrc/export 搏斗。
    已存在的环境变量优先（不覆盖）。在 config 导入时自动执行。
    """
    env_path = path or (DATA_DIR / "env")
    loaded = {}
    if not env_path.exists():
        return loaded
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
            loaded[k] = v
    return loaded


load_env_file()


def _mask(v: str) -> str:
    return f"{v[:6]}…{v[-4:]}" if len(v) > 12 else "***"


def integrations_status() -> dict:
    """各接口打通状态（只返回布尔与脱敏值，绝不外泄完整 key）。"""
    llm = llm_settings()
    tg_token = os.environ.get("WEALTHOS_TELEGRAM_TOKEN", "")
    tg_chat = os.environ.get("WEALTHOS_TELEGRAM_CHAT_ID", "")
    fred = os.environ.get("WEALTHOS_FRED_KEY", "")
    x = os.environ.get("WEALTHOS_X_BEARER_TOKEN", "")
    xq = os.environ.get("WEALTHOS_XUEQIU_COOKIE", "")
    exa = os.environ.get("WEALTHOS_EXA_API_KEY", "")
    return {
        "llm": {
            "configured": bool(llm),
            "provider": llm.get("provider", ""),
            "model": llm.get("model", ""),
            "key": _mask(llm["api_key"]) if llm and llm.get("api_key") else "",
            "local": llm.get("provider") == "ollama",
        },
        "telegram": {
            "configured": bool(tg_token and tg_chat),
            "token": _mask(tg_token) if tg_token else "",
            "chat_id": tg_chat,
        },
        "fred": {"configured": bool(fred), "key": _mask(fred) if fred else ""},
        "xueqiu": {"configured": bool(xq), "cookie": _mask(xq) if xq else ""},
        "exa": {"configured": bool(exa), "key": _mask(exa) if exa else ""},
        "x": {"configured": bool(x), "token": _mask(x) if x else ""},
    }

CONFIG_DIR = Path(os.environ.get("WEALTHOS_CONFIG", REPO_ROOT / "config"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


class Profile:
    """Personal Wealth Profile（H 报告）的最小实现：yaml 可覆盖默认。"""

    def __init__(self) -> None:
        self.base_currency = os.environ.get("WEALTHOS_BASE_CCY", "HKD")
        self.tax_residencies = ["HK"]
        self.jurisdictions = ["HK", "SG", "JP", "US"]
        p = CONFIG_DIR / "profile.yaml"
        if p.exists():
            import yaml

            data = yaml.safe_load(p.read_text()) or {}
            self.base_currency = data.get("base_currency", self.base_currency)
            self.tax_residencies = data.get("tax_residencies", self.tax_residencies)
            self.jurisdictions = data.get("jurisdictions_of_interest", self.jurisdictions)


PROFILE = Profile()


def llm_settings() -> dict:
    """BYOK LLM 配置；无 key 返回空 dict（确定性模式）。"""
    provider = os.environ.get("WEALTHOS_LLM_PROVIDER", "").lower()
    key = os.environ.get("WEALTHOS_LLM_API_KEY", "")
    model = os.environ.get("WEALTHOS_LLM_MODEL", "")
    if not provider:
        return {}
    if provider == "ollama":
        return {
            "provider": "ollama",
            "base_url": os.environ.get("WEALTHOS_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            "api_key": "ollama",
            "model": model or "qwen2.5:7b",
        }
    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": key,
            "model": model or "claude-sonnet-4-5",
        }
    # 默认 openai 兼容
    return {
        "provider": "openai",
        "base_url": os.environ.get("WEALTHOS_LLM_BASE_URL", "https://api.openai.com/v1"),
        "api_key": key,
        "model": model or "gpt-4o-mini",
    }


def fred_key() -> str:
    return os.environ.get("WEALTHOS_FRED_KEY", "")
