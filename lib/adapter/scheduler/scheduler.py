#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import threading
import heapq
from queue import PriorityQueue, Empty
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from lib.logger import logger
from .task import Task, PeriodicTask, TaskStatus
from .worker import Worker

class TaskScheduler:
    """任务调度器，负责管理任务队列和调度任务执行"""
    
    def __init__(self, max_workers: int = 5, use_process: bool = False):
        """
        初始化任务调度器
        
        Args:
            max_workers: 最大并发工作线程/进程数
            use_process: 是否使用进程池（True）或线程池（False）
        """
        self.worker = Worker(max_workers=max_workers, use_process=use_process)
        
        # 任务队列 (优先级队列)
        self.task_queue = PriorityQueue()
        
        # 任务记录
        self.tasks = {}  # task_id -> Task
        self.periodic_tasks = {}  # task_id -> PeriodicTask
        
        # 调度线程
        self._scheduler_thread = None
        self._running = False
        
        # 用于在任务完成时执行的回调
        self._task_callbacks = {}  # task_id -> callback_func
        
        # 任务完成结果
        self._task_results = {}  # task_id -> result
        
        # 用于线程同步
        self._lock = threading.RLock()

    def register_task(
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
        callback: Callable[[str, Any], None] = None
    ) -> str:
        """
        注册一个任务
        
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
            callback: 任务完成后的回调函数，接收task_id和result两个参数
            
        Returns:
            str: 任务ID
        """
        with self._lock:
            task = Task(
                func=func,
                args=args,
                kwargs=kwargs,
                task_id=task_id,
                priority=priority,
                retry_count=retry_count,
                retry_interval=retry_interval,
                timeout=timeout,
                description=description
            )
            
            self.tasks[task.task_id] = task
            self.task_queue.put(task)
            
            if callback:
                self._task_callbacks[task.task_id] = callback
                
            logger.info(f"已注册任务: {task.task_id} - {description}")
            return task.task_id

    def register_periodic_task(
        self,
        func: Callable,
        interval: int,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        task_id: str = None,
        priority: int = 0,
        retry_count: int = 0,
        retry_interval: int = 5,
        timeout: int = None,
        description: str = "",
        callback: Callable[[str, Any], None] = None
    ) -> str:
        """
        注册一个周期性任务
        
        Args:
            func: 要执行的函数
            interval: 执行间隔（秒）
            args: 位置参数列表
            kwargs: 关键字参数字典
            task_id: 任务ID，如果不指定则自动生成
            priority: 优先级，数字越大优先级越高
            retry_count: 失败重试次数
            retry_interval: 重试间隔（秒）
            timeout: 超时时间（秒），None表示无超时限制
            description: 任务描述
            callback: 任务完成后的回调函数，接收task_id和result两个参数
            
        Returns:
            str: 任务ID
        """
        with self._lock:
            task = PeriodicTask(
                func=func,
                interval=interval,
                args=args,
                kwargs=kwargs,
                task_id=task_id,
                priority=priority,
                retry_count=retry_count,
                retry_interval=retry_interval,
                timeout=timeout,
                description=description
            )
            
            self.periodic_tasks[task.task_id] = task
            
            if callback:
                self._task_callbacks[task.task_id] = callback
                
            logger.info(f"已注册周期任务: {task.task_id} - {description} (每 {interval} 秒执行一次)")
            return task.task_id
            
    def start(self):
        """启动任务调度线程"""
        if self._running:
            logger.warning("调度器已在运行")
            return
            
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("任务调度器已启动")
        
    def stop(self):
        """停止任务调度线程"""
        if not self._running:
            logger.warning("调度器未在运行")
            return
            
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
        self.worker.shutdown(wait=True)
        logger.info("任务调度器已停止")
    
    def _scheduler_loop(self):
        """调度线程主循环"""
        while self._running:
            try:
                # 处理周期性任务
                self._check_periodic_tasks()
                
                # 从队列中获取任务
                try:
                    task = self.task_queue.get(block=False)
                    
                    # 提交任务到工作线程池
                    future_callback = lambda f, task_id=task.task_id: self._task_completed(task_id, f)
                    success = self.worker.submit_task(task)
                    
                    if not success:
                        # 如果提交失败，放回队列
                        self.task_queue.put(task)
                        
                except Empty:
                    # 队列为空，等待
                    pass
                    
                # 短暂休眠以避免CPU占用过高
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"调度循环异常: {str(e)}")
                time.sleep(1)  # 出错后稍微休眠一段时间
    
    def _check_periodic_tasks(self):
        """检查周期任务并提交到执行队列"""
        now = datetime.now()
        
        with self._lock:
            for task_id, task in list(self.periodic_tasks.items()):
                # 检查任务是否应该执行
                if task.next_run <= now:
                    # 创建任务的副本用于执行
                    execution_task = Task(
                        func=task.func,
                        args=task.args,
                        kwargs=task.kwargs,
                        task_id=f"{task_id}_{int(now.timestamp())}",
                        priority=task.priority,
                        retry_count=task.retry_count,
                        retry_interval=task.retry_interval,
                        timeout=task.timeout,
                        description=f"{task.description} (周期执行)"
                    )
                    
                    # 提交任务
                    self.task_queue.put(execution_task)
                    
                    # 更新下次执行时间
                    task.update_next_run()
                    
    def _task_completed(self, task_id: str, future):
        """
        处理任务完成事件
        
        Args:
            task_id: 任务ID
            future: 任务执行的Future对象
        """
        try:
            result = future.result()
            
            with self._lock:
                # 保存结果
                self._task_results[task_id] = result
                
                # 如果有回调函数，执行回调
                if task_id in self._task_callbacks:
                    try:
                        self._task_callbacks[task_id](task_id, result)
                    except Exception as e:
                        logger.error(f"执行任务回调失败: {task_id}, 错误: {str(e)}")
                
                # 更新任务状态
                if task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.COMPLETED
                    self.tasks[task_id].result = result
                    
        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.FAILED
                    self.tasks[task_id].error = str(e)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消待执行的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        with self._lock:
            # 如果是周期任务，从周期任务列表移除
            if task_id in self.periodic_tasks:
                del self.periodic_tasks[task_id]
                logger.info(f"已取消周期任务: {task_id}")
                return True
                
            # 如果任务已经在执行，尝试取消
            cancelled = self.worker.cancel_task(task_id)
            
            # 从任务记录中移除
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.CANCELED
                
            return cancelled
            
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            dict: 任务状态信息，如果任务不存在则返回None
        """
        with self._lock:
            if task_id in self.tasks:
                return self.tasks[task_id].to_dict()
            elif task_id in self.periodic_tasks:
                return self.periodic_tasks[task_id].to_dict()
            else:
                return None
                
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """
        获取任务执行结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Any: 任务执行结果，如果任务不存在或未完成则返回None
        """
        with self._lock:
            return self._task_results.get(task_id)
            
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务的状态
        
        Returns:
            List[Dict]: 所有任务的状态信息列表
        """
        with self._lock:
            all_tasks = []
            
            # 添加普通任务
            for task_id, task in self.tasks.items():
                all_tasks.append(task.to_dict())
                
            # 添加周期任务
            for task_id, task in self.periodic_tasks.items():
                all_tasks.append(task.to_dict())
                
            return all_tasks
            
    def clear_completed_tasks(self) -> int:
        """
        清理已完成的任务
        
        Returns:
            int: 清理的任务数量
        """
        count = 0
        with self._lock:
            for task_id in list(self.tasks.keys()):
                task = self.tasks[task_id]
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED]:
                    del self.tasks[task_id]
                    if task_id in self._task_results:
                        del self._task_results[task_id]
                    count += 1
                    
        return count