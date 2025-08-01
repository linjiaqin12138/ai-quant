
import akshare as ak
from typing import List, Dict, Any, Literal, Optional, TypedDict
import pandas as pd
from datetime import datetime, time, timedelta

from lib.adapter.apis import fetch_realtime_stock_snapshot, get_china_holiday
from lib.adapter.database.db_transaction import create_transaction
from lib.model import NewsInfo
from lib.utils.string import hash_str
from lib.tools.cache_decorator import use_cache
from lib.logger import create_logger
from lib.utils.symbol import determine_exchange, is_etf

logger = create_logger('lib.tools.ashare_stock')

AShareStockInfo = TypedDict('AShareStockInfo', {
    'stock_type': Literal["ETF", "股票"],
    'stock_name': str,
    'stock_business': str,
    'exchange': str,
})

@use_cache(
    86400 * 7,
    use_db_cache=True,
    serializer=lambda df: df.to_json(orient="records", force_ascii=False),
    deserializer=lambda x: pd.read_json(x, orient="records"),
)
def get_fund_list() -> pd.DataFrame:
    """
    获取ETF基金列表，使用二级缓存
    """
    # 从 akshare 获取数据
    return ak.fund_name_em()


@use_cache(86400 * 30, use_db_cache=True)
def get_ashare_stock_info(symbol: str) -> AShareStockInfo:
    """
    获取A股股票或ETF的基本信息，使用二级缓存
    """
    result: AShareStockInfo = {}
    if is_etf(symbol):
        df = get_fund_list()  # 使用缓存的基金列表
        result["stock_type"] = "ETF"
        result["stock_name"] = df["基金简称"].loc[df["基金代码"] == symbol].iloc[0]
        result["stock_business"] = "未知"
    else:
        df = ak.stock_individual_info_em(symbol)
        result["stock_type"] = "股票"
        result["stock_name"] = df["value"].loc[df["item"] == "股票简称"].iloc[0]
        result["stock_business"] = df["value"].loc[df["item"] == "行业"].iloc[0]
        result["exchange"] = determine_exchange(symbol)
    return result


# 不适用数据库 Data too long for column 'context' at row 1
@use_cache(
    86400, 
    use_db_cache=True,
    serializer=lambda l: [x.to_dict() for x in l],
    deserializer=lambda l: [NewsInfo.from_dict(x) for x in l],
)
def get_stock_news(symbol: str) -> List[NewsInfo]:
    """
    获取A股股票的新闻数据，使用数据库缓存
    
    Args:
        symbol: 股票代码
    
    Returns:
        NewsInfo对象列表，按时间倒序排列
    """
    # 从 akshare 获取数据
    news_df = ak.stock_news_em(symbol=symbol)
    news_df["发布时间"] = pd.to_datetime(news_df["发布时间"])
    
    news_info_list: List[NewsInfo] = []

    for _, row in news_df.iterrows():
        news_info = NewsInfo(
            title=row["新闻标题"],
            timestamp=row["发布时间"],
            description=row["新闻内容"],
            news_id=hash_str(row["新闻标题"]),
            url=row["新闻链接"],
            platform="eastmoney",
        )
        news_info_list.append(news_info)

    return news_info_list

def get_stock_news_during(symbol: str, from_time: datetime, end_time: datetime = datetime.now()) -> List[NewsInfo]:
    """
    获取指定时间范围内的A股股票新闻数据
    
    Args:
        symbol: 股票代码
        from_time: 起始时间
        end_time: 结束时间
    
    Returns:
        NewsInfo对象列表，按时间倒序排列
    """
    news_list = get_stock_news(symbol)
    return [
        news for news in news_list 
        if from_time <= news.timestamp <= end_time
    ]


def colum_mapping_transform(latest_row: pd.Series, mapping: Dict[str, Any]) -> Dict[str, Any]:
    data = {}
    for origin_col in latest_row.index.to_list():
        if origin_col in mapping:
            chn_name = mapping[origin_col]
            value = latest_row[origin_col]
            data[chn_name] = float(value) if pd.notna(value) and value != "" else 0
        else:
            logger.warning("字段：%s 未在映射中找到", origin_col)
    return data

