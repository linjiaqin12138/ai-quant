# Dev
## 模块规范

## UT
单跑某个case并打印日志：`pytest -s test/test_exchange.py:test_cn_market_exchange_fetch_history`
也可以`pytest -s -k test_cn_market_exchange_fetch_history`, 但是这样pytest会遍历测试文件寻找测试case，会比较慢

## TODO
1. g4f导入的时候遇到   requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接。', None, 10054, None))