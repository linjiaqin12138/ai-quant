import os
import abc

import requests

from ..config import get_push_token
from ..logger import logger
from ..utils.retry import with_retry

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
    
        def retryable_part():
            res = requests.post(
                "http://www.pushplus.plus/send",
                {
                    "token": os.environ.get("PUSH_PLUS_TOKEN"),
                    "content": content,
                    "title": title
                },
            )
            logger.debug(f"PushPlus reply with body {res.content}")
            rspBody = res.json()
            if rspBody['code'] == 200:
                logger.info(f"Send push plus notification success")
                return
            logger.error(f"Pushplus reply failed {rspBody}")
            #TODO identify retryable error by document and network failure and add retry 
        
        return retryable_part()
    