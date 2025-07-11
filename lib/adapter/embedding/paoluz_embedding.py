#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from typing import List, Union, Optional, Dict, Any
from .embedding_base import EmbeddingAbstract, EmbeddingRequest, EmbeddingResult, EmbeddingResponse

from lib.config import get_paoluz_token


class PaoluzEmbedding(EmbeddingAbstract):
    """NewAPI嵌入服务提供者实现"""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or get_paoluz_token()
        self.base_url = "https://chatapi.nloli.xyz/"
        self.endpoint = f"{self.base_url}/v1/embeddings"

    def _build_request_data(
        self,
        input_text: Union[str, List[str]],
        model: str,
        encoding_format: str,
        dimensions: Optional[int] = None
    ) -> Dict[str, Any]:
        """构建请求数据"""
        return {
            "input": input_text,
            "model": model,
            "encoding_format": encoding_format,
            "dimensions": dimensions
        }

    def _parse_response(self, response_data: Dict[str, Any]) -> EmbeddingResponse:
        """解析API响应"""
        embedding_results = []
        
        for item in response_data["data"]:
            embedding_result = EmbeddingResult(
                embedding=item["embedding"],
                index=item["index"]
            )
            embedding_results.append(embedding_result)
        
        return EmbeddingResponse(
            data=embedding_results
        )

    def create_embedding(
        self,
        input_text: Union[str, List[str]],
        model: str = "text-embedding-ada-002",
        dimensions: Optional[int] = None
    ) -> EmbeddingResponse:
        """同步创建文本嵌入"""
        request_data = self._build_request_data(
            input_text, model, 'float', dimensions
        )
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=request_data
        )
        
        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")

        response_data = response.json()
        return self._parse_response(response_data)

