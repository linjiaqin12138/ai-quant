#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
嵌入服务适配器模块
提供统一的嵌入服务接口和多种实现
"""

from .embedding_base import (
    EmbeddingAbstract,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingResponse
)

from .paoluz_embedding import PaoluzEmbedding

def create_default_embedding_service() -> EmbeddingAbstract:
    """
    创建默认的嵌入服务实例
    
    Returns:
        EmbeddingAbstract: 默认嵌入服务实例
    """
    # 这里可以根据配置或环境变量选择不同的嵌入服务实现
    return PaoluzEmbedding()

__all__ = [
    # 基础接口和数据类
    'EmbeddingAbstract',
    'EmbeddingRequest',
    'EmbeddingResult',
    'EmbeddingResponse',
    
    # 具体实现
    'PaoluzEmbedding',
    'create_default_embedding_service'
]