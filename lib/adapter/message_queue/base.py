"""消息队列抽象基类"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from lib.model.message import QueueMessage
from lib.logger import logger

# 消息处理器类型定义
MessageHandler = Callable[[QueueMessage], Any]
AsyncMessageHandler = Callable[[QueueMessage], Any]


class MessageQueueAdapter(ABC):
    """消息队列抽象基类"""
    
    def __init__(self, max_workers: int = 4):
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._async_handlers: Dict[str, List[AsyncMessageHandler]] = {}
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._stop_event = threading.Event()
    
    @abstractmethod
    def publish(
        self, 
        topic: str, 
        payload: Any, 
        headers: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        delay_until: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ) -> str:
        """
        发布消息到指定主题
        
        Args:
            topic: 消息主题
            payload: 消息内容
            headers: 消息头部信息
            priority: 优先级 (1-10)
            delay_until: 延迟投递时间
            expires_at: 消息过期时间
            
        Returns:
            消息ID
        """
        pass
    
    @abstractmethod
    def publish_message(self, message: QueueMessage) -> str:
        """
        发布消息对象
        
        Args:
            message: 消息对象
            
        Returns:
            消息ID
        """
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, handler: MessageHandler) -> bool:
        """
        订阅主题消息
        
        Args:
            topic: 消息主题
            handler: 消息处理器
            
        Returns:
            是否订阅成功
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, topic: str, handler: Optional[MessageHandler] = None) -> bool:
        """
        取消订阅
        
        Args:
            topic: 消息主题
            handler: 消息处理器，如果为None则取消该主题的所有订阅
            
        Returns:
            是否取消成功
        """
        pass
    
    @abstractmethod
    def get_queue_size(self, topic: str) -> int:
        """
        获取队列大小
        
        Args:
            topic: 消息主题
            
        Returns:
            队列中消息数量
        """
        pass
    
    @abstractmethod
    def clear_queue(self, topic: str) -> bool:
        """
        清空队列
        
        Args:
            topic: 消息主题
            
        Returns:
            是否清空成功
        """
        pass
    
    @abstractmethod
    def start_listening(self) -> None:
        """开始监听消息"""
        pass
    
    @abstractmethod
    def stop_listening(self) -> None:
        """停止监听消息"""
        pass
    
    def subscribe_async(self, topic: str, handler: AsyncMessageHandler) -> bool:
        """
        订阅主题消息（异步处理器）
        
        Args:
            topic: 消息主题
            handler: 异步消息处理器
            
        Returns:
            是否订阅成功
        """
        if topic not in self._async_handlers:
            self._async_handlers[topic] = []
        
        if handler not in self._async_handlers[topic]:
            self._async_handlers[topic].append(handler)
            logger.info(f"异步订阅主题 {topic}")
            return True
        return False
    
    def unsubscribe_async(self, topic: str, handler: Optional[AsyncMessageHandler] = None) -> bool:
        """
        取消异步订阅
        
        Args:
            topic: 消息主题
            handler: 异步消息处理器，如果为None则取消该主题的所有异步订阅
            
        Returns:
            是否取消成功
        """
        if topic not in self._async_handlers:
            return False
        
        if handler is None:
            del self._async_handlers[topic]
            logger.info(f"取消主题 {topic} 的所有异步订阅")
            return True
        
        if handler in self._async_handlers[topic]:
            self._async_handlers[topic].remove(handler)
            logger.info(f"取消主题 {topic} 的异步订阅")
            if not self._async_handlers[topic]:
                del self._async_handlers[topic]
            return True
        return False
    
    def _handle_message(self, message: QueueMessage) -> None:
        """
        处理消息
        
        Args:
            message: 消息对象
        """
        topic = message.topic
        
        # 处理同步订阅者
        if topic in self._handlers:
            for handler in self._handlers[topic]:
                try:
                    self._executor.submit(self._safe_handle_message, handler, message)
                except Exception as e:
                    logger.error(f"处理消息时发生错误: {e}")
        
        # 处理异步订阅者
        if topic in self._async_handlers:
            for handler in self._async_handlers[topic]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(self._safe_handle_async_message(handler, message))
                    else:
                        self._executor.submit(self._safe_handle_message, handler, message)
                except Exception as e:
                    logger.error(f"处理异步消息时发生错误: {e}")
    
    def _safe_handle_message(self, handler: MessageHandler, message: QueueMessage) -> None:
        """
        安全处理消息
        
        Args:
            handler: 消息处理器
            message: 消息对象
        """
        try:
            handler(message)
            logger.debug(f"消息处理成功: {message.id}")
        except Exception as e:
            logger.error(f"消息处理失败: {message.id}, 错误: {e}")
            # 这里可以实现重试逻辑
            if message.can_retry():
                message.retry_count += 1
                logger.info(f"消息 {message.id} 重试第 {message.retry_count} 次")
                # 重新发布消息进行重试
                self.publish_message(message)
    
    async def _safe_handle_async_message(self, handler: AsyncMessageHandler, message: QueueMessage) -> None:
        """
        安全处理异步消息
        
        Args:
            handler: 异步消息处理器
            message: 消息对象
        """
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
            logger.debug(f"异步消息处理成功: {message.id}")
        except Exception as e:
            logger.error(f"异步消息处理失败: {message.id}, 错误: {e}")
            # 这里可以实现重试逻辑
            if message.can_retry():
                message.retry_count += 1
                logger.info(f"消息 {message.id} 异步重试第 {message.retry_count} 次")
                # 重新发布消息进行重试
                self.publish_message(message)
    
    def get_subscribed_topics(self) -> List[str]:
        """
        获取已订阅的主题列表
        
        Returns:
            主题列表
        """
        topics = set()
        topics.update(self._handlers.keys())
        topics.update(self._async_handlers.keys())
        return list(topics)
    
    def is_running(self) -> bool:
        """
        检查是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_listening()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop_listening()
        self._executor.shutdown(wait=True)
