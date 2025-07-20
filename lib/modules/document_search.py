#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文档搜索模块
提供基于向量数据库和嵌入模型的文档搜索和管理功能
"""

import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field

from lib.logger import logger
from lib.adapter.vector_db import (
    VectorDatabaseAbstract,
    VectorRecord,
    create_default_vector_db
)
from lib.adapter.embedding import (
    EmbeddingAbstract,
    PaoluzEmbedding,
)
from lib.adapter.lock import with_lock
from lib.tools.cache_decorator import use_cache


@dataclass
class DocumentInfo:
    """文档信息数据类"""
    id: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentInfo':
        """从字典创建实例"""
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class SearchResult:
    """搜索结果数据类"""
    document: DocumentInfo
    score: float
    similarity: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document": self.document.to_dict(),
            "score": self.score,
            "similarity": self.similarity
        }


@dataclass
class DocumentChunk:
    """文档分块数据类"""
    id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata
        }


class DocumentSearch:
    """
    文档搜索类
    提供基于向量数据库和嵌入模型的文档搜索和管理功能
    """
    
    def __init__(
        self,
        vector_db: Optional[VectorDatabaseAbstract] = None,
        embedding_service: Optional[EmbeddingAbstract] = None,
        index_name: str = "document-search",
        embedding_dimension: int = 1536,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        auto_create_index: bool = True
    ):
        """
        初始化文档搜索服务
        
        Args:
            vector_db: 向量数据库实例，如果为None则使用默认配置
            embedding_service: 嵌入服务实例，如果为None则使用PaoluzEmbedding
            index_name: 索引名称
            embedding_dimension: 嵌入向量维度
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
            auto_create_index: 是否自动创建索引
        """
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        # 初始化向量数据库
        if self.vector_db is None:
            self.vector_db = create_default_vector_db(default_path="./chromadb")
   
        # 初始化嵌入服务
        if self.embedding_service is None:
            self.embedding_service = PaoluzEmbedding()
            
        # 自动创建索引
        if auto_create_index:
            self._ensure_index_exists()
    
    def _ensure_index_exists(self) -> None:
        """确保索引存在"""
        try:
            existing_indexes = self.vector_db.list_indexes()
            if self.index_name not in existing_indexes:
                logger.info(f"创建索引: {self.index_name}")
                self.vector_db.create_index(
                    name=self.index_name,
                    dimension=self.embedding_dimension,
                    metric="cosine"
                )
        except Exception as e:
            logger.error(f"创建索引失败: {e}")
            raise
    
    def _generate_document_id(self, title: str, content: str) -> str:
        """生成文档ID"""
        content_hash = hashlib.md5(f"{title}{content}".encode()).hexdigest()
        return f"doc_{content_hash}"
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 要分块的文本
            
        Returns:
            List[str]: 分块后的文本列表
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # 尝试在句号、感叹号或问号处分割
            chunk = text[start:end]
            for i in range(len(chunk) - 1, -1, -1):
                if chunk[i] in '.!?。！？':
                    end = start + i + 1
                    break
            
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        
        return chunks
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本嵌入
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        try:
            response = self.embedding_service.create_embedding(texts)
            embeddings = [result.embedding for result in response.data]
            logger.info(f"成功获取 {len(embeddings)} 个嵌入向量")
            return embeddings
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            raise
    
    def add_document(
        self,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ) -> DocumentInfo:
        """
        添加文档到搜索索引
        
        Args:
            title: 文档标题
            content: 文档内容
            metadata: 元数据
            document_id: 文档ID，如果为None则自动生成
            
        Returns:
            DocumentInfo: 文档信息
        """
        if document_id is None:
            document_id = self._generate_document_id(title, content)
        
        if metadata is None:
            metadata = {}
        
        # 创建文档信息
        document = DocumentInfo(
            id=document_id,
            title=title,
            content=content,
            metadata=metadata
        )
        
        # 分块处理
        chunks = self._chunk_text(content)
        logger.info(f"文档 {title} 分为 {len(chunks)} 个块")
        
        # 获取嵌入向量
        embeddings = self._get_embeddings(chunks)
        
        # 创建向量记录
        vector_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{document_id}_chunk_{i}"
            vector_record = VectorRecord(
                id=chunk_id,
                values=embedding,
                metadata={
                    "document_id": document_id,
                    "title": title,
                    "content": chunk,
                    "chunk_index": i,
                    "chunk_total": len(chunks),
                    "created_at": document.created_at.isoformat(),
                    **metadata
                }
            )
            vector_records.append(vector_record)
        
        # 插入向量数据库
        try:
            response = self.vector_db.upsert(
                index_name=self.index_name,
                vectors=vector_records
            )
            logger.info(f"成功插入 {response.upserted_count} 个向量")
        except Exception as e:
            logger.error(f"插入向量失败: {e}")
            raise
        
        return document
    
    def search_documents(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        include_content: bool = True,
        score_threshold: float = 0.0
    ) -> List[SearchResult]:
        """
        搜索文档
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
            include_content: 是否包含文档内容
            score_threshold: 分数阈值
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        # 获取查询嵌入
        query_embedding = self._get_embeddings([query])[0]
        
        # 执行向量搜索
        try:
            response = self.vector_db.query(
                index_name=self.index_name,
                vector=query_embedding,
                top_k=top_k * 2,  # 获取更多结果以便去重
                include_metadata=True,
                filter_dict=filter_metadata
            )
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            raise
        
        # 处理搜索结果
        document_scores = {}
        for match in response.matches:
            if match.score < score_threshold:
                continue
                
            doc_id = match.metadata.get("document_id")
            if doc_id not in document_scores:
                document_scores[doc_id] = {
                    "max_score": match.score,
                    "total_score": match.score,
                    "chunk_count": 1,
                    "best_match": match
                }
            else:
                document_scores[doc_id]["total_score"] += match.score
                document_scores[doc_id]["chunk_count"] += 1
                if match.score > document_scores[doc_id]["max_score"]:
                    document_scores[doc_id]["max_score"] = match.score
                    document_scores[doc_id]["best_match"] = match
        
        # 构建搜索结果
        results = []
        for doc_id, scores in document_scores.items():
            best_match = scores["best_match"]
            
            # 创建文档信息
            document = DocumentInfo(
                id=doc_id,
                title=best_match.metadata.get("title", ""),
                content=best_match.metadata.get("content", "") if include_content else "",
                metadata={k: v for k, v in best_match.metadata.items() 
                         if k not in ["document_id", "title", "content", "chunk_index", "chunk_total"]},
                created_at=datetime.fromisoformat(best_match.metadata.get("created_at", datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(best_match.metadata.get("updated_at", datetime.now().isoformat()))
            )
            
            # 计算相似度分数
            avg_score = scores["total_score"] / scores["chunk_count"]
            similarity = (scores["max_score"] + avg_score) / 2
            
            result = SearchResult(
                document=document,
                score=scores["max_score"],
                similarity=similarity
            )
            results.append(result)
        
        # 按相似度排序并返回指定数量
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]
    
    def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 查找相关的块
            response = self.vector_db.query(
                index_name=self.index_name,
                vector=[0.0] * self.embedding_dimension,  # 使用零向量
                top_k=1000,  # 获取足够多的结果
                filter_dict={"document_id": document_id},
                include_metadata=True
            )
            
            # 收集要删除的ID
            chunk_ids = [match.id for match in response.matches]
            
            if not chunk_ids:
                logger.warning(f"未找到文档 {document_id} 的任何块")
                return False
            
            # 删除向量
            delete_response = self.vector_db.delete(
                index_name=self.index_name,
                ids=chunk_ids
            )
            
            logger.info(f"成功删除文档 {document_id} 的 {delete_response.deleted_count} 个块")
            return delete_response.deleted_count > 0
            
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    
    def update_document(
        self,
        document_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DocumentInfo]:
        """
        更新文档
        
        Args:
            document_id: 文档ID
            title: 新标题
            content: 新内容
            metadata: 新元数据
            
        Returns:
            Optional[DocumentInfo]: 更新后的文档信息
        """
        # 先删除旧文档
        if not self.delete_document(document_id):
            logger.error(f"删除旧文档 {document_id} 失败")
            return None
        
        # 添加新文档
        if title is not None and content is not None:
            return self.add_document(
                title=title,
                content=content,
                metadata=metadata,
                document_id=document_id
            )
        
        logger.error("更新文档需要提供标题和内容")
        return None
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        Returns:
            Dict[str, Any]: 索引统计信息
        """
        try:
            stats = self.vector_db.get_index_stats(self.index_name)
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            logger.error(f"获取索引统计信息失败: {e}")
            return {}
    
    def clear_index(self) -> bool:
        """
        清空索引
        
        Returns:
            bool: 是否成功
        """
        try:
            # 删除索引
            success = self.vector_db.delete_index(self.index_name)
            if success:
                # 重新创建索引
                self._ensure_index_exists()
                logger.info(f"成功清空索引 {self.index_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"清空索引失败: {e}")
            return False


# 创建默认实例
# document_search = DocumentSearch()