"""消息队列工厂和全局管理器"""

from typing import Any, Dict, Optional

from lib.adapter.message_queue.base import MessageQueueAdapter
from lib.adapter.message_queue.memory_queue import MemoryMessageQueue
from lib.logger import logger


def create_message_queue(
    queue_type: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> MessageQueueAdapter:
    """
    创建消息队列实例
    
    Args:
        queue_type: 队列类型 ('memory', 'redis')
        config: 配置字典
        **kwargs: 其他参数
        
    Returns:
        消息队列实例
    """
    # 默认使用内存队列
    if queue_type is None:
        queue_type = "memory"
    
    # 合并配置
    final_config = {**(config or {}), **kwargs}
    
    if queue_type.lower() == "memory":
        logger.info("创建内存消息队列")
        return MemoryMessageQueue(**final_config)
    
    # 这里可以添加其他类型的消息队列实现
    # elif queue_type.lower() == "redis":
    #     logger.info("创建Redis消息队列")
    #     return RedisMessageQueue(**final_config)
    
    else:
        raise ValueError(f"不支持的消息队列类型: {queue_type}")


# 全局消息队列实例
_global_queue: Optional[MessageQueueAdapter] = None


def get_message_queue() -> MessageQueueAdapter:
    """
    获取全局消息队列实例
    
    Returns:
        消息队列实例
    """
    global _global_queue
    if _global_queue is None:
        _global_queue = create_message_queue()
    return _global_queue


def set_message_queue(queue: MessageQueueAdapter) -> None:
    """
    设置全局消息队列实例
    
    Args:
        queue: 消息队列实例
    """
    global _global_queue
    if _global_queue and _global_queue.is_running():
        _global_queue.stop_listening()
    _global_queue = queue
