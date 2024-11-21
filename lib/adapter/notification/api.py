import abc


class NotificationAbstract(abc.ABC):

    @abc.abstractmethod
    def send(self, content: str, title: str = ''):
        raise NotImplementedError("Invalid Notification Instance")