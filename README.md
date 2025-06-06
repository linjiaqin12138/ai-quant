# 项目介绍
这是一个量化交易框架，支持
- AI股价/新闻分析并对当天交易做出决策
- 加密货币自动交易
- 自定义策略与策略回测

## 依赖安装

### 使用 Docker 安装
1. 确保已安装 Docker。
2. 构建 Docker 镜像：
   ```bash
   docker build -t ai-quant .
   ```
3. 运行容器并进入 Bash：
   ```bash
   docker run -it -v ~/quant.sqlite:/app/quant.sqlite ai-quant bash
   ```

### 正常安装步骤
1. 安装 Python 3.12 或更高版本。
2. 安装 TA-Lib C 库：
   ```bash
   wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
   tar -xzf ta-lib-0.6.4-src.tar.gz
   cd ta-lib-0.6.4/
   ./configure --prefix=/usr
   make
   sudo make install
   cd ..
   rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz
   ```
3. 安装 Python 依赖：
   ```bash
   pip install --no-cache-dir -r requirements.txt
   ```

4. 安装本项目:
    ```bash
    pip install -e .
    ```
## 运行配置
创建一个.env文件，在其中配置环境变量，支持哪些环境变量可以在[config.py](./lib/config.py)查看

下面是一个Example
```.env
LOG_LEVEL=INFO
CREATE_TABLE=TRUE
PUSH_PLUS_TOKEN='' # 用于接收定时任务消息结果
SILICONFLOW_TOKEN='' # 硅基流动模型token
PAOLUZ_AI_TOKEN='' # 某大模型供应商的token
BAI_CHUAN_TOKEN='' # 百川大模型
```
申请硅基流动大模型令牌：https://siliconflow.cn/

申请PAOLUZ大模型令牌：https://chatapi.nloli.xyz

如果想支持其它大模型的Provider也非常简单，参考[siliconflow.py](./lib/adapter/llm/siliconflow.py), 只要是兼容OPENAI的大模型，都可以简单替换其中的参数实现

## 运行示例
### AI交易策略回测
#### 测试AI从今年4月1日到4月30日，本金1000USDT，操盘比特币

```
python3 scripts/gpt_trade_v2.py BTC/USDT "比特币4月AI模拟交易测试" 1000 \
    --start-time 2025-04-01 --end-time 2025-04-30 \
    --advice-model-provider siliconflow --advice-model deepseek-ai/DeepSeek-V3 \
    --news-summary-model-provider siliconflow --news-summary-model THUDM/glm-4-9b-chat \
    --risk-prefer 风险喜好型 --strategy-prefer 高抛低吸，见好就收，分批买入
```
这个程序会模拟从4月1号到4月29号币安交易所的BTC/USDT历史走势，模拟4月1号到4月29号每一天根据当时的历史数据、新闻进行分析，并做出决策，这个过程中，每一天都要总结历史新闻并结合历史数据做出决策，一次会调用两次大模型接口，4月1号到4月29号一共29天，所以一共要调用29 * 2 = 58次大模型接口，速度会比较慢。最终运行结果如下：

运行结果：
<div align="center">
<img src="./docs/BTCUSDT_20250401_20250430.png" alt="比特币4月AI模拟交易测试" width="500" height="300">
</div>

其中灰色的线代表本金全部一次新投资的收益走势，蓝色的线代表AI操盘的收益，在这个图中，由于AI没有一次新投入所有本金，后面下跌的时候也没有加仓，币价总体呈上升趋势，所以收益没有跑赢梭哈的收益。

> 图片标题的地方显示中文不成功，忽略这个问题=-=

#### 测试AI从今年4月1日到4月30日，本金10000元，某支A股股票

```
python3 scripts/gpt_trade_v2.py 600588 "用友网络4月AI模拟交易测试" 10000 \
    --start-time 2025-04-01 --end-time 2025-04-30 \
    --advice-model-provider siliconflow --advice-model deepseek-ai/DeepSeek-V3 \
    --news-summary-model-provider siliconflow --news-summary-model THUDM/glm-4-9b-chat \
    --risk-prefer 稳健型 --strategy-prefer 跟进利好消息分批买入
```
<div align="center">
<img src="./docs/600588_20250401_20250430.png" alt="比特币4月AI模拟交易测试" width="500" height="300">
</div>