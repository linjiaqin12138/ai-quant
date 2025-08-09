from datetime import datetime, timedelta
import traceback
from textwrap import dedent, indent
from flask import json
import typer


from lib.adapter.database.db_transaction import create_transaction
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.exchange.crypto_exchange import BinanceExchange
from lib.adapter.notification.push_plus import PushPlus
from lib.logger import logger
from lib.modules.crypto_futures.binance_futures_operations import BinanceFuturesOperator
from lib.modules.crypto_futures.future_position_manager import FuturesPositionStateManager
from lib.modules.crypto_futures.model import FuturesOrder
from lib.modules.crypto_futures.operate_agent import FuturesOperationAgent
from lib.modules.news_proxy import news_proxy
from lib.modules.agents.common import format_indicators, format_ohlcv_list, format_ohlcv_pattern
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade.crypto import crypto
from lib.modules.trade.crypto import crypto
from lib.utils.news import render_news_in_markdown_group_by_platform
import threading

app = typer.Typer()

class CryptoAgent:

    def __init__(
            self,
            symbol: str,
            investment: float = 1000.0
        ):
        self.binance = BinanceExchange(future_mode=True)
        self.symbol = symbol
        self.futures_operator = BinanceFuturesOperator(symbol)
        self.futures_position_manager = FuturesPositionStateManager(
            position_id=f"crypto_agent_{self.symbol}_{investment}",
            initial_balance=investment,
            futures_opeator=self.futures_operator
        )

        self.message_express = NotificationLogger(f"{symbol} Crypto Bot", PushPlus(template="markdown"))
        self.ask_for_technical_analysis = get_llm_direct_ask(
            system_prompt=dedent(f"""
            你是一位经验丰富的技术分析专家，擅长深入的技术分析。
            
            分析原则：
            1. **综合分析**: 结合价格走势、技术指标和K线形态进行综合判断
            2. **风险评估**: 务必评估当前市场风险，给出明确的风险提示
            3. **多时间周期**: 分析短期(1小时)、中期(1天)的趋势一致性
            4. **量价关系**: 关注成交量与价格变化的配合度

            ## 输出要求
            1. 提供详细的技术分析报告，包含：
                - 趋势分析（短期=1小时，中期=1天，并分析趋势一致性）
                - 关键支撑和阻力位（标注具体价格区间）
                - 技术指标解读（SMA、MACD、RSI、BOLL、ATR等，重点关注背离信号）
                - K线形态分析（如检测到主要形态则列出，否则说明"无明显K线形态"）
                - 成交量分析（量价配合度）
                - 风险评估（具体风险点和概率评估）
            2. 给出明确的交易建议和可信度：
                - **强烈买入**: 多个指标强烈看涨，可信度90%以上
                - **买入**: 多个指标显示积极信号，可信度70-90%
                - **观望**: 信号不明确或处于关键位置，可信度50-70%
                - **卖出**: 多个指标显示负面信号，可信度70-90%
                - **强烈卖出**: 多个指标强烈看跌，可信度90%以上
            3. 在报告末尾添加一个Markdown表格，总结关键要点：
                | 时间周期 | 分析项目 | 状态 | 说明 | 可信度 |
                |----------|----------|------|------|--------|
                | 短期/中期 | 趋势方向 | 上升/下降/震荡 | 具体说明 | 高/中/低 |
                | 短期/中期 | 技术指标 | 积极/中性/消极 | 主要信号 | 高/中/低 |
                | 短期/中期 | K线形态 | 看涨/看跌/中性 | 形态说明 | 高/中/低 |
                | - | 风险等级 | 低/中/高 | 风险因素 | - |
                | - | 交易建议 | 强烈买入/买入/观望/卖出/强烈卖出 | 建议理由 | 可信度% |
            """),
            llm=get_llm("paoluz", "gemini-2.5-flash")
        )
        self.ask_for_news_analysis = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是一位专业的金融新闻分析师，擅长为特定投资标的分析金融市场新闻信息。

            **分析重点：**
            1. **影响程度分级**: 将新闻按对{self.symbol}的影响程度分为：重大影响、中等影响、轻微影响、无影响
            2. **时效性分析**: 区分短期影响(1-24小时)、中期影响(1-7天)、长期影响(1个月以上)
            3. **黑天鹅识别**: 特别关注可能引起剧烈波动的突发事件

            **报告要求：**
            - 使用中文撰写，结构清晰
            - 按影响程度排序新闻事件
            - 明确标注是否存在黑天鹅事件
            - 给出市场情绪评分(1-10，1为极度恐慌，10为极度乐观)
            - 提供具体的短期价格影响预测(涨跌幅度范围)

            **输出格式：**
            1. 新闻摘要(按影响程度分级)
            2. 黑天鹅事件预警(如有)
            3. 市场情绪评估
            4. 短期影响预测
            5. 投资建议

            请始终保持专业和客观的态度，基于事实进行分析。                 
            """
            )
        )
        self.operation_advice_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是一位专业的加密货币交易顾问，根据技术分析和新闻分析提供精确的交易建议。

            ## 决策框架
            1. **信号权重**: 技术分析70%，新闻分析30%
            2. **风险控制**: 必须考虑止盈止损设置
            3. **仓位管理**: 根据信号强度决定仓位大小
            4. **时机选择**: 明确入场和出场时机

            ## 输出要求
            1. **明确方向建议**:
                - 强烈做多/做多/观望/做空/强烈做空
                - 信号强度评分(1-10分)
                - 建议仓位比例(如：满仓、7成仓、5成仓、轻仓)
            
            2. **仓位操作建议**:
                - 如已有仓位：加仓/减仓/平仓的具体比例
                - 如无仓位：建议开仓比例和分批策略
            
            3. **风险管理**:
                - 止盈位设置(具体价格区间)
                - 止损位设置(具体价格区间)
                - 最大可承受亏损比例
            
            4. **时间预测**:
                - 接下来1小时价格波动区间
                - 关键观察时间点
                - 信号失效的条件
            
            5. **操作优先级**:
                - 立即执行/等待确认/观望等待
                - 市价单/限价单建议
            
            ## 输出格式
            使用以下结构化格式：
            
            ### 交易信号
            - **方向**: [强烈做多/做多/观望/做空/强烈做空]
            - **信号强度**: [X/10分]
            - **建议仓位**: [具体比例]
            
            ### 具体操作
            - **当前仓位处理**: [具体操作]
            - **新仓建议**: [具体建议]
            - **执行方式**: [市价/限价，具体价格]
            
            ### 风险管理
            - **止盈**: [价格区间]
            - **止损**: [价格区间]
            - **最大风险**: [百分比]
            
            ### 时间预测
            - **1小时目标区间**: [价格范围]
            - **关键时点**: [具体时间]
            
            严格基于技术分析和新闻分析内容，避免主观臆断。
            """
            )
        )
        self.operation_proposal_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是交易执行专家，根据操作建议和当前仓位制定具体可执行的操作方案。

            ## 分析步骤
            1. **现状分析**: 详细分析当前仓位、挂单、风险状况
            2. **目标确定**: 根据操作建议确定目标仓位状态
            3. **路径规划**: 制定从现状到目标的具体执行步骤
            4. **风险评估**: 评估每个操作的风险和可能结果

            ## 输出格式
            ### 1. 现状分析
            - 当前仓位状况总结
            - 未完成订单分析
            - 风险敞口评估

            ### 2. 操作目标
            - 目标仓位方向和大小
            - 目标杠杆倍数
            - 目标止盈止损设置

            ### 3. 执行计划（按顺序）
            **步骤1**: [具体操作]
            - 操作类型: [取消订单/调整杠杆/开仓/平仓/设置止损止盈]
            - 具体参数: [订单类型、价格、数量等]
            - 执行理由: [为什么这样操作]
            - 风险提示: [可能的风险]

            **步骤2**: [下一步操作]
            ...

            ### 4. 风险控制
            - 最大亏损预估
            - 紧急处理预案
            - 执行过程监控要点

            ### 5. 执行建议
            - 推荐执行时机
            - 订单类型选择理由
            - 需要人工确认的环节

            ## 重要约束
            1. 不能同时做多做空
            2. 操作顺序必须正确（先取消冲突订单，再执行新操作）
            3. 加仓数量不得超过“杠杆后余额最大可继续加仓开多/开空合约数量”
            4. 止盈止损只能各设置一次
            5. 必须考虑限价单可能不成交的情况
            6. 每个操作都要有明确的风险评估

            请确保方案具体可执行，避免模糊指令。
            """
            )
        )
        self.operation_agent = FuturesOperationAgent(
            llm=get_llm("paoluz", "gemini-2.5-pro"),
            futures_operator=self.futures_operator,
            futures_position_manager=self.futures_position_manager
        )

    def _get_cache(self, key: str) -> tuple[bool, str]:
        with create_transaction() as db:
            result = db.kv_store.get(key)
            if result:
                return True, result
            return False, None
        
    def _set_cache_and_return(self, key: str, value: str) -> str:
        if not value:
            return value 
        with create_transaction() as db:
            db.kv_store.set(key, value)
            db.commit()
            return value

    def get_operation_proposal(self) -> str:
        cache_key = f"crypto_operation_proposal_{self.symbol}_{datetime.now().strftime('%Y-%m-%d_%H:00')}"
        cache_exist, value = self._get_cache(cache_key)
        if cache_exist:
            return value
        
        current_position_info_str = self.futures_position_manager.get_position_info_text()
        self.message_express.msg(current_position_info_str)
        operation_advice = self.get_operation_advice()
        self.message_express.msg(operation_advice)
        
        prompt = "请根据以下信息给出操作方案：\n"
        prompt += f"当前仓位信息：\n {indent(current_position_info_str, ' ' * 2)}\n"
        prompt += f"当前操作建议：\n {indent(operation_advice, ' ' * 2)}\n"
        return self._set_cache_and_return(
            cache_key,
            self.operation_proposal_ask(prompt)
        )

    def get_operation_advice(self) -> str:
        cache_key = f"crypto_operation_advice_{self.symbol}_{datetime.now().strftime('%Y-%m-%d_%H:00')}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value
        
        news_report = None
        technical_report = None

        def fetch_news():
            nonlocal news_report
            news_report = self.get_news_analysis_report(from_time=(datetime.now() - timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0))

        def fetch_technical():
            nonlocal technical_report
            technical_report = self.get_technical_analysis_report()

        t1 = threading.Thread(target=fetch_news)
        t2 = threading.Thread(target=fetch_technical)
        t1.start()
        t1.join()
        t2.start()
        t2.join()
        
        assert news_report is not None, "新闻分析报告不能为空"
        assert technical_report is not None, "技术分析报告不能为空"

        self.message_express.msg(news_report)
        self.message_express.msg(technical_report)

        curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        curr_price = self.binance.fetch_ticker(self.symbol).last

        prompt = f"新闻分析:\n{news_report}\n\n技术分析:\n{technical_report}\n"
        prompt += f"当前时间: {curr_time}\n"
        prompt += f"当前价格: {curr_price}\n\n"
        prompt += "请根据以上信息，预测未来一小时涨跌并给出操作建议"

        return self._set_cache_and_return(cache_key, self.operation_advice_ask(prompt))
    
    def get_news_analysis_report(self, from_time: datetime) -> str:
        """
        获取新闻分析报告。
        参数：
            from_time: 分析的起始时间
        返回：新闻分析报告字符串
        """
        cache_key = f"crypto_news_analysis_{self.symbol}_{from_time.strftime('%Y-%m-%d_%H:00')}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value

        coin_time = news_proxy.get_news_from("cointime", start=from_time)
        if len(coin_time) == 0:
            return "过去一小时无需要关注的新闻"
        news_in_str = render_news_in_markdown_group_by_platform({
            "cointime": coin_time
        })
        prompt = f"请分析以下从{from_time}开始的新闻，会不会对投资标的{self.symbol}产生影响？\n{news_in_str}"
        logger.debug(prompt)
        return self._set_cache_and_return(cache_key, self.ask_for_news_analysis(prompt))

    def get_technical_analysis_report(self) -> str:
        # 为了使用上缓存，使用现货的symbol代替合约的symbol
        # assert interval in ['1d', '1h', '15m'], "不支持的时间周期"
        symbol = self.symbol.rstrip("USDT").rstrip("/") + '/USDT'
        curr_time = datetime.now().strftime('%Y-%m-%d_%H:00')
        cache_key = f"crypto_news_analysis_{self.symbol}_1h_48_{curr_time}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value
            
        data = crypto.get_ohlcv_history(
            symbol=symbol,
            frame="1h",
            limit=48
        ).data

        user_prompt = f"请分析以下{self.symbol}的小时级别OHLCV数据\n"
        user_prompt += f"过去{len(data)}小时级别OHLCV数据如下:\n\n"
        user_prompt += format_ohlcv_list(data)
        ohlcv_patterns = format_ohlcv_pattern(data)
        if ohlcv_patterns:
            user_prompt += "\n\n检测到的K线形态：\n" + ohlcv_patterns
        user_prompt += "\n\n技术指标：\n" + format_indicators(data, ["sma", "macd", "rsi", "boll", "atr"], 20, "1h")

        user_prompt += "\n\n以下是过去4小时15min级别的OHLCV数据， 用于更精确的短期趋势分析。"
        data = crypto.get_ohlcv_history(
            symbol=symbol,
            frame="15m",
            limit=16
        ).data
        user_prompt += format_ohlcv_list(data)

        user_prompt += f"\n\n请分析以上数据，对未来1小时的行情预测。"

        logger.debug(user_prompt)

        return self._set_cache_and_return(cache_key, self.ask_for_technical_analysis(user_prompt))

    def listen_order_change_callback(self, order: FuturesOrder):
        self.message_express.msg(f"订单状态变更: {json.dumps(order.raw, indent=2)}")
        self.message_express.send()
    
    def run(self):
        try:
            proposal = self.get_operation_proposal()
            self.message_express.msg(proposal)
            operation_result = self.operation_agent.ask(proposal)
            self.message_express.msg(operation_result)
            self.futures_position_manager.save()
        except Exception as e:
            self.message_express.msg(f"运行过程中发生错误: {str(e)} {traceback.format_exc()}")
        finally:
            self.message_express.send()
            # wait_until = (datetime.now() + timedelta(minutes=60)).replace(second=0, microsecond=0, minute=0)
            # stopper = self.futures_position_manager.listen_for_limit_order_change(
            #     self.listen_order_change_callback
            # )
            # self.operation_agent.wait_for_orders_resolve(
            #     wait_until
            # )
            # self.futures_position_manager._order_listening_thread.join()
            # stopper()
            # self.futures_position_manager.save()


@app.command()
def main():
    """
    运行加密货币智能仓位管理Agent。
    """
    try:
        agent = CryptoAgent(
            symbol="SUIUSDT",
            investment=50,  # 初始投资金额
        )
        
        agent.run()
    except KeyboardInterrupt:
        print('Ctrl-C pressed – the request is still running in the daemon thread')
        exit(1)
    

if __name__ == "__main__":
    app()