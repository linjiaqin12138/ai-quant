# scripts/test_market_master.py
import sys
import os
from datetime import datetime, timedelta

# Add project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from lib.tools.market_master import MarketMaster, AshareContext, TradeContext
from lib.model import Ohlcv

# --- Mock Data ---
def create_mock_ohlcv(days=30) -> list[Ohlcv]:
    """Creates mock OHLCV data for the last 'days' days."""
    ohlcv_list = []
    start_date = datetime.now() - timedelta(days=days)
    price = 100.0
    volume = 1000
    for i in range(days):
        timestamp = start_date + timedelta(days=i)
        open_p = price + (i % 5 - 2) # Simulate some fluctuation
        high_p = open_p + 2
        low_p = open_p - 2
        close_p = low_p + (i % 3)
        volume += (i % 10 - 5) * 10
        ohlcv_list.append(Ohlcv(
            timestamp=timestamp,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=max(100, volume) # Ensure volume is positive
        ))
        price = close_p # Next day starts from previous close
    return ohlcv_list

mock_ashare_context = AshareContext(
    stock_code="836720",
    ohlcv_list=create_mock_ohlcv(60), # Need enough data for indicators
    account_info={'free': 10000.0, 'hold_amount': 500.0, 'hold_val': 500.0 * 3.5}, # hold 5 lots
    trade_history=[
        {'timestamp': int((datetime.now() - timedelta(days=5)).timestamp() * 1000), 'action': 'buy', 'buy_cost': 600.0, 'position_ratio': 0.2, 'price': 1200.0, 'summary': '初步建仓'},
        {'timestamp': int((datetime.now() - timedelta(days=2)).timestamp() * 1000), 'action': 'sell', 'sell_amount': 300.0, 'cost': 1000.0, 'position_ratio': 0.5, 'price': 1000, 'summary': '加仓'},
    ]
)

mock_crypto_context = TradeContext(
    coin_name="BTC",
    ohlcv_list=create_mock_ohlcv(60),
    account_info={'free': 5000.0, 'hold_amount': 0.1, 'hold_val': 0.1 * 60000.0},
    trade_history=[
        {'timestamp': int((datetime.now() - timedelta(days=10)).timestamp() * 1000), 'action': 'buy', 'buy_cost': 2500.0, 'position_ratio': 0.5, 'price': 1200.0, 'summary': '低位买入'},
        {'timestamp': int((datetime.now() - timedelta(days=3)).timestamp() * 1000), 'action': 'sell', 'sell_amount': 0.02, 'position_ratio': 0.3, 'price': 1000, 'summary': '部分止盈'}, # Missing cost for sell, ok
    ]
)

# --- Test Execution ---
if __name__ == "__main__":
    print("Initializing MarketMaster...")
    # Use default settings, potentially override LLM config if needed for testing
    # For real testing, you might want to mock the LLM call itself
    market_master = MarketMaster(
        # Example: Use a potentially faster/cheaper model for testing if available
        # llm_provider='your_test_provider',
        model='deepseek-v3',
        temperature=0.9
    )
    print("MarketMaster Initialized.")
    print("-" * 20)

    print("Testing A-Share Advice...")
    try:
        ashare_advice = market_master.give_ashare_trade_advice(mock_ashare_context)
        print("A-Share Advice Received:")
        print(f"  Action: {ashare_advice.action}")
        print(f"  Cost/Amount: {ashare_advice.buy_cost if ashare_advice.buy_cost else ashare_advice.sell_amount}")
        print(f"  Summary: {ashare_advice.summary}")
        # print(f"  Reason: {ashare_advice.reason}") # Reason can be long
    except Exception as e:
        print(f"Error getting A-Share advice: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 20)

    print("Testing Crypto Advice...")
    try:
        crypto_advice = market_master.give_crypto_trade_advice(mock_crypto_context)
        print("Crypto Advice Received:")
        print(f"  Action: {crypto_advice.action}")
        print(f"  Cost/Amount: {crypto_advice.buy_cost if crypto_advice.buy_cost else crypto_advice.sell_amount}")
        print(f"  Summary: {crypto_advice.summary}")
        # print(f"  Reason: {crypto_advice.reason}") # Reason can be long
    except Exception as e:
        print(f"Error getting Crypto advice: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 20)
    print("Test script finished.")
