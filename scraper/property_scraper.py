import asyncio
import re
from typing import Optional
from bs4 import BeautifulSoup
from .browser import BrowserManager
from database.db import get_db
from database.models import Property

BASE_URL = "https://rent.591.com.tw"

# 591 縣市代碼
REGION_CODES = {
    "台北市": "1", "新北市": "3", "基隆市": "2", "桃園市": "6",
    "新竹市": "9", "新竹縣": "10", "苗栗縣": "13", "台中市": "8",
    "彰化縣": "14", "南投縣": "16", "雲林縣": "20", "嘉義市": "22",
    "台南市": "7", "高雄市": "5", "屏東縣": "27", "宜蘭縣": "4",
    "花蓮縣": "30", "台東縣": "29", "澎湖縣": "32",
}


def _parse_float(text: str) -> Optional[float]:
    m = re.search(r"[\d.]+", (text or "").replace(",", ""))
    return float(m.group()) if m else None


def _parse_listing(card) -> Optional[dict]:
    """解析 591 .recommend-ware 卡片"""
    try:
        title_tag = card.select_one("a.title")
        if not title_tag:
            return None

        href = title_tag.get("href", "")
        property_id_match = re.search(r"/(\d+)$", href)
        if not property_id_match:
            return None
        property_id = property_id_match.group(1)

        price_tag = card.select_one(".price")
        address_tag = card.select_one(".address-info")
        area_tag = card.select_one(".area")
        img_tag = card.select_one("img[data-src]") or card.select_one("img")
        labels = [el.get_text(strip=True) for el in card.select(".label-item")]

        # 解析地址資訊 "社區名稱 區域-街道 N房/N坪"
        address_text = address_tag.get_text(strip=True) if address_tag else ""
        district = ""
        address = ""
        area_sqm = None
        rooms = None

        # 地址格式: "社區名 XX區-街道名 N房/N坪"
        district_match = re.search(r"([^\s]+[縣市]?[^\s]*區)", address_text)
        if district_match:
            district = district_match.group(1)

        street_match = re.search(r"區[- ]?(.+?)\s*(?:\d+房|$)", address_text)
        if street_match:
            address = street_match.group(1)

        area_match = re.search(r"(\d+(?:\.\d+)?)坪", address_text)
        if area_match:
            area_sqm = float(area_match.group(1))

        rooms_match = re.search(r"(\d+)房", address_text)
        if rooms_match:
            rooms = int(rooms_match.group(1))

        return {
            "property_id": property_id,
            "title": title_tag.get_text(strip=True),
            "url": href,
            "price": _parse_float(price_tag.get_text() if price_tag else ""),
            "area": area_sqm,
            "district": district,
            "address": address,
            "rooms": rooms,
            "features": str(labels),
            "image_url": (img_tag.get("data-src") or img_tag.get("src", "")) if img_tag else "",
        }
    except Exception as e:
        print(f"[scraper] parse error: {e}")
        return None


async def scrape_listings(
    kind: str = "1",
    region: str = "1",
    price_min: int = 0,
    price_max: int = 0,
    area_min: int = 0,
    area_max: int = 0,
    max_pages: int = 5,
) -> list[dict]:
    """爬取 591 物件列表，回傳 dict list"""
    results = []

    async with BrowserManager() as bm:
        ctx = await bm.new_context()
        page = await ctx.new_page()

        for page_num in range(1, max_pages + 1):
            params = f"kind={kind}&region={region}&page={page_num}"
            if price_min or price_max:
                params += f"&price={price_min},{price_max}"
            if area_min or area_max:
                params += f"&area={area_min},{area_max}"

            url = f"{BASE_URL}/list?{params}"
            print(f"[scraper] fetching page {page_num}: {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"[scraper] page {page_num} error: {e}")
                break

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select(".recommend-ware")

            if not cards:
                print(f"[scraper] no cards on page {page_num}, stopping")
                break

            for card in cards:
                item = _parse_listing(card)
                if item:
                    results.append(item)

            print(f"[scraper] page {page_num}: {len(cards)} 筆")
            await asyncio.sleep(1.5)

        await ctx.close()

    print(f"[scraper] 共爬取: {len(results)} 筆")
    return results


def save_listings(listings: list[dict], kind: str = "1", region: str = "1"):
    """將爬取結果寫入資料庫（自動去重）"""
    saved = updated = 0

    # 同批次去重，保留最後出現的
    seen: dict = {}
    for item in listings:
        seen[item["property_id"]] = item
    unique_listings = list(seen.values())

    with get_db() as db:
        for item in unique_listings:
            existing = db.query(Property).filter_by(
                property_id=item["property_id"]
            ).first()

            if existing:
                for key, val in item.items():
                    if val is not None:
                        setattr(existing, key, val)
                existing.is_active = True
                updated += 1
            else:
                prop = Property(kind=kind, region=region, **item)
                db.add(prop)
                saved += 1

    print(f"[scraper] saved={saved}, updated={updated}")
    return saved, updated
