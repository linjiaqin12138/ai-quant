from typing import TypedDict, Mapping, Any

from .session import get_session
from .tables import Events_Cache

def set_event(key: str, context: str) -> None:
    try: 
        session = get_session()
        session.add(Events_Cache(key = key, context = context))
        session.commit()
    except:
        session.rollback()

def get_event(key: str) -> Any | None:
    sess = get_session()
    result = sess.query(Events_Cache).filter(Events_Cache.key == key).first()
    return result.context if result is not None else None

def has_event(key: str) -> bool:
    session = get_session()
    return bool(session.query(Events_Cache).filter(Events_Cache.key == key).first())

def del_event(key: str) -> None:
    sess = get_session()
    sess.query(Events_Cache).filter(Events_Cache.key == key).delete()
    sess.commit()
  