#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Optional

from lib.config import get_default_chromadb_config, get_default_pinecone_config
from lib.logger import logger

from .vector_database_base import VectorDatabaseAbstract

# 便捷函数
def create_pinecone_database(
    api_key: str,
    environment: Dict[str, str] = {"cloud": "aws", "region": "us-east-1"}
) -> VectorDatabaseAbstract:
    """
    创建Pinecone向量数据库实例的便捷函数
    
    Args:
        api_key: Pinecone API密钥
        environment: 环境
        
    Returns:
        PineconeVectorDatabase: Pinecone数据库实例
    """
    try:
        from .pinecone_vector_database import PineconeVectorDatabase
        return PineconeVectorDatabase(**{
            "api_key": api_key,
            "environment": environment
        })
    except ImportError:
        logger.error("PineconeVectorDatabase模块导入失败")
        raise


def create_chromadb_database(
    path: str = "./chroma_db",
    host: Optional[str] = None,
    port: Optional[int] = None
) -> VectorDatabaseAbstract:
    """
    创建ChromaDB向量数据库实例的便捷函数
    
    Args:
        path: 本地数据库路径
        host: 远程服务器地址
        port: 远程服务器端口
        instance_name: 实例名称
        
    Returns:
        ChromaDBVectorDatabase: ChromaDB数据库实例
    """
    config = {
        "path": path,
        "host": host,
        "port": port
    }
    try:
        from .chromadb_vector_database import ChromaDBVectorDatabase
        return ChromaDBVectorDatabase(
            path=config.get("path", "./chroma_db"),
            host=config.get("host"),
            port=config.get("port"),
            settings=config.get("settings")
        )
    except ImportError:
        logger.error("ChromaDBVectorDatabase模块导入失败")
        raise

def create_default_vector_db() -> VectorDatabaseAbstract:
    """
    创建默认向量数据库实例
    
    优先尝试使用Pinecone，如果失败则回退到ChromaDB
    
    Returns:
        VectorDatabaseAbstract: 向量数据库实例
        
    Raises:
        Exception: 如果所有数据库都创建失败
    """
    try:
        # 优先尝试使用Pinecone
        pinecone_config = get_default_pinecone_config()
        if pinecone_config.get("api_key"):
            logger.info("使用Pinecone作为默认向量数据库")
            return create_pinecone_database(**pinecone_config)
    except Exception:
        # 忽略Pinecone创建失败的异常
        pass
    
    logger.warning("Pinecone创建失败，尝试使用ChromaDB作为默认向量数据库")
    # 回退到ChromaDB
    try:
        chromadb_config = get_default_chromadb_config()
        logger.info("使用ChromaDB作为默认向量数据库")
        return create_chromadb_database(**chromadb_config)
    except Exception as e:
        raise Exception(f"创建默认向量数据库失败: {e}")