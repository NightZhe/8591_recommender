from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Property(Base):
    """物件資料表"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(50), unique=True, nullable=False)  # 8591 的物件ID
    title = Column(String(200))
    url = Column(String(500))
    kind = Column(String(10))           # 出租/出售
    property_type = Column(String(50))  # 整層住家/套房/分租等
    region = Column(String(50))         # 縣市
    district = Column(String(50))       # 區
    address = Column(String(200))
    price = Column(Float)               # 租金或售價
    area = Column(Float)                # 坪數
    floor = Column(String(20))          # 樓層
    total_floor = Column(String(10))    # 總樓層
    rooms = Column(Integer)             # 房數
    living_rooms = Column(Integer)      # 廳數
    bathrooms = Column(Integer)         # 衛數
    features = Column(Text)             # 特色標籤 JSON
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    view_logs = relationship("ViewLog", back_populates="property")


class ViewLog(Base):
    """用戶瀏覽紀錄"""
    __tablename__ = "view_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(50), ForeignKey("properties.property_id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(20), default="manual")  # manual / recommended

    property = relationship("Property", back_populates="view_logs")


class UserPreference(Base):
    """用戶偏好設定"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Recommendation(Base):
    """每日推薦紀錄"""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(50), ForeignKey("properties.property_id"), nullable=False)
    score = Column(Float)
    reason = Column(Text)
    recommended_at = Column(DateTime, default=datetime.utcnow)
    is_sent = Column(Boolean, default=False)
    is_viewed = Column(Boolean, default=False)


class ScrapeRun(Base):
    """每次爬取的 session 紀錄"""
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime, default=datetime.utcnow)
    total_found = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    search_areas = Column(String(200), default="")   # e.g. "板橋,五股"
    status = Column(String(20), default="success")   # success / failed
    error_msg = Column(Text, nullable=True)


class BuyProperty(Base):
    """買屋物件（店面）"""
    __tablename__ = "buy_properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(50), unique=True, nullable=False)
    title = Column(String(200))
    url = Column(String(500))
    district = Column(String(50))    # 板橋 / 五股
    address = Column(String(200))
    price = Column(Float)            # 萬元
    unit_price = Column(Float)       # 萬/坪
    area = Column(Float)             # 坪數
    floor = Column(String(20))       # 樓層資訊
    house_type = Column(String(50))  # 店面 / 辦公 等
    image_url = Column(String(500))
    is_new = Column(Boolean, default=True)   # 是否為新出現物件
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=True)
