from .session import create_session
from .cryto_trade import TradeHistory
from .kv_store import KeyValueStore
from .news_cache import HotNewsCache
from .ohlcv_cache import OhlcvCacheFetcher

class DbTransaction:

    def __init__(self):
        self.session = create_session()
        self.kv_store = KeyValueStore(self.session)
        self.trade_log = TradeHistory(self.session)
        self.news_cache = HotNewsCache(self.session)
        self.ohlcv_cache = OhlcvCacheFetcher(self.session)

    def __enter__(self):
        return self.session.__enter__()

    def rollback(self):
        return self.session.rollback()

    def commit(self):
        return self.session.commit()

    def __exit__(self, *args):
        return self.session.__exit__(*args)
    
def create_transaction() -> DbTransaction:
    return DbTransaction()

__all__ = [
    'DbTransaction',
    'create_transaction'
]