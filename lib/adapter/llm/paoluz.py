
from typing import List, Any
import requests

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES, get_paoluz_token
from ...utils.decorators import with_retry
from .interface import LlmAbstract
from .openai_compatible import OpenAiApiMixin, OpenAiRetryableError

def api_query(method: str, endpoint: str, path: str, token: str, data: str = None):
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

@with_retry((OpenAiRetryableError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ProxyError), API_MAX_RETRY_TIMES)
def query_with_endpoint_retry(
    default_endpoint: str, 
    backup_endpoint: str, 
    method: str, 
    path: str, 
    token: str, 
    data: str = None
) -> requests.Response:
    rsp = api_query(method, default_endpoint, path, token, data)
    if rsp.status_code != 200:
        if rsp.status_code == 429 or rsp.status_code >= 500:
            logger.warning(f"Paoluz API calling failed with statusCode: {rsp.status_code} with endpoint {default_endpoint}, retry another endpoint")
            logger.debug(rsp.text)
            rsp = api_query(method, backup_endpoint, path, token, data)
            if rsp.status_code == 429:
                raise OpenAiRetryableError(f"Paoluz API calling failed with statusCode: {rsp.status_code}, message {rsp.text}")
            assert rsp.status_code == 200
        else:
            raise Exception(f"Paoluz API calling failed with statusCode: {rsp.status_code}, response body: {rsp.text}")
    return rsp

class PaoluzAgent(OpenAiApiMixin, LlmAbstract):
    default_endpoint = "https://chatapi.nloli.xyz"
    backup_endpoint  = "https://hkc3s.shamiko.uk"
    api_key = get_paoluz_token()

    def __init__(self, model: str = 'gpt-3.5-turbo', **system_params: dict):
        super().__init__(model, **system_params)
        self.backup_endpoint = system_params.get('api_backup_endpoint', PaoluzAgent.backup_endpoint)
        self.default_endpoint = system_params.get('api_default_endpoint', PaoluzAgent.default_endpoint)
        self.api_key = system_params.get('token', PaoluzAgent.api_key)
    
    @staticmethod
    def supported_models() -> List[Any]:
        rsp = query_with_endpoint_retry(
            PaoluzAgent.default_endpoint, 
            PaoluzAgent.backup_endpoint, 
            "get", 
            "/v1/models", 
            PaoluzAgent.api_key,
        )
        return rsp.json().get('data')

    def ask(self, context: List) -> str:
        json_data = self._build_req_body(context)
        rsp = query_with_endpoint_retry(
            self.default_endpoint, 
            self.backup_endpoint, 
            "post", 
            "/v1/chat/completions", 
            self.api_key, 
            json_data
        )
        return rsp.json()["choices"][0]["message"]["content"]
