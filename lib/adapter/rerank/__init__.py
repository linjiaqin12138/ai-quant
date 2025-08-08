#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重排序服务适配器模块
提供统一的重排序服务接口和多种实现
"""
from lib.config import get_paoluz_token
from .rerank_base import (
    RerankAbstract,
    RerankRequest,
    RerankResult,
    RerankResponse
)

from .openai_compatible_rerank import OpenAICompatibleRerank

def create_default_rerank_service() -> RerankAbstract:
    """
    创建默认的重排序服务实例
    
    Returns:
        RerankAbstract: 默认重排序服务实例
    """
    # 这里可以根据配置或环境变量选择不同的重排序服务实现
    return OpenAICompatibleRerank(
        api_key=get_paoluz_token(),
        base_url="https://chatapi.nloli.xyz/"
    )

__all__ = [
    # 基础接口和数据类
    'RerankAbstract',
    'RerankRequest',
    'RerankResult',
    'RerankResponse',
    
    # 具体实现
    'OpenAICompatibleRerank',
    'create_default_rerank_service'
]
