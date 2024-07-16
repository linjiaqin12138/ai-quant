from lib.logger import logger
from lib.adapter.notification import NotificationAbstract

class FakeNotification(NotificationAbstract):
    def send(self, content: str, title: str = ''):
        logger.info('Send Notification:')
        logger.info(f'Title: {title}')
        logger.info(f'Content: {content}')