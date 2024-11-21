from lib.logger import logger
from lib.adapter.notification import NotificationAbstract
from lib.modules.notification_logger import NotificationLogger

class FakeNotification(NotificationAbstract):
    def send(self, content: str, title: str = ''):
        logger.info('Send Notification:')
        logger.info(f'Title: {title}')
        logger.info(f'Content: {content}')

fake_notification_logger =  NotificationLogger('Fake Notification', FakeNotification())