import akshare as ak
import pandas as pd
from typing import List, Dict
from lib.tools.cache_decorator import use_cache

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

@use_cache(
    86400 * 7,
    use_db_cache=True
)
def get_stock_list() -> List[Dict[str, str]]:
    """
    获取A股股票列表，使用二级缓存
    """
    df = ak.stock_info_a_code_name()
    result = []
    for _, row in df.iterrows():
        result.append({
            "stock_code": row["code"],
            "name": row["name"]
        })
    return result
