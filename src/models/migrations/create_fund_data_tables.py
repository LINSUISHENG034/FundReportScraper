"""
创建基金数据表的迁移脚本
Migration script to create fund data tables

手动迁移脚本，用于创建Phase 4的核心数据表
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.logging import get_logger
from src.models.fund_data import Base, create_fund_data_tables

logger = get_logger(__name__)


def create_fund_data_migration(db_url: str = "sqlite:///fund_reports.db"):
    """
    执行基金数据表创建迁移
    Execute fund data tables creation migration
    """
    bound_logger = logger.bind(db_url=db_url)
    bound_logger.info("migration.fund_data.start")
    
    try:
        # 创建数据库引擎
        engine = create_engine(db_url, echo=True)
        
        # 创建所有表
        create_fund_data_tables(engine)
        
        # 验证表是否创建成功
        with engine.connect() as conn:
            # 检查表是否存在
            tables_to_check = ['fund_reports', 'asset_allocations', 'top_holdings', 'industry_allocations']
            
            for table_name in tables_to_check:
                if db_url.startswith('sqlite'):
                    result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                else:
                    result = conn.execute(text(f"SELECT table_name FROM information_schema.tables WHERE table_name='{table_name}'"))
                
                if result.fetchone():
                    bound_logger.info(f"migration.fund_data.table_created", table=table_name)
                else:
                    raise Exception(f"Table {table_name} was not created")
        
        bound_logger.info("migration.fund_data.success")
        return True
        
    except Exception as e:
        bound_logger.error(
            "migration.fund_data.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise


def get_table_info(db_url: str = "sqlite:///fund_reports.db"):
    """
    获取表结构信息
    Get table structure information
    """
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        if db_url.startswith('sqlite'):
            # SQLite查询
            tables_info = {}
            
            # 获取所有表名
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            
            for table in tables:
                if table.startswith('fund_') or table.startswith('asset_') or table.startswith('top_') or table.startswith('industry_'):
                    # 获取表结构
                    result = conn.execute(text(f"PRAGMA table_info({table})"))
                    columns = []
                    for row in result.fetchall():
                        columns.append({
                            'name': row[1],
                            'type': row[2],
                            'nullable': not row[3],
                            'primary_key': bool(row[5])
                        })
                    tables_info[table] = columns
            
            return tables_info
        else:
            # 其他数据库的查询逻辑
            pass


def verify_migration(db_url: str = "sqlite:///fund_reports.db"):
    """
    验证迁移是否成功
    Verify migration success
    """
    bound_logger = logger.bind(db_url=db_url)
    bound_logger.info("migration.fund_data.verify.start")
    
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            # 尝试导入模型
            from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
            
            # 验证每个表是否可以查询
            models_to_test = [
                ('fund_reports', FundReport),
                ('asset_allocations', AssetAllocation), 
                ('top_holdings', TopHolding),
                ('industry_allocations', IndustryAllocation)
            ]
            
            for table_name, model_class in models_to_test:
                try:
                    count = session.query(model_class).count()
                    bound_logger.info(
                        "migration.fund_data.verify.table_ok",
                        table=table_name,
                        count=count
                    )
                except Exception as e:
                    bound_logger.error(
                        "migration.fund_data.verify.table_error",
                        table=table_name,
                        error=str(e)
                    )
                    raise
        
        bound_logger.info("migration.fund_data.verify.success")
        return True
        
    except Exception as e:
        bound_logger.error(
            "migration.fund_data.verify.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise


if __name__ == "__main__":
    # 执行迁移
    print("🔄 开始创建基金数据表...")
    
    try:
        # 创建表
        create_fund_data_migration()
        print("✅ 基金数据表创建成功")
        
        # 验证迁移
        verify_migration()
        print("✅ 迁移验证成功")
        
        # 显示表信息
        tables_info = get_table_info()
        print("\n📊 创建的表结构:")
        for table_name, columns in tables_info.items():
            print(f"\n🔹 {table_name}:")
            for col in columns:
                pk_mark = " (PK)" if col['primary_key'] else ""
                null_mark = " NULL" if col['nullable'] else " NOT NULL"
                print(f"  - {col['name']}: {col['type']}{null_mark}{pk_mark}")
        
        print("\n🎉 Phase 4 步骤1完成：核心数据模型已创建！")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
