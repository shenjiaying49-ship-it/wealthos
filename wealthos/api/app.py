"""FastAPI：只绑定 127.0.0.1（安全架构 L7），静态前端 + JSON API。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import db as dbm

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


class QuizAnswer(BaseModel):
    concept: str
    correct: bool
    level: str = "easy"       # easy | hard


class ChatIn(BaseModel):
    question: str


class AccountIn(BaseModel):
    name: str
    institution: str = ""
    country: str = ""
    currency: str
    account_type: str = "bank"       # bank/brokerage/cash/property/crypto/pension/loan


class HoldingIn(BaseModel):
    account: str                     # 账户名
    symbol: str                      # 证券符号；CASH:HKD 表示现金
    quantity: float
    currency: str
    price: float | None = None       # 现金自动为 1；证券留空则尝试行情补价
    as_of: str | None = None         # 默认今天


class RoadmapToggle(BaseModel):
    stage_id: str


def create_app() -> FastAPI:
    app = FastAPI(title="WealthOS", docs_url="/api/docs")

    @app.get("/api/status")
    def status():
        from .. import demo as demo_mod

        with dbm.get_db() as db:
            return {
                "accounts": db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"],
                "holdings_as_of": db.execute("SELECT MAX(as_of) d FROM holdings").fetchone()["d"],
                "fx_as_of": db.execute("SELECT MAX(as_of) d FROM fx_rates").fetchone()["d"],
                "items": db.execute("SELECT COUNT(*) c FROM items").fetchone()["c"],
                "demo_mode": demo_mod.is_demo_mode(db),
                **demo_mod.counts(db),
                "sources": [dict(r) for r in db.execute(
                    "SELECT id,name,tier,reliability,last_fetch,last_status,enabled "
                    "FROM sources ORDER BY tier")],
            }

    @app.post("/api/accounts")
    def create_account(a: AccountIn):
        with dbm.get_db() as db:
            cur = a.currency.strip().upper()
            if len(cur) != 3 or not cur.isalpha():
                raise HTTPException(422, "currency 需为 3 位字母（如 HKD/USD/CNY）")
            name = a.name.strip()
            if not name:
                raise HTTPException(422, "账户名不能为空")
            if db.execute("SELECT 1 FROM accounts WHERE name=?", (name,)).fetchone():
                raise HTTPException(409, f"账户已存在: {name}")
            db.execute(
                """INSERT INTO accounts(name,institution,country,currency,account_type,
                                       is_asset,is_demo,opened_at)
                   VALUES(?,?,?,?,?,1,0,date('now'))""",
                (name, a.institution.strip() or name, a.country.strip().upper(), cur,
                 a.account_type.strip() or "bank"),
            )
            return {"ok": True, "name": name}

    @app.post("/api/holdings")
    def create_holding(h: HoldingIn):
        from datetime import date

        from ..engine.exposures import compute_exposures, persist_exposures
        from ..engine.networth import recompute_valuations

        with dbm.get_db() as db:
            acct = db.execute("SELECT id FROM accounts WHERE name=?",
                              (h.account.strip(),)).fetchone()
            if not acct:
                raise HTTPException(404, f"账户不存在: {h.account}")
            symbol = h.symbol.strip().upper() if not h.symbol.strip().startswith("CASH:") \
                else h.symbol.strip().upper()
            cur = h.currency.strip().upper()
            as_of = (h.as_of or date.today().isoformat()).strip()
            price = 1.0 if symbol.startswith("CASH:") else h.price
            db.execute(
                """INSERT INTO holdings(account_id,as_of,symbol,quantity,currency,price,source)
                   VALUES(?,?,?,?,?,?,'manual')
                   ON CONFLICT(account_id,as_of,symbol) DO UPDATE SET
                     quantity=excluded.quantity, price=excluded.price""",
                (acct["id"], as_of, symbol, float(h.quantity), cur, price),
            )
            if not symbol.startswith("CASH:"):
                from ..importers.csv_import import _ensure_instrument

                _ensure_instrument(db, symbol, cur)
            recompute_valuations(db, as_of)
            exp = compute_exposures(db)
            if exp.get("as_of"):
                persist_exposures(db, exp)
            return {"ok": True, "symbol": symbol, "as_of": as_of}

    @app.post("/api/demo/load")
    def demo_load():
        from .. import demo as demo_mod
        from ..engine.exposures import compute_exposures, persist_exposures

        with dbm.get_db() as db:
            r = demo_mod.load_demo(db)
            if r.get("loaded"):
                exp = compute_exposures(db)
                if exp.get("as_of"):
                    persist_exposures(db, exp)
            return r

    @app.post("/api/demo/clear")
    def demo_clear():
        from .. import demo as demo_mod

        with dbm.get_db() as db:
            return demo_mod.clear_demo(db)

    @app.get("/api/portfolio")
    def portfolio():
        from ..engine import exposures, networth

        with dbm.get_db() as db:
            return {"net_worth": networth.net_worth_summary(db),
                    "exposures": exposures.compute_exposures(db),
                    "accounts": [dict(r) for r in db.execute(
                        "SELECT a.*, v.market_value, v.as_of val_as_of FROM accounts a "
                        "LEFT JOIN valuations v ON v.account_id=a.id "
                        "AND v.as_of=(SELECT MAX(as_of) FROM valuations) ORDER BY a.id")]}

    @app.get("/api/feed")
    def feed(limit: int = 50, min_relevance: float = 0.0):
        with dbm.get_db() as db:
            rows = [dict(r) for r in db.execute(
                """SELECT i.id, i.title, i.summary, i.url, i.published_at, i.label,
                          i.relevance, i.entities_json, s.name src_name, s.tier, s.reliability
                   FROM items i JOIN sources s ON s.id=i.source_id
                   WHERE i.relevance >= ? ORDER BY i.relevance DESC, i.published_at DESC
                   LIMIT ?""", (min_relevance, limit))]
            for r in rows:
                r["entities"] = json_list(r.pop("entities_json"))
            return {"items": rows}

    @app.get("/api/brief/latest")
    def brief_latest():
        with dbm.get_db() as db:
            row = db.execute(
                "SELECT * FROM reports WHERE kind='daily' ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                raise HTTPException(404, "尚无简报——POST /api/run/brief 生成")
            return {"id": row["id"], "as_of": row["as_of"],
                    "snapshot_hash": row["data_snapshot_hash"],
                    "content": row["content"],
                    "content_json": json_loads(row["content_json"]),
                    "created_at": row["created_at"]}

    @app.post("/api/run/brief")
    def run_brief():
        from ..agents import brief as brief_mod

        with dbm.get_db() as db:
            return brief_mod.generate(db)

    @app.post("/api/run/fetch")
    def run_fetch():
        from ..cli import cmd_fetch

        rc = cmd_fetch()
        return {"rc": rc}

    @app.get("/api/lessons/today")
    def lesson_today():
        from ..agents import education

        with dbm.get_db() as db:
            dbm._seed_lessons(db)  # 捡起新增课程（幂等）
            lesson = education.pick_lesson(db)
            if not lesson:
                return {"done": True}
            return {"concept": lesson["concept"], "title": lesson["title"],
                    "body": lesson["body"].strip(), "domain": lesson.get("domain"),
                    "relation": education.relation_to_portfolio(db, lesson["concept"]),
                    "quiz": lesson.get("quiz"), "quiz_level": lesson.get("quiz_level", "easy"),
                    "status": lesson.get("status")}

    @app.post("/api/lessons/answer")
    def lesson_answer(a: QuizAnswer):
        import yaml

        from ..agents import education
        from ..config import CONFIG_DIR

        with dbm.get_db() as db:
            cfg = yaml.safe_load((CONFIG_DIR / "lessons.yaml").read_text())
            lesson = next((l for l in cfg["lessons"] if l["concept"] == a.concept), None)
            if not lesson:
                raise HTTPException(404, "concept not found")
            r = education.record_lesson(db, lesson, _today(), a.correct, a.level)
            return {"status": r["status"], "mastery": r["mastery"], "known": r["known"],
                    "level": r["level"], "answer": (lesson.get("quiz") or {}).get("answer")}

    @app.get("/api/lessons/progress")
    def lessons_progress():
        from ..agents import education

        with dbm.get_db() as db:
            dbm._seed_lessons(db)
            return education.progress(db)

    @app.get("/api/roadmap")
    def roadmap():
        from ..agents import roadmap as rm

        with dbm.get_db() as db:
            return rm.get_roadmap(db)

    @app.get("/api/config-status")
    def config_status():
        from ..config import integrations_status, load_env_file

        load_env_file()  # 用户改完 env 文件，刷新页面即可看到（无需重启）
        return integrations_status()

    @app.post("/api/roadmap/toggle")
    def roadmap_toggle(t: RoadmapToggle):
        from ..agents import roadmap as rm

        with dbm.get_db() as db:
            try:
                return rm.toggle_manual(db, t.stage_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc))

    @app.get("/api/research")
    def research_list():
        from ..agents import research as rs

        with dbm.get_db() as db:
            return {"briefs": rs.latest_briefs(db),
                    "watchlist": [{"symbol": c["symbol"], "name": c["cn_name"],
                                   "why": c["why"], "held": bool(db.execute(
                                       "SELECT 1 FROM holdings WHERE symbol=? LIMIT 1",
                                       (c["symbol"],)).fetchone())}
                                  for c in rs.load_companies()]}

    @app.get("/api/research/{symbol}")
    def research_one(symbol: str):
        from ..agents import research as rs

        with dbm.get_db() as db:
            row = db.execute(
                "SELECT * FROM reports WHERE kind='earnings_brief' AND content_json LIKE ? "
                "ORDER BY id DESC LIMIT 1", (f'%"symbol": "{symbol}"%',)).fetchone()
            if row:
                import json

                return json.loads(row["content_json"])
            try:
                return rs.build_brief(db, symbol)
            except ValueError as exc:
                raise HTTPException(404, str(exc))

    @app.post("/api/run/research")
    def run_research():
        from ..agents import research as rs
        from ..providers import notify

        with dbm.get_db() as db:
            r = rs.run_watchlist(db)
        if notify.configured():
            notify.send("📚 WealthOS 研报精读更新：\n" + "\n".join(r["done"]))
        return r

    @app.post("/api/chat")
    def chat_api(c: ChatIn):
        from ..agents import chat as chat_mod

        with dbm.get_db() as db:
            return {"answer": chat_mod.answer(db, c.question)}

    if WEB_DIR.exists():
        class NoCacheStatic(StaticFiles):
            async def get_response(self, path, scope):  # noqa: ANN001
                resp = await super().get_response(path, scope)
                resp.headers["Cache-Control"] = "no-cache"
                return resp

        app.mount("/static", NoCacheStatic(directory=WEB_DIR), name="static")

        @app.get("/")
        def index():
            return FileResponse(WEB_DIR / "index.html",
                                headers={"Cache-Control": "no-cache"})

    @app.exception_handler(Exception)
    async def unhandled(request, exc):  # noqa: ANN001
        return JSONResponse({"error": str(exc)[:300]}, status_code=500)

    return app


def json_list(s):
    import json

    try:
        return json.loads(s or "[]")
    except (TypeError, ValueError):
        return []


def json_loads(s):
    import json

    try:
        return json.loads(s or "{}")
    except (TypeError, ValueError):
        return {}


def _today():
    from datetime import date

    return date.today().isoformat()
