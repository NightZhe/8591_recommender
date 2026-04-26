"""
buy.591.com.tw 買屋爬蟲
搜尋條件：板橋（江翠北）、五股，一樓店面，20~40坪，0~3000萬
"""
import asyncio
import re
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from .browser import BrowserManager
from database.db import get_db
from database.models import BuyProperty, ScrapeRun

BUY_BASE = "https://buy.591.com.tw"

# 搜尋目標區域（名稱 -> district 代碼）
SEARCH_AREAS = {
    "板橋": {"region": "3", "district": "1"},
    "五股": {"region": "3", "district": "13"},
}

# 搜尋條件
PRICE_MAX = 3000   # 萬
AREA_MIN  = 20     # 坪
AREA_MAX  = 40     # 坪
# houseType: 4=店面/商辦；floor=1 只看一樓
HOUSE_TYPE = "4"
FLOOR      = "1"


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


def _parse_card(card, district_name: str) -> Optional[dict]:
    """解析一張物件卡片，回傳 dict 或 None"""
    try:
        # --- 取得連結與 property_id ---
        link = card.select_one("a[href]")
        if not link:
            link = card.find("a")
        href = link.get("href", "") if link else ""
        if not href.startswith("http"):
            href = BUY_BASE + href
        pid_m = re.search(r"/(\d+)(?:[/?]|$)", href)
        if not pid_m:
            return None
        property_id = pid_m.group(1)

        # --- 標題 ---
        title_el = (card.select_one(".house-title") or
                    card.select_one(".title") or
                    card.select_one("h3") or
                    card.select_one("h2"))
        title = title_el.get_text(strip=True) if title_el else ""

        # --- 價格 ---
        price_el = (card.select_one(".price-num") or
                    card.select_one(".price") or
                    card.select_one("[class*='price']"))
        price = _parse_price(price_el.get_text() if price_el else "")

        # --- 坪數 ---
        area_el = (card.select_one(".area") or
                   card.select_one("[class*='area']") or
                   card.select_one(".info"))
        area_text = area_el.get_text() if area_el else card.get_text()
        area = _parse_area(area_text)

        # --- 樓層 ---
        floor_text = ""
        floor_m = re.search(r"(\d+\s*/\s*\d+)\s*樓|(\d+)\s*樓", card.get_text())
        if floor_m:
            floor_text = floor_m.group()

        # --- 地址 ---
        addr_el = (card.select_one(".address") or
                   card.select_one("[class*='address']") or
                   card.select_one(".info-txt"))
        address = addr_el.get_text(strip=True) if addr_el else ""

        # --- 圖片 ---
        img = card.select_one("img")
        image_url = ""
        if img:
            image_url = img.get("data-src") or img.get("src") or ""

        # --- 單價 ---
        unit_price = None
        if price and area and area > 0:
            unit_price = round(price / area, 1)

        if not title and not price:
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
            "house_type": "店面",
            "image_url": image_url,
        }
    except Exception as e:
        print(f"[buy_scraper] parse error: {e}")
        return None


async def scrape_buy_listings(max_pages: int = 3) -> list[dict]:
    """爬取買屋物件，回傳 dict list"""
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
                    f"{BUY_BASE}/?type=1&searchtype=1"
                    f"&region={region}&district={district}"
                    f"&houseType={HOUSE_TYPE}&floor={FLOOR}"
                    f"&price=0_{PRICE_MAX}&area={AREA_MIN}_{AREA_MAX}"
                    f"&firstRow={first_row}&totalRows=999"
                )
                print(f"[buy_scraper] {area_name} page {page_num}: {url}")

                try:
                    await page.goto(url, wait_until="networkidle", timeout=40000)
                    await page.wait_for_timeout(2500)
                    html = await page.content()
                except Exception as e:
                    print(f"[buy_scraper] 載入失敗: {e}")
                    break

                soup = BeautifulSoup(html, "lxml")

                # 嘗試多種可能的容器 selector
                cards = (soup.select(".houseList-item") or
                         soup.select(".buy-item") or
                         soup.select(".house-item") or
                         soup.select("ul.house-list > li") or
                         soup.select(".list-items .item"))

                if not cards:
                    print(f"[buy_scraper] {area_name} p{page_num}: 沒有找到卡片，停止")
                    break

                page_results = []
                for card in cards:
                    item = _parse_card(card, area_name)
                    if item:
                        page_results.append(item)

                print(f"[buy_scraper] {area_name} p{page_num}: {len(page_results)} 筆")
                results.extend(page_results)

                if len(cards) < 10:
                    break  # 最後一頁

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
                # 更新 last_seen 與價格
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
