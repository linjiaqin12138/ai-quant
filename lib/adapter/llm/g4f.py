import asyncio
import json
import sys
from typing import List, Dict, Any, Optional

from g4f import debug as g4f_debug
from g4f.client import Client
from g4f.errors import *

from lib.config import API_MAX_RETRY_TIMES, get_http_proxy, get_log_level
from lib.logger import logger
from lib.utils.decorators import with_retry
from lib.utils.string import extract_json_string
from .interface import LlmAbstract
from .openai_compatible import OpenAiRetryableError


class G4f(LlmAbstract):

    def __init__(self, model: str = "gpt-3.5-turbo", **system_params):
        super().__init__(model, **system_params)
        self.model = model
        self.client = Client(proxies={"all": get_http_proxy()})
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        if "DEBUG" == get_log_level():
            g4f_debug.logging = True

    def ask(self, context: List, response_format: Optional[str] = None) -> str:
        """实现LlmAbstract的ask方法"""
        return self._ask(context, response_format)

    def ask_with_tools(
        self, context: List, available_tools: Optional[List[str]] = None, response_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """实现LlmAbstract的ask_with_tools方法，支持工具调用"""
        # 获取可用工具
        tools = self.get_available_tools(available_tools)
        
        # 如果没有工具可用，直接返回普通聊天响应
        if not tools:
            content = self._ask(context, response_format)
            return {"content": content}
        
        # 使用工具调用
        return self._ask_with_tools(context, tools, response_format)

    @with_retry(
        (RateLimitError, ResponseError, ResponseStatusError),
        API_MAX_RETRY_TIMES,
    )
    def _ask(self, context: List, response_format: Optional[str] = None) -> str:
        logger.debug(
            f"G4F calling data: {json.dumps(context, ensure_ascii=False, indent=2)}"
        )
        logger.info(
            f"G4F API calling with body size: {len(json.dumps(context))} Byte"
        )

        # 构建请求参数
        request_params = {
            "model": self.model,
            "messages": context,
            "stream": False,
            "temperature": self.params.get("temperature"),
            "top_p": self.params.get("top_p"),
            "frequency_penalty": self.params.get("frequency_penalty"),
            "presence_penalty": self.params.get("presence_penalty"),
            "response_format": response_format if response_format else None
        }

        # 移除None值
        request_params = {k: v for k, v in request_params.items() if v is not None}

        rsp = self.client.chat.completions.create(**request_params)
        logger.debug(f"GPT response detailes {rsp}")
        rsp_message = rsp.choices[0].message.content or ""

        # G4F 有时候response会是一个JSON，{"code": 200, "status": true, "model": "gpt-3.5-turbo", "gpt": ".......}
        try_extracted_json = extract_json_string(rsp_message)
        if try_extracted_json and all(
            try_extracted_json.get(key) is not None for key in ["code", "status"]
        ):
            logger.warning(
                f"G4F response message is an object, provider: {rsp.provider}"
            )
            if (
                try_extracted_json.get("code") != 200
                or try_extracted_json.get("gpt") is None
            ):
                raise OpenAiRetryableError(rsp_message)
            rsp_message = try_extracted_json["gpt"]
        return rsp_message

    @with_retry(
        (RateLimitError, ResponseError, ResponseStatusError),
        API_MAX_RETRY_TIMES,
    )
    def _ask_with_tools(self, context: List, tools: List[Dict[str, Any]], response_format: Optional[str] = None) -> Dict[str, Any]:
        """支持工具调用的内部实现"""
        logger.debug(
            f"G4F calling with tools data: {json.dumps(context, ensure_ascii=False, indent=2)}"
        )
        logger.info(
            f"G4F API calling with tools body size: {len(json.dumps(context))} Byte"
        )

        # 构建请求参数，包含工具定义
        request_params = {
            "model": self.model,
            "messages": context,
            "stream": False,
            "temperature": self.params.get("temperature"),
            "top_p": self.params.get("top_p"),
            "frequency_penalty": self.params.get("frequency_penalty"),
            "presence_penalty": self.params.get("presence_penalty"),
            "tools": tools,
            "tool_choice": "auto",
            "response_format": response_format if response_format else None
            
        }

        # 移除None值
        request_params = {k: v for k, v in request_params.items() if v is not None}

        rsp = self.client.chat.completions.create(**request_params)
        logger.debug(f"G4F response details {rsp}")
        
        # 获取响应消息
        message = rsp.choices[0].message
        rsp_message = message.content or ""
        
        # 处理特殊的JSON响应格式
        try_extracted_json = extract_json_string(rsp_message)
        if try_extracted_json and all(
            try_extracted_json.get(key) is not None for key in ["code", "status"]
        ):
            logger.warning(
                f"G4F response message is an object, provider: {rsp.provider}"
            )
            if (
                try_extracted_json.get("code") != 200
                or try_extracted_json.get("gpt") is None
            ):
                raise OpenAiRetryableError(rsp_message)
            rsp_message = try_extracted_json["gpt"]

        # 构建返回结果
        result = {"content": rsp_message}

        # 检查是否有工具调用
        if hasattr(message, 'tool_calls') and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in message.tool_calls
            ]

        return result
