"""配置打通：env 文件加载 / 脱敏状态 / config-status 端点。"""
import pytest

from wealthos import config as cfg


def test_env_file_loader(tmp_path, monkeypatch):
    f = tmp_path / "env"
    f.write_text(
        "# 注释行\n"
        'WEALTHOS_LLM_API_KEY="sk-test-1234567890abcd"\n'
        "WEALTHOS_TELEGRAM_TOKEN=111:AAAhello\n"
        "BADLINE_NO_EQUAL\n"
        "WEALTHOS_FRED_KEY='abc123def456ghi789jkl123'\n")
    for k in ("WEALTHOS_LLM_API_KEY", "WEALTHOS_TELEGRAM_TOKEN", "WEALTHOS_FRED_KEY"):
        monkeypatch.delenv(k, raising=False)
    loaded = cfg.load_env_file(f)
    assert loaded["WEALTHOS_LLM_API_KEY"] == "sk-test-1234567890abcd"  # 引号被剥掉
    assert loaded["WEALTHOS_FRED_KEY"] == "abc123def456ghi789jkl123"
    # 已存在的环境变量不被覆盖
    monkeypatch.setenv("WEALTHOS_FRED_KEY", "already-set")
    f.write_text("WEALTHOS_FRED_KEY=from-file\n")
    assert cfg.load_env_file(f) == {}


def test_masking_never_leaks_full_key(monkeypatch):
    for k in ("WEALTHOS_LLM_PROVIDER", "WEALTHOS_LLM_API_KEY", "WEALTHOS_LLM_MODEL",
              "WEALTHOS_LLM_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("WEALTHOS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("WEALTHOS_LLM_API_KEY", "sk-very-secret-key-9876543210xyz")
    st = cfg.integrations_status()
    masked = st["llm"]["key"]
    assert masked.startswith("sk-ver") and masked.endswith("xyz")
    full = "sk-very-secret-key-9876543210xyz"
    assert full not in str(st)  # 完整 key 绝不出现


def test_config_status_endpoint(tmp_path, monkeypatch):
    from wealthos import db as dbm
    from wealthos.api.app import create_app

    db_file = tmp_path / "s.db"
    dbm.init_db(db_file)
    monkeypatch.setattr(dbm, "DB_PATH", db_file)
    from fastapi.testclient import TestClient

    r = TestClient(create_app()).get("/api/config-status").json()
    assert set(r) >= {"llm", "telegram", "fred", "x"}
    assert r["llm"]["configured"] is False  # 未配置时清晰表达
    assert r["telegram"]["chat_id"] == ""


def test_doctor_runs_without_config(capsys):
    from wealthos.cli import cmd_doctor

    assert cmd_doctor() == 0
    out = capsys.readouterr().out
    assert "未配置" in out and "确定性模式" in out
