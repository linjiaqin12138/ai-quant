from lib.config import get_baichuan_token
from .interface import LlmAbstract
from .openai_compatible import OpenAiApiMixin


class BaiChuan(OpenAiApiMixin, LlmAbstract):
    def _is_support_json_rsp(self) -> bool:
        return self.model in [
            "Baichuan4-Turbo",
            "Baichuan4-Air",
            "Baichuan4",
            "Baichuan3-Turbo",
            "Baichuan3-Turbo-128k",
        ]

    def __init__(self, model: str = "Baichuan3-Turbo-128k", **params):
        super().__init__(model, **params)
        self.endpoint = params.get("endpoint", "https://api.baichuan-ai.com")
        self.api_key = params.get("api_key", get_baichuan_token())
