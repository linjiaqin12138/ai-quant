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