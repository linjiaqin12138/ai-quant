"""消息队列中的消息模型"""

from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import uuid
import json


@dataclass
class QueueMessage:
    """消息队列中的消息模型"""
    
    # 消息唯一标识
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 消息主题/队列名称
    topic: str = ""
    
    # 消息内容
    payload: Any = None
    
    # 消息头部信息
    headers: Dict[str, Any] = field(default_factory=dict)
    
    # 消息创建时间
    created_at: datetime = field(default_factory=datetime.now)
    
    # 消息优先级 (1-10, 10为最高优先级)
    priority: int = 5
    
    # 消息延迟投递时间
    delay_until: Optional[datetime] = None
    
    # 重试次数
    retry_count: int = 0
    
    # 最大重试次数
    max_retries: int = 3
    
    # 消息过期时间
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'topic': self.topic,
            'payload': self.payload,
            'headers': self.headers,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'priority': self.priority,
            'delay_until': self.delay_until.isoformat() if self.delay_until else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        """从字典创建消息对象"""
        message = cls()
        message.id = data.get('id', message.id)
        message.topic = data.get('topic', '')
        message.payload = data.get('payload')
        message.headers = data.get('headers', {})
        
        if data.get('created_at'):
            message.created_at = datetime.fromisoformat(data['created_at'])
        
        message.priority = data.get('priority', 5)
        
        if data.get('delay_until'):
            message.delay_until = datetime.fromisoformat(data['delay_until'])
        
        message.retry_count = data.get('retry_count', 0)
        message.max_retries = data.get('max_retries', 3)
        
        if data.get('expires_at'):
            message.expires_at = datetime.fromisoformat(data['expires_at'])
        
        return message
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QueueMessage':
        """从JSON字符串创建消息对象"""
        return cls.from_dict(json.loads(json_str))
    
    def is_expired(self) -> bool:
        """检查消息是否已过期"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def is_ready_for_delivery(self) -> bool:
        """检查消息是否准备好投递"""
        if self.is_expired():
            return False
        if self.delay_until and datetime.now() < self.delay_until:
            return False
        return True
    
    def can_retry(self) -> bool:
        """检查消息是否可以重试"""
        return self.retry_count < self.max_retries
    
    def __lt__(self, other):
        """支持优先队列比较，使用创建时间作为次要排序"""
        if not isinstance(other, QueueMessage):
            return NotImplemented
        return self.created_at < other.created_at
    
    def __eq__(self, other):
        """相等比较"""
        if not isinstance(other, QueueMessage):
            return NotImplemented
        return self.id == other.id
