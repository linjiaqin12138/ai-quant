def change_rate(before: float, after: float) -> float:
    return (after - before) / before

def get_total_assets(price: float, coin: float, usdt: float) -> float:
    return coin * price + usdt