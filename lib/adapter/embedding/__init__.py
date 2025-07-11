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

__all__ = [
    # 基础接口和数据类
    'EmbeddingAbstract',
    'EmbeddingRequest',
    'EmbeddingResult',
    'EmbeddingResponse',
    
    # 具体实现
    'PaoluzEmbedding',
]