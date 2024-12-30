import abc
from typing import Optional, TypedDict

GptSystemParams = TypedDict('GptSystemParams', {
    "temperature": float,      
    "top_p": float,   
    "frequency_penalty": float,
    "presence_penalty": float,
})

class GptAgentAbstract(abc.ABC):
    def __init__(self, model: str, system_prompt: Optional[str] = None, system_params: GptSystemParams = {}):
        self.model = model
        self.chat_context = []
        self.params: GptSystemParams = system_params
        if system_prompt is not None:
            self.chat_context.append({"role": "system", "content": system_prompt})

    @abc.abstractmethod
    def ask(self, question: str)-> str:
        raise Exception("Not-Implement")

    def export(self):
        pass
    
    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear(self):
        if self.chat_context and self.chat_context[0]['role'] == 'system':
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []


__all__ = [
    'GptAgentAbstract'
]