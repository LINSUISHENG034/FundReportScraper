"""
Monitoring tasks for Celery.
系统监控和维护任务的Celery异步实现。
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

from celery import Task
from celery.exceptions import Retry

from src.core.celery_app import app
from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.models.database import FundReport, TaskStatus
from src.services.data_persistence import FundDataPersistenceService

logger = get_logger(__name__)


class MonitoringTask(Task):
    """自定义监控任务基类"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调"""
        logger.error(
            "monitoring.task.failed",
            task_id=task_id,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调"""
        logger.info(
            "monitoring.task.success",
            task_id=task_id,
            result_type=type(retval).__name__
        )


@app.task(bind=True, base=MonitoringTask)
def check_task_health(self) -> Dict[str, Any]:
    """
    检查任务队列健康状况
    
    Returns:
        健康状况报告
    """
    bound_logger = logger.bind(task_id=self.request.id)
    bound_logger.info("monitoring.health_check.start")
    
    try:
        # 获取Celery应用实例
        celery_app = app
        
        # 检查Redis连接
        redis_status = "unknown"
        try:
            # 通过Celery检查Redis连接
            celery_app.control.ping(timeout=5)
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"error: {str(e)}"
        
        # 检查数据库连接
        db_status = "unknown"
        try:
            with FundDataPersistenceService() as persistence:
                summary = persistence.get_fund_reports_summary()
                db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # 检查活跃worker数量
        active_workers = 0
        try:
            inspect = celery_app.control.inspect()
            active_workers_info = inspect.active()
            if active_workers_info:
                active_workers = len(active_workers_info)
        except Exception as e:
            bound_logger.warning(
                "monitoring.health_check.worker_check_failed",
                error=str(e)
            )
        
        # 检查待处理任务数量
        pending_tasks = 0
        try:
            inspect = celery_app.control.inspect()
            reserved_tasks = inspect.reserved()
            if reserved_tasks:
                pending_tasks = sum(len(tasks) for tasks in reserved_tasks.values())
        except Exception as e:
            bound_logger.warning(
                "monitoring.health_check.pending_tasks_failed",
                error=str(e)
            )
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy" if redis_status == "healthy" and db_status == "healthy" else "degraded",
            "components": {
                "redis": redis_status,
                "database": db_status,
                "active_workers": active_workers,
                "pending_tasks": pending_tasks
            },
            "celery_info": {
                "broker_url": celery_app.conf.broker_url,
                "result_backend": celery_app.conf.result_backend,
                "worker_concurrency": celery_app.conf.worker_concurrency
            }
        }
        
        bound_logger.info(
            "monitoring.health_check.completed",
            overall_status=health_report["overall_status"],
            active_workers=active_workers,
            pending_tasks=pending_tasks
        )
        
        return health_report
        
    except Exception as exc:
        bound_logger.error(
            "monitoring.health_check.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc


@app.task(bind=True, base=MonitoringTask)
def cleanup_expired_tasks(
    self,
    days_to_keep: int = 7
) -> Dict[str, Any]:
    """
    清理过期的任务结果和失败记录
    
    Args:
        days_to_keep: 保留多少天的记录
        
    Returns:
        清理结果统计
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        days_to_keep=days_to_keep
    )
    
    bound_logger.info("monitoring.cleanup.start")
    
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # 清理数据库中的失败报告
        cleaned_reports = 0
        try:
            with FundDataPersistenceService() as persistence:
                cleaned_reports = persistence.cleanup_failed_reports()
        except Exception as e:
            bound_logger.error(
                "monitoring.cleanup.database_failed",
                error=str(e)
            )
        
        # 清理Celery结果后端
        cleaned_results = 0
        try:
            # 使用Celery的结果后端清理功能
            celery_app = app
            
            # 注意：这里简化处理，实际可以实现更复杂的清理逻辑
            # celery_app.backend.cleanup()
            cleaned_results = 0  # 占位符
            
        except Exception as e:
            bound_logger.error(
                "monitoring.cleanup.celery_backend_failed",
                error=str(e)
            )
        
        cleanup_result = {
            "timestamp": datetime.now().isoformat(),
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_items": {
                "database_reports": cleaned_reports,
                "celery_results": cleaned_results
            },
            "total_cleaned": cleaned_reports + cleaned_results
        }
        
        bound_logger.info(
            "monitoring.cleanup.completed",
            total_cleaned=cleanup_result["total_cleaned"],
            database_reports=cleaned_reports,
            celery_results=cleaned_results
        )
        
        return cleanup_result
        
    except Exception as exc:
        bound_logger.error(
            "monitoring.cleanup.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc


@app.task(bind=True, base=MonitoringTask)
def generate_daily_report(self) -> Dict[str, Any]:
    """
    生成每日运行报告
    
    Returns:
        每日报告数据
    """
    bound_logger = logger.bind(task_id=self.request.id)
    bound_logger.info("monitoring.daily_report.start")
    
    try:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # 获取数据库统计信息
        db_stats = {}
        try:
            with FundDataPersistenceService() as persistence:
                db_stats = persistence.get_fund_reports_summary()
        except Exception as e:
            bound_logger.error(
                "monitoring.daily_report.db_stats_failed",
                error=str(e)
            )
            db_stats = {"error": str(e)}
        
        # 获取任务执行统计
        task_stats = {
            "total_tasks_today": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "pending_tasks": 0
        }
        
        try:
            # 这里可以从Celery监控或日志中获取任务统计
            # 简化处理，实际可以集成flower或其他监控工具的API
            inspect = app.control.inspect()
            
            # 获取活跃任务
            active_tasks = inspect.active()
            if active_tasks:
                for worker_tasks in active_tasks.values():
                    task_stats["total_tasks_today"] += len(worker_tasks)
            
            # 获取预约任务
            reserved_tasks = inspect.reserved()
            if reserved_tasks:
                for worker_tasks in reserved_tasks.values():
                    task_stats["pending_tasks"] += len(worker_tasks)
                    
        except Exception as e:
            bound_logger.warning(
                "monitoring.daily_report.task_stats_failed",
                error=str(e)
            )
        
        # 生成系统健康状况
        health_status = "unknown"
        try:
            health_check_result = check_task_health.delay()
            # 注意：在实际生产中，这里不应该使用.get()，而应该异步处理
            # health_info = health_check_result.get(timeout=30)
            # health_status = health_info.get("overall_status", "unknown")
            health_status = "monitoring"  # 占位符
        except Exception as e:
            health_status = f"error: {str(e)}"
        
        daily_report = {
            "report_date": today.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "system_health": health_status,
            "database_stats": db_stats,
            "task_stats": task_stats,
            "summary": {
                "total_funds": db_stats.get("total_reports", 0),
                "parsed_reports": db_stats.get("parsed_reports", 0),
                "data_quality": f"{(db_stats.get('parsed_reports', 0) / max(db_stats.get('total_reports', 1), 1) * 100):.1f}%"
            }
        }
        
        bound_logger.info(
            "monitoring.daily_report.completed",
            report_date=today.isoformat(),
            total_funds=daily_report["summary"]["total_funds"],
            data_quality=daily_report["summary"]["data_quality"]
        )
        
        return daily_report
        
    except Exception as exc:
        bound_logger.error(
            "monitoring.daily_report.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc


@app.task(bind=True, base=MonitoringTask)
def monitor_scraping_progress(
    self,
    batch_task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    监控爬取任务进度
    
    Args:
        batch_task_id: 批量任务ID，为None时监控所有活跃任务
        
    Returns:
        爬取进度报告
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        batch_task_id=batch_task_id
    )
    
    bound_logger.info("monitoring.scraping_progress.start")
    
    try:
        # 获取任务进度信息
        progress_info = {
            "timestamp": datetime.now().isoformat(),
            "batch_task_id": batch_task_id,
            "active_scraping_tasks": 0,
            "active_parsing_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "queue_status": {}
        }
        
        try:
            inspect = app.control.inspect()
            
            # 检查活跃任务
            active_tasks = inspect.active()
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        task_name = task.get('name', '')
                        if 'scraping' in task_name:
                            progress_info["active_scraping_tasks"] += 1
                        elif 'parsing' in task_name:
                            progress_info["active_parsing_tasks"] += 1
            
            # 检查队列状态
            reserved_tasks = inspect.reserved()
            if reserved_tasks:
                for worker, tasks in reserved_tasks.items():
                    queue_name = worker.split('@')[0] if '@' in worker else worker
                    progress_info["queue_status"][queue_name] = len(tasks)
            
        except Exception as e:
            bound_logger.warning(
                "monitoring.scraping_progress.inspection_failed",
                error=str(e)
            )
        
        # 如果指定了批量任务ID，获取具体任务的进度
        if batch_task_id:
            try:
                # 这里可以查询数据库获取相关任务的完成情况
                # 简化处理
                progress_info["batch_progress"] = {
                    "total_expected": "unknown",
                    "completed": "unknown",
                    "success_rate": "unknown"
                }
            except Exception as e:
                bound_logger.warning(
                    "monitoring.scraping_progress.batch_progress_failed",
                    error=str(e)
                )
        
        bound_logger.info(
            "monitoring.scraping_progress.completed",
            active_scraping=progress_info["active_scraping_tasks"],
            active_parsing=progress_info["active_parsing_tasks"],
            queues=list(progress_info["queue_status"].keys())
        )
        
        return progress_info
        
    except Exception as exc:
        bound_logger.error(
            "monitoring.scraping_progress.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc


@app.task(bind=True, base=MonitoringTask)
def alert_on_failures(
    self,
    failure_threshold: int = 5,
    time_window_minutes: int = 30
) -> Dict[str, Any]:
    """
    检查失败率并发送告警
    
    Args:
        failure_threshold: 失败次数阈值
        time_window_minutes: 时间窗口（分钟）
        
    Returns:
        告警检查结果
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        failure_threshold=failure_threshold,
        time_window_minutes=time_window_minutes
    )
    
    bound_logger.info("monitoring.alert_check.start")
    
    try:
        time_window_start = datetime.now() - timedelta(minutes=time_window_minutes)
        
        alert_info = {
            "timestamp": datetime.now().isoformat(),
            "time_window_start": time_window_start.isoformat(),
            "failure_threshold": failure_threshold,
            "alerts_triggered": [],
            "system_status": "normal"
        }
        
        # 检查数据库中的失败记录
        try:
            with FundDataPersistenceService() as persistence:
                # 这里可以查询最近的失败记录
                # 简化处理，实际可以添加时间范围查询
                summary = persistence.get_fund_reports_summary()
                
                unparsed_reports = summary.get("unparsed_reports", 0)
                total_reports = summary.get("total_reports", 1)
                
                failure_rate = unparsed_reports / max(total_reports, 1)
                
                if failure_rate > 0.1:  # 10%失败率阈值
                    alert_info["alerts_triggered"].append({
                        "type": "high_failure_rate",
                        "message": f"解析失败率过高: {failure_rate:.1%}",
                        "severity": "warning",
                        "details": {
                            "unparsed_reports": unparsed_reports,
                            "total_reports": total_reports
                        }
                    })
                    alert_info["system_status"] = "warning"
                
        except Exception as e:
            alert_info["alerts_triggered"].append({
                "type": "database_error",
                "message": f"数据库检查失败: {str(e)}",
                "severity": "error"
            })
            alert_info["system_status"] = "error"
        
        # 检查Celery队列积压
        try:
            inspect = app.control.inspect()
            reserved_tasks = inspect.reserved()
            
            if reserved_tasks:
                total_queued = sum(len(tasks) for tasks in reserved_tasks.values())
                
                if total_queued > 100:  # 队列积压阈值
                    alert_info["alerts_triggered"].append({
                        "type": "queue_backlog",
                        "message": f"任务队列积压严重: {total_queued}个待处理任务",
                        "severity": "warning",
                        "details": {"queued_tasks": total_queued}
                    })
                    if alert_info["system_status"] == "normal":
                        alert_info["system_status"] = "warning"
        
        except Exception as e:
            alert_info["alerts_triggered"].append({
                "type": "celery_error", 
                "message": f"Celery检查失败: {str(e)}",
                "severity": "error"
            })
            alert_info["system_status"] = "error"
        
        # 记录告警结果
        if alert_info["alerts_triggered"]:
            bound_logger.warning(
                "monitoring.alert_check.alerts_found",
                alerts_count=len(alert_info["alerts_triggered"]),
                system_status=alert_info["system_status"]
            )
        else:
            bound_logger.info(
                "monitoring.alert_check.all_normal",
                system_status=alert_info["system_status"]
            )
        
        return alert_info
        
    except Exception as exc:
        bound_logger.error(
            "monitoring.alert_check.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc