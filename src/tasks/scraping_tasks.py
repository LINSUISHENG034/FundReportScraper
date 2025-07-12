"""
Scraping tasks for Celery.
爬取任务的Celery异步实现。
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4

from celery import Task
from celery.exceptions import Retry

from src.core.celery_app import app
from src.core.logging import get_logger
from src.scrapers.fund_scraper import FundReportScraper
from src.storage.minio_client import MinIOClient
from src.models.database import ReportType, TaskStatus
from src.models.connection import get_db_session
from src.tasks.parsing_tasks import parse_xbrl_file

logger = get_logger(__name__)


class ScrapeTask(Task):
    """自定义爬取任务基类"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调"""
        logger.error(
            "scraping.task.failed",
            task_id=task_id,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调"""
        logger.info(
            "scraping.task.success",
            task_id=task_id,
            result=retval
        )


@app.task(bind=True, base=ScrapeTask, max_retries=3)
def scrape_fund_reports(
    self,
    fund_codes: Optional[List[str]] = None,
    report_types: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force_update: bool = False
) -> Dict[str, Any]:
    """
    批量爬取基金报告
    
    Args:
        fund_codes: 基金代码列表，为None时爬取所有基金
        report_types: 报告类型列表 ['annual', 'semi_annual', 'quarterly']
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        force_update: 是否强制更新已存在的报告
        
    Returns:
        爬取结果摘要
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        fund_codes_count=len(fund_codes) if fund_codes else 0,
        report_types=report_types
    )
    
    bound_logger.info("scraping.batch.start")
    
    try:
        # 解析报告类型
        if report_types:
            parsed_types = []
            for rt in report_types:
                if rt == 'annual':
                    parsed_types.append(ReportType.ANNUAL)
                elif rt == 'semi_annual':
                    parsed_types.append(ReportType.SEMI_ANNUAL)
                elif rt == 'quarterly':
                    parsed_types.append(ReportType.QUARTERLY)
        else:
            parsed_types = [ReportType.ANNUAL, ReportType.SEMI_ANNUAL, ReportType.QUARTERLY]
        
        # 解析日期
        parsed_start_date = None
        parsed_end_date = None
        if start_date:
            parsed_start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 创建爬虫实例
        scraper = FundReportScraper()
        
        # 执行爬取
        results = {
            'total_attempts': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'parsing_tasks_created': 0,
            'errors': []
        }
        
        # 获取基金列表（如果未指定）
        if not fund_codes:
            fund_codes = scraper.get_all_fund_codes()
            bound_logger.info("scraping.fund_codes.fetched", count=len(fund_codes))
        
        # 对每个基金创建独立的爬取任务
        for fund_code in fund_codes:
            try:
                # 创建单个基金爬取任务
                task_result = scrape_single_fund_report.delay(
                    fund_code=fund_code,
                    report_types=report_types,
                    start_date=start_date,
                    end_date=end_date,
                    force_update=force_update
                )
                
                results['total_attempts'] += 1
                bound_logger.debug(
                    "scraping.single_task.created",
                    fund_code=fund_code,
                    task_id=task_result.id
                )
                
            except Exception as e:
                results['failed_downloads'] += 1
                results['errors'].append({
                    'fund_code': fund_code,
                    'error': str(e)
                })
                bound_logger.error(
                    "scraping.single_task.creation_failed",
                    fund_code=fund_code,
                    error=str(e)
                )
        
        bound_logger.info(
            "scraping.batch.completed",
            **results
        )
        
        return results
        
    except Exception as exc:
        bound_logger.error(
            "scraping.batch.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            bound_logger.info(
                "scraping.batch.retrying",
                retry_count=self.request.retries + 1
            )
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        raise exc


