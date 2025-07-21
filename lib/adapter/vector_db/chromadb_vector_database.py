#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from .vector_database_base import (
    VectorDatabaseAbstract,
    VectorRecord,
    QueryResult,
    QueryResponse,
    UpsertResponse,
    DeleteResponse,
    IndexStats
)


class ChromaDBVectorDatabase(VectorDatabaseAbstract):
    """基于ChromaDB的向量数据库实现"""
    
    def __init__(self, 
                 path: str = "./chroma_db",
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 settings: Optional[Settings] = None):
        """
        初始化ChromaDB客户端
        
        Args:
            path: 本地数据库路径（用于持久化存储）
            host: 远程ChromaDB服务器地址（可选）
            port: 远程ChromaDB服务器端口（可选）
            settings: ChromaDB配置（可选）
        """
        self.path = path
        self.host = host
        self.port = port
        
        # 初始化ChromaDB客户端
        if host and port:
            # 连接远程ChromaDB服务器
            self.client = chromadb.HttpClient(host=host, port=port)
        else:
            # 使用本地持久化存储
            if settings is None:
                settings = Settings(
                    persist_directory=path,
                    anonymized_telemetry=False
                )
            self.client = chromadb.PersistentClient(
                path=path,
                settings=settings
            )
        
        self._collections_cache = {}  # 缓存已获取的集合
    
    def _get_collection(self, name: str):
        """获取或创建集合（ChromaDB中的索引概念）"""
        if name in self._collections_cache:
            return self._collections_cache[name]
        self._collections_cache[name] = self.client.get_collection(name)
        return self._collections_cache[name]
    
    def create_index(self, name: str, dimension: int, metric: str = "cosine", **kwargs) -> bool:
        """
        创建索引（在ChromaDB中创建集合）
        
        Args:
            name: 索引名称
            dimension: 向量维度
            metric: 距离度量方式 (cosine, euclidean, dotproduct)
            **kwargs: 其他配置参数
            
        Returns:
            bool: 是否创建成功
        """
        # 映射距离度量方式
        distance_function = "cosine"  # ChromaDB默认使用cosine
        if metric == "euclidean":
            distance_function = "l2"
        elif metric == "dotproduct":
            distance_function = "ip"  # inner product
        
        # 创建集合
        collection = self.client.create_collection(
            name=name,
            metadata={
                "dimension": dimension,
                "metric": metric,
                "distance_function": distance_function
            }
        )
        
        # 缓存集合
        self._collections_cache[name] = collection
        return True
    
    def delete_index(self, name: str) -> bool:
        """
        删除索引（删除ChromaDB集合）
        
        Args:
            name: 索引名称
            
        Returns:
            bool: 是否删除成功
        """
        self.client.delete_collection(name)
        # 清理缓存
        if name in self._collections_cache:
            del self._collections_cache[name]
        return True
    
    def list_indexes(self) -> List[str]:
        """
        列出所有索引（列出所有集合）
        
        Returns:
            List[str]: 索引名称列表
        """
        collections = self.client.list_collections()
        return [collection.name for collection in collections]
    
    def describe_index(self, name: str) -> Dict[str, Any]:
        """
        获取索引详细信息
        
        Args:
            name: 索引名称
            
        Returns:
            Dict[str, Any]: 索引信息
        """
        collection = self.client.get_collection(name)
        
        # 获取集合统计信息
        count = collection.count()
        metadata = collection.metadata or {}
        
        return {
            'name': collection.name,
            'id': collection.id,
            'count': count,
            'dimension': metadata.get('dimension', 'unknown'),
            'metric': metadata.get('metric', 'cosine'),
            'distance_function': metadata.get('distance_function', 'cosine'),
            'metadata': metadata
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
            namespace: 命名空间（在ChromaDB中通过metadata实现）
            
        Returns:
            UpsertResponse: 插入响应
        """
        collection = self._get_collection(index_name)
        
        # 准备数据
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        for vector in vectors:
            ids.append(vector.id)
            embeddings.append(vector.values)
            
            # 处理元数据，添加命名空间信息
            metadata = vector.metadata.copy()
            if namespace:
                metadata['namespace'] = namespace
            
            # ChromaDB要求metadata的值必须是基本类型
            filtered_metadata = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    filtered_metadata[k] = v
                else:
                    filtered_metadata[k] = str(v)
            
            metadatas.append(filtered_metadata)
            
            # 使用文本内容作为document，如果没有则使用ID
            documents.append(
                metadata.get('text', metadata.get('content', vector.id))
            )
        
        # 执行插入/更新
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        
        return UpsertResponse(upserted_count=len(vectors))
    
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
        collection = self._get_collection(index_name)
        
        # 构建查询条件
        where_clause = {}
        if namespace:
            where_clause['namespace'] = namespace
        
        if filter_dict:
            where_clause.update(filter_dict)
        
        # 执行查询
        results = collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where_clause if where_clause else None,
            include=['distances', 'metadatas', 'documents'] + 
                    (['embeddings'] if include_values else [])
        )
        
        # 转换查询结果
        matches = []
        if results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                # ChromaDB返回距离，需要转换为相似度分数
                distance = results['distances'][0][i]
                # 对于cosine距离，相似度 = 1 - distance
                # 对于其他距离度量，可能需要不同的转换
                score = 1.0 - distance if distance <= 1.0 else 1.0 / (1.0 + distance)
                
                query_result = QueryResult(
                    id=doc_id,
                    score=score,
                    values=results['embeddings'][0][i] if include_values and 'embeddings' in results else None,
                    metadata=results['metadatas'][0][i] if include_metadata and 'metadatas' in results else {}
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
        collection = self._get_collection(index_name)
        
        # 构建删除条件
        where_clause = {}
        if namespace:
            where_clause['namespace'] = namespace
        
        # 执行删除
        collection.delete(
            ids=ids,
            where=where_clause if where_clause else None
        )
        
        return DeleteResponse(deleted_count=len(ids))
    
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
        collection = self._get_collection(index_name)
        
        # 构建查询条件
        where_clause = {}
        if namespace:
            where_clause['namespace'] = namespace
        
        # 获取向量
        results = collection.get(
            ids=ids,
            where=where_clause if where_clause else None,
            include=['embeddings', 'metadatas', 'documents']
        )
        
        # 转换结果
        result = {}
        if results['ids']:
            for i, doc_id in enumerate(results['ids']):
                result[doc_id] = VectorRecord(
                    id=doc_id,
                    values=results['embeddings'][i] if 'embeddings' in results else [],
                    metadata=results['metadatas'][i] if 'metadatas' in results else {}
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
        collection = self._get_collection(index_name)
        
        # 获取集合统计信息
        count = collection.count()
        metadata = collection.metadata or {}
        
        # 获取命名空间信息
        namespaces = {}
        # 尝试获取不同命名空间的统计信息
        # 这是一个简化的实现，实际可能需要更复杂的查询
        results = collection.get(include=['metadatas'])
        namespace_counts = {}
        
        if results['metadatas']:
            for meta in results['metadatas']:
                ns = meta.get('namespace', '')
                namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
        
        for ns, count in namespace_counts.items():
            namespaces[ns] = {'vector_count': count}
        
        return IndexStats(
            total_vector_count=count,
            dimension=metadata.get('dimension', 0),
            index_fullness=0.0,  # ChromaDB不提供此信息
            namespaces=namespaces
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
        collection = self._get_collection(index_name)
        
        # 先获取现有数据
        existing_data = collection.get(
            ids=[id],
            include=['embeddings', 'metadatas', 'documents']
        )
        
        if not existing_data['ids']:
            print(f"向量 {id} 不存在")
            return False
        
        # 准备更新数据
        update_embedding = values if values is not None else existing_data['embeddings'][0]
        update_metadata = existing_data['metadatas'][0].copy() if existing_data['metadatas'] else {}
        
        if metadata:
            update_metadata.update(metadata)
        
        if namespace:
            update_metadata['namespace'] = namespace
        
        # 过滤元数据
        filtered_metadata = {}
        for k, v in update_metadata.items():
            if isinstance(v, (str, int, float, bool)):
                filtered_metadata[k] = v
            else:
                filtered_metadata[k] = str(v)
        
        update_document = existing_data['documents'][0] if existing_data['documents'] else id
        
        # 执行更新（ChromaDB使用upsert进行更新）
        collection.upsert(
            ids=[id],
            embeddings=[update_embedding],
            metadatas=[filtered_metadata],
            documents=[update_document]
        )
        
        return True
        """
        删除命名空间中的所有向量
        
        Args:
            index_name: 索引名称
            namespace: 命名空间
            
        Returns:
            bool: 是否删除成功
        """
        collection = self._get_collection(index_name)
        
        # 构建删除条件
        where_clause = {}
        if namespace:
            where_clause['namespace'] = namespace
        
        # 获取所有匹配的ID
        results = collection.get(
            where=where_clause if where_clause else None,
            include=['metadatas']
        )
        
        if results['ids']:
            # 删除所有匹配的向量
            collection.delete(
                ids=results['ids'],
                where=where_clause if where_clause else None
            )
        
        return True
            
        """
        重置集合（删除所有数据但保留集合结构）
        
        Args:
            index_name: 索引名称
            
        Returns:
            bool: 是否重置成功
        """
        try:
            collection = self._get_collection(index_name)
            
            # 获取所有ID
            results = collection.get()
            
            if results['ids']:
                # 删除所有向量
                collection.delete(ids=results['ids'])
            
            return True
            
        except Exception as e:
            print(f"重置集合失败: {str(e)}")
            return False