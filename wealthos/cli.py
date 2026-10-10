"""WealthOS CLI：init-db / import / fetch / brief / lesson / status / serve。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import db as dbm


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wealthos")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="建库 + 种子数据")
    pi = sub.add_parser("import", help="导入 CSV/Flex XML")
    pi.add_argument("path")
    pf = sub.add_parser("fetch", help="拉取行情+汇率+新闻")
    pf.add_argument("--no-news", action="store_true")
    pf.add_argument("--no-quotes", action="store_true")
    pb = sub.add_parser("brief", help="生成 Daily Brief")
    pb.add_argument("--print", dest="do_print", action="store_true")
    pl = sub.add_parser("lesson", help="今日一课")
    pl.add_argument("--print", dest="do_print", action="store_true")
    sub.add_parser("status", help="数据新鲜度总览")
    ps = sub.add_parser("serve", help="启动 API + Web UI")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8787)
    ps.add_argument("--no-scheduler", action="store_true")
    pc = sub.add_parser("chat", help="终端问答")
    pc.add_argument("question", nargs="+")
    pd_ = sub.add_parser("demo", help="示例数据：load 载入 / clear 清除")

    pd_.add_argument("action", choices=["load", "clear"])
    pr = sub.add_parser("research", help="明星公司研报精读")
    pr.add_argument("symbol", nargs="?", help="留空=跑全部观察名单")
    sub.add_parser("doctor", help="接口打通自检（配置了 Telegram 会真发一条测试消息）")

    args = p.parse_args(argv)
    if args.cmd == "init-db":
        dbm.init_db()
        print("✓ 数据库与种子就绪")
        return 0

    if args.cmd == "import":
        return cmd_import(args.path)

    if args.cmd == "fetch":
        return cmd_fetch(no_news=args.no_news, no_quotes=args.no_quotes)

    if args.cmd == "brief":
        with dbm.get_db() as db:
            from .agents import brief as brief_mod

            result = brief_mod.generate(db)
        if result["audit_failures"]:
            print(f"⚠ 审计未通过: {result['audit_failures']}", file=sys.stderr)
        if args.do_print:
            print(result["content"])
        else:
            print(f"✓ Daily Brief #{result['report_id']} 生成（snapshot {result['snapshot_hash']}）"
                  f" --print 查看")
        return 0

    if args.cmd == "lesson":
        with dbm.get_db() as db:
            from .agents import education

            lesson = education.pick_lesson(db)
        if not lesson:
            print("课程库已学完一轮")
            return 0
        if args.do_print:
            print(f"📖 {lesson['title']}\n{lesson['body'].strip()}")
            q = lesson.get("quiz") or {}
            print(f"\n小问题：{q.get('q')}\n选项：{' / '.join(q.get('options', []))}")
        else:
            print(f"📖 今日一课：{lesson['title']}")
        return 0

    if args.cmd == "status":
        return cmd_status()

    if args.cmd == "serve":
        import uvicorn

        from .api.app import create_app

        if not args.no_scheduler:
            from .scheduler import start_scheduler

            start_scheduler()
        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
        return 0

    if args.cmd == "chat":
        from .agents.chat import answer

        with dbm.get_db() as db:
            print(answer(db, " ".join(args.question)))
        return 0

    if args.cmd == "demo":
        from . import demo as demo_mod
        from .engine.exposures import compute_exposures, persist_exposures

        with dbm.get_db() as db:
            if args.action == "load":
                r = demo_mod.load_demo(db)
                if r.get("loaded"):
                    exp = compute_exposures(db)
                    if exp.get("as_of"):
                        persist_exposures(db, exp)
                    print("✓ 示例数据已载入（账户名带「示例·」前缀，demo clear 一键清除）")
                else:
                    print(f"→ {r.get('note')}")
            else:
                r = demo_mod.clear_demo(db)
                print(f"✓ 已清除 {r.get('cleared', 0)} 个示例账户")
        return 0

    if args.cmd == "doctor":
        return cmd_doctor()

    if args.cmd == "research":
        from .agents import research as rs

        with dbm.get_db() as db:
            if args.symbol:
                brief = rs.build_brief(db, args.symbol.upper())
                print(f"✓ {brief['name']}（{brief['symbol']}）研报精读已生成："
                      f"{len(brief['sections'])} 节 · {brief['data_source']}")
            else:
                r = rs.run_watchlist(db)
                print(f"✓ 完成 {len(r['done'])} 家：{', '.join(r['done'])}")
                if r["failed"]:
                    print(f"⚠ 失败：{r['failed']}")
        return 0
    return 1


def cmd_doctor() -> int:
    from .config import integrations_status, load_env_file

    load_env_file()  # 刚写进 env 文件的 key 立即生效
    st = integrations_status()
    print("WealthOS 接口打通自检")
    print("=" * 46)
    llm = st["llm"]
    if llm["configured"]:
        where = "本机（数据不出电脑）" if llm["local"] else f"云端（{llm['provider']} · {llm['key']}）"
        print(f"✅ LLM      {llm['model']} @ {where}")
    else:
        print("⛔ LLM      未配置 → 简报/对话保持确定性模式（完全可用，只是没有 AI 润色）")
    if st["telegram"]["configured"]:
        from .providers.notify import send

        ok = send("✅ WealthOS 已打通 Telegram —— 以后晨报和研报会自动推到这里。")
        print(f"{'✅' if ok else '⚠️'} Telegram token={st['telegram']['token']} "
              f"chat_id={st['telegram']['chat_id']} "
              + ("测试消息已发送，去 Telegram 看看！" if ok else "测试发送失败，检查 token/chat_id"))
    else:
        print("⛔ Telegram 未配置 → 晨报只能在网页看")
    print(("✅" if st["fred"]["configured"] else "⛔")
          + f" FRED      {st['fred']['key'] or '未配置 → 利率数据走无 key 备源'}")
    print(("✅" if st["xueqiu"]["configured"] else "⛔")
          + f" 雪球      {st['xueqiu']['cookie'] or '未配置 → 行情走 Yahoo/Stooq'}")
    print(("✅" if st["exa"]["configured"] else "⛔")
          + f" Exa 搜索  {st['exa']['key'] or '未配置 → 深度研究退化为本地数据'}")
    print(("✅" if st["x"]["configured"] else "⛔")
          + " X 情报    " + ("已配置（信号层开发中）" if st["x"]["configured"]
                              else "未配置（可选付费，暂不影响任何功能）"))
    print("=" * 46)
    print("配置方法：把 KEY=VALUE 逐行写进 ~/.wealthos/env，然后重新运行本命令。")
    print("保姆级步骤见网页「⚙️ 接口」页或 KEYS_GUIDE.md。")
    return 0


def cmd_import(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f"文件不存在: {p}", file=sys.stderr)
        return 1
    with dbm.get_db() as db:
        if p.suffix.lower() == ".xml":
            from .importers.flex import import_flex

            result = import_flex(p, db)
        else:
            from .importers.csv_import import import_csv

            result = import_csv(p, db)
        from .engine import exposures as exp_mod

        exp = exp_mod.compute_exposures(db)
        if exp.get("as_of"):
            exp_mod.persist_exposures(db, exp)
    print(f"✓ 导入 {result}")
    return 0


def cmd_fetch(no_news: bool = False, no_quotes: bool = False) -> int:
    with dbm.get_db() as db:
        summary = {}
        if not no_quotes:
            from .providers import fx as fx_mod
            from .providers import quotes as q_mod

            currencies = {r["currency"] for r in db.execute("SELECT currency FROM accounts")}
            currencies |= {r["currency"] for r in db.execute("SELECT currency FROM holdings")}
            currencies.discard("USD")
            try:
                n = fx_mod.fetch_fx_latest(db, sorted(currencies))
                summary["fx"] = f"{n} 条"
                days = [r["as_of"] for r in db.execute(
                    "SELECT DISTINCT as_of FROM holdings")]
                summary["fx"] += f"（历史补 {fx_mod.fx_for_dates(db, days, sorted(currencies))} 条）"
            except Exception as exc:  # noqa: BLE001
                summary["fx"] = f"失败: {exc}"
            try:
                from .engine.networth import recompute_valuations

                rv = recompute_valuations(db)  # 汇率齐了，重算全部估值日
                if rv["warned_accounts"]:
                    summary["valuations"] = f"重算 {rv['days']} 天（{rv['warned_accounts']} 处缺汇率）"
            except Exception as exc:  # noqa: BLE001
                summary["valuations"] = f"重算失败: {exc}"
            try:
                r = q_mod.refresh_holdings_prices(db)
                summary["quotes"] = f"{r.get('updated', 0)} 个标的更新至 {r.get('as_of', '-')}"
            except Exception as exc:  # noqa: BLE001
                summary["quotes"] = f"失败: {exc}"
        if not no_news:
            from .ingest import dispatch

            try:
                dbm._seed_sources(db)  # 捡起新增的源（幂等）
                res = dispatch.fetch_all(db)
                summary["news"] = (f"新增 {res['new']} 条"
                                   + (f"，失败: {res['failed']}" if res["failed"] else ""))
            except Exception as exc:  # noqa: BLE001
                summary["news"] = f"失败: {exc}"
        # 敞口与相关性重算
        from .engine import exposures as exp_mod
        from .ingest import relevance as rel_mod

        exp = exp_mod.compute_exposures(db)
        if exp.get("as_of"):
            exp_mod.persist_exposures(db, exp)
            rel_mod.attach_my_exposure_nodes(db, exp["as_of"])
            rel_mod.score_items(db)
    for k, v in summary.items():
        print(f"✓ {k}: {v}")
    return 0


def cmd_status() -> int:
    with dbm.get_db() as db:
        rows = {
            "accounts": db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"],
            "holdings_days": [r["as_of"] for r in db.execute(
                "SELECT DISTINCT as_of FROM holdings ORDER BY as_of DESC LIMIT 3")],
            "fx_days": [r["as_of"] for r in db.execute(
                "SELECT DISTINCT as_of FROM fx_rates ORDER BY as_of DESC LIMIT 3")],
            "items": db.execute("SELECT COUNT(*) c FROM items").fetchone()["c"],
            "sources_ok": db.execute(
                "SELECT COUNT(*) c FROM sources WHERE last_status='ok'").fetchone()["c"],
            "reports": db.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"],
            "llm_calls": db.execute("SELECT COUNT(*) c FROM llm_calls").fetchone()["c"],
        }
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
