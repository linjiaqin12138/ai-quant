from datetime import datetime, timezone
import akshare as ak
import requests
import urllib3

from ...utils.retry import with_retry
from ...config import API_MAX_RETRY_TIMES
from ...model import CnStockHistoryFrame
from ...utils.time import dt_to_ts, round_datetime_in_local_zone
from ...model.common import OhlcvHistory, Order, OrderSide, OrderType, TradeTicker, Ohlcv
from .api import ExchangeAPI

class CnMarketExchange(ExchangeAPI):
    """A股交易所API实现"""
    
    def _get_symbol_type(self, symbol: str) -> str:
        """
        判断证券代码类型
        
        Returns:
            str: 'stock' - A股股票
                 'etf' - ETF基金
        """
        if symbol.startswith(('51', '15', '16')):  # ETF场内基金
            return 'etf'
        else:  # A股股票
            return 'stock'
    
    def fetch_ticker(self, symbol: str) -> TradeTicker:
        """获取实时行情"""
        symbol_type = self._get_symbol_type(symbol)
        
        if symbol_type == 'etf':
            df = ak.fund_etf_spot_em()  # ETF实时行情
        else:
            df = ak.stock_zh_a_spot_em()  # A股实时行情
            
        stock_data = df[df['代码'] == symbol].iloc[0]
        
        return TradeTicker(
            last=float(stock_data['最新价']),
        )

    @with_retry((requests.exceptions.ConnectionError, requests.exceptions.Timeout), API_MAX_RETRY_TIMES)
    def fetch_ohlcv(self, symbol: str, frame: CnStockHistoryFrame, start: datetime, end: datetime = datetime.now()) -> OhlcvHistory[CnStockHistoryFrame]:
        """获取K线数据"""
        rounded_start = round_datetime_in_local_zone(start, frame)
        rounded_end = round_datetime_in_local_zone(end, frame)
        
        if rounded_end <= rounded_start:
            raise ValueError(f"结束时间({rounded_end})必须大于开始时间({rounded_start})")
            
        period_map = {
            '1d': 'daily',
            '1w': 'weekly',
            '1M': 'monthly'
        }
        period = period_map.get(frame, 'daily')
        
        symbol_type = self._get_symbol_type(symbol)
        
        # 根据不同类型证券调用不同的API
        if symbol_type == 'etf':
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period=period,
                start_date=rounded_start.strftime('%Y%m%d'),
                end_date=rounded_end.strftime('%Y%m%d'),
                adjust="qfq"
            )
        else:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=rounded_start.strftime('%Y%m%d'),
                end_date=rounded_end.strftime('%Y%m%d'),
                adjust="qfq"
            )
        
        # 判断end是否超过UTC时间的早上7点半
        end_in_utc = datetime.fromtimestamp(dt_to_ts(end) / 1000, tz=timezone.utc)
        is_after_utc_730_in_a_day = frame == '1d' and end_in_utc.strftime('%Y-%m-%d') == end.strftime('%Y-%m-%d') and (end_in_utc.hour > 7 or (end_in_utc.hour ==7 and  end_in_utc.minute > 29))
        
        # 转换数据格式
        ohlcv_data = []
        for _, row in df.iterrows():
            # 处理日期格式转换
            if isinstance(row['日期'], str):
                timestamp = datetime.strptime(row['日期'], '%Y-%m-%d')
            else:
                timestamp = datetime.combine(row['日期'], datetime.min.time())
            
            ohlcv_obj = Ohlcv(
                round_datetime_in_local_zone(timestamp, tframe=frame),
                float(row['开盘']),
                float(row['最高']),
                float(row['最低']),
                float(row['收盘']),
                float(row['成交量'])
            )
            
            # 如果end超过UTC时间的早上7点半，直接添加最后一根K线
            if is_after_utc_730_in_a_day or timestamp < rounded_end:
                ohlcv_data.append(ohlcv_obj)
            
        return OhlcvHistory(symbol=symbol, frame=frame, data=ohlcv_data)

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None) -> Order:
        """创建订单（暂未实现）"""
        raise NotImplementedError("A股交易下单功能暂未实现")

cn_market = CnMarketExchange()