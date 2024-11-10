from lib.adapter.gpt import GptAgentAbstract
from typing import Optional

class FakeGpt(GptAgentAbstract):
    def __init__(self):
        self.reply: Optional[str] = None

    def set_reply(self, reply: str):
        """设置预期的回复"""
        self.reply = reply

    def ask(self, question: str) -> str:
        """返回设置的回复"""
        if self.reply is None:
            return "No reply set"
        
        response = self.reply
        self.reply = None  # 使用后清除回复
        return response
    
fake_gpt = FakeGpt()
    
