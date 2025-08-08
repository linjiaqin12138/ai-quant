#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股股票初步筛选工具
根据财务指标和技术指标筛选符合条件的股票

使用示例：
python stock_screener.py --min-price 5 --max-price 50 --min-pe 5 --max-pe 25 --min-roe 15
"""

import typer
import pandas as pd
from typing import Optional, List, Dict, Any

from lib.adapter.apis import fetch_realtime_stock_snapshot
from lib.tools.ashare_stock import (
    get_recent_financial_balance_sheet,
    get_recent_financial_profit_statement,
    get_recent_financial_cash_flow,
    get_ashare_stock_info,
    get_stock_list
)
from lib.logger import create_logger

logger = create_logger('stock_screener')

app = typer.Typer(help="A股股票筛选工具")

class StockScreener:
    """股票筛选器"""
    
    def __init__(self):
        self.filtered_stocks = []
        
    def get_stock_list(self) -> List[str]:
        """
        获取A股股票列表
        
        Returns:
            股票代码列表
        """
        try:
            
            # 获取沪深A股股票代码列表
            stock_list = []
            all_stocks = get_stock_list()
            # 获取沪市A股
            try:
                if all_stocks:
                    sh_codes = [stock['stock_code'] for stock in all_stocks if stock['stock_code'].startswith(('600', '601', '603', '605'))]
                    stock_list.extend(sh_codes)
                    logger.info(f"获取沪市A股 {len(sh_codes)} 只")
            except Exception as e:
                logger.warning(f"获取沪市股票列表失败: {e}")
            
            # 获取深市A股（包括中小板和创业板）
            try:
                # 获取所有A股，然后筛选深市的
                if all_stocks:
                    sz_codes = [stock['stock_code'] for stock in all_stocks if stock['stock_code'].startswith(('000', '001', '002', '003', '004', '300'))]
                    stock_list.extend(sz_codes)
                    logger.info(f"获取深市A股 {len(sz_codes)} 只")
            except Exception as e:
                logger.warning(f"获取深市股票列表失败: {e}")
                
            # 去重并排序
            stock_list = list(set(stock_list))
            stock_list.sort()
            
            logger.info(f"总共获取A股股票 {len(stock_list)} 只")
            return stock_list
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            # 返回一些常见的股票代码用于测试
            return [
                '000001', '000002', '000858', '002415', '002594',
                '600036', '600519', '600887', '000858', '002027'
            ]
    
    def calculate_roe(self, balance_sheet: Dict, profit_statement: Dict) -> Optional[float]:
        """
        计算净资产收益率(ROE)
        
        Args:
            balance_sheet: 资产负债表数据
            profit_statement: 利润表数据
            
        Returns:
            ROE值，计算失败返回None
        """
        try:
            # 获取净利润（归属于母公司）
            net_profit = None
            if profit_statement.get('data'):
                net_profit = profit_statement['data'].get('归属于母公司所有者的净利润')
                if net_profit is None:
                    net_profit = profit_statement['data'].get('净利润')
            
            # 获取股东权益
            equity = None
            if balance_sheet.get('data'):
                equity = balance_sheet['data'].get('归属于母公司股东权益合计')
                if equity is None:
                    equity = balance_sheet['data'].get('所有者权益合计')
            
            if net_profit is not None and equity is not None and equity != 0:
                roe = (float(net_profit) / float(equity)) * 100  # 转换为百分比
                return roe
            
            return None
            
        except Exception as e:
            logger.debug(f"计算ROE失败: {e}")
            return None
    
    def calculate_eps(self, profit_statement: Dict) -> Optional[float]:
        """
        计算每股收益(EPS)
        
        Args:
            profit_statement: 利润表数据
            
        Returns:
            EPS值，计算失败返回None
        """
        try:
            if profit_statement.get('data'):
                eps = profit_statement['data'].get('基本每股收益')
                if eps is not None:
                    return float(eps)
            return None
        except Exception as e:
            logger.debug(f"计算EPS失败: {e}")
            return None
    
    def get_historical_profit_data(self, stock_code: str, years: int = 3) -> List[Dict]:
        """
        获取历史多年利润数据
        
        Args:
            stock_code: 股票代码
            years: 获取年数
            
        Returns:
            历史利润数据列表，按年份降序排列
        """
        try:
            from lib.tools.ashare_stock import get_financial_profit_statement_history
            
            # 获取多年利润表数据
            profit_data = get_financial_profit_statement_history(stock_code)
            
            if not profit_data.get('data'):
                return []
            
            # 过滤年报数据（通常在报告期列中以12-31结尾）
            annual_data = []
            for item in profit_data['data']:
                report_date = item.get('报告日', item.get('REPORT_DATE', ''))
                if report_date and '12-31' in str(report_date):
                    annual_data.append(item)
            
            # 取最近几年的数据
            annual_data = annual_data[:years]
            
            result = []
            for item in annual_data:
                data = {
                    'report_date': item.get('报告日', item.get('REPORT_DATE')),
                    'net_profit': item.get('归属于母公司所有者的净利润', item.get('PARENT_NETPROFIT')),  # 归属于母公司净利润
                    'eps': item.get('基本每股收益', item.get('BASIC_EPS')),  # 基本每股收益
                    'revenue': item.get('营业收入', item.get('OPERATE_INCOME'))  # 营业收入
                }
                result.append(data)
            
            return result
            
        except Exception as e:
            logger.warning(f"获取股票 {stock_code} 历史数据失败: {e}")
            return []
    
    def calculate_profit_growth_rate(self, historical_data: List[Dict]) -> Optional[float]:
        """
        计算净利润增长率
        
        Args:
            historical_data: 历史利润数据
            
        Returns:
            年均净利润增长率（百分比），计算失败返回None
        """
        try:
            if len(historical_data) < 2:
                return None
            
            # 按年份排序（从旧到新）
            sorted_data = sorted(historical_data, key=lambda x: x['report_date'])
            
            growth_rates = []
            for i in range(1, len(sorted_data)):
                current = sorted_data[i]['net_profit']
                previous = sorted_data[i-1]['net_profit']
                
                if current is None or previous is None or previous == 0:
                    continue
                
                growth_rate = ((float(current) - float(previous)) / abs(float(previous))) * 100
                growth_rates.append(growth_rate)
            
            if not growth_rates:
                return None
            
            # 计算平均增长率
            avg_growth_rate = sum(growth_rates) / len(growth_rates)
            return avg_growth_rate
            
        except Exception as e:
            logger.debug(f"计算净利润增长率失败: {e}")
            return None
    
    def check_eps_consistency(self, historical_data: List[Dict], min_eps: float = 0.3) -> bool:
        """
        检查每股收益的稳定性
        
        Args:
            historical_data: 历史利润数据
            min_eps: 最低每股收益要求
            
        Returns:
            是否满足EPS稳定性要求
        """
        try:
            if len(historical_data) < 3:
                return False
            
            for data in historical_data:
                eps = data.get('eps')
                if eps is None or float(eps) < min_eps:
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"检查EPS稳定性失败: {e}")
            return False
    
    def calculate_debt_ratio(self, balance_sheet: Dict) -> Optional[float]:
        """
        计算资产负债率
        
        Args:
            balance_sheet: 资产负债表数据
            
        Returns:
            资产负债率，计算失败返回None
        """
        try:
            if balance_sheet.get('data'):
                total_liabilities = balance_sheet['data'].get('负债合计')
                total_assets = balance_sheet['data'].get('资产总计')
                
                if total_liabilities is not None and total_assets is not None and total_assets != 0:
                    debt_ratio = (float(total_liabilities) / float(total_assets)) * 100
                    return debt_ratio
            return None
        except Exception as e:
            logger.debug(f"计算资产负债率失败: {e}")
            return None
    
    def check_cash_flow_quality(self, cash_flow: Dict, profit_statement: Dict) -> bool:
        """
        检查现金流质量：经营活动现金流净额 > 净利润
        
        Args:
            cash_flow: 现金流量表数据
            profit_statement: 利润表数据
            
        Returns:
            现金流质量是否良好
        """
        try:
            operating_cash_flow = None
            if cash_flow.get('data'):
                operating_cash_flow = cash_flow['data'].get('经营活动产生的现金流量净额')
            
            net_profit = None
            if profit_statement.get('data'):
                net_profit = profit_statement['data'].get('净利润')
            
            if operating_cash_flow is not None and net_profit is not None:
                return float(operating_cash_flow) > float(net_profit)
            
            return False
        except Exception as e:
            logger.debug(f"检查现金流质量失败: {e}")
            return False
    
    def is_st_stock(self, stock_code: str) -> bool:
        """
        判断是否为ST股票
        
        Args:
            stock_code: 股票代码
            
        Returns:
            是否为ST股票
        """
        try:
            stock_info = get_ashare_stock_info(stock_code)
            stock_name = stock_info.get('stock_name', '')
            return 'ST' in stock_name.upper()
        except Exception as e:
            logger.debug(f"判断ST股票失败: {e}")
            return False
    
    def screen_stock(
        self,
        stock_code: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_pe: Optional[float] = None,
        max_pe: Optional[float] = None,
        min_pb: Optional[float] = None,
        max_pb: Optional[float] = None,
        min_roe: Optional[float] = None,
        min_eps: Optional[float] = None,
        max_debt_ratio: Optional[float] = None,
        require_good_cash_flow: bool = False,
        min_profit_growth: Optional[float] = None,
        require_eps_consistency: bool = False
    ) -> Dict[str, Any]:
        """
        筛选单只股票
        
        Args:
            stock_code: 股票代码
            min_price: 最低价格
            max_price: 最高价格
            min_pe: 最低市盈率
            max_pe: 最高市盈率
            min_pb: 最低市净率
            max_pb: 最高市净率
            min_roe: 最低ROE
            min_eps: 最低EPS
            max_debt_ratio: 最高资产负债率
            require_good_cash_flow: 是否要求良好现金流
            min_profit_growth: 最低净利润增长率（年均）
            require_eps_consistency: 是否要求EPS连续稳定
            
        Returns:
            筛选结果字典
        """
        result = {
            'stock_code': stock_code,
            'passed': False,
            'reason': [],
            'metrics': {}
        }
        
        try:
            # 跳过ST股票
            if self.is_st_stock(stock_code):
                result['reason'].append('ST股票')
                return result
            
            # 获取基本信息
            stock_info = get_ashare_stock_info(stock_code)
            result['stock_name'] = stock_info.get('stock_name', '未知')
            result['industry'] = stock_info.get('stock_business', '未知')
            
            # 获取实时PE、PB数据\
            stock_snapshot = fetch_realtime_stock_snapshot(stock_code)
            current_pe = float(stock_snapshot["pe_dynamic"])
            current_pb = float(stock_snapshot["pb_ratio"])
            current_price = float(stock_snapshot["latest_price"])

            result['metrics']['PE'] = current_pe
            result['metrics']['PB'] = current_pb
            
            # 价格筛选
            if min_price is not None or max_price is not None:
                if current_price is None:
                    result['reason'].append('无法获取当前价格')
                    return result
                if min_price is not None and current_price < min_price:
                    result['reason'].append(f'价格过低: {current_price}')
                    return result
                if max_price is not None and current_price > max_price:
                    result['reason'].append(f'价格过高: {current_price}')
                    return result
            
            # PE筛选
            if min_pe is not None or max_pe is not None:
                if current_pe is None or current_pe <= 0:
                    result['reason'].append('PE无效或负值')
                    return result
                if min_pe is not None and current_pe < min_pe:
                    result['reason'].append(f'PE过低: {current_pe:.2f}')
                    return result
                if max_pe is not None and current_pe > max_pe:
                    result['reason'].append(f'PE过高: {current_pe:.2f}')
                    return result
            
            # PB筛选
            if min_pb is not None or max_pb is not None:
                if current_pb is None or current_pb <= 0:
                    result['reason'].append('PB无效或负值')
                    return result
                if min_pb is not None and current_pb < min_pb:
                    result['reason'].append(f'PB过低: {current_pb:.2f}')
                    return result
                if max_pb is not None and current_pb > max_pb:
                    result['reason'].append(f'PB过高: {current_pb:.2f}')
                    return result
            
            # 获取财务数据
            balance_sheet = get_recent_financial_balance_sheet(stock_code)
            profit_statement = get_recent_financial_profit_statement(stock_code)
            cash_flow = get_recent_financial_cash_flow(stock_code)
            
            # ROE筛选
            if min_roe is not None:
                roe = self.calculate_roe(balance_sheet, profit_statement)
                result['metrics']['ROE'] = roe
                if roe is None:
                    result['reason'].append('无法计算ROE')
                    return result
                if roe < min_roe:
                    result['reason'].append(f'ROE过低: {roe:.2f}%')
                    return result
            
            # EPS筛选
            if min_eps is not None:
                eps = self.calculate_eps(profit_statement)
                result['metrics']['EPS'] = eps
                if eps is None:
                    result['reason'].append('无法获取EPS')
                    return result
                if eps < min_eps:
                    result['reason'].append(f'EPS过低: {eps:.2f}')
                    return result
            
            # 资产负债率筛选
            if max_debt_ratio is not None:
                debt_ratio = self.calculate_debt_ratio(balance_sheet)
                result['metrics']['债务率'] = debt_ratio
                if debt_ratio is None:
                    result['reason'].append('无法计算资产负债率')
                    return result
                if debt_ratio > max_debt_ratio:
                    result['reason'].append(f'资产负债率过高: {debt_ratio:.2f}%')
                    return result
            
            # 现金流质量筛选
            if require_good_cash_flow:
                cash_flow_good = self.check_cash_flow_quality(cash_flow, profit_statement)
                result['metrics']['现金流质量'] = '良好' if cash_flow_good else '一般'
                if not cash_flow_good:
                    result['reason'].append('现金流质量不佳')
                    return result
            
            # 净利润增长率筛选
            if min_profit_growth is not None or require_eps_consistency:
                historical_data = self.get_historical_profit_data(stock_code, years=3)
                
                if min_profit_growth is not None:
                    profit_growth = self.calculate_profit_growth_rate(historical_data)
                    result['metrics']['净利润增长率'] = profit_growth
                    if profit_growth is None:
                        result['reason'].append('无法计算净利润增长率')
                        return result
                    if profit_growth < min_profit_growth:
                        result['reason'].append(f'净利润增长率过低: {profit_growth:.2f}%')
                        return result
                
                if require_eps_consistency:
                    eps_consistent = self.check_eps_consistency(historical_data, min_eps or 0.3)
                    result['metrics']['EPS稳定性'] = '良好' if eps_consistent else '不稳定'
                    if not eps_consistent:
                        result['reason'].append('EPS连续性不符合要求')
                        return result
            
            # 通过所有筛选条件
            result['passed'] = True
            result['reason'] = ['通过筛选']
            
        except Exception as e:
            logger.error(f"筛选股票 {stock_code} 时出错: {e}")
            result['reason'].append(f'数据获取错误: {str(e)}')
        
        return result
    
    def screen_stocks(
        self,
        stock_codes: List[str],
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_pe: Optional[float] = None,
        max_pe: Optional[float] = None,
        min_pb: Optional[float] = None,
        max_pb: Optional[float] = None,
        min_roe: Optional[float] = None,
        min_eps: Optional[float] = None,
        max_debt_ratio: Optional[float] = None,
        require_good_cash_flow: bool = False,
        min_profit_growth: Optional[float] = None,
        require_eps_consistency: bool = False,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        批量筛选股票
        
        Args:
            stock_codes: 股票代码列表
            其他参数: 筛选条件
            max_results: 最大返回结果数
            
        Returns:
            筛选结果列表
        """
        results = []
        passed_count = 0
        
        logger.info(f"开始筛选 {len(stock_codes)} 只股票")
        
        for i, stock_code in enumerate(stock_codes):
            if passed_count >= max_results:
                logger.info(f"已达到最大结果数 {max_results}，停止筛选")
                break
                
            logger.info(f"正在筛选 {stock_code} ({i+1}/{len(stock_codes)})")
            
            result = self.screen_stock(
                stock_code=stock_code,
                min_price=min_price,
                max_price=max_price,
                min_pe=min_pe,
                max_pe=max_pe,
                min_pb=min_pb,
                max_pb=max_pb,
                min_roe=min_roe,
                min_eps=min_eps,
                max_debt_ratio=max_debt_ratio,
                require_good_cash_flow=require_good_cash_flow,
                min_profit_growth=min_profit_growth,
                require_eps_consistency=require_eps_consistency
            )
            
            if result['passed']:
                passed_count += 1
                logger.info(f"✓ {stock_code} 通过筛选")
            else:
                logger.debug(f"✗ {stock_code} 未通过筛选: {result['reason']}")
            
            results.append(result)
        
        logger.info(f"筛选完成，共 {passed_count} 只股票通过筛选")
        return results


