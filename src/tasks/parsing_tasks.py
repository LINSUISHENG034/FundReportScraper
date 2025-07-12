"""
Parsing tasks for Celery.
XBRL解析任务的Celery异步实现。
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4

from celery import Task
from celery.exceptions import Retry

from src.core.celery_app import app
from src.core.logging import get_logger
from src.parsers.xbrl_parser import XBRLParser, XBRLParseError
from src.services.data_persistence import FundDataPersistenceService, DataPersistenceError
from src.storage.minio_client import MinIOClient
from src.models.database import ReportType

logger = get_logger(__name__)


class ParseTask(Task):
    """自定义解析任务基类"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调"""
        logger.error(
            "parsing.task.failed",
            task_id=task_id,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调"""
        logger.info(
            "parsing.task.success",
            task_id=task_id,
            result_type=type(retval).__name__
        )


@app.task(bind=True, base=ParseTask, max_retries=3)
def parse_xbrl_file(
    self,
    fund_code: str,
    storage_path: str,
    report_type: str,
    report_date: str,
    file_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    解析单个XBRL文件
    
    Args:
        fund_code: 基金代码
        storage_path: MinIO存储路径
        report_type: 报告类型
        report_date: 报告日期
        file_url: 原始文件URL
        
    Returns:
        解析结果
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        fund_code=fund_code,
        storage_path=storage_path
    )
    
    bound_logger.info("parsing.single.start")
    
    try:
        # 解析报告类型
        if report_type == 'annual':
            parsed_report_type = ReportType.ANNUAL
        elif report_type == 'semi_annual':
            parsed_report_type = ReportType.SEMI_ANNUAL
        elif report_type == 'quarterly':
            parsed_report_type = ReportType.QUARTERLY
        else:
            raise ValueError(f"Unsupported report type: {report_type}")
        
        # 解析报告日期
        parsed_report_date = datetime.fromisoformat(report_date)
        
        # 从MinIO下载文件
        storage = MinIOClient()
        file_content = storage.download_file_content(storage_path)
        
        # 创建XBRL解析器
        parser = XBRLParser()
        parser.load_from_content(file_content)
        
        # 提取基金基本信息
        fund_info = parser.extract_fund_basic_info()
        if not fund_info:
            raise XBRLParseError("无法提取基金基本信息")
        
        # 确保基金代码匹配
        if fund_info.fund_code != fund_code:
            bound_logger.warning(
                "parsing.fund_code.mismatch",
                expected=fund_code,
                actual=fund_info.fund_code
            )
            # 使用传入的基金代码
            fund_info.fund_code = fund_code
        
        # 确保报告日期匹配
        if fund_info.report_date.date() != parsed_report_date.date():
            bound_logger.warning(
                "parsing.report_date.mismatch",
                expected=parsed_report_date.date(),
                actual=fund_info.report_date.date()
            )
            # 使用传入的报告日期
            fund_info.report_date = parsed_report_date
        
        # 提取资产配置数据
        asset_allocation = parser.extract_asset_allocation()
        
        # 提取前十大重仓股
        top_holdings = parser.extract_top_holdings()
        
        # 提取行业配置
        industry_allocations = parser.extract_industry_allocation()
        
        # 保存到数据库
        with FundDataPersistenceService() as persistence:
            report_id = persistence.save_fund_report_data(
                fund_info=fund_info,
                report_type=parsed_report_type,
                file_path=storage_path,
                file_type="XBRL",
                asset_allocation=asset_allocation,
                top_holdings=top_holdings,
                industry_allocations=industry_allocations,
                original_file_url=file_url,
                file_size=len(file_content)
            )
        
        result = {
            'fund_code': fund_code,
            'report_id': report_id,
            'report_type': report_type,
            'report_date': report_date,
            'storage_path': storage_path,
            'extracted_data': {
                'has_basic_info': fund_info is not None,
                'has_asset_allocation': asset_allocation is not None,
                'top_holdings_count': len(top_holdings),
                'industry_allocations_count': len(industry_allocations)
            },
            'file_size': len(file_content),
            'parsed_at': datetime.now().isoformat()
        }
        
        bound_logger.info(
            "parsing.single.success",
            fund_code=fund_code,
            report_id=report_id,
            **result['extracted_data']
        )
        
        return result
        
    except XBRLParseError as exc:
        bound_logger.error(
            "parsing.single.xbrl_error",
            fund_code=fund_code,
            error=str(exc)
        )
        
        # XBRL解析错误不重试，直接失败
        raise exc
        
    except DataPersistenceError as exc:
        bound_logger.error(
            "parsing.single.persistence_error",
            fund_code=fund_code,
            error=str(exc)
        )
        
        # 数据持久化错误重试
        if self.request.retries < self.max_retries:
            bound_logger.info(
                "parsing.single.retrying",
                fund_code=fund_code,
                retry_count=self.request.retries + 1
            )
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        
        raise exc
        
    except Exception as exc:
        bound_logger.error(
            "parsing.single.error",
            fund_code=fund_code,
            error=str(exc),
            error_type=type(exc).__name__
        )
        
        # 其他错误重试
        if self.request.retries < self.max_retries:
            bound_logger.info(
                "parsing.single.retrying",
                fund_code=fund_code,
                retry_count=self.request.retries + 1
            )
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        raise exc


@app.task(bind=True, base=ParseTask)
def batch_parse_xbrl_files(
    self,
    file_info_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    批量解析XBRL文件
    
    Args:
        file_info_list: 文件信息列表，每个元素包含 {fund_code, storage_path, report_type, report_date}
        
    Returns:
        批量解析结果
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        files_count=len(file_info_list)
    )
    
    bound_logger.info("parsing.batch.start")
    
    try:
        results = {
            'total_files': len(file_info_list),
            'successful_parses': 0,
            'failed_parses': 0,
            'parsing_tasks': [],
            'errors': []
        }
        
        # 为每个文件创建独立的解析任务
        for file_info in file_info_list:
            try:
                task_result = parse_xbrl_file.delay(
                    fund_code=file_info['fund_code'],
                    storage_path=file_info['storage_path'],
                    report_type=file_info['report_type'],
                    report_date=file_info['report_date'],
                    file_url=file_info.get('file_url')
                )
                
                results['parsing_tasks'].append({
                    'task_id': task_result.id,
                    'fund_code': file_info['fund_code'],
                    'storage_path': file_info['storage_path']
                })
                
                bound_logger.debug(
                    "parsing.batch.task_created",
                    fund_code=file_info['fund_code'],
                    task_id=task_result.id
                )
                
            except Exception as e:
                results['failed_parses'] += 1
                error_info = {
                    'fund_code': file_info['fund_code'],
                    'storage_path': file_info['storage_path'],
                    'error': str(e)
                }
                results['errors'].append(error_info)
                
                bound_logger.error(
                    "parsing.batch.task_creation_failed",
                    **error_info
                )
        
        bound_logger.info(
            "parsing.batch.completed",
            total_files=results['total_files'],
            tasks_created=len(results['parsing_tasks']),
            creation_failures=results['failed_parses']
        )
        
        return results
        
    except Exception as exc:
        bound_logger.error(
            "parsing.batch.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc


@app.task(bind=True)
def reparse_failed_reports(
    self,
    days_back: int = 7,
    fund_codes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    重新解析失败的报告
    
    Args:
        days_back: 查找多少天前的失败报告
        fund_codes: 指定基金代码列表，为None时处理所有基金
        
    Returns:
        重新解析结果
    """
    bound_logger = logger.bind(
        task_id=self.request.id,
        days_back=days_back
    )
    
    bound_logger.info("parsing.reparse.start")
    
    try:
        # 从数据库查找失败的报告
        with FundDataPersistenceService() as persistence:
            # 这里简化处理，实际可以添加查询失败报告的方法
            # failed_reports = persistence.get_failed_reports(days_back, fund_codes)
            failed_reports = []  # 占位符
        
        if not failed_reports:
            bound_logger.info("parsing.reparse.no_failed_reports")
            return {
                'failed_reports_found': 0,
                'reparse_tasks_created': 0
            }
        
        # 创建重新解析任务
        results = {
            'failed_reports_found': len(failed_reports),
            'reparse_tasks_created': 0,
            'reparse_tasks': [],
            'errors': []
        }
        
        for report in failed_reports:
            try:
                task_result = parse_xbrl_file.delay(
                    fund_code=report['fund_code'],
                    storage_path=report['storage_path'],
                    report_type=report['report_type'],
                    report_date=report['report_date']
                )
                
                results['reparse_tasks'].append(task_result.id)
                results['reparse_tasks_created'] += 1
                
            except Exception as e:
                results['errors'].append({
                    'fund_code': report['fund_code'],
                    'error': str(e)
                })
        
        bound_logger.info(
            "parsing.reparse.completed",
            **results
        )
        
        return results
        
    except Exception as exc:
        bound_logger.error(
            "parsing.reparse.error",
            error=str(exc),
            error_type=type(exc).__name__
        )
        raise exc