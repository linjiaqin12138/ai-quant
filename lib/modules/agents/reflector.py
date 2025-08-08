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

from lib.adapter.embedding.openai_compatible_embedding import OpenAICompatibleEmbedding
from lib.adapter.llm.interface import LlmAbstract
from lib.logger import logger
from lib.modules.agent import get_agent
from lib.adapter.vector_db import (
    VectorDatabaseAbstract,
    VectorRecord,
    create_default_vector_db
)
from lib.adapter.embedding import EmbeddingAbstract, create_default_embedding_service
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
    situation: str = ""  # 面对的情况描述
    analysis_opinion: str = ""  # 分析观点
    decision: str = "" # 决策内容
    decision_result: str = "" # 决策结果（如收益、亏损等）


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
        embedding_service: Optional[EmbeddingAbstract] = None,
        index_name: str = "reflection-memories",
        namespace: str = "investment_reflection",
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
        self.namespace = namespace
        self.embedding_dimension = embedding_dimension

        # 初始化Agent
        self.agent = get_agent(llm=self.llm)
        self.agent.set_system_prompt(SYS_PROMPT)
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        # 初始化向量数据库
        if self.vector_db is None:
            self.vector_db = create_default_vector_db()

        # 初始化嵌入服务
        if embedding_service is None:
            self.embedding_service = create_default_embedding_service()

        # 确保索引存在
        self._ensure_index_exists()
        
        logger.info(f"InvestmentReflector已初始化，使用模型: {self.llm.provider}/{self.llm.model}")

    def _ensure_index_exists(self):
        """确保向量数据库索引存在"""
        # 检查索引是否存在
        existing_indexes = self.vector_db.list_indexes()
        if self.index_name not in existing_indexes:
            logger.info(f"创建向量数据库索引: {self.index_name}")
            self.vector_db.create_index(
                name=self.index_name,
                dimension=self.embedding_dimension,
                metric="cosine"
            )
        else:
            logger.info(f"索引 {self.index_name} 已存在")

    def reflect_on_decision(self, reflection_data: ReflectionData) -> str:
        """
        对投资决策进行反思分析
        
        Args:
            reflection_data: 反思数据，包含市场情况、分析观点、决策、决策结果等信息
            
        Returns:
            str: 反思结果，包含完整的AI分析内容
        """
        reflection_prompt = self._build_reflection_prompt(reflection_data)
            
        # 调用Agent进行反思
        logger.info(f"开始对决策进行反思...")
        reflection_response = self.agent.ask(reflection_prompt)
        # 存储反思结果到向量数据库
        self._store_reflection_to_vector_db(reflection_data, reflection_response)
        logger.info(f"完成决策反思")

        return reflection_response

    def _build_reflection_prompt(self, data: ReflectionData) -> str:
        """构建反思提示词"""

        prompt = f"""
        请对以下决策分析进行深入的反思：

        ## 市场情况与背景
        {data.situation}

        ## 当时的分析观点
        {data.analysis_opinion}

        ## 当时的决策
        {data.decision}

        ## 决策结果
        {data.decision_result}

        请基于以上信息，按照系统提示词的要求进行全面的反思分析。
        """
        
        return prompt
    
    def _store_reflection_to_vector_db(self, reflection_data: ReflectionData, reflection_content: str):
        """将反思结果存储到向量数据库"""
        # 使用situation字段生成embedding
        logger.info("正在生成embedding向量...")
        embedding_response = self.embedding_service.create_embedding([reflection_data.situation])
        
        embedding_vector = embedding_response.data[0].embedding
        
        # 创建元数据，将反思内容存储在metadata中
        metadata = {
            # "type": "reflection",
            "created_at": datetime.now().isoformat(),
            "provider": self.llm.provider,
            "model": self.llm.model,
            "situation": reflection_data.situation,
            "analysis_opinion": reflection_data.analysis_opinion,
            "decision": reflection_data.decision,
            "decision_result": reflection_data.decision_result,
            "reflection_content": reflection_content
        }
        
        # 创建向量记录
        vector_record = VectorRecord(
            id=random_id(),
            values=embedding_vector,
            metadata=metadata
        )
        
        # 存储到向量数据库
        logger.info("正在存储到向量数据库...")
        self.vector_db.upsert(
            index_name=self.index_name,
            vectors=[vector_record],
            namespace=self.namespace
        )

    def search_similar_reflections(
        self, 
        situation: str, 
        top_k: int = 5
    ) -> List[str]:
        """
        搜索相似的反思记录
        
        Args:
            situation: 查询的市场情况描述
            top_k: 返回结果数量
            
        Returns:
            相似反思记录列表
        """
        # 生成查询向量
        logger.info(f"正在生成回忆反思embedding...")
        embedding_response = self.embedding_service.create_embedding([situation])
        query_vector = embedding_response.data[0].embedding
        # 构建过滤条件
    
        # 执行向量搜索
        logger.info(f"正在搜索相似向量...")
        query_response = self.vector_db.query(
            index_name=self.index_name,
            vector=query_vector,
            top_k=top_k,
            include_values=False,
            include_metadata=True,
            namespace=self.namespace
        )
        # 转换搜索结果
        results = []
        for match in query_response.matches:
            results.append(match.metadata.get("reflection_content", ""))

        logger.info(f"搜索到 {len(results)} 条相似反思记录")
        return results
