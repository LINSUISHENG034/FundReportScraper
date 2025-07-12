"""
全局错误处理和重试机制
Global error handling and retry mechanisms for robust operation.
"""

import asyncio
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from functools import wraps
from dataclasses import dataclass
import random

from src.core.logging import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"          # 低级错误，可以忽略
    MEDIUM = "medium"    # 中级错误，需要重试
    HIGH = "high"        # 高级错误，需要告警
    CRITICAL = "critical"  # 严重错误，需要立即处理


class RetryStrategy(Enum):
    """重试策略"""
    FIXED = "fixed"              # 固定延迟
    LINEAR = "linear"            # 线性增长
    EXPONENTIAL = "exponential"  # 指数退避
    RANDOM = "random"            # 随机延迟


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class ErrorContext:
    """错误上下文信息"""
    error: Exception
    error_type: Type[Exception]
    severity: ErrorSeverity
    timestamp: datetime
    function_name: str
    args: tuple
    kwargs: dict
    attempt: int
    max_attempts: int
    traceback_str: str


class RetryableError(Exception):
    """可重试的错误"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        super().__init__(message)
        self.severity = severity


class NonRetryableError(Exception):
    """不可重试的错误"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH):
        super().__init__(message)
        self.severity = severity


class CircuitBreakerError(Exception):
    """熔断器错误"""
    pass


class CircuitBreaker:
    """
    熔断器模式实现
    
    当错误率超过阈值时，暂时停止调用，给系统恢复时间。
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败次数阈值
            recovery_timeout: 恢复超时时间（秒）
            expected_exception: 期望的异常类型
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
        logger.info(
            "circuit_breaker.initialized",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数的返回值
            
        Raises:
            CircuitBreakerError: 当熔断器处于开启状态时
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker.half_open")
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        if self.last_failure_time is None:
            return False
        
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """成功调用时的处理"""
        self.failure_count = 0
        self.state = "CLOSED"
        logger.debug("circuit_breaker.success_reset")
    
    def _on_failure(self):
        """失败调用时的处理"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                "circuit_breaker.opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )
    
    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recovery_timeout": self.recovery_timeout
        }


