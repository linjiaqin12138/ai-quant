import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, TypedDict
from lib.adapter.apis import fetch_realtime_stock_snapshot, get_china_holiday
from lib.adapter.database.db_transaction import create_transaction
from lib.tools.cache_decorator import use_cache
from lib.logger import create_logger
from .utils import clean_data_for_json

logger = create_logger('lib.tools.ashare_stock.calendar')

@use_cache(86400 * 7, use_db_cache=True)
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

global_china_holiday_cache_by_year: Dict[str, List[str]] = {}
def is_china_business_day(day: datetime) -> bool:
    """
    判断给定日期是否为中国交易日
    
    Args:
        day: 要判断的日期
        
    Returns:
        是否为交易日
    """
    global global_china_holiday_cache_by_year
    if day.weekday() >= 5:
        return False

    year_str = day.strftime("%Y")
    day_str = day.strftime("%Y-%m-%d")
    if year_str in global_china_holiday_cache_by_year:
        return day_str not in global_china_holiday_cache_by_year[year_str]

    with create_transaction() as db:
        cache_key = f"{year_str}_china_holiday"
        holiday_list = db.kv_store.get(f"{year_str}_china_holiday")
        if holiday_list is None:
            holiday_list = get_china_holiday(year_str)
            db.kv_store.set(cache_key, holiday_list)
            db.commit()
        global_china_holiday_cache_by_year[year_str] = holiday_list
        return day_str not in holiday_list


def is_china_business_time(time: datetime) -> bool:
    """
    判断给定时间是否为中国交易时间
    
    Args:
        time: 要判断的时间
        
    Returns:
        是否为交易时间
    """
    if time.hour < 9 or (time.hour == 9 and time.minute < 30):
        return False

    if time.hour > 15 or (time.hour == 15 and time.minute > 0):
        return False

    if not is_china_business_day(time):
        return False

    return True

LeGuLeGuIndicators = TypedDict("LeGuLeGuIndicators", {
    "pe": Optional[float], # 市盈率
    "pe_ttm": Optional[float], # 市盈率（TTM，Trailing Twelve Months，过去12个月滚动市盈率
    "pb": Optional[float], # 市净率
    "dv_ratio": Optional[float], # 股息率
    "dv_ttm": Optional[float], # 股息率（TTM，Trailing Twelve Months，过去12个月滚动股息率
    "ps": Optional[float], # 市销率
    "ps_ttm": Optional[float], # 市销率（TTM，Trailing Twelve Months，过去12个月滚动市销率
    "total_mv": Optional[float], # 总市值
})

# _cache_key_generator = 
# @use_cache(ttl_seconds=3600, use_db_cache=False)
def get_indicators_from_legulegu(symbol: str, date: Optional[datetime] = None) -> LeGuLeGuIndicators:
    """
    获取A股股票的市盈率（PE）及其他相关指标

    Args:
        symbol: 股票代码
        date: 查询日期，默认为当前日期
    
    Returns:
        市盈率（PE）等指标，如果获取失败则返回空字典
    """
    if date is None:
        date = datetime.now()

    is_curr_date = date.date() == datetime.now().date()

    if not is_china_business_day(date):
        logger.warning(f"日期 {date} 不是中国的交易日, 将获取之前最近的交易日数据")
        while not is_china_business_day(date):
            date -= timedelta(days=1)
    
    date_in_str = str(date.date())
    cache_exist = False
    with create_transaction() as db:
        cache_key = f"pe_and_etc_indicators_{symbol}"
        cache_exist = db.kv_store.has(cache_key)
        if cache_exist:
            cache_data_json = db.kv_store.get(cache_key)
            data_of_date = cache_data_json.get(date_in_str)
            if data_of_date:
                return data_of_date
            elif not is_curr_date:
                raise ValueError(f"{symbol} 在 {date_in_str} 的没有数据")

    df = ak.stock_a_indicator_lg(symbol=symbol)
    if df is not None and not df.empty:
        indicators_dict = {}
        for _, row in df.iterrows():
            date_str = str(row["trade_date"])
            indicators_dict[date_str] = {
                "pe": row.get("pe", None),
                "pe_ttm": row.get("pe_ttm", None),
                "pb": row.get("pb", None),
                "dv_ratio": row.get("dv_ratio", None),
                "dv_ttm": row.get("dv_ttm", None),
                "ps": row.get("ps", None),
                "ps_ttm": row.get("ps_ttm", None),
                "total_mv": row.get("total_mv", None),
            }
        # 存入数据库缓存
        with create_transaction() as db:
            cache_key = f"pe_and_etc_indicators_{symbol}"
            db.kv_store.set(cache_key, indicators_dict)
            db.commit()
        data_of_date = indicators_dict.get(date_in_str)
        if data_of_date:
            return data_of_date
        elif not is_curr_date:
            raise ValueError(f"{symbol} 在 {date_in_str} 没有数据")
    else:
        raise ValueError(f"stock_a_indicator_lg 获取数据失败，可能是股票代码 {symbol} 不存在或数据源异常")

CurrentPePbFromTencent = TypedDict("CurrentPePbFromTencent", {
    "pe": float, # 当前市盈率
    "pb": float, # 当前市净率
    "total_market_cap": float, # 当前总市值
})

@use_cache(ttl_seconds=86400, use_db_cache=True)
def get_current_pe_pb_from_tencent(symbol: str) -> Dict[str, float]:
    """
    获取当前A股股票的市盈率（PE）和市净率（PB）

    Args:
        symbol: 股票代码
    
    Returns:
        包含市盈率（PE）市净率（PB）和总市值的字典
    """
    snap_shot = fetch_realtime_stock_snapshot(symbol)
    return {
        'pe': float(snap_shot['pe_dynamic']),
        'pb': float(snap_shot['pb_ratio']),
        'total_market_cap': float(snap_shot['total_market_cap'])
    }
