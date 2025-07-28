import requests

from ...config import get_push_token, API_MAX_RETRY_TIMES
from ...logger import logger
from ...utils.decorators import with_retry

from .api import NotificationAbstract

class PushPlus(NotificationAbstract):
    def __init__(self, template: str = "markdown"):
        self.token = get_push_token()
        self.template = template
        if not self.token:
            raise Exception("Push plus token is not set")

    def send(self, content: str, title: str = ""):
        logger.debug(f"Send Push Plus Notification: title: {title}, content: {content}")

        @with_retry(
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
            ),
            API_MAX_RETRY_TIMES,
        )
        def retryable_part():
            res = requests.post(
                "https://www.pushplus.plus/send",
                {"token": self.token, "content": content, "title": title, "template": self.template},
            )
            logger.debug(f"PushPlus reply with body {res.content}")
            rspBody = res.json()
            if rspBody["code"] == 200:
                logger.info(f"Send push plus notification success")
                return
            logger.error(f"Pushplus reply failed {rspBody}")
            # TODO identify retryable error by document and network failure and add retry

        return retryable_part()
