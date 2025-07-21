#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class VectorRecord:
    """向量记录数据类"""
    id: str
    values: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class QueryResult:
    """查询结果数据类"""
    id: str
    score: float
    values: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResponse:
    """查询响应数据类"""
    matches: List[QueryResult]
    namespace: str = ""


@dataclass
class UpsertResponse:
    """插入/更新响应数据类"""
    upserted_count: int


@dataclass
class DeleteResponse:
    """删除响应数据类"""
    deleted_count: int


@dataclass

class IndexStats:
    """
    索引统计信息数据类

    Attributes:
        total_vector_count (int): 向量总数，表示索引中存储的向量数量。
        dimension (int): 向量维度，表示每个向量的特征维数。
        index_fullness (float): 索引填充度，表示索引的使用率或占用比例，范围通常为0到1。
        namespaces (Dict[str, Dict[str, Any]]): 命名空间信息，键为命名空间名称，值为该命名空间的详细统计信息字典。
    """
    total_vector_count: int
    dimension: int
    index_fullness: float
    namespaces: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class VectorDatabaseAbstract(ABC):
    """向量数据库抽象基类"""
    
    @abstractmethod
    def create_index(self, name: str, dimension: int, metric: str = "cosine", **kwargs) -> bool:
        """
        创建索引
        
        Args:
            name: 索引名称
            dimension: 向量维度
            metric: 距离度量方式 (cosine, euclidean, dotproduct)
            **kwargs: 其他配置参数
            
        Returns:
            bool: 是否创建成功
        """
        pass
    
    @abstractmethod
    def delete_index(self, name: str) -> bool:
        """
        删除索引
        
        Args:
            name: 索引名称
            
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abstractmethod
    def list_indexes(self) -> List[str]:
        """
        列出所有索引
        
        Returns:
            List[str]: 索引名称列表
        """
        pass
    
    @abstractmethod
    def describe_index(self, name: str) -> Dict[str, Any]:
        """
        获取索引详细信息
        
        Args:
            name: 索引名称
            
        Returns:
            Dict[str, Any]: 索引信息
        """
        pass
    
    @abstractmethod
    def upsert(self, 
               index_name: str, 
               vectors: List[VectorRecord], 
               namespace: str = "") -> UpsertResponse:
        """
        插入或更新向量
        
        Args:
            index_name: 索引名称
            vectors: 向量记录列表
            namespace: 命名空间
            
        Returns:
            UpsertResponse: 插入响应
        """
        pass
    
    @abstractmethod
    def query(self, 
              index_name: str, 
              vector: List[float], 
              top_k: int = 10,
              namespace: str = "",
              include_values: bool = False,
              include_metadata: bool = True,
              filter_dict: Optional[Dict[str, Any]] = None) -> QueryResponse:
        """
        查询相似向量
        
        Args:
            index_name: 索引名称
            vector: 查询向量
            top_k: 返回结果数量
            namespace: 命名空间
            include_values: 是否包含向量值
            include_metadata: 是否包含元数据
            filter_dict: 过滤条件
            
        Returns:
            QueryResponse: 查询响应
        """
        pass
    
    @abstractmethod
    def delete(self, 
               index_name: str, 
               ids: List[str], 
               namespace: str = "") -> DeleteResponse:
        """
        删除向量
        
        Args:
            index_name: 索引名称
            ids: 要删除的向量ID列表
            namespace: 命名空间
            
        Returns:
            DeleteResponse: 删除响应
        """
        pass
    
    @abstractmethod
    def fetch(self, 
              index_name: str, 
              ids: List[str], 
              namespace: str = "") -> Dict[str, VectorRecord]:
        """
        获取指定ID的向量
        
        Args:
            index_name: 索引名称
            ids: 向量ID列表
            namespace: 命名空间
            
        Returns:
            Dict[str, VectorRecord]: ID到向量记录的映射
        """
        pass
    
    @abstractmethod
    def get_index_stats(self, index_name: str) -> IndexStats:
        """
        获取索引统计信息
        
        Args:
            index_name: 索引名称
            
        Returns:
            IndexStats: 索引统计信息
        """
        pass
    
    @abstractmethod
    def update(self, 
               index_name: str, 
               id: str, 
               values: Optional[List[float]] = None,
               metadata: Optional[Dict[str, Any]] = None,
               namespace: str = "") -> bool:
        """
        更新向量
        
        Args:
            index_name: 索引名称
            id: 向量ID
            values: 新的向量值
            metadata: 新的元数据
            namespace: 命名空间
            
        Returns:
            bool: 是否更新成功
        """
        pass