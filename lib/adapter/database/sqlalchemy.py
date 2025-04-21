from typing import Dict
from sqlalchemy import MetaData, create_engine
from sqlalchemy import Table, Text, Column, Enum, String, DateTime, DECIMAL, BigInteger

from lib.model import CryptoHistoryFrame
from lib.config import get_database_uri, get_create_table

engine = create_engine(get_database_uri())

metadata_obj = MetaData()

def get_cache_table(market_type: str, frame: str) -> Table:
    return Table(
        market_type + "_ohlcv_cache_" + frame,
        metadata_obj,
        Column("symbol", String(20), primary_key=True),
        Column("timestamp", BigInteger, primary_key=True),
        Column("open", String(25)),
        Column("high", String(25)),
        Column("low", String(25)),
        Column("close", String(25)),
        Column("volume", String(25))
    )

crypto_ohlcv_cache_tables: Dict[CryptoHistoryFrame, Table] = {
    '1d': get_cache_table('crypto', '1d'),
    '1h': get_cache_table('crypto', '1h'),
    '15m': get_cache_table('crypto', '15m')
}

ashare_ohlcv_cache_tables: Dict[str, Table] = {
    '1d': get_cache_table('ashare', '1d')
}

trade_action_info = Table(
    'trade_action_info',
    metadata_obj,
    Column("symbol", String(20), primary_key=True),
    Column("timestamp", DateTime, primary_key=True),
    Column('action', Enum("buy", "sell"), primary_key=True),
    Column('reason', String(1024), index=True),
    Column('amount', DECIMAL(15, 10), nullable=False),
    Column('price', DECIMAL(15, 10), nullable=False),
    Column('type', Enum("limit", "market"), nullable=False),
    Column('context', String(4096)),
    Column('order_id', String(100)),
    Column('comment', Text)
)

events = Table(
    'events',
    metadata_obj,
    Column("key", String(512), primary_key=True),
    Column("context", Text),
    Column('type', Enum("string", "json"), default="string")
)

hot_news_cache = Table(
    'hot_news_cache',
    metadata_obj,
    Column("news_id", String(512), primary_key=True),
    Column("platform", String(128)),
    Column("title", Text),
    Column('description',Text),
    Column('url', Text),
    Column('timestamp', BigInteger),
    Column('reason', Text),
    Column('mood', DECIMAL(3,2))
)


if get_create_table():
    metadata_obj.create_all(engine)