@use_cache(86400 * 7, use_db_cache=True)
def get_financial_balance_sheet(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司资产负债表数据

    Args:
        symbol: 股票代码

    Returns:
        包含资产负债表数据的字典
    """
    # 转换为字典格式，便于处理
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务报表-资产负债表",
        "data": {},
    }
    # 获取资产负债表数据
    df = ak.stock_financial_report_sina(stock='600588', symbol="资产负债表")
    if not df.empty:
        result['data'] = df.head(1).iloc[0].dropna().to_dict()
        return result
    result['source'] = "东方财富-股票-财务分析-资产负债表-按报告期"
    
    df = ak.stock_balance_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)
    # 主要资产负债表项目（英文列名映射）
    AK_BALANCE_SHEET_COLUMN_MAP = {
        "SECUCODE": "证券代码",
        "SECURITY_CODE": "股票代码",
        "SECURITY_NAME_ABBR": "股票简称",
        "ORG_CODE": "机构代码",
        "ORG_TYPE": "机构类型",
        "REPORT_DATE": "报告日",
        "REPORT_TYPE": "报告类型",
        "REPORT_DATE_NAME": "报告期",
        "SECURITY_TYPE_CODE": "证券类型代码",
        "NOTICE_DATE": "公告日期",
        "UPDATE_DATE": "更新日期",
        "CURRENCY": "币种",
        "ACCEPT_DEPOSIT_INTERBANK": "吸收存款及同业存放",
        "ACCOUNTS_PAYABLE": "应付账款",
        "ACCOUNTS_RECE": "应收账款",
        "ACCRUED_EXPENSE": "预提费用",
        "ADVANCE_RECEIVABLES": "预收款项",
        "AGENT_TRADE_SECURITY": "代理买卖证券款",
        "AGENT_UNDERWRITE_SECURITY": "代理承销证券款",
        "AMORTIZE_COST_FINASSET": "以摊余成本计量的金融资产",
        "AMORTIZE_COST_FINLIAB": "以摊余成本计量的金融负债",
        "AMORTIZE_COST_NCFINASSET": "以摊余成本计量的非流动金融资产",
        "AMORTIZE_COST_NCFINLIAB": "以摊余成本计量的非流动金融负债",
        "APPOINT_FVTPL_FINASSET": "指定以公允价值计量且其变动计入当期损益的金融资产",
        "APPOINT_FVTPL_FINLIAB": "指定以公允价值计量且其变动计入当期损益的金融负债",
        "ASSET_BALANCE": "资产余额",
        "ASSET_OTHER": "其他资产",
        "ASSIGN_CASH_DIVIDEND": "拟分配现金股利",
        "AVAILABLE_SALE_FINASSET": "可供出售金融资产",
        "BOND_PAYABLE": "应付债券",
        "BORROW_FUND": "拆入资金",
        "BUY_RESALE_FINASSET": "买入返售金融资产",
        "CAPITAL_RESERVE": "资本公积",
        "CIP": "在建工程",
        "CONSUMPTIVE_BIOLOGICAL_ASSET": "消耗性生物资产",
        "CONTRACT_ASSET": "合同资产",
        "CONTRACT_LIAB": "合同负债",
        "CONVERT_DIFF": "外币报表折算差额",
        "CREDITOR_INVEST": "债权投资",
        "CURRENT_ASSET_BALANCE": "流动资产余额",
        "CURRENT_ASSET_OTHER": "其他流动资产",
        "CURRENT_LIAB_BALANCE": "流动负债余额",
        "CURRENT_LIAB_OTHER": "其他流动负债",
        "DEFER_INCOME": "递延收益",
        "DEFER_INCOME_1YEAR": "一年内到期的递延收益",
        "DEFER_TAX_ASSET": "递延所得税资产",
        "DEFER_TAX_LIAB": "递延所得税负债",
        "DERIVE_FINASSET": "衍生金融资产",
        "DERIVE_FINLIAB": "衍生金融负债",
        "DEVELOP_EXPENSE": "开发支出",
        "DIV_HOLDSALE_ASSET": "划分为持有待售的资产",
        "DIV_HOLDSALE_LIAB": "划分为持有待售的负债",
        "DIVIDEND_PAYABLE": "应付股利",
        "DIVIDEND_RECE": "应收股利",
        "EQUITY_BALANCE": "所有者权益余额",
        "EQUITY_OTHER": "其他所有者权益",
        "EXPORT_REFUND_RECE": "应收出口退税",
        "FEE_COMMISSION_PAYABLE": "应付手续费及佣金",
        "FIN_FUND": "结算备付金",
        "FINANCE_RECE": "应收款项融资",
        "FIXED_ASSET": "固定资产",
        "FIXED_ASSET_DISPOSAL": "固定资产清理",
        "FVTOCI_FINASSET": "以公允价值计量且其变动计入其他综合收益的金融资产",
        "FVTOCI_NCFINASSET": "以公允价值计量且其变动计入其他综合收益的非流动金融资产",
        "FVTPL_FINASSET": "以公允价值计量且其变动计入当期损益的金融资产",
        "FVTPL_FINLIAB": "以公允价值计量且其变动计入当期损益的金融负债",
        "GENERAL_RISK_RESERVE": "一般风险准备",
        "GOODWILL": "商誉",
        "HOLD_MATURITY_INVEST": "持有至到期投资",
        "HOLDSALE_ASSET": "持有待售资产",
        "HOLDSALE_LIAB": "持有待售负债",
        "INSURANCE_CONTRACT_RESERVE": "保险合同准备金",
        "INTANGIBLE_ASSET": "无形资产",
        "INTEREST_PAYABLE": "应付利息",
        "INTEREST_RECE": "应收利息",
        "INTERNAL_PAYABLE": "内部应付款",
        "INTERNAL_RECE": "内部应收款",
        "INVENTORY": "存货",
        "INVEST_REALESTATE": "投资性房地产",
        "LEASE_LIAB": "租赁负债",
        "LEND_FUND": "发放贷款及垫款",
        "LIAB_BALANCE": "负债余额",
        "LIAB_EQUITY_BALANCE": "负债和所有者权益余额",
        "LIAB_EQUITY_OTHER": "负债和所有者权益其他",
        "LIAB_OTHER": "其他负债",
        "LOAN_ADVANCE": "发放贷款及垫款",
        "LOAN_PBC": "向中央银行借款",
        "LONG_EQUITY_INVEST": "长期股权投资",
        "LONG_LOAN": "长期借款",
        "LONG_PAYABLE": "长期应付款",
        "LONG_PREPAID_EXPENSE": "长期待摊费用",
        "LONG_RECE": "长期应收款",
        "LONG_STAFFSALARY_PAYABLE": "长期应付职工薪酬",
        "MINORITY_EQUITY": "少数股东权益",
        "MONETARYFUNDS": "货币资金",
        "NONCURRENT_ASSET_1YEAR": "一年内到期的非流动资产",
        "NONCURRENT_ASSET_BALANCE": "非流动资产余额",
        "NONCURRENT_ASSET_OTHER": "其他非流动资产",
        "NONCURRENT_LIAB_1YEAR": "一年内到期的非流动负债",
        "NONCURRENT_LIAB_BALANCE": "非流动负债余额",
        "NONCURRENT_LIAB_OTHER": "其他非流动负债",
        "NOTE_ACCOUNTS_PAYABLE": "应付票据及应付账款",
        "NOTE_ACCOUNTS_RECE": "应收票据及应收账款",
        "NOTE_PAYABLE": "应付票据",
        "NOTE_RECE": "应收票据",
        "OIL_GAS_ASSET": "油气资产",
        "OTHER_COMPRE_INCOME": "其他综合收益",
        "OTHER_CREDITOR_INVEST": "其他债权投资",
        "OTHER_CURRENT_ASSET": "其他流动资产",
        "OTHER_CURRENT_LIAB": "其他流动负债",
        "OTHER_EQUITY_INVEST": "其他权益工具投资",
        "OTHER_EQUITY_OTHER": "其他权益工具其他",
        "OTHER_EQUITY_TOOL": "其他权益工具",
        "OTHER_NONCURRENT_ASSET": "其他非流动资产",
        "OTHER_NONCURRENT_FINASSET": "其他非流动金融资产",
        "OTHER_NONCURRENT_LIAB": "其他非流动负债",
        "OTHER_PAYABLE": "其他应付款",
        "OTHER_RECE": "其他应收款",
        "PARENT_EQUITY_BALANCE": "归属于母公司股东权益合计",
        "PARENT_EQUITY_OTHER": "归属于母公司股东权益其他",
        "PERPETUAL_BOND": "永续债",
        "PERPETUAL_BOND_PAYBALE": "应付永续债",
        "PREDICT_CURRENT_LIAB": "预计流动负债",
        "PREDICT_LIAB": "预计非流动负债",
        "PREFERRED_SHARES": "优先股",
        "PREFERRED_SHARES_PAYBALE": "应付优先股",
        "PREMIUM_RECE": "应收保费",
        "PREPAYMENT": "预付款项",
        "PRODUCTIVE_BIOLOGY_ASSET": "生产性生物资产",
        "PROJECT_MATERIAL": "工程物资",
        "RC_RESERVE_RECE": "应收分保合同准备金",
        "REINSURE_PAYABLE": "应付分保账款",
        "REINSURE_RECE": "应收分保账款",
        "SELL_REPO_FINASSET": "卖出回购金融资产款",
        "SETTLE_EXCESS_RESERVE": "结算备付金",
        "SHARE_CAPITAL": "实收资本(或股本)",
        "SHORT_BOND_PAYABLE": "应付短期债券",
        "SHORT_FIN_PAYABLE": "短期融资款",
        "SHORT_LOAN": "短期借款",
        "SPECIAL_PAYABLE": "专项应付款",
        "SPECIAL_RESERVE": "专项储备",
        "STAFF_SALARY_PAYABLE": "应付职工薪酬",
        "SUBSIDY_RECE": "应收补贴款",
        "SURPLUS_RESERVE": "盈余公积",
        "TAX_PAYABLE": "应交税费",
        "TOTAL_ASSETS": "资产总计",
        "TOTAL_CURRENT_ASSETS": "流动资产合计",
        "TOTAL_CURRENT_LIAB": "流动负债合计",
        "TOTAL_EQUITY": "所有者权益合计",
        "TOTAL_LIAB_EQUITY": "负债和所有者权益(或股东权益)总计",
        "TOTAL_LIABILITIES": "负债合计",
        "TOTAL_NONCURRENT_ASSETS": "非流动资产合计",
        "TOTAL_NONCURRENT_LIAB": "非流动负债合计",
        "TOTAL_OTHER_PAYABLE": "其他应付款合计",
        "TOTAL_OTHER_RECE": "其他应收款合计",
        "TOTAL_PARENT_EQUITY": "归属于母公司股东权益合计",
        "TRADE_FINASSET": "交易性金融资产",
        "TRADE_FINASSET_NOTFVTPL": "交易性金融资产(非以公允价值计量)",
        "TRADE_FINLIAB": "交易性金融负债",
        "TRADE_FINLIAB_NOTFVTPL": "交易性金融负债(非以公允价值计量)",
        "TREASURY_SHARES": "库存股",
        "UNASSIGN_RPOFIT": "未分配利润",
        "UNCONFIRM_INVEST_LOSS": "未确定的投资损失",
        "USERIGHT_ASSET": "使用权资产",
        "OPINION_TYPE": "审计意见类型",
        "OSOPINION_TYPE": "原审计意见类型",
        "LISTING_STATE": "上市状态",
    }
    if not df.empty:
        latest_row = df.iloc[0]
        result['data'] = colum_mapping_transform(latest_row, AK_BALANCE_SHEET_COLUMN_MAP)
        return result
    return result


@use_cache(86400 * 7, use_db_cache=True)
def get_financial_profit_statement(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司利润表数据

    Args:
        symbol: 股票代码

    Returns:
        包含利润表数据的字典
    """
    # 获取利润表数据
    df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
    # ['报告日', '营业总收入', '营业收入', '利息收入', '已赚保费', '手续费及佣金收入', '房地产销售收入', '其他业务收入', '营业总成本', '营业成本', '手续费及佣金支出', '房地产销售成本', '退 保金', '赔付支出净额', '提取保险合同准备金净额', '保单红利支出', '分保费用', '其他业务成本', '营业税金及附加', '研发费用', '销售费用', '管理费用', '财务费用', '利息费用', '利息支出', '投资收益', '对联营企业和合营企业的投资收益', '以摊余成本计量的金融资产终止确认产生的收益', '汇兑收益', '净敞口套期收益', '公允价值变动收益', '期货损益', '托管收益', '补贴收入', '其他收益', '资产减值损失', '信用减值损失', '其他业务利润', '资产处置收益', '营业利润', '营业外收入', '非流动资产处置利得', '营业外支出', '非流动资产处置损失', '利润总额', '所得税费用', ' 未确认投资损失', '净利润', '持续经营净利润', '终止经营净利润', '归属于母公司所有者的净利润', '被合并方在合并前实现净利润', '少数股东损益', '其他综合收益', '归属于母公司所有者的其他综 合收益', '（一）以后不能重分类进损益的其他综合收益', '重新计量设定受益计划变动额', '权益法下不能转损益的其他综合收益', '其他权益工具投资公允价值变动', '企业自身信用风险公允价值变动', '（二）以后将重分类进损益的其他综合收益', '权益法下可转损益的其他综合收益', '可供出售金融资产公允价值变动损益', '其他债权投资公允价值变动', '金融资产重分类计入其他综合收益的金额', '其他债权投资信用减值准备', '持有至到期投资重分类为可供出售金融资产损益', '现金流量套期储备', '现金流量套期损益的有效部分', '外币财务报表折算差额', '其他', '归属于少数股东的其他综合收益', '综合收益总额', '归属于母公司所有者的综合收益总额', '归属于少数股东的综合收益总额', '基本每股收益', '稀释每股收益', '数据源', '是否审计', '公告日期', '币种', '类型', '更新日期'] 
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务分析-利润表",
        "data": {},
    }
    if not df.empty:
        result['data'] = dict(df.head(1).iloc[0].dropna()) # 取最新一期数据
        return result

    df = ak.stock_profit_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)
    result['source'] = "东方财富-股票-财务分析-利润表-报告期"
    

    # 主要利润表项目（英文列名映射）
    PROFIT_COLUMN_MAP = {
        "SECUCODE": "证券代码",
        "SECURITY_CODE": "股票代码",
        "SECURITY_NAME_ABBR": "股票简称",
        "ORG_CODE": "机构代码",
        "ORG_TYPE": "机构类型",
        "REPORT_DATE": "报告日",
        "REPORT_TYPE": "报告类型",
        "REPORT_DATE_NAME": "报告期",
        "SECURITY_TYPE_CODE": "证券类型代码",
        "NOTICE_DATE": "公告日期",
        "UPDATE_DATE": "更新日期",
        "CURRENCY": "币种",
        "TOTAL_OPERATE_INCOME": "营业总收入",
        "TOTAL_OPERATE_INCOME_YOY": "营业总收入同比",
        "OPERATE_INCOME": "营业收入",
        "OPERATE_INCOME_YOY": "营业收入同比",
        "INTEREST_INCOME": "利息收入",
        "INTEREST_INCOME_YOY": "利息收入同比",
        "EARNED_PREMIUM": "已赚保费",
        "EARNED_PREMIUM_YOY": "已赚保费同比",
        "FEE_COMMISSION_INCOME": "手续费及佣金收入",
        "FEE_COMMISSION_INCOME_YOY": "手续费及佣金收入同比",
        "OTHER_BUSINESS_INCOME": "其他业务收入",
        "OTHER_BUSINESS_INCOME_YOY": "其他业务收入同比",
        "TOI_OTHER": "其他营业总收入",
        "TOI_OTHER_YOY": "其他营业总收入同比",
        "TOTAL_OPERATE_COST": "营业总成本",
        "TOTAL_OPERATE_COST_YOY": "营业总成本同比",
        "OPERATE_COST": "营业成本",
        "OPERATE_COST_YOY": "营业成本同比",
        "INTEREST_EXPENSE": "利息支出",
        "INTEREST_EXPENSE_YOY": "利息支出同比",
        "FEE_COMMISSION_EXPENSE": "手续费及佣金支出",
        "FEE_COMMISSION_EXPENSE_YOY": "手续费及佣金支出同比",
        "RESEARCH_EXPENSE": "研发费用",
        "RESEARCH_EXPENSE_YOY": "研发费用同比",
        "SURRENDER_VALUE": "退保金",
        "SURRENDER_VALUE_YOY": "退保金同比",
        "NET_COMPENSATE_EXPENSE": "赔付支出净额",
        "NET_COMPENSATE_EXPENSE_YOY": "赔付支出净额同比",
        "NET_CONTRACT_RESERVE": "提取保险合同准备金净额",
        "NET_CONTRACT_RESERVE_YOY": "提取保险合同准备金净额同比",
        "POLICY_BONUS_EXPENSE": "保单红利支出",
        "POLICY_BONUS_EXPENSE_YOY": "保单红利支出同比",
        "REINSURE_EXPENSE": "分保费用",
        "REINSURE_EXPENSE_YOY": "分保费用同比",
        "OTHER_BUSINESS_COST": "其他业务成本",
        "OTHER_BUSINESS_COST_YOY": "其他业务成本同比",
        "OPERATE_TAX_ADD": "营业税金及附加",
        "OPERATE_TAX_ADD_YOY": "营业税金及附加同比",
        "SALE_EXPENSE": "销售费用",
        "SALE_EXPENSE_YOY": "销售费用同比",
        "MANAGE_EXPENSE": "管理费用",
        "MANAGE_EXPENSE_YOY": "管理费用同比",
        "ME_RESEARCH_EXPENSE": "研发费用(管理费用下)",
        "ME_RESEARCH_EXPENSE_YOY": "研发费用(管理费用下)同比",
        "FINANCE_EXPENSE": "财务费用",
        "FINANCE_EXPENSE_YOY": "财务费用同比",
        "FE_INTEREST_EXPENSE": "利息费用",
        "FE_INTEREST_EXPENSE_YOY": "利息费用同比",
        "FE_INTEREST_INCOME": "利息收入(财务费用下)",
        "FE_INTEREST_INCOME_YOY": "利息收入(财务费用下)同比",
        "ASSET_IMPAIRMENT_LOSS": "资产减值损失",
        "ASSET_IMPAIRMENT_LOSS_YOY": "资产减值损失同比",
        "CREDIT_IMPAIRMENT_LOSS": "信用减值损失",
        "CREDIT_IMPAIRMENT_LOSS_YOY": "信用减值损失同比",
        "TOC_OTHER": "其他营业总成本",
        "TOC_OTHER_YOY": "其他营业总成本同比",
        "FAIRVALUE_CHANGE_INCOME": "公允价值变动收益",
        "ASSET_DISPOSAL_INCOME": "资产处置收益",
        "ASSET_DISPOSAL_INCOME_YOY": "资产处置收益同比",
        "ASSET_IMPAIRMENT_INCOME": "资产减值收益",
        "ASSET_IMPAIRMENT_INCOME_YOY": "资产减值收益同比",
        "CREDIT_IMPAIRMENT_INCOME": "信用减值收益",
        "CREDIT_IMPAIRMENT_INCOME_YOY": "信用减值收益同比",
        "OTHER_INCOME": "其他收益",
        "OTHER_INCOME_YOY": "其他收益同比",
        "OPERATE_PROFIT_OTHER": "其他营业利润",
        "OPERATE_PROFIT_OTHER_YOY": "其他营业利润同比",
        "OPERATE_PROFIT_BALANCE": "营业利润小计",
        "OPERATE_PROFIT_BALANCE_YOY": "营业利润小计同比",
        "OPERATE_PROFIT": "营业利润",
        "OPERATE_PROFIT_YOY": "营业利润同比",
        "NONBUSINESS_INCOME": "营业外收入",
        "NONBUSINESS_INCOME_YOY": "营业外收入同比",
        "NONCURRENT_DISPOSAL_INCOME": "非流动资产处置利得",
        "NONCURRENT_DISPOSAL_INCOME_YOY": "非流动资产处置利得同比",
        "NONBUSINESS_EXPENSE": "营业外支出",
        "NONBUSINESS_EXPENSE_YOY": "营业外支出同比",
        "NONCURRENT_DISPOSAL_LOSS": "非流动资产处置损失",
        "NONCURRENT_DISPOSAL_LOSS_YOY": "非流动资产处置损失同比",
        "EFFECT_TP_OTHER": "其他影响利润总额的项目",
        "EFFECT_TP_OTHER_YOY": "其他影响利润总额的项目同比",
        "TOTAL_PROFIT_BALANCE": "利润总额小计",
        "TOTAL_PROFIT_BALANCE_YOY": "利润总额小计同比",
        "TOTAL_PROFIT": "利润总额",
        "TOTAL_PROFIT_YOY": "利润总额同比",
        "INCOME_TAX": "所得税费用",
        "INCOME_TAX_YOY": "所得税费用同比",
        "EFFECT_NETPROFIT_OTHER": "其他影响净利润的项目",
        "EFFECT_NETPROFIT_OTHER_YOY": "其他影响净利润的项目同比",
        "EFFECT_NETPROFIT_BALANCE": "净利润小计",
        "EFFECT_NETPROFIT_BALANCE_YOY": "净利润小计同比",
        "UNCONFIRM_INVEST_LOSS": "未确认投资损失",
        "UNCONFIRM_INVEST_LOSS_YOY": "未确认投资损失同比",
        "NETPROFIT": "净利润",
        "NETPROFIT_YOY": "净利润同比",
        "PRECOMBINE_PROFIT": "被合并方在合并前实现净利润",
        "PRECOMBINE_PROFIT_YOY": "被合并方在合并前实现净利润同比",
        "CONTINUED_NETPROFIT": "持续经营净利润",
        "CONTINUED_NETPROFIT_YOY": "持续经营净利润同比",
        "DISCONTINUED_NETPROFIT": "终止经营净利润",
        "DISCONTINUED_NETPROFIT_YOY": "终止经营净利润同比",
        "PARENT_NETPROFIT": "归属于母公司所有者的净利润",
        "PARENT_NETPROFIT_YOY": "归属于母公司所有者的净利润同比",
        "MINORITY_INTEREST": "少数股东损益",
        "MINORITY_INTEREST_YOY": "少数股东损益同比",
        "DEDUCT_PARENT_NETPROFIT": "扣除非经常性损益后的净利润",
        "DEDUCT_PARENT_NETPROFIT_YOY": "扣除非经常性损益后的净利润同比",
        "NETPROFIT_OTHER": "其他净利润",
        "NETPROFIT_OTHER_YOY": "其他净利润同比",
        "NETPROFIT_BALANCE": "净利润合计",
        "NETPROFIT_BALANCE_YOY": "净利润合计同比",
        "BASIC_EPS": "基本每股收益",
        "BASIC_EPS_YOY": "基本每股收益同比",
        "DILUTED_EPS": "稀释每股收益",
        "DILUTED_EPS_YOY": "稀释每股收益同比",
        "OTHER_COMPRE_INCOME": "其他综合收益",
        "OTHER_COMPRE_INCOME_YOY": "其他综合收益同比",
        "PARENT_OCI": "归属于母公司所有者的其他综合收益",
        "PARENT_OCI_YOY": "归属于母公司所有者的其他综合收益同比",
        "MINORITY_OCI": "归属于少数股东的其他综合收益",
        "MINORITY_OCI_YOY": "归属于少数股东的其他综合收益同比",
        "PARENT_OCI_OTHER": "归属于母公司所有者的其他综合收益-其他",
        "PARENT_OCI_OTHER_YOY": "归属于母公司所有者的其他综合收益-其他同比",
        "PARENT_OCI_BALANCE": "归属于母公司所有者的其他综合收益合计",
        "PARENT_OCI_BALANCE_YOY": "归属于母公司所有者的其他综合收益合计同比",
        "UNABLE_OCI": "以后不能重分类进损益的其他综合收益",
        "UNABLE_OCI_YOY": "以后不能重分类进损益的其他综合收益同比",
        "CREDITRISK_FAIRVALUE_CHANGE": "企业自身信用风险公允价值变动",
        "CREDITRISK_FAIRVALUE_CHANGE_YOY": "企业自身信用风险公允价值变动同比",
        "OTHERRIGHT_FAIRVALUE_CHANGE": "其他权益工具投资公允价值变动",
        "OTHERRIGHT_FAIRVALUE_CHANGE_YOY": "其他权益工具投资公允价值变动同比",
        "SETUP_PROFIT_CHANGE": "设定受益计划变动额",
        "SETUP_PROFIT_CHANGE_YOY": "设定受益计划变动额同比",
        "RIGHTLAW_UNABLE_OCI": "权益法下不能转损益的其他综合收益",
        "RIGHTLAW_UNABLE_OCI_YOY": "权益法下不能转损益的其他综合收益同比",
        "UNABLE_OCI_OTHER": "以后不能重分类进损益的其他综合收益-其他",
        "UNABLE_OCI_OTHER_YOY": "以后不能重分类进损益的其他综合收益-其他同比",
        "UNABLE_OCI_BALANCE": "以后不能重分类进损益的其他综合收益合计",
        "UNABLE_OCI_BALANCE_YOY": "以后不能重分类进损益的其他综合收益合计同比",
        "ABLE_OCI": "以后将重分类进损益的其他综合收益",
        "ABLE_OCI_YOY": "以后将重分类进损益的其他综合收益同比",
        "RIGHTLAW_ABLE_OCI": "权益法下可转损益的其他综合收益",
        "RIGHTLAW_ABLE_OCI_YOY": "权益法下可转损益的其他综合收益同比",
        "AFA_FAIRVALUE_CHANGE": "可供出售金融资产公允价值变动损益",
        "AFA_FAIRVALUE_CHANGE_YOY": "可供出售金融资产公允价值变动损益同比",
        "HMI_AFA": "持有至到期投资重分类为可供出售金融资产损益",
        "HMI_AFA_YOY": "持有至到期投资重分类为可供出售金融资产损益同比",
        "CASHFLOW_HEDGE_VALID": "现金流量套期损益的有效部分",
        "CASHFLOW_HEDGE_VALID_YOY": "现金流量套期损益的有效部分同比",
        "CREDITOR_FAIRVALUE_CHANGE": "其他债权投资公允价值变动",
        "CREDITOR_FAIRVALUE_CHANGE_YOY": "其他债权投资公允价值变动同比",
        "CREDITOR_IMPAIRMENT_RESERVE": "其他债权投资信用减值准备",
        "CREDITOR_IMPAIRMENT_RESERVE_YOY": "其他债权投资信用减值准备同比",
        "FINANCE_OCI_AMT": "金融资产重分类计入其他综合收益的金额",
        "FINANCE_OCI_AMT_YOY": "金融资产重分类计入其他综合收益的金额同比",
        "CONVERT_DIFF": "外币财务报表折算差额",
        "CONVERT_DIFF_YOY": "外币财务报表折算差额同比",
        "ABLE_OCI_OTHER": "以后将重分类进损益的其他综合收益-其他",
        "ABLE_OCI_OTHER_YOY": "以后将重分类进损益的其他综合收益-其他同比",
        "ABLE_OCI_BALANCE": "以后将重分类进损益的其他综合收益合计",
        "ABLE_OCI_BALANCE_YOY": "以后将重分类进损益的其他综合收益合计同比",
        "OCI_OTHER": "其他综合收益-其他",
        "OCI_OTHER_YOY": "其他综合收益-其他同比",
        "OCI_BALANCE": "其他综合收益合计",
        "OCI_BALANCE_YOY": "其他综合收益合计同比",
        "TOTAL_COMPRE_INCOME": "综合收益总额",
        "TOTAL_COMPRE_INCOME_YOY": "综合收益总额同比",
        "PARENT_TCI": "归属于母公司所有者的综合收益总额",
        "PARENT_TCI_YOY": "归属于母公司所有者的综合收益总额同比",
        "MINORITY_TCI": "归属于少数股东的综合收益总额",
        "MINORITY_TCI_YOY": "归属于少数股东的综合收益总额同比",
        "PRECOMBINE_TCI": "被合并方在合并前实现的综合收益总额",
        "PRECOMBINE_TCI_YOY": "被合并方在合并前实现的综合收益总额同比",
        "EFFECT_TCI_BALANCE": "综合收益总额合计",
        "EFFECT_TCI_BALANCE_YOY": "综合收益总额合计同比",
        "TCI_OTHER": "综合收益总额-其他",
        "TCI_OTHER_YOY": "综合收益总额-其他同比",
        "TCI_BALANCE": "综合收益总额合计",
        "TCI_BALANCE_YOY": "综合收益总额合计同比",
        "ACF_END_INCOME": "期末未分配利润",
        "ACF_END_INCOME_YOY": "期末未分配利润同比",
        "OPINION_TYPE": "审计意见类型",
    }

    # 获取最新一期数据
    latest_row = df.iloc[0]
    result['data'] = colum_mapping_transform(latest_row, PROFIT_COLUMN_MAP)
    return result
 
