
import json
from typing import Optional, TypedDict, List, Any
import requests

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES, get_paoluz_token
from ...utils.decorators import with_retry
from .interface import GptAgentAbstract, GptSystemParams

class ServerRateLimit(Exception):
    ...

@with_retry((ServerRateLimit, requests.exceptions.ConnectionError, requests.exceptions.Timeout), API_MAX_RETRY_TIMES)
def retryable_query(method: str, endpoint: str, path: str, token: str, data: str = None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    logger.debug(f"Paoluz API calling endpoint {endpoint}{path} data: {data}, headers: {headers}")
    if data:
        logger.info(f"Paoluz API calling with body size: {len(data)} Byte")
    if method == 'post':
        response = requests.post(f'{endpoint}{path}', data=data, headers=headers, stream=False)
    else:
        response = requests.get(f'{endpoint}{path}', headers=headers)
    logger.info(f"Paoluz API calling statusCode: {response.status_code}")
    logger.debug(f"Paoluz API response header {response.headers}")
    logger.debug(f"Paoluz API response body {response.text}")
    return response

class PaoluzAgent(GptAgentAbstract):
    AdditionalOptions = TypedDict('AdditionalOptions', {
        'api_endpoint': Optional[str],
        'token': Optional[str],
    })
    default_endpoint = "https://chatapi.nloli.xyz"
    backup_endpoint  = "https://hkc3s.shamiko.uk"
    system_token = get_paoluz_token()

    def __init__(self, model: str = 'gpt-3.5-turbo', system_prompt: Optional[str] = None, system_params: GptSystemParams = {}, **addtional_options: AdditionalOptions):
        super().__init__(model, system_prompt, system_params)
        self.backup_endpoint = addtional_options.get('api_backup_endpoint', PaoluzAgent.backup_endpoint)
        self.endpoint = addtional_options.get('api_endpoint', PaoluzAgent.default_endpoint)
        self.api_key = addtional_options.get('token', PaoluzAgent.system_token)
    
    @staticmethod
    def supported_models() -> List[Any]:
        path = "/v1/models"
        rsp = None
        try:
            rsp = retryable_query("get", PaoluzAgent.default_endpoint, path, PaoluzAgent.system_token)
            rsp.raise_for_status()
        except Exception as e:
            logger.error(f"Paoluz API calling failed with exception: {e}")
            rsp = retryable_query("get", PaoluzAgent.backup_endpoint, path, PaoluzAgent.system_token)
            rsp.raise_for_status()
        return rsp.json().get('data')

    def _query_with_endpoint_retry(self, method: str, path: str, data: str = None):
        rsp = retryable_query(method, self.endpoint, path, self.api_key, data)
        if rsp.status_code != 200:
            if rsp.status_code == 429 or rsp.status_code >= 500:
                logger.warning(f"Paoluz API calling failed with statusCode: {rsp.status_code}, retry another endpoint")
                rsp = retryable_query(method, self.backup_endpoint, path, self.api_key, data)
                if rsp.status_code == 429:
                    raise ServerRateLimit(f"Paoluz API calling failed with statusCode: {rsp.status_code}, message {rsp.text}")
                assert rsp.status_code == 200
            else:
                raise Exception(f"Paoluz API calling failed with statusCode: {rsp.status_code}, response body: {rsp.text}")
        return rsp

    def ask(self, question: str) -> str:
        self.chat_context.append({"role": "user", "content": question})
        data = {
            "model": self.model,
            "messages": self.chat_context,
            "stream": False,
        }
        data.update(self.params)
        json_data = json.dumps(data, ensure_ascii=False)
        rsp = self._query_with_endpoint_retry("post", "/v1/chat/completions", json_data)
        rsp_body = rsp.json()
        rsp_message = rsp_body["choices"][0]["message"]["content"]
        self.chat_context.append({"role": "assistant", "content": rsp_message})
        return rsp_message
