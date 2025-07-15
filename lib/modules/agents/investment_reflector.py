#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
投资决策反思工具
基于向量数据库的智能投资决策反思分析工具，支持多时间尺度的决策复盘和经验总结
"""
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from textwrap import dedent
import traceback

from lib.adapter.llm import get_llm
from lib.adapter.llm.interface import LlmAbstract
from lib.logger import logger
from lib.modules.agent import get_agent
from lib.adapter.vector_db import (
    VectorDatabaseAbstract,
    VectorRecord,
    create_default_vector_db
)
from lib.adapter.embedding import PaoluzEmbedding
from lib.utils.string import random_id

SYS_PROMPT = """
你是一名资深金融分析师，负责回顾交易决策/分析，并提供全面、逐步的分析。
你的目标是对投资决策给出详细见解，并突出改进机会，严格遵循以下指南：

## 推理分析：
对每个交易决策，判断其正确与否。正确的决策会带来收益增加，错误的决策则相反。
分析每次成功或失误的影响因素。需考虑：
- 市场情报
- 技术指标
- 技术信号
- 价格走势分析
- 整体市场数据分析
- 新闻分析
- 社交媒体与情绪分析
- 基本面数据分析
- 在决策过程中权衡各因素的重要性

## 改进建议：
对于任何错误的决策，提出修正建议以最大化收益。
提供详细的改进措施清单，包括具体建议（如在某日期将决策从HOLD改为BUY等）。

## 总结：
总结从成功与失误中获得的经验教训。
强调这些经验如何应用于未来的交易场景，并将类似情境联系起来以迁移所学知识。

## 关键信息提炼：
从总结中提炼出不超过1000个token的简明句子。
确保该简明句子能抓住经验教训和推理的核心，便于参考。

