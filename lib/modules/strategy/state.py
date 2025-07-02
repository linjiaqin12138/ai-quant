import abc
from typing import Any, Dict, Optional

from lib.adapter.database import create_transaction


class StateApi(abc.ABC):
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
    def increase(self, key: str, value: float | int) -> None:
        return

    @abc.abstractmethod
    def decrease(self, key: str, value: float | int) -> None:
        return

    @abc.abstractmethod
    def save(self) -> None:
        return


class SimpleState(StateApi):

    def __init__(self, default: dict):
        self.temp_context = default
        self._context = default

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.temp_context.get(key)

    def delete(self, key: str) -> None:
        del self.temp_context[key]

    def set(self, key: str, val: Any) -> None:
        self.temp_context[key] = val

    def append(self, key: str, val: Any) -> None:
        self.temp_context[key].append(val)

    def increase(self, key: str, value: float | int) -> None:
        self.temp_context[key] = self.temp_context[key] + value

    def decrease(self, key: str, value: float | int) -> None:
        self.temp_context[key] = self.temp_context[key] - value

    def save(self) -> None:
        self._context = self.temp_context


class PersisitentState(StateApi):
    def __init__(self, id, default: dict):
        self.id = id
        self.is_dirt = False
        with create_transaction() as db:
            self._context = db.kv_store.get(self.id)
            if self._context is None:
                self._context = default
                self.is_dirt = True

    def get(self, key: str) -> Any | None:
        return self._context.get(key)

    def set(self, key: str, value: Any) -> None:
        self.is_dirt = True
        self._context[key] = value

    def append(self, key: str, val: Any) -> None:
        assert self._context.get(key) is not None, f"{key} is not exist in context"
        assert isinstance(self._context[key], list), f"{key} is not a value of list"
        self.set(key, self._context[key] + [val])

    def increase(self, key: str, value: float | int) -> None:
        assert self._context.get(key) is not None, f"{key} is not exist in context"
        assert isinstance(
            self._context[key], (int, float)
        ), f"{key} is not a value of number"
        self.set(key, self._context[key] + value)

    def decrease(self, key: str, value: float | int) -> None:
        return self.increase(key, -value)

    def delete(self, key) -> None:
        if self._context.get(key):
            self.is_dirt = True
            del self._context[key]

    def save(self):
        if self.is_dirt:
            with create_transaction() as db:
                db.kv_store.set(self.id, self._context)
                db.commit()
                self.is_dirt = False
