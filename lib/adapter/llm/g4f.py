import asyncio
import json
import sys
from typing import Optional

from g4f import debug as g4f_debug
from g4f.client import Client
from g4f.errors import *

from ...config import API_MAX_RETRY_TIMES, get_http_proxy, get_log_level
from ...logger import logger
from ...utils.decorators import with_retry
from ...utils.string import extract_json_string
from .interface import GptAgentAbstract, OpenAiRetryableError

class G4fAgent(GptAgentAbstract):
    
    def __init__(self, model: str = "gpt-3.5-turbo", **system_params):
        super().__init__(model, **system_params)
        self.model = model
        self.client = Client(proxies = {
            "all": get_http_proxy()
        })
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        if 'DEBUG' == get_log_level():
            g4f_debug.logging = True
    
    @with_retry((OpenAiRetryableError, RateLimitError, ResponseError, ResponseStatusError), API_MAX_RETRY_TIMES)
    def _ask(self) -> str:
        logger.debug(f"G4F calling data: {json.dumps(self.chat_context, ensure_ascii=False, indent=2)}")
        logger.info(f"G4F API calling with body size: {len(json.dumps(self.chat_context))} Byte")
        rsp= self.client.chat.completions.create(
            model=self.model,
            messages=self.chat_context,
            stream=False,
            temperature=self.params.get('temperature'), 
            top_p=self.params.get('top_p'),
            frequency_penalty=self.params.get('frequency_penalty'),
            presence_penalty=self.params.get('presence_penalty')
        )
        logger.debug(f"GPT response detailes {rsp}")
        rsp_message = rsp.choices[0].message.content or ''
        # G4F 有时候response会是一个JSON，{"code": 200, "status": true, "model": "gpt-3.5-turbo", "gpt": "......."}
        try_extracted_json = extract_json_string(rsp_message)
        if try_extracted_json and all(try_extracted_json.get(key) is not None for key in ['code', 'status']):
            logger.warning(f"G4F response message is an object, provider: {rsp.provider}")
            if try_extracted_json.get('code') != 200 or try_extracted_json.get('gpt') is None:
                raise OpenAiRetryableError(rsp_message)
            rsp_message = try_extracted_json['gpt']
        return rsp_message