import abc
from typing import Any, Optional, Callable, List
from dataclasses import dataclass

from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract, SqlAlchemySession

from ..logger import logger
from ..model import CryptoHistoryFrame, Ohlcv
from ..adapter.crypto_exchange.base import CryptoExchangeAbstract
from ..modules.crypto import CryptoOperationModule, ModuleDependency
from ..modules.notification_logger import NotificationLogger

# Param = TypeVar('Param')s
@dataclass
class ParamsBase:
    money: float
    data_frame: CryptoHistoryFrame
    symbol: str

@dataclass
class ResultBase:
    total_assets: float

@dataclass
class Dependency:

    def __init__(self, session: SessionAbstract = None, exchange: CryptoExchangeAbstract = None, notification: Optional[NotificationLogger] = None):
        self.session = session or SqlAlchemySession()
        self.crypto = CryptoOperationModule(ModuleDependency(self.session, exchange))
        self.notification_logger = notification


class ContextBase(abc.ABC):
    def __init__(self, params: ParamsBase, deps: Dependency = Dependency()):
        self.id = self.init_id(params)
        self.kv_store = KeyValueStore(session = deps.session)
        self.is_dirt = False

        self._deps = deps
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
            with self._deps.session:
                self._context = self.kv_store.get(self.id) or self.init_context(self._params)
                self.is_dirt = True
        return self
    
    def __exit__(self, *args):
        
        if self.is_dirt:
            with self._deps.session:
                self.kv_store.set(self.id, self._context)
                self.is_dirt = False
                self._deps.session.commit()
        
        if len(args) and args[0] and args[1] and args[2]:
            logger.error(args[2])
            if self._deps.notification_logger:
                self._deps.notification_logger.msg(args[2])
            else:
                logger.error(args[2])

# StrategyResult = 
StrategyFunc = Callable[[ContextBase, Optional[List[Ohlcv]]], ResultBase]

# def run_once(strategy: StrategyFunc, contextClass: Type[ContextBase], params: ParamsBase, default_contxt: dict, deps: Dependency = Dependency()): 
#     with contextClass(params, deps.session, default_contxt) as context:
#         strategy(context)