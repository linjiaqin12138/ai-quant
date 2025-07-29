from datetime import datetime, timedelta
import json
from textwrap import dedent, indent
from typing import Annotated, Dict, Literal, Optional
import typer

from lib.adapter.database.db_transaction import create_transaction
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.exchange.crypto_exchange import BinanceExchange
from lib.adapter.notification.push_plus import PushPlus
from lib.logger import logger
from lib.modules.news_proxy import news_proxy
from lib.modules.agent import get_agent
from lib.modules.agents.common import format_indicators, format_ohlcv_list, format_ohlcv_pattern
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade.crypto import crypto
from lib.modules.strategy.state import PersisitentState
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
        self.message_express = NotificationLogger(f"{symbol} Crypto Bot", PushPlus(template="markdown"))
        self.ask_for_technical_analysis = get_llm_direct_ask(
            system_prompt=dedent(f"""
            你是一位经验丰富的技术分析专家，擅长深入的技术分析。
            
            分析原则：
            1. **综合分析**: 结合价格走势、技术指标和K线形态进行综合判断
            2. **风险评估**: 务必评估当前市场风险，给出明确的风险提示

            ## 输出要求
            1. 提供详细的技术分析报告，包含：
                - 趋势分析（短期、中期）
                - 关键支撑和阻力位
                - 技术指标解读
                - K线形态分析（如果检测到）
                - 风险评估
            2. 给出明确的交易建议：
                - **买入**: 多个指标显示积极信号，风险可控
                - **卖出**: 多个指标显示负面信号，风险较高
                - **持有**: 信号不明确或处于关键位置
            3. 在报告末尾添加一个Markdown表格，总结关键要点：
                | 分析项目 | 状态 | 说明 |
                |----------|------|------|
                | 趋势方向 | 上升/下降/震荡 | 具体说明 |
                | 技术指标 | 积极/中性/消极 | 主要信号 |
                | K线形态 | 看涨/看跌/中性 | 形态说明 |
                | 风险等级 | 低/中/高 | 风险因素 |
                | 交易建议 | 买入/卖出/持有 | 建议理由 |
            """),
            llm=get_llm("paoluz", "gemini-2.5-flash")
        )
        self.ask_for_news_analysis = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是一位专业的金融新闻分析师，擅长为某个投资标的分析短时间内收集到的金融市场新闻信息，以及时做出投资建议。

            **报告要求：**
            - 使用中文撰写
            - 结构清晰，包含市场分析、风险提示、投资建议
            - 基于事实，客观专业
            - 重点关注对交易决策有影响的信息，判断有没有对投资标的有影响的事件，特别关注是否有黑天鹅事件，并在报告中明确指出

            请始终保持专业和客观的态度，提供有价值的分析内容。                 
            """
            )
        )
        self.operation_advice_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            # - 如果建议挂限价单，请明确说明可以在什么价位做多/做空，并给出建议的杠杆倍数
            system_prompt=dedent(
            f"""
            你是一位专业的加密货币交易顾问，擅长为用户提供基于市场数据和新闻分析的交易建议。

            ## 输出要求
            1. 明确给出做多/做空建议，以及是否继续加仓/减仓（多/空），并给出具体比例或数量
            2. 建议内容包括：
                - 当前建议方向（做多/做空/观望）
                - 如果现在已经有仓位，是否建议继续加仓或减仓（多/空），请说明加减仓比例或数量
                - 是否需要设置止盈或止损（请给出具体价格区间或触发条件）
                - 当前持仓是否需要调整（如全部平仓、部分平仓等）
                - 预计接下来一小时内的价格波动范围（请给出具体区间，如“预计在4.20~4.35之间波动”）
            3. 用简洁的Markdown格式输出，包含建议摘要和详细说明
            4. 严格根据技术分析和新闻分析内容进行判断，避免主观臆断
            """
            )
        )
        self.operation_proposal_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            根据操作建议和当前仓位信息，给出具体的操作方案。包括：
            1. 当前是否有未完成的限价单，如果有未完成的限价单，是否需要取消, 如果不需要取消，保持当前限价单，并结束
            2. 是否需要进行杠杠倍数调整，是的话请给出具体倍数
            3. 如果当前未开仓
                2.1 建议开仓方向（做多/做空）
                2.2 建议开仓数量（合约数量）
                2.3 使用限价单还是市价单开仓
                    2.3.1. 如果使用限价单，需指明价格, 需要观察限价单是否成交才能设置止盈止损
                    2.3.2. 如果使用市价单，可以顺便指明止盈止损
                2.4 开仓后建议止盈止损价格
            4. 如果当前已开仓
                3.1 判断是否需要加仓/减仓，加减多少
                3.2 判断是否有仓位止盈止损单
                    3.2 如果没有设置止盈止损单，是否设置止盈止损单，并给出具体价格
                    3.3 如果已经设置了止盈止损单，是否根据市场情况调整止盈止损价格
            5. 其它建议（如果有的话）

            注意：
            1. 请给出明确的操作建议，避免模糊不清的建议。请确保操作建议是基于当前市场情况和仓位信息的合理判断。
            2. 不可以同时双向布局，要么做空，要么做多，要么观望
            3. 止盈止损是针对整个仓位的，只能最多设置一次止盈，一次止损
            """
            )
        )
        self.operation_agent = get_agent(
            llm=get_llm("paoluz", "gemini-2.5-pro")
        )
        self.operation_agent.set_system_prompt(
            dedent(
                f"""
                    请根据操作说明，调用工具进行操作。
                    尽量采用市价单，防止限价单无法成交导致错过行情。
                """
            )
        )
        self.operation_agent.register_tool(self.create_order)
        self.operation_agent.register_tool(self.cancel_order)
        self.operation_agent.register_tool(self.set_leverage)

        plan_id = f"crypto_agent_{self.symbol}_{investment}"
        self.position_status = None
        self.state = PersisitentState(plan_id, {
            "free_balance": investment, # 可用余额
            "suspended_balance": 0, # 挂单冻结
            "leverage": 5, # 杠杆倍数
            "position_amount": 0, # 仓位数量
            "position_side": "none", # 当前仓位方向, LONG-多仓，SHORT-空仓
            "recent_limit_order_id": None, # 开仓限价单
            "recent_take_profit_order_id": None, # 止盈限价单
            "recent_stop_loss_order_id": None, # 止损限价单
        })
        
        # self.agent.register_tool()

    # def check_pending_orders(self):
    #     """
    #     检查当前是否有未resolve的挂单（限价单、止盈、止损等）。
    #     返回：True-有未resolve挂单，False-无
    #     """
    #     open_orders = self.binance.binance.fapiPrivateGetOpenOrders({"symbol": self.symbol})
    #     """[
    #         {
    #             "orderId": "29278155713",
    #             "symbol": "SUIUSDT",
    #             "status": "NEW",
    #             "clientOrderId": "x-xcKtGhcu6de7f31f3753daadb083ce",
    #             "price": "0",
    #             "avgPrice": "0",
    #             "origQty": "0",
    #             "executedQty": "0",
    #             "cumQuote": "0.0000000",
    #             "timeInForce": "GTC",
    #             "type": "STOP_MARKET",
    #             "reduceOnly": true,
    #             "closePosition": true,
    #             "side": "BUY",
    #             "positionSide": "BOTH",
    #             "stopPrice": "4.500000",
    #             "workingType": "CONTRACT_PRICE",
    #             "priceProtect": false,
    #             "origType": "STOP_MARKET",
    #             "priceMatch": "NONE",
    #             "selfTradePreventionMode": "EXPIRE_MAKER",
    #             "goodTillDate": "0",
    #             "time": "1753682466867",
    #             "updateTime": "1753682466867"
    #         },
    #         {
    #             "orderId": "29278075138",
    #             "symbol": "SUIUSDT",
    #             "status": "NEW",
    #             "clientOrderId": "x-xcKtGhcubfaff7e9bb1afceeeb524a",
    #             "price": "0",
    #             "avgPrice": "0",
    #             "origQty": "0",
    #             "executedQty": "0",
    #             "cumQuote": "0.0000000",
    #             "timeInForce": "GTC",
    #             "type": "TAKE_PROFIT_MARKET",
    #             "reduceOnly": true,
    #             "closePosition": true,
    #             "side": "BUY",
    #             "positionSide": "BOTH",
    #             "stopPrice": "4.230000",
    #             "workingType": "CONTRACT_PRICE",
    #             "priceProtect": false,
    #             "origType": "TAKE_PROFIT_MARKET",
    #             "priceMatch": "NONE",
    #             "selfTradePreventionMode": "EXPIRE_MAKER",
    #             "goodTillDate": "0",
    #             "time": "1753682351208",
    #             "updateTime": "1753682351208"
    #         }
    #         ]"""

    #     for order in open_orders:
    #         if order["status"] == "NEW":
    #             logger.info(f"未完成挂单: {json.dumps(order, indent=2)}")

    def fetch_ohlcv_history(self, interval: str, limit: int) -> str:
        """
        获取历史K线数据。
        参数：
            interval: K线周期，如"1m"、"5m"等
            limit: 返回数据的条数
        返回：OHLCV数据列表
        """
        # 示例实现，实际可根据Binance接口调整
        ohlcv = self.binance.binance.fetch_ohlcv(self.symbol, timeframe=interval, limit=limit)
        return str(ohlcv)


    def _get_cache(self, key: str) -> tuple[bool, str]:
        with create_transaction() as db:
            result = db.kv_store.get(key)
            if result:
                return True, result
            return False, None
        
    def _set_cache_and_return(self, key: str, value: str) -> str:
        with create_transaction() as db:
            db.kv_store.set(key, value)
            db.commit()
            return value

    def get_operation_proposal(self) -> str:
        cache_key = f"crypto_operation_proposal_{self.symbol}_{datetime.now().strftime('%Y-%m-%d_%H:00')}"
        cache_exist, value = self._get_cache(cache_key)
        if cache_exist:
            return value
        
        current_position_info_str = self.get_position_info()
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
        """
        多agent对未来1小时涨跌进行辩论，最后给出建议。
        """
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
            technical_report = self.get_technical_analysis_report('1h', 48)

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
    
    # @use_cache(3600, use_db_cache=True, key_generator=lambda args, _: f"{args['symbol']}_{str(args["from_time"])}")
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
        gushitong = news_proxy.get_news_from("gushitong", start=from_time)
        news_in_str = render_news_in_markdown_group_by_platform({
            "cointime": coin_time,
            "gushitong": gushitong
        })
        prompt = f"请分析以下从{from_time}开始的新闻，会不会对投资标的{self.symbol}产生影响？\n{news_in_str}"
        logger.debug(prompt)
        return self._set_cache_and_return(cache_key, self.ask_for_news_analysis(prompt))

    def get_technical_analysis_report(self, interval: str = '1h', limit: int = 40) -> str:
        # 为了使用上缓存，使用现货的symbol代替合约的symbol
        assert interval in ['1d', '1h', '15m'], "不支持的时间周期"
        curr_time = datetime.now().strftime('%Y-%m-%d_%H:00')
        cache_key = f"crypto_news_analysis_{self.symbol}_{interval}_{limit}_{curr_time}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value
            
        data = crypto.get_ohlcv_history(
            symbol=self.symbol.rstrip("USDT").rstrip("/") + '/USDT',
            frame=interval,
            limit=limit
        ).data

        # 根据interval构造单位
        if interval == '1d':
            unit = '天'
        elif interval == '1h':
            unit = '小时'
        elif interval == '15m':
            unit = '周期(15min)'
        
        user_prompt = f"过去{len(data)}{unit}的{interval}级别OHLCV数据如下:\n\n"
        user_prompt += format_ohlcv_list(data)
        ohlcv_patterns = format_ohlcv_pattern(data)
        if ohlcv_patterns:
            user_prompt += "\n\n检测到的K线形态：\n" + ohlcv_patterns
        user_prompt += "\n\n技术指标：\n" + format_indicators(data, ["sma", "macd", "rsi", "boll, atr"], 20, interval)
        user_prompt += f"\n\n请分析以上数据，对未来1{unit}的行情预测。"

        logger.debug(user_prompt)

        return self._set_cache_and_return(cache_key, self.ask_for_technical_analysis(user_prompt))

    def create_order(
            self, 
            order_type: Annotated[
                Literal["LIMIT", "MARKET", "STOP_MARKET", "TAKE_PROFIT_MARKET"], 
                """订单类型, 如LIMIT(限价单)、MARKET(市价单）、TAKE_PROFIT_MARKET(止盈平仓限价单), STOP_MARKET(止损平仓限单)"""
            ],
            order_side: Annotated[
                Literal["BUY", "SELL"], 
                dedent("""
                订单方向, 买入卖出
                    - 订单类型为限价单/市价单时，做多使用'BUY'，做空使用'SELL'
                    - 订单类型为止盈止损时，当前方向为做多时使用"SELL"，做空时使用"BUY"
                """)
            ],
            amount: Annotated[
                Optional[float], 
                "交易数量"
            ] = None,
            # postion_side: str = None,
            price: Annotated[
                Optional[float], 
                "限价单价格, 限价单LIMIT必填"
            ] = None,
            stop_price: Annotated[
                Optional[float], 
                "止盈止损价格, TAKE_PROFIT_MARKET和STOP_MARKET必填"
            ] = None,
            # reduce_only: bool = None,
            # close_position: Annotated[
            #     Optional[bool], 
            #     "是否平仓"
            # ] = None,
        ) -> Dict[str, str]:
        """
        创建订单函数。
        返回：订单ID或其它相关信息。
        """
        params = {}
        # if postion_side:
        #     params['positionSide'] = postion_side.upper() # 我们只支持BOTH
        if stop_price is not None:
            params['stopPrice'] = stop_price
        # if reduce_only is not None:
        #     params['reduceOnly'] = reduce_only
        # if close_position is not None:
        if order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
            params['closePosition'] = True
        
        result = self.binance.binance.create_order(
            symbol=self.symbol,
            type=order_type,
            side=order_side,
            amount=amount,
            price=price,
            params=params
        )['info']

        if order_type == 'LIMIT':
            if result['status'] == 'NEW':
                self.state.set("recent_limit_order_id", result['orderId'])
            if result['status'] == 'FILLED':
                self.state.set("recent_limit_order_id", None)
                self.state.set("free_balance", self.state.get("free_balance") - (float(result['executedQty']) * float(result['avgPrice']) / self.state.get("leverage")))
        if order_type == 'MARKET':
            if result['status'] == 'FILLED':
                self.state.set("recent_limit_order_id", None)
                self.state.set("free_balance", self.state.get("free_balance") - (float(result['executedQty']) * float(result['avgPrice']) / self.state.get("leverage")))
        if order_type == 'STOP_MARKET':
            self.state.set("recent_stop_loss_order_id", result['orderId'])
        if order_type == 'TAKE_PROFIT_MARKET':
            self.state.set("recent_take_profit_order_id", result['orderId'])
        
        return result

    def get_order(self, order_id: str) -> Dict[str, str]:
        raw_order = self.binance.binance.fetch_order(**{ 'symbol': self.symbol, 'id': order_id })['info']
        """
        {
            "orderId": "29276685412",              # 订单ID
            "symbol": "SUIUSDT",                   # 交易对
            "status": "NEW",                       # 订单状态
            "clientOrderId": "x-xcKtGhcuf5ca5812c869e01544a85d", # 客户端订单ID
            "price": "4.330000",                   # 限价单价格
            "avgPrice": "0.00",                    # 平均成交价
            "origQty": "15.0",                     # 原始委托数量
            "executedQty": "0.0",                  # 已成交数量
            "cumQty": "0.0",                       # 累计成交数量
            "cumQuote": "0.0000000",               # 累计成交金额
            "timeInForce": "GTC",                  # 有效方式（如GTC为一直有效）
            "type": "LIMIT",                       # 订单类型（限价单）
            "reduceOnly": false,                   # 仅减仓标志
            "closePosition": false,                # 是否全部平仓
            "side": "SELL",                        # 买卖方向
            "positionSide": "BOTH",                # 仓位方向（BOTH/SHORT/LONG）
            "stopPrice": "0.000000",               # 止损价格
            "workingType": "CONTRACT_PRICE",       # 触发类型
            "priceProtect": false,                 # 是否价格保护
            "origType": "LIMIT",                   # 原始订单类型
            "priceMatch": "NONE",                  # 价格匹配模式
            "selfTradePreventionMode": "EXPIRE_MAKER", # 自成交防止模式
            "goodTillDate": "0",                   # 有效截止日期
            "updateTime": "1753680586540"          # 更新时间（时间戳）
        }
        """
        logger.debug(f"获取订单信息: {json.dumps(raw_order, indent=2)}")
        return {
            'orderId': raw_order['orderId'],
            'status': raw_order['status'],
            "price": raw_order["price"],
            "type": raw_order['type'],
            "side": raw_order['side'],
            "positionSide": raw_order['positionSide'],
            "origQty": float(raw_order['origQty']),
            'avgPrice': float(raw_order['avgPrice']),
            "cumQty": float(raw_order.get('cumQty', 0)) if raw_order.get('cumQty', 0) else None, # 订单resolve后没有
            'executedQty': float(raw_order['executedQty']),
            'cumQuote': float(raw_order['cumQuote']),
            'reduceOnly': bool(raw_order['reduceOnly']),
            'closePosition': bool(raw_order['closePosition']),
            'stopPrice': float(raw_order['stopPrice']),
            'updateTime': int(raw_order['updateTime'])
        }


    def set_leverage(self, leverage: Annotated[int, "杠杆倍率"]) -> Dict[str, str]:
        """
        设置杠杆倍率
        """
        result = self.binance.binance.fapiPrivatePostLeverage({ 'symbol': self.symbol, 'leverage': leverage })
        self.state.set("leverage", leverage)
        return result

    def cancel_order(self, order_id: Annotated[str, "订单ID"]) -> Dict[str, str]:
        """
        取消订单。
        参数：
            order_id: 订单ID
        返回：取消结果信息。
        """

        result = self.binance.binance.cancel_order(symbol=self.symbol, id=order_id)
        for order_id_key in ["recent_limit_order_id", "recent_take_profit_order_id", "recent_stop_loss_order_id"]:
            if order_id == self.state.get(order_id_key):
                self.state.set(order_id_key, None)
        return result['info']

    def get_unresolved_order(self, order_key) -> Optional[Dict[str, str]]:
        """
        获取当前开仓限价单信息。
        """
        order_id = self.state.get(order_key)
        if not order_id:
            return None
        order = self.get_order(order_id)
        if order['status'] in ['FILLED', 'CANCELED', 'EXPIRED']:
            self.state.set(order_key, None)
            if order['status'] == 'FILLED':
                logger.info(f"订单已完成: {order}")
                if order_key == "recent_limit_order_id":
                    # self.state.set("position_amount", self.state.get("position_amount") + order['executedQty'])
                    self.state.set("free_balance", self.state.get("free_balance") - (order['executedQty'] * order['avgPrice'] / self.state.get("leverage")))
                else:
                    self.state.set("free_balance", self.state.get("free_balance") + (order['executedQty'] * order['avgPrice'] / self.state.get("leverage")))
            return None
        if order['status'] == 'NEW':
            return order
        
        logger.error("未知状态订单: %s", order)
        return None
    
    def get_position_info(self) -> str:
        """
        获取当前仓位信息，包括杠杆倍率、仓位水平等。
        返回：仓位信息结构体或字典。
        """
        rsp = self.binance.binance.fapiPrivateV2GetPositionRisk(params={ 'symbol': self.symbol })
        """
        [
            {
                "symbol": "SUIUSDT",                # 交易对名称
                "positionAmt": "-16.0",             # 持仓数量（正为多，负为空）
                "entryPrice": "4.2101",             # 开仓均价
                "breakEvenPrice": "4.20799495",     # 盈亏平衡价格
                "markPrice": "4.20890000",          # 当前标记价格
                "unRealizedProfit": "0.01920000",   # 未实现盈亏
                "liquidationPrice": "7.26039104",   # 强平价格
                "leverage": "5",                    # 杠杆倍数
                "maxNotionalValue": "20000000",     # 最大名义价值
                "marginType": "cross",              # 保证金模式（全仓/逐仓）
                "isolatedMargin": "0.00000000",     # 逐仓保证金数量
                "isAutoAddMargin": "false",         # 是否自动追加保证金
                "positionSide": "BOTH",             # 仓位方向（BOTH/SHORT/LONG）
                "notional": "-67.34240000",         # 持仓名义价值
                "isolatedWallet": "0",              # 逐仓钱包余额
                "updateTime": "1753602954123",      # 更新时间（时间戳）
                "isolated": false,                  # 是否逐仓
                "adlQuantile": "3"                  # ADL分位数
            }
        ]
        """
        info = next((item for item in rsp if item.get('positionSide', '').upper() == 'BOTH'), None)
        logger.debug(f"获取仓位信息: {json.dumps(info, indent=2)}")
        leverage = int(info.get('leverage', 5))
        position_amount = float(info.get('positionAmt', 0))
        self.state.set("position_amount", abs(position_amount))
        self.state.set("position_side", "long" if position_amount > 0 else "short" if position_amount < 0 else "none")
        self.state.set("leverage", leverage)
        free_balance = self.state.get('free_balance')

        curr_price = float(info['markPrice'])

        recent_limit_order = self.get_unresolved_order("recent_limit_order_id")
        if self.state.get("recent_limit_order_id") and not recent_limit_order:
            # position_info_str += "限价单已完成或取消。\n"
            logger.info(f"限价单已完成或取消: {self.state.get('recent_limit_order_id')}")

        position_info_str = ""
        recent_take_profit_order = self.get_unresolved_order("recent_take_profit_order_id")
        recent_stop_loss_order = self.get_unresolved_order("recent_stop_loss_order_id")

        if not info or position_amount == 0.0:
            position_info_str = (
                f"当前没有持仓。\n"
                f"当前杠杆倍数: {leverage}\n"
                f"可用: {free_balance}USDT\n"
                f"杠杆后余额: {free_balance * leverage}USDT\n"
                f"当前标记价格: {curr_price}\n"
                f"杠杆后余额最大可开多/开空合约数量: {free_balance * leverage / curr_price:2f}\n"
            )
            if recent_limit_order:
                position_info_str += (
                    f"当前有未完成开仓限价单: {recent_limit_order['orderId']}\n"
                    f"限价单价格: {recent_limit_order['price']}\n"
                    f"限价单委托数量: {recent_limit_order['origQty']}\n"
                    f"限价单状态: {recent_limit_order['status']}\n"
                    f"仓位方向: {recent_limit_order['side']}\n"
                )
            # 没有仓位但是又有未完成的止盈止损单，可能是之前的仓位触发止盈止损后的僵尸单
            if recent_take_profit_order:
                self.cancel_order(recent_take_profit_order['orderId'])
            if recent_stop_loss_order:
                self.cancel_order(recent_stop_loss_order['orderId'])
            return position_info_str
        

        position_info_str = (
            f"持仓数量: {info.get('positionAmt', '')}（正为多，负为空）\n"
            f"开仓均价: {info.get('entryPrice', '')}\n"
            f"盈亏平衡价格: {info.get('breakEvenPrice', '')}\n"
            f"当前标记价格: {curr_price}\n"
            f"未实现盈亏: {info.get('unRealizedProfit', '')}\n"
            f"强平价格: {info.get('liquidationPrice', '')}\n"
            f"当前杠杆倍数: {leverage}\n"
            # f"最大名义价值: {info.get('maxNotionalValue', '')}\n"
            f"保证金模式: 全仓\n"
            # f"逐仓保证金数量: {info.get('isolatedMargin', '')}\n"
            # f"是否自动追加保证金: {info.get('isAutoAddMargin', '')}\n"
            # f"仓位方向: {info.get('positionSide', '')}\n"
            f"持仓名义价值: {info.get('notional', '')}\n"
            # f"逐仓钱包余额: {info.get('isolatedWallet', '')}\n"
            # f"更新时间: {info.get('updateTime', '')}\n"
            # f"是否逐仓: {info.get('isolated', '')}\n"
            # f"ADL分位数: {info.get('adlQuantile', '')}"
            f"当前可用: {free_balance}USDT\n"
            f"杠杆后余额: {free_balance * leverage}USDT\n"
            f"杠杆后余额最大可继续{'开多' if position_amount > 0 else '开空'}合约数量: {free_balance * leverage / curr_price}\n"
            f"最大可反向{'开多' if position_amount < 0 else '开空'}合约数量: {free_balance * leverage / curr_price + abs(position_amount)}\n"
        )
        if recent_take_profit_order:
            position_info_str += (
                f"当前有未完成止盈平仓限价单: {recent_take_profit_order['orderId']}\n"
                # f"止盈限价单价格: {recent_take_profit_order['price']}\n"
                # f"止盈限价单委托数量: {recent_take_profit_order['origQty']}\n"
                # f"止盈限价单状态: {recent_take_profit_order['status']}\n"
                f"仓位方向: {recent_take_profit_order['side']}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止盈。\n"
            )
        if recent_stop_loss_order:
            position_info_str += (
                f"当前有未完成止损平仓限价单: {recent_stop_loss_order['orderId']}\n"
                # f"止损限价单价格: {recent_stop_loss_order['price']}\n"
                # f"止损限价单委托数量: {recent_stop_loss_order['origQty']}\n"
                # f"止损限价单状态: {recent_stop_loss_order['status']}\n"
                f"仓位方向: {recent_stop_loss_order['side']}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止损。\n"
            )
        position_info_str += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return position_info_str

    def run(self):
        try:
            proposal = self.get_operation_proposal()
            self.message_express.msg(proposal)
            operation_result = self.operation_agent.ask(proposal, tool_use=True)
            self.message_express.msg(operation_result)
            self.state.save()
        except Exception as e:
            self.message_express.msg(f"运行过程中发生错误: {str(e)}")
        finally:
            self.message_express.send()


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
        # agent.message_express.msg(agent.get_position_info())
        # agent.message_express.msg(agent.get_news_analysis_report(datetime.now() - timedelta(minutes=55)))
        # agent.message_express.msg(agent.get_technical_analysis_report())
        # agent.message_express.msg(agent.get_operation_advice())
        # agent.message_express.msg(agent.get_operation_proposal())
        # agent.message_express.send()
        # print(agent.create_order(
        #     order_type="LIMIT",
        #     order_side="SELL",
        #     amount=15,
        #     # postion_side="BOTH",
        #     price=4.2509
        #     # stop_price=4.5,
        #     # reduce_only=True,
        #     # close_position=True
        # ))
        # print(agent.get_operation_proposal())
        agent.run()
    except KeyboardInterrupt:
        print('Ctrl-C pressed – the request is still running in the daemon thread')
        exit(1)
    
    # print(agent.create_order(
    #     order_type="STOP_MARKET",
    #     order_side="BUY",
    #     # amount=15,
    #     # postion_side="BOTH",
    #     # price=4.2300,
    #     stop_price=4.5,
    #     # reduce_only=True,
    #     close_position=True
    # ))
    # print(agent.get_position_info())
    # print(
    #     json.dumps(
    #         agent.binance.binance.fapiPrivateGetOpenOrders({ "symbol": "SUIUSDT" }),
    #         indent=2
    #     )
    # )
    # [
    #     {
    #     "orderId": "29235756919",
    #     "symbol": "SUIUSDT",
    #     "status": "NEW",
    #     "clientOrderId": "android_KqG0DumNkfuNb3pce8pK",
    #     "price": "0",
    #     "avgPrice": "0",
    #     "origQty": "0",
    #     "executedQty": "0",
    #     "cumQuote": "0.0000000",
    #     "timeInForce": "GTE_GTC",
    #     "type": "TAKE_PROFIT_MARKET",
    #     "reduceOnly": true,
    #     "closePosition": true,
    #     "side": "SELL",
    #     "positionSide": "BOTH",
    #     "stopPrice": "4.339000",
    #     "workingType": "MARK_PRICE",
    #     "priceProtect": true,
    #     "origType": "TAKE_PROFIT_MARKET",
    #     "priceMatch": "NONE",
    #     "selfTradePreventionMode": "NONE",
    #     "goodTillDate": "0",
    #     "time": "1753634347888",
    #     "time": "1753634347888",
    #     "updateTime": "1753634347900"
    #     "updateTime": "1753634347900"
    #     },
    #     {
    #     "orderId": "29235756925",
    #     "orderId": "29235756925",
    #     "symbol": "SUIUSDT",
    #     "status": "NEW",
    #     "clientOrderId": "android_kGyqRg4vBDzKJgbtbUAN",
    #     "price": "0",
    #     "avgPrice": "0",
    #     "origQty": "0",
    #     "executedQty": "0",
    #     "cumQuote": "0.0000000",
    #     "timeInForce": "GTE_GTC",
    #     "type": "STOP_MARKET",
    #     "reduceOnly": true,
    #     "closePosition": true,
    #     "side": "SELL",
    #     "positionSide": "BOTH",
    #     "stopPrice": "4.210100",
    #     "workingType": "MARK_PRICE",
    #     "priceProtect": true,
    #     "origType": "STOP_MARKET",
    #     "priceMatch": "NONE",
    #     "selfTradePreventionMode": "NONE",
    #     "goodTillDate": "0",
    #     "time": "1753634347891",
    #     "updateTime": "1753634347902"
    #     }
    #     ]
    # acc = agent.binance.binance.fapiPrivateV2GetAccount()
    # print(acc)
    # print(acc['totalMaintMargin'])  # 0.64334970 维持保证金总额（所有持仓维持不被强平所需的最低保证金总和）
    # print(acc['totalWalletBalance'])  # 49.57185143 账户总余额（包括已实现盈亏，未实现盈亏未计入）
    # print(acc['totalUnrealizedProfit'])  # 0.05508000 所有持仓的未实现盈亏总和
    # print(acc['totalMarginBalance'])  # 49.62693143 保证金余额（= totalWalletBalance + totalUnrealizedProfit，实际可用来抵扣保证金的总额）
    # print(acc['totalPositionInitialMargin'])  # 12.86699400 所有持仓的初始保证金总额（开仓时冻结的保证金总和）
    # print(acc['totalOpenOrderInitialMargin'])  # 0.00000000 所有挂单的初始保证金总额（挂单冻结的保证金总和）
    # print(acc['totalCrossWalletBalance'])  # 49.57185143 全仓钱包余额（全仓模式下可用的总余额）
    # print(acc['totalCrossUnPnl'])  # 0.05508000 全仓未实现盈亏
    # print(acc['availableBalance'])  # 36.75993743 可用余额（可用于开新仓或提取的余额）
    # print(acc['maxWithdrawAmount'])  # 36.75993743 最大可提取金额（不影响当前持仓的情况下可提取的最大金额）
    
    # print(agent.create_order(
    #     order_type="LIMIT",
    #     order_side="BUY",
    #     amount=0.230,
    #     postion_side="LONG",
    #     price=39,
    #     stop_price=50

    # ))

if __name__ == "__main__":
    app()