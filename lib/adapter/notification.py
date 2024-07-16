import os
import abc

import requests

from ..config import get_push_token
from ..logger import logger

class NotificationAbstract(abc.ABC):

    @abc.abstractmethod
    def send(self, content: str, title: str = ''):
        raise NotImplementedError

class PushPlus(NotificationAbstract):
    def __init__(self):
        self.token = get_push_token()
        if not self.token:
            raise Exception("Push plus token is not set")
    def send(self, content: str, title: str = ''):
        logger.debug(f'Send Push Plus Notification: title: {title}, content: {content}')
        try:
            # TODO Support Retry
            res = requests.post(
                "http://www.pushplus.plus/send",
                {
                    "token": os.environ.get("PUSH_PLUS_TOKEN"),
                    "content": content,
                    "title": title
                },
            )

            return {"success": res.json()["code"] == 200}
        except:
            return {"success": False}
    