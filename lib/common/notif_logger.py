import logging
import os
from typing import Callable

from lib.notification.push.push_plus import send_push


class NotificationLogger(logging.getLoggerClass()):
    message_store = []

    def __init__(self, name: str):
        super(name)
        log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper())
        self.setLevel(log_level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        self.addHandler(console_handler)

    def commit(self) -> None:
        send_push({"title": self.title, "content": "\n".join(self.message_store)})

    def _log(self, level: int, msg: str, args: tuple, kwargs: dict) -> None:
        self.message_store.append(msg)
        super()._log(level, msg, args, **kwargs)

    def __getattr__(self, name: str) -> Callable:
        if name in ["info", "debug", "error", "warning"]:

            def log_method(msg: str, *args, **kwargs) -> None:
                self._log(logging._nameToLevel[name.upper()], msg, args, **kwargs)

            return log_method
        return super().__getattr__(name)


__all__ = ["NotificationLogger"]
