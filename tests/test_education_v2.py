"""Education v2：强化排程 + 难度梯度 + 进度可视化。"""
import pytest

from wealthos import db as dbm
from wealthos.agents import education
from wealthos.api.app import create_app


@pytest.fixture()
def db(tmp_path):
    f = tmp_path / "e.db"
    dbm.init_db(f)
    conn = dbm.connect(f)
    yield conn
    conn.close()


def test_reinforcement_until_known(db):
    """修复核心 bug：learning 状态的概念连续多日重练，直到掌握（不再 14 天锁定）。"""
    l1 = education.pick_lesson(db, "2026-10-01")
    education.record_lesson(db, l1, "2026-10-01", True)          # 0.3
    day2 = education.pick_lesson(db, "2026-10-02")
    assert day2["concept"] == l1["concept"], "次日应优先强化同一概念"
    education.record_lesson(db, day2, "2026-10-02", True)        # 0.6
    day3 = education.pick_lesson(db, "2026-10-03")
    assert day3["concept"] == l1["concept"]
    r = education.record_lesson(db, day3, "2026-10-03", True)    # 0.9 → known
    assert r["known"] is True and r["mastery"] == 0.9
    day4 = education.pick_lesson(db, "2026-10-04")
    assert day4["concept"] != l1["concept"], "已掌握 → 让位给新概念"


def test_hard_level_unlock_and_deltas(db):
    """掌握度 ≥0.3 自动出进阶题；进阶答对 +0.5、答错 -0.1。"""
    import yaml

    from wealthos.config import CONFIG_DIR

    l = next(x for x in yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())["lessons"]
             if x.get("quiz_hard"))
    education.record_lesson(db, l, "2026-10-01", True)           # 0.3
    picked = education.pick_lesson(db, "2026-10-02")
    assert picked["quiz_level"] == "hard"
    assert picked["quiz"]["q"] == l["quiz_hard"]["q"]
    r = education.record_lesson(db, l, "2026-10-02", True, level="hard")
    assert r["mastery"] == 0.8 and r["known"]                    # 0.3+0.5 一步掌握
    r2 = education.record_lesson(db, l, "2026-10-03", False, level="hard")
    assert r2["mastery"] == 0.7                                   # -0.1 而非 -0.15
    r3 = education.record_lesson(db, l, "2026-10-04", False, level="easy")
    assert r3["mastery"] == 0.55 and r3["status"] == "learning"  # -0.15


def test_weak_gets_top_priority(db):
    l1 = education.pick_lesson(db, "2026-10-01")
    education.record_lesson(db, l1, "2026-10-01", True)          # 0.3 learning
    # 换一个无前置、importance 5 的概念答错打成 weak
    import json as _json

    import yaml

    from wealthos.config import CONFIG_DIR

    lessons = {x["concept"]: x for x in
               yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())["lessons"]}
    target = next(c for c, ls in lessons.items()
                  if c != l1["concept"] and not ls.get("prereq")
                  and ls.get("importance") == 5)
    education.record_lesson(db, lessons[target], "2026-10-01", False, level="easy")  # 0→weak
    picked = education.pick_lesson(db, "2026-10-02")
    assert picked["concept"] == target, "weak(4.0×5) 优先于 learning(3.6×5)"


def test_progress_endpoint(db, monkeypatch, tmp_path):
    f = tmp_path / "p.db"
    dbm.init_db(f)
    monkeypatch.setattr(dbm, "DB_PATH", f)
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    p = client.get("/api/lessons/progress").json()
    assert p["total"] >= 24                       # 24 门课全部登记
    assert p["known"] == 0 and "avg_mastery" in p
    # 答一题后进度可见地变化（掌握度从 0 上升）
    today = client.get("/api/lessons/today").json()
    r = client.post("/api/lessons/answer", json={
        "concept": today["concept"], "correct": True, "level": "easy"}).json()
    assert r["mastery"] == 0.3
    p2 = client.get("/api/lessons/progress").json()
    assert p2["avg_mastery"] > p["avg_mastery"]
    node = next(n for n in p2["nodes"] if n["concept"] == today["concept"])
    assert node["mastery_score"] == 0.3           # 用户报告的核心问题：可见上升


def test_micro_macro_lessons_seeded(db):
    doms = {r["domain"] for r in db.execute("SELECT DISTINCT domain FROM knowledge_nodes")}
    assert {"micro_economics", "macro_economics"} <= doms
