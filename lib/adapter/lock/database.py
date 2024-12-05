import time
import sqlite3
from sqlalchemy import create_engine, select, delete, update, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from lib.adapter.lock.api import DistributedLock, Options
from lib.adapter.database.sqlalchemy import events
from lib.logger import logger
from lib.config import get_mysql_uri
import json
import uuid

class DbBasedDistributedLock(DistributedLock):
    def __init__(self, name: str, max_concurrent_access: int, expiration_time: int, db_url: str = get_mysql_uri()):
        super().__init__(name = name, max_concurrent_access = max_concurrent_access, expiration_time = expiration_time)
        self.engine = create_engine(echo=False, url=db_url)
        self.Session = sessionmaker(bind=self.engine)

    def acquire(self):
        session = self.Session()
        try:
            with session.begin():
                if self.engine.url.drivername.find('sqlite') >= 0:
                    session.execute(text('BEGIN IMMEDIATE TRANSACTION'))

                lock_row = session.execute(
                    select(events.c.context).where(events.c.key == self.name).with_for_update()
                ).fetchone()

                current_time = time.time()
                if lock_row:
                    context_data = json.loads(lock_row[0])
                    # Remove expired locks
                    context_data['locks'] = [lock for lock in context_data.get('locks', []) 
                                             if lock['expiration'] > current_time]
                    if len(context_data['locks']) < self.max_concurrent_access:
                        lock_id = str(uuid.uuid4())
                        context_data['locks'].append({
                            'id': lock_id,
                            'expiration': current_time + self.expiration_time
                        })
                        session.execute(
                            update(events).where(events.c.key == self.name)
                            .values(context=json.dumps(context_data))
                        )
                    else:
                        return None
                else:
                    lock_id = str(uuid.uuid4())
                    context_data = {
                        "locks": [{
                            'id': lock_id,
                            "expiration": current_time + self.expiration_time
                        }]
                    }
                    session.execute(
                        events.insert().values(
                            key=self.name, 
                            context=json.dumps(context_data),
                            type='json'
                        )
                    )
            session.commit()
            return lock_id
        except OperationalError as e:
            logger.error(f"[{e.code}] Lock acquisition failed: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def release(self, lock_id: str):
        session = self.Session()
        try:
            with session.begin():
                if self.engine.url.drivername.find('sqlite') >= 0:
                    session.execute(text('BEGIN IMMEDIATE TRANSACTION'))
                lock_row = session.execute(
                    select(events.c.context).where(events.c.key == self.name).with_for_update()
                ).fetchone()

                if lock_row:
                    context_data = json.loads(lock_row[0])
                    current_time = time.time()
                    # Remove expired locks
                    context_data['locks'] = [lock for lock in context_data.get('locks', []) 
                                             if lock['expiration'] > current_time]
                    
                    # Find lock by id
                    lock_to_remove = next((lock for lock in context_data['locks'] if lock['id'] == lock_id), None)
                    if not lock_to_remove:
                        return False
                        
                    context_data['locks'].remove(lock_to_remove)

                    if not context_data['locks']:
                    # Delete row if no locks left
                        session.execute(delete(events).where(events.c.key == self.name))
                    else:
                        session.execute(
                            update(events).where(events.c.key == self.name)
                            .values(context=json.dumps(context_data))
                        )
            session.commit()
            return True
        except OperationalError as e:
            logger.error(f"Lock release failed: {e}")
            session.rollback()
            return False
        finally:
            session.close()

def create_lock(options: Options) -> DistributedLock:
    return DbBasedDistributedLock(**options)