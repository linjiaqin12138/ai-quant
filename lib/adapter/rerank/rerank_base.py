from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class RerankRequest:
    """重排序请求数据类"""
    query: str
    documents: List[str]
    model: str = "rerank-multilingual-v3.0"
    top_k: Optional[int] = None
    return_documents: bool = True


@dataclass
class RerankResult:
    """重排序结果数据类"""
    index: int
    relevance_score: float
    document: Optional[str] = None


@dataclass
class RerankResponse:
    """重排序响应数据类"""
    results: List[RerankResult]
    model: str
    usage: Optional[Dict[str, Any]] = None


class RerankAbstract(ABC):
    """重排序服务提供者抽象基类"""
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[str],
        model: str = "rerank-multilingual-v3.0",
        top_k: Optional[int] = None,
        return_documents: bool = True
    ) -> RerankResponse:
        """
        对文档列表根据查询进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表
            model: 模型名称
            top_k: 返回前k个结果，None表示返回所有
            return_documents: 是否在结果中返回文档内容
            
        Returns:
            RerankResponse: 重排序响应对象
        """
        pass
