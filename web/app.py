"""
Flask web 伺服器：提供租屋推薦儀表板
端口：由 PORT 環境變數決定（預設 5591）
"""
from flask import Flask, jsonify, send_from_directory
from datetime import datetime, timezone, timedelta
import asyncio
import threading

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
    }


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
            return jsonify({"run": None, "properties": [], "has_new": False})

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

        return jsonify({
            "run":        _run_dict(latest_run),
            "properties": results,
            "has_new":    len(results) > 0,
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

        return jsonify({"run": _run_dict(run), "properties": results})


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
    """手動觸發一次爬蟲（背景執行）"""
    global _scrape_running
    if _scrape_running:
        return jsonify({"status": "already_running"}), 409

    def _run():
        global _scrape_running
        _scrape_running = True
        try:
            from scheduler.daily_job import run_daily_job
            asyncio.run(run_daily_job())
        finally:
            _scrape_running = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"status": "started"}), 202


def run_web(host: str = "0.0.0.0", port: int = 5591, debug: bool = False):
    app.run(host=host, port=port, debug=debug, use_reloader=False)
