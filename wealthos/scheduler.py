"""定时任务（架构文档 G2 调度表的 MVP 版）。"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from . import db as dbm


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Hong_Kong")

    def job_news():
        from .ingest import dispatch

        with dbm.get_db() as db:
            dbm._seed_sources(db)
            dispatch.fetch_all(db)

    def job_quotes():
        from .providers import fx as fx_mod
        from .providers import quotes as q_mod

        with dbm.get_db() as db:
            currencies = {r["currency"] for r in db.execute("SELECT currency FROM accounts")}
            currencies |= {r["currency"] for r in db.execute("SELECT currency FROM holdings")}
            currencies.discard("USD")
            fx_mod.fetch_fx_latest(db, sorted(currencies))
            q_mod.refresh_holdings_prices(db)

    def job_exposures():
        from .engine import exposures as exp_mod
        from .ingest import relevance as rel_mod

        with dbm.get_db() as db:
            exp = exp_mod.compute_exposures(db)
            if exp.get("as_of"):
                exp_mod.persist_exposures(db, exp)
                rel_mod.attach_my_exposure_nodes(db, exp["as_of"])
                rel_mod.score_items(db)

    def job_brief():
        from .agents import brief as brief_mod

        with dbm.get_db() as db:
            brief_mod.generate(db)

    def job_research():
        from .agents import research as rs
        from .providers import notify

        with dbm.get_db() as db:
            r = rs.run_watchlist(db)
        if r["done"] and notify.configured():
            notify.send("📚 每周研报精读已更新：" + "、".join(r["done"]))

    sched.add_job(job_news, "interval", minutes=15, id="news")
    sched.add_job(job_quotes, "cron", hour=6, minute=30, id="quotes")     # 收盘后
    sched.add_job(job_exposures, "cron", hour=6, minute=45, id="exposures")
    sched.add_job(job_brief, "cron", hour=7, minute=5, id="brief")        # 晨报
    sched.add_job(job_research, "cron", day_of_week="mon", hour=8, minute=0,
                  id="research")                                          # 每周一研报
    sched.start()
    return sched
