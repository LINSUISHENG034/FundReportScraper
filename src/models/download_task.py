"""
下载任务数据模型
Download Task Data Models

SQLAlchemy模型用于持久化下载任务
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import json

from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base

from src.services.download_task_service import TaskStatus

Base = declarative_base()


class DownloadTaskModel(Base):
    """
    下载任务数据库模型
    Download Task Database Model
    """

    __tablename__ = "download_tasks"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 任务基本信息
    task_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)

    # 任务配置
    report_ids = Column(Text, nullable=False)  # JSON字符串存储报告ID列表
    save_dir = Column(String(500), nullable=False)
    max_concurrent = Column(Integer, nullable=False, default=3)

    # 计数信息
    total_count = Column(Integer, nullable=False)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 结果信息
    completed_ids = Column(Text, nullable=True)  # JSON字符串存储成功的ID列表
    failed_results = Column(Text, nullable=True)  # JSON字符串存储失败的结果

    # 错误信息
    error_message = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "status": self.status,
            "report_ids": json.loads(self.report_ids) if self.report_ids else [],
            "save_dir": self.save_dir,
            "max_concurrent": self.max_concurrent,
            "total_count": self.total_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "completed_ids": json.loads(self.completed_ids)
            if self.completed_ids
            else [],
            "failed_results": json.loads(self.failed_results)
            if self.failed_results
            else [],
            "error_message": self.error_message,
        }

    @classmethod
    def from_download_task(cls, task) -> "DownloadTaskModel":
        """从DownloadTask对象创建数据库模型"""
        return cls(
            task_id=task.task_id,
            status=task.status,
            report_ids=json.dumps(task.report_ids),
            save_dir=task.save_dir,
            max_concurrent=task.max_concurrent,
            total_count=task.total_count,
            completed_count=task.completed_count,
            failed_count=task.failed_count,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            completed_ids=json.dumps(task.completed_ids)
            if task.completed_ids
            else None,
            failed_results=json.dumps(task.failed_results)
            if task.failed_results
            else None,
            error_message=task.error_message,
        )

    def to_download_task(self):
        """转换为DownloadTask对象"""
        from src.services.download_task_service import DownloadTask

        return DownloadTask(
            task_id=self.task_id,
            report_ids=json.loads(self.report_ids) if self.report_ids else [],
            save_dir=self.save_dir,
            max_concurrent=self.max_concurrent,
            status=self.status,
            created_at=self.created_at,
            total_count=self.total_count,
            completed_count=self.completed_count,
            failed_count=self.failed_count,
            started_at=self.started_at,
            completed_at=self.completed_at,
            completed_ids=json.loads(self.completed_ids) if self.completed_ids else [],
            failed_results=json.loads(self.failed_results)
            if self.failed_results
            else [],
            error_message=self.error_message,
        )

    def update_from_download_task(self, task):
        """从DownloadTask对象更新数据库模型"""
        self.status = task.status
        self.completed_count = task.completed_count
        self.failed_count = task.failed_count
        self.started_at = task.started_at
        self.completed_at = task.completed_at
        self.completed_ids = (
            json.dumps(task.completed_ids) if task.completed_ids else None
        )
        self.failed_results = (
            json.dumps(task.failed_results) if task.failed_results else None
        )
        self.error_message = task.error_message

    def __repr__(self):
        return f"<DownloadTaskModel(task_id='{self.task_id}', status='{self.status}', progress={self.completed_count}/{self.total_count})>"


def create_download_task_table(engine):
    """
    创建下载任务表
    Create download task table
    """
    Base.metadata.create_all(engine)


def get_download_task_table_info():
    """
    获取下载任务表信息
    Get download task table information
    """
    return {
        "table_name": DownloadTaskModel.__tablename__,
        "columns": [
            {"name": "id", "type": "Integer", "primary_key": True},
            {"name": "task_id", "type": "String(36)", "unique": True, "index": True},
            {"name": "status", "type": "Enum(TaskStatus)", "nullable": False},
            {
                "name": "report_ids",
                "type": "Text",
                "description": "JSON array of report IDs",
            },
            {"name": "save_dir", "type": "String(500)", "nullable": False},
            {"name": "max_concurrent", "type": "Integer", "default": 3},
            {"name": "total_count", "type": "Integer", "nullable": False},
            {"name": "completed_count", "type": "Integer", "default": 0},
            {"name": "failed_count", "type": "Integer", "default": 0},
            {"name": "created_at", "type": "DateTime", "default": "utcnow"},
            {"name": "started_at", "type": "DateTime", "nullable": True},
            {"name": "completed_at", "type": "DateTime", "nullable": True},
            {
                "name": "completed_ids",
                "type": "Text",
                "description": "JSON array of completed IDs",
            },
            {
                "name": "failed_results",
                "type": "Text",
                "description": "JSON array of failed results",
            },
            {"name": "error_message", "type": "Text", "nullable": True},
        ],
    }
