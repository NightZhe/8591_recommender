# 8591 房源推薦系統

每天自動爬取 8591 房源，根據你的瀏覽紀錄推薦相似物件，透過 Line 通知。

## 安裝

```bash
cd 8591_recommender
pip install -r requirements.txt
playwright install chromium
```

## 設定

```bash
cp .env.example .env
# 編輯 .env，填入 LINE_NOTIFY_TOKEN 和搜尋條件
```

取得 Line Notify Token：https://notify-bot.line.me/my/

## 使用方式

```bash
# 立刻執行一次（爬取 + 推薦 + 通知）
python main.py run

# 啟動排程器（每天早上 9:00 自動執行）
python main.py start

# 記錄你看過的物件（輸入 8591 物件頁面的數字 ID）
python main.py view 12345678
```

## 專案結構

```
8591_recommender/
├── config/settings.py          # 環境變數與設定
├── scraper/
│   ├── browser.py              # Playwright 瀏覽器管理
│   └── property_scraper.py     # 8591 爬蟲
├── database/
│   ├── models.py               # SQLAlchemy 資料模型
│   └── db.py                   # DB 連線與 session
├── recommender/
│   ├── feature_extractor.py    # 物件特徵向量化
│   └── similarity.py           # Cosine similarity 推薦引擎
├── notifier/
│   └── line_notify.py          # Line Notify 通知
├── scheduler/
│   └── daily_job.py            # 每日排程任務
└── main.py                     # 程式進入點
```

## 推薦邏輯

1. 記錄你手動瀏覽的物件 (`python main.py view <id>`)
2. 系統從瀏覽紀錄中學習你的偏好（價格、坪數、地區、類型）
3. 每天爬取新物件，用 **Cosine Similarity** 找出最相似的 Top-10
4. 透過 Line 通知推送

## 調整搜尋範圍

編輯 `config/settings.py` 中的 `DEFAULT_SEARCH_PARAMS`：

```python
DEFAULT_SEARCH_PARAMS = {
    "kind": "1",        # 1=出租, 2=出售
    "region": "01",     # 01=台北市, 02=新北市...
    "price_min": 10000, # 最低租金
    "price_max": 30000, # 最高租金
    "area_min": 10,     # 最小坪數
    "area_max": 30,     # 最大坪數
}
```
