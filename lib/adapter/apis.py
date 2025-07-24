import requests
from typing import Any, Dict, List

from lib.config import get_http_proxy


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
    """获取加密货币恐慌与贪婪指数（Fear & Greed Index）"""
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