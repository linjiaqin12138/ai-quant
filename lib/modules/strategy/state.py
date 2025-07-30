import abc
from typing import Any, Dict, List, Optional

from lib.adapter.database import create_transaction
from lib.logger import logger


class StateApi(abc.ABC):

    def has(self, key_or_path: str | List[str]) -> bool:
        return self.get(key_or_path) is not None
    
    @abc.abstractmethod
    def get(self, key_or_path: str | List[str]) -> Any | None:
        return None

    @abc.abstractmethod
    def delete(self, key_or_path: str | List[str]) -> None:
        return None

    @abc.abstractmethod
    def set(self, key_or_path: str | List[str], val: Any) -> None:
        return

    @abc.abstractmethod
    def append(self, key_or_path: str | List[str], val: Any) -> None:
        return

    @abc.abstractmethod
    def increase(self, key_or_path: str | List[str], value: float | int) -> None:
        return

    @abc.abstractmethod
    def decrease(self, key_or_path: str | List[str], value: float | int) -> None:
        return

    @abc.abstractmethod
    def save(self) -> None:
        return


def _get_nested(context: dict, key_or_path: str | List[str]):
    if isinstance(key_or_path, str):
        return context.get(key_or_path)
    curr = context
    for k in key_or_path:
        if not isinstance(curr, dict) or k not in curr:
            return None
        curr = curr[k]
    return curr


def _set_nested(context: dict, key_or_path: str | List[str], value: Any):
    logger.info(f"SET {key_or_path} {_get_nested(context, key_or_path)} => {value}")
    if isinstance(key_or_path, str):
        context[key_or_path] = value
        return
    curr = context
    for i, k in enumerate(key_or_path):
        if i == len(key_or_path) - 1:
            curr[k] = value
        else:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]


def _del_nested(context: dict, key_or_path: str | List[str]):
    logger.info(f"DEL {key_or_path}")
    if isinstance(key_or_path, str):
        if context.get(key_or_path) is None:
            logger.warning(f"Key {key_or_path} does not exist in context")
            return
        del context[key_or_path]
        return
    curr = context
    for k in key_or_path[:-1]:
        curr = curr[k]
    del curr[key_or_path[-1]]


class SimpleState(StateApi):
    def __init__(self, default: dict):
        self.temp_context = default
        self._context = default

    def get(self, key_or_path: str | List[str]) -> Any | None:
        return _get_nested(self.temp_context, key_or_path)

    def delete(self, key_or_path: str | List[str]) -> None:
        _del_nested(self.temp_context, key_or_path)

    def set(self, key_or_path: str | List[str], val: Any) -> None:
        _set_nested(self.temp_context, key_or_path, val)

    def append(self, key_or_path: str | List[str], val: Any) -> None:
        arr = self.get(key_or_path)
        assert isinstance(arr, list), f"{key_or_path} is not a list"
        arr.append(val)
        self.set(key_or_path, arr)

    def increase(self, key_or_path: str | List[str], value: float | int) -> None:
        v = self.get(key_or_path)
        assert isinstance(v, (int, float)), f"{key_or_path} is not a number"
        self.set(key_or_path, v + value)

    def decrease(self, key_or_path: str | List[str], value: float | int) -> None:
        v = self.get(key_or_path)
        assert isinstance(v, (int, float)), f"{key_or_path} is not a number"
        self.set(key_or_path, v - value)

    def save(self) -> None:
        self._context = self.temp_context


class PersisitentState(StateApi):
    def __init__(self, id, default: dict):
        self.id = id
        self.is_dirt = False
        with create_transaction() as db:
            context = db.kv_store.get(self.id)
            if context is None:
                context = default
                self.is_dirt = True
        self._simple_state = SimpleState(context)

    
    def get(self, key_or_path: str | List[str]) -> Any | None:
        return self._simple_state.get(key_or_path)

    def set(self, key_or_path: str | List[str], value: Any) -> None:
        self.is_dirt = True
        self._simple_state.set(key_or_path, value)

    def append(self, key_or_path: str | List[str], val: Any) -> None:
        self.is_dirt = True
        self._simple_state.append(key_or_path, val)

    def increase(self, key_or_path: str | List[str], value: float | int) -> None:
        self.is_dirt = True
        self._simple_state.increase(key_or_path, value)

    def decrease(self, key_or_path: str | List[str], value: float | int) -> None:
        self.is_dirt = True
        self._simple_state.decrease(key_or_path, value)

    def delete(self, key_or_path: str | List[str]) -> None:
        self.is_dirt = True
        self._simple_state.delete(key_or_path)

    def save(self):
        if self.is_dirt:
            with create_transaction() as db:
                db.kv_store.set(self.id, self._simple_state.temp_context)
                db.commit()
                self.is_dirt = False