@app.command()
def screen(
    min_price: Optional[float] = typer.Option(None, "--min-price", help="最低价格"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="最高价格"),
    min_pe: Optional[float] = typer.Option(None, "--min-pe", help="最低市盈率"),
    max_pe: Optional[float] = typer.Option(None, "--max-pe", help="最高市盈率"),
    min_pb: Optional[float] = typer.Option(None, "--min-pb", help="最低市净率"),
    max_pb: Optional[float] = typer.Option(None, "--max-pb", help="最高市净率"),
    min_roe: Optional[float] = typer.Option(None, "--min-roe", help="最低净资产收益率(%)"),
    min_eps: Optional[float] = typer.Option(None, "--min-eps", help="最低每股收益"),
    max_debt_ratio: Optional[float] = typer.Option(None, "--max-debt-ratio", help="最高资产负债率(%)"),
    require_good_cash_flow: bool = typer.Option(False, "--good-cash-flow", help="要求良好现金流"),
    min_profit_growth: Optional[float] = typer.Option(None, "--min-profit-growth", help="最低净利润增长率(%)"),
    require_eps_consistency: bool = typer.Option(False, "--eps-consistency", help="要求EPS连续稳定"),
    max_results: int = typer.Option(50, "--max-results", help="最大结果数"),
    test_mode: bool = typer.Option(False, "--test", help="测试模式（只使用少量股票）"),
    output_file: Optional[str] = typer.Option(None, "--output", help="输出文件路径")
):
    """
    筛选A股股票
    """
    screener = StockScreener()
    
    # 获取股票列表
    if test_mode:
        # 测试模式使用少量股票
        stock_codes = ['000001', '000002', '600036', '600519', '000858', '002415']
        logger.info("测试模式：使用预设股票列表")
    else:
        stock_codes = screener.get_stock_list()
    
    if not stock_codes:
        typer.echo("未获取到股票列表")
        return
    
    # 执行筛选
    results = screener.screen_stocks(
        stock_codes=stock_codes,
        min_price=min_price,
        max_price=max_price,
        min_pe=min_pe,
        max_pe=max_pe,
        min_pb=min_pb,
        max_pb=max_pb,
        min_roe=min_roe,
        min_eps=min_eps,
        max_debt_ratio=max_debt_ratio,
        require_good_cash_flow=require_good_cash_flow,
        min_profit_growth=min_profit_growth,
        require_eps_consistency=require_eps_consistency,
        max_results=max_results
    )
    
    # 筛选通过的股票
    passed_stocks = [r for r in results if r['passed']]
    
    # 显示结果
    typer.echo(f"\n筛选条件:")
    if min_price: typer.echo(f"  最低价格: {min_price}")
    if max_price: typer.echo(f"  最高价格: {max_price}")
    if min_pe: typer.echo(f"  最低PE: {min_pe}")
    if max_pe: typer.echo(f"  最高PE: {max_pe}")
    if min_pb: typer.echo(f"  最低PB: {min_pb}")
    if max_pb: typer.echo(f"  最高PB: {max_pb}")
    if min_roe: typer.echo(f"  最低ROE: {min_roe}%")
    if min_eps: typer.echo(f"  最低EPS: {min_eps}")
    if max_debt_ratio: typer.echo(f"  最高资产负债率: {max_debt_ratio}%")
    if require_good_cash_flow: typer.echo(f"  要求良好现金流: 是")
    if min_profit_growth: typer.echo(f"  最低净利润增长率: {min_profit_growth}%")
    if require_eps_consistency: typer.echo(f"  要求EPS连续稳定: 是")
    
    typer.echo(f"\n筛选结果: {len(passed_stocks)} 只股票通过筛选")
    typer.echo("-" * 80)
    
    for stock in passed_stocks:
        typer.echo(f"{stock['stock_code']} - {stock.get('stock_name', '未知')} ({stock.get('industry', '未知')})")
        metrics = stock.get('metrics', {})
        metric_strs = []
        for key, value in metrics.items():
            if isinstance(value, float):
                if key in ['PE', 'PB']:
                    metric_strs.append(f"{key}: {value:.2f}")
                elif key in ['ROE', '债务率', '净利润增长率']:
                    metric_strs.append(f"{key}: {value:.2f}%")
                else:
                    metric_strs.append(f"{key}: {value:.2f}")
            else:
                metric_strs.append(f"{key}: {value}")
        if metric_strs:
            typer.echo(f"  指标: {', '.join(metric_strs)}")
        typer.echo()
    
    # 输出到文件
    if output_file:
        df = pd.DataFrame(passed_stocks)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        typer.echo(f"结果已保存到: {output_file}")


if __name__ == "__main__":
    app()
