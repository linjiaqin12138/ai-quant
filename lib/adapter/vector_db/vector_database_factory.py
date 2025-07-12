#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional
from enum import Enum
from .vector_database_base import VectorDatabaseAbstract
from .pinecone_vector_database import PineconeVectorDatabase
from .chromadb_vector_database import ChromaDBVectorDatabase


class VectorDatabaseType(Enum):
    """支持的向量数据库类型"""
    PINECONE = "pinecone"
    CHROMADB = "chromadb"
    # 可以在这里添加其他向量数据库类型
    # WEAVIATE = "weaviate"
    # QDRANT = "qdrant"


class VectorDatabaseFactory:
    """向量数据库工厂类"""
    
    _instances: Dict[str, VectorDatabaseAbstract] = {}
    
    @classmethod
    def create_database(
        cls,
        db_type: VectorDatabaseType,
        config: Dict[str, Any],
        instance_name: Optional[str] = None
    ) -> VectorDatabaseAbstract:
        """
        创建向量数据库实例
        
        Args:
            db_type: 数据库类型
            config: 配置参数
            instance_name: 实例名称（可选，用于缓存）
            
        Returns:
            VectorDatabaseAbstract: 向量数据库实例
        """
        
        # 生成实例缓存键
        cache_key = instance_name or f"{db_type.value}_{hash(str(sorted(config.items())))}"
        
        # 检查是否已有缓存实例
        if cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # 根据类型创建实例
        if db_type == VectorDatabaseType.PINECONE:
            instance = cls._create_pinecone_database(config)
        elif db_type == VectorDatabaseType.CHROMADB:
            instance = cls._create_chromadb_database(config)
        else:
            raise ValueError(f"不支持的向量数据库类型: {db_type}")
        
        # 缓存实例
        cls._instances[cache_key] = instance
        return instance
    
    @classmethod
    def _create_pinecone_database(cls, config: Dict[str, Any]) -> PineconeVectorDatabase:
        """
        创建Pinecone数据库实例
        
        Args:
            config: 配置参数
            
        Returns:
            PineconeVectorDatabase: Pinecone数据库实例
        """
        required_keys = ["api_key"]
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            raise ValueError(f"Pinecone配置缺少必需参数: {missing_keys}")
        
        return PineconeVectorDatabase(
            api_key=config["api_key"],
            environment=config.get("environment", "us-east-1-aws")
        )
    
    @classmethod
    def _create_chromadb_database(cls, config: Dict[str, Any]) -> ChromaDBVectorDatabase:
        """
        创建ChromaDB数据库实例
        
        Args:
            config: 配置参数
            
        Returns:
            ChromaDBVectorDatabase: ChromaDB数据库实例
        """
        return ChromaDBVectorDatabase(
            path=config.get("path", "./chroma_db"),
            host=config.get("host"),
            port=config.get("port"),
            settings=config.get("settings")
        )
    
    @classmethod
    def get_instance(cls, instance_name: str) -> Optional[VectorDatabaseAbstract]:
        """
        获取缓存的数据库实例
        
        Args:
            instance_name: 实例名称
            
        Returns:
            Optional[VectorDatabaseAbstract]: 数据库实例
        """
        return cls._instances.get(instance_name)
    
    @classmethod
    def remove_instance(cls, instance_name: str) -> bool:
        """
        移除缓存的数据库实例
        
        Args:
            instance_name: 实例名称
            
        Returns:
            bool: 是否移除成功
        """
        if instance_name in cls._instances:
            del cls._instances[instance_name]
            return True
        return False
    
    @classmethod
    def clear_instances(cls):
        """清除所有缓存的实例"""
        cls._instances.clear()
    
    @classmethod
    def list_instances(cls) -> Dict[str, str]:
        """
        列出所有缓存的实例
        
        Returns:
            Dict[str, str]: 实例名称到类型的映射
        """
        return {
            name: type(instance).__name__
            for name, instance in cls._instances.items()
        }


# 便捷函数
def create_pinecone_database(
    api_key: str,
    environment: str = "us-east-1-aws",
    instance_name: Optional[str] = None
) -> PineconeVectorDatabase:
    """
    创建Pinecone向量数据库实例的便捷函数
    
    Args:
        api_key: Pinecone API密钥
        environment: 环境
        instance_name: 实例名称
        
    Returns:
        PineconeVectorDatabase: Pinecone数据库实例
    """
    config = {
        "api_key": api_key,
        "environment": environment
    }
    
    return VectorDatabaseFactory.create_database(
        VectorDatabaseType.PINECONE,
        config,
        instance_name
    )


def create_chromadb_database(
    path: str = "./chroma_db",
    host: Optional[str] = None,
    port: Optional[int] = None,
    instance_name: Optional[str] = None
) -> ChromaDBVectorDatabase:
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
    
    return VectorDatabaseFactory.create_database(
        VectorDatabaseType.CHROMADB,
        config,
        instance_name
    )


def get_default_pinecone_config() -> Dict[str, Any]:
    """
    获取默认的Pinecone配置
    
    Returns:
        Dict[str, Any]: 默认配置
    """
    import os
    
    config = {}
    
    # 从环境变量获取API密钥
    api_key = os.getenv("PINECONE_API_KEY")
    if api_key:
        config["api_key"] = api_key
    
    # 从环境变量获取环境
    environment = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")
    config["environment"] = environment
    
    return config


def get_default_chromadb_config() -> Dict[str, Any]:
    """
    获取默认的ChromaDB配置
    
    Returns:
        Dict[str, Any]: 默认配置
    """
    import os
    
    config = {
        "path": os.getenv("CHROMADB_PATH", "./chroma_db"),
        "host": os.getenv("CHROMADB_HOST"),
        "port": int(os.getenv("CHROMADB_PORT", "8000")) if os.getenv("CHROMADB_PORT") else None
    }
    
    return config


def create_default_vector_db(default_path: str = "./chroma_db") -> VectorDatabaseAbstract:
    """
    创建默认向量数据库实例
    
    优先尝试使用Pinecone，如果失败则回退到ChromaDB
    
    Args:
        default_path: ChromaDB默认路径
        
    Returns:
        VectorDatabaseAbstract: 向量数据库实例
        
    Raises:
        Exception: 如果所有数据库都创建失败
    """
    try:
        # 优先尝试使用Pinecone
        pinecone_config = get_default_pinecone_config()
        if pinecone_config.get("api_key"):
            return create_pinecone_database(api_key=pinecone_config["api_key"])
    except Exception:
        # 忽略Pinecone创建失败的异常
        pass
    
    # 回退到ChromaDB
    try:
        chromadb_config = get_default_chromadb_config()
        return create_chromadb_database(
            path=chromadb_config.get("path", default_path)
        )
    except Exception as e:
        raise Exception(f"创建默认向量数据库失败: {e}")