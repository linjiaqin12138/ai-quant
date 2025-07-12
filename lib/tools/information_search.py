from datetime import datetime
from typing import List
import httplib2

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from lib.config import get_http_proxy, get_google_api_key, get_google_cse_id
from lib.model.news import NewsInfo
from lib.utils.time import parse_datetime_string
from lib.utils.string import hash_str
from lib.utils.decorators import with_retry
from lib.logger import logger

def duckduckgo_search(query: str, max_results: int = 10, region: str = "us-en", time_limit: str = None) -> List[NewsInfo]:
    """
    使用DuckDuckGo搜索新闻信息
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数量，默认10
        region: 搜索区域，默认us-en
        time_limit: 时间限制，默认w(一周)，可选值: d(一天), w(一周), m(一个月), y(一年)
    
    Returns:
        NewsInfo对象数组
    """
    
    # 获取代理设置
    proxy = get_http_proxy()
    ddgs_kwargs = {}
    
    if proxy:
        # 设置代理参数（新版本使用proxy而不是proxies）
        ddgs_kwargs['proxy'] = proxy
    
    with DDGS(**ddgs_kwargs) as ddgs:
        # 搜索新闻
        results = list(ddgs.news(
            keywords=query,
            region=region,
            safesearch='off',
            timelimit=time_limit,
            max_results=max_results
        ))
        logger.debug("DuckDuckGo搜索结果数量: %d", len(results))

        # 将结果转换为NewsInfo对象数组
        news_infos = []
        for result in results:
            # 生成唯一的news_id
            news_id = hash_str(f"{result.get('url', '')}{result.get('title', '')}")

            # 解析时间戳
            date_str = result.get('date', '')
            timestamp = None
            if date_str:
                # 尝试解析日期字符串
                timestamp = parse_datetime_string(date_str)
            
            # 如果解析失败或没有日期，使用当前时间
            if timestamp is None:
                timestamp = datetime.now()
            
            # 创建NewsInfo对象
            news_info = NewsInfo(
                news_id=news_id,
                title=result.get('title', ''),
                timestamp=timestamp,
                url=result.get('url', ''),
                platform="ddgo",
                description=result.get('body', '')
            )
            news_infos.append(news_info)
        
        return news_infos

def google_search(query: str, max_results: int = 10, region: str = "us-en", time_limit: str =  None) -> List[NewsInfo]:
    """
    使用Google Custom Search API搜索新闻信息
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数量，默认10
        region: 搜索区域，默认us-en (格式如us-en, cn-zh等)
        time_limit: 时间限制，默认w(一周)，可选值: d(一天), w(一周), m(一个月), y(一年)
    
    Returns:
        NewsInfo对象数组
    """
    api_key = get_google_api_key()
    cse_id = get_google_cse_id()
    
    if not api_key or not cse_id:
        raise ValueError("Google API密钥或Custom Search Engine ID未配置")
    
    # 获取代理设置
    proxy = get_http_proxy()
    
    # 构建HTTP客户端，支持代理
    http = httplib2.Http()
    if proxy:
        # 解析代理URL
        if proxy.startswith('http://'):
            proxy_host_port = proxy[7:]  # 去掉 http:// 前缀
        elif proxy.startswith('https://'):
            proxy_host_port = proxy[8:]  # 去掉 https:// 前缀
        else:
            proxy_host_port = proxy
        
        # 设置代理
        if ':' in proxy_host_port:
            host, port = proxy_host_port.split(':', 1)
            http = httplib2.Http(proxy_info=httplib2.ProxyInfo(
                proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
                proxy_host=host,
                proxy_port=int(port)
            ))
        else:
            # 默认使用80端口
            http = httplib2.Http(proxy_info=httplib2.ProxyInfo(
                proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
                proxy_host=proxy_host_port,
                proxy_port=80
            ))
    
    # 构建Google Custom Search服务
    service = build("customsearch", "v1", developerKey=api_key, http=http)
    
    # 转换time_limit为Google API的dateRestrict格式
    time_limit_map = {
        'd': 'd1',      # 一天
        'w': 'w1',      # 一周
        'm': 'm1',      # 一个月
        'y': 'y1'       # 一年
    }
    date_restrict = time_limit_map.get(time_limit, 'w1') if time_limit else None
    
    # 根据region设置搜索语言和地区
    search_params = {
        'q': query,
        'cx': cse_id,
        'num': min(max_results, 10),  # Google API最多返回10个结果
        'sort': 'date',  # 按日期排序
        'dateRestrict': date_restrict
    }
    
    # 设置语言和地区参数
    if region:
        # 解析region格式 (如us-en, cn-zh)
        if '-' in region:
            country, lang = region.split('-', 1)
            search_params['gl'] = country.upper()  # 地理位置 (US, CN等)
            search_params['hl'] = lang.lower()     # 界面语言 (en, zh等)
            search_params['lr'] = f'lang_{lang.lower()}'  # 搜索结果语言
        else:
            # 如果只有语言代码
            search_params['hl'] = region.lower()
            search_params['lr'] = f'lang_{region.lower()}'
    
    # 执行搜索
    try:
        result = service.cse().list(**search_params).execute()
        
        # 将结果转换为NewsInfo对象数组
        news_infos = []
        items = result.get('items', [])
        logger.debug(f"Google搜索结果: {result}")
        logger.debug(f"Google搜索结果数量: {len(items)}")   
        for item in items:
            # 生成唯一的news_id
            news_id = hash_str(f"{item.get('link', '')}{item.get('title', '')}")
            
            # 解析时间戳
            timestamp = datetime.now()  # Google搜索结果通常没有精确时间戳
            
            # 创建NewsInfo对象
            news_info = NewsInfo(
                news_id=news_id,
                title=item.get('title', ''),
                timestamp=timestamp,
                url=item.get('link', ''),
                platform="google",
                description=item.get('snippet', '')
            )
            news_infos.append(news_info)
        
        return news_infos
        
    except HttpError as e:
        raise ConnectionError(f"Google搜索API请求失败: {e}")

@with_retry(
    retry_errors=(ConnectionError, TimeoutError, OSError, HttpError, RatelimitException),
    max_retry_times=3
)
def unified_search(query: str, max_results: int = 10, region: str = "zh-cn", time_limit: str = None) -> List[NewsInfo]:
    """
    统一搜索函数，优先使用Google搜索，失败时使用DuckDuckGo搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数量，默认10
        region: 搜索区域, 如en-us
        time_limit: 时间限制，默认w(一周)
    
    Returns:
        NewsInfo对象数组
    """
    # 首先尝试使用Google搜索

    logger.info("正在搜索：%s", query)
    api_key = get_google_api_key()
    cse_id = get_google_cse_id()

    if api_key and cse_id:
        try:
            return google_search(query, max_results, region, time_limit)
        except Exception as e:
            logger.error(f"Google搜索失败，错误信息: {e}")
            # 如果Google搜索失败，回退到DuckDuckGo搜索
            logger.info(f"Google搜索失败，尝试使用DuckDuckGo搜索: {e}")
            
    return duckduckgo_search(query, max_results, region, time_limit)


