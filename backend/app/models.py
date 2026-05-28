from sqlalchemy import Column, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Ping(Base):
    __tablename__ = "pings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )


class PriceDay(Base):
    # REQ-005 — one row per (zone, date); payload_json is the rendered hours list
    # (spot/vat/tariff/total already computed) so cache hits never re-run the math.
    __tablename__ = "price_days"
    __table_args__ = (UniqueConstraint("zone", "date", name="uq_price_days_zone_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone = Column(String(8), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    fetched_at = Column(DateTime, nullable=False)
    payload_json = Column(Text, nullable=False)
