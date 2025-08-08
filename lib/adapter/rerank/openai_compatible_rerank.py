#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from typing import List, Optional, Dict, Any
from .rerank_base import RerankAbstract, RerankResult, RerankResponse

from lib.config import get_paoluz_token


class OpenAICompatibleRerank(RerankAbstract):
    """OpenAI兼容的重排序服务提供者实现"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or get_paoluz_token()
        self.base_url = base_url or "https://chatapi.nloli.xyz/"
        self.endpoint = f"{self.base_url}/v1/rerank"

    def _build_request_data(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_k: Optional[int] = None,
        return_documents: bool = True
    ) -> Dict[str, Any]:
        """构建请求数据"""
        request_data = {
            "query": query,
            "documents": documents,
            "model": model,
            "return_documents": return_documents
        }
        
        if top_k is not None:
            request_data["top_k"] = top_k
            
        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> RerankResponse:
        """解析API响应"""
        rerank_results = []
        
        for item in response_data["results"]:
            rerank_result = RerankResult(
                index=item["index"],
                relevance_score=item["relevance_score"],
                document=item.get("document")
            )
            rerank_results.append(rerank_result)
        
        return RerankResponse(
            results=rerank_results,
            model=response_data["model"],
            usage=response_data.get("usage")
        )

    def rerank(
        self,
        query: str,
        documents: List[str],
        model: str = "rerank-multilingual-v3.0",
        top_k: Optional[int] = None,
        return_documents: bool = True
    ) -> RerankResponse:
        """对文档列表根据查询进行重排序"""
        request_data = self._build_request_data(
            query, documents, model, top_k, return_documents
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
