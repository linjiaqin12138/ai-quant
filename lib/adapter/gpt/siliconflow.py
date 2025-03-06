
from lib.config import get_silicon_token
from .interface import GptAgentAbstract, OpenAiApiMixin

class SiliconFlowAgent(OpenAiApiMixin, GptAgentAbstract):
    
    def __init__(self, model: str = 'deepseek-ai/DeepSeek-V3', **params):
        super().__init__(model, **params)
        self.api_key = params.get('api_key', get_silicon_token())
        self.endpoint = params.get('api_endpoint', "https://api.siliconflow.cn")

