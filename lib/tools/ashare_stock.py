import traceback
import akshare as ak
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta

from lib.model import NewsInfo
from lib.utils.string import hash_str
from lib.tools.cache_decorator import use_cache
from lib.logger import create_logger

logger = create_logger('lib.tools.ashare_stock')

def determine_exchange(stock_symbol: str) -> str:
    """
    根据股票代码判断交易所
    
    Args:
        stock_symbol: 股票代码
        
    Returns:
        交易所代码：SH或SZ
    """
    # 根据股票代码规则判断
    if stock_symbol.startswith("6"):
        return "SH"  # 上海证券交易所
    elif stock_symbol.startswith(("0", "2", "3")):
        return "SZ"  # 深圳证券交易所
    else:
        # 默认返回SH
        return "SH"

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


@use_cache(86400 * 7, use_db_cache=True)
def get_financial_balance_sheet(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司资产负债表数据

    Args:
        symbol: 股票代码

    Returns:
        包含资产负债表数据的字典
    """
    # 获取资产负债表数据
    df = ak.stock_balance_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)

    if df.empty:
        raise ValueError(f"未找到股票 {symbol} 的资产负债表数据")

    # 转换为字典格式，便于处理
    result = {
        "symbol": symbol,
        "report_date": str(df.iloc[0]["REPORT_DATE"]) if "REPORT_DATE" in df.columns and not df.empty else "未知",
        "data": {},
    }

    # 主要资产负债表项目（英文列名映射）
    key_items_mapping = {
        "TOTAL_ASSETS": "总资产",
        "TOTAL_CURRENT_ASSETS": "流动资产",
        "MONETARYFUNDS": "货币资金",
        "TRADE_FINASSET": "交易性金融资产",
        "ACCOUNTS_RECE": "应收账款",
        "INVENTORY": "存货",
        "FIXED_ASSET": "固定资产",
        "INTANGIBLE_ASSET": "无形资产",
        "GOODWILL": "商誉",
        "TOTAL_LIABILITIES": "总负债",
        "TOTAL_CURRENT_LIAB": "流动负债",
        "ACCOUNTS_PAYABLE": "应付账款",
        "SHORT_LOAN": "短期借款",
        "LONG_LOAN": "长期借款",
        "TOTAL_EQUITY": "所有者权益",
        "SHARE_CAPITAL": "股本",
        "CAPITAL_RESERVE": "资本公积",
        "SURPLUS_RESERVE": "盈余公积",
        "UNASSIGN_RPOFIT": "未分配利润",
    }

    # 获取最新一期数据
    latest_row = df.iloc[0]
    
    for eng_col, chn_name in key_items_mapping.items():
        if eng_col in df.columns:
            # 取最新一期数据
            value = latest_row[eng_col]
            result["data"][chn_name] = float(value) if pd.notna(value) and value != "" else 0

    return result


@use_cache(86400 * 7, use_db_cache=True)
def get_financial_profit_statement(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司利润表数据

    Args:
        symbol: 股票代码

    Returns:
        包含利润表数据的字典
    """
    # 获取利润表数据
    df = ak.stock_profit_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)

    if df.empty:
        raise ValueError(f"未找到股票 {symbol} 的利润表数据")

    result = {
        "symbol": symbol,
        "report_date": str(df.iloc[0]["REPORT_DATE"]) if "REPORT_DATE" in df.columns and not df.empty else "未知",
        "data": {},
    }

    # 主要利润表项目（英文列名映射）
    key_items_mapping = {
        "TOTAL_OPERATE_INCOME": "营业收入",
        "OPERATE_COST": "营业成本",
        "OPERATE_PROFIT": "营业利润",
        "TOTAL_PROFIT": "利润总额",
        "NETPROFIT": "净利润",
        "PARENT_NETPROFIT": "归属于母公司所有者的净利润",
        "BASIC_EPS": "基本每股收益",
        "DILUTED_EPS": "稀释每股收益",
    }

    # 获取最新一期数据
    latest_row = df.iloc[0]
    
    for eng_col, chn_name in key_items_mapping.items():
        if eng_col in df.columns:
            value = latest_row[eng_col]
            result["data"][chn_name] = float(value) if pd.notna(value) and value != "" else 0

    return result


