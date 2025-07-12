"""Initial database schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-07-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    reporttype = postgresql.ENUM('QUARTERLY', 'SEMI_ANNUAL', 'ANNUAL', name='reporttype')
    reporttype.create(op.get_bind())
    
    taskstatus = postgresql.ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRYING', name='taskstatus')
    taskstatus.create(op.get_bind())
    
    # Create funds table
    op.create_table('funds',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_code', sa.String(length=10), nullable=False),
        sa.Column('fund_name', sa.String(length=100), nullable=False),
        sa.Column('fund_type', sa.String(length=50), nullable=True),
        sa.Column('management_company', sa.String(length=100), nullable=True),
        sa.Column('establishment_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_code')
    )
    op.create_index('idx_fund_code', 'funds', ['fund_code'], unique=False)
    op.create_index('idx_fund_name', 'funds', ['fund_name'], unique=False)
    
    # Create fund_reports table
    op.create_table('fund_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_date', sa.DateTime(), nullable=False),
        sa.Column('report_type', reporttype, nullable=False),
        sa.Column('report_year', sa.Integer(), nullable=False),
        sa.Column('report_period', sa.String(length=20), nullable=True),
        sa.Column('net_asset_value', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('total_shares', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('unit_nav', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('accumulated_nav', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('original_file_url', sa.Text(), nullable=True),
        sa.Column('original_file_path', sa.String(length=500), nullable=True),
        sa.Column('file_type', sa.String(length=10), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('is_parsed', sa.Boolean(), nullable=True),
        sa.Column('parsed_at', sa.DateTime(), nullable=True),
        sa.Column('parse_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_fund_report', 'fund_reports', ['fund_id', 'report_date'], unique=False)
    op.create_index('idx_report_date', 'fund_reports', ['report_date'], unique=False)
    op.create_index('idx_report_type', 'fund_reports', ['report_type'], unique=False)
    op.create_constraint('uq_fund_report', 'fund_reports', ['fund_id', 'report_date', 'report_type'], type_='unique')
    
    # Create asset_allocations table
    op.create_table('asset_allocations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stock_investments', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('stock_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('bond_investments', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('bond_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('fund_investments', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('fund_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('cash_and_equivalents', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('cash_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('other_investments', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('other_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('extended_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['fund_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_asset_report', 'asset_allocations', ['report_id'], unique=False)
    
    # Create top_holdings table
    op.create_table('top_holdings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(length=10), nullable=False),
        sa.Column('stock_name', sa.String(length=100), nullable=False),
        sa.Column('shares_held', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('market_value', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('portfolio_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['fund_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_holding_rank', 'top_holdings', ['report_id', 'rank'], unique=False)
    op.create_index('idx_holding_report', 'top_holdings', ['report_id'], unique=False)
    op.create_index('idx_stock_code', 'top_holdings', ['stock_code'], unique=False)
    
    # Create industry_allocations table
    op.create_table('industry_allocations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('industry_name', sa.String(length=100), nullable=False),
        sa.Column('industry_code', sa.String(length=20), nullable=True),
        sa.Column('market_value', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('portfolio_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['fund_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_industry_name', 'industry_allocations', ['industry_name'], unique=False)
    op.create_index('idx_industry_report', 'industry_allocations', ['report_id'], unique=False)
    
    # Create scraping_tasks table
    op.create_table('scraping_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_name', sa.String(length=200), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('status', taskstatus, nullable=True),
        sa.Column('target_year', sa.Integer(), nullable=True),
        sa.Column('target_report_type', reporttype, nullable=True),
        sa.Column('fund_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_reports', sa.Integer(), nullable=True),
        sa.Column('processed_reports', sa.Integer(), nullable=True),
        sa.Column('failed_reports', sa.Integer(), nullable=True),
        sa.Column('execution_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_task_created', 'scraping_tasks', ['created_at'], unique=False)
    op.create_index('idx_task_status', 'scraping_tasks', ['status'], unique=False)
    op.create_index('idx_task_type', 'scraping_tasks', ['task_type'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('scraping_tasks')
    op.drop_table('industry_allocations')
    op.drop_table('top_holdings')
    op.drop_table('asset_allocations')
    op.drop_table('fund_reports')
    op.drop_table('funds')
    
    # Drop enum types
    reporttype = postgresql.ENUM('QUARTERLY', 'SEMI_ANNUAL', 'ANNUAL', name='reporttype')
    reporttype.drop(op.get_bind())
    
    taskstatus = postgresql.ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRYING', name='taskstatus')
    taskstatus.drop(op.get_bind())