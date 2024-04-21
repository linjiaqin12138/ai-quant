from typing import Any

from sqlalchemy.orm import sessionmaker

from ..utils.logger import logger
from .engine import engine

Session = sessionmaker(bind=engine)

session_pool = []

def is_free_session(sess: Any) -> bool:
    return not sess.dirty

def get_session() -> Any: # type: ignore
    sess = next(filter(is_free_session, session_pool), None)
    if sess:
        return sess
    logger.info('Create an new database session')
    sess = Session()
    session_pool.append(sess)
    return sess

__all__ = [
  'get_session'
]