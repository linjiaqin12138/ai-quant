from typing import Union, Dict, List
import abc
import json

from sqlalchemy import select, update, delete

from .session import SessionAbstract
from .sqlalchemy import events

Value = Union[str | Dict | List]

class KeyValueStoreAbstract(abc.ABC):
    @abc.abstractmethod
    def set(self, key: str, val: Value):
        raise NotImplementedError
    @abc.abstractmethod
    def get(self, key: str) -> Union[Value, None]:
        raise NotImplementedError
    @abc.abstractmethod
    def delete(self, key: str):
        raise NotImplementedError
    
class KeyValueStore(KeyValueStoreAbstract):
    def __init__(self, session: SessionAbstract):
        self.session = session

    def _val_to_str(self, v: Value):
        if type(v) == str:
            return v
        return json.dumps(v)
    
    def delete(self, key: str):
        compiled = delete(events).where(events.c.key == key).compile()
        self.session.execute(compiled.string, compiled.params)

    def get(self, key: str) -> Union[Value, None]:
        compiled = select(events).where(events.c.key == key).compile()
        res = self.session.execute(compiled.string, compiled.params)
        if len(res.rows) > 0:
            if res.rows[0].type == 'json':
                return json.loads(res.rows[0].context)
            else:
                return res.rows[0].context
        return None

    def set(self, key: str, val: Value):
        compiled = select(events).where(events.c.key == key).compile()
        res = self.session.execute(compiled.string, compiled.params)
        val_in_str = self._val_to_str(val)
        if len(res.rows) > 0:
            if res.rows[0].context == val_in_str:
                return
            compiled = update(events).where(events.c.key == key).values(
                context = val_in_str,
                type = 'string' if type(val) == str else 'json'
            ).compile()
            self.session.execute(compiled.string, compiled.params)
            return
        else:
            # compiled = insert(events).values(key = key, context = val_in_str, type = 'string' if type(val) == str else 'json').compile()
            self.session.execute(
                "INSERT INTO events (`key`, `context`, `type`) VALUES (:key, :context, :type)", 
                {
                    'key': key, 
                    'context': val_in_str, 
                    'type': 'string' if type(val) == str else 'json'
                }
            )
            return

