"""消息队列适配器模块"""

from lib.adapter.message_queue.base import MessageQueueAdapter, MessageHandler, AsyncMessageHandler
from lib.adapter.message_queue.memory_queue import MemoryMessageQueue
from lib.adapter.message_queue.factory import create_message_queue, get_message_queue, set_message_queue
from lib.model.message import QueueMessage

__all__ = [
    'MessageQueueAdapter',
    'MessageHandler', 
    'AsyncMessageHandler',
    'MemoryMessageQueue',
    'QueueMessage',
    'create_message_queue',
    'get_message_queue',
    'set_message_queue'
]