请严格遵循上述指令，确保输出内容详细、准确且可操作。
"""

@dataclass
class ReflectionData:
    """反思数据结构"""
    situation: str = ""  # 综合情况描述（包含市场研究、情绪、新闻等）
    analysis_opinion: str = ""  # 分析观点
    days_past: int = 1  # 距离决策日期过去的天数
    return_loss_percentage: float = 0.0  # 从决策日期过去days_past天后的价格变动百分比
    decision_date: datetime = field(default_factory=datetime.now)  # 决策日期
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "situation": self.situation,
            "analysis_opinion": self.analysis_opinion,
            "days_past": self.days_past,
            "return_loss_percentage": self.return_loss_percentage,
            "decision_date": self.decision_date.isoformat(),
        }


@dataclass
class ReflectionResult:
    """反思结果"""
    reflection_content: str = ""  # 完整的反思内容
    success: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "reflection_content": self.reflection_content,
            "success": self.success,
        }


class InvestmentReflector:
    """
    投资决策反思工具
    
    基于向量数据库的智能投资决策反思分析工具，使用AI进行深度决策复盘和经验总结。
    支持对同一决策在不同时间尺度（1天/7天/30天）下进行反思分析。
    """
    
    def __init__(
        self,
        llm: LlmAbstract,
        vector_db: Optional[VectorDatabaseAbstract] = None,
        embedding_service: Optional[PaoluzEmbedding] = None,
        index_name: str = "reflection-memories",
        embedding_dimension: int = 1536
    ):
        """
        初始化投资决策反思工具
        
        Args:
            llm: LLM实例
            vector_db: 向量数据库实例，如不提供则自动创建
            embedding_service: 嵌入服务实例，如不提供则自动创建
            index_name: 向量数据库索引名称
            embedding_dimension: 嵌入向量维度
        """
        self.llm = llm
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension
        
        # 初始化Agent
        self.agent = get_agent(llm=self.llm)
        self.agent.set_system_prompt(SYS_PROMPT)
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        # 初始化向量数据库
        if self.vector_db is None:
            self.vector_db = create_default_vector_db(default_path="./data/investment_reflection_db")

        # 初始化嵌入服务
        if embedding_service is None:
            self.embedding_service = PaoluzEmbedding()

        # 确保索引存在
        self._ensure_index_exists()
        
        logger.info(f"InvestmentReflector已初始化，使用模型: {self.llm.provider}/{self.llm.model}")

    def _ensure_index_exists(self):
        """确保向量数据库索引存在"""
        try:
            # 检查索引是否存在
            existing_indexes = self.vector_db.list_indexes()
            if self.index_name not in existing_indexes:
                logger.info(f"创建向量数据库索引: {self.index_name}")
                success = self.vector_db.create_index(
                    name=self.index_name,
                    dimension=self.embedding_dimension,
                    metric="cosine"
                )
                if not success:
                    raise Exception(f"创建索引 {self.index_name} 失败")
            else:
                logger.info(f"索引 {self.index_name} 已存在")
        except Exception as e:
            logger.error(f"确保索引存在时发生错误: {e}")
            raise
    
    def reflect_on_decision(self, reflection_data: ReflectionData) -> ReflectionResult:
        """
        对投资决策进行反思分析
        
        Args:
            reflection_data: 反思数据，包含市场情况、分析观点、时间尺度等信息
            
        Returns:
            ReflectionResult: 反思结果，包含完整的AI分析内容
        """
        try:
            # 构建反思提示词
            reflection_prompt = self._build_reflection_prompt(reflection_data)
            
            # 调用Agent进行反思
            logger.info(f"开始对决策进行反思（时间尺度：{reflection_data.days_past}天）...")
            reflection_response = self.agent.ask(reflection_prompt)
            
            # 直接使用完整响应作为反思结果
            result = ReflectionResult(
                reflection_content=reflection_response,
                success=True
            )
            
            # 存储反思结果到向量数据库
            self._store_reflection_to_vector_db(reflection_data, result)
            
            logger.info(f"完成决策反思")
            return result
            
        except Exception as e:
            logger.error(f"反思决策失败: {e}")
            logger.debug(traceback.format_exc())
            return ReflectionResult(
                reflection_content="反思过程中发生错误",
                success=False
            )
    
    def _build_reflection_prompt(self, data: ReflectionData) -> str:
        """构建反思提示词"""
        
        # 确定时间尺度描述
        time_scale = f"{data.days_past}天后"
        
        # 确定结果描述
        if data.return_loss_percentage > 0:
            result_desc = f"{time_scale}产生了{data.return_loss_percentage:.2%}的正收益"
        elif data.return_loss_percentage < 0:
            result_desc = f"{time_scale}产生了{abs(data.return_loss_percentage):.2%}的亏损"
        else:
            result_desc = f"{time_scale}收益为零"

        prompt = dedent(f"""
            请对以下交易决策进行深入的反思分析：

            ## 交易基本信息
            - 决策日期: {data.decision_date.strftime('%Y-%m-%d')}
            - 观察时间尺度: {time_scale}
            - 价格变动: {data.return_loss_percentage:.2%}

            ## 市场情况与背景
            {data.situation}

            ## 当时的分析观点
            {data.analysis_opinion}

            ## 实际结果
            {result_desc}

            ## 分析要求
            请特别关注以下几点：
            1. 在{time_scale}这个时间尺度下，该决策的有效性如何？
            2. 短期（1天）、中期（1周）、长期（1个月）的投资逻辑是否有所不同？
            3. 市场情况和分析观点在这个时间尺度下的预测准确性如何？
            4. 针对这个特定时间尺度，应该如何优化决策策略？

            请基于以上信息，按照系统提示词的要求进行全面的反思分析。
        """).strip()
        
        return prompt
    
    def _store_reflection_to_vector_db(self, reflection_data: ReflectionData, result: ReflectionResult):
        """将反思结果存储到向量数据库"""
        try:
            # 使用situation字段生成embedding
            logger.info("正在生成embedding向量...")
            embedding_response = self.embedding_service.create_embedding([reflection_data.situation])
            
            if not embedding_response.data:
                raise Exception("生成embedding失败")
            
            embedding_vector = embedding_response.data[0].embedding
            
            # 创建元数据，将反思内容存储在metadata中
            metadata = {
                "type": "reflection",
                "decision_date": reflection_data.decision_date.isoformat(),
                "days_past": reflection_data.days_past,
                "return_loss_percentage": reflection_data.return_loss_percentage,
                "created_at": datetime.now().isoformat(),
                "success": result.success,
                "provider": self.llm.provider,
                "model": self.llm.model,
                "situation": reflection_data.situation,
                "analysis_opinion": reflection_data.analysis_opinion,
                "reflection_content": result.reflection_content  # 将反思内容存储在metadata中
            }
            
            # 创建向量记录
            vector_record = VectorRecord(
                id=random_id(),
                values=embedding_vector,
                metadata=metadata
            )
            
            # 存储到向量数据库
            logger.info("正在存储到向量数据库...")
            upsert_response = self.vector_db.upsert(
                index_name=self.index_name,
                vectors=[vector_record]
            )
            
            if upsert_response.upserted_count > 0:
                logger.info(f"成功存储反思结果到向量数据库")
            else:
                logger.warning("存储反思结果到向量数据库时没有新增记录")
                
        except Exception as e:
            logger.error(f"存储反思结果到向量数据库失败: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def search_similar_reflections(
        self, 
        situation: str, 
        top_k: int = 5,
        days_past_filter: Optional[int] = None,
        return_percentage_filter: Optional[Tuple[float, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似的反思记录
        
        Args:
            situation: 查询的市场情况描述
            top_k: 返回结果数量
            days_past_filter: 按观察天数过滤，如果指定则只返回该天数的记录
            return_percentage_filter: 收益率过滤范围 (min, max)
            
        Returns:
            相似反思记录列表
        """
        try:
            # 生成查询向量
            logger.info(f"正在生成查询embedding...")
            embedding_response = self.embedding_service.create_embedding([situation])
            
            if not embedding_response.data:
                logger.error("生成查询embedding失败")
                return []
            
            query_vector = embedding_response.data[0].embedding
            
            # 构建过滤条件
            filter_dict = {"type": "reflection"}
            
            if days_past_filter is not None:
                filter_dict["days_past"] = days_past_filter
                
            if return_percentage_filter:
                min_return, max_return = return_percentage_filter
                filter_dict["return_loss_percentage"] = {"$gte": min_return, "$lte": max_return}

            # 执行向量搜索
            logger.info(f"正在搜索相似向量...")
            query_response = self.vector_db.query(
                index_name=self.index_name,
                vector=query_vector,
                top_k=top_k,
                include_values=False,
                include_metadata=True,
                filter_dict=filter_dict
            )
            
            # 转换搜索结果
            results = []
            for match in query_response.matches:
                result = {
                    "id": match.id,
                    "score": match.score,
                    "similarity": match.score,  # 兼容旧接口
                    "metadata": match.metadata or {},
                    "content": match.metadata.get("reflection_content", "") if match.metadata else ""
                }
                results.append(result)
            
            logger.info(f"搜索到 {len(results)} 条相似反思记录")
            return results
            
        except Exception as e:
            logger.error(f"搜索相似反思记录失败: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    # def get_reflection_statistics(self) -> Dict[str, Any]:
    #     """获取反思数据库统计信息"""
    #     try:
    #         stats = self.vector_db.get_index_stats(self.index_name)
    #         return {
    #             "total_reflections": stats.total_vector_count,
    #             "vector_dimension": stats.dimension,
    #             "index_fullness": stats.index_fullness,
    #             "namespaces": stats.namespaces
    #         }
    #     except Exception as e:
    #         logger.error(f"获取反思统计信息失败: {e}")
    #         return {}
    
    # def clear_all_reflections(self) -> bool:
    #     """清空所有反思记录"""
    #     try:
    #         success = self.vector_db.delete_all(self.index_name)
    #         if success:
    #             logger.info("已清空所有反思记录")
    #         return success
    #     except Exception as e:
    #         logger.error(f"清空反思记录失败: {e}")
    #         return False
    
    # def export_reflections_to_json(self, output_path: str) -> bool:
    #     """
    #     导出反思记录到JSON文件
        
    #     Args:
    #         output_path: 输出文件路径
            
    #     Returns:
    #         是否导出成功
    #     """
    #     try:
    #         # 获取所有反思记录
    #         all_reflections = self.search_similar_reflections(
    #             situation="反思记录",
    #             top_k=1000  # 获取大量记录
    #         )
            
    #         # 写入JSON文件
    #         with open(output_path, 'w', encoding='utf-8') as f:
    #             json.dump(all_reflections, f, ensure_ascii=False, indent=2)
            
    #         logger.info(f"成功导出 {len(all_reflections)} 条反思记录到 {output_path}")
    #         return True
            
    #     except Exception as e:
    #         logger.error(f"导出反思记录失败: {e}")
    #         return False
