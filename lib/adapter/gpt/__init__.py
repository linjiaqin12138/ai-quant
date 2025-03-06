
from .baichuan import BaiChuanAgent
from .g4f import G4fAgent
from .paoluz import PaoluzAgent
from .siliconflow import SiliconFlowAgent
from .interface import GptAgentAbstract

def get_agent(provider: str, model: str, **params) -> GptAgentAbstract:
    if provider == 'baichuan':
        return BaiChuanAgent(model, **params)
    
    if provider == 'paoluz':
        return PaoluzAgent(model, **params)
    
    if provider == 'g4f':
        return G4fAgent(model, **params)
    
    if provider == 'siliconflow':
        return SiliconFlowAgent(model, **params)

    raise ValueError(f"Unsupported provider: {provider}")
    
__all__ = [
    'get_agent',
    'GptAgentAbstract',
    'BaiChuanAgent',
    'PaoluzAgent',
    'G4fAgent',
    'SiliconFlowAgent'
]