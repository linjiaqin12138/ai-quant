import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

username = os.environ.get('MYSQL_USER', 'py')
# TODO: urlencoded
password = os.environ.get('MYSQL_PASS', 'wapwap12')
hostname = os.environ.get('MYSQL_HOST', '127.0.0.1')
db_name = os.environ.get('MYSQL_DB', 'python_job')
db_port = os.environ.get('MYSQL_PORT', '3306')

# 创建数据库连接引擎
engine = create_engine(f'mysql+pymysql://{username}:{password}@{hostname}:{db_port}/{db_name}')

__all__ = [
  'engine'
]