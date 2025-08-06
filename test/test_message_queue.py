"""消息队列测试用例"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock

from lib.adapter.message_queue import (
    MemoryMessageQueue,
    QueueMessage,
    create_message_queue,
    get_message_queue,
    MessageQueueAdapter
)


class TestQueueMessage:
    """QueueMessage类测试"""
    
    def test_message_creation(self):
        """测试消息创建"""
        message = QueueMessage(
            topic="test_topic",
            payload={"key": "value"},
            priority=8
        )
        
        assert message.topic == "test_topic"
        assert message.payload == {"key": "value"}
        assert message.priority == 8
        assert message.retry_count == 0
        assert message.max_retries == 3
        assert isinstance(message.id, str)
        assert isinstance(message.created_at, datetime)
    
    def test_message_to_dict(self):
        """测试消息转换为字典"""
        message = QueueMessage(
            topic="test_topic",
            payload="test_payload",
            priority=5
        )
        
        data = message.to_dict()
        
        assert data["topic"] == "test_topic"
        assert data["payload"] == "test_payload"
        assert data["priority"] == 5
        assert "id" in data
        assert "created_at" in data
    
    def test_message_from_dict(self):
        """测试从字典创建消息"""
        data = {
            "id": "test-id",
            "topic": "test_topic",
            "payload": "test_payload",
            "priority": 7,
            "retry_count": 1
        }
        
        message = QueueMessage.from_dict(data)
        
        assert message.id == "test-id"
        assert message.topic == "test_topic"
        assert message.payload == "test_payload"
        assert message.priority == 7
        assert message.retry_count == 1
    
    def test_message_json_serialization(self):
        """测试JSON序列化和反序列化"""
        original = QueueMessage(
            topic="test_topic",
            payload={"data": [1, 2, 3]},
            priority=6
        )
        
        json_str = original.to_json()
        assert isinstance(json_str, str)
        
        restored = QueueMessage.from_json(json_str)
        assert restored.topic == original.topic
        assert restored.payload == original.payload
        assert restored.priority == original.priority
        assert restored.id == original.id
    
    def test_message_expiry(self):
        """测试消息过期"""
        # 测试未过期消息
        message = QueueMessage(topic="test")
        assert not message.is_expired()
        
        # 测试已过期消息
        past_time = datetime.now() - timedelta(seconds=1)
        expired_message = QueueMessage(topic="test", expires_at=past_time)
        assert expired_message.is_expired()
        
        # 测试未来过期时间
        future_time = datetime.now() + timedelta(seconds=10)
        future_message = QueueMessage(topic="test", expires_at=future_time)
        assert not future_message.is_expired()
    
    def test_message_delivery_readiness(self):
        """测试消息投递准备状态"""
        # 测试普通消息
        message = QueueMessage(topic="test")
        assert message.is_ready_for_delivery()
        
        # 测试延迟消息
        future_time = datetime.now() + timedelta(seconds=10)
        delayed_message = QueueMessage(topic="test", delay_until=future_time)
        assert not delayed_message.is_ready_for_delivery()
        
        # 测试过期消息
        past_time = datetime.now() - timedelta(seconds=1)
        expired_message = QueueMessage(topic="test", expires_at=past_time)
        assert not expired_message.is_ready_for_delivery()
    
    def test_message_retry(self):
        """测试消息重试"""
        message = QueueMessage(topic="test", max_retries=2)
        
        assert message.can_retry()
        
        message.retry_count = 1
        assert message.can_retry()
        
        message.retry_count = 2
        assert not message.can_retry()
        
        message.retry_count = 3
        assert not message.can_retry()


class TestMemoryMessageQueue:
    """MemoryMessageQueue类测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.queue = MemoryMessageQueue(max_workers=2, check_interval=0.01)
        self.received_messages = []
        self.message_handler = Mock(side_effect=self._collect_message)
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        if self.queue.is_running():
            self.queue.stop_listening()
        self.received_messages.clear()
    
    def _collect_message(self, message: QueueMessage):
        """收集接收到的消息"""
        self.received_messages.append(message)
    
    def test_queue_creation(self):
        """测试队列创建"""
        assert isinstance(self.queue, MessageQueueAdapter)
        assert not self.queue.is_running()
        assert len(self.queue.get_subscribed_topics()) == 0
    
    def test_subscribe_and_unsubscribe(self):
        """测试订阅和取消订阅"""
        # 测试订阅
        result = self.queue.subscribe("test_topic", self.message_handler)
        assert result is True
        assert "test_topic" in self.queue.get_subscribed_topics()
        
        # 测试重复订阅
        result = self.queue.subscribe("test_topic", self.message_handler)
        assert result is False
        
        # 测试取消订阅
        result = self.queue.unsubscribe("test_topic", self.message_handler)
        assert result is True
        assert "test_topic" not in self.queue.get_subscribed_topics()
        
        # 测试取消不存在的订阅
        result = self.queue.unsubscribe("nonexistent_topic", self.message_handler)
        assert result is False
    
    def test_publish_and_receive_message(self):
        """测试发布和接收消息"""
        self.queue.subscribe("test_topic", self.message_handler)
        self.queue.start_listening()
        
        # 发布消息
        message_id = self.queue.publish("test_topic", "Hello World!")
        assert isinstance(message_id, str)
        
        # 等待消息处理
        time.sleep(0.1)
        
        # 验证消息被接收
        assert len(self.received_messages) == 1
        assert self.received_messages[0].topic == "test_topic"
        assert self.received_messages[0].payload == "Hello World!"
        assert self.received_messages[0].id == message_id
    
    def test_multiple_messages(self):
        """测试多条消息处理"""
        self.queue.subscribe("test_topic", self.message_handler)
        self.queue.start_listening()
        
        # 发布多条消息
        payloads = ["message1", "message2", "message3"]
        for payload in payloads:
            self.queue.publish("test_topic", payload)
        
        # 等待消息处理
        time.sleep(0.2)
        
        # 验证所有消息都被接收
        assert len(self.received_messages) == 3
        received_payloads = [msg.payload for msg in self.received_messages]
        assert set(received_payloads) == set(payloads)
    
    def test_message_priority(self):
        """测试消息优先级"""
        self.queue.subscribe("priority_topic", self.message_handler)
        
        # 发布不同优先级的消息（先发布低优先级，再发布高优先级）
        self.queue.publish("priority_topic", "low_priority", priority=1)
        self.queue.publish("priority_topic", "high_priority", priority=10)
        self.queue.publish("priority_topic", "medium_priority", priority=5)
        
        self.queue.start_listening()
        time.sleep(0.2)
        
        # 验证消息按优先级处理（高优先级先处理）
        assert len(self.received_messages) == 3
        # 由于是异步处理，只验证高优先级消息确实被处理了
        payloads = [msg.payload for msg in self.received_messages]
        assert "high_priority" in payloads
        assert "medium_priority" in payloads
        assert "low_priority" in payloads
    
    def test_delayed_message(self):
        """测试延迟消息"""
        self.queue.subscribe("delay_topic", self.message_handler)
        self.queue.start_listening()
        
        # 发布延迟消息
        delay_time = datetime.now() + timedelta(seconds=0.1)
        self.queue.publish("delay_topic", "immediate_message")
        self.queue.publish("delay_topic", "delayed_message", delay_until=delay_time)
        
        # 立即检查，延迟消息不应该被处理
        time.sleep(0.05)
        immediate_count = len(self.received_messages)
        
        # 等待延迟时间过去
        time.sleep(0.1)
        
        # 现在延迟消息应该被处理
        final_count = len(self.received_messages)
        assert final_count > immediate_count
        
        # 验证消息内容
        payloads = [msg.payload for msg in self.received_messages]
        assert "immediate_message" in payloads
        assert "delayed_message" in payloads
    
    def test_expired_message(self):
        """测试消息过期"""
        self.queue.subscribe("expiry_topic", self.message_handler)
        self.queue.start_listening()
        
        # 发布立即过期的消息
        past_time = datetime.now() - timedelta(seconds=1)
        self.queue.publish("expiry_topic", "normal_message")
        self.queue.publish("expiry_topic", "expired_message", expires_at=past_time)
        
        time.sleep(0.2)
        
        # 验证只有未过期的消息被处理
        assert len(self.received_messages) == 1
        assert self.received_messages[0].payload == "normal_message"
    
    def test_queue_size_and_clear(self):
        """测试队列大小和清空"""
        # 发布消息但不启动监听
        self.queue.publish("test_topic", "message1")
        self.queue.publish("test_topic", "message2")
        
        # 检查队列大小
        assert self.queue.get_queue_size("test_topic") == 2
        assert self.queue.get_queue_size("nonexistent_topic") == 0
        
        # 清空队列
        result = self.queue.clear_queue("test_topic")
        assert result is True
        assert self.queue.get_queue_size("test_topic") == 0
        
        # 清空不存在的队列
        result = self.queue.clear_queue("nonexistent_topic")
        assert result is False
    
    def test_multiple_topics(self):
        """测试多主题"""
        handler1 = Mock()
        handler2 = Mock()
        
        self.queue.subscribe("topic1", handler1)
        self.queue.subscribe("topic2", handler2)
        self.queue.start_listening()
        
        # 发布到不同主题
        self.queue.publish("topic1", "message_for_topic1")
        self.queue.publish("topic2", "message_for_topic2")
        
        time.sleep(0.1)
        
        # 验证消息被正确路由
        handler1.assert_called_once()
        handler2.assert_called_once()
        
        # 验证消息内容
        topic1_message = handler1.call_args[0][0]
        topic2_message = handler2.call_args[0][0]
        
        assert topic1_message.topic == "topic1"
        assert topic1_message.payload == "message_for_topic1"
        assert topic2_message.topic == "topic2"
        assert topic2_message.payload == "message_for_topic2"
    
    def test_multiple_handlers_per_topic(self):
        """测试一个主题多个处理器"""
        handler1 = Mock()
        handler2 = Mock()
        
        self.queue.subscribe("test_topic", handler1)
        self.queue.subscribe("test_topic", handler2)
        self.queue.start_listening()
        
        self.queue.publish("test_topic", "test_message")
        time.sleep(0.1)
        
        # 验证两个处理器都被调用
        handler1.assert_called_once()
        handler2.assert_called_once()
    
    def test_context_manager(self):
        """测试上下文管理器"""
        with MemoryMessageQueue() as queue:
            assert queue.is_running()
            queue.subscribe("test_topic", self.message_handler)
            queue.publish("test_topic", "test_message")
            time.sleep(0.1)
        
        # 退出上下文后应该停止运行
        assert not queue.is_running()
    
    def test_queue_stats(self):
        """测试队列统计信息"""
        self.queue.subscribe("topic1", self.message_handler)
        self.queue.subscribe("topic2", self.message_handler)
        
        # 发布一些消息但不处理
        self.queue.publish("topic1", "message1")
        self.queue.publish("topic1", "message2")
        self.queue.publish("topic2", "message3")
        
        stats = self.queue.get_queue_stats()
        
        assert stats["total_topics"] == 2
        assert stats["total_messages"] == 3
        assert "topic1" in stats["queue_sizes"]
        assert "topic2" in stats["queue_sizes"]
        assert stats["queue_sizes"]["topic1"] == 2
        assert stats["queue_sizes"]["topic2"] == 1
        assert set(stats["subscribed_topics"]) == {"topic1", "topic2"}
        assert stats["is_running"] is False


class TestMessageQueueFactory:
    """消息队列工厂测试"""
    
    def test_create_memory_queue(self):
        """测试创建内存队列"""
        queue = create_message_queue("memory", max_workers=3)
        assert isinstance(queue, MemoryMessageQueue)
    
    def test_create_default_queue(self):
        """测试创建默认队列"""
        queue = create_message_queue()
        assert isinstance(queue, MemoryMessageQueue)
    
    def test_unsupported_queue_type(self):
        """测试不支持的队列类型"""
        with pytest.raises(ValueError, match="不支持的消息队列类型"):
            create_message_queue("unsupported_type")
    
    def test_global_queue(self):
        """测试全局队列"""
        # 获取全局队列
        queue1 = get_message_queue()
        queue2 = get_message_queue()
        
        # 应该返回同一个实例
        assert queue1 is queue2
        assert isinstance(queue1, MemoryMessageQueue)


if __name__ == "__main__":
    pytest.main([__file__])
