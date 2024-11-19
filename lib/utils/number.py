from typing import List, Any
import math

def change_rate(before: float, after: float) -> float:
    return (after - before) / before

def get_total_assets(price: float, symbol: float, money: float) -> float:
    return symbol * price + money

def is_nan(num: float) -> bool:
    return math.isnan(num)

def mean(*args: List[Any]) -> Any:
    return sum(args) / len(args)

def remain_significant_digits(num: float, n: int) -> float:
    if num == 0:
        return 0
    
    # 获取数字的科学计数法表示
    sci_notation = f"{num:.{n-1}e}"
    
    # 分离指数和尾数
    mantissa, exponent = sci_notation.split('e')
    
    # 保留N位有效数字
    mantissa = float(mantissa)
    
    # 重新组合科学计数法表示
    result = f"{mantissa:.{n}g}e{exponent}"
    
    # 转换回浮点数
    return float(result)

