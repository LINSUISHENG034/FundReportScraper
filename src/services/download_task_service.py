"""
下载任务服务层
Download Task Service Layer

管理下载任务的创建、状态更新和查询
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from src.core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"           # 等待中
    IN_PROGRESS = "IN_PROGRESS"   # 进行中
    COMPLETED = "COMPLETED"       # 已完成
    FAILED = "FAILED"             # 失败
    CANCELLED = "CANCELLED"       # 已取消


@dataclass
class DownloadTask:
    """下载任务数据模型"""
    task_id: str
    report_ids: List[str]
    save_dir: str
    max_concurrent: int
    status: TaskStatus
    created_at: datetime
    total_count: int
    
    # 进度相关字段
    completed_count: int = 0
    failed_count: int = 0
    
    # 时间戳字段
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果字段
    completed_ids: Optional[List[str]] = field(default_factory=list)
    failed_results: Optional[List[Dict[str, str]]] = field(default_factory=list)
    
    # 错误信息
    error_message: Optional[str] = None


class DownloadTaskService:
    """
    下载任务服务
    Download Task Service
    
    管理下载任务的生命周期，包括创建、状态更新、进度跟踪等
    """
    
    def __init__(self):
        # 使用内存存储任务（生产环境应该使用数据库）
        self._tasks: Dict[str, DownloadTask] = {}
        
    async def create_task(self, task: DownloadTask) -> DownloadTask:
        """
        创建新的下载任务
        Create a new download task
        """
        bound_logger = logger.bind(
            task_id=task.task_id,
            report_count=len(task.report_ids),
            save_dir=task.save_dir
        )
        
        bound_logger.info("download_task_service.create_task.start")
        
        try:
            # 验证任务ID唯一性
            if task.task_id in self._tasks:
                raise ValueError(f"任务ID已存在: {task.task_id}")
            
            # 保存任务
            self._tasks[task.task_id] = task
            
            bound_logger.info(
                "download_task_service.create_task.success",
                total_tasks=len(self._tasks)
            )
            
            return task
            
        except Exception as e:
            bound_logger.error(
                "download_task_service.create_task.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """
        获取指定的下载任务
        Get a specific download task
        """
        bound_logger = logger.bind(task_id=task_id)
        bound_logger.info("download_task_service.get_task.start")
        
        try:
            task = self._tasks.get(task_id)
            
            if task:
                bound_logger.info(
                    "download_task_service.get_task.found",
                    status=task.status.value,
                    progress=f"{task.completed_count}/{task.total_count}"
                )
            else:
                bound_logger.warning("download_task_service.get_task.not_found")
            
            return task
            
        except Exception as e:
            bound_logger.error(
                "download_task_service.get_task.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        Update task status
        """
        bound_logger = logger.bind(
            task_id=task_id,
            new_status=status.value
        )
        
        bound_logger.info("download_task_service.update_status.start")
        
        try:
            task = self._tasks.get(task_id)
            if not task:
                bound_logger.warning("download_task_service.update_status.task_not_found")
                return False
            
            old_status = task.status
            task.status = status
            
            if started_at:
                task.started_at = started_at
            if completed_at:
                task.completed_at = completed_at
            if error_message:
                task.error_message = error_message
            
            bound_logger.info(
                "download_task_service.update_status.success",
                old_status=old_status.value,
                new_status=status.value
            )
            
            return True
            
        except Exception as e:
            bound_logger.error(
                "download_task_service.update_status.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def update_task_progress(
        self,
        task_id: str,
        completed_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        completed_ids: Optional[List[str]] = None,
        failed_results: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """
        更新任务进度
        Update task progress
        """
        bound_logger = logger.bind(
            task_id=task_id,
            completed_count=completed_count,
            failed_count=failed_count
        )
        
        bound_logger.info("download_task_service.update_progress.start")
        
        try:
            task = self._tasks.get(task_id)
            if not task:
                bound_logger.warning("download_task_service.update_progress.task_not_found")
                return False
            
            if completed_count is not None:
                task.completed_count = completed_count
            if failed_count is not None:
                task.failed_count = failed_count
            if completed_ids is not None:
                task.completed_ids = completed_ids
            if failed_results is not None:
                task.failed_results = failed_results
            
            progress_percentage = round((task.completed_count / task.total_count) * 100, 2) if task.total_count > 0 else 0.0
            
            bound_logger.info(
                "download_task_service.update_progress.success",
                completed=task.completed_count,
                failed=task.failed_count,
                total=task.total_count,
                percentage=progress_percentage
            )
            
            return True
            
        except Exception as e:
            bound_logger.error(
                "download_task_service.update_progress.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def list_tasks(
        self, 
        status: Optional[TaskStatus] = None, 
        limit: int = 20
    ) -> List[DownloadTask]:
        """
        获取任务列表
        Get list of tasks
        """
        bound_logger = logger.bind(
            status_filter=status.value if status else None,
            limit=limit
        )
        
        bound_logger.info("download_task_service.list_tasks.start")
        
        try:
            tasks = list(self._tasks.values())
            
            # 按状态筛选
            if status:
                tasks = [task for task in tasks if task.status == status]
            
            # 按创建时间倒序排序
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # 限制数量
            tasks = tasks[:limit]
            
            bound_logger.info(
                "download_task_service.list_tasks.success",
                total_tasks=len(self._tasks),
                filtered_tasks=len(tasks)
            )
            
            return tasks
            
        except Exception as e:
            bound_logger.error(
                "download_task_service.list_tasks.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        Delete a task
        """
        bound_logger = logger.bind(task_id=task_id)
        bound_logger.info("download_task_service.delete_task.start")
        
        try:
            if task_id in self._tasks:
                del self._tasks[task_id]
                bound_logger.info("download_task_service.delete_task.success")
                return True
            else:
                bound_logger.warning("download_task_service.delete_task.not_found")
                return False
                
        except Exception as e:
            bound_logger.error(
                "download_task_service.delete_task.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """
        获取任务统计信息
        Get task statistics
        """
        try:
            total_tasks = len(self._tasks)
            status_counts = {}
            
            for status in TaskStatus:
                count = sum(1 for task in self._tasks.values() if task.status == status)
                status_counts[status.value] = count
            
            return {
                "total_tasks": total_tasks,
                "status_counts": status_counts,
                "active_tasks": status_counts.get(TaskStatus.PENDING.value, 0) + status_counts.get(TaskStatus.IN_PROGRESS.value, 0)
            }
            
        except Exception as e:
            logger.error(
                "download_task_service.get_statistics.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "total_tasks": 0,
                "status_counts": {},
                "active_tasks": 0
            }
