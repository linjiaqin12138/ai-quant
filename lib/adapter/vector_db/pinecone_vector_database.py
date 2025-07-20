#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException

from .vector_database_base import (
    VectorDatabaseAbstract,
    VectorRecord,
    QueryResult,
    QueryResponse,
    UpsertResponse,
    DeleteResponse,
    IndexStats
)

class PineconeVectorDatabase(VectorDatabaseAbstract):
    """基于Pinecone的向量数据库实现"""
    
    def __init__(self, api_key: str = "", environment: Dict[str, str] = {"cloud": "aws", "region": "us-east-1"}):
        """
        初始化Pinecone客户端
        
        Args:
            api_key: Pinecone API密钥
            environment: Pinecone环境（云区域）
        """
        self.api_key = api_key
        self.environment = environment
        self.pc = Pinecone(api_key=self.api_key)
        self._index_cache = {}  # 缓存已连接的索引
    
    def _get_index(self, index_name: str):
        """获取索引连接（带缓存）"""
        if index_name not in self._index_cache:
            self._index_cache[index_name] = self.pc.Index(index_name)
        return self._index_cache[index_name]
    
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
        # 默认使用Serverless规格
        spec = ServerlessSpec(**self.environment)
        
        self.pc.create_index(
            name=name,
            dimension=dimension,
            metric=metric,
            spec=spec
        )
        
        # 等待索引创建完成
        timeout = kwargs.get('timeout', 60)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            index_info = self.pc.describe_index(name)
            if index_info.status['ready']:
                return True
            time.sleep(2)
        
        return False
    
    def delete_index(self, name: str) -> bool:
        """
        删除索引
        
        Args:
            name: 索引名称
            
        Returns:
            bool: 是否删除成功
        """
        self.pc.delete_index(name)
        # 清理缓存
        if name in self._index_cache:
            del self._index_cache[name]
        return True
    
    def list_indexes(self) -> List[str]:
        """
        列出所有索引
        
        Returns:
            List[str]: 索引名称列表
        """
        indexes = self.pc.list_indexes()
        return [index.name for index in indexes]
       
    def describe_index(self, name: str) -> Dict[str, Any]:
        """
        获取索引详细信息
        
        Args:
            name: 索引名称
            
        Returns:
            Dict[str, Any]: 索引信息
        """
        index_info = self.pc.describe_index(name)
        return {
            'name': index_info.name,
            'dimension': index_info.dimension,
            'metric': index_info.metric,
            'host': index_info.host,
            'status': index_info.status,
            'spec': index_info.spec
        }
    
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
        index = self._get_index(index_name)
        
        # 转换为Pinecone格式
        pinecone_vectors = []
        for vector in vectors:
            pinecone_vector = {
                'id': vector.id,
                'values': vector.values
            }
            if vector.metadata:
                pinecone_vector['metadata'] = vector.metadata
            
            pinecone_vectors.append(pinecone_vector)
        
        # 执行插入
        response = index.upsert(vectors=pinecone_vectors, namespace=namespace)
        
        return UpsertResponse(
            upserted_count=response.get('upserted_count', len(vectors))
        )
            
    
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
        index = self._get_index(index_name)
        
        # 执行查询
        response = index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_values=include_values,
            include_metadata=include_metadata,
            filter=filter_dict
        )
        
        # 转换查询结果
        matches = []
        for match in response.matches:
            query_result = QueryResult(
                id=match.id,
                score=match.score,
                values=match.values if include_values else None,
                metadata=match.metadata if include_metadata else {}
            )
            matches.append(query_result)
        
        return QueryResponse(
            matches=matches,
            namespace=namespace
        )
            
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
        index = self._get_index(index_name)
        
        # 执行删除
        index.delete(ids=ids, namespace=namespace)
        
        return DeleteResponse(
            deleted_count=len(ids)  # Pinecone不直接返回删除数量
        )
        
    
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
        index = self._get_index(index_name)
        
        # 执行获取
        response = index.fetch(ids=ids, namespace=namespace)
        
        # 转换结果
        result = {}
        for vector_id, vector_data in response.vectors.items():
            result[vector_id] = VectorRecord(
                id=vector_id,
                values=vector_data.values,
                metadata=vector_data.metadata or {}
            )
        
        return result
    
    def get_index_stats(self, index_name: str) -> IndexStats:
        """
        获取索引统计信息
        
        Args:
            index_name: 索引名称
            
        Returns:
            IndexStats: 索引统计信息
        """
        index = self._get_index(index_name)
        
        # 获取统计信息
        stats = index.describe_index_stats()
        
        return IndexStats(
            total_vector_count=stats.total_vector_count,
            dimension=stats.dimension,
            index_fullness=stats.index_fullness,
            namespaces=stats.namespaces or {}
        )

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
        try:
            index = self._get_index(index_name)
            
            # 构建更新数据
            update_data = {'id': id}
            if values is not None:
                update_data['values'] = values
            if metadata is not None:
                update_data['metadata'] = metadata
            
            # 执行更新
            index.update(**update_data, namespace=namespace)
            
            return True
        
        except NotFoundException:
            # 如果向量不存在，返回False
            return False
    
    def delete_all(self, index_name: str, namespace: str = "") -> bool:
        """
        删除命名空间中的所有向量
        
        Args:
            index_name: 索引名称
            namespace: 命名空间
            
        Returns:
            bool: 是否删除成功
        """
        try:
            index = self._get_index(index_name)
            index.delete(delete_all=True, namespace=namespace)
            return True
        except NotFoundException:
            # 如果向量不存在，返回False
            return False