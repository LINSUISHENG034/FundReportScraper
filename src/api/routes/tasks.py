"""
任务管理相关API路由
Task management related API routes
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid

from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.api.schemas import (
    TaskResponse, TaskListResponse, TaskInfo, TaskCreateRequest,
    TaskStatusEnum, BaseResponse
)

# 导入真实的爬虫任务
logger = get_logger(__name__)

# 常量定义
DEFAULT_PROGRESS = 50

try:
    from src.tasks.scraping_tasks import scrape_fund_reports, scrape_single_fund_report
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery tasks not available, using fallback mode")

router = APIRouter()

# 模拟任务存储（生产环境应该使用数据库或Redis）
# In production, this should be stored in database or Redis
tasks_storage: Dict[str, Dict[str, Any]] = {}


def create_task_info(task_id: str, task_data: Dict[str, Any]) -> TaskInfo:
    """创建TaskInfo对象"""
    return TaskInfo(
        task_id=task_id,
        task_name=task_data.get("task_name", ""),
        status=TaskStatusEnum(task_data.get("status", "pending")),
        progress=task_data.get("progress", 0),
        result=task_data.get("result"),
        error_message=task_data.get("error_message"),
        created_at=task_data.get("created_at", datetime.utcnow()),
        started_at=task_data.get("started_at"),
        completed_at=task_data.get("completed_at")
    )


@router.get("/", response_model=TaskListResponse, summary="获取任务列表")
async def get_tasks(
    status: Optional[TaskStatusEnum] = Query(None, description="任务状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db_session)
):
    """
    获取任务列表，支持状态筛选和分页
    Get task list with status filtering and pagination
    """
    logger.info("api.tasks.get_tasks.start", 
               status=status,
               page=page, 
               size=size)
    
    try:
        # 筛选任务
        filtered_tasks = []
        for task_id, task_data in tasks_storage.items():
            if status is None or task_data.get("status") == status.value:
                filtered_tasks.append((task_id, task_data))
        
        # 按创建时间倒序排序
        filtered_tasks.sort(key=lambda x: x[1].get("created_at", datetime.min), reverse=True)
        
        # 分页
        total = len(filtered_tasks)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_tasks = filtered_tasks[start_idx:end_idx]
        
        # 转换为响应模型
        task_list = []
        for task_id, task_data in page_tasks:
            task_info = create_task_info(task_id, task_data)
            task_list.append(task_info)
        
        logger.info("api.tasks.get_tasks.success", 
                   total=total, 
                   returned=len(task_list))
        
        return TaskListResponse(
            data=task_list,
            total=total,
            page=page,
            size=size,
            message=f"成功获取 {len(task_list)} 个任务"
        )
        
    except Exception as e:
        logger.error("api.tasks.get_tasks.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取任务列表失败: {str(e)}"
        )


@router.get("/{task_id}", response_model=TaskResponse, summary="获取任务详情")
async def get_task_detail(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    """
    根据任务ID获取任务详细信息
    Get task detail by task ID
    """
    logger.info("api.tasks.get_task_detail.start", task_id=task_id)
    
    try:
        if task_id not in tasks_storage:
            logger.warning("api.tasks.get_task_detail.not_found", task_id=task_id)
            raise HTTPException(
                status_code=404,
                detail=f"未找到ID为 {task_id} 的任务"
            )
        
        task_data = tasks_storage[task_id]
        
        # 如果有Celery任务ID，检查真实任务状态
        if CELERY_AVAILABLE and "celery_task_id" in task_data:
            try:
                from celery.result import AsyncResult
                celery_task_id = task_data["celery_task_id"]
                celery_result = AsyncResult(celery_task_id)
                
                # 更新任务状态基于Celery任务状态
                if celery_result.state == "PENDING":
                    task_data["status"] = "pending"
                    task_data["progress"] = 0
                elif celery_result.state == "PROGRESS":
                    task_data["status"] = "running"
                    # 尝试获取进度信息
                    if hasattr(celery_result.info, 'get') and 'progress' in celery_result.info:
                        task_data["progress"] = celery_result.info['progress']
                    else:
                        task_data["progress"] = DEFAULT_PROGRESS  # 默认进度
                elif celery_result.state == "SUCCESS":
                    task_data["status"] = "success"
                    task_data["progress"] = 100
                    task_data["completed_at"] = datetime.utcnow()
                    task_data["result"] = celery_result.result
                elif celery_result.state == "FAILURE":
                    task_data["status"] = "failed"
                    task_data["completed_at"] = datetime.utcnow()
                    task_data["error_message"] = str(celery_result.info)
                
                logger.debug("api.tasks.get_task_detail.celery_status_checked",
                           task_id=task_id,
                           celery_task_id=celery_task_id,
                           celery_state=celery_result.state,
                           updated_status=task_data["status"])
                           
            except Exception as e:
                logger.warning("api.tasks.get_task_detail.celery_check_failed",
                             task_id=task_id,
                             error=str(e))
        
        task_info = create_task_info(task_id, task_data)
        
        logger.info("api.tasks.get_task_detail.success", 
                   task_id=task_id,
                   status=task_info.status)
        
        return TaskResponse(
            data=task_info,
            message=f"成功获取任务 {task_id} 的详细信息"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.tasks.get_task_detail.error", 
                    task_id=task_id, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取任务详情失败: {str(e)}"
        )


@router.post("/", response_model=TaskResponse, summary="创建新任务")
async def create_task(
    task_request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    创建新的数据采集任务
    Create new data collection task
    """
    logger.info("api.tasks.create_task.start", 
               task_type=task_request.task_type,
               parameters=task_request.parameters)
    
    try:
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 根据任务类型确定任务名称
        task_name_mapping = {
            "fund_scraping": "基金数据爬取",
            "report_parsing": "报告解析",
            "data_analysis": "数据分析",
            "batch_update": "批量更新",
            "historical_backfill": "历史数据回补"
        }
        
        task_name = task_name_mapping.get(
            task_request.task_type, 
            f"任务-{task_request.task_type}"
        )
        
        # 创建任务记录
        task_data = {
            "task_name": task_name,
            "task_type": task_request.task_type,
            "status": "pending",
            "progress": 0,
            "parameters": task_request.parameters,
            "description": task_request.description,
            "result": None,
            "error_message": None,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None
        }
        
        tasks_storage[task_id] = task_data
        
        # 启动真实的数据采集任务
        if CELERY_AVAILABLE and task_request.task_type == "fund_scraping":
            # 提取基金代码参数
            fund_codes = task_request.parameters.get("fund_codes", [])
            start_date = task_request.parameters.get("start_date")
            end_date = task_request.parameters.get("end_date")
            
            # 根据基金代码数量决定使用批量还是单个任务
            if len(fund_codes) == 1:
                # 单个基金代码，使用单个任务
                celery_task = scrape_single_fund_report.delay(
                    fund_code=fund_codes[0],
                    report_types=['annual', 'semi_annual', 'quarterly'],
                    start_date=start_date,
                    end_date=end_date,
                    force_update=False
                )
            else:
                # 多个基金代码，使用批量任务
                celery_task = scrape_fund_reports.delay(
                    fund_codes=fund_codes,
                    report_types=['annual', 'semi_annual', 'quarterly'],
                    start_date=start_date,
                    end_date=end_date,
                    force_update=False
                )
            
            # 更新任务数据，存储Celery任务ID
            task_data["celery_task_id"] = celery_task.id
            task_data["status"] = "running"
            task_data["started_at"] = datetime.utcnow()
            
            logger.info("api.tasks.create_task.celery_task_started", 
                       task_id=task_id, 
                       celery_task_id=celery_task.id,
                       fund_codes=fund_codes)
        else:
            # 如果Celery不可用或其他任务类型，使用后台任务
            if not CELERY_AVAILABLE and task_request.task_type == "fund_scraping":
                logger.warning("api.tasks.create_task.celery_unavailable", 
                             task_id=task_id,
                             task_type=task_request.task_type)
            background_tasks.add_task(execute_background_task, task_id, task_request.task_type, task_request.parameters)
        
        task_info = create_task_info(task_id, task_data)
        
        logger.info("api.tasks.create_task.success", 
                   task_id=task_id,
                   task_type=task_request.task_type)
        
        return TaskResponse(
            data=task_info,
            message=f"成功创建任务 {task_id}"
        )
        
    except Exception as e:
        logger.error("api.tasks.create_task.error", 
                    task_type=task_request.task_type,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"创建任务失败: {str(e)}"
        )


