"""
房屋實價追蹤系統 - 資料庫 Models
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, BigInteger, Boolean, Text, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Trade(Base):
    """不動產買賣交易紀錄"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 地理位置
    city = Column(String(20), nullable=False, index=True)
    district = Column(String(30), nullable=False, index=True)
    address = Column(String(200), nullable=False)
    address_raw = Column(String(200))

    # 地理座標
    lon = Column(Float)
    lat = Column(Float)

    # 交易資訊
    trade_date = Column(Date, index=True)
    trade_date_roc = Column(String(7))
    season = Column(String(10))

    total_price = Column(BigInteger)
    unit_price = Column(Float)
    unit_price_tping = Column(Float)

    # 面積資訊 (平方公尺)
    land_area = Column(Float)
    building_area = Column(Float)
    main_building_area = Column(Float)
    attached_building_area = Column(Float)
    balcony_area = Column(Float)
    parking_area = Column(Float)
    parking_price = Column(BigInteger)

    # 建物屬性
    building_type = Column(String(50))
    floor = Column(String(100))
    total_floors = Column(String(100))
    rooms = Column(Integer)
    living_rooms = Column(Integer)
    bathrooms = Column(Integer)
    has_elevator = Column(Boolean)
    has_mgmt_org = Column(Boolean)

    # 用途與建材
    main_use = Column(String(30))
    main_material = Column(String(30))
    land_use_zone = Column(String(30))
    build_complete_date = Column(String(10))

    # 車位
    parking_type = Column(String(30))

    # 原始資料
    raw_id = Column(String(30), unique=True, index=True)
    trade_target = Column(String(30))
    notes = Column(Text)
    created_at = Column(Date, default=datetime.utcnow)

    # 生活圈評分 (pre-computed by batch job)
    score_overall = Column(Float)
    score_transit = Column(Float)
    score_education = Column(Float)
    score_medical = Column(Float)
    score_shopping = Column(Float)
    score_leisure = Column(Float)
    score_dining = Column(Float)
    score_updated_at = Column(DateTime)

    __table_args__ = (
        Index('idx_city_district', 'city', 'district'),
        Index('idx_trade_date', 'trade_date'),
        Index('idx_price_range', 'total_price', 'unit_price'),
    )


class Presale(Base):
    """預售屋交易紀錄"""
    __tablename__ = "presales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(20), nullable=False, index=True)
    district = Column(String(30), nullable=False, index=True)
    address = Column(String(200), nullable=False)
    lon = Column(Float)
    lat = Column(Float)

    trade_date = Column(Date, index=True)
    season = Column(String(10))

    developer = Column(String(100))
    project_name = Column(String(200))
    sales_office = Column(String(200))

    total_price = Column(BigInteger)
    unit_price = Column(Float)
    unit_price_tping = Column(Float)

    building_area = Column(Float)
    main_building_area = Column(Float)
    balcony_area = Column(Float)
    parking_area = Column(Float)

    floor = Column(String(20))
    rooms = Column(Integer)
    living_rooms = Column(Integer)
    bathrooms = Column(Integer)

    raw_id = Column(String(30), unique=True, index=True)
    created_at = Column(Date, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_presale_city_district', 'city', 'district'),
    )


class Rental(Base):
    """租賃交易紀錄"""
    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(20), nullable=False, index=True)
    district = Column(String(30), nullable=False, index=True)
    address = Column(String(200), nullable=False)
    lon = Column(Float)
    lat = Column(Float)

    trade_date = Column(Date, index=True)
    season = Column(String(10))

    monthly_rent = Column(BigInteger)
    deposit = Column(BigInteger)
    rent_per_tping = Column(Float)

    building_area = Column(Float)
    main_building_area = Column(Float)
    balcony_area = Column(Float)

    floor = Column(String(20))
    rooms = Column(Integer)
    living_rooms = Column(Integer)
    bathrooms = Column(Integer)
    building_type = Column(String(50))

    raw_id = Column(String(30), unique=True, index=True)
    created_at = Column(Date, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_rental_city_district', 'city', 'district'),
    )


class TradeAmenity(Base):
    """交易物件周邊生活機能（POI）"""
    __tablename__ = "trade_amenities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(Integer, nullable=False, index=True)
    category = Column(String(50), nullable=False)
    amenity_name = Column(String(255), nullable=False)
    distance = Column(Integer, nullable=False)  # meters
    lat = Column(Float)
    lon = Column(Float)

    __table_args__ = (
        Index('idx_trade_amenity_trade', 'trade_id'),
    )


class SyncLog(Base):
    """資料同步紀錄"""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset = Column(String(20), nullable=False)
    season = Column(String(10))
    synced_at = Column(DateTime, default=datetime.utcnow)
    rows_imported = Column(Integer, default=0)
    rows_updated = Column(Integer, default=0)
    status = Column(String(20), default="running")
    error = Column(Text)


class SyncState(Base):
    """各資料集同步狀態追蹤（用於差異更新）"""
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset = Column(String(20), unique=True, nullable=False)
    last_synced_at = Column(DateTime)
    last_synced_date = Column(Date)
    total_rows = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
