import asyncio
import argparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.db import init_db
from database.models import ViewLog
from database.db import get_db
from scheduler.daily_job import run_daily_job


def add_view_log(property_id: str):
    """手動記錄瀏覽紀錄（CLI 輔助工具）"""
    with get_db() as db:
        log = ViewLog(property_id=property_id, source="manual")
        db.add(log)
    print(f"[main] 已記錄瀏覽: {property_id}")


async def run_scheduler():
    """啟動排程器，每天早上 9:00 執行"""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_job,
        trigger="cron",
        hour=9,
        minute=0,
        id="daily_recommendation",
    )
    scheduler.start()
    print("[main] 排程器已啟動，每天 09:00 執行推薦任務")
    print("[main] Ctrl+C 停止")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[main] 排程器已停止")


async def main():
    parser = argparse.ArgumentParser(description="8591 房源推薦系統")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("start", help="啟動排程器（每天自動執行）")
    subparsers.add_parser("run", help="立刻執行一次爬取+推薦")

    view_parser = subparsers.add_parser("view", help="記錄瀏覽某物件")
    view_parser.add_argument("property_id", help="8591 物件 ID")

    args = parser.parse_args()

    # 初始化資料庫
    init_db()
    print("[main] 資料庫初始化完成")

    if args.command == "start":
        await run_scheduler()
    elif args.command == "run":
        await run_daily_job()
    elif args.command == "view":
        add_view_log(args.property_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
