import re
import pandas as pd
from typing import Dict, Any
from lib.logger import create_logger
from lib.tools.cache_decorator import use_cache

logger = create_logger('lib.tools.ashare_stock.utils')

unknown_column_cache = set()

def colum_mapping_transform(latest_row: pd.Series, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    将pandas行数据按照映射表转换为字典
    
    Args:
        latest_row: pandas Series对象
        mapping: 列名映射字典
        
    Returns:
        转换后的字典数据
    """
    data = {}
    for origin_col in latest_row.index.to_list():
        if origin_col in mapping:
            chn_name = mapping[origin_col]
            value = latest_row[origin_col]
            # 判断是否为nan，如果是nan则跳过
            if pd.isna(value):
                continue
            # 判断是否为数字或浮点数
            if re.match(r"^\d+(\.\d+)?$", str(value)):
                data[chn_name] = float(value)
            else:
                data[chn_name] = str(value)
        else:
            if origin_col not in unknown_column_cache:
                logger.warning("字段：%s 未在映射中找到", origin_col)
                unknown_column_cache.add(origin_col)
    return data


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
