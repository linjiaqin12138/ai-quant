from typing import Callable, Optional
from .baichuan import BaiChuan
from .g4f import G4f
from .paoluz import PaoluzAgent
from .siliconflow import SiliconFlow
from .interface import LlmAbstract, LlmParams


def get_llm(provider: str, model: str, **params) -> LlmAbstract:
    if provider == "baichuan":
        return BaiChuan(model, **params)

    if provider == "paoluz":
        return PaoluzAgent(model, **params)

    if provider == "g4f":
        return G4f(model, **params)

    if provider == "siliconflow":
        return SiliconFlow(model, **params)

    raise ValueError(f"Unsupported provider: {provider}")


def get_llm_direct_ask(
    system_prompt: Optional[str] = None, 
    provider: Optional[str] = 'paoluz', 
    model: Optional[str] = 'gpt-4o-mini', 
    llm: Optional[LlmAbstract] = None,
    **params
) -> Callable[[str], str]:
    llm = llm or get_llm(provider, model, **params)
    context = []
    if system_prompt:
        context.append({"role": "system", "content": system_prompt})
    
    return lambda question: llm.chat(
        context + 
        [
            {"role": "user", "content": question},
        ],
        response_format=params.get("response_format", None),
    )['content']


__all__ = [
    "get_llm",
    "get_llm_direct_ask",
    "LlmParams",
    "LlmAbstract",
    "BaiChuan",
    "PaoluzAgent",
    "G4f",
    "OpenAICompatible",
]
