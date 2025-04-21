#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务调度框架
============

提供异步任务调度和执行功能，支持一次性任务和周期性任务，可设置并发数量。

基本用法:
    from lib.adapter.scheduler import TaskScheduler, Task, PeriodicTask

    # 创建调度器
    scheduler = TaskScheduler(max_workers=5)  # 5个并发线程
    
    # 启动调度器
    scheduler.start()
    
    # 注册普通任务
    def my_task(a, b):
        return a + b
        
    task_id = scheduler.register_task(
        func=my_task,
        args=[1, 2],
        description="测试任务"
    )
    
    # 注册周期任务
    def periodic_job():
        print("周期任务执行")
        
    periodic_task_id = scheduler.register_periodic_task(
        func=periodic_job,
        interval=60,  # 每60秒执行一次
        description="测试周期任务"
    )
    
    # 获取任务状态
    status = scheduler.get_task_status(task_id)
    
    # 获取任务结果
    result = scheduler.get_task_result(task_id)
    
    # 停止调度器
    scheduler.stop()
"""

from .task import Task, PeriodicTask, TaskStatus
from .worker import Worker
from .scheduler import TaskScheduler

__all__ = ['Task', 'PeriodicTask', 'TaskStatus', 'Worker', 'TaskScheduler']