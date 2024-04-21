from .session import get_session
from .tables import EVENTS

def set_event(key: str, context: dict) -> None:
    try: 
        session = get_session()
        session.add(EVENTS(key = key, context = context))
        session.commit()
    except:
        session.rollback()

def has_event(key: str) -> bool:
    session = get_session()
    return bool(session.query(EVENTS).filter(EVENTS.key == key).first())

def del_event(key: str) -> None:
    sess = get_session()
    sess.query(EVENTS).filter(EVENTS.key == key).delete()
    sess.commit()
  