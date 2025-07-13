"""
Configuration management for the fund report scraper.
Loads settings from environment variables and provides typed configuration.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(default="sqlite:///./fund_reports.db")
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="fund_reports")
    user: str = Field(default="fund_user")
    password: str = Field(default="fund_password")
    
    class Config:
        env_prefix = "DATABASE_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    url: str = Field(default="redis://localhost:6379/0")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    
    class Config:
        env_prefix = "REDIS_"


class MinIOSettings(BaseSettings):
    """MinIO object storage settings."""
    
    endpoint: str = Field(default="localhost:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    bucket_name: str = Field(default="fund-reports")
    secure: bool = Field(default=False)
    
    class Config:
        env_prefix = "MINIO_"


class CelerySettings(BaseSettings):
    """Celery task queue settings."""
    
    broker_url: str = Field(default="redis://localhost:6379/0")
    result_backend: str = Field(default="redis://localhost:6379/0")
    
    class Config:
        env_prefix = "CELERY_"


class ScraperSettings(BaseSettings):
    """Web scraper configuration settings."""
    
    user_agent: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    request_delay: float = Field(default=1.0)
    max_retries: int = Field(default=3)
    timeout: int = Field(default=30)
    
    class Config:
        env_prefix = "SCRAPER_"


class TargetSettings(BaseSettings):
    """Target website configuration."""
    
    base_url: str = Field(default="https://www.eid.csrc.gov.cn")
    search_url: str = Field(default="https://www.eid.csrc.gov.cn/eid/fund/fundList")
    
    class Config:
        env_prefix = "TARGET_"


class AppSettings(BaseSettings):
    """Application configuration settings."""
    
    name: str = Field(default="FundReportScraper")
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    target: TargetSettings = Field(default_factory=TargetSettings)
    
    class Config:
        env_prefix = "APP_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings(
        database=DatabaseSettings(),
        redis=RedisSettings(),
        minio=MinIOSettings(),
        celery=CelerySettings(),
        scraper=ScraperSettings(),
        target=TargetSettings(),
    )


# Global settings instance
settings = get_settings()