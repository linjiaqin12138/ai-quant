from typing import List, Any
from lib.adapter.notification import NotificationAbstract
from lib.logger import logger


class NotificationLogger:

    def __init__(self, topic: str, notification: NotificationAbstract) -> None:
        self.sender = notification
        self.topic = topic
        self.message_pool: List[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.send()

    def msg(self, *msgs: List[Any]):
        temp_message = ""
        for msg in msgs:
            if type(msg) == float:
                temp_message += "%.4g" % msg  # 保留4位有效数字
            elif type(msg) == str:
                temp_message += msg
            else:
                temp_message += f"{msg}"
        if len(temp_message):
            logger.info(temp_message)
            self.message_pool.append(temp_message)

    def send(self) -> None:
        if len(self.message_pool):
            self.sender.send("\n".join(self.message_pool), self.topic)
