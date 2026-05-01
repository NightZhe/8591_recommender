import httpx
from config.settings import LINE_NOTIFY_TOKEN

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


def send_line_notify(message: str, image_url: str = None):
    """發送 Line Notify 訊息"""
    if not LINE_NOTIFY_TOKEN:
        print("[notifier] LINE_NOTIFY_TOKEN 未設定，跳過通知")
        return False

    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}

    if image_url:
        data["imageThumbnail"] = image_url
        data["imageFullsize"] = image_url

    resp = httpx.post(LINE_NOTIFY_URL, headers=headers, data=data, timeout=10)
    return resp.status_code == 200


def format_property_message(prop: dict, score: float, reason: str, rank: int) -> str:
    price = prop.get("price")
    area = prop.get("area")
    price_str = f"{price:,.0f}" if price else "未提供"
    area_str = f"{area:.1f} 坪" if area else "未提供"
    floor_str = prop.get("floor") or "未知"

    room_str = ""
    rooms = prop.get("rooms")
    if rooms is not None:
        room_str = f"{rooms}房{prop.get('living_rooms') or 0}廳{prop.get('bathrooms') or 0}衛"

    location = prop.get("address") or prop.get("district") or prop.get("region", "")

    return f"""
#{rank} 推薦房源（符合度 {score:.0%}）
📍 {location}
🏠 {prop.get('property_type') or '住宅'} {room_str}
💰 {price_str} 元/月
📐 {area_str}  🏢 {floor_str}樓
✨ {reason}
🔗 {prop.get('url', '')}
"""


def send_daily_recommendations(recommendations: list[dict]):
    """發送每日推薦通知"""
    if not recommendations:
        send_line_notify("\n📭 今日沒有符合條件的新推薦房源")
        return

    header = f"\n🏡 每日推薦房源 — 今天找到 {len(recommendations)} 筆適合您的物件！"
    send_line_notify(header)

    for i, item in enumerate(recommendations, 1):
        msg = format_property_message(
            item["property"], item["score"], item["reason"], i
        )
        send_line_notify(msg, image_url=item["property"]["image_url"] or None)
