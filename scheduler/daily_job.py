import asyncio
from config.settings import DEFAULT_SEARCH_PARAMS, MAX_PAGES_PER_SEARCH
from scraper.property_scraper import scrape_listings, save_listings
from recommender.similarity import compute_recommendations
from notifier.line_notify import send_daily_recommendations


async def run_daily_job():
    """每日排程主流程"""
    print("=" * 50)
    print("[job] 開始每日房源爬取 & 推薦")

    # Step 1: 爬取最新物件
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
        save_listings(
            listings,
            kind=DEFAULT_SEARCH_PARAMS["kind"],
            region=DEFAULT_SEARCH_PARAMS["region"],
        )
    except Exception as e:
        print(f"[job] 爬蟲失敗: {e}")
        return

    # Step 2: 產生推薦
    try:
        recommendations = compute_recommendations()
    except Exception as e:
        print(f"[job] 推薦失敗: {e}")
        return

    # Step 3: 發送 Line 通知
    try:
        send_daily_recommendations(recommendations)
        print("[job] 通知已發送")
    except Exception as e:
        print(f"[job] 通知失敗: {e}")

    print("[job] 每日任務完成")
    print("=" * 50)
