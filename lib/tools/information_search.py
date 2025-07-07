from datetime import datetime
from typing import List
import requests
import httplib2

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from lib.adapter.llm import get_agent
from lib.config import get_http_proxy, get_google_api_key, get_google_cse_id
from lib.model.news import NewsInfo
from lib.utils.time import parse_datetime_string
from lib.utils.string import hash_str
from lib.utils.decorators import with_retry
from lib.logger import logger

@with_retry(
    retry_errors=(ConnectionError, TimeoutError, OSError, RatelimitException),
    max_retry_times=3
)
def duckduckgo_search(query: str, max_results: int = 10, region: str = "us-en", time_limit: str = "w") -> List[NewsInfo]:
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

@with_retry(
    retry_errors=(ConnectionError, TimeoutError, OSError, HttpError),
    max_retry_times=3
)
def google_search(query: str, max_results: int = 10, region: str = "us-en", time_limit: str = "w") -> List[NewsInfo]:
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
    date_restrict = time_limit_map.get(time_limit, 'w1')
    
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

def unified_search(query: str, max_results: int = 10, region: str = "zh-cn", time_limit: str = "w") -> List[NewsInfo]:
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
    try:
        api_key = get_google_api_key()
        cse_id = get_google_cse_id()
        
        if api_key and cse_id:
            return google_search(query, max_results, region, time_limit)
        else:
            # 如果没有配置Google API，直接使用DuckDuckGo
            return duckduckgo_search(query, max_results, region, time_limit)
            
    except Exception as e:
        # Google搜索失败，回退到DuckDuckGo搜索
        print(f"Google搜索失败，回退到DuckDuckGo搜索: {e}")
        return duckduckgo_search(query, max_results, region, time_limit)

def get_global_news_report(provider: str = 'paoluz', model: str = 'gpt-4o-mini', time_range: str = 'w') -> str:
    """
    获取全球新闻和宏观经济信息
    
    Args:
        provider: LLM提供商
        model: 模型名称
        time_range: 时间范围，可选值: 'd'(一天), 'w'(一周), 'm'(一个月), 'y'(一年)
    
    Returns:
        分析后的新闻摘要
    """
    # 根据时间范围设置描述
    time_descriptions = {
        'd': '一天内',
        'w': '一周内',
        'm': '一个月内', 
        'y': '一年内'
    }
    
    time_desc = time_descriptions.get(time_range, '一周内')
    
    # 设置系统提示
    system_prompt = f"""你是一个专业的金融分析师。请搜索{time_desc}的全球新闻和宏观经济信息，重点关注对交易有用的信息。请分析这些新闻对市场的潜在影响，并提供简洁的投资建议。回复请使用中文。"""
    
    agent = get_agent(provider, model)
    agent.set_system_prompt(system_prompt)
    
    # 注册统一搜索工具 - 优先使用Google搜索，失败时使用DuckDuckGo
    agent.register_tool(unified_search)
    
    # 构建搜索提示
    prompt = f"""
    请使用unified_search工具搜索以下关键词的最新新闻，获取{time_desc}的信息（time_limit参数设置为"{time_range}"）：

    1. "global economy macroeconomic indicators" (全球经济和宏观经济指标)
    2. "central bank policy interest rates" (央行政策和利率)
    3. "market volatility stock market news" (市场波动和股市新闻)
    4. "geopolitical events market impact" (地缘政治事件和市场影响)
    5. "inflation data economic reports" (通胀数据和经济报告)
    6. "cryptocurrency bitcoin market" (加密货币和比特币市场)
    7. "oil gold commodity prices" (石油黄金商品价格)
    
    搜索时请使用以下参数：
    - time_limit: "{time_range}"
    - max_results: 10
    
    搜索完成后，请分析这些新闻信息并提供：
    
    ## 分析报告结构：
    
    ### 1. 主要市场影响因素总结
    - 列出最重要的3-5个市场驱动因素
    - 简要说明其影响程度和时间范围
    
    ### 2. 资产类别影响分析
    - **股票市场**: 对主要股指的影响分析
    - **债券市场**: 对利率和债券价格的影响
    - **外汇市场**: 对主要货币对的影响
    - **商品市场**: 对黄金、石油等大宗商品的影响
    - **加密货币**: 对比特币等数字资产的影响
    
    ### 3. 投资建议
    - **短期建议** (1-2周): 具体的交易策略和仓位建议
    - **中期建议** (1-3个月): 资产配置和风险管理
    
    ### 4. 风险提示
    - 需要重点关注的风险因素
    - 可能的黑天鹅事件
    - 建议的风险控制措施
    
    请确保所有信息都基于搜索到的最新新闻数据，并保持客观和专业的分析态度。
    
    注意：如果搜索返回的是模拟数据（由于网络问题），请在分析中说明这一点，并基于一般市场知识提供分析。
    """
    
    try:
        response = agent.ask(prompt, tool_use=True)
        return response
    except Exception as e:
        return f"获取新闻信息失败: {str(e)}"

@with_retry(
    retry_errors=(ConnectionError, TimeoutError, OSError, RatelimitException),
    max_retry_times=3
)
def read_web_page(url: str) -> str:
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
    response.raise_for_status()
    
    # 返回网页内容
    return response.text

