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
from lib.utils.object import remove_none
from lib.utils.string import extract_json_string
from .interface import LlmAbstract, ChatResponse
from .openai_compatible import OpenAiRetryableError


class G4f(LlmAbstract):
    provider: str = "g4f"

    def __init__(self, model: str = "gpt-3.5-turbo", **system_params):
        super().__init__(model, **system_params)
        self.model = model
        self.client = Client(proxies={"all": get_http_proxy()})
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        if "DEBUG" == get_log_level():
            g4f_debug.logging = True

    @with_retry(
        (RateLimitError, ResponseError, ResponseStatusError),
        API_MAX_RETRY_TIMES,
    )
    def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[str] = None
    ) -> ChatResponse:
        """统一的聊天接口实现"""
        logger.debug(
            f"G4F calling data: {json.dumps(messages, ensure_ascii=False, indent=2)}"
        )
        logger.info(
            f"G4F API calling with body size: {len(json.dumps(messages))} Byte"
        )

        # 构建请求参数
        request_params = {
            "model": self.model,
            "messages": messages,
            "stream": False,

            # 实际上下面这些参数可能是不支持的
            "temperature": self.params.get("temperature"),
            "top_p": self.params.get("top_p"),
            "frequency_penalty": self.params.get("frequency_penalty"),
            "presence_penalty": self.params.get("presence_penalty"),
            "response_format": response_format if response_format else None
        }

        # 如果有工具，添加工具参数
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        rsp = self.client.chat.completions.create(**remove_none(request_params))
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
                logger.warning(f"Unexpected response : {rsp_message}")
                raise OpenAiRetryableError(rsp_message)
            rsp_message = try_extracted_json["gpt"]

        # 构建返回结果
        result: ChatResponse = {"content": rsp_message, "tool_calls": None}

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

    # ...existing deprecated methods...
