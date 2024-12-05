from lib.adapter.lock.api import CreateLockFactory
from lib.adapter.lock.database import DbBasedDistributedLock
from .fake_db import db_str

create_lock_factory: CreateLockFactory = lambda o: DbBasedDistributedLock(**o, db_url=db_str)