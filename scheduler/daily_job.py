import asyncio
from datetime import datetime
from config.settings import DEFAULT_SEARCH_PARAMS, MAX_PAGES_PER_SEARCH
from scraper.property_scraper import scrape_listings, save_listings
from database.db import get_db
from database.models import ScrapeRun


async def run_daily_job():
    """每日排程主流程（每天早上 09:00 執行）"""
    print("=" * 50)
    print(f"[job] 開始每日租屋爬取  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with get_db() as db:
        run = ScrapeRun(
            run_at=datetime.utcnow(),
            search_areas=f"台北市 {DEFAULT_SEARCH_PARAMS['price_min']}~{DEFAULT_SEARCH_PARAMS['price_max']}元",
            status="running",
        )
        db.add(run)
        db.flush()
        run_id = run.id

    try:
        listings = await scrape_listings(
            kind=DEFAULT_SEARCH_PARAMS["kind"],
            region=DEFAULT_SEARCH_PARAMS["region"],
            price_min=DEFAULT_SEARCH_PARAMS["price_min"],
            price_max=DEFAULT_SEARCH_PARAMS["price_max"],
            area_min=DEFAULT_SEARCH_PARAMS["area_min"],
            area_max=DEFAULT_SEARCH_PARAMS["area_max"],
            max_pages=MAX_PAGES_PER_SEARCH,
        )
        saved, updated = save_listings(
            listings,
            kind=DEFAULT_SEARCH_PARAMS["kind"],
            region=DEFAULT_SEARCH_PARAMS["region"],
        )

        from recommender.similarity import compute_recommendations
        compute_recommendations()

        with get_db() as db:
            run = db.query(ScrapeRun).filter_by(id=run_id).first()
            if run:
                run.total_found = len(listings)
                run.new_count = saved
                run.status = "success"

        print(f"[job] 完成：共 {len(listings)} 筆，新增 {saved}，更新 {updated}")

    except Exception as e:
        print(f"[job] 爬蟲失敗: {e}")
        with get_db() as db:
            run = db.query(ScrapeRun).filter_by(id=run_id).first()
            if run:
                run.status = "failed"
                run.error_msg = str(e)

    print("[job] 每日任務完成")
    print("=" * 50)
