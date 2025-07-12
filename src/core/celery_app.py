"""
Celery application configuration and setup.
配置和初始化Celery应用实例。
"""

from celery import Celery
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# 获取配置
settings = get_settings()

# 创建Celery应用实例
app = Celery(
    'fund-report-scraper',
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=[
        'src.tasks.scraping_tasks',
        'src.tasks.parsing_tasks', 
        'src.tasks.monitoring_tasks'
    ]
)

# Celery配置
app.conf.update(
    # 时区设置
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 序列化设置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 任务路由
    task_routes={
        'src.tasks.scraping_tasks.*': {'queue': 'scraping'},
        'src.tasks.parsing_tasks.*': {'queue': 'parsing'},
        'src.tasks.monitoring_tasks.*': {'queue': 'monitoring'},
    },
    
    # 工作进程设置
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # 任务结果设置
    result_expires=3600,  # 1小时后过期
    
    # 任务重试设置
    task_default_retry_delay=60,  # 默认重试延迟60秒
    task_max_retries=3,
    
    # 心跳和健康检查
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # 并发设置
    worker_concurrency=4,
    
    # 队列设置
    task_default_queue='default',
    task_create_missing_queues=True,
    
    # 监控设置
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# 可选的队列配置
app.conf.task_routes.update({
    'src.tasks.scraping_tasks.scrape_fund_reports': {
        'queue': 'scraping',
        'routing_key': 'scraping',
    },
    'src.tasks.parsing_tasks.parse_xbrl_file': {
        'queue': 'parsing',
        'routing_key': 'parsing',
    },
    'src.tasks.monitoring_tasks.check_task_health': {
        'queue': 'monitoring',
        'routing_key': 'monitoring',
    }
})

# 启动时日志
logger.info(
    "celery.app.configured",
    broker_url=settings.celery.broker_url,
    result_backend=settings.celery.result_backend,
    worker_concurrency=app.conf.worker_concurrency
)


# 用于导入的便捷函数
def get_celery_app() -> Celery:
    """获取Celery应用实例"""
    return app