@use_cache(86400 * 7, use_db_cache=True)
def get_financial_cash_flow(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司现金流量表数据

    Args:
        symbol: 股票代码

    Returns:
        包含现金流量表数据的字典
    """
    # 获取现金流量表数据
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务分析-现金流量表",
        "data": {},
    }
    df = ak.stock_financial_report_sina(stock='600588', symbol="现金流量表")
    if not df.empty:
        result['data'] = dict(df.head(1).iloc[0].dropna()) # 取最新一期数据
        return result
    
    CASH_FLOW_COLUMN_MAP = {
        "SECUCODE": "证券代码",
        "SECURITY_CODE": "股票代码",
        "SECURITY_NAME_ABBR": "股票简称",
        "ORG_CODE": "机构代码",
        "ORG_TYPE": "机构类型",
        "REPORT_DATE": "报告日",
        "REPORT_TYPE": "报告类型",
        "REPORT_DATE_NAME": "报告期",
        "SECURITY_TYPE_CODE": "证券类型代码",
        "NOTICE_DATE": "公告日期",
        "UPDATE_DATE": "更新日期",
        "CURRENCY": "币种",
        "SALES_SERVICES": "销售商品、提供劳务收到的现金",
        "DEPOSIT_INTERBANK_ADD": "客户存款和同业存放款项净增加额",
        "LOAN_PBC_ADD": "向中央银行借款净增加额",
        "OFI_BF_ADD": "向其他金融机构拆入资金净增加额",
        "RECEIVE_ORIGIC_PREMIUM": "收到原保险合同保费取得的现金",
        "RECEIVE_REINSURE_NET": "收到再保险业务现金净额",
        "INSURED_INVEST_ADD": "保户储金及投资款净增加额",
        "DISPOSAL_TFA_ADD": "处置交易性金融资产净增加额",
        "RECEIVE_INTEREST_COMMISSION": "收取利息、手续费及佣金的现金",
        "BORROW_FUND_ADD": "拆入资金净增加额",
        "LOAN_ADVANCE_REDUCE": "客户贷款及垫款净增加额",
        "REPO_BUSINESS_ADD": "回购业务资金净增加额",
        "RECEIVE_TAX_REFUND": "收到的税费返还",
        "RECEIVE_OTHER_OPERATE": "收到的其他与经营活动有关的现金",
        "OPERATE_INFLOW_OTHER": "经营活动现金流入其他",
        "OPERATE_INFLOW_BALANCE": "经营活动现金流入小计",
        "TOTAL_OPERATE_INFLOW": "经营活动现金流入合计",
        "BUY_SERVICES": "购买商品、接受劳务支付的现金",
        "LOAN_ADVANCE_ADD": "客户贷款及垫款净增加额",
        "PBC_INTERBANK_ADD": "存放中央银行和同业款项净增加额",
        "PAY_ORIGIC_COMPENSATE": "支付原保险合同赔付款项的现金",
        "PAY_INTEREST_COMMISSION": "支付利息、手续费及佣金的现金",
        "PAY_POLICY_BONUS": "支付保单红利的现金",
        "PAY_STAFF_CASH": "支付给职工以及为职工支付的现金",
        "PAY_ALL_TAX": "支付的各项税费",
        "PAY_OTHER_OPERATE": "支付的其他与经营活动有关的现金",
        "OPERATE_OUTFLOW_OTHER": "经营活动现金流出其他",
        "OPERATE_OUTFLOW_BALANCE": "经营活动现金流出小计",
        "TOTAL_OPERATE_OUTFLOW": "经营活动现金流出合计",
        "OPERATE_NETCASH_OTHER": "经营活动产生的现金流量净额其他",
        "OPERATE_NETCASH_BALANCE": "经营活动产生的现金流量净额小计",
        "NETCASH_OPERATE": "经营活动产生的现金流量净额",
        "WITHDRAW_INVEST": "收回投资所收到的现金",
        "RECEIVE_INVEST_INCOME": "取得投资收益收到的现金",
        "DISPOSAL_LONG_ASSET": "处置固定资产、无形资产和其他长期资产所收回的现金净额",
        "DISPOSAL_SUBSIDIARY_OTHER": "处置子公司及其他营业单位收到的现金净额",
        "REDUCE_PLEDGE_TIMEDEPOSITS": "减少质押和定期存款所收到的现金",
        "RECEIVE_OTHER_INVEST": "收到的其他与投资活动有关的现金",
        "INVEST_INFLOW_OTHER": "投资活动现金流入其他",
        "INVEST_INFLOW_BALANCE": "投资活动现金流入小计",
        "TOTAL_INVEST_INFLOW": "投资活动现金流入合计",
        "CONSTRUCT_LONG_ASSET": "购建固定资产、无形资产和其他长期资产所支付的现金",
        "INVEST_PAY_CASH": "投资所支付的现金",
        "PLEDGE_LOAN_ADD": "质押贷款净增加额",
        "OBTAIN_SUBSIDIARY_OTHER": "取得子公司及其他营业单位支付的现金净额",
        "ADD_PLEDGE_TIMEDEPOSITS": "增加质押和定期存款所支付的现金",
        "PAY_OTHER_INVEST": "支付的其他与投资活动有关的现金",
        "INVEST_OUTFLOW_OTHER": "投资活动现金流出其他",
        "INVEST_OUTFLOW_BALANCE": "投资活动现金流出小计",
        "TOTAL_INVEST_OUTFLOW": "投资活动现金流出合计",
        "INVEST_NETCASH_OTHER": "投资活动产生的现金流量净额其他",
        "INVEST_NETCASH_BALANCE": "投资活动产生的现金流量净额小计",
        "NETCASH_INVEST": "投资活动产生的现金流量净额",
        "ACCEPT_INVEST_CASH": "吸收投资收到的现金",
        "SUBSIDIARY_ACCEPT_INVEST": "子公司吸收少数股东投资收到的现金",
        "RECEIVE_LOAN_CASH": "取得借款收到的现金",
        "ISSUE_BOND": "发行债券收到的现金",
        "RECEIVE_OTHER_FINANCE": "收到其他与筹资活动有关的现金",
        "FINANCE_INFLOW_OTHER": "筹资活动现金流入其他",
        "FINANCE_INFLOW_BALANCE": "筹资活动现金流入小计",
        "TOTAL_FINANCE_INFLOW": "筹资活动现金流入合计",
        "PAY_DEBT_CASH": "偿还债务支付的现金",
        "ASSIGN_DIVIDEND_PORFIT": "分配股利、利润或偿付利息所支付的现金",
        "SUBSIDIARY_PAY_DIVIDEND": "子公司支付给少数股东的股利、利润",
        "BUY_SUBSIDIARY_EQUITY": "购买子公司股权支付的现金",
        "PAY_OTHER_FINANCE": "支付其他与筹资活动有关的现金",
        "SUBSIDIARY_REDUCE_CASH": "子公司减少现金",
        "FINANCE_OUTFLOW_OTHER": "筹资活动现金流出其他",
        "FINANCE_OUTFLOW_BALANCE": "筹资活动现金流出小计",
        "TOTAL_FINANCE_OUTFLOW": "筹资活动现金流出合计",
        "FINANCE_NETCASH_OTHER": "筹资活动产生的现金流量净额其他",
        "FINANCE_NETCASH_BALANCE": "筹资活动产生的现金流量净额小计",
        "NETCASH_FINANCE": "筹资活动产生的现金流量净额",
        "RATE_CHANGE_EFFECT": "汇率变动对现金及现金等价物的影响",
        "CCE_ADD_OTHER": "现金及现金等价物净增加额其他",
        "CCE_ADD_BALANCE": "现金及现金等价物净增加额小计",
        "CCE_ADD": "现金及现金等价物净增加额",
        "BEGIN_CCE": "期初现金及现金等价物余额",
        "END_CCE_OTHER": "期末现金及现金等价物余额其他",
        "END_CCE_BALANCE": "期末现金及现金等价物余额小计",
        "END_CCE": "期末现金及现金等价物余额",
        "NETPROFIT": "净利润",
        "ASSET_IMPAIRMENT": "资产减值损失",
        "FA_IR_DEPR": "固定资产折旧",
        "OILGAS_BIOLOGY_DEPR": "油气及生物资产折旧",
        "IR_DEPR": "无形资产摊销",
        "IA_AMORTIZE": "无形资产摊销",
        "LPE_AMORTIZE": "长期待摊费用摊销",
        "DEFER_INCOME_AMORTIZE": "递延收益摊销",
        "PREPAID_EXPENSE_REDUCE": "预付费用减少",
        "ACCRUED_EXPENSE_ADD": "应计费用增加",
        "DISPOSAL_LONGASSET_LOSS": "处置长期资产损失",
        "FA_SCRAP_LOSS": "固定资产报废损失",
        "FAIRVALUE_CHANGE_LOSS": "公允价值变动损失",
        "FINANCE_EXPENSE": "财务费用",
        "INVEST_LOSS": "投资损失",
        "DEFER_TAX": "递延所得税",
        "DT_ASSET_REDUCE": "递延所得税资产减少",
        "DT_LIAB_ADD": "递延所得税负债增加",
        "PREDICT_LIAB_ADD": "预计负债增加",
        "INVENTORY_REDUCE": "存货减少",
        "OPERATE_RECE_REDUCE": "经营性应收项目减少",
        "OPERATE_PAYABLE_ADD": "经营性应付项目增加",
        "OTHER": "其他",
        "OPERATE_NETCASH_OTHERNOTE": "经营活动产生的现金流量净额其他说明",
        "OPERATE_NETCASH_BALANCENOTE": "经营活动产生的现金流量净额小计说明",
        "NETCASH_OPERATENOTE": "经营活动产生的现金流量净额说明",
        "DEBT_TRANSFER_CAPITAL": "债务转为资本",
        "CONVERT_BOND_1YEAR": "一年内到期可转换公司债券",
        "FINLEASE_OBTAIN_FA": "融资租赁取得固定资产",
        "UNINVOLVE_INVESTFIN_OTHER": "未涉及投资和筹资活动的其他事项",
        "END_CASH": "期末现金余额",
        "BEGIN_CASH": "期初现金余额",
        # 下面是同比相关字段，通常可忽略
        # ...省略...
        "OPINION_TYPE": "审计意见类型",
        "OSOPINION_TYPE": "原审计意见类型",
        "MINORITY_INTEREST": "少数股东权益",
        "USERIGHT_ASSET_AMORTIZE": "使用权资产摊销",
    }
    df = ak.stock_cash_flow_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)
    result['source'] = "东方财富-股票-财务分析-现金流量表-按报告期"
    if not df.empty:
        latest_row = df.iloc[0]
        result['data'] = colum_mapping_transform(latest_row, CASH_FLOW_COLUMN_MAP)   
    return result

@use_cache(86400 * 7, use_db_cache=True)
def get_financial_indicators(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司主要财务指标

    Args:
        symbol: 股票代码

    Returns:
        包含主要财务指标的字典
    """
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务分析-财务指标",
        "data": {},
    }
    from_year = str(datetime.now().year) if datetime.now().month >= 4 else str(datetime.now().year - 1)
    df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=from_year)
    if df.empty:
        logger.warning(f"未找到股票 {symbol} 的财务指标数据")
        result["source"] = "同花顺-财务分析-财务指标"
        df = ak.stock_financial_abstract_ths(symbol=symbol)

    # 将最新一期数据转换为字典格式
    if not df.empty:
        result['data'] = df.tail(1).iloc[0].dropna().to_dict()
        if result['data'].get("日期"):
            result['data']["日期"] = str(result['data'].get("日期"))

    return result