@use_cache(86400 * 7, use_db_cache=True)
def get_financial_cash_flow(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司现金流量表数据

    Args:
        symbol: 股票代码

    Returns:
        包含现金流量表数据的字典
    """
    # 获取现金流量表数据
    df = ak.stock_cash_flow_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)

    if df.empty:
        raise ValueError(f"未找到股票 {symbol} 的现金流量表数据")

    result = {
        "symbol": symbol,
        "report_date": str(df.iloc[0]["REPORT_DATE"]) if "REPORT_DATE" in df.columns and not df.empty else "未知",
        "data": {},
    }

    # 主要现金流量表项目（英文列名映射）
    key_items_mapping = {
        "NETCASH_OPERATE": "经营活动产生的现金流量净额",
        "NETCASH_INVEST": "投资活动产生的现金流量净额",
        "NETCASH_FINANCE": "筹资活动产生的现金流量净额",
        "CCE_ADD": "现金及现金等价物净增加额",
        "SALES_SERVICES": "销售商品、提供劳务收到的现金",
        "RECEIVE_TAX_REFUND": "收到的税费返还",
        "CONSTRUCT_LONG_ASSET": "购建固定资产、无形资产和其他长期资产支付的现金",
        "PAY_DEBT_CASH": "偿还债务支付的现金",
        "ASSIGN_DIVIDEND_PORFIT": "分配股利、利润或偿付利息支付的现金",
    }

    # 获取最新一期数据
    latest_row = df.iloc[0]
    
    for eng_col, chn_name in key_items_mapping.items():
        if eng_col in df.columns:
            value = latest_row[eng_col]
            result["data"][chn_name] = float(value) if pd.notna(value) and value != "" else 0

    return result


@use_cache(86400 * 7, use_db_cache=True)
def get_financial_indicators(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司主要财务指标

    Args:
        symbol: 股票代码

    Returns:
        包含主要财务指标的字典
    """
    # 获取财务指标数据
    df = ak.stock_financial_abstract_ths(symbol=symbol)

    if df.empty:
        raise ValueError(f"未找到股票 {symbol} 的财务指标数据")

    result = {
        "symbol": symbol,
        "data": {},
    }

    # 将最新一期数据转换为字典格式
    if not df.empty:
        latest_data = df.iloc[0]  # 取最新一期数据
        
        # 主要财务指标
        key_indicators = [
            "净利润",
            "净利润同比增长率", 
            "扣非净利润",
            "营业总收入",
            "营业总收入同比增长率",
            "基本每股收益",
            "每股净资产",
            "每股资本公积金",
            "每股未分配利润",
            "每股经营现金流",
            "销售净利率",
            "销售毛利率",
            "净资产收益率",
            "流动比率",
            "速动比率",
            "资产负债率",
        ]
        
        for indicator in key_indicators:
            if indicator in latest_data.index:
                value = latest_data[indicator]
                # 处理特殊值
                if pd.notna(value) and value != "False" and value != "":
                    result["data"][indicator] = value
                else:
                    result["data"][indicator] = None

    return result


def get_comprehensive_financial_data(symbol: str) -> Dict[str, Any]:
    """
    获取公司综合财务数据（资产负债表、利润表、现金流量表）

    Args:
        symbol: 股票代码

    Returns:
        包含综合财务数据的字典
    """
    return {
        "symbol": symbol,
        "balance_sheet": get_financial_balance_sheet(symbol),
        "profit_statement": get_financial_profit_statement(symbol),
        "cash_flow": get_financial_cash_flow(symbol),
        "financial_indicators": get_financial_indicators(symbol),
    }


def convert_to_json_serializable(obj):
    """
    将对象转换为JSON可序列化的格式
    """
    if hasattr(obj, 'isoformat'):  # datetime, date objects
        return obj.isoformat()
    elif hasattr(obj, 'item'):  # numpy types
        return obj.item()
    elif pd.isna(obj):  # pandas NaN
        return None
    else:
        return obj


def remove_unwanted_fields(data_record):
    """
    从数据记录中移除不需要的字段（最新价、涨跌幅）
    
    Args:
        data_record: 单条数据记录字典
    
    Returns:
        清理后的数据记录
    """
    unwanted_fields = ['最新价', '涨跌幅']
    
    if not data_record or not isinstance(data_record, dict):
        return data_record
    
    return {k: v for k, v in data_record.items() if k not in unwanted_fields}


def clean_data_for_json(data):
    """
    清理数据使其可以序列化为JSON
    """
    if isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: clean_data_for_json(value) for key, value in data.items()}
    else:
        return convert_to_json_serializable(data)


@use_cache(86400, use_db_cache=True)
def get_shareholder_changes_data(stock_code: str) -> Dict[str, Any]:
    """
    获取指定股票的股东股本变动详情（最新数据）
    
    Args:
        stock_code: 股票代码（如：000001、600036等）
    
    Returns:
        包含字典：股东持股变动详情
    """
    
    logger.info(f"开始获取股票 {stock_code} 的股东变动数据")
    
    results = {}

    try:
        logger.info(f"正在获取股票 {stock_code} 的高管持股变动详情")

        management_df = ak.stock_zh_a_gdhs_detail_em(symbol=stock_code)
        
        if not management_df.empty:
            # 查找日期列并排序，只返回最新的一条数据
            date_columns = [col for col in management_df.columns if '日期' in col or '时间' in col or 'date' in col.lower()]
            date_col = date_columns[0]
            management_df[date_col] = pd.to_datetime(management_df[date_col], errors='coerce')
            management_df_sorted = management_df.sort_values(by=date_col, ascending=False, na_position='last')
            latest_record = management_df_sorted.iloc[0]
            results = clean_data_for_json(latest_record.to_dict())
            logger.info(f"成功获取 {stock_code} 的高管持股变动详情最新记录，日期: {latest_record[date_col]}")
        
        else:
            logger.warning(f"未获取到 {stock_code} 的高管持股变动详情")
            
    except Exception as e:
        logger.error(f"获取高管持股变动详情失败: {e}")
    
    return results
