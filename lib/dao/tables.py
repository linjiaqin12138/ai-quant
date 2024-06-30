from typing import Any

from sqlalchemy import Column, String, Float, DateTime, DECIMAL, Enum
from sqlalchemy.orm import declarative_base

from .engine import engine

Base = declarative_base()

# Query expected range data
class OhlcvCacheBase():
    timestamp = Column(DateTime, primary_key=True)
    pair = Column(String(20), primary_key=True)
    open = Column(String(25))
    high = Column(String(25))
    low = Column(String(25))
    close = Column(String(25))
    volume = Column(String(25))
# Check if any data is missed, if yes, query it from backend
class OhlcvCache1H(OhlcvCacheBase, Base):
    __tablename__ = 'ohlcv_cache_1h'

class OhlcvCache1D(OhlcvCacheBase, Base):
    __tablename__ = 'ohlcv_cache_1d'

class OhlcvCache15M(OhlcvCacheBase, Base):
    __tablename__ = 'ohlcv_cache_15m'


# TODO: 改掉其他类的名字风格，统一改成驼峰
# https://www.python.org/dev/peps/pep-0008/#class-names


class Exchange_Info(Base):
    __tablename__ = "exchange_info"
    pair = Column(String(20), primary_key=True)
    quote_volume = Column(DECIMAL(20, 6))


class Trade_Action_Info(Base):
    __tablename__ = "trade_action_info"
    pair = Column(String(20), primary_key=True)
    timestamp = Column(DateTime, primary_key=True)
    action = Column(Enum("buy", "sell"), primary_key=True)
    reason = Column(String(1024))
    amount = Column(DECIMAL(15, 10), nullable=False)
    price = Column(DECIMAL(15, 10), nullable=False)
    type = Column(Enum("limit", "market"), nullable=False)
    context = Column(String(4096))
    order_id = Column(String(100))


class Events_Cache(Base):
    __tablename__ = "events"
    key = Column(String(512), primary_key=True)
    context = Column(String(4096))
    type = Column(Enum("string", "json"), default="string")


# 创建模型对应的表
Base.metadata.create_all(engine)

# def get_table_class(pair: str, scale: str) -> OHLCV:
#     if pair == ExchangePair.BTC_USDT.value and scale == Scale.One_Day.value:
#         return BTC_USDT_1D
#     return None
