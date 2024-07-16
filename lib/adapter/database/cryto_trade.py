import abc
import json
from sqlalchemy import insert

from ...adapter.database.session import SqlAlchemySession
from ...model import CryptoOrder
from .sqlalchemy import trade_action_info

class CryptoTradeHistoryAbstract(abc.ABC):
    @abc.abstractmethod
    def add(self, order: CryptoOrder, reason: str):
        raise NotImplementedError
    
class CryptoTradeHistory(CryptoTradeHistoryAbstract):
    def __init__(self, session: SqlAlchemySession):
        self.session = session
    def add(self, order: CryptoOrder, reason: str):
        stmt = insert(trade_action_info).values(
            pair = order.pair,
            timestamp = order.timestamp,
            action = order.side,
            reason = reason,
            amount = order.amount,
            price = order.price,
            type = order.type,
            context = json.dumps(order.context),
            order_id = order.id
        )
        compiled = stmt.compile()
        self.session.execute(compiled.string, compiled.params)