@app.task(bind=True, base=ScrapeTask, max_retries=3)
def scrape_single_fund_report(
    self,
    fund_code: str,
    report_types: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force_update: bool = False
) -> Dict[str, Any]:
    """
    爬取单个基金的报告
    
    Args:
        fund_code: 基金代码
        report_types: 报告类型列表
        start_date: 开始日期
        end_date: 结束日期
        force_update: 是否强制更新
        
    Returns:
        爬取结果
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        fund_code=fund_code
    )
    
    bound_logger.info("scraping.single.start")
    
    try:
        # 解析报告类型
        if report_types:
            parsed_types = []
            for rt in report_types:
                if rt == 'annual':
                    parsed_types.append(ReportType.ANNUAL)
                elif rt == 'semi_annual':
                    parsed_types.append(ReportType.SEMI_ANNUAL)
                elif rt == 'quarterly':
                    parsed_types.append(ReportType.QUARTERLY)
        else:
            parsed_types = [ReportType.ANNUAL, ReportType.SEMI_ANNUAL, ReportType.QUARTERLY]
        
        # 创建爬虫和存储客户端
        scraper = FundReportScraper()
        storage = MinIOClient()
        
        results = {
            'fund_code': fund_code,
            'downloaded_files': [],
            'parsing_tasks': [],
            'errors': []
        }
        
        # 对每种报告类型进行爬取
        for report_type in parsed_types:
            try:
                # 获取报告列表
                reports = scraper.get_fund_reports(
                    fund_code=fund_code,
                    report_type=report_type,
                    start_date=datetime.strptime(start_date, '%Y-%m-%d') if start_date else None,
                    end_date=datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
                )
                
                # 下载每个报告
                for report_info in reports:
                    try:
                        # 检查是否已存在（如果不强制更新）
                        if not force_update:
                            # 这里可以添加数据库检查逻辑
                            pass
                        
                        # 下载文件
                        file_content = scraper.download_report(report_info['download_url'])
                        
                        # 生成存储路径
                        file_name = f"{fund_code}_{report_type.value}_{report_info['report_date'].strftime('%Y%m%d')}.xbrl"
                        storage_path = f"fund-reports/{fund_code}/{file_name}"
                        
                        # 上传到MinIO
                        storage.upload_file_content(
                            content=file_content,
                            object_name=storage_path,
                            content_type='application/xml'
                        )
                        
                        results['downloaded_files'].append({
                            'report_date': report_info['report_date'].isoformat(),
                            'report_type': report_type.value,
                            'storage_path': storage_path,
                            'file_size': len(file_content)
                        })
                        
                        # 创建解析任务
                        parse_task = parse_xbrl_file.delay(
                            fund_code=fund_code,
                            storage_path=storage_path,
                            report_type=report_type.value,
                            report_date=report_info['report_date'].isoformat()
                        )
                        
                        results['parsing_tasks'].append(parse_task.id)
                        
                        bound_logger.info(
                            "scraping.single.file_processed",
                            fund_code=fund_code,
                            report_date=report_info['report_date'].isoformat(),
                            storage_path=storage_path,
                            parse_task_id=parse_task.id
                        )
                        
                    except Exception as e:
                        error_info = {
                            'report_date': report_info['report_date'].isoformat(),
                            'report_type': report_type.value,
                            'error': str(e)
                        }
                        results['errors'].append(error_info)
                        
                        bound_logger.error(
                            "scraping.single.file_failed",
                            fund_code=fund_code,
                            **error_info
                        )
                        
            except Exception as e:
                results['errors'].append({
                    'report_type': report_type.value,
                    'error': str(e)
                })
                
                bound_logger.error(
                    "scraping.single.type_failed",
                    fund_code=fund_code,
                    report_type=report_type.value,
                    error=str(e)
                )
        
        bound_logger.info(
            "scraping.single.completed",
            fund_code=fund_code,
            downloaded_count=len(results['downloaded_files']),
            parsing_tasks_count=len(results['parsing_tasks']),
            errors_count=len(results['errors'])
        )
        
        return results
        
    except Exception as exc:
        bound_logger.error(
            "scraping.single.error",
            fund_code=fund_code,
            error=str(exc),
            error_type=type(exc).__name__
        )
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            bound_logger.info(
                "scraping.single.retrying",
                fund_code=fund_code,
                retry_count=self.request.retries + 1
            )
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        
        raise exc


@app.task(bind=True)
def schedule_periodic_scraping(self) -> Dict[str, Any]:
    """
    定时调度爬取任务
    
    Returns:
        调度结果
    """
    bound_logger = logger.bind(task_id=self.request.id)
    bound_logger.info("scraping.schedule.start")
    
    try:
        # 获取需要更新的基金代码（可以从数据库获取）
        # 这里简化处理，实际可以根据业务需求定制
        
        # 创建批量爬取任务 - 只爬取最近的季报和年报
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 最近90天
        
        task_result = scrape_fund_reports.delay(
            fund_codes=None,  # 爬取所有基金
            report_types=['quarterly', 'annual'],
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            force_update=False
        )
        
        result = {
            'scheduled_at': datetime.now().isoformat(),
            'batch_task_id': task_result.id,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }
        
        bound_logger.info(
            "scraping.schedule.completed",
            **result
        )
        
        return result
        
    except Exception as exc:
        bound_logger.error(
            "scraping.schedule.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc