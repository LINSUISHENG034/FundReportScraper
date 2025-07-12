"""
Advanced rate limiter with multiple algorithms and strategies.
增强型限流器，支持令牌桶、漏桶、滑动窗口等多种算法。
"""

import asyncio
import time
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from enum import Enum
from dataclasses import dataclass

from src.core.logging import get_logger
from src.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class LimitStrategy(Enum):
    """限流策略枚举"""
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """限流配置"""
    max_requests: int = 60  # 最大请求数
    time_window: int = 60   # 时间窗口（秒）
    burst_size: int = 10    # 突发大小
    strategy: LimitStrategy = LimitStrategy.TOKEN_BUCKET
    key_prefix: str = "rate_limit"


class AdvancedRateLimiter:
    """
    高级限流器
    
    支持多种限流算法：
    1. 令牌桶 (Token Bucket) - 允许突发流量
    2. 漏桶 (Leaky Bucket) - 平滑输出
    3. 滑动窗口 (Sliding Window) - 精确时间控制
    4. 固定窗口 (Fixed Window) - 简单实现
    """
    
    def __init__(
        self,
        config: RateLimitConfig,
        redis_client: Optional[redis.Redis] = None,
        distributed: bool = True
    ):
        """
        初始化高级限流器
        
        Args:
            config: 限流配置
            redis_client: Redis客户端，用于分布式限流
            distributed: 是否使用分布式限流
        """
        self.config = config
        self.distributed = distributed
        
        if distributed and redis_client is None:
            # 使用默认Redis配置
            self.redis_client = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                decode_responses=True
            )
        else:
            self.redis_client = redis_client
        
        # 本地状态（用于非分布式模式）
        self._local_state = {}
        self._lock = asyncio.Lock()
        
        logger.info(
            "advanced_rate_limiter.initialized",
            strategy=config.strategy.value,
            max_requests=config.max_requests,
            time_window=config.time_window,
            distributed=distributed
        )
    
    async def is_allowed(
        self,
        key: str,
        tokens: int = 1
    ) -> Dict[str, Any]:
        """
        检查请求是否被允许
        
        Args:
            key: 限流键（如IP地址、用户ID等）
            tokens: 请求的令牌数量
            
        Returns:
            包含allowed, remaining, reset_time等信息的字典
        """
        full_key = f"{self.config.key_prefix}:{self.config.strategy.value}:{key}"
        
        if self.config.strategy == LimitStrategy.TOKEN_BUCKET:
            return await self._token_bucket_check(full_key, tokens)
        elif self.config.strategy == LimitStrategy.LEAKY_BUCKET:
            return await self._leaky_bucket_check(full_key, tokens)
        elif self.config.strategy == LimitStrategy.SLIDING_WINDOW:
            return await self._sliding_window_check(full_key, tokens)
        elif self.config.strategy == LimitStrategy.FIXED_WINDOW:
            return await self._fixed_window_check(full_key, tokens)
        else:
            raise ValueError(f"Unsupported strategy: {self.config.strategy}")
    
    async def _token_bucket_check(self, key: str, tokens: int) -> Dict[str, Any]:
        """令牌桶算法检查"""
        now = time.time()
        
        if self.distributed:
            return await self._distributed_token_bucket(key, tokens, now)
        else:
            return await self._local_token_bucket(key, tokens, now)
    
    async def _distributed_token_bucket(self, key: str, tokens: int, now: float) -> Dict[str, Any]:
        """分布式令牌桶实现"""
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        local ttl = tonumber(ARGV[5])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or now
        
        -- 计算需要补充的令牌
        local elapsed = now - last_refill
        if elapsed > 0 then
            local tokens_to_add = elapsed * refill_rate
            tokens = math.min(max_tokens, tokens + tokens_to_add)
        end
        
        local allowed = 0
        local remaining = tokens
        
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            allowed = 1
            remaining = tokens
        end
        
        -- 更新状态
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        return {allowed, remaining, math.ceil(max_tokens)}
        """
        
        try:
            refill_rate = self.config.max_requests / self.config.time_window
            ttl = self.config.time_window * 2  # TTL设为时间窗口的2倍
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.redis_client.eval(
                    lua_script, 1, key,
                    self.config.burst_size, refill_rate, tokens, now, ttl
                )
            )
            
            allowed, remaining, limit = result
            
            return {
                "allowed": bool(allowed),
                "remaining": int(remaining),
                "limit": int(limit),
                "reset_time": now + self.config.time_window,
                "strategy": self.config.strategy.value
            }
            
        except Exception as e:
            logger.error(
                "advanced_rate_limiter.distributed_token_bucket.error",
                key=key,
                error=str(e)
            )
            # 降级到允许请求
            return {
                "allowed": True,
                "remaining": self.config.burst_size,
                "limit": self.config.burst_size,
                "reset_time": now + self.config.time_window,
                "strategy": self.config.strategy.value,
                "error": str(e)
            }
    
    async def _local_token_bucket(self, key: str, tokens: int, now: float) -> Dict[str, Any]:
        """本地令牌桶实现"""
        async with self._lock:
            if key not in self._local_state:
                self._local_state[key] = {
                    "tokens": self.config.burst_size,
                    "last_refill": now
                }
            
            state = self._local_state[key]
            
            # 计算需要补充的令牌
            elapsed = now - state["last_refill"]
            if elapsed > 0:
                refill_rate = self.config.max_requests / self.config.time_window
                tokens_to_add = elapsed * refill_rate
                state["tokens"] = min(self.config.burst_size, state["tokens"] + tokens_to_add)
                state["last_refill"] = now
            
            allowed = state["tokens"] >= tokens
            if allowed:
                state["tokens"] -= tokens
            
            return {
                "allowed": allowed,
                "remaining": int(state["tokens"]),
                "limit": self.config.burst_size,
                "reset_time": now + self.config.time_window,
                "strategy": self.config.strategy.value
            }
    
    async def _leaky_bucket_check(self, key: str, tokens: int) -> Dict[str, Any]:
        """漏桶算法检查"""
        now = time.time()
        
        if self.distributed:
            lua_script = """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local leak_rate = tonumber(ARGV[2])
            local tokens_requested = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])
            local ttl = tonumber(ARGV[5])
            
            local bucket = redis.call('HMGET', key, 'level', 'last_leak')
            local level = tonumber(bucket[1]) or 0
            local last_leak = tonumber(bucket[2]) or now
            
            -- 计算泄漏的令牌
            local elapsed = now - last_leak
            if elapsed > 0 then
                local tokens_leaked = elapsed * leak_rate
                level = math.max(0, level - tokens_leaked)
            end
            
            local allowed = 0
            if level + tokens_requested <= capacity then
                level = level + tokens_requested
                allowed = 1
            end
            
            -- 更新状态
            redis.call('HMSET', key, 'level', level, 'last_leak', now)
            redis.call('EXPIRE', key, ttl)
            
            return {allowed, capacity - level, capacity}
            """
            
            try:
                leak_rate = self.config.max_requests / self.config.time_window
                ttl = self.config.time_window * 2
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.redis_client.eval(
                        lua_script, 1, key,
                        self.config.burst_size, leak_rate, tokens, now, ttl
                    )
                )
                
                allowed, remaining, limit = result
                
                return {
                    "allowed": bool(allowed),
                    "remaining": int(remaining),
                    "limit": int(limit),
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value
                }
                
            except Exception as e:
                logger.error(
                    "advanced_rate_limiter.leaky_bucket.error",
                    key=key,
                    error=str(e)
                )
                return {
                    "allowed": True,
                    "remaining": self.config.burst_size,
                    "limit": self.config.burst_size,
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value,
                    "error": str(e)
                }
        else:
            # 本地漏桶实现
            async with self._lock:
                if key not in self._local_state:
                    self._local_state[key] = {
                        "level": 0,
                        "last_leak": now
                    }
                
                state = self._local_state[key]
                
                # 计算泄漏的令牌
                elapsed = now - state["last_leak"]
                if elapsed > 0:
                    leak_rate = self.config.max_requests / self.config.time_window
                    tokens_leaked = elapsed * leak_rate
                    state["level"] = max(0, state["level"] - tokens_leaked)
                    state["last_leak"] = now
                
                allowed = state["level"] + tokens <= self.config.burst_size
                if allowed:
                    state["level"] += tokens
                
                return {
                    "allowed": allowed,
                    "remaining": int(self.config.burst_size - state["level"]),
                    "limit": self.config.burst_size,
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value
                }
    
    async def _sliding_window_check(self, key: str, tokens: int) -> Dict[str, Any]:
        """滑动窗口算法检查"""
        now = time.time()
        window_start = now - self.config.time_window
        
        if self.distributed:
            lua_script = """
            local key = KEYS[1]
            local window_start = tonumber(ARGV[1])
            local now = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local tokens_requested = tonumber(ARGV[4])
            local ttl = tonumber(ARGV[5])
            
            -- 清理过期的记录
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- 获取当前窗口内的请求数
            local current_requests = redis.call('ZCARD', key)
            
            local allowed = 0
            if current_requests + tokens_requested <= max_requests then
                -- 添加新的请求记录
                for i = 1, tokens_requested do
                    redis.call('ZADD', key, now + i * 0.000001, now .. ':' .. i)
                end
                allowed = 1
            end
            
            redis.call('EXPIRE', key, ttl)
            
            local remaining = math.max(0, max_requests - current_requests - (allowed == 1 and tokens_requested or 0))
            return {allowed, remaining, max_requests}
            """
            
            try:
                ttl = self.config.time_window + 10
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.redis_client.eval(
                        lua_script, 1, key,
                        window_start, now, self.config.max_requests, tokens, ttl
                    )
                )
                
                allowed, remaining, limit = result
                
                return {
                    "allowed": bool(allowed),
                    "remaining": int(remaining),
                    "limit": int(limit),
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value
                }
                
            except Exception as e:
                logger.error(
                    "advanced_rate_limiter.sliding_window.error",
                    key=key,
                    error=str(e)
                )
                return {
                    "allowed": True,
                    "remaining": self.config.max_requests,
                    "limit": self.config.max_requests,
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value,
                    "error": str(e)
                }
        else:
            # 本地滑动窗口实现
            async with self._lock:
                if key not in self._local_state:
                    self._local_state[key] = []
                
                requests = self._local_state[key]
                
                # 清理过期的请求
                requests[:] = [req_time for req_time in requests if req_time > window_start]
                
                allowed = len(requests) + tokens <= self.config.max_requests
                if allowed:
                    for i in range(tokens):
                        requests.append(now + i * 0.000001)
                
                return {
                    "allowed": allowed,
                    "remaining": max(0, self.config.max_requests - len(requests)),
                    "limit": self.config.max_requests,
                    "reset_time": now + self.config.time_window,
                    "strategy": self.config.strategy.value
                }
    
    async def _fixed_window_check(self, key: str, tokens: int) -> Dict[str, Any]:
        """固定窗口算法检查"""
        now = time.time()
        window_start = int(now // self.config.time_window) * self.config.time_window
        window_key = f"{key}:{window_start}"
        
        if self.distributed:
            try:
                # 原子操作：获取当前计数并增加
                current_count = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.redis_client.get(window_key)
                )
                current_count = int(current_count or 0)
                
                allowed = current_count + tokens <= self.config.max_requests
                if allowed:
                    new_count = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.redis_client.incrby(window_key, tokens)
                    )
                    # 设置过期时间
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.redis_client.expire(window_key, self.config.time_window + 10)
                    )
                else:
                    new_count = current_count
                
                remaining = max(0, self.config.max_requests - new_count)
                reset_time = window_start + self.config.time_window
                
                return {
                    "allowed": allowed,
                    "remaining": remaining,
                    "limit": self.config.max_requests,
                    "reset_time": reset_time,
                    "strategy": self.config.strategy.value
                }
                
            except Exception as e:
                logger.error(
                    "advanced_rate_limiter.fixed_window.error",
                    key=key,
                    error=str(e)
                )
                return {
                    "allowed": True,
                    "remaining": self.config.max_requests,
                    "limit": self.config.max_requests,
                    "reset_time": window_start + self.config.time_window,
                    "strategy": self.config.strategy.value,
                    "error": str(e)
                }
        else:
            # 本地固定窗口实现
            async with self._lock:
                if window_key not in self._local_state:
                    self._local_state[window_key] = 0
                
                current_count = self._local_state[window_key]
                allowed = current_count + tokens <= self.config.max_requests
                if allowed:
                    self._local_state[window_key] = current_count + tokens
                    new_count = self._local_state[window_key]
                else:
                    new_count = current_count
                
                return {
                    "allowed": allowed,
                    "remaining": max(0, self.config.max_requests - new_count),
                    "limit": self.config.max_requests,
                    "reset_time": window_start + self.config.time_window,
                    "strategy": self.config.strategy.value
                }
    
    async def wait_if_limited(self, key: str, tokens: int = 1) -> Dict[str, Any]:
        """
        如果被限流则等待，直到允许通过
        
        Args:
            key: 限流键
            tokens: 请求的令牌数量
            
        Returns:
            最终的检查结果
        """
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            result = await self.is_allowed(key, tokens)
            
            if result["allowed"]:
                return result
            
            # 计算等待时间
            if "reset_time" in result:
                wait_time = min(result["reset_time"] - time.time(), self.config.time_window)
            else:
                wait_time = self.config.time_window / self.config.max_requests * tokens
            
            wait_time = max(0.1, wait_time)  # 最少等待0.1秒
            
            logger.info(
                "advanced_rate_limiter.waiting",
                key=key,
                wait_time=wait_time,
                retry_count=retry_count,
                strategy=self.config.strategy.value
            )
            
            await asyncio.sleep(wait_time)
            retry_count += 1
        
        # 达到最大重试次数，返回最后的结果
        logger.warning(
            "advanced_rate_limiter.max_retries_reached",
            key=key,
            max_retries=max_retries
        )
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "strategy": self.config.strategy.value,
            "max_requests": self.config.max_requests,
            "time_window": self.config.time_window,
            "burst_size": self.config.burst_size,
            "distributed": self.distributed,
            "key_prefix": self.config.key_prefix
        }


# 预定义的限流器配置
class RateLimitPresets:
    """预定义的限流器配置"""
    
    # 严格限流：每分钟30个请求，突发5个
    STRICT = RateLimitConfig(
        max_requests=30,
        time_window=60,
        burst_size=5,
        strategy=LimitStrategy.TOKEN_BUCKET
    )
    
    # 中等限流：每分钟60个请求，突发10个
    MODERATE = RateLimitConfig(
        max_requests=60,
        time_window=60,
        burst_size=10,
        strategy=LimitStrategy.TOKEN_BUCKET
    )
    
    # 宽松限流：每分钟120个请求，突发20个
    LENIENT = RateLimitConfig(
        max_requests=120,
        time_window=60,
        burst_size=20,
        strategy=LimitStrategy.TOKEN_BUCKET
    )
    
    # 爬虫专用：每分钟10个请求，平滑输出
    SCRAPING = RateLimitConfig(
        max_requests=10,
        time_window=60,
        burst_size=3,
        strategy=LimitStrategy.LEAKY_BUCKET
    )


# 创建全局限流器实例
def create_rate_limiter(
    preset: RateLimitConfig = RateLimitPresets.MODERATE,
    distributed: bool = True
) -> AdvancedRateLimiter:
    """
    创建限流器实例
    
    Args:
        preset: 预设配置
        distributed: 是否使用分布式模式
        
    Returns:
        配置好的限流器实例
    """
    return AdvancedRateLimiter(preset, distributed=distributed)