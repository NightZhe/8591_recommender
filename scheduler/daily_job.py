import asyncio
from datetime import datetime
from config.settings import DEFAULT_SEARCH_PARAMS, MAX_PAGES_PER_SEARCH
from scraper.property_scraper import scrape_listings, save_listings
from database.db import get_db
from database.models import ScrapeRun

# 各模式的 search_areas 標籤
_MODE_LABELS = {
    "rent":             "租屋 台北市",
    "buy_residential":  "買屋 住宅 台北市",
    "buy_commercial":   "買屋 店面/商辦",
}


async def run_job_with_params(mode: str = "rent", price_min: int = 0, price_max: int = 0):
    """依前端選擇的模式與價格範圍執行爬蟲，並寫入 ScrapeRun 紀錄。
    mode: 'rent' | 'buy_residential' | 'buy_commercial'
    """
    print("=" * 50)
    label = _MODE_LABELS.get(mode, mode)
    price_desc = f"  {price_min}~{price_max}" if price_min or price_max else ""
    print(f"[job] 開始爬取  mode={mode}  price={price_min}~{price_max}  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with get_db() as db:
        run = ScrapeRun(
            run_at=datetime.utcnow(),
            search_areas=f"{label}{price_desc}",
            status="running",
        )
        db.add(run)
        db.flush()
        run_id = run.id

    try:
        listings, saved, updated = await _do_scrape(mode, price_min, price_max)

        with get_db() as db:
            run = db.query(ScrapeRun).filter_by(id=run_id).first()
            if run:
                run.total_found = len(listings)
                run.new_count   = saved
                run.status      = "success"

        print(f"[job] 完成：共 {len(listings)} 筆，新增 {saved}，更新 {updated}")

    except Exception as e:
        print(f"[job] 爬蟲失敗: {e}")
        with get_db() as db:
            run = db.query(ScrapeRun).filter_by(id=run_id).first()
            if run:
                run.status    = "failed"
                run.error_msg = str(e)

    print("[job] 任務完成")
    print("=" * 50)


async def _do_scrape(mode: str, price_min: int, price_max: int):
    """實際呼叫對應爬蟲，回傳 (listings, saved, updated)"""
    if mode == "buy_commercial":
        from scraper.buy_scraper import scrape_buy_listings, save_buy_listings
        listings = await scrape_buy_listings(max_pages=MAX_PAGES_PER_SEARCH)
        saved, updated = save_buy_listings(listings)
        return listings, saved, updated

    # rent 或 buy_residential：同一個 scraper，kind 不同
    kind = "1" if mode == "rent" else "2"
    region = DEFAULT_SEARCH_PARAMS.get("region", "1")
    area_min = DEFAULT_SEARCH_PARAMS.get("area_min", 0) if mode == "rent" else 0
    area_max = DEFAULT_SEARCH_PARAMS.get("area_max", 0) if mode == "rent" else 0

    listings = await scrape_listings(
        kind=kind,
        region=region,
        price_min=price_min or DEFAULT_SEARCH_PARAMS.get("price_min", 0),
        price_max=price_max or DEFAULT_SEARCH_PARAMS.get("price_max", 0),
        area_min=area_min,
        area_max=area_max,
        max_pages=MAX_PAGES_PER_SEARCH,
    )
    saved, updated = save_listings(listings, kind=kind, region=region)

    if mode == "rent":
        from recommender.similarity import compute_recommendations
        compute_recommendations()

    return listings, saved, updated


async def run_daily_job():
    """每天 09:00 排程預設執行：租屋搜尋"""
    await run_job_with_params(
        mode="rent",
        price_min=DEFAULT_SEARCH_PARAMS.get("price_min", 20000),
        price_max=DEFAULT_SEARCH_PARAMS.get("price_max", 32000),
    )
