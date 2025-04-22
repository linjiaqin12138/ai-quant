from .session import create_session, SessionAbstract
from .cryto_trade import TradeHistory
from .kv_store import KeyValueStore
from .news_cache import HotNewsCache
from .ohlcv_cache import OhlcvCacheFetcher

class DbTransaction:

    def __init__(self, session: SessionAbstract):
        self.session = session
        self.kv_store = KeyValueStore(self.session)
        self.trade_log = TradeHistory(self.session)
        self.news_cache = HotNewsCache(self.session)
        self.ohlcv_cache = OhlcvCacheFetcher(self.session)

    def __enter__(self):
        self.session.__enter__()
        return self

    def rollback(self):
        return self.session.rollback()

    def commit(self):
        return self.session.commit()

    def __exit__(self, *args):
        return self.session.__exit__(*args)
    
def create_transaction(session: SessionAbstract = create_session()) -> DbTransaction:
    return DbTransaction(session)

__all__ = [
    'create_transaction'
]