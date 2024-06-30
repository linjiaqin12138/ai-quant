from typing import Union, Dict, List
import abc

Value = Union[str | Dict | List]

class KeyValueStoreAbstract(abc.ABC):
    def set(self, key: str, val: Value):
        raise NotImplementedError
    def get(self, key: str) ->Union[Value, None]:
        raise NotImplementedError
    def delete(self, key: str):
        raise NotImplementedError
    