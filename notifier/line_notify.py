import httpx
from config.settings import LINE_NOTIFY_TOKEN
from database.models import Property

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


def format_property_message(prop: Property, score: float, reason: str, rank: int) -> str:
    price_str = f"{prop.price:,.0f}" if prop.price else "未提供"
    area_str = f"{prop.area:.1f} 坪" if prop.area else "未提供"
    floor_str = prop.floor or "未知"

    room_str = ""
    if prop.rooms is not None:
        room_str = f"{prop.rooms}房{prop.living_rooms or 0}廳{prop.bathrooms or 0}衛"

    return f"""
#{rank} 推薦房源（符合度 {score:.0%}）
📍 {prop.address or prop.district or prop.region}
🏠 {prop.property_type or '住宅'} {room_str}
💰 {price_str} 元/月
📐 {area_str}  🏢 {floor_str}樓
✨ {reason}
🔗 {prop.url}
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
        send_line_notify(msg, image_url=item["property"].image_url or None)
