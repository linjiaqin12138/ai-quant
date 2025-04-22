import abc
from typing import TypedDict, Literal, Optional, List

LlmParams = TypedDict('LlmParams', {
    "temperature": Optional[float],      
    "top_p": Optional[float],   
    "frequency_penalty": Optional[float],
    "presence_penalty": Optional[float],
    "response_format": Optional[Literal['json']],
    "max_token": Optional[int],
    "api_key": Optional[str],
    "endpoint": Optional[str]
})

class LlmAbstract(abc.ABC):
    def __init__(self, model: str, **system_params):
        self.model = model
        self.params: LlmParams = system_params
    
    @abc.abstractmethod
    def ask(self, context: List) -> str:
        raise Exception("Not-Implement")

class Agent:
    def __init__(self, llm: LlmAbstract):
        self.llm = llm
        self.chat_context = []

    def ask(self, question: str)-> str:
        self.chat_context.append({"role": "user", "content": question})
        rsp_message = self.llm.ask(self.chat_context)
        self.chat_context.append({"role": "assistant", "content": rsp_message})
        return rsp_message

    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear(self):
        if self.chat_context and self.chat_context[0]['role'] == 'system':
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []

__all__ = [
    'LlmAbstract',
    'Agent'
]