import numpy as np
import json
from database.models import Property


# 地區權重對照（可依需求調整）
REGION_MAP = {
    "台北市": 1, "新北市": 2, "基隆市": 3, "桃園市": 4,
    "新竹市": 5, "新竹縣": 6, "台中市": 7, "台南市": 8,
    "高雄市": 9, "其他": 10,
}

PROPERTY_TYPE_MAP = {
    "整層住家": 1, "獨立套房": 2, "分租套房": 3,
    "雅房": 4, "車位": 5, "店面": 6, "其他": 7,
}


def property_to_vector(prop: Property) -> np.ndarray:
    """
    將物件轉成特徵向量
    特徵：[price_norm, area_norm, rooms, living_rooms, bathrooms,
           floor_norm, region_enc, type_enc]
    """
    price = prop.price or 0
    area = prop.area or 0
    rooms = prop.rooms or 0
    living = prop.living_rooms or 0
    baths = prop.bathrooms or 0
    region_enc = REGION_MAP.get(prop.region, 10) / 10.0
    type_enc = PROPERTY_TYPE_MAP.get(prop.property_type, 7) / 7.0

    # 樓層：取數字部分
    floor_num = 0
    if prop.floor:
        import re
        m = re.search(r"(\d+)", prop.floor)
        if m:
            floor_num = int(m.group(1))

    # 正規化（粗略範圍）
    price_norm = min(price / 100000, 1.0)   # 最高 10 萬
    area_norm = min(area / 100, 1.0)         # 最高 100 坪
    floor_norm = min(floor_num / 30, 1.0)    # 最高 30 樓

    return np.array([
        price_norm,
        area_norm,
        rooms / 5.0,
        living / 3.0,
        baths / 3.0,
        floor_norm,
        region_enc,
        type_enc,
    ], dtype=np.float32)


def build_user_profile(view_history: list[Property]) -> np.ndarray:
    """
    根據瀏覽紀錄計算用戶偏好向量（加權平均，越近期越高權重）
    """
    if not view_history:
        return None

    vectors = [property_to_vector(p) for p in view_history]
    n = len(vectors)
    # 線性遞增權重：最新的權重最高
    weights = np.linspace(1, 3, n)
    weights /= weights.sum()

    profile = np.average(vectors, axis=0, weights=weights)
    return profile.astype(np.float32)
