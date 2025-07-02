from lib.config import get_silicon_token
from .interface import LlmAbstract
from .openai_compatible import OpenAiApiMixin


class SiliconFlow(OpenAiApiMixin, LlmAbstract):

    def __init__(self, model: str = "deepseek-ai/DeepSeek-V3", **params):
        super().__init__(model, **params)
        self.api_key = params.get("api_key", get_silicon_token())
        self.endpoint = params.get("api_endpoint", "https://api.siliconflow.cn")


if __name__ == "__main__":
    agent = SiliconFlow(model="deepseek-ai/DeepSeek-V3")
    print(agent.ask([{"role": "user", "content": "Hello, how are you?"}]))
