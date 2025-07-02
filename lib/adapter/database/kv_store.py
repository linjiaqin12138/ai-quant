from typing import Union, Dict, List
import json

from sqlalchemy import select, update, delete
from lib.logger import logger
from .session import SessionAbstract, SqlAlchemySession
from .sqlalchemy import events

Value = Union[str | Dict | List]


class KeyValueStore:
    def __init__(self, session: SessionAbstract):
        self.session = session

    def is_sqlite(self) -> bool:
        return (
            isinstance(self.session, SqlAlchemySession)
            and self.session.engine.url.drivername.find("sqlite") >= 0
        )

    def _val_to_str(self, v: Value):
        if type(v) == str:
            return v
        return json.dumps(v)

    def setnx(self, key: str, val: Value) -> bool:
        if self.is_sqlite():
            compiled = select(events).where(events.c.key == key).compile()
        else:
            compiled = (
                select(events).where(events.c.key == key).with_for_update().compile()
            )
        res = self.session.execute(compiled.string, compiled.params)
        if len(res.rows) > 0:
            return False
        return (
            self.session.execute(
                "INSERT INTO events (`key`, `context`, `type`) VALUES (:key, :context, :type)",
                {
                    "key": key,
                    "context": self._val_to_str(val),
                    "type": "string" if type(val) == str else "json",
                },
            ).row_count
            > 0
        )

    def delete(self, key: str):
        compiled = delete(events).where(events.c.key == key).compile()
        self.session.execute(compiled.string, compiled.params)

    def get(self, key: str) -> Union[Value, None]:
        compiled = select(events).where(events.c.key == key).compile()
        res = self.session.execute(compiled.string, compiled.params)
        if len(res.rows) > 0:
            if res.rows[0].type == "json":
                return json.loads(res.rows[0].context)
            else:
                return res.rows[0].context
        return None

    def set(self, key: str, val: Value):
        if not self.setnx(key, val):
            compiled = (
                update(events)
                .where(events.c.key == key)
                .values(
                    context=self._val_to_str(val),
                    type="string" if type(val) == str else "json",
                )
                .compile()
            )
            if self.session.execute(compiled.string, compiled.params).row_count > 0:
                return
            else:
                logger.error(f"Failed to set update {key} with value {val}")


__all__ = ["KeyValueStore"]
