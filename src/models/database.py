"""数据库连接和会话管理模块"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.models.fund_data import Base


class DatabaseManager:
    """数据库管理器
    
    提供同步和异步数据库连接管理功能
    """
    
    def __init__(self):
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None
        self._initialized = False
    
    def initialize(self):
        """初始化数据库连接"""
        if self._initialized:
            return
            
        # 同步引擎
        self._engine = create_engine(
            settings.database.url,
            poolclass=StaticPool if "sqlite" in settings.database.url else None,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database.url else {},
            echo=False
        )
        
        # 异步引擎（如果支持）
        if not settings.database.url.startswith("sqlite"):
            async_url = settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
            self._async_engine = create_async_engine(
                async_url,
                echo=False
            )
            self._async_session_factory = async_sessionmaker(
                self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        
        # 同步会话工厂
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False
        )
        
        self._initialized = True
    
    def create_tables(self):
        """创建所有表"""
        if not self._initialized:
            self.initialize()
        Base.metadata.create_all(bind=self._engine)
    
    def get_session(self) -> Session:
        """获取同步数据库会话"""
        if not self._initialized:
            self.initialize()
        return self._session_factory()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取异步数据库会话（上下文管理器）"""
        if not self._initialized:
            self.initialize()
            
        if self._async_session_factory is None:
            raise RuntimeError("异步数据库连接不可用，请使用 PostgreSQL")
            
        async with self._async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def get_async_session_simple(self) -> AsyncSession:
        """获取简单的异步数据库会话（需要手动管理）"""
        if not self._initialized:
            self.initialize()
            
        if self._async_session_factory is None:
            raise RuntimeError("异步数据库连接不可用，请使用 PostgreSQL")
            
        return self._async_session_factory()
    
    def close(self):
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
        if self._async_engine:
            asyncio.create_task(self._async_engine.aclose())
        self._initialized = False
    
    @property
    def engine(self):
        """获取同步数据库引擎"""
        if not self._initialized:
            self.initialize()
        return self._engine
    
    @property
    def async_engine(self):
        """获取异步数据库引擎"""
        if not self._initialized:
            self.initialize()
        return self._async_engine


# 全局数据库管理器实例
db_manager = DatabaseManager()


def get_db_session() -> Session:
    """获取数据库会话（依赖注入用）"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（依赖注入用）"""
    async with db_manager.get_async_session() as session:
        yield session


# 导出 Base 以供 migrations 使用
__all__ = ["Base", "DatabaseManager", "db_manager", "get_db_session", "get_async_db_session"]