# 里面的函数都设置了7天缓存，可以不用设置了
def get_comprehensive_financial_data(symbol: str) -> Dict[str, Any]:
    """
    获取公司综合财务数据（资产负债表、利润表、现金流量表、财务指标）

    Args:
        symbol: 股票代码

    Returns:
        包含综合财务数据的字典
    """
    return {
        "symbol": symbol,
        "balance_sheet": get_financial_balance_sheet(symbol),
        "profit_statement": get_financial_profit_statement(symbol),
        "cash_flow": get_financial_cash_flow(symbol),
        "financial_indicators": get_financial_indicators(symbol),
    }


def convert_to_json_serializable(obj):
    """
    将对象转换为JSON可序列化的格式
    """
    if hasattr(obj, 'isoformat'):  # datetime, date objects
        return obj.isoformat()
    elif hasattr(obj, 'item'):  # numpy types
        return obj.item()
    elif pd.isna(obj):  # pandas NaN
        return None
    else:
        return obj


def remove_unwanted_fields(data_record):
    """
    从数据记录中移除不需要的字段（最新价、涨跌幅）
    
    Args:
        data_record: 单条数据记录字典
    
    Returns:
        清理后的数据记录
    """
    unwanted_fields = ['最新价', '涨跌幅']
    
    if not data_record or not isinstance(data_record, dict):
        return data_record
    
    return {k: v for k, v in data_record.items() if k not in unwanted_fields}


