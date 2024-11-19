from dataclasses import dataclass
from typing import Literal, TypedDict, Union, List

from ...utils.string import extract_json_string

from ...utils.list import map_by, filter_by

from ...utils.number import remain_significant_digits, is_nan

from ...model import Ohlcv
from ...utils.ohlcv import (
    atr_info, boll_info, macd_info, sam20_info, 
    sam5_info, rsi_info, stochastic_oscillator_info
)

GptAdviceDict = Union[
    TypedDict('GptAdviceDictBuy', {
        "action": Literal["buy"],
        "cost": float,
        "summary": str,
        "reason": str
    }),
    TypedDict('GptAdviceDictSell', {
        "action": Literal["sell"],
        "amount": float,
        "summary": str,
        "reason": str
    }),
    TypedDict('GptAdviceDictHold', {
        "action": Literal["hold"],
        "reason": str
    }),
]

class GptReplyNotValid(Exception):
    pass

def validate_gpt_advice(advice: str, max_cost: float, max_sell_amount: float) -> GptAdviceDict:
    try:
        advice_json = extract_json_string(advice)
        assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
        assert 'action' in advice_json, "GPT回复缺少'action'字段"
        assert advice_json['action'] in ['buy', 'sell', 'hold'], f"无效的action值: {advice_json['action']}, 必须是'buy'/'sell'/'hold'之一"
        assert 'reason' in advice_json, "GPT回复缺少'reason'字段"
        assert isinstance(advice_json['reason'], str), "'reason'字段必须是字符串类型"
        if advice_json['action'] != 'hold':
            assert 'summary' in advice_json, f"{advice_json['action']}操作必须包含'summary'字段"
        if advice_json['action'] == 'buy':
            assert 'cost' in advice_json, "买入操作缺少'cost'字段"
            assert isinstance(advice_json['cost'], float), "'cost'字段必须是浮点数类型"
            assert advice_json['cost'] > 0, "'cost'必须大于0"
            assert advice_json['cost'] <= max_cost, f"买入金额{advice_json['cost']}超过可用余额{max_cost}"
        elif advice_json['action'] == 'sell':   
            assert 'amount' in advice_json, "卖出操作缺少'amount'字段"
            assert isinstance(advice_json['amount'], float), "'amount'字段必须是浮点数类型"
            assert advice_json['amount'] > 0, "'amount'必须大于0"
            assert advice_json['amount'] <= max_sell_amount, f"卖出数量{advice_json['amount']}超过持仓数量{max_sell_amount}"
        return advice_json
    except Exception as err:
        raise GptReplyNotValid(err)
        
round_to_5 = lambda x: remain_significant_digits(x, 5)
map_by_round_to_5 = lambda x: map_by(x, round_to_5)

@dataclass(frozen=True)
class TechnicalIndicators:
    """技术指标数据类型定义"""
    sma5: List[float]            # 5日简单移动平均线
    sma20: List[float]           # 20日简单移动平均线
    rsi: List[float]             # 相对强弱指标
    bollinger_upper: List[float] # 布林带上轨
    bollinger_middle: List[float]# 布林带中轨
    bollinger_lower: List[float] # 布林带下轨
    macd_histogram: List[float]  # MACD柱状图
    is_macd_gold_cross: bool
    is_macd_dead_cross: bool
    is_macd_turn_good: bool
    is_macd_turn_bad: bool
    stoch_k: List[float]         # KDJ指标中的K值
    stoch_d: List[float]         # KDJ指标中的D值
    atr: List[float]             # 平均真实波幅

def calculate_technical_indicators(data: List[Ohlcv], data_length: int = 20) -> TechnicalIndicators:
    """
    计算常用技术指标
    
    Args:
        data: OHLCV数据列表
        data_length: 需要返回的数据长度，默认20个周期
        
    Returns:
        包含各项技术指标的字典，类型为TechnicalIndicators
    """
    # 计算各项指标
    sma_5 = map_by_round_to_5(sam5_info(data)['sma5'][-data_length:])
    sma_20 = map_by_round_to_5(sam20_info(data)['sma20'][-data_length:])
    rsi = map_by_round_to_5(rsi_info(data)['rsi'][-data_length:])
    
    boll = boll_info(data)
    bb_upper = map_by_round_to_5(boll['upperband'][-data_length:])
    bb_middle = map_by_round_to_5(boll['middleband'][-data_length:])
    bb_lower = map_by_round_to_5(boll['lowerband'][-data_length:])
    
    macd = macd_info(data)
    macd_histogram = map_by_round_to_5(filter_by(macd['macd_hist'][-data_length:], lambda x: not is_nan(x)))
    
    stochastic_oscillator = stochastic_oscillator_info(data)
    stoch_k = map_by_round_to_5(stochastic_oscillator['stoch_k'][-data_length:])
    stoch_d = map_by_round_to_5(stochastic_oscillator['stoch_d'][-data_length:])
    
    atr = map_by_round_to_5(atr_info(data)['atr'][-data_length:])

    return TechnicalIndicators(**{
        'sma5': sma_5,
        'sma20': sma_20,
        'rsi': rsi,
        'bollinger_upper': bb_upper,
        'bollinger_middle': bb_middle,
        'bollinger_lower': bb_lower,
        'is_macd_gold_cross': macd['is_gold_cross'],
        'is_macd_dead_cross': macd['is_dead_cross'],
        'is_macd_turn_good': macd['is_turn_good'],
        'is_macd_turn_bad': macd['is_turn_bad'],
        'macd_histogram': macd_histogram,
        'stoch_k': stoch_k,
        'stoch_d': stoch_d,
        'atr': atr
    })