import os
import ccxt

exchange = ccxt.binance({
  'apiKey': os.environ.get('API_KEY'),
  'secret': os.environ.get('SECRET_KEY')
})