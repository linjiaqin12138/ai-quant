#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Any

from lib.logger import logger
from .task import Task

class Worker:
    """工作线程管理器，负责执行任务"""

    def __init__(self, max_workers: int = 5, use_process: bool = False):
        """
        初始化工作线程/进程池
        
        Args:
            max_workers: 最大并发工作线程/进程数
            use_process: 是否使用进程池（True）或线程池（False）
        """
        self.max_workers = max_workers
        self.use_process = use_process
        self._executor = None
        self._running = False
        self._tasks = {}  # task_id -> future
        self.init_executor()
        
    def init_executor(self):
        """初始化执行器"""
        if self.use_process:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        logger.info(f"已初始化{'进程' if self.use_process else '线程'}池，最大并发数: {self.max_workers}")
    
    def submit_task(self, task: Task) -> bool:
        """
        提交任务到工作池执行
        
        Args:
            task: 要执行的任务
            
        Returns:
            bool: 是否成功提交
        """
        if not self._executor:
            logger.error("执行器未初始化")
            return False
            
        if task.task_id in self._tasks:
            logger.warning(f"任务 {task.task_id} 已在执行队列中")
            return False
            
        # 提交任务执行
        future = self._executor.submit(self._execute_task, task)
        
        # 添加回调处理完成事件
        future.add_done_callback(lambda f: self._handle_task_done(task.task_id, f))
        
        # 记录任务
        self._tasks[task.task_id] = future
        logger.info(f"已提交任务: {task.task_id} - {task.description}")
        return True
    
    def _execute_task(self, task: Task) -> Any:
        """
        执行任务的包装函数，处理重试逻辑
        
        Args:
            task: 要执行的任务
            
        Returns:
            Any: 任务执行结果
        """
        retry = 0
        while True:
            try:
                logger.info(f"开始执行任务: {task.task_id} - {task.description}")
                result = task.execute()
                logger.info(f"任务 {task.task_id} 执行成功")
                return result
                
            except Exception as e:
                task.retry_attempts += 1
                logger.error(f"任务 {task.task_id} 执行失败: {str(e)} {traceback.format_exc()}")

                if retry < task.retry_count:
                    retry += 1
                    logger.info(f"将在 {task.retry_interval}秒 后重试任务 {task.task_id}，第 {retry}/{task.retry_count} 次重试")
                    time.sleep(task.retry_interval)
                else:
                    logger.error(f"任务 {task.task_id} 达到最大重试次数，放弃执行")
                    raise
    
    def _handle_task_done(self, task_id: str, future):
        """
        处理任务完成事件
        
        Args:
            task_id: 任务ID
            future: 任务执行的Future对象
        """
        # 移除任务记录
        if task_id in self._tasks:
            del self._tasks[task_id]
            
    def cancel_task(self, task_id: str) -> bool:
        """
        取消正在执行的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        if task_id not in self._tasks:
            logger.warning(f"任务 {task_id} 不在执行队列中")
            return False
            
        future = self._tasks[task_id]
        cancelled = future.cancel()
        if cancelled:
            logger.info(f"已取消任务: {task_id}")
            del self._tasks[task_id]
        else:
            logger.warning(f"任务 {task_id} 无法取消，可能已在执行")
        return cancelled
        
    def get_active_task_count(self) -> int:
        """
        获取当前活动任务数量
        
        Returns:
            int: 活动任务数量
        """
        return len(self._tasks)
        
    def shutdown(self, wait: bool = True):
        """
        关闭工作线程/进程池
        
        Args:
            wait: 是否等待所有任务完成
        """
        if self._executor:
            logger.info("正在关闭工作线程池...")
            self._executor.shutdown(wait=wait)
            self._executor = None
            self._tasks = {}
            logger.info("工作线程池已关闭")