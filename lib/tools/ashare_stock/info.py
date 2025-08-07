import akshare as ak
from typing import Literal, TypedDict
from lib.tools.cache_decorator import use_cache
from lib.utils.symbol import determine_exchange, is_etf
from .list import get_fund_list

AShareStockInfo = TypedDict('AShareStockInfo', {
    'stock_type': Literal["ETF", "股票"],
    'stock_name': str,
    'stock_business': str,
    'exchange': str,
})

@use_cache(86400 * 30, use_db_cache=True)
def get_ashare_stock_info(symbol: str) -> AShareStockInfo:
    """
    获取A股股票或ETF的基本信息，使用二级缓存
    """
    result: AShareStockInfo = {}
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
        result["exchange"] = determine_exchange(symbol)
    return result
