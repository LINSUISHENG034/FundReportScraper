"""
Celery Beat定时调度配置
配置周期性任务的调度规则，实现自动化数据采集。
"""

from datetime import timedelta
from celery.schedules import crontab

from src.core.celery_app import app
from src.core.logging import get_logger

logger = get_logger(__name__)

# Celery Beat定时任务配置
app.conf.beat_schedule = {
    # 每日凌晨2点执行基金报告批量爬取
    'daily-fund-scraping': {
        'task': 'src.tasks.scraping_tasks.schedule_periodic_scraping',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2:00
        'options': {
            'queue': 'scraping',
            'routing_key': 'scraping'
        }
    },
    
    # 每小时检查系统健康状况
    'hourly-health-check': {
        'task': 'src.tasks.monitoring_tasks.check_task_health',
        'schedule': timedelta(minutes=60),  # 每60分钟
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring'
        }
    },
    
    # 每天凌晨3点生成日报
    'daily-report-generation': {
        'task': 'src.tasks.monitoring_tasks.generate_daily_report',
        'schedule': crontab(hour=3, minute=0),  # 每天凌晨3:00
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring'
        }
    },
    
    # 每周日凌晨4点清理过期数据
    'weekly-cleanup': {
        'task': 'src.tasks.monitoring_tasks.cleanup_expired_tasks',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # 每周日凌晨4:00
        'kwargs': {'days_to_keep': 30},  # 保留30天数据
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring'
        }
    },
    
    # 每15分钟监控爬取进度
    'scraping-progress-monitor': {
        'task': 'src.tasks.monitoring_tasks.monitor_scraping_progress',
        'schedule': timedelta(minutes=15),  # 每15分钟
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring'
        }
    },
    
    # 每30分钟检查失败告警
    'failure-alert-check': {
        'task': 'src.tasks.monitoring_tasks.alert_on_failures',
        'schedule': timedelta(minutes=30),  # 每30分钟
        'kwargs': {'failure_threshold': 10, 'time_window_minutes': 60},
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring'
        }
    },
    
    # 每2小时重新解析失败的报告
    'retry-failed-parsing': {
        'task': 'src.tasks.parsing_tasks.reparse_failed_reports',
        'schedule': timedelta(hours=2),  # 每2小时
        'kwargs': {'days_back': 1},  # 重试最近1天的失败记录
        'options': {
            'queue': 'parsing',
            'routing_key': 'parsing'
        }
    }
}

# 时区设置
app.conf.timezone = 'Asia/Shanghai'

logger.info(
    "celery.beat.configured",
    scheduled_tasks=list(app.conf.beat_schedule.keys()),
    timezone=app.conf.timezone
)