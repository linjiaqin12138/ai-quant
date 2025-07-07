# from dataclasses import dataclass

# @dataclass
class LlmReplyInvalid(Exception):
    """LLM回复错误异常"""
    def __init__(self, message: str, llm_reply: str):
        super().__init__(message)
        self.llm_reply = llm_reply