"""
Flask web 伺服器：提供買屋物件儀表板
端口：5591
"""
from flask import Flask, jsonify, send_from_directory
from datetime import datetime, timezone
import os

from database.db import get_db
from database.models import BuyProperty, ScrapeRun

app = Flask(__name__, static_folder="static", static_url_path="")


# ---------- helpers ----------

def _prop_dict(p: BuyProperty) -> dict:
    return {
        "id":          p.id,
        "property_id": p.property_id,
        "title":       p.title or "",
        "url":         p.url or "",
        "district":    p.district or "",
        "address":     p.address or "",
        "price":       p.price,
        "unit_price":  p.unit_price,
        "area":        p.area,
        "floor":       p.floor or "",
        "house_type":  p.house_type or "",
        "image_url":   p.image_url or "",
        "is_new":      p.is_new,
        "first_seen":  _fmt_dt(p.first_seen),
        "last_seen":   _fmt_dt(p.last_seen),
    }


def _run_dict(r: ScrapeRun) -> dict:
    return {
        "id":          r.id,
        "run_at":      _fmt_dt(r.run_at),
        "total_found": r.total_found or 0,
        "new_count":   r.new_count or 0,
        "search_areas": r.search_areas or "",
        "status":      r.status or "unknown",
        "error_msg":   r.error_msg,
    }


def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # 轉台灣時間 UTC+8
    from datetime import timedelta
    tw = dt + timedelta(hours=8)
    return tw.strftime("%Y-%m-%d %H:%M")


# ---------- routes ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/latest")
def api_latest():
    """最新一次爬取的物件"""
    with get_db() as db:
        latest_run = (db.query(ScrapeRun)
                      .filter(ScrapeRun.status == "success")
                      .order_by(ScrapeRun.run_at.desc())
                      .first())

        if not latest_run:
            return jsonify({"run": None, "properties": [], "has_new": False})

        props = (db.query(BuyProperty)
                 .filter(BuyProperty.scrape_run_id == latest_run.id)
                 .order_by(BuyProperty.is_new.desc(), BuyProperty.price)
                 .all())

        return jsonify({
            "run":        _run_dict(latest_run),
            "properties": [_prop_dict(p) for p in props],
            "has_new":    any(p.is_new for p in props),
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
    """某次 scrape run 的物件"""
    with get_db() as db:
        run = db.query(ScrapeRun).filter_by(id=run_id).first()
        if not run:
            return jsonify({"error": "not found"}), 404

        props = (db.query(BuyProperty)
                 .filter(BuyProperty.scrape_run_id == run_id)
                 .order_by(BuyProperty.is_new.desc(), BuyProperty.price)
                 .all())

        return jsonify({
            "run":        _run_dict(run),
            "properties": [_prop_dict(p) for p in props],
        })


@app.route("/api/all")
def api_all():
    """全部物件（不分 run，用於開發測試）"""
    with get_db() as db:
        props = (db.query(BuyProperty)
                 .order_by(BuyProperty.first_seen.desc())
                 .limit(200)
                 .all())
        return jsonify([_prop_dict(p) for p in props])


@app.route("/api/status")
def api_status():
    """系統狀態"""
    with get_db() as db:
        total = db.query(BuyProperty).count()
        latest = (db.query(ScrapeRun)
                  .order_by(ScrapeRun.run_at.desc())
                  .first())
        return jsonify({
            "total_properties": total,
            "latest_run": _run_dict(latest) if latest else None,
        })


def run_web(host: str = "0.0.0.0", port: int = 5591, debug: bool = False):
    app.run(host=host, port=port, debug=debug, use_reloader=False)
