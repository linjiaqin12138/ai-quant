
from .baichuan import BaiChuanAgent
from .g4f import G4fAgent
from .interface import GptAgentAbstract, GptSystemParams

def get_agent_by_model(model: str, system_params: GptSystemParams = {}) -> GptAgentAbstract:
    if model.startswith("Baichuan"):
        return BaiChuanAgent(model, system_params=system_params)
    else:
        return G4fAgent(model, system_params=system_params)
    
__all__ = [
    'get_agent_by_model',
    'GptAgentAbstract',
    'BaiChuanAgent',
    'G4fAgent'
]