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
    "fund-report-scraper",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=[
        "src.tasks.download_tasks",  # Phase 5新增的下载任务
    ],
)

# Celery配置 - 生产级配置
app.conf.update(
    # 时区设置
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 序列化设置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # 任务路由配置
    task_routes={
        "src.tasks.download_tasks.download_fund_report_task": {"queue": "download"},
        "src.tasks.download_tasks.test_celery_task": {"queue": "default"},
    },
    # 队列设置
    task_default_queue="default",
    task_create_missing_queues=True,
    # 工作进程设置
    worker_prefetch_multiplier=1,  # 每个worker一次只处理一个任务
    task_acks_late=True,  # 任务完成后才确认
    worker_max_tasks_per_child=1000,  # 每个子进程最多处理1000个任务后重启
    # 任务结果设置
    result_expires=3600,  # 任务结果1小时后过期
    result_persistent=True,  # 持久化结果
    # 任务重试设置
    task_default_retry_delay=60,  # 默认重试延迟60秒
    task_max_retries=3,  # 最大重试次数
    # 任务时间限制
    task_soft_time_limit=300,  # 软时间限制5分钟
    task_time_limit=600,  # 硬时间限制10分钟
    # 监控和事件设置 (Windows兼容)
    worker_send_task_events=False,  # 禁用任务事件发送
    task_send_sent_event=False,  # 禁用任务发送事件
    task_track_started=False,  # 禁用任务开始状态追踪
    # 日志设置
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    # 并发设置 (将在启动时根据执行池类型调整)
    worker_concurrency=None,  # 让Celery自动决定
)

# 队列配置 (可选的高级配置)
app.conf.task_routes.update(
    {
        # 下载任务使用专用队列
        "src.tasks.download_tasks.download_fund_report_task": {
            "queue": "download",
            "routing_key": "download",
        },
        # 测试任务使用默认队列
        "src.tasks.download_tasks.test_celery_task": {
            "queue": "default",
            "routing_key": "default",
        },
    }
)

# 启动时日志
logger.info(
    "celery.app.configured",
    broker_url=settings.celery.broker_url,
    result_backend=settings.celery.result_backend,
    worker_concurrency=app.conf.worker_concurrency,
    task_routes=len(app.conf.task_routes),
    queues=["default", "download"],
)


# 辅助函数
def get_celery_app() -> Celery:
    """获取Celery应用实例"""
    return app


def configure_for_windows():
    """为Windows环境优化Celery配置"""
    import platform

    if platform.system() == "Windows":
        # Windows环境下的特殊配置
        app.conf.update(
            # 禁用一些在Windows上可能有问题的功能
            worker_pool_restarts=True,
            worker_disable_rate_limits=True,
        )
        logger.info("celery.windows_optimization.applied")


def validate_configuration():
    """验证Celery配置"""
    try:
        # 测试Redis连接
        import redis

        redis_client = redis.from_url(settings.celery.broker_url)
        redis_client.ping()
        logger.info("celery.config.redis_connection.ok")

        # 验证任务注册
        registered_tasks = list(app.tasks.keys())
        expected_tasks = [
            "src.tasks.download_tasks.download_fund_report_task",
            "src.tasks.download_tasks.test_celery_task",
        ]

        for task in expected_tasks:
            if task in registered_tasks:
                logger.info("celery.config.task_registered", task=task)
            else:
                logger.warning("celery.config.task_missing", task=task)

        return True

    except Exception as e:
        logger.error("celery.config.validation_failed", error=str(e))
        return False


# 自动应用Windows优化
configure_for_windows()

# 确保任务模块被导入和注册
try:
    import src.tasks.download_tasks

    logger.info("celery.tasks.imported", module="src.tasks.download_tasks")
except ImportError as e:
    logger.error(
        "celery.tasks.import_failed", module="src.tasks.download_tasks", error=str(e)
    )
