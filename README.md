# Dev
## 模块规范

## UT
单跑某个case并打印日志：`pytest -s test/test_exchange.py:test_cn_market_exchange_fetch_history`
也可以`pytest -s -k test_cn_market_exchange_fetch_history`, 但是这样pytest会遍历测试文件寻找测试case，会比较慢

## TODO
1. g4f导入的时候遇到 requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接。', None, 10054, None))
2. curl 'https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1&max_time=2024-11-27+09:00:05&t=1732671830052'   \
    -H 'x-app-id: bVBF4FyRTn5NJF5n'   \
    -H 'x-version: 1.0.0' | jq