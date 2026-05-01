from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///591.db")
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")

SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "24"))
MAX_PAGES_PER_SEARCH = int(os.getenv("MAX_PAGES_PER_SEARCH", "5"))

TOP_N_RECOMMENDATIONS = int(os.getenv("TOP_N_RECOMMENDATIONS", "10"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))

# 591 搜尋條件設定（可依需求調整）
# 曾先生需求：台北市，套房/獨立套房，租金 20,000–32,000，坪數 10–25 坪
DEFAULT_SEARCH_PARAMS = {
    "kind": "1",         # 1=出租
    "region": "1",       # 1=台北市
    "price_min": 20000,
    "price_max": 32000,
    "area_min": 10,
    "area_max": 25,
}
