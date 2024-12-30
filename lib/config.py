import os
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(verbose=True)

def get_log_level() -> str:
    return os.environ.get("LOG_LEVEL", "INFO").upper()

def get_create_table() -> bool:
    return os.environ.get("CREATE_TABLE", "FALSE") == "TRUE"

def get_database_uri() -> str:
    db_engine = os.environ.get("DB_ENGINE") or "sqlite"
    if db_engine == 'sqlite':
        return f'sqlite:///{Path.home() / "quant.sqlite"}'
    username = os.environ.get("MYSQL_USER") or "py"
    password = os.environ.get("MYSQL_PASS") or "wapwap12"
    hostname = os.environ.get("MYSQL_HOST") or "127.0.0.1"
    database = os.environ.get("MYSQL_DB") or "python_job"
    port = os.environ.get("MYSQL_PORT") or 3306
    return f"mysql+pymysql://{username}:{password}@{hostname}:{port}/{database}"

def get_binance_config() -> Dict:
    proxy = get_http_proxy()
    config = {
        "apiKey": os.environ.get("BINANCE_API_KEY"),
        "secret": os.environ.get("BINANCE_SECRET_KEY")
    }
    if proxy:
        config['httpsProxy'] = proxy
        config['wsProxy'] = proxy
    return config

def get_push_token() -> str:
    return os.environ.get("PUSH_PLUS_TOKEN")

def get_baichuan_token() -> str:
    return os.environ.get("BAI_CHUAN_TOKEN")

def get_paoluz_token() -> str:
    return os.environ.get("PAOLUZ_AI_TOKEN")

def get_http_proxy() -> str:
    return os.environ.get("PROXY")

API_MAX_RETRY_TIMES = int(os.environ.get("API_MAX_RETRY_TIMES") or 5)

if __name__ == "__main__":
    print(get_database_uri())
    print(get_binance_config())
    print(get_http_proxy())
    print(get_log_level())
    print(get_create_table())
    print(get_push_token())
    print(get_baichuan_token())
    print(API_MAX_RETRY_TIMES)