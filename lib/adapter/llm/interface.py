import abc
import json
from typing import TypedDict, Literal, Optional, List, Any

import requests

from lib.config import API_MAX_RETRY_TIMES
from lib.utils.decorators import with_retry
from lib.logger import logger

GptSystemParams = TypedDict('GptSystemParams', {
    "temperature": Optional[float],      
    "top_p": Optional[float],   
    "frequency_penalty": Optional[float],
    "presence_penalty": Optional[float],
    "response_format": Optional[Literal['json']],
    "max_token": Optional[int],
    "api_key": Optional[str],
    "endpoint": Optional[str]
})

class OpenAiRetryableError(Exception):
    ... 

class OpenAiApiMixin:
    model: str
    api_key: str
    endpoint: str
    chat_context: List[Any]
    params: dict
    

    def _is_support_json_rsp(self) -> bool:
        return self.model.startswith(('gpt-3.5-turbo', 'gpt-4')) 
    
    def _build_req_header(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key
        }

    def _build_req_body(self) -> str:
        result = {
            "model": self.model,
            "messages": self.chat_context,
            "stream": False,
            'temperature': self.params.get('temperature'),
            'top_p': self.params.get('top_p'),
            'frequency_penalty': self.params.get('frequency_penalty'),
            'presence_penalty': self.params.get('presence_penalty'),
            'max_token': self.params.get('max_token')
        }
        if (self.params.get('response_format') == 'json') and self._is_support_json_rsp():
            result['response_format'] = {"type":"json_object"}
        return json.dumps(result, ensure_ascii=False)
    
    @with_retry((OpenAiRetryableError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ProxyError), API_MAX_RETRY_TIMES)
    def _ask(self) -> str:
        json_body_str = self._build_req_body()
        headers = self._build_req_header()

        logger.debug(f"{self.model} calling data: {json_body_str}")
        logger.info(f"{self.model} calling with body size: {len(json_body_str)} Byte")
        response = requests.post(f"{self.endpoint}/v1/chat/completions", data=json_body_str, headers=headers, stream=False)
        logger.info(f"{self.model} calling statusCode: {response.status_code}")
        logger.debug(f"{self.model} response header {response.headers}")
        logger.debug(f"{self.model} response body {response.text}")

        if response.status_code == 200:
            rsp_body = response.json()
            rsp_message = rsp_body["choices"][0]["message"]["content"]
            self.chat_context.append({"role": "assistant", "content": rsp_message})
            return rsp_message

        if response.status_code >= 400 and response.status_code < 500 and response.status_code != 429:
            raise Exception(f"Client request error: {response.status_code=} {response.text=}")

        raise OpenAiRetryableError(f"{self.model} failed with error: {response.text}")

class GptAgentAbstract(abc.ABC):
    def __init__(self, model: str, **system_params):
        self.model = model
        self.chat_context = []
        self.params: GptSystemParams = system_params
    
    @abc.abstractmethod
    def _ask(self) -> str:
        raise Exception("Not-Implement")

    def ask(self, question: str)-> str:
        self.chat_context.append({"role": "user", "content": question})
        rsp_message = self._ask()
        self.chat_context.append({"role": "assistant", "content": rsp_message})
        return rsp_message

    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear(self):
        if self.chat_context and self.chat_context[0]['role'] == 'system':
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []


__all__ = [
    'GptAgentAbstract',
    'OpenAiApiMixin'
]