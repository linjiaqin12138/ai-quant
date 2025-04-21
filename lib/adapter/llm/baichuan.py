
from ...config import get_baichuan_token
from .interface import GptAgentAbstract, OpenAiApiMixin

class BaiChuanAgent(OpenAiApiMixin, GptAgentAbstract):

    def _is_support_json_rsp(self) -> bool:
        return self.model in [
            'Baichuan4-Turbo', 
            'Baichuan4-Air', 
            'Baichuan4', 
            'Baichuan3-Turbo', 
            'Baichuan3-Turbo-128k'
        ]
    
    def __init__(self, model: str = 'Baichuan3-Turbo-128k', **params):
        super().__init__(model, **params)
        self.endpoint = params.get('api_endpoint', "https://api.baichuan-ai.com")
        self.api_key = params.get('token', get_baichuan_token())
