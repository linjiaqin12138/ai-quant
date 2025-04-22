from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .camel import CamelModel

# Define literal types with English names
RiskPreferLiteral = Literal["risk_averse", "stable", "risk_seeking"]
StrategyPreferLiteral = Literal["long_term", "short_term", "buy_low_sell_high", "trend_following"]

class LLMSetting(BaseModel):
    """LLM Model Settings"""
    model: str = Field(..., description="Model name, e.g. gpt-3.5-turbo")
    temperature: float = Field(..., ge=0, le=1, description="Temperature parameter to control randomness of output, range 0-1")

class History(CamelModel):
    """Trading History Record"""
    timestamp: int = Field(..., description="Timestamp of the trade")
    action: Literal['buy', 'sell'] = Field(..., description="Trade action: buy or sell")
    buy_cost: Optional[float] = Field(None, ge=0, description="Cost of buying")
    sell_amount: Optional[float] = Field(None, ge=0, description="Amount to sell")
    position_ratio: Optional[float] = Field(None, ge=0, le=1, description="Position ratio")
    price: float = Field(..., ge=0, description="Trading price")
    summary: str = Field(..., description="Trade summary")

    @field_validator('buy_cost')
    @classmethod
    def buy_cost_required_if_buy(cls, value, info):
        if info.data.get('action') == 'buy' and value is None:
            raise ValueError('buy_cost is required when action is buy')
        return value

    @field_validator('sell_amount')
    @classmethod
    def sell_amount_required_if_sell(cls, value, info):
        if info.data.get('action') == 'sell' and value is None:
            raise ValueError('sell_amount is required when action is sell')
        return value

class TradeAdviceReq(CamelModel):
    """Trade Input Model"""
    model_config = ConfigDict(title='TradeAdviceRequest', validate_assignment=True)

    symbol: str = Field(..., description="Trading pair, e.g. BTC/USDT")
    market: Literal["crypto", "stock"] = Field(..., description="Market type, e.g. crypto")
    risk_prefer: RiskPreferLiteral = Field(
        ..., 
        description="Risk preference: risk-averse, stable, growth-investment, or risk-seeking"
    )
    strategy_prefer: StrategyPreferLiteral = Field(
        ..., 
        description="Strategy preference: long-term-investment, short-term, buy-low-sell-high, or trend-following"
    )
    llm_settings: List[LLMSetting] = Field(
        ..., 
        min_length=1, 
        max_length=4, 
        description="LLM settings, minimum 1 setting required"
    )
    historys: List[History] = Field(..., description="Historical trading records")
    hold_amount: float = Field(..., ge=0, description="Amount currently holding, must be greater than or equal to 0")
    remaining: float = Field(..., ge=0, description="Remaining amount, must be greater than or equal to 0")
    callback_url: str = Field(..., description="Callback URL, e.g. http://localhost:5000/ai/simtrade")
    id: str = Field(..., description="Request ID, e.g. 50738043-a339-4508-bd73-4f3582088f7a")