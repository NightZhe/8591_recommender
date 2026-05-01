import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from database.db import get_db
from database.models import Property, ViewLog, Recommendation
from .feature_extractor import property_to_vector, build_user_profile
from config.settings import TOP_N_RECOMMENDATIONS, SIMILARITY_THRESHOLD
from datetime import datetime, timedelta


def _prop_to_dict(prop: Property) -> dict:
    return {
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
    }


def get_viewed_ids(db) -> set:
    logs = db.query(ViewLog.property_id).distinct().all()
    return {row.property_id for row in logs}


def get_recent_viewed_properties(db, days: int = 30) -> list:
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(ViewLog)
        .filter(ViewLog.viewed_at >= since)
        .order_by(ViewLog.viewed_at.asc())
        .all()
    )
    seen = set()
    properties = []
    for log in logs:
        if log.property_id not in seen and log.property:
            seen.add(log.property_id)
            properties.append(log.property)
    return properties


def compute_recommendations() -> list:
    """
    核心推薦邏輯：
    1. 取得用戶瀏覽歷史 → 建立偏好向量
    2. 對所有在架物件計算 cosine similarity
    3. 過濾已看過的，取 Top-N
    回傳 list of {"property": dict, "score": float, "reason": str}
    """
    with get_db() as db:
        viewed_history = get_recent_viewed_properties(db)

        if not viewed_history:
            print("[recommender] 沒有瀏覽紀錄，改用最新物件推薦")
            props = (
                db.query(Property)
                .filter_by(is_active=True)
                .order_by(Property.scraped_at.desc())
                .limit(TOP_N_RECOMMENDATIONS)
                .all()
            )
            return [
                {"property": _prop_to_dict(p), "score": 1.0, "reason": "最新上架"}
                for p in props
            ]

        user_profile = build_user_profile(viewed_history)
        viewed_ids = get_viewed_ids(db)

        candidates = (
            db.query(Property)
            .filter(
                Property.is_active == True,
                Property.property_id.notin_(viewed_ids),
            )
            .all()
        )

        if not candidates:
            print("[recommender] 沒有新物件可推薦")
            return []

        candidate_vectors = np.array([property_to_vector(p) for p in candidates])
        user_vec = user_profile.reshape(1, -1)
        scores = cosine_similarity(user_vec, candidate_vectors)[0]

        scored = [
            (candidates[i], float(scores[i]))
            for i in range(len(candidates))
            if scores[i] >= SIMILARITY_THRESHOLD
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:TOP_N_RECOMMENDATIONS]

        results = []
        for prop, score in top:
            reason = _build_reason(prop, viewed_history, score)
            results.append({
                "property": _prop_to_dict(prop),
                "score": score,
                "reason": reason,
            })

        for item in results:
            rec = Recommendation(
                property_id=item["property"]["property_id"],
                score=item["score"],
                reason=item["reason"],
            )
            db.add(rec)

        print(f"[recommender] 產生 {len(results)} 筆推薦")
        return results


def _build_reason(prop: Property, history: list, score: float) -> str:
    reasons = []

    prices = [p.price for p in history if p.price]
    areas = [p.area for p in history if p.area]

    if prices and prop.price:
        avg_price = np.mean(prices)
        if abs(prop.price - avg_price) / (avg_price + 1) < 0.2:
            reasons.append("價格符合您的偏好")

    if areas and prop.area:
        avg_area = np.mean(areas)
        if abs(prop.area - avg_area) / (avg_area + 1) < 0.2:
            reasons.append("坪數符合您的偏好")

    common_regions = [p.district for p in history if p.district]
    if common_regions and prop.district == max(set(common_regions), key=common_regions.count):
        reasons.append(f"位於您常看的{prop.district}")

    common_types = [p.property_type for p in history if p.property_type]
    if common_types and prop.property_type and prop.property_type == max(set(common_types), key=common_types.count):
        reasons.append(f"類型符合您偏好的{prop.property_type}")

    if not reasons:
        reasons.append(f"綜合相似度 {score:.0%}")

    return "、".join(reasons)
