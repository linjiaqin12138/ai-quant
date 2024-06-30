import abc
from dataclasses import dataclass
from typing import List, Any
from sqlalchemy import text, Engine
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

    @abc.abstractclassmethod
    def commit(self):
        raise NotImplementedError
    @abc.abstractclassmethod
    def rollback(self):
        raise NotImplementedError
    @abc.abstractclassmethod
    def execute(self, sql: str, params: dict) -> ExecuteResult:
        raise NotADirectoryError

class SqlAlchemySession(SessionAbstract):

    def __init__(self, engine: Engine = default_engine):
        self.engine = engine
    
    def __enter__(self):
        self.conn = self.engine.connect()
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def execute(self, sql: str, params: dict = None) -> ExecuteResult:
        result = self.conn.execute(
            text(sql),
            params
        )
        
        return ExecuteResult(
            rows = result.all() if result.returns_rows else [], 
            row_count=result.rowcount
        )

