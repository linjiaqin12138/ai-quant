"""基于内存的消息队列实现"""

import threading
import time
from queue import PriorityQueue, Empty
from typing import Any, Dict, Optional
from datetime import datetime

from lib.adapter.message_queue.base import MessageQueueAdapter, MessageHandler
from lib.model.message import QueueMessage
from lib.logger import logger


class MemoryMessageQueue(MessageQueueAdapter):
    """基于内存的消息队列实现"""
    
    def __init__(self, max_workers: int = 4, check_interval: float = 0.1):
        super().__init__(max_workers)
        self._queues: Dict[str, PriorityQueue] = {}
        self._queue_locks = threading.RLock()
        self._check_interval = check_interval
        self._listener_thread: Optional[threading.Thread] = None
    
    def publish(
        self, 
        topic: str, 
        payload: Any, 
        headers: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        delay_until: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ) -> str:
        """发布消息到指定主题"""
        message = QueueMessage(
            topic=topic,
            payload=payload,
            headers=headers or {},
            priority=priority,
            delay_until=delay_until,
            expires_at=expires_at
        )
        return self.publish_message(message)
    
    def publish_message(self, message: QueueMessage) -> str:
        """发布消息对象"""
        with self._queue_locks:
            if message.topic not in self._queues:
                self._queues[message.topic] = PriorityQueue()
            
            # 使用负优先级实现高优先级优先处理（PriorityQueue是最小堆）
            priority_item = (-message.priority, message.created_at.timestamp(), message)
            self._queues[message.topic].put(priority_item)
            
            logger.debug(f"消息已发布到主题 {message.topic}: {message.id}")
            return message.id
    
    def subscribe(self, topic: str, handler: MessageHandler) -> bool:
        """订阅主题消息"""
        if topic not in self._handlers:
            self._handlers[topic] = []
        
        if handler not in self._handlers[topic]:
            self._handlers[topic].append(handler)
            logger.info(f"订阅主题 {topic}")
            return True
        return False
    
    def unsubscribe(self, topic: str, handler: Optional[MessageHandler] = None) -> bool:
        """取消订阅"""
        if topic not in self._handlers:
            return False
        
        if handler is None:
            del self._handlers[topic]
            logger.info(f"取消主题 {topic} 的所有订阅")
            return True
        
        if handler in self._handlers[topic]:
            self._handlers[topic].remove(handler)
            logger.info(f"取消主题 {topic} 的订阅")
            if not self._handlers[topic]:
                del self._handlers[topic]
            return True
        return False
    
    def get_queue_size(self, topic: str) -> int:
        """获取队列大小"""
        with self._queue_locks:
            if topic not in self._queues:
                return 0
            return self._queues[topic].qsize()
    
    def clear_queue(self, topic: str) -> bool:
        """清空队列"""
        with self._queue_locks:
            if topic not in self._queues:
                return False
            
            # 清空队列
            while not self._queues[topic].empty():
                try:
                    self._queues[topic].get_nowait()
                except Empty:
                    break
            
            logger.info(f"已清空主题 {topic} 的队列")
            return True
    
    def start_listening(self) -> None:
        """开始监听消息"""
        if self._running:
            logger.warning("消息队列已在运行中")
            return
        
        self._running = True
        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        logger.info("消息队列开始监听")
    
    def stop_listening(self) -> None:
        """停止监听消息"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
        
        logger.info("消息队列停止监听")
    
    def _listen_loop(self) -> None:
        """消息监听循环"""
        while self._running and not self._stop_event.is_set():
            try:
                with self._queue_locks:
                    topics_to_process = list(self._queues.keys())
                
                for topic in topics_to_process:
                    if not self._running:
                        break
                    
                    self._process_topic_messages(topic)
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(self._check_interval)
                
            except Exception as e:
                logger.error(f"消息监听循环发生错误: {e}")
                time.sleep(1)  # 发生错误时休眠1秒
    
    def _process_topic_messages(self, topic: str) -> None:
        """处理特定主题的消息"""
        # 检查是否有订阅者
        if topic not in self._handlers and topic not in self._async_handlers:
            return
        
        with self._queue_locks:
            if topic not in self._queues:
                return
            
            queue = self._queues[topic]
            messages_to_requeue = []
            
            # 处理队列中的消息
            while not queue.empty():
                try:
                    priority_item = queue.get_nowait()
                    _, _, message = priority_item
                    
                    assert isinstance(message, QueueMessage), "队列中的项不是QueueMessage类型"
                    # 检查消息是否过期
                    if message.is_expired():
                        logger.debug(f"消息已过期，丢弃: {message.id}")
                        continue
                    
                    # 检查消息是否准备好投递
                    if not message.is_ready_for_delivery():
                        # 重新入队
                        messages_to_requeue.append(priority_item)
                        continue
                    
                    # 处理消息
                    self._handle_message(message)
                    
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"处理主题 {topic} 消息时发生错误: {e}")
            
            # 重新入队延迟消息
            for item in messages_to_requeue:
                queue.put(item)
    
    def get_all_queue_sizes(self) -> Dict[str, int]:
        """获取所有队列的大小"""
        with self._queue_locks:
            return {topic: queue.qsize() for topic, queue in self._queues.items()}
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        with self._queue_locks:
            stats = {
                'total_topics': len(self._queues),
                'total_messages': sum(queue.qsize() for queue in self._queues.values()),
                'queue_sizes': self.get_all_queue_sizes(),
                'subscribed_topics': self.get_subscribed_topics(),
                'is_running': self.is_running()
            }
            return stats
