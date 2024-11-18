from datetime import datetime
import akshare as ak

from ...model import CnStockHistoryFrame
from ...utils.time import round_datetime_in_local_zone
from .api import ExchangeAPI
from ...model.common import OhlcvHistory, Order, OrderSide, OrderType, TradeTicker, Ohlcv

class CnMarketExchange(ExchangeAPI):
    """A股交易所API实现"""
    
    def _get_symbol_type(self, symbol: str) -> str:
        """
        判断证券代码类型
        
        Returns:
            str: 'stock' - A股股票
                 'etf' - ETF基金
                 'index' - 指数
        """
        if symbol.startswith(('51', '15', '16')):  # ETF基金
            return 'etf'
        elif symbol.startswith(('000001', '000300', '399001', '000016')):  # 主要指数
            return 'index'
        else:  # A股股票
            return 'stock'
    
    def fetch_ticker(self, symbol: str) -> TradeTicker:
        """获取实时行情"""
        symbol_type = self._get_symbol_type(symbol)
        
        if symbol_type == 'etf':
            df = ak.fund_etf_spot_em()  # ETF实时行情
        elif symbol_type == 'index':
            # TODO 这里是错误的，对于指数以后再研究
            df = ak.stock_zh_index_spot()  # 指数实时行情
        else:
            df = ak.stock_zh_a_spot_em()  # A股实时行情
            
        stock_data = df[df['代码'] == symbol].iloc[0]
        
        return TradeTicker(
            last=float(stock_data['最新价']),
        )

    def fetch_ohlcv(self, symbol: str, frame: CnStockHistoryFrame, start: datetime, end: datetime = datetime.now()) -> OhlcvHistory:
        """获取K线数据"""
        start = round_datetime_in_local_zone(start, frame)
        end = round_datetime_in_local_zone(end, frame)
        
        if end <= start:
            raise ValueError(f"结束时间({end})必须大于开始时间({start})")
            
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
                start_date=start.strftime('%Y%m%d'),
                end_date=end.strftime('%Y%m%d'),
                adjust="qfq"
            )
        elif symbol_type == 'index':
            if frame != '1d':
                raise ValueError(f"指数数据暂不支持 {frame} 周期，仅支持日线(1d)数据")
            df = ak.stock_zh_index_daily(symbol=symbol)
        else:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start.strftime('%Y%m%d'),
                end_date=end.strftime('%Y%m%d'),
                adjust="qfq"
            )
        
        # 转换数据格式
        ohlcv_data = []
        for _, row in df.iterrows():
            # 处理日期格式转换
            if isinstance(row['日期'], str):
                timestamp = datetime.strptime(row['日期'], '%Y-%m-%d')
            else:
                timestamp = datetime.combine(row['日期'], datetime.min.time())
            
            if timestamp < end:
                ohlcv_data.append(
                    Ohlcv(
                        round_datetime_in_local_zone(timestamp, tframe=frame),
                        float(row['开盘']),
                        float(row['最高']),
                        float(row['最低']),
                        float(row['收盘']),
                        float(row['成交量'])
                    )
                )
            
        return OhlcvHistory(symbol=symbol, frame=frame, data=ohlcv_data)

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None) -> Order:
        """创建订单（暂未实现）"""
        raise NotImplementedError("A股交易下单功能暂未实现")

cn_market = CnMarketExchange()