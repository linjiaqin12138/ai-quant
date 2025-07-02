import json
from typing import List, TypedDict
from sqlalchemy import insert, select

from lib.utils.object import omit_keys
from lib.adapter.database.session import SessionAbstract
from lib.model import CryptoOrder
from .sqlalchemy import trade_action_info

TradeHistoryWithComment = TypedDict(
    "TradeHistoryWithComment", {"order": CryptoOrder, "comment": str}
)


class TradeHistory:
    def __init__(self, session: SessionAbstract):
        self.session = session

    def get_trade_history_by_reason(self, reason: str) -> List[TradeHistoryWithComment]:
        stmt = (
            select(trade_action_info)
            .where(trade_action_info.c.reason == reason)
            .order_by(trade_action_info.c.timestamp.desc())
        )
        compiled = stmt.compile()
        records = self.session.execute(compiled.string, compiled.params)

        def convert_order(record):
            record["context"] = json.loads(record["context"])
            return CryptoOrder(**omit_keys(record.order, ["comment", "reason"]))

        return [
            TradeHistoryWithComment(order=convert_order(record), comment=record.comment)
            for record in records.rows
        ]

    def add(self, order: CryptoOrder, tags: str, comment: str = None):
        stmt = insert(trade_action_info).values(
            symbol=order.symbol,
            timestamp=order.timestamp,
            action=order.side,
            reason=tags,
            amount=order.get_net_amount(),
            price=order.price,
            type=order.type,
            context=json.dumps(order.context),
            order_id=order.id,
            comment=comment,
        )
        compiled = stmt.compile()
        self.session.execute(compiled.string, compiled.params)


__all__ = ["TradeHistory"]
