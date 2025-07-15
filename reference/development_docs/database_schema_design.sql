-- 基金报告数据库设计方案
-- 基于XBRL报告样本分析，设计支持多维度投资分析的数据库结构

-- 1. 基金基本信息表
CREATE TABLE funds (
    fund_code VARCHAR(20) PRIMARY KEY,
    fund_name VARCHAR(200) NOT NULL,
    fund_type VARCHAR(50),
    management_company VARCHAR(100),
    custodian_bank VARCHAR(100),
    inception_date DATE,
    benchmark TEXT,
    investment_objective TEXT,
    investment_strategy TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 报告元数据表
CREATE TABLE reports (
    report_id VARCHAR(50) PRIMARY KEY,
    fund_code VARCHAR(20) REFERENCES funds(fund_code),
    report_type VARCHAR(20) NOT NULL, -- ANNUAL, Q1, Q2, Q3, SEMI_ANNUAL, FUND_PROFILE
    report_period DATE NOT NULL,
    report_date DATE NOT NULL,
    upload_date DATE,
    file_path VARCHAR(500),
    parsing_status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, SUCCESS, FAILED
    parsing_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 资产配置表
CREATE TABLE asset_allocations (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    asset_type VARCHAR(50) NOT NULL, -- 股票投资, 债券投资, 基金投资, 银行存款等
    asset_subtype VARCHAR(50), -- 境内股票, 港股通, 国债, 企业债等
    market_value DECIMAL(20,2),
    net_value_ratio DECIMAL(8,4), -- 占基金资产净值比例
    previous_period_value DECIMAL(20,2),
    change_amount DECIMAL(20,2),
    change_ratio DECIMAL(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 股票持仓明细表
CREATE TABLE stock_holdings (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    industry_code VARCHAR(20),
    industry_name VARCHAR(100),
    shares_held BIGINT,
    market_value DECIMAL(20,2),
    net_value_ratio DECIMAL(8,4),
    rank_by_value INTEGER,
    is_restricted BOOLEAN DEFAULT FALSE, -- 是否存在流通受限
    restriction_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 债券持仓明细表
CREATE TABLE bond_holdings (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    bond_code VARCHAR(20) NOT NULL,
    bond_name VARCHAR(200),
    bond_type VARCHAR(50), -- 国债, 企业债, 可转债等
    credit_rating VARCHAR(10),
    face_value DECIMAL(20,2),
    market_value DECIMAL(20,2),
    net_value_ratio DECIMAL(8,4),
    rank_by_value INTEGER,
    maturity_date DATE,
    coupon_rate DECIMAL(6,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. 基金投资明细表（FOF基金）
CREATE TABLE fund_holdings (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    target_fund_code VARCHAR(20),
    target_fund_name VARCHAR(200),
    target_fund_type VARCHAR(50),
    shares_held BIGINT,
    market_value DECIMAL(20,2),
    net_value_ratio DECIMAL(8,4),
    rank_by_value INTEGER,
    management_fee_rate DECIMAL(6,4),
    custodian_fee_rate DECIMAL(6,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 交易活动记录表
CREATE TABLE trading_activities (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    security_code VARCHAR(20) NOT NULL,
    security_name VARCHAR(200),
    security_type VARCHAR(20), -- STOCK, BOND, FUND
    transaction_type VARCHAR(20), -- BUY, SELL
    transaction_amount DECIMAL(20,2), -- 交易金额
    transaction_volume BIGINT, -- 交易数量
    period_start DATE,
    period_end DATE,
    rank_by_amount INTEGER, -- 按交易金额排名
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. 财务指标表
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    metric_category VARCHAR(50), -- 投资收益, 公允价值变动, 费用等
    metric_type VARCHAR(100), -- 具体指标名称
    current_period_value DECIMAL(20,2),
    previous_period_value DECIMAL(20,2),
    change_amount DECIMAL(20,2),
    change_ratio DECIMAL(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. 风险指标表
CREATE TABLE risk_indicators (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    risk_category VARCHAR(50), -- 信用风险, 流动性风险, 市场风险
    indicator_name VARCHAR(100),
    indicator_value DECIMAL(20,2),
    indicator_ratio DECIMAL(8,4),
    risk_level VARCHAR(20), -- HIGH, MEDIUM, LOW
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. 业绩归因表
CREATE TABLE performance_attribution (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(50) REFERENCES reports(report_id),
    attribution_type VARCHAR(50), -- 资产配置, 行业配置, 个股选择
    attribution_category VARCHAR(100),
    contribution_value DECIMAL(20,2),
    attribution_ratio DECIMAL(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引设计
CREATE INDEX idx_reports_fund_period ON reports(fund_code, report_period);
CREATE INDEX idx_reports_type_period ON reports(report_type, report_period);
CREATE INDEX idx_asset_allocations_report ON asset_allocations(report_id, asset_type);
CREATE INDEX idx_stock_holdings_report ON stock_holdings(report_id, rank_by_value);
CREATE INDEX idx_bond_holdings_report ON bond_holdings(report_id, rank_by_value);
CREATE INDEX idx_trading_activities_report ON trading_activities(report_id, transaction_type);
CREATE INDEX idx_financial_metrics_report ON financial_metrics(report_id, metric_category);

-- 视图：基金最新报告概览
CREATE VIEW fund_latest_reports AS
SELECT DISTINCT ON (f.fund_code) 
    f.fund_code,
    f.fund_name,
    f.management_company,
    r.report_type,
    r.report_period,
    r.report_date
FROM funds f
JOIN reports r ON f.fund_code = r.fund_code
WHERE r.parsing_status = 'SUCCESS'
ORDER BY f.fund_code, r.report_period DESC;
