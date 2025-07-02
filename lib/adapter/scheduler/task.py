#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    CANCELED = "canceled"  # 已取消


class Task:
    """任务基类，表示一个可执行的任务"""

    def __init__(
        self,
        func: Callable,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        task_id: str = None,
        priority: int = 0,
        retry_count: int = 0,
        retry_interval: int = 5,
        timeout: int = None,
        description: str = "",
    ):
        """
        初始化一个任务

        Args:
            func: 要执行的函数
            args: 位置参数列表
            kwargs: 关键字参数字典
            task_id: 任务ID，如果不指定则自动生成
            priority: 优先级，数字越大优先级越高
            retry_count: 失败重试次数
            retry_interval: 重试间隔（秒）
            timeout: 超时时间（秒），None表示无超时限制
            description: 任务描述
        """
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.task_id = task_id or str(uuid.uuid4())
        self.priority = priority
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.timeout = timeout
        self.description = description

        # 任务状态信息
        self.status = TaskStatus.PENDING
        self.create_time = datetime.now()
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.retry_attempts = 0

    def __lt__(self, other):
        """用于优先级队列比较"""
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority > other.priority  # 优先级数值大的先执行

    def execute(self) -> Any:
        """执行任务并返回结果"""
        self.start_time = datetime.now()
        self.status = TaskStatus.RUNNING

        try:
            start = time.time()

            # 执行带超时的任务
            if self.timeout:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.func, *self.args, **self.kwargs)
                    try:
                        self.result = future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        raise TimeoutError(f"任务执行超时 ({self.timeout}秒)")
            else:
                # 无超时直接执行
                self.result = self.func(*self.args, **self.kwargs)

            execution_time = time.time() - start
            self.status = TaskStatus.COMPLETED
            return self.result

        except Exception as e:
            self.error = str(e)
            self.status = TaskStatus.FAILED
            raise
        finally:
            self.end_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为字典"""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "retry_attempts": self.retry_attempts,
            "retry_count": self.retry_count,
        }


class PeriodicTask(Task):
    """周期性任务"""

    def __init__(
        self,
        func: Callable,
        interval: int,  # 间隔秒数
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        task_id: str = None,
        priority: int = 0,
        retry_count: int = 0,
        retry_interval: int = 5,
        timeout: int = None,
        description: str = "",
    ):
        super().__init__(
            func,
            args,
            kwargs,
            task_id,
            priority,
            retry_count,
            retry_interval,
            timeout,
            description,
        )
        self.interval = interval
        self.last_run = None
        self.next_run = datetime.now()

    def update_next_run(self):
        """更新下次运行时间"""
        self.last_run = datetime.now()
        self.next_run = self.last_run.fromtimestamp(
            self.last_run.timestamp() + self.interval
        )

    def to_dict(self) -> Dict[str, Any]:
        """将周期任务转换为字典"""
        result = super().to_dict()
        result.update(
            {
                "interval": self.interval,
                "last_run": self.last_run.isoformat() if self.last_run else None,
                "next_run": self.next_run.isoformat() if self.next_run else None,
            }
        )
        return result
