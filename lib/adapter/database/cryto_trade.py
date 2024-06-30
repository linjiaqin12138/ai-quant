import abc
import json
from sqlalchemy import insert, select, and_

from ...adapter.database.session import SessionAbstract
from ...model import CryptoOrder
from .sqlalchemy import exchange_info

class CryptoTradeHistoryAbstract(abc.ABC):
    def __init__(self, session: SessionAbstract):
        self.session = session
    @abc.abstractclassmethod
    def add(self, order: CryptoOrder, reason: str):
        raise NotImplementedError
    
class CryptoTradeHistory(CryptoTradeHistoryAbstract):
    def add(self, order: CryptoOrder, reason: str):
        stmt = insert(exchange_info).values(
            pair = order.pair,
            timestamp = order.timestamp,
            action = order.side,
            reason = reason,
            amount = order.amount,
            price = order.price,
            type = order.type,
            context = json.dumps(order.context),
            order_id = order.clientOrderId
        )
        compiled = stmt.compile()
        self.session.execute(compiled.string, compiled.params)