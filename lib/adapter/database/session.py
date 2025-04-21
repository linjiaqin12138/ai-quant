import abc
from dataclasses import dataclass
from typing import List, Any
from sqlalchemy import text, Engine
from ...logger import logger
from .sqlalchemy import engine as default_engine

@dataclass(frozen=True)
class ExecuteResult:
    rows: List[Any]
    row_count: int

class SessionAbstract(abc.ABC):
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.rollback()

    @abc.abstractmethod
    def begin(self):
        return

    @abc.abstractmethod
    def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, sql: str, params: dict) -> ExecuteResult:
        raise NotADirectoryError

class SqlAlchemySession(SessionAbstract):

    def __init__(self, engine: Engine = default_engine):
        self.engine = engine
        self.conn = None
    
    def __enter__(self):
        self.begin()
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.conn.close()

    def begin(self):
        self.conn = self.engine.connect()
        if self.engine.url.drivername.find('sqlite') >= 0:
            self.execute("BEGIN IMMEDIATE TRANSACTION")

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def execute(self, sql: str, params: dict = None) -> ExecuteResult:
        # if self.conn is None:
        #     self.conn = self.engine.connect()
        result = self.conn.execute(
            text(sql),
            params
        )
        logger.debug(f'SQL: {sql}')
        logger.debug(f'params: {params}')
        return ExecuteResult(
            rows = result.all() if result.returns_rows else [], 
            row_count= result.rowcount
        )

def create_session() -> SessionAbstract:
    return SqlAlchemySession(default_engine)

__all__ = [
    'SessionAbstract',
    'create_session'
]