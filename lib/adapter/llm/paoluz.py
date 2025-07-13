import json
from typing import List, Any, Literal, Optional, Dict
import requests

from lib.logger import logger
from lib.config import API_MAX_RETRY_TIMES, get_paoluz_token
from lib.utils.decorators import with_retry
from lib.utils.object import pretty_output
from .interface import LlmAbstract, ChatResponse, debug_req, debug_rsp
from .openai_compatible import OpenAiApiMixin, OpenAiRetryableError

def api_query(method: str, endpoint: str, path: str, token: str, data: dict = None):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    debug_req(method, endpoint, path, headers, data)
    if data:
        logger.info(f"Paoluz API calling with body size: {len(json.dumps(data))} Byte")
    if method == "post":
        response = requests.post(
            f"{endpoint}{path}", json=data, headers=headers, stream=False
        )
    else:
        response = requests.get(f"{endpoint}{path}", headers=headers)
    logger.info(f"Paoluz API calling status code: {response.status_code}")
    debug_rsp(response)
    return response


@with_retry(
    (
        OpenAiRetryableError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ProxyError,
    ),
    API_MAX_RETRY_TIMES,
)
def query_with_endpoint_retry(
    default_endpoint: str,
    backup_endpoint: str,
    method: str,
    path: str,
    token: str,
    data: dict = None,
) -> requests.Response:
    rsp = api_query(method, default_endpoint, path, token, data)
    if rsp.status_code != 200:
        if rsp.status_code == 429 or rsp.status_code >= 500:
            logger.warning(
                f"Paoluz API calling failed with statusCode: {rsp.status_code} with endpoint {default_endpoint}, retry another endpoint"
            )
            rsp = api_query(method, backup_endpoint, path, token, data)
            if rsp.status_code == 429:
                raise OpenAiRetryableError("Paoluz response error:" + rsp.text[:200])
            assert rsp.status_code == 200
        else:
            logger.error(f"Paoluz API calling failed with statusCode: {rsp.status_code} with endpoint {default_endpoint}")
            raise Exception("Paoluz response error:" + rsp.text[:200])
    return rsp


class PaoluzAgent(OpenAiApiMixin, LlmAbstract):
    default_endpoint = "https://chatapi.nloli.xyz"
    backup_endpoint = "https://hkc3s.shamiko.uk"
    api_key = get_paoluz_token()
    provider: str = "paoluz"

    def __init__(self, model: str = "gpt-3.5-turbo", **system_params: dict):
        super().__init__(model, **system_params)
        self.backup_endpoint = system_params.get(
            "api_backup_endpoint", PaoluzAgent.backup_endpoint
        )
        self.default_endpoint = system_params.get(
            "api_default_endpoint", PaoluzAgent.default_endpoint
        )
        self.api_key = system_params.get("token", PaoluzAgent.api_key)
        # 为了兼容OpenAiApiMixin，设置endpoint属性
        self.endpoint = self.default_endpoint

    @staticmethod
    def supported_models() -> List[Any]:
        rsp = query_with_endpoint_retry(
            PaoluzAgent.default_endpoint,
            PaoluzAgent.backup_endpoint,
            "get",
            "/v1/models",
            PaoluzAgent.api_key,
        )
        return rsp.json().get("data")

    def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Literal['auto', 'required', 'none']] = None,
        response_format: Optional[Literal['json_object']] = None
    ) -> ChatResponse:
        """统一的聊天接口实现"""
        json_data = self._build_req_body(messages, tools, tool_choice, response_format)
        rsp = query_with_endpoint_retry(
            self.default_endpoint,
            self.backup_endpoint,
            "post",
            "/v1/chat/completions",
            self.api_key,
            json_data,
        )
        
        rsp_body = rsp.json()
        message = rsp_body["choices"][0]["message"]

        result: ChatResponse = {"content": message.get("content", ""), "tool_calls": None}

        # 检查是否有工具调用
        if "tool_calls" in message and message["tool_calls"]:
            result["tool_calls"] = message["tool_calls"]

        return result

    # ...existing deprecated methods...
