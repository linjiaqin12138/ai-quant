import akshare as ak
import pandas as pd
from typing import List
from datetime import datetime
from lib.model import NewsInfo
from lib.utils.string import hash_str
from lib.tools.cache_decorator import use_cache

# 不适用数据库 Data too long for column 'context' at row 1
@use_cache(
    86400, 
    use_db_cache=True,
    serializer=lambda l: [x.to_dict() for x in l],
    deserializer=lambda l: [NewsInfo.from_dict(x) for x in l],
)
def get_stock_news(symbol: str) -> List[NewsInfo]:
    """
    获取A股股票的新闻数据，使用数据库缓存
    
    Args:
        symbol: 股票代码
    
    Returns:
        NewsInfo对象列表，按时间倒序排列
    """
    # 从 akshare 获取数据
    news_df = ak.stock_news_em(symbol=symbol)
    news_df["发布时间"] = pd.to_datetime(news_df["发布时间"])
    
    news_info_list: List[NewsInfo] = []

    for _, row in news_df.iterrows():
        news_info = NewsInfo(
            title=row["新闻标题"],
            timestamp=row["发布时间"],
            description=row["新闻内容"],
            news_id=hash_str(row["新闻标题"]),
            url=row["新闻链接"],
            platform="eastmoney",
        )
        news_info_list.append(news_info)

    return news_info_list

def get_stock_news_during(symbol: str, from_time: datetime, end_time: datetime = datetime.now()) -> List[NewsInfo]:
    """
    获取指定时间范围内的A股股票新闻数据
    
    Args:
        symbol: 股票代码
        from_time: 起始时间
        end_time: 结束时间
    
    Returns:
        NewsInfo对象列表，按时间倒序排列
    """
    news_list = get_stock_news(symbol)
    return [
        news for news in news_list 
        if from_time <= news.timestamp <= end_time
    ]
