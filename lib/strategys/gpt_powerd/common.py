from typing import Literal, TypedDict, Union

from ...utils.string import extract_json_string

from ...utils.list import map_by

from ...utils.number import remain_significant_digits

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