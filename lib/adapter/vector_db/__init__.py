#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
向量数据库适配器模块
提供统一的向量数据库接口和多种实现
"""

from .vector_database_base import (
    VectorDatabaseAbstract,
    VectorRecord,
    QueryResult,
    QueryResponse,
    UpsertResponse,
    DeleteResponse,
    IndexStats
)

from .pinecone_vector_database import PineconeVectorDatabase
from .chromadb_vector_database import ChromaDBVectorDatabase

from .vector_database_factory import (
    create_pinecone_database,
    create_chromadb_database,
    get_default_pinecone_config,
    get_default_chromadb_config,
    create_default_vector_db
)

__all__ = [
    # 基础接口和数据类
    'VectorDatabaseAbstract',
    'VectorRecord',
    'QueryResult',
    'QueryResponse',
    'UpsertResponse',
    'DeleteResponse',
    'IndexStats',
    
    # 具体实现
    'PineconeVectorDatabase',
    'ChromaDBVectorDatabase',
    
    # 工厂类和工具函数
    'create_pinecone_database',
    'create_chromadb_database',
    'get_default_pinecone_config',
    'get_default_chromadb_config',
    'create_default_vector_db',
]