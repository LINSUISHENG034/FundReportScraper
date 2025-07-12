"""
任务调度管理器
统一管理和协调所有异步任务的调度。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from uuid import uuid4

from src.core.celery_app import app
from src.core.logging import get_logger
from src.tasks.scraping_tasks import scrape_fund_reports, scrape_single_fund_report
from src.tasks.parsing_tasks import parse_xbrl_file, batch_parse_xbrl_files
from src.tasks.monitoring_tasks import check_task_health, monitor_scraping_progress

logger = get_logger(__name__)


class TaskScheduler:
    """
    任务调度管理器
    
    负责协调爬取、解析、监控等各类任务的执行，
    确保任务按照正确的依赖关系和优先级执行。
    """
    
    def __init__(self):
        """初始化任务调度器"""
        self.celery_app = app
        self.active_batches = {}  # 追踪活跃的批量任务
        
        logger.info("task_scheduler.initialized")
    
    def schedule_fund_collection(
        self,
        fund_codes: Optional[List[str]] = None,
        report_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        调度基金数据采集任务
        
        Args:
            fund_codes: 基金代码列表
            report_types: 报告类型列表
            start_date: 开始日期
            end_date: 结束日期
            priority: 任务优先级 ('high', 'normal', 'low')
            
        Returns:
            调度结果信息
        """
        batch_id = str(uuid4())
        
        bound_logger = logger.bind(
            batch_id=batch_id,
            fund_codes_count=len(fund_codes) if fund_codes else 0,
            priority=priority
        )
        
        bound_logger.info("task_scheduler.collection.start")
        
        try:
            # 确定任务队列
            queue_name = "scraping"
            if priority == "high":
                queue_name = "scraping_priority"
            
            # 创建批量爬取任务
            scraping_task = scrape_fund_reports.apply_async(
                args=(fund_codes, report_types, start_date, end_date, False),
                queue=queue_name,
                routing_key=queue_name
            )
            
            # 记录批量任务信息
            batch_info = {
                "batch_id": batch_id,
                "scraping_task_id": scraping_task.id,
                "created_at": datetime.now().isoformat(),
                "status": "scheduled",
                "parameters": {
                    "fund_codes": fund_codes,
                    "report_types": report_types,
                    "start_date": start_date,
                    "end_date": end_date,
                    "priority": priority
                },
                "estimated_tasks": len(fund_codes) if fund_codes else "unknown"
            }
            
            self.active_batches[batch_id] = batch_info
            
            # 调度进度监控任务
            monitor_task = monitor_scraping_progress.apply_async(
                args=(batch_id,),
                countdown=300,  # 5分钟后开始监控
                queue="monitoring"
            )
            
            batch_info["monitor_task_id"] = monitor_task.id
            
            bound_logger.info(
                "task_scheduler.collection.scheduled",
                scraping_task_id=scraping_task.id,
                monitor_task_id=monitor_task.id
            )
            
            return batch_info
            
        except Exception as exc:
            bound_logger.error(
                "task_scheduler.collection.error",
                error=str(exc),
                error_type=type(exc).__name__
            )
            raise exc
    
    def schedule_single_fund(
        self,
        fund_code: str,
        report_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        调度单个基金的数据采集
        
        Args:
            fund_code: 基金代码
            report_types: 报告类型列表
            start_date: 开始日期
            end_date: 结束日期
            priority: 任务优先级
            
        Returns:
            调度结果信息
        """
        bound_logger = logger.bind(
            fund_code=fund_code,
            priority=priority
        )
        
        bound_logger.info("task_scheduler.single_fund.start")
        
        try:
            # 确定任务队列
            queue_name = "scraping"
            if priority == "high":
                queue_name = "scraping_priority"
            
            # 创建单基金爬取任务
            scraping_task = scrape_single_fund_report.apply_async(
                args=(fund_code, report_types, start_date, end_date, False),
                queue=queue_name,
                routing_key=queue_name
            )
            
            task_info = {
                "task_id": scraping_task.id,
                "fund_code": fund_code,
                "created_at": datetime.now().isoformat(),
                "status": "scheduled",
                "priority": priority,
                "parameters": {
                    "report_types": report_types,
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
            
            bound_logger.info(
                "task_scheduler.single_fund.scheduled",
                task_id=scraping_task.id
            )
            
            return task_info
            
        except Exception as exc:
            bound_logger.error(
                "task_scheduler.single_fund.error",
                fund_code=fund_code,
                error=str(exc),
                error_type=type(exc).__name__
            )
            raise exc
    
    def schedule_parsing_batch(
        self,
        file_info_list: List[Dict[str, Any]],
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        调度批量解析任务
        
        Args:
            file_info_list: 文件信息列表
            priority: 任务优先级
            
        Returns:
            调度结果信息
        """
        batch_id = str(uuid4())
        
        bound_logger = logger.bind(
            batch_id=batch_id,
            files_count=len(file_info_list),
            priority=priority
        )
        
        bound_logger.info("task_scheduler.parsing_batch.start")
        
        try:
            # 确定任务队列
            queue_name = "parsing"
            if priority == "high":
                queue_name = "parsing_priority"
            
            # 创建批量解析任务
            parsing_task = batch_parse_xbrl_files.apply_async(
                args=(file_info_list,),
                queue=queue_name,
                routing_key=queue_name
            )
            
            batch_info = {
                "batch_id": batch_id,
                "parsing_task_id": parsing_task.id,
                "created_at": datetime.now().isoformat(),
                "status": "scheduled",
                "files_count": len(file_info_list),
                "priority": priority
            }
            
            bound_logger.info(
                "task_scheduler.parsing_batch.scheduled",
                parsing_task_id=parsing_task.id,
                files_count=len(file_info_list)
            )
            
            return batch_info
            
        except Exception as exc:
            bound_logger.error(
                "task_scheduler.parsing_batch.error",
                error=str(exc),
                error_type=type(exc).__name__
            )
            raise exc
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """
        获取批量任务状态
        
        Args:
            batch_id: 批量任务ID
            
        Returns:
            任务状态信息
        """
        if batch_id not in self.active_batches:
            return None
        
        batch_info = self.active_batches[batch_id].copy()
        
        try:
            # 获取主任务状态
            scraping_task_id = batch_info.get("scraping_task_id")
            if scraping_task_id:
                task_result = self.celery_app.AsyncResult(scraping_task_id)
                batch_info["task_status"] = task_result.status
                batch_info["task_result"] = task_result.result if task_result.ready() else None
            
            # 获取监控任务状态
            monitor_task_id = batch_info.get("monitor_task_id")
            if monitor_task_id:
                monitor_result = self.celery_app.AsyncResult(monitor_task_id)
                batch_info["monitor_status"] = monitor_result.status
            
        except Exception as e:
            logger.warning(
                "task_scheduler.batch_status.error",
                batch_id=batch_id,
                error=str(e)
            )
        
        return batch_info
    
    def cancel_batch(self, batch_id: str) -> bool:
        """
        取消批量任务
        
        Args:
            batch_id: 批量任务ID
            
        Returns:
            取消是否成功
        """
        if batch_id not in self.active_batches:
            return False
        
        bound_logger = logger.bind(batch_id=batch_id)
        bound_logger.info("task_scheduler.cancel_batch.start")
        
        try:
            batch_info = self.active_batches[batch_id]
            
            # 取消主任务
            scraping_task_id = batch_info.get("scraping_task_id")
            if scraping_task_id:
                self.celery_app.control.revoke(scraping_task_id, terminate=True)
            
            # 取消监控任务
            monitor_task_id = batch_info.get("monitor_task_id")
            if monitor_task_id:
                self.celery_app.control.revoke(monitor_task_id, terminate=True)
            
            # 从活跃列表中移除
            del self.active_batches[batch_id]
            
            bound_logger.info("task_scheduler.cancel_batch.success")
            return True
            
        except Exception as exc:
            bound_logger.error(
                "task_scheduler.cancel_batch.error",
                error=str(exc)
            )
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取整个系统的任务状态
        
        Returns:
            系统状态信息
        """
        logger.info("task_scheduler.system_status.start")
        
        try:
            status_info = {
                "timestamp": datetime.now().isoformat(),
                "active_batches": len(self.active_batches),
                "batch_list": list(self.active_batches.keys()),
                "celery_info": {},
                "queue_status": {}
            }
            
            # 获取Celery状态
            try:
                inspect = self.celery_app.control.inspect()
                
                # 活跃任务
                active_tasks = inspect.active()
                if active_tasks:
                    status_info["celery_info"]["active_workers"] = len(active_tasks)
                    status_info["celery_info"]["total_active_tasks"] = sum(
                        len(tasks) for tasks in active_tasks.values()
                    )
                
                # 预约任务
                reserved_tasks = inspect.reserved()
                if reserved_tasks:
                    status_info["celery_info"]["total_reserved_tasks"] = sum(
                        len(tasks) for tasks in reserved_tasks.values()
                    )
                    
                    # 按队列统计
                    for worker, tasks in reserved_tasks.items():
                        queue_name = worker.split('@')[0] if '@' in worker else 'default'
                        status_info["queue_status"][queue_name] = len(tasks)
                
            except Exception as e:
                logger.warning(
                    "task_scheduler.system_status.celery_inspect_failed",
                    error=str(e)
                )
                status_info["celery_info"]["error"] = str(e)
            
            logger.info(
                "task_scheduler.system_status.completed",
                active_batches=status_info["active_batches"],
                active_workers=status_info["celery_info"].get("active_workers", 0)
            )
            
            return status_info
            
        except Exception as exc:
            logger.error(
                "task_scheduler.system_status.error",
                error=str(exc),
                error_type=type(exc).__name__
            )
            raise exc
    
    def cleanup_completed_batches(self, max_age_hours: int = 24) -> int:
        """
        清理已完成的批量任务记录
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的批量任务数量
        """
        logger.info("task_scheduler.cleanup.start", max_age_hours=max_age_hours)
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cleaned_count = 0
            
            batch_ids_to_remove = []
            
            for batch_id, batch_info in self.active_batches.items():
                created_at = datetime.fromisoformat(batch_info["created_at"])
                
                if created_at < cutoff_time:
                    # 检查任务是否已完成
                    scraping_task_id = batch_info.get("scraping_task_id")
                    if scraping_task_id:
                        task_result = self.celery_app.AsyncResult(scraping_task_id)
                        if task_result.ready():  # 任务已完成（成功或失败）
                            batch_ids_to_remove.append(batch_id)
            
            # 移除已完成的旧批量任务
            for batch_id in batch_ids_to_remove:
                del self.active_batches[batch_id]
                cleaned_count += 1
            
            logger.info(
                "task_scheduler.cleanup.completed",
                cleaned_count=cleaned_count,
                remaining_batches=len(self.active_batches)
            )
            
            return cleaned_count
            
        except Exception as exc:
            logger.error(
                "task_scheduler.cleanup.error",
                error=str(exc)
            )
            return 0


# 全局任务调度器实例
task_scheduler = TaskScheduler()