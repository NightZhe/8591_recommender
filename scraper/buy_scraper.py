"""
business.591.com.tw 商業不動產爬蟲
搜尋條件：板橋（江翠北）、五股，店面/商辦，20~40坪，0~3000萬
"""
import asyncio
import re
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from .browser import BrowserManager
from database.db import get_db
from database.models import BuyProperty, ScrapeRun

BUY_BASE = "https://business.591.com.tw"

# 搜尋目標區域（名稱 -> region/district 代碼）
SEARCH_AREAS = {
    "板橋": {"region": "3", "district": "1"},
    "五股": {"region": "3", "district": "13"},
}

# 搜尋條件
PRICE_MAX = 3000   # 萬
AREA_MIN  = 20     # 坪
AREA_MAX  = 40     # 坪


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*萬", text)
    if m:
        return float(m.group(1))
    m = re.search(r"[\d.]+", text)
    return float(m.group()) if m else None


def _parse_area(text: str) -> Optional[float]:
    m = re.search(r"([\d.]+)\s*坪", (text or ""))
    return float(m.group(1)) if m else None


def _parse_card(item_info_div, district_name: str) -> Optional[dict]:
    """解析一個 .item-info 卡片"""
    try:
        # 連結與 property_id
        link = item_info_div.select_one("a.link[href*='/sale/']")
        if not link:
            link = item_info_div.select_one("a[href*='/sale/']")
        if not link:
            return None

        href = link.get("href", "")
        pid_m = re.search(r"/sale/(\d+)", href)
        if not pid_m:
            return None
        property_id = pid_m.group(1)

        # 標題（去除 <em> 高亮的干擾，取純文字）
        title = link.get_text(strip=True)

        # 找卡片的父容器（包含所有資訊）
        card = item_info_div.parent if item_info_div.parent else item_info_div

        # 價格
        price_el = card.select_one(".item-info-price strong") or card.select_one(".item-info-price")
        price_text = price_el.get_text() if price_el else ""
        price = _parse_price(price_text)

        # 單價（萬/坪）
        unit_price_el = card.select_one(".item-info-price div")
        unit_price = None
        if unit_price_el:
            up_m = re.search(r"([\d.]+)萬/坪", unit_price_el.get_text())
            if up_m:
                unit_price = float(up_m.group(1))

        # 坪數、地址、樓層 等其他資訊
        full_text = card.get_text(" ", strip=True)

        area = _parse_area(full_text)

        floor_text = ""
        floor_m = re.search(r"(\d+)\s*/\s*(\d+)\s*樓|(\d+)\s*樓", full_text)
        if floor_m:
            floor_text = floor_m.group()

        # 地址：取 tag 之前的文字區塊
        addr_el = card.select_one(".item-info-location") or card.select_one("[class*='location']") or card.select_one("[class*='address']")
        address = addr_el.get_text(strip=True) if addr_el else ""

        # 圖片
        img = card.select_one("img[src]") or card.select_one("img[data-src]")
        image_url = ""
        if img:
            image_url = img.get("src") or img.get("data-src") or ""

        if not property_id:
            return None

        return {
            "property_id": property_id,
            "title": title,
            "url": href,
            "district": district_name,
            "address": address,
            "price": price,
            "unit_price": unit_price,
            "area": area,
            "floor": floor_text,
            "house_type": "商業不動產",
            "image_url": image_url,
        }
    except Exception as e:
        print(f"[buy_scraper] parse error: {e}")
        return None


async def scrape_buy_listings(max_pages: int = 3) -> list[dict]:
    """爬取 business.591.com.tw 商業物件，回傳 dict list"""
    results = []

    async with BrowserManager() as bm:
        ctx = await bm.new_context()
        page = await ctx.new_page()

        for area_name, codes in SEARCH_AREAS.items():
            region   = codes["region"]
            district = codes["district"]

            for page_num in range(1, max_pages + 1):
                first_row = (page_num - 1) * 30
                url = (
                    f"{BUY_BASE}/list?type=2&searchtype=1"
                    f"&region={region}&district={district}"
                    f"&price=0_{PRICE_MAX}&area={AREA_MIN}_{AREA_MAX}"
                    f"&firstRow={first_row}"
                )
                print(f"[buy_scraper] {area_name} page {page_num}: {url}")

                try:
                    await page.goto(url, wait_until="networkidle", timeout=40000)
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                except Exception as e:
                    print(f"[buy_scraper] 載入失敗: {e}")
                    break

                soup = BeautifulSoup(html, "lxml")

                # 找所有物件卡片：business.591 使用 .item-info 包住每個物件
                cards = soup.select(".item-info")

                if not cards:
                    print(f"[buy_scraper] {area_name} p{page_num}: 沒有找到卡片，停止")
                    # debug: 印出 /sale/ 連結數量
                    links = soup.select("a[href*='/sale/']")
                    print(f"[buy_scraper]   (/sale/ links found: {len(links)})")
                    break

                page_results = []
                for card in cards:
                    item = _parse_card(card, area_name)
                    if item:
                        page_results.append(item)

                print(f"[buy_scraper] {area_name} p{page_num}: {len(page_results)} 筆")
                results.extend(page_results)

                if len(cards) < 10:
                    break

                await asyncio.sleep(2)

        await ctx.close()

    # 去重
    seen = {}
    for item in results:
        seen[item["property_id"]] = item
    final = list(seen.values())
    print(f"[buy_scraper] 共 {len(final)} 筆（去重後）")
    return final


def save_buy_listings(listings: list[dict], run_id: int = None) -> tuple[int, int]:
    """寫入 DB，回傳 (新增數, 更新數)"""
    saved = updated = 0
    now = datetime.utcnow()

    with get_db() as db:
        for item in listings:
            existing = db.query(BuyProperty).filter_by(
                property_id=item["property_id"]
            ).first()

            if existing:
                existing.last_seen = now
                existing.price = item["price"] or existing.price
                existing.unit_price = item["unit_price"] or existing.unit_price
                existing.area = item["area"] or existing.area
                existing.is_new = False
                if run_id:
                    existing.scrape_run_id = run_id
                updated += 1
            else:
                prop = BuyProperty(
                    first_seen=now,
                    last_seen=now,
                    is_new=True,
                    scrape_run_id=run_id,
                    **item,
                )
                db.add(prop)
                saved += 1

    print(f"[buy_scraper] saved={saved}, updated={updated}")
    return saved, updated
