"""Celery工具函数
Celery utility functions for handling async operations in gevent workers.
"""

import asyncio
from typing import Any, Callable, Coroutine
from celery.result import AsyncResult
from src.core.logging import get_logger

logger = get_logger(__name__)


def run_async_task(async_func: Callable[..., Coroutine], *args, **kwargs) -> Any:
    """
    在gevent worker中运行异步函数
    Run async function in gevent worker context.

    Args:
        async_func: 异步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        异步函数的返回值
    """
    try:
        # 在gevent环境中，可以直接运行异步代码
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_func(*args, **kwargs))
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error running async task: {e}")
        raise


def get_async_result(task_id: str) -> AsyncResult:
    """
    获取Celery任务的AsyncResult对象
    Get AsyncResult object for a Celery task.

    Args:
        task_id: Celery任务ID

    Returns:
        AsyncResult对象
    """
    from src.core.celery_app import app

    return AsyncResult(task_id, app=app)