def clean_data_for_json(data):
    """
    清理数据使其可以序列化为JSON
    """
    if isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: clean_data_for_json(value) for key, value in data.items()}
    else:
        return convert_to_json_serializable(data)


@use_cache(86400 * 7, use_db_cache=True)
def get_shareholder_changes_data(stock_code: str) -> Dict[str, Any]:
    """
    获取指定股票的股东股本变动详情（最新数据）
    
    Args:
        stock_code: 股票代码（如：000001、600036等）
    
    Returns:
        包含字典：股东持股变动详情
    """
    
    logger.info(f"开始获取股票 {stock_code} 的股东变动数据")
    
    results = {}

    try:
        logger.info(f"正在获取股票 {stock_code} 的高管持股变动详情")

        management_df = ak.stock_zh_a_gdhs_detail_em(symbol=stock_code)
        
        if not management_df.empty:
            # 查找日期列并排序，只返回最新的一条数据
            date_columns = [col for col in management_df.columns if '日期' in col or '时间' in col or 'date' in col.lower()]
            date_col = date_columns[0]
            management_df[date_col] = pd.to_datetime(management_df[date_col], errors='coerce')
            management_df_sorted = management_df.sort_values(by=date_col, ascending=False, na_position='last')
            latest_record = management_df_sorted.iloc[0]
            results = clean_data_for_json(latest_record.to_dict())
            logger.info(f"成功获取 {stock_code} 的高管持股变动详情最新记录，日期: {latest_record[date_col]}")
        
        else:
            logger.warning(f"未获取到 {stock_code} 的高管持股变动详情")
            
    except Exception as e:
        logger.error(f"获取高管持股变动详情失败: {e}")
    
    return results

