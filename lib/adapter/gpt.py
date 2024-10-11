import abc
import json

import requests
from g4f.client import Client
from g4f.errors import *

from ..config import get_http_proxy, get_baichuan_token, API_MAX_RETRY_TIMES
from ..logger import logger
from ..utils.retry import with_retry
from ..utils.string import extract_json_string

class GptAgentAbstract(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def ask(self, question: str)-> str:
        raise Exception("Not-Implement")

    def export(self):
        pass
    
    @abc.abstractmethod
    def clear(self):
        pass

    @abc.abstractmethod
    def set_system_prompt(self, prompt: str):
        pass


class BaiChuanAgent(GptAgentAbstract):
    class BaiChuanApiFailed(Exception):
        ...
    def __init__(self, model: str, system_prompt: str):
        super().__init__()
        self.url = "https://api.baichuan-ai.com/v1/chat/completions"
        self.api_key = get_baichuan_token()
        self.model = model
        self.chat_context = [
            # assistant
            {"role": "system", "content": system_prompt}
        ]

    def set_system_prompt(self, prompt: str):
        self.clear()
        self.chat_context[0]['content'] = prompt

    def clear(self):
        self.chat_context = self.chat_context[:1]

    def ask(self, question: str) -> str:
        self.chat_context.append({"role": "user", "content": question})
        data = {
            "model": self.model,
            "messages": self.chat_context,
            "stream": False
        }
        json_data = json.dumps(data, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key
        }

        @with_retry((self.BaiChuanApiFailed), API_MAX_RETRY_TIMES)
        def retryable_part():
            logger.debug(f"Baichuan API calling data: {json_data}")
            logger.info(f"Baichuan API calling with body size: {len(json_data)} Byte")
            response = requests.post(self.url, data=json_data, headers=headers, timeout=60, stream=False)
            logger.info(f"Baichuan API calling statusCode: {response.status_code}")
            logger.debug(f"Baichuan API response header {response.headers}")
            logger.debug(f"Baichuan API response body {response.text}")
            return response
        
        rsp = retryable_part()
        if rsp.status_code == 200:
            rsp_body = rsp.json()
            rsp_message = rsp_body["choices"][0]["message"]["content"]
            self.chat_context.append({"role": "assistant", "content": rsp_message})
            return rsp_message
        raise self.BaiChuanApiFailed(f"API failed with error: {rsp.text}")
        
        
        return retryable_part()
            # {
            #     "id": "chatcmpl-M0bc0015KKZqooq",
            #     "object": "chat.completion",
            #     "created": 1716208552,
            #     "model": "Baichuan4",
            #     "choices": [
            #         {
            #         "index": 0,
            #         "message": {
            #             "role": "assistant",
            #             "content": "根据您的要求，以下是一份为期10天的欧洲之旅计划，涵盖巴黎、米兰和马德里三个城市。请注意，这份计划是基于当前的旅游信息和汇率制定的，实际费用可能会有所不同。\n\n### 第1天：抵达巴黎\n- **上午**：抵达巴黎，入住酒店休息。\n- **下午**：参观埃菲尔铁塔，欣赏巴黎全景。\n- **晚上**：在塞纳河边享受法式晚餐。\n\n### 第2天：巴黎\n- **上午**：参观卢浮宫，欣赏《蒙娜丽莎》等世界名画。\n- **下午**：游览巴黎圣母院和圣心大教堂。\n- **晚上**：自由活动，可逛巴黎的夜生活或品尝当地美食。\n\n### 第3天：巴黎\n- **全天**：游览凡尔赛宫，了解法国历史和文化。\n- **晚上**：在香榭丽舍大街购物或品尝法式甜点。\n\n### 第4天：前往米兰\n- **上午**：乘坐火车前往米兰。\n- **下午**：抵达米兰，入住酒店休息。\n- **晚上**：在米兰大教堂广场散步，欣赏夜景。\n\n### 第5天：米兰\n- **上午**：参观米兰大教堂和斯福尔扎城堡。\n- **下午**：游览达芬奇《最后的晚餐》壁画所在的恩宠圣母教堂。\n- **晚上**：在蒙特拿破仑大街购物或品尝意大利披萨和意面。\n\n### 第6天：米兰\n- **上午**：参观布雷拉画廊，欣赏意大利文艺复兴时期的艺术作品。\n- **下午**：游览圣玛丽亚修道院和感恩圣母堂。\n- **晚上**：自由活动，可探索米兰的时尚区或品尝当地美食。\n\n### 第7天：前往马德里\n- **上午**：乘坐飞机前往马德里。\n- **下午**：抵达马德里，入住酒店休息。\n- **晚上**：在马约尔广场品尝西班牙小吃和葡萄酒。\n\n### 第8天：马德里\n- **上午**：参观普拉多博物馆，欣赏戈雅和委拉斯开兹等大师的作品。\n- **下午**：游览马德里皇宫和圣米格尔市场。\n- **晚上**：在查马丁区的酒吧享受西班牙夜生活。\n\n### 第9天：马德里\n- **上午**：参观索菲亚王后艺术中心，欣赏毕加索的《格尔尼卡》。\n- **下午**：游览丽池公园和阿尔卡拉门。\n- **晚上**：自由活动，可继续探索马德里的美食或购物。\n\n### 第10天：返回\n- **上午**：整理行李，退房。\n- **下午**：前往机场，结束愉快的欧洲之旅。\n\n请注意，这只是一个基本的行程安排，您可以根据自己的兴趣和时间进行调整。此外，由于汇率变动和季节性价格调整，实际费用可能有所不同。建议您提前预订机票、酒店和旅游活动，以获得更好的价格和服务。祝您旅途愉快！"
            #         },
            #         "finish_reason": "stop"
            #         }
            #     ],
            #     "usage": {
            #         "prompt_tokens": 158,
            #         "completion_tokens": 640,
            #         "total_tokens": 798
            #     }
            #     }
        
class G4fAgent(GptAgentAbstract):
    class G4fReplyErrorJson(Exception):
        pass
    def __init__(self, model: str, system_prompt: str):
        super().__init__()
        self.model = model
        self.client = Client(proxies = {
            "all": get_http_proxy()
        })
        self.chat_context = [
            # assistant
            {"role": "system", "content": system_prompt}
        ]

    def clear(self):
        self.chat_context = self.chat_context[:1]

    def set_system_prompt(self, system_prompt: str):
        self.clear()
        self.chat_context[0]['content'] = system_prompt
    
    def ask(self, question: str) -> str:
        self.chat_context.append({"role": "user", "content": question})
        
        @with_retry((self.G4fReplyErrorJson, RateLimitError, ResponseError, ResponseStatusError), API_MAX_RETRY_TIMES)
        def retryable_part():
            logger.debug(f"G4F calling data: {json.dumps(self.chat_context, ensure_ascii=False, indent=2)}")
            logger.info(f"G4F API calling with body size: {len(json.dumps(self.chat_context))} Byte")
            rsp= self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_context,
                stream=False
            )
            logger.debug(f"GPT response detailes {rsp.to_json()}")
            rsp_message = rsp.choices[0].message.content or ''
            # G4F 有时候response会是一个JSON，{"code": 200, "status": true, "model": "gpt-3.5-turbo", "gpt": "......."}
            try_extracted_json = extract_json_string(rsp_message)
            if try_extracted_json and all(try_extracted_json.get(key) is not None for key in ['code', 'status']):
                logger.warning(f"G4F response message is an object, provider: {rsp.provider}")
                if try_extracted_json.get('code') != 200 or try_extracted_json.get('gpt') is None:
                    raise self.G4fReplyErrorJson(rsp_message)
                rsp_message = try_extracted_json['gpt']
            return rsp_message
        
        rsp_message = retryable_part()
        
        self.chat_context.append({"role": "assistant", "content": rsp_message})
        return rsp_message