class GlobalErrorHandler:
    """
    全局错误处理器
    
    统一处理各种异常，分类错误严重程度，记录详细日志。
    """
    
    def __init__(self):
        """初始化全局错误处理器"""
        self.error_counts = {}
        self.circuit_breakers = {}
        
        # 错误分类映射
        self.error_severity_map = {
            # 网络相关错误
            ConnectionError: ErrorSeverity.MEDIUM,
            TimeoutError: ErrorSeverity.MEDIUM,
            
            # HTTP错误
            Exception: ErrorSeverity.MEDIUM,  # 默认为中级
            
            # 数据库错误
            # sqlalchemy.exc.OperationalError: ErrorSeverity.HIGH,
            
            # 解析错误
            ValueError: ErrorSeverity.LOW,
            KeyError: ErrorSeverity.LOW,
            
            # 文件系统错误
            FileNotFoundError: ErrorSeverity.MEDIUM,
            PermissionError: ErrorSeverity.HIGH,
            
            # 内存错误
            MemoryError: ErrorSeverity.CRITICAL,
            
            # 自定义错误
            RetryableError: ErrorSeverity.MEDIUM,
            NonRetryableError: ErrorSeverity.HIGH,
        }
        
        logger.info("global_error_handler.initialized")
    
    def classify_error(self, error: Exception) -> ErrorSeverity:
        """
        分类错误严重程度
        
        Args:
            error: 异常对象
            
        Returns:
            错误严重程度
        """
        # 检查是否有自定义的严重程度
        if hasattr(error, 'severity'):
            return error.severity
        
        # 根据异常类型分类
        for error_type, severity in self.error_severity_map.items():
            if isinstance(error, error_type):
                return severity
        
        # 默认为中级错误
        return ErrorSeverity.MEDIUM
    
    def should_retry(self, error: Exception, attempt: int, max_attempts: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 异常对象
            attempt: 当前尝试次数
            max_attempts: 最大尝试次数
            
        Returns:
            是否应该重试
        """
        if attempt >= max_attempts:
            return False
        
        # 不可重试的错误
        if isinstance(error, NonRetryableError):
            return False
        
        # 严重错误不重试
        severity = self.classify_error(error)
        if severity == ErrorSeverity.CRITICAL:
            return False
        
        # 其他情况可以重试
        return True
    
    def calculate_delay(
        self, 
        attempt: int, 
        config: RetryConfig
    ) -> float:
        """
        计算重试延迟时间
        
        Args:
            attempt: 当前尝试次数
            config: 重试配置
            
        Returns:
            延迟时间（秒）
        """
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_factor ** (attempt - 1))
        elif config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(config.base_delay, config.max_delay)
        else:
            delay = config.base_delay
        
        # 限制最大延迟
        delay = min(delay, config.max_delay)
        
        # 添加随机抖动
        if config.jitter:
            jitter_range = delay * 0.1  # 10%的抖动
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext
    ) -> None:
        """
        处理错误
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        # 记录错误统计
        error_key = f"{context.function_name}:{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 记录详细日志
        log_data = {
            "function": context.function_name,
            "error_type": context.error_type.__name__,
            "error_message": str(error),
            "severity": context.severity.value,
            "attempt": context.attempt,
            "max_attempts": context.max_attempts,
            "args_count": len(context.args),
            "kwargs_keys": list(context.kwargs.keys()),
            "timestamp": context.timestamp.isoformat()
        }
        
        if context.severity == ErrorSeverity.LOW:
            logger.debug("error_handler.low_severity", **log_data)
        elif context.severity == ErrorSeverity.MEDIUM:
            logger.warning("error_handler.medium_severity", **log_data)
        elif context.severity == ErrorSeverity.HIGH:
            logger.error("error_handler.high_severity", **log_data)
        elif context.severity == ErrorSeverity.CRITICAL:
            logger.critical(
                "error_handler.critical_severity",
                traceback=context.traceback_str,
                **log_data
            )
        
        # 发送告警（如果需要）
        if context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._send_alert(error, context)
    
    async def _send_alert(
        self,
        error: Exception,
        context: ErrorContext
    ) -> None:
        """
        发送告警
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        # 这里可以集成告警系统，如钉钉、微信、邮件等
        # 简化实现，只记录告警日志
        logger.critical(
            "error_handler.alert_triggered",
            function=context.function_name,
            error_type=type(error).__name__,
            error_message=str(error),
            severity=context.severity.value,
            traceback=context.traceback_str
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": self.error_counts,
            "circuit_breakers": {
                name: breaker.get_status() 
                for name, breaker in self.circuit_breakers.items()
            }
        }
    
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """
        获取或创建熔断器
        
        Args:
            name: 熔断器名称
            **kwargs: 熔断器配置参数
            
        Returns:
            熔断器实例
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(**kwargs)
        return self.circuit_breakers[name]


# 全局错误处理器实例
global_error_handler = GlobalErrorHandler()


def retry_on_failure(
    config: RetryConfig = None,
    circuit_breaker_name: Optional[str] = None,
    circuit_breaker_config: Optional[Dict] = None
):
    """
    重试装饰器
    
    Args:
        config: 重试配置
        circuit_breaker_name: 熔断器名称
        circuit_breaker_config: 熔断器配置
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 获取熔断器（如果配置了）
            circuit_breaker = None
            if circuit_breaker_name:
                cb_config = circuit_breaker_config or {}
                circuit_breaker = global_error_handler.get_circuit_breaker(
                    circuit_breaker_name, **cb_config
                )
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    if circuit_breaker:
                        return await circuit_breaker.call(func, *args, **kwargs)
                    else:
                        return await func(*args, **kwargs)
                        
                except Exception as e:
                    # 创建错误上下文
                    error_context = ErrorContext(
                        error=e,
                        error_type=type(e),
                        severity=global_error_handler.classify_error(e),
                        timestamp=datetime.now(),
                        function_name=func.__name__,
                        args=args,
                        kwargs=kwargs,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        traceback_str=traceback.format_exc()
                    )
                    
                    # 处理错误
                    await global_error_handler.handle_error(e, error_context)
                    
                    # 判断是否应该重试
                    if not global_error_handler.should_retry(e, attempt, config.max_attempts):
                        raise e
                    
                    # 最后一次尝试失败，直接抛出异常
                    if attempt == config.max_attempts:
                        raise e
                    
                    # 计算延迟时间并等待
                    delay = global_error_handler.calculate_delay(attempt, config)
                    logger.info(
                        "retry_decorator.waiting",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay=delay,
                        error_type=type(e).__name__
                    )
                    await asyncio.sleep(delay)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步函数的包装器
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # 返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def handle_exceptions(
    exceptions: Union[Type[Exception], tuple] = Exception,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    reraise: bool = True
):
    """
    异常处理装饰器
    
    Args:
        exceptions: 要捕获的异常类型
        severity: 错误严重程度
        reraise: 是否重新抛出异常
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                # 创建错误上下文
                error_context = ErrorContext(
                    error=e,
                    error_type=type(e),
                    severity=severity,
                    timestamp=datetime.now(),
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs,
                    attempt=1,
                    max_attempts=1,
                    traceback_str=traceback.format_exc()
                )
                
                # 处理错误
                await global_error_handler.handle_error(e, error_context)
                
                if reraise:
                    raise e
                else:
                    return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                # 同步版本的错误处理
                error_context = ErrorContext(
                    error=e,
                    error_type=type(e),
                    severity=severity,
                    timestamp=datetime.now(),
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs,
                    attempt=1,
                    max_attempts=1,
                    traceback_str=traceback.format_exc()
                )
                
                # 同步处理错误
                asyncio.run(global_error_handler.handle_error(e, error_context))
                
                if reraise:
                    raise e
                else:
                    return None
        
        # 返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator