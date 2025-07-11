from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class EmbeddingRequest:
    """嵌入请求数据类"""
    input_text: Union[str, List[str]]
    model: str = "text-embedding-ada-002"
    encoding_format: str = "float"
    dimensions: Optional[int] = None


@dataclass
class EmbeddingResult:
    """嵌入结果数据类"""
    embedding: List[float]
    index: int


@dataclass
class EmbeddingResponse:
    """嵌入响应数据类"""
    data: List[EmbeddingResult]


class EmbeddingAbstract(ABC):
    """嵌入服务提供者抽象基类"""
    @abstractmethod
    def create_embedding(
        self,
        input_text: Union[str, List[str]],
        model: str = "text-embedding-ada-002",
        encoding_format: str = "float",
        dimensions: Optional[int] = None
    ) -> EmbeddingResponse:
        """
        创建文本嵌入
        
        Args:
            input_text: 单个文本或文本列表
            model: 模型名称
            encoding_format: 编码格式，默认为"float"
            dimensions: 向量维度（可选）
            
        Returns:
            EmbeddingResponse: 嵌入响应对象
        """
        pass