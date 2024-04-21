from typing import Any

from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

from ..typedef import Scale, ExchangePair
from .engine import engine

Base = declarative_base()

class OHLCV:
    timestamp = Column(DateTime, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class BTC_USDT_1D(Base, OHLCV):
    __tablename__ = 'btc_usdt_1d'

class BTC_USDT_1M(Base, OHLCV):
    __tablename__ = 'btc_usdt_1m'

class EVENTS(Base):
    __tablename__ = 'events'
    key = Column(String(512), primary_key=True)
    context = Column(String(2048))

# 创建模型对应的表
Base.metadata.create_all(engine)

def get_table_class(pair: str, scale: str) -> OHLCV: 
    if pair == ExchangePair.BTC_USDT.value and scale == Scale.One_Day.value:
        return BTC_USDT_1D
    return None