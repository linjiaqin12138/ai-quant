import akshare as ak
from typing import List
import pandas as pd

from lib.model import NewsInfo
from lib.utils.string import hash_str
from lib.tools.cache_decorator import use_cache


def is_etf(symbol: str) -> bool:
    """
    判断证券代码是否为ETF基金
    """
    return symbol.startswith(("51", "15", "16"))


@use_cache(
    86400 * 7,
    use_db_cache=True,
    serializer=lambda df: df.to_json(orient="records", force_ascii=False),
    deserializer=lambda x: pd.read_json(x, orient="records"),
)
def get_fund_list() -> pd.DataFrame:
    """
    获取ETF基金列表，使用二级缓存
    """
    # 从 akshare 获取数据
    return ak.fund_name_em()


@use_cache(86400 * 30, use_db_cache=True)
def get_ashare_stock_info(symbol: str) -> dict:
    """
    获取A股股票或ETF的基本信息，使用二级缓存
    """
    result = {}
    if is_etf(symbol):
        df = get_fund_list()  # 使用缓存的基金列表
        result["stock_type"] = "ETF"
        result["stock_name"] = df["基金简称"].loc[df["基金代码"] == symbol].iloc[0]
        result["stock_business"] = "未知"
    else:
        df = ak.stock_individual_info_em(symbol)
        result["stock_type"] = "股票"
        result["stock_name"] = df["value"].loc[df["item"] == "股票简称"].iloc[0]
        result["stock_business"] = df["value"].loc[df["item"] == "行业"].iloc[0]
    return result


# 不适用数据库 Data too long for column 'context' at row 1
@use_cache(600)
def get_stock_news(symbol: str) -> List[NewsInfo]:
    """
    获取A股股票的新闻数据，使用数据库缓存
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
