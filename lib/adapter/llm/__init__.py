from typing import Callable
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


def get_llm_tool(
    system_prompt: str, provider: str, model: str, **params
) -> Callable[[str], str]:
    llm = get_llm(provider, model, **params)

    return lambda question: llm.ask(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        # tools=params.get("tools", None),
        response_format=params.get("response_format", None),
    )


__all__ = [
    "get_llm",
    "get_llm_tool",
    "LlmParams",
    "LlmAbstract",
    "BaiChuan",
    "Paoluz",
    "G4f",
    "SiliconFlow",
]