@router.post("/{task_id}/cancel", response_model=BaseResponse, summary="取消任务")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    """
    取消指定的任务
    Cancel specified task
    """
    logger.info("api.tasks.cancel_task.start", task_id=task_id)
    
    try:
        if task_id not in tasks_storage:
            raise HTTPException(
                status_code=404,
                detail=f"未找到ID为 {task_id} 的任务"
            )
        
        task_data = tasks_storage[task_id]
        current_status = task_data.get("status")
        
        # 检查任务是否可以取消
        if current_status in ["success", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"任务已完成，无法取消"
            )
        
        # 更新任务状态
        task_data["status"] = "failed"
        task_data["error_message"] = "任务被用户取消"
        task_data["completed_at"] = datetime.utcnow()
        
        logger.info("api.tasks.cancel_task.success", task_id=task_id)
        
        return BaseResponse(
            success=True,
            message=f"成功取消任务 {task_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.tasks.cancel_task.error", 
                    task_id=task_id, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"取消任务失败: {str(e)}"
        )


@router.delete("/{task_id}", response_model=BaseResponse, summary="删除任务")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    """
    删除指定的任务记录
    Delete specified task record
    """
    logger.info("api.tasks.delete_task.start", task_id=task_id)
    
    try:
        if task_id not in tasks_storage:
            raise HTTPException(
                status_code=404,
                detail=f"未找到ID为 {task_id} 的任务"
            )
        
        # 删除任务
        del tasks_storage[task_id]
        
        logger.info("api.tasks.delete_task.success", task_id=task_id)
        
        return BaseResponse(
            success=True,
            message=f"成功删除任务 {task_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.tasks.delete_task.error", 
                    task_id=task_id, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"删除任务失败: {str(e)}"
        )


