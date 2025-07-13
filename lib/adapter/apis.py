import requests
from typing import List

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