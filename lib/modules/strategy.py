import abc, traceback
from typing import Any, Dict, Optional, Callable, Generic, TypeVar
from dataclasses import dataclass

from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract, SqlAlchemySession

from ..modules.notification_logger import NotificationLogger


@dataclass
class ParamsBase:
    money: float
    data_frame: str
    symbol: str

class ContextApi(abc.ABC):

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return None
    
    @abc.abstractmethod
    def delete(self, key: str) -> None:
        return None
    
    @abc.abstractmethod
    def set(self, key: str, val: Any) -> None:
        return
    
    @abc.abstractmethod
    def append(self, key: str, val: Any) -> None:
        return 
    
    @abc.abstractmethod
    def increate(self, key: str, value: float | int) -> None:
        return

    @abc.abstractmethod
    def decreate(self, key: str, value: float | int) -> None:
        return
    
    @abc.abstractmethod
    def __enter__(self):
        return 

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, traceback_obj):
        return

@dataclass
class BasicDependency:
    def __init__(self, session: SessionAbstract = None, notification: Optional[NotificationLogger] = None):
        self.session = session or SqlAlchemySession()
        self.kv_store = KeyValueStore(session = self.session)
        self.notification_logger = notification

CT = TypeVar('ContextTypeDict', bound=dict)
class BasicContext(ContextApi, Generic[CT]):
    def __init__(self, id: str, deps: BasicDependency):
        self.id = id
        self.deps = deps
        self.is_dirt = False
        self._context: CT = None
        
    @abc.abstractmethod
    def _initial_context(self) -> CT:
        return {}

    def get(self, key: str) -> Any | None:
        return self._context.get(key)
    
    def set(self, key: str, value: Any) -> None:
        self.is_dirt = True
        self._context[key] = value

    def append(self, key: str, val: Any) -> None:
        assert self._context.get(key) is not None, f'{key} is not exist in context'
        assert isinstance(self._context[key], list), f'{key} is not a value of list'
        self.set(key, self._context[key] + [val])
    
    def increate(self, key: str, value: float | int) -> None:
        assert self._context.get(key) is not None, f'{key} is not exist in context'
        assert isinstance(self._context[key], (int, float)), f'{key} is not a value of number'
        self.set(key, self._context[key] + value)

    def decreate(self, key: str, value: float | int) -> None:
        return self.increate(key, -value)

    def delete(self, key) -> None:
        if self._context.get(key):
            self.is_dirt = True
            del self._context[key]

    def __enter__(self):
        if not self._context:
            with self.deps.session:
                self._context = self.deps.kv_store.get(self.id)
                if self._context is None: 
                    self._context = self._initial_context()
                    self.is_dirt = True
        return self
    
    def __exit__(self, exc_type, exc_value, traceback_obj):
        
        if self.is_dirt and exc_value is None:
            with self.deps.session:
                self.deps.kv_store.set(self.id, self._context)
                self.deps.session.commit()
                self.is_dirt = False
        
        if exc_type and exc_value and traceback_obj:
            if self.deps.notification_logger:
                self.deps.notification_logger.msg('Script error happened:\n', *traceback.format_tb(traceback_obj), '\n', exc_value)
        
        # 不在这里发通知，是为了多交易对交易的时候统一发
        # if self._deps.notification_logger:
        #     self._deps.notification_logger.send()

StrategyFunc = Callable[[ContextApi], None]
