from typing import Dict, Any
import json
from .session import get_session
from .tables import Events_Cache
from ..utils.logger import logger

def set_event(key: str, context: str | Dict) -> None:
    try: 
        session = get_session()
        event_to_update = session.query(Events_Cache).filter(Events_Cache.key == key).first()
        if event_to_update != None:
            logger.debug(f'Update event {key}')
            if type(context) == str:
                event_to_update.context = context
                event_to_update.type = 'string'
            if type(context) == dict:
                event_to_update.context = json.dumps(context)
                event_to_update.type = 'json'
        else:
            logger.debug(f'Insert new event {key}')
            if type(context) == str:
                session.add(Events_Cache(key = key, context = context, type='string'))
            if type(context) == dict:
                session.add(Events_Cache(key = key, context = json.dumps(context), type='json'))
        session.commit()
    except:
        session.rollback()

def get_event(key: str) -> str  | None:
    sess = get_session()
    result = sess.query(Events_Cache).filter(Events_Cache.key == key).first()
    if result is None:
        return None
    if result.type == 'string':
        return result.context
    if result.type == 'json':
        return json.loads(result.context)
    return None

def has_event(key: str) -> bool:
    session = get_session()
    return bool(session.query(Events_Cache).filter(Events_Cache.key == key).first())

def del_event(key: str) -> None:
    sess = get_session()
    sess.query(Events_Cache).filter(Events_Cache.key == key).delete()
    sess.commit()
  