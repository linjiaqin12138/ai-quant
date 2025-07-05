import json
from typing import List, Dict, Any, Optional

import requests

from lib.config import API_MAX_RETRY_TIMES
from lib.logger import logger
from lib.utils.decorators import with_retry
from lib.utils.object import remove_none


class OpenAiRetryableError(Exception): ...


class OpenAiApiMixin:
    model: str
    api_key: str
    endpoint: str
    params: dict

    def _is_support_json_rsp(self) -> bool:
        return self.model.startswith(("gpt-3.5-turbo", "gpt-4"))

    def _build_req_header(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    def _build_req_body(
        self, context: List, tools: Optional[List[Dict[str, Any]]]= None, response_format: Optional[str] = None
    ) -> str:
        result = remove_none(
            {
                "model": self.model,
                "messages": context,
                "stream": False,
                "temperature": self.params.get("temperature"),
                "top_p": self.params.get("top_p"),
                "frequency_penalty": self.params.get("frequency_penalty"),
                "presence_penalty": self.params.get("presence_penalty"),
                "max_token": self.params.get("max_token"),
            }
        )

        # 添加工具定义
        if tools:
            result["tools"] = tools
            result["tool_choice"] = "auto"

        if (response_format) and self._is_support_json_rsp():
            result["response_format"] = {"type": response_format}
        return json.dumps(result, ensure_ascii=False)

    @with_retry(
        (
            OpenAiRetryableError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ProxyError,
        ),
        API_MAX_RETRY_TIMES,
    )
    def ask(self, context: List, response_format: Optional[str] = None) -> str:
        json_body_str = self._build_req_body(context, response_format=response_format)
        headers = self._build_req_header()

        logger.debug(f"{self.model} calling data: {json_body_str}")
        logger.info(f"{self.model} calling with body size: {len(json_body_str)} Byte")
        response = requests.post(
            f"{self.endpoint}/v1/chat/completions",
            data=json_body_str,
            headers=headers,
            stream=False,
        )
        logger.info(f"{self.model} calling statusCode: {response.status_code}")
        logger.debug(f"{self.model} response header {response.headers}")
        logger.debug(f"{self.model} response body {response.text}")

        if response.status_code == 200:
            rsp_body = response.json()
            rsp_message = rsp_body["choices"][0]["message"]["content"]
            return rsp_message

        if (
            response.status_code >= 400
            and response.status_code < 500
            and response.status_code != 429
        ):
            raise Exception(
                f"Client request error: {response.status_code=} {response.text=}"
            )

        raise OpenAiRetryableError(f"{self.model} failed with error: {response.text}")

    @with_retry(
        (
            OpenAiRetryableError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ProxyError,
        ),
        API_MAX_RETRY_TIMES,
    )
    def ask_with_tools(
        self, context: List, available_tools: Optional[List[str]] = None, response_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """支持工具调用的请求方法"""
        # 获取可用工具
        tools = (
            self.get_available_tools(available_tools)
            if hasattr(self, "get_available_tools")
            else None
        )

        json_body_str = self._build_req_body(context, tools, response_format)
        headers = self._build_req_header()

        logger.debug(f"{self.model} calling with tools data: {json_body_str}")
        logger.info(
            f"{self.model} calling with tools body size: {len(json_body_str)} Byte"
        )
        response = requests.post(
            f"{self.endpoint}/v1/chat/completions",
            data=json_body_str,
            headers=headers,
            stream=False,
        )
        logger.info(
            f"{self.model} calling with tools statusCode: {response.status_code}"
        )
        logger.debug(f"{self.model} response header {response.headers}")
        logger.debug(f"{self.model} response body {response.text}")

        if response.status_code == 200:
            rsp_body = response.json()
            message = rsp_body["choices"][0]["message"]

            result = {"content": message.get("content", "")}

            # 检查是否有工具调用
            if "tool_calls" in message and message["tool_calls"]:
                result["tool_calls"] = message["tool_calls"]

            return result

        if (
            response.status_code >= 400
            and response.status_code < 500
            and response.status_code != 429
        ):
            raise Exception(
                f"Client request error: {response.status_code=} {response.text=}"
            )

        raise OpenAiRetryableError(f"{self.model} failed with error: {response.text}")


__all__ = ["OpenAiApiMixin", "OpenAiRetryableError"]
