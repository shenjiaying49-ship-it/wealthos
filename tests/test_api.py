"""API 集成测试：零状态 → 载入示例 → 手动建账户 → 清除示例。"""
import pytest

from wealthos import db as dbm
from wealthos.api.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "api.db"
    dbm.init_db(db_file)
    # API 内部用全局 DB_PATH，测试前替换为临时库
    monkeypatch.setattr(dbm, "DB_PATH", db_file)
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def test_zero_state_then_demo_flow(client):
    # ① 零状态
    s = client.get("/api/status").json()
    assert s["accounts"] == 0 and s["demo_mode"] is False and s["real_accounts"] == 0

    # ② 载入示例 → 演示模式
    r = client.post("/api/demo/load").json()
    assert r["loaded"] is True
    s = client.get("/api/status").json()
    assert s["demo_mode"] is True and s["accounts"] == 5 and s["demo_accounts"] == 5
    p = client.get("/api/portfolio").json()
    assert not p["net_worth"].get("empty")
    assert all(a["name"].startswith("示例·") for a in p["accounts"])

    # 重复载入幂等
    assert client.post("/api/demo/load").json()["loaded"] is False


def test_manual_account_and_holding(client):
    # ③ 手动创建真实账户（从零开始路径）
    r = client.post("/api/accounts", json={
        "name": "我的钱包", "institution": "现金", "currency": "CNY", "account_type": "cash"})
    assert r.status_code == 200
    # 重名 409 / 坏币种 422
    assert client.post("/api/accounts", json={
        "name": "我的钱包", "currency": "CNY"}).status_code == 409
    assert client.post("/api/accounts", json={
        "name": "X", "currency": "RMB!"}).status_code == 422

    # 记录现金持仓
    r = client.post("/api/holdings", json={
        "account": "我的钱包", "symbol": "CASH:CNY",
        "quantity": 50000, "currency": "CNY"})
    assert r.status_code == 200
    with dbm.get_db() as db:
        row = db.execute("""SELECT h.quantity, h.price FROM holdings h
                            JOIN accounts a ON a.id=h.account_id
                            WHERE a.name='我的钱包'""").fetchone()
        assert row["quantity"] == 50000 and row["price"] == 1.0
        # 估值已生成（币种感知）
        v = db.execute("""SELECT market_value FROM valuations v JOIN accounts a
                          ON a.id=v.account_id WHERE a.name='我的钱包'""").fetchone()
        assert v["market_value"] == 50000
    # 未知账户 404
    assert client.post("/api/holdings", json={
        "account": "不存在", "symbol": "CASH:CNY", "quantity": 1, "currency": "CNY"}
    ).status_code == 404


def test_demo_clear_keeps_real(client):
    client.post("/api/demo/load")
    client.post("/api/accounts", json={"name": "真实账户", "currency": "HKD"})
    client.post("/api/holdings", json={
        "account": "真实账户", "symbol": "CASH:HKD", "quantity": 1000, "currency": "HKD"})
    r = client.post("/api/demo/clear").json()
    assert r["cleared"] == 5
    s = client.get("/api/status").json()
    assert s["demo_mode"] is False
    assert s["accounts"] == 1 and s["real_accounts"] == 1
    p = client.get("/api/portfolio").json()
    assert [a["name"] for a in p["accounts"]] == ["真实账户"]
    assert p["net_worth"]["total"] == 1000  # HKD base 直接相等
