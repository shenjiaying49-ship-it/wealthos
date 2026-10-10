"""Roadmap：阶段内容 + 数据联动完成状态 + 手动勾选。"""
import pytest

from wealthos import db as dbm
from wealthos.api.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "rm.db"
    dbm.init_db(db_file)
    monkeypatch.setattr(dbm, "DB_PATH", db_file)
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def _stage(rm, sid):
    return next(s for s in rm["stages"] if s["id"] == sid)


def test_roadmap_content_and_empty_state(client):
    rm = client.get("/api/roadmap").json()
    ids = [s["id"] for s in rm["stages"]]
    assert ids == [f"s{i}" for i in range(7)]  # s6 = 合规与税务（香港居民）
    # 每张卡必须有"依据"字段（用户核心要求：之后的依据）
    for st in rm["stages"]:
        assert st["cards"], f"{st['id']} 无卡片"
        for c in st["cards"]:
            assert c.get("evidence"), f"{st['id']}/{c['id']} 缺依据"
    # 空库：s0 未自动完成
    assert _stage(rm, "s0")["auto_done"] is False
    assert _stage(rm, "s0")["done"] is False
    assert rm["context"]["real_accounts"] == 0


def test_roadmap_auto_progression(client):
    # 记录现金 → s0 自动完成（先备好汇率，现金按 USD 桥换算到 HKD）
    with dbm.get_db() as db:
        import datetime

        d = datetime.date.today().isoformat()
        db.execute("INSERT OR REPLACE INTO fx_rates VALUES(?,?,?,?,?)",
                   (d, "USD", "CNY", 7.1, "fixture"))
        db.execute("INSERT OR REPLACE INTO fx_rates VALUES(?,?,?,?,?)",
                   (d, "USD", "HKD", 7.8, "fixture"))
    client.post("/api/accounts", json={"name": "钱包", "currency": "CNY"})
    client.post("/api/holdings", json={"account": "钱包", "symbol": "CASH:CNY",
                                       "quantity": 30000, "currency": "CNY"})
    rm = client.get("/api/roadmap").json()
    assert _stage(rm, "s0")["auto_done"] is True and _stage(rm, "s0")["done"] is True
    assert _stage(rm, "s4")["auto_done"] is False
    assert abs(rm["context"]["cash_total_base"] - 30000 * 7.8 / 7.1) < 1  # ≈32958 HKD

    # 记录证券 → s4 自动完成
    client.post("/api/holdings", json={"account": "钱包", "symbol": "AAPL",
                                       "quantity": 1, "currency": "USD", "price": 300})
    rm = client.get("/api/roadmap").json()
    assert _stage(rm, "s4")["auto_done"] is True


def test_roadmap_manual_toggle(client):
    r = client.post("/api/roadmap/toggle", json={"stage_id": "s1"})
    assert r.status_code == 200 and r.json()["manual_done"] is True
    rm = client.get("/api/roadmap").json()
    assert _stage(rm, "s1")["done"] is True
    client.post("/api/roadmap/toggle", json={"stage_id": "s1"})
    rm = client.get("/api/roadmap").json()
    assert _stage(rm, "s1")["done"] is False
    assert client.post("/api/roadmap/toggle", json={"stage_id": "bad"}).status_code == 404


def test_roadmap_ignores_demo_data(client):
    """演示数据不应推进真实路线图进度。"""
    client.post("/api/demo/load")
    rm = client.get("/api/roadmap").json()
    assert _stage(rm, "s0")["auto_done"] is False  # 示例账户被排除
    assert _stage(rm, "s4")["auto_done"] is False
    assert rm["context"]["real_accounts"] == 0
