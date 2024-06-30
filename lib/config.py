import os
from typing import Dict

def get_mysql_uri() -> str:
    # username = os.environ.get("MYSQL_USER") or "py"
    # password = os.environ.get("MYSQL_PASS") or "wapwap12"
    # hostname = os.environ.get("MYSQL_HOST") or "127.0.0.1",
    # database = os.environ.get("MYSQL_DB") or "python_job",
    # port = os.environ.get("MYSQL_PORT").strip('"') or 3306
    return f"mysql+pymysql://py:wapwap12@127.0.0.1:3306/python_job"
    # print(f"mysql+pymysql://{username}:{password}@{hostname}:{port}/{database}")
    # return f"mysql+pymysql://{username}:{password}@{hostname}:{port}/{database}"

def get_binance_config() -> Dict:
    return {
        "apiKey": os.environ.get("BINANCE_API_KEY"),
        "secret": os.environ.get("BINANCE_SECRET_KEY"),
        "httpsProxy": 'http://127.0.0.1:7890',
        "wsProxy": 'http://127.0.0.1:7890'
    }

def get_http_proxy() -> str:
    return ''

API_MAX_RETRY_TIMES = int(os.environ.get("API_MAX_RETRY_TIMES") or 5)
