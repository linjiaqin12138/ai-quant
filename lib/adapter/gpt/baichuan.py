
import json
from typing import Optional, TypedDict
import requests

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES, get_baichuan_token
from ...utils.retry import with_retry
from .interface import GptAgentAbstract, GptSystemParams

class BaiChuanAgent(GptAgentAbstract):
    AdditionalOptions = TypedDict('AdditionalOptions', {
        'api_endpoint': Optional[str],
        'token': Optional[str],
    })
    class BaiChuanApiFailed(Exception):
        ...
    def __init__(self, model: str = 'Baichuan3-Turbo-128k', system_prompt: Optional[str] = None, system_params: GptSystemParams = {}, **addtional_options: AdditionalOptions):
        super().__init__(model, system_prompt, system_params)
        self.url = addtional_options.get('api_endpoint', "https://api.baichuan-ai.com/v1/chat/completions")
        self.api_key = addtional_options.get('token', get_baichuan_token())

    def ask(self, question: str) -> str:
        self.chat_context.append({"role": "user", "content": question})
        data = {
            "model": self.model,
            "messages": self.chat_context,
            "stream": False,
        }
        data.update(self.params)

        json_data = json.dumps(data, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key
        }

        @with_retry((self.BaiChuanApiFailed, requests.exceptions.ConnectionError, requests.exceptions.Timeout), API_MAX_RETRY_TIMES)
        def retryable_part():
            logger.debug(f"Baichuan API calling data: {json_data}")
            logger.info(f"Baichuan API calling with body size: {len(json_data)} Byte")
            response = requests.post(self.url, data=json_data, headers=headers, stream=False)
            logger.info(f"Baichuan API calling statusCode: {response.status_code}")
            logger.debug(f"Baichuan API response header {response.headers}")
            logger.debug(f"Baichuan API response body {response.text}")

            if response.status_code == 200:
                rsp_body = response.json()
                rsp_message = rsp_body["choices"][0]["message"]["content"]
                self.chat_context.append({"role": "assistant", "content": rsp_message})
                return rsp_message

            raise self.BaiChuanApiFailed(f"API failed with error: {response.text}")
        return retryable_part()
