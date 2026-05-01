from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from database.db import init_db, get_db
from database.models import Property, Recommendation, ViewLog
from recommender.similarity import compute_recommendations
import os

app = FastAPI()

init_db()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>591 房源推薦</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #333; }}
  header {{ background: #e8451e; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }}
  header h1 {{ font-size: 1.2rem; font-weight: 600; }}
  .badge {{ background: rgba(255,255,255,0.25); border-radius: 12px; padding: 2px 10px; font-size: 0.8rem; }}
  .container {{ max-width: 900px; margin: 24px auto; padding: 0 16px; }}
  .meta {{ font-size: 0.85rem; color: #888; margin-bottom: 20px; }}
  .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 6px rgba(0,0,0,.08); margin-bottom: 16px; overflow: hidden; display: flex; }}
  .card-img {{ width: 140px; min-height: 120px; object-fit: cover; flex-shrink: 0; background: #eee; }}
  .card-img-placeholder {{ width: 140px; min-height: 120px; flex-shrink: 0; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 2rem; }}
  .card-body {{ padding: 16px; flex: 1; }}
  .card-rank {{ font-size: 0.75rem; color: #e8451e; font-weight: 700; margin-bottom: 4px; }}
  .card-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 8px; }}
  .card-title a {{ color: #333; text-decoration: none; }}
  .card-title a:hover {{ color: #e8451e; }}
  .card-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .tag {{ background: #f5f5f5; border-radius: 6px; padding: 2px 8px; font-size: 0.78rem; color: #555; }}
  .tag.price {{ background: #fff3f0; color: #e8451e; font-weight: 600; }}
  .card-reason {{ font-size: 0.82rem; color: #888; border-top: 1px solid #f0f0f0; padding-top: 8px; margin-top: 8px; }}
  .score-bar {{ display: inline-block; width: 48px; height: 6px; background: #eee; border-radius: 3px; vertical-align: middle; margin-right: 6px; position: relative; overflow: hidden; }}
  .score-fill {{ height: 100%; background: #e8451e; border-radius: 3px; }}
  .empty {{ text-align: center; padding: 60px 20px; color: #aaa; }}
  .actions {{ margin-bottom: 20px; }}
  .btn {{ display: inline-block; padding: 8px 18px; border-radius: 8px; font-size: 0.88rem; font-weight: 500; cursor: pointer; border: none; text-decoration: none; }}
  .btn-primary {{ background: #e8451e; color: white; }}
  .btn-primary:hover {{ background: #c93a19; }}
</style>
</head>
<body>
<header>
  <h1>🏠 591 房源推薦系統</h1>
  <span class="badge">今日推薦 {count} 筆</span>
</header>
<div class="container">
  <div class="meta">根據您的瀏覽偏好，為您推薦以下房源。</div>
  <div class="actions">
    <a href="/refresh" class="btn btn-primary">🔄 重新產生推薦</a>
  </div>
  {cards}
</div>
</body>
</html>"""

CARD_TEMPLATE = """
<div class="card">
  {img_html}
  <div class="card-body">
    <div class="card-rank">#{rank} 推薦</div>
    <div class="card-title"><a href="{url}" target="_blank">{title}</a></div>
    <div class="card-tags">
      <span class="tag price">💰 {price}</span>
      <span class="tag">📐 {area}</span>
      <span class="tag">📍 {location}</span>
      <span class="tag">🏢 {floor}樓</span>
      {type_tag}
    </div>
    <div class="card-reason">
      <span class="score-bar"><span class="score-fill" style="width:{score_pct}%"></span></span>
      符合度 {score_pct}%　✨ {reason}
    </div>
  </div>
</div>"""


def _render_card(item: dict, rank: int) -> str:
    prop = item["property"]
    score_pct = round(item["score"] * 100)
    price = f"{prop['price']:,.0f} 元/月" if prop.get("price") else "未提供"
    area = f"{prop['area']:.1f} 坪" if prop.get("area") else "未提供"
    location = prop.get("address") or prop.get("district") or prop.get("region", "")
    floor_str = prop.get("floor") or "?"
    prop_type = prop.get("property_type") or ""
    type_tag = f'<span class="tag">{prop_type}</span>' if prop_type else ""

    img_url = prop.get("image_url") or ""
    img_html = (
        f'<img class="card-img" src="{img_url}" alt="" loading="lazy">'
        if img_url
        else '<div class="card-img-placeholder">🏠</div>'
    )

    return CARD_TEMPLATE.format(
        rank=rank, url=prop.get("url", "#"), title=prop.get("title", "未知物件"),
        price=price, area=area, location=location, floor=floor_str,
        type_tag=type_tag, score_pct=score_pct, reason=item["reason"],
        img_html=img_html,
    )


def _get_or_compute_recommendations():
    with get_db() as db:
        recs = (
            db.query(Recommendation)
            .order_by(Recommendation.recommended_at.desc())
            .limit(20)
            .all()
        )
        if not recs:
            return compute_recommendations()

        results = []
        for r in recs:
            prop = db.query(Property).filter_by(property_id=r.property_id).first()
            if prop:
                results.append({
                    "property": {
                        "property_id": prop.property_id,
                        "title": prop.title,
                        "url": prop.url,
                        "price": prop.price,
                        "area": prop.area,
                        "district": prop.district,
                        "address": prop.address,
                        "rooms": prop.rooms,
                        "living_rooms": prop.living_rooms,
                        "bathrooms": prop.bathrooms,
                        "property_type": prop.property_type,
                        "floor": prop.floor,
                        "image_url": prop.image_url,
                        "region": prop.region,
                    },
                    "score": r.score,
                    "reason": r.reason,
                })
        return results


@app.get("/", response_class=HTMLResponse)
def index():
    results = _get_or_compute_recommendations()
    if results:
        cards = "".join(_render_card(item, i + 1) for i, item in enumerate(results))
    else:
        cards = '<div class="empty">📭 目前沒有推薦房源，請先執行爬蟲或記錄瀏覽紀錄。</div>'
    return HTML_TEMPLATE.format(count=len(results), cards=cards)


@app.get("/refresh", response_class=HTMLResponse)
def refresh():
    results = compute_recommendations()
    if results:
        cards = "".join(_render_card(item, i + 1) for i, item in enumerate(results))
    else:
        cards = '<div class="empty">📭 目前沒有推薦房源，請先執行爬蟲或記錄瀏覽紀錄。</div>'
    return HTMLResponse(
        HTML_TEMPLATE.format(count=len(results), cards=cards),
        headers={"Refresh": "0; url=/"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
