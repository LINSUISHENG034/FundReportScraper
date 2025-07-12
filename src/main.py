"""
Main FastAPI application entry point.
FastAPI应用的主入口点，提供REST API接口。
"""

from contextlib import asynccontextmanager
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.logging import configure_logging, get_logger
from src.models import get_db_session, init_database
from src.models.database import ReportType, TaskStatus

# Configure logging
configure_logging(
    log_level=settings.log_level,
    json_logs=not settings.debug
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("application.startup")
    
    # Initialize database
    try:
        init_database()
        logger.info("application.database.initialized")
    except Exception as e:
        logger.error("application.database.initialization_failed", error=str(e))
        raise
    
    yield
    
    logger.info("application.shutdown")


# Create FastAPI application
app = FastAPI(
    title=settings.name,
    version=settings.version,
    description="公募基金报告自动化采集与分析平台",
    lifespan=lifespan,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class ScrapingTaskRequest(BaseModel):
    """Request model for creating scraping tasks."""
    task_name: str
    target_year: int
    report_type: ReportType
    fund_codes: List[str] = None


class ScrapingTaskResponse(BaseModel):
    """Response model for scraping tasks."""
    task_id: str
    task_name: str
    status: TaskStatus
    target_year: int
    report_type: ReportType
    created_at: str


class ReportListResponse(BaseModel):
    """Response model for report lists."""
    reports: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int


# API Routes
@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "name": settings.name,
        "version": settings.version,
        "description": "公募基金报告自动化采集与分析平台",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": logger.bind().info("health.check"),
        "version": settings.version
    }


@app.post("/tasks/scraping", response_model=ScrapingTaskResponse)
async def create_scraping_task(
    request: ScrapingTaskRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Create a new scraping task.
    创建新的爬取任务。
    """
    bound_logger = logger.bind(
        task_name=request.task_name,
        target_year=request.target_year,
        report_type=request.report_type.value
    )
    
    bound_logger.info("api.task.create.start")
    
    try:
        # Import here to avoid circular imports
        from src.models.database import ScrapingTask
        from datetime import datetime
        import uuid
        
        # Create task record
        task = ScrapingTask(
            id=uuid.uuid4(),
            task_name=request.task_name,
            task_type="SCRAPING",
            status=TaskStatus.PENDING,
            target_year=request.target_year,
            target_report_type=request.report_type,
            fund_codes=request.fund_codes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Add background task (placeholder for now)
        # background_tasks.add_task(execute_scraping_task, task.id)
        
        bound_logger.info(
            "api.task.create.success",
            task_id=str(task.id)
        )
        
        return ScrapingTaskResponse(
            task_id=str(task.id),
            task_name=task.task_name,
            status=task.status,
            target_year=task.target_year,
            report_type=task.target_report_type,
            created_at=task.created_at.isoformat()
        )
        
    except Exception as e:
        bound_logger.error(
            "api.task.create.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"Failed to create task: {e}")


@app.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get task status by ID.
    根据ID获取任务状态。
    """
    bound_logger = logger.bind(task_id=task_id)
    bound_logger.info("api.task.get.start")
    
    try:
        from src.models.database import ScrapingTask
        import uuid
        
        task = db.query(ScrapingTask).filter(
            ScrapingTask.id == uuid.UUID(task_id)
        ).first()
        
        if not task:
            bound_logger.warning("api.task.get.not_found")
            raise HTTPException(status_code=404, detail="Task not found")
        
        bound_logger.info("api.task.get.success")
        
        return {
            "task_id": str(task.id),
            "task_name": task.task_name,
            "status": task.status,
            "target_year": task.target_year,
            "report_type": task.target_report_type,
            "total_reports": task.total_reports,
            "processed_reports": task.processed_reports,
            "failed_reports": task.failed_reports,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message
        }
        
    except ValueError:
        bound_logger.warning("api.task.get.invalid_uuid")
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    except Exception as e:
        bound_logger.error(
            "api.task.get.error",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to get task: {e}")


@app.get("/reports")
async def list_reports(
    fund_code: str = None,
    year: int = None,
    report_type: ReportType = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db_session)
):
    """
    List fund reports with filtering and pagination.
    列出基金报告，支持筛选和分页。
    """
    bound_logger = logger.bind(
        fund_code=fund_code,
        year=year,
        report_type=report_type.value if report_type else None,
        page=page,
        page_size=page_size
    )
    
    bound_logger.info("api.reports.list.start")
    
    try:
        from src.models.database import FundReport, Fund
        from sqlalchemy import and_
        
        # Build query
        query = db.query(FundReport).join(Fund)
        
        filters = []
        if fund_code:
            filters.append(Fund.fund_code == fund_code)
        if year:
            filters.append(FundReport.report_year == year)
        if report_type:
            filters.append(FundReport.report_type == report_type)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        reports = query.offset(offset).limit(page_size).all()
        
        # Format response
        report_list = []
        for report in reports:
            report_list.append({
                "id": str(report.id),
                "fund_code": report.fund.fund_code,
                "fund_name": report.fund.fund_name,
                "report_date": report.report_date.isoformat(),
                "report_type": report.report_type.value,
                "report_year": report.report_year,
                "net_asset_value": float(report.net_asset_value) if report.net_asset_value else None,
                "unit_nav": float(report.unit_nav) if report.unit_nav else None,
                "is_parsed": report.is_parsed,
                "file_type": report.file_type,
                "created_at": report.created_at.isoformat()
            })
        
        bound_logger.info(
            "api.reports.list.success",
            total_count=total_count,
            returned_count=len(report_list)
        )
        
        return {
            "reports": report_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
        
    except Exception as e:
        bound_logger.error(
            "api.reports.list.error",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {e}")


@app.get("/funds")
async def list_funds(
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db_session)
):
    """
    List funds with optional search.
    列出基金，支持搜索。
    """
    bound_logger = logger.bind(
        search=search,
        page=page,
        page_size=page_size
    )
    
    bound_logger.info("api.funds.list.start")
    
    try:
        from src.models.database import Fund
        from sqlalchemy import or_
        
        query = db.query(Fund)
        
        if search:
            search_filter = or_(
                Fund.fund_code.ilike(f"%{search}%"),
                Fund.fund_name.ilike(f"%{search}%"),
                Fund.management_company.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        total_count = query.count()
        
        offset = (page - 1) * page_size
        funds = query.offset(offset).limit(page_size).all()
        
        fund_list = []
        for fund in funds:
            fund_list.append({
                "id": str(fund.id),
                "fund_code": fund.fund_code,
                "fund_name": fund.fund_name,
                "fund_type": fund.fund_type,
                "management_company": fund.management_company,
                "establishment_date": fund.establishment_date.isoformat() if fund.establishment_date else None,
                "created_at": fund.created_at.isoformat()
            })
        
        bound_logger.info(
            "api.funds.list.success",
            total_count=total_count,
            returned_count=len(fund_list)
        )
        
        return {
            "funds": fund_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
        
    except Exception as e:
        bound_logger.error(
            "api.funds.list.error",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to list funds: {e}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "application.starting",
        host="0.0.0.0",
        port=8000,
        debug=settings.debug
    )
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=None  # Use our custom logging
    )