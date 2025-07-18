"""添加质量监控表

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库结构"""
    
    # 为fund_reports表添加质量监控字段
    op.add_column('fund_reports', sa.Column('parsing_method', sa.String(50), nullable=True))
    op.add_column('fund_reports', sa.Column('parsing_confidence', sa.Float, nullable=True))
    op.add_column('fund_reports', sa.Column('data_quality_score', sa.Float, nullable=True))
    op.add_column('fund_reports', sa.Column('validation_status', sa.String(20), nullable=True))
    op.add_column('fund_reports', sa.Column('llm_assisted', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('fund_reports', sa.Column('parsing_metadata', postgresql.JSON, nullable=True))
    op.add_column('fund_reports', sa.Column('validation_issues', postgresql.JSON, nullable=True))
    op.add_column('fund_reports', sa.Column('data_completeness', postgresql.JSON, nullable=True))
    
    # 创建质量指标表
    op.create_table(
        'quality_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('fund_code', sa.String(20), nullable=False, index=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('parsing_time', sa.Float, nullable=False),
        sa.Column('success_rate', sa.Float, nullable=False),
        sa.Column('completeness_score', sa.Float, nullable=False),
        sa.Column('accuracy_score', sa.Float, nullable=False),
        sa.Column('consistency_score', sa.Float, nullable=False),
        sa.Column('timeliness_score', sa.Float, nullable=False),
        sa.Column('overall_score', sa.Float, nullable=False),
        sa.Column('issues_count', sa.Integer, nullable=False, default=0),
        sa.Column('warnings_count', sa.Integer, nullable=False, default=0),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # 创建质量指标索引
    op.create_index('idx_quality_metrics_fund_time', 'quality_metrics', ['fund_code', 'timestamp'])
    op.create_index('idx_quality_metrics_score', 'quality_metrics', ['overall_score'])
    op.create_index('idx_quality_metrics_timestamp', 'quality_metrics', ['timestamp'])
    
    # 创建解析任务表
    op.create_table(
        'parsing_tasks',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('fund_code', sa.String(20), nullable=False, index=True),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='PENDING'),  # PENDING, PROCESSING, COMPLETED, FAILED
        sa.Column('parsing_method', sa.String(50), nullable=True),
        sa.Column('llm_assisted', sa.Boolean, nullable=False, default=False),
        sa.Column('start_time', sa.DateTime, nullable=True),
        sa.Column('end_time', sa.DateTime, nullable=True),
        sa.Column('parsing_time', sa.Float, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('result_metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # 创建解析任务索引
    op.create_index('idx_parsing_tasks_status', 'parsing_tasks', ['status'])
    op.create_index('idx_parsing_tasks_fund_time', 'parsing_tasks', ['fund_code', 'created_at'])
    
    # 创建数据质量告警表
    op.create_table(
        'quality_alerts',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('alert_type', sa.String(50), nullable=False),  # SUCCESS_RATE, QUALITY_SCORE, PARSING_TIME
        sa.Column('severity', sa.String(20), nullable=False),  # LOW, MEDIUM, HIGH, CRITICAL
        sa.Column('fund_code', sa.String(20), nullable=True, index=True),
        sa.Column('threshold_value', sa.Float, nullable=False),
        sa.Column('actual_value', sa.Float, nullable=False),
        sa.Column('alert_message', sa.Text, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='ACTIVE'),  # ACTIVE, RESOLVED, IGNORED
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # 创建质量告警索引
    op.create_index('idx_quality_alerts_type_status', 'quality_alerts', ['alert_type', 'status'])
    op.create_index('idx_quality_alerts_severity', 'quality_alerts', ['severity'])
    op.create_index('idx_quality_alerts_created', 'quality_alerts', ['created_at'])
    
    # 创建LLM使用统计表
    op.create_table(
        'llm_usage_stats',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('model_name', sa.String(50), nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=False),  # TABLE_ANALYSIS, DATA_EXTRACTION, VALIDATION, REPAIR
        sa.Column('fund_code', sa.String(20), nullable=True, index=True),
        sa.Column('input_tokens', sa.Integer, nullable=True),
        sa.Column('output_tokens', sa.Integer, nullable=True),
        sa.Column('processing_time', sa.Float, nullable=False),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    
    # 创建LLM使用统计索引
    op.create_index('idx_llm_usage_model_operation', 'llm_usage_stats', ['model_name', 'operation_type'])
    op.create_index('idx_llm_usage_success', 'llm_usage_stats', ['success'])
    op.create_index('idx_llm_usage_created', 'llm_usage_stats', ['created_at'])
    
    # 为现有表添加新的索引以支持质量监控查询
    op.create_index('idx_fund_reports_quality', 'fund_reports', ['data_quality_score', 'parsing_confidence'])
    op.create_index('idx_fund_reports_validation', 'fund_reports', ['validation_status'])
    op.create_index('idx_fund_reports_llm', 'fund_reports', ['llm_assisted'])


def downgrade():
    """降级数据库结构"""
    
    # 删除新增的索引
    op.drop_index('idx_fund_reports_llm')
    op.drop_index('idx_fund_reports_validation')
    op.drop_index('idx_fund_reports_quality')
    
    # 删除LLM使用统计表
    op.drop_index('idx_llm_usage_created')
    op.drop_index('idx_llm_usage_success')
    op.drop_index('idx_llm_usage_model_operation')
    op.drop_table('llm_usage_stats')
    
    # 删除质量告警表
    op.drop_index('idx_quality_alerts_created')
    op.drop_index('idx_quality_alerts_severity')
    op.drop_index('idx_quality_alerts_type_status')
    op.drop_table('quality_alerts')
    
    # 删除解析任务表
    op.drop_index('idx_parsing_tasks_fund_time')
    op.drop_index('idx_parsing_tasks_status')
    op.drop_table('parsing_tasks')
    
    # 删除质量指标表
    op.drop_index('idx_quality_metrics_timestamp')
    op.drop_index('idx_quality_metrics_score')
    op.drop_index('idx_quality_metrics_fund_time')
    op.drop_table('quality_metrics')
    
    # 删除fund_reports表的新增字段
    op.drop_column('fund_reports', 'data_completeness')
    op.drop_column('fund_reports', 'validation_issues')
    op.drop_column('fund_reports', 'parsing_metadata')
    op.drop_column('fund_reports', 'llm_assisted')
    op.drop_column('fund_reports', 'validation_status')
    op.drop_column('fund_reports', 'data_quality_score')
    op.drop_column('fund_reports', 'parsing_confidence')
    op.drop_column('fund_reports', 'parsing_method')