global_china_holiday_cache_by_year: Dict[str, List[str]] = {}
def is_china_business_day(day: datetime) -> bool:
    global global_china_holiday_cache_by_year
    if day.weekday() >= 5:
        return False

    year_str = day.strftime("%Y")
    day_str = day.strftime("%Y-%m-%d")
    if year_str in global_china_holiday_cache_by_year:
        return day_str not in global_china_holiday_cache_by_year[year_str]

    with create_transaction() as db:
        cache_key = f"{year_str}_china_holiday"
        holiday_list = db.kv_store.get(f"{year_str}_china_holiday")
        if holiday_list is None:
            holiday_list = get_china_holiday(year_str)
            db.kv_store.set(cache_key, holiday_list)
            db.commit()
        global_china_holiday_cache_by_year[year_str] = holiday_list
        return day_str not in holiday_list


def is_china_business_time(time: datetime) -> bool:
    if time.hour < 9 or (time.hour == 9 and time.minute < 30):
        return False

    if time.hour > 15 or (time.hour == 15 and time.minute > 0):
        return False

    if not is_china_business_day(time):
        return False

    return True

LeGuLeGuIndicators = TypedDict("LeGuLeGuIndicators", {
    "pe": Optional[float], # 市盈率
    "pe_ttm": Optional[float], # 市盈率（TTM，Trailing Twelve Months，过去12个月滚动市盈率
    "pb": Optional[float], # 市净率
    "dv_ratio": Optional[float], # 股息率
    "dv_ttm": Optional[float], # 股息率（TTM，Trailing Twelve Months，过去12个月滚动股息率
    "ps": Optional[float], # 市销率
    "ps_ttm": Optional[float], # 市销率（TTM，Trailing Twelve Months，过去12个月滚动市销率
    "total_mv": Optional[float], # 总市值
})

