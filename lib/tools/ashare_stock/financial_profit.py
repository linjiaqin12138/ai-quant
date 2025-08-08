import akshare as ak
from typing import Dict, Any
from lib.logger import logger
from lib.tools.cache_decorator import use_cache
from lib.utils.symbol import determine_exchange
from .utils import colum_mapping_transform

@use_cache(86400 * 7, use_db_cache=True)
def get_financial_profit_statement_history(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司利润表历史数据

    Args:
        symbol: 股票代码

    Returns:
        包含利润表历史数据的字典
    """
    result = {
        "symbol": symbol,
        "source": "新浪财经-财务分析-利润表",
        "data": [],
    }
    try:
        df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
        for _, row in df.iterrows():
            result["data"].append(row.dropna().to_dict())
        if result["data"]:
            return result
    except Exception as e:
        logger.error("获取利润表历史数据失败: %s, 尝试切换到其他数据源", e)

    result['source'] = "东方财富-股票-财务分析-利润表-按报告期"
    df = ak.stock_profit_sheet_by_report_em(symbol=determine_exchange(symbol) + symbol)
    
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

        "FAIRVALUE_CHANGE_INCOME_YOY": "公允价值变动收益同比",
        "INVEST_INCOME": "投资收益",
        "INVEST_INCOME_YOY": "投资收益同比",
        "INVEST_JOINT_INCOME": "对联营企业和合营企业的投资收益",
        "INVEST_JOINT_INCOME_YOY": "对联营企业和合营企业的投资收益同比",
        "NET_EXPOSURE_INCOME": "净敞口套期收益",
        "NET_EXPOSURE_INCOME_YOY": "净敞口套期收益同比",
        "EXCHANGE_INCOME": "汇兑收益",
        "EXCHANGE_INCOME_YOY": "汇兑收益同比",
    }

    for _, row in df.iterrows():
        result["data"].append(colum_mapping_transform(row, PROFIT_COLUMN_MAP))

    return result

def get_recent_financial_profit_statement(symbol: str) -> Dict[str, Any]:
    """
    获取A股公司利润表数据

    Args:
        symbol: 股票代码

    Returns:
        包含利润表数据的字典
    """
    result = get_financial_profit_statement_history(symbol).copy()
    result['data'] = result['data'][0] if result['data'] else {}
    return result
