import requests
from typing import Any, Dict, List

from lib.config import get_http_proxy
from lib.utils.symbol import determine_exchange

def get_china_holiday(year: str) -> List[str]:
    return list(
        requests.get(f"https://api.jiejiariapi.com/v1/holidays/{year}").json().keys()
    )

def read_web_page_by_jina(url: str) -> str:
    """
    使用Jina API读取网页内容
    
    Args:
        url: 要读取的网页URL
    
    Returns:
        网页内容字符串
    """
    # Jina Reader API端点
    jina_url = f"https://r.jina.ai/{url}"
    
    # 获取代理设置
    proxy = get_http_proxy()
    proxies = None
    if proxy:
        proxies = {
            'http': proxy,
            'https': proxy
        }
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 发送请求到Jina API
    response = requests.get(jina_url, headers=headers, proxies=proxies, timeout=600)
    if response.status_code == 451:
        raise Exception("根据法律要求，无法爬取该网页内容")

    response.raise_for_status()
    
    # 返回网页内容
    return response.text

def get_crypto_info(coin_ids: List[str]) -> List[Dict[str, Any]]:
    """获取加密货币数据（价格、市值、流通量、涨跌幅等）"""
    ids = ",".join(coin_ids)
    params = {
        "vs_currency": "usd",
        "ids": ids.strip(),
        "order": "market_cap_desc",
        "per_page": len(coin_ids),
        "page": 1,
        "sparkline": "false"
    }
    proxies = None
    if proxy := get_http_proxy():
        proxies = {"http": proxy, "https": proxy}
    response = requests.get("https://api.coingecko.com/api/v3/coins/markets", params=params, proxies=proxies)
    response.raise_for_status()
    # "id": "bitcoin",
    # "symbol": "btc",
    # "name": "Bitcoin",
    # "image": "https://coin-images.coingecko.com/coins/images/1/large/bitcoin.png?1696501400",
    # "current_price": 119058,
    # "market_cap": 2368101320607,
    # "market_cap_rank": 1,
    # "fully_diluted_valuation": 2368105367313,
    # "total_volume": 45372765379,
    # "high_24h": 119157,
    # "low_24h": 117583,
    # "price_change_24h": -98.71209599151916,
    # "price_change_percentage_24h": -0.08284,
    # "market_cap_change_24h": -2995154463.3911133,
    # "market_cap_change_percentage_24h": -0.12632,
    # "circulating_supply": 19896537.0,
    # "total_supply": 19896571.0,
    # "max_supply": 21000000.0,
    # "ath": 122838,
    # "ath_change_percentage": -3.15454,
    # "ath_date": "2025-07-14T07:56:01.937Z",
    # "atl": 67.81,
    # "atl_change_percentage": 175338.37917,
    # "atl_date": "2013-07-06T00:00:00.000Z",
    # "roi": null,
    # "last_updated": "2025-07-24T02:49:13.559Z" 
    return response.json()

def get_fear_greed_index() -> Dict[str, Any]:
    """
    获取加密货币恐慌与贪婪指数（Fear & Greed Index
    # 获取当前恐惧贪婪指数
    curl -X GET "https://api.alternative.me/fng/?limit=1" -H "Accept: application/json"

    # 获取最近10天的历史数据
    curl -X GET "https://api.alternative.me/fng/?limit=10&date_format=world" -H "Accept: application/json"

    # 获取特定日期的数据
    curl -X GET "https://api.alternative.me/fng/?limit=1&date_format=world&format=json" -H "Accept: application/json"   
    """
    url = "https://api.alternative.me/fng/"
    proxies = None
    if proxy := get_http_proxy():
        proxies = {"http": proxy, "https": proxy}
    response = requests.get(url, proxies=proxies)
    response.raise_for_status()
    data = response.json()
    if "data" in data and len(data["data"]) > 0:
        return data["data"][0]
    else:
        raise ValueError("未获取到指数数据。")
    
def fetch_realtime_stock_snapshot(symbol: str) -> Dict[str, str]:
    exchange = determine_exchange(symbol).lower()
    url = f"https://qt.gtimg.cn/q={exchange + symbol}"
    response = requests.get(url).text  # 返回文本数据
    data = response.split("~")  # 按 ~ 分割字段
    # 字段名列表，未知字段用 unknow_n 命名
    field_names = [
        "__ignore__", 
        "name", "code", "latest_price", "prev_close", "open", "volume", # 最新价、昨收、今开、成交量
        "active_buy_vol", # 外盘 以卖出价成交的成交量，代表主动买入的成交量。即买方以卖方报价主动成交，通常被认为是买方积极进攻的量
        "active_sell_vol", # 内盘 以买入价成交的成交量，代表主动卖出的成交量。即卖方以买方报价主动成交，通常被认为是卖方主动抛售的量
        "bid_price", "bid_volume", "bid2_price", "bid2_volume", "bid3_price", "bid3_volume", "bid4_price", "bid4_volume",
        "bid5_price", "bid5_volume", "ask_price", "ask_volume", "ask2_price", "ask2_volume", "ask3_price", "ask3_volume",
        "ask4_price", "ask4_volume", "ask5_price", "ask5_volume", # 买卖N价，N量
        "last_tick_trade", # 最近逐笔成交 表示最近一笔成交的价格和数量等信息，通常用于反映最新一笔实际成交的市场情况。它可以帮助分析当前市场的活跃度和买卖双方的力量变化
        "timestamp", "change", "change_percent", "high", "low", # 时间戳、涨跌额、涨跌幅%、最高价、最低价
        "__ignore__", # 价格/成交量（手）/成交额 14.65/816103/1191862295
        "volume_in_lots", # 成交量（手）
        "turnover_amount", # 成交额（万）
        "turnover_rate", # 换手率（%）
        "pe_dynamic", # 市盈率（动态）
        "__ignore__", 
        "__ignore__", # 最高
        "__ignore__", # 最低
        "amplitude", # 振幅（%）
        "circulating_market_cap", # 流通市值
        "total_market_cap", # 总市值
        "pb_ratio", # 市净率
        "limit_up_price", # 涨停价
        "limit_down_price", # 跌停价
    ]
    # 保证字段数和数据长度一致
    if len(data) < len(field_names):
        # 补齐未知字段名
        field_names += ([f"__ignore__"] * (len(data) - len(field_names)))
    elif len(data) > len(field_names):
        data = data[:len(field_names)]

    result = {field: value for field, value in zip(field_names, data)}
    del result['__ignore__']
    return result

# get_single_stock_price("sh600588")