@router.get("/stats/summary", response_model=BaseResponse, summary="获取任务统计信息")
async def get_tasks_stats():
    """
    获取任务的统计信息
    Get tasks statistics
    """
    logger.info("api.tasks.get_tasks_stats.start")
    
    try:
        total_tasks = len(tasks_storage)
        
        # 按状态统计
        status_stats = {}
        for status in TaskStatusEnum:
            count = sum(1 for task in tasks_storage.values() 
                       if task.get("status") == status.value)
            status_stats[status.value] = count
        
        # 按任务类型统计
        type_stats = {}
        for task in tasks_storage.values():
            task_type = task.get("task_type", "unknown")
            type_stats[task_type] = type_stats.get(task_type, 0) + 1
        
        stats = {
            "total_tasks": total_tasks,
            "by_status": status_stats,
            "by_type": type_stats
        }
        
        logger.info("api.tasks.get_tasks_stats.success", 
                   total_tasks=total_tasks)
        
        return BaseResponse(
            success=True,
            message="成功获取任务统计信息",
            data=stats
        )
        
    except Exception as e:
        logger.error("api.tasks.get_tasks_stats.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )


async def execute_background_task(task_id: str, task_type: str, parameters: Dict[str, Any]):
    """
    执行后台任务
    Execute background task
    """
    logger.info("background_task.start", task_id=task_id, task_type=task_type)
    
    try:
        if task_id not in tasks_storage:
            return
        
        # 更新任务状态为运行中
        tasks_storage[task_id].update({
            "status": "running",
            "started_at": datetime.utcnow(),
            "progress": 10
        })
        
        # 模拟任务执行
        import asyncio
        
        # 模拟进度更新
        for progress in [25, 50, 75, 90]:
            await asyncio.sleep(2)  # 模拟工作时间
            if task_id in tasks_storage:
                tasks_storage[task_id]["progress"] = progress
        
        # 模拟任务完成
        await asyncio.sleep(1)
        
        if task_id in tasks_storage:
            tasks_storage[task_id].update({
                "status": "success",
                "progress": 100,
                "completed_at": datetime.utcnow(),
                "result": {
                    "message": f"任务 {task_type} 执行成功",
                    "processed_items": parameters.get("count", 1),
                    "execution_time": "模拟执行时间"
                }
            })
        
        logger.info("background_task.success", task_id=task_id)
        
    except Exception as e:
        logger.error("background_task.error", task_id=task_id, error=str(e))
        
        if task_id in tasks_storage:
            tasks_storage[task_id].update({
                "status": "failed",
                "completed_at": datetime.utcnow(),
                "error_message": str(e)
            })