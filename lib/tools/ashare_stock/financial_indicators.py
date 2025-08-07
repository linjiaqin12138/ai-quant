from datetime import datetime
import akshare as ak
from typing import Dict, Any
from lib.logger import logger
from lib.tools.cache_decorator import use_cache

@use_cache(86400 * 7, use_db_cache=True)
def get_financial_indicators_history(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司主要财务指标历史数据

    Args:
        symbol: 股票代码

    Returns:
        包含主要财务指标历史数据的字典
    """
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务分析-财务指标",
        "data": [],
    }
    try:
        from_year = str(datetime.now().year) if datetime.now().month >= 4 else str(datetime.now().year - 1)
        df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=from_year)
        if not df.empty:
            for _, row in df.iterrows():
                row_dict = row.dropna().to_dict()
                if row_dict.get("日期"):
                    row_dict["日期"] = str(row_dict.get("日期"))
                result["data"].append(row_dict)
            return result
    except Exception as e:
        logger.error("获取财务指标历史数据失败: %s, 尝试切换到其他数据源", e)

    result["source"] = "同花顺-财务分析-财务指标"
    df = ak.stock_financial_abstract_ths(symbol=symbol)
    if not df.empty:
        for _, row in df.iterrows():
            row_dict = row.dropna().to_dict()
            if row_dict.get("日期"):
                row_dict["日期"] = str(row_dict.get("日期"))
            result["data"].append(row_dict)

    return result

def get_recent_financial_indicators(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司主要财务指标

    Args:
        symbol: 股票代码

    Returns:
        包含主要财务指标的字典
    """
    result = get_financial_indicators_history(symbol)
    result['data'] = result['data'][-1] if result['data'] else {}
    return result
