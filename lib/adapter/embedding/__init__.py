#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
嵌入服务适配器模块
提供统一的嵌入服务接口和多种实现
"""
from lib.config import get_paoluz_token, get_silicon_token
from .embedding_base import (
    EmbeddingAbstract,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingResponse
)

from .openai_compatible_embedding import OpenAICompatibleEmbedding

def create_default_embedding_service() -> EmbeddingAbstract:
    """
    创建默认的嵌入服务实例
    
    Returns:
        EmbeddingAbstract: 默认嵌入服务实例
    """
    # 这里可以根据配置或环境变量选择不同的嵌入服务实现
    return OpenAICompatibleEmbedding(
        api_key=get_paoluz_token(),
        base_url="https://chatapi.nloli.xyz/"
    )

__all__ = [
    # 基础接口和数据类
    'EmbeddingAbstract',
    'EmbeddingRequest',
    'EmbeddingResult',
    'EmbeddingResponse',
    
    # 具体实现
    'OpenAICompatibleEmbedding',
    'create_default_embedding_service'
]