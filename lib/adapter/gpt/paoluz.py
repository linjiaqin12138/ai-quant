
import json
from typing import Optional, TypedDict
import requests

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES, get_paoluz_token
from ...utils.decorators import with_retry
from .interface import GptAgentAbstract, GptSystemParams

class PaoluzAgent(GptAgentAbstract):
    AdditionalOptions = TypedDict('AdditionalOptions', {
        'api_endpoint': Optional[str],
        'token': Optional[str],
    })
    
    def __init__(self, model: str = 'gpt-3.5-turbo', system_prompt: Optional[str] = None, system_params: GptSystemParams = {}, **addtional_options: AdditionalOptions):
        super().__init__(model, system_prompt, system_params)
        self.endpoint = addtional_options.get('api_endpoint', "https://chatapi.nloli.xyz")
        self.api_key = addtional_options.get('token', get_paoluz_token())

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

        @with_retry((requests.exceptions.ConnectionError, requests.exceptions.Timeout), API_MAX_RETRY_TIMES)
        def retryable_part():
            logger.debug(f"Paoluz API calling data: {json_data}")
            logger.info(f"Paoluz API calling with body size: {len(json_data)} Byte")
            response = requests.post(f'{self.endpoint}/v1/chat/completions', data=json_data, headers=headers, stream=False)
            logger.info(f"Paoluz API calling statusCode: {response.status_code}")
            logger.debug(f"Paoluz API response header {response.headers}")
            logger.debug(f"Paoluz API response body {response.text}")

            assert response.status_code == 200
            rsp_body = response.json()
            rsp_message = rsp_body["choices"][0]["message"]["content"]
            self.chat_context.append({"role": "assistant", "content": rsp_message})
            return rsp_message
        return retryable_part()
