from typing import Dict, Any
from .financial_balance import get_recent_financial_balance_sheet
from .financial_profit import get_recent_financial_profit_statement
from .financial_cashflow import get_recent_financial_cash_flow
from .financial_indicators import get_recent_financial_indicators

def get_comprehensive_financial_data(symbol: str) -> Dict[str, Any]:
    """
    获取公司综合财务数据（资产负债表、利润表、现金流量表、财务指标）

    Args:
        symbol: 股票代码

    Returns:
        包含综合财务数据的字典
    """
    return {
        "symbol": symbol,
        "balance_sheet": get_recent_financial_balance_sheet(symbol),
        "profit_statement": get_recent_financial_profit_statement(symbol),
        "cash_flow": get_recent_financial_cash_flow(symbol),
        "financial_indicators": get_recent_financial_indicators(symbol),
    }