# _cache_key_generator = 
# @use_cache(ttl_seconds=3600, use_db_cache=False)
def get_indicators_from_legulegu(symbol: str, date: Optional[datetime] = None) -> LeGuLeGuIndicators:
    """
    获取A股股票的市盈率（PE）及其他相关指标

    Args:
        symbol: 股票代码
    
    Returns:
        市盈率（PE），如果获取失败则返回0.0
    """
    if date is None:
        date = datetime.now()

    is_curr_date = date.date() == datetime.now().date()

    if not is_china_business_day(date):
        logger.warning(f"日期 {date} 不是中国的交易日, 将获取之前最近的交易日数据")
        while not is_china_business_day(date):
            date -= timedelta(days=1)
    
    date_in_str = str(date.date())
    cache_exist = False
    with create_transaction() as db:
        cache_key = f"pe_and_etc_indicators_{symbol}"
        cache_exist = db.kv_store.has(cache_key)
        if cache_exist:
            cache_data_json = db.kv_store.get(cache_key)
            data_of_date = cache_data_json.get(date_in_str)
            if data_of_date:
                return data_of_date
            elif not is_curr_date:
                raise ValueError(f"{symbol} 在 {date_in_str} 的没有数据")

    df = ak.stock_a_indicator_lg(symbol=symbol)
    if df is not None and not df.empty:
        indicators_dict = {}
        for _, row in df.iterrows():
            date_str = str(row["trade_date"])
            indicators_dict[date_str] = {
                "pe": row.get("pe", None),
                "pe_ttm": row.get("pe_ttm", None),
                "pb": row.get("pb", None),
                "dv_ratio": row.get("dv_ratio", None),
                "dv_ttm": row.get("dv_ttm", None),
                "ps": row.get("ps", None),
                "ps_ttm": row.get("ps_ttm", None),
                "total_mv": row.get("total_mv", None),
            }
        # 存入数据库缓存
        with create_transaction() as db:
            cache_key = f"pe_and_etc_indicators_{symbol}"
            db.kv_store.set(cache_key, indicators_dict)
            db.commit()
        data_of_date = indicators_dict.get(date_in_str)
        if data_of_date:
            return data_of_date
        elif not is_curr_date:
            raise ValueError(f"{symbol} 在 {date_in_str} 没有数据")
    else:
        raise ValueError(f"stock_a_indicator_lg 获取数据失败，可能是股票代码 {symbol} 不存在或数据源异常")

CurrentPePbFromTencent = TypedDict("CurrentPePbFromTencent", {
    "pe": float, # 当前市盈率
    "pb": float, # 当前市净率
    "total_market_cap": float, # 当前总市值
})

@use_cache(ttl_seconds=86400, use_db_cache=True)
def get_current_pe_pb_from_tencent(symbol: str) -> Dict[str, float]:
    """
    获取当前A股股票的市盈率（PE）和市净率（PB）

    Args:
        symbol: 股票代码
    
    Returns:
        包含市盈率（PE）市净率（PB）和总市值的字典
    """
    snap_shot = fetch_realtime_stock_snapshot(symbol)
    return {
        'pe': snap_shot['pe_dynamic'],
        'pb': snap_shot['pb_ratio'],
        'total_market_cap': snap_shot['total_market_cap']
    }

