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
DEFAULT_SEARCH_PARAMS = {
    "kind": "1",        # 1=出租, 2=出售
    "region": "1",      # 1=台北市, 3=新北市, 5=高雄市
    "price_min": 0,
    "price_max": 0,     # 0=不限
    "area_min": 0,
    "area_max": 0,
}
