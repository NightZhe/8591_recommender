import asyncio
import argparse
import threading
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.db import init_db
from database.models import ViewLog
from database.db import get_db
from scheduler.daily_job import run_daily_job

_DEFAULT_PORT = int(os.environ.get("PORT", 5591))


def add_view_log(property_id: str):
    """手動記錄瀏覽紀錄（CLI 輔助工具）"""
    with get_db() as db:
        log = ViewLog(property_id=property_id, source="manual")
        db.add(log)
    print(f"[main] 已記錄瀏覽: {property_id}")


def start_web(port: int = 5591):
    """在背景 thread 啟動 Flask 網頁伺服器"""
    from web.app import run_web
    print(f"[web] 啟動網頁伺服器：http://localhost:{port}")
    run_web(port=port)


async def run_scheduler(port: int = 5591, no_web: bool = False):
    """啟動排程器（每晚 22:00），同時跑網頁伺服器"""

    if not no_web:
        t = threading.Thread(target=start_web, args=(port,), daemon=True)
        t.start()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_job,
        trigger="cron",
        hour=9,
        minute=0,
        id="daily_rent_scrape",
    )
    scheduler.start()
    print("[main] 排程器已啟動，每天 09:00 爬取租屋物件")
    print("[main] Ctrl+C 停止")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[main] 排程器已停止")


async def main():
    parser = argparse.ArgumentParser(description="591 買屋追蹤系統")
    subparsers = parser.add_subparsers(dest="command")

    # start：啟動排程器 + 網頁
    sp_start = subparsers.add_parser("start", help="啟動排程器 + 網頁伺服器（每天 22:00 自動執行）")
    sp_start.add_argument("--port", type=int, default=_DEFAULT_PORT, help="網頁端口（預設讀 PORT 環境變數）")
    sp_start.add_argument("--no-web", action="store_true", help="不啟動網頁伺服器")

    # run：立刻執行一次爬取
    subparsers.add_parser("run", help="立刻執行一次爬取")

    # web：只啟動網頁伺服器
    sp_web = subparsers.add_parser("web", help="只啟動網頁伺服器（不排程）")
    sp_web.add_argument("--port", type=int, default=_DEFAULT_PORT, help="端口（預設讀 PORT 環境變數）")

    # view：記錄瀏覽
    view_parser = subparsers.add_parser("view", help="記錄瀏覽某物件")
    view_parser.add_argument("property_id", help="591 物件 ID")

    args = parser.parse_args()

    # 初始化資料庫
    init_db()
    print("[main] 資料庫初始化完成")

    if args.command == "start":
        await run_scheduler(port=getattr(args, "port", 5591),
                            no_web=getattr(args, "no_web", False))

    elif args.command == "run":
        await run_daily_job()

    elif args.command == "web":
        port = getattr(args, "port", 5591)
        print(f"[web] http://localhost:{port}")
        from web.app import run_web
        run_web(port=port, debug=True)

    elif args.command == "view":
        add_view_log(args.property_id)

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
