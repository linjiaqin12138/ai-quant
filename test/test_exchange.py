import sys
sys.path.append('.')
from lib.dao.exchange import buy_at_market_price, sell_at_market_price, sell_at_price, add_trade_info
from lib.utils.logger import logger
# buy_at_market_price('ERN/USDT', amount=4.9, reason='TEST')
# sell_at_price('BTC/USDT', price=69000, amount=0.00138005, reason='REAL_TEST')
# sell_at_market_price('ETH/USDT', amount=0.0032776138970829235, reason='TEST')
# buy_at_market_price('ETH/USDT', spend=10, reason='TEST')
# add_trade_info('BTC/USDT', 'sell', 'TEST', {}, 69000, 0.00138005, 'limit')
# buy_at_price('POND/USDT', price=0.02401, amount=1002.29, reason='REAL_TEST')
