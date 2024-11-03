import abc, traceback
from typing import Any, Optional, Callable, List, Generic, TypeVar
from dataclasses import dataclass

from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract, SqlAlchemySession

from ..model import CryptoHistoryFrame, Ohlcv
from ..modules.crypto import CryptoOperationAbstract, crypto as default_crypto
from ..modules.notification_logger import NotificationLogger


@dataclass
class ParamsBase:
    money: float
    data_frame: CryptoHistoryFrame
    symbol: str

@dataclass
class ResultBase:
    total_assets: float

class DependencyAbstract(abc.ABC):
    notification_logger: Optional[NotificationLogger] # 出错时通知
    kv_store: KeyValueStore # 存储上下文信息

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, traceback_obj):
        pass

    @abc.abstractmethod
    def __init__(self):
        pass

@dataclass
class CryptoDependency(DependencyAbstract):
    # 这里我纠结了好久究竟crypto注入还是注入session然后里面build一个crypto
    # 最后决定注入crypto，因为这样就不用关心session的开启关闭，同时crypto模块相对独立，方便测试
    # crypto模块内部自己会开启关闭session，而且不能依赖外部是否失败成功都要在做了交易所操作之后根据交易所操作来commit
    def __init__(self, session: SessionAbstract = None, crypto: CryptoOperationAbstract = None, notification: Optional[NotificationLogger] = None):
        self.session = session or SqlAlchemySession()
        self.kv_store = KeyValueStore(session = self.session)
        self.crypto = crypto or default_crypto
        self.notification_logger = notification

    def __enter__(self):
        self.session.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback_obj):
        if exc_type and exc_value and traceback_obj:
            self.session.rollback()
        else:
            self.session.commit()

T = TypeVar('T', bound=DependencyAbstract)
class ContextBase(abc.ABC, Generic[T]):
    def __init__(self, params: ParamsBase, deps: DependencyAbstract = CryptoDependency()):
        self.id = self.init_id(params)
        self.is_dirt = False

        self._deps: T = deps
        self._params = params
        self._context = None
    
    @abc.abstractmethod
    def init_context(self, params: ParamsBase) -> dict:
        raise NotImplementedError

    def init_id(self, params: ParamsBase) -> str:
        return f'{params.symbol}_{params.data_frame}_{params.money}'
    
    def get(self, key: str) -> Any | None:
        return self._context.get(key)
    
    def set(self, key: str, value: Any) -> None:
        self.is_dirt = True
        self._context[key] = value

    def delete(self, key) -> None:
        if self._context.get(key):
            self.is_dirt = True
            del self._context[key]

    def __enter__(self):
        if not self._context:
            with self._deps:
                self._context = self._deps.kv_store.get(self.id)
                if self._context is None: 
                    self._context = self.init_context(self._params)
                    self.is_dirt = True
        return self
    
    def __exit__(self, exc_type, exc_value, traceback_obj):
        
        if self.is_dirt and exc_value is None:
            with self._deps:
                self._deps.kv_store.set(self.id, self._context)
                self.is_dirt = False
        
        if exc_type and exc_value and traceback_obj:
            if self._deps.notification_logger:
                self._deps.notification_logger.msg('Script error happened:\n', *traceback.format_tb(traceback_obj), '\n', exc_value)
        
        # 不在这里发通知，是为了多交易对交易的时候统一发
        # if self._deps.notification_logger:
        #     self._deps.notification_logger.send()

StrategyFunc = Callable[[ContextBase, Optional[List[Ohlcv]]], ResultBase]
