"""
Flask web 伺服器：提供房產搜尋儀表板（租屋 / 買屋住宅 / 買屋商辦）
端口：由 PORT 環境變數決定（預設 5591）
"""
from flask import Flask, jsonify, send_from_directory, request
from datetime import datetime, timezone, timedelta
import asyncio
import threading
import json
import os
from dotenv import load_dotenv

load_dotenv()

from database.db import get_db
from database.models import Property, Recommendation, ScrapeRun

app = Flask(__name__, static_folder="static", static_url_path="")


# ---------- helpers ----------

def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tw = dt + timedelta(hours=8)
    return tw.strftime("%Y-%m-%d %H:%M")


def _run_dict(r: ScrapeRun) -> dict:
    return {
        "id":           r.id,
        "run_at":       _fmt_dt(r.run_at),
        "total_found":  r.total_found or 0,
        "new_count":    r.new_count or 0,
        "search_areas": r.search_areas or "",
        "status":       r.status or "unknown",
        "error_msg":    r.error_msg,
        "mode":         r.error_msg and "unknown" or _infer_mode(r.search_areas or ""),
    }


def _infer_mode(search_areas: str) -> str:
    if "買屋" in search_areas or "店面" in search_areas or "商辦" in search_areas:
        return "buy"
    return "rent"


def _rec_dict(rec: Recommendation, prop: Property) -> dict:
    return {
        "property_id":   prop.property_id,
        "title":         prop.title or "",
        "url":           prop.url or "",
        "district":      prop.district or "",
        "address":       prop.address or prop.district or "",
        "region":        prop.region or "",
        "price":         prop.price,
        "area":          prop.area,
        "floor":         prop.floor or "",
        "rooms":         prop.rooms,
        "living_rooms":  prop.living_rooms,
        "bathrooms":     prop.bathrooms,
        "property_type": prop.property_type or "",
        "image_url":     prop.image_url or "",
        "score":         rec.score,
        "reason":        rec.reason or "",
        "is_new":        True,
    }


# ---------- routes ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/latest")
def api_latest():
    """最新一次爬取後產生的推薦房源"""
    with get_db() as db:
        latest_run = (db.query(ScrapeRun)
                      .filter(ScrapeRun.status == "success")
                      .order_by(ScrapeRun.run_at.desc())
                      .first())

        if not latest_run:
            return jsonify({"run": None, "properties": [], "has_new": False, "mode": "rent"})

        recs = (db.query(Recommendation)
                .filter(Recommendation.recommended_at >= latest_run.run_at)
                .order_by(Recommendation.score.desc())
                .limit(20)
                .all())

        results = []
        for rec in recs:
            prop = db.query(Property).filter_by(property_id=rec.property_id).first()
            if prop:
                results.append(_rec_dict(rec, prop))

        # 若推薦表還沒資料，改顯示最新爬到的物件
        if not results:
            props = (db.query(Property)
                     .filter(Property.is_active == True)
                     .order_by(Property.scraped_at.desc())
                     .limit(20)
                     .all())
            results = [{
                "property_id":   p.property_id,
                "title":         p.title or "",
                "url":           p.url or "",
                "district":      p.district or "",
                "address":       p.address or p.district or "",
                "region":        p.region or "",
                "price":         p.price,
                "area":          p.area,
                "floor":         p.floor or "",
                "rooms":         p.rooms,
                "living_rooms":  p.living_rooms,
                "bathrooms":     p.bathrooms,
                "property_type": p.property_type or "",
                "image_url":     p.image_url or "",
                "score":         None,
                "reason":        "最新上架",
                "is_new":        True,
            } for p in props]

        run_info = _run_dict(latest_run)
        return jsonify({
            "run":        run_info,
            "properties": results,
            "has_new":    len(results) > 0,
            "mode":       run_info["mode"],
        })


@app.route("/api/history")
def api_history():
    """所有 scrape run 清單（最近 60 次）"""
    with get_db() as db:
        runs = (db.query(ScrapeRun)
                .order_by(ScrapeRun.run_at.desc())
                .limit(60)
                .all())
        return jsonify([_run_dict(r) for r in runs])


@app.route("/api/history/<int:run_id>")
def api_history_detail(run_id: int):
    """某次爬取的推薦結果"""
    with get_db() as db:
        run = db.query(ScrapeRun).filter_by(id=run_id).first()
        if not run:
            return jsonify({"error": "not found"}), 404

        recs = (db.query(Recommendation)
                .filter(Recommendation.recommended_at >= run.run_at)
                .order_by(Recommendation.score.desc())
                .limit(20)
                .all())

        results = []
        for rec in recs:
            prop = db.query(Property).filter_by(property_id=rec.property_id).first()
            if prop:
                results.append(_rec_dict(rec, prop))

        run_info = _run_dict(run)
        return jsonify({"run": run_info, "properties": results, "mode": run_info["mode"]})


@app.route("/api/last-error")
def api_last_error():
    """最近一次失敗的完整錯誤訊息"""
    with get_db() as db:
        run = (db.query(ScrapeRun)
               .filter(ScrapeRun.status == "failed")
               .order_by(ScrapeRun.run_at.desc())
               .first())
        if not run:
            return jsonify({"error": None})
        return jsonify(_run_dict(run))


@app.route("/api/status")
def api_status():
    """系統狀態"""
    with get_db() as db:
        total = db.query(Property).count()
        latest = (db.query(ScrapeRun)
                  .order_by(ScrapeRun.run_at.desc())
                  .first())
        return jsonify({
            "total_properties": total,
            "latest_run": _run_dict(latest) if latest else None,
        })


_scrape_running = False


@app.route("/api/trigger-scrape", methods=["POST"])
def trigger_scrape():
    """手動觸發一次爬蟲（背景執行）
    Body JSON: { mode: "rent"|"buy_residential"|"buy_commercial", price_min, price_max }
    """
    global _scrape_running
    if _scrape_running:
        return jsonify({"status": "already_running"}), 409

    body      = request.get_json(silent=True) or {}
    mode      = body.get("mode", "rent")
    price_min = int(body.get("price_min", 0))
    price_max = int(body.get("price_max", 0))

    def _run():
        global _scrape_running
        _scrape_running = True
        try:
            from scheduler.daily_job import run_job_with_params
            asyncio.run(run_job_with_params(mode, price_min, price_max))
        finally:
            _scrape_running = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"status": "started", "mode": mode}), 202


_AI_SYSTEM = """你是一個台灣房產搜尋助手。從用戶的自然語言輸入中提取搜尋參數，**只**回傳以下 JSON 格式，不要加任何說明：

{"mode": "rent"|"buy_residential"|"buy_commercial", "price_min": 整數, "price_max": 整數}

規則：
- mode: 提到「租」「租屋」→ "rent"；提到「買」「購買」「住宅」→ "buy_residential"；提到「店面」「商辦」「商業」→ "buy_commercial"；預設 "rent"
- price_min / price_max: 租屋單位為元/月（「兩萬」→ 20000）；買屋單位為萬元（「一千萬」→ 1000）；無法判斷則填 0
- 只填能確定的欄位，無法判斷的填 0"""


@app.route("/api/ai-parse", methods=["POST"])
def ai_parse():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty input"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY 未設定，請聯絡管理員"}), 503

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_AI_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        result = json.loads(response.content[0].text)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "AI 回傳格式錯誤，請重試"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_web(host: str = "0.0.0.0", port: int = 5591, debug: bool = False):
    app.run(host=host, port=port, debug=debug, use_reloader=False)
