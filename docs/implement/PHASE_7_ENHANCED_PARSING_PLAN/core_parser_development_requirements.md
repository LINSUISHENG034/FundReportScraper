# 基金报告核心解析器开发需求文档

## 项目概述

基于对真实XBRL报告样本的深入分析，开发一个高质量、可维护的基金报告解析器系统，实现从CSRC电子化信息披露平台获取的XBRL格式报告中提取结构化数据，为后续的投资分析、风险管理和基金评估提供可靠的数据基础。

## 需求范围

本需求文档涵盖**核心解析器开发**和**数据质量和完整性**两个核心模块，为项目的基础建设阶段提供完整的技术规范。

## 技术栈要求

### 核心技术栈
- **Python 3.9+**：主要开发语言
- **专业XBRL库**：
  - `python-xbrl` 或 `arelle`：专业XBRL文档解析
  - `xbrl-parser`：轻量级XBRL解析工具
- **HTML解析**：`BeautifulSoup4` + `lxml`
- **数据处理**：`pandas` + `numpy`
- **数据库**：`PostgreSQL` + `SQLAlchemy`
- **异步处理**：`asyncio` + `aiohttp`

### 智能解析增强
- **Ollama + 本地LLM**：
  - 模型选择：`llama3.1:8b` 或 `qwen2.5:7b`
  - 用途：复杂表格结构识别、数据验证、异常处理
  - 集成方式：通过 `ollama-python` 客户端

### 数据质量保证
- **数据验证**：`pydantic` + `cerberus`
- **日志系统**：`structlog` + `loguru`
- **监控告警**：`prometheus-client`
- **测试框架**：`pytest` + `pytest-asyncio`

## 核心功能需求

### 1. 多格式XBRL解析器

#### 1.1 基础解析能力
```python
class XBRLReportParser:
    """XBRL报告解析器基类"""
    
    def __init__(self, use_llm_assist: bool = True):
        self.xbrl_parser = None  # 专业XBRL库解析器
        self.html_parser = None  # HTML结构解析器
        self.llm_assistant = None  # LLM辅助解析器
    
    def parse_report(self, file_path: str, report_metadata: Dict) -> ParsedReport:
        """解析完整报告"""
        pass
    
    def extract_xbrl_facts(self, xbrl_content: bytes) -> Dict:
        """提取XBRL标准化事实数据"""
        pass
    
    def parse_html_tables(self, html_content: str) -> List[TableData]:
        """解析HTML表格数据"""
        pass
```

#### 1.2 报告类型适配
- **年度报告（ANNUAL）**：完整数据结构解析
- **季度报告（Q1/Q2/Q3/Q4）**：简化数据结构适配
- **半年报（SEMI_ANNUAL）**：中等复杂度处理
- **基金概况（FUND_PROFILE）**：基本信息提取

### 2. 智能数据提取模块

#### 2.1 资产配置数据提取
```python
class AssetAllocationExtractor:
    """资产配置数据提取器"""
    
    def extract_asset_composition(self, parsed_data: Dict) -> List[AssetAllocation]:
        """提取基金资产组合情况"""
        # 股票投资、债券投资、基金投资、银行存款等
        pass
    
    def extract_allocation_changes(self, current_data: Dict, previous_data: Dict) -> List[AllocationChange]:
        """提取资产配置变化"""
        pass
```

#### 2.2 持仓明细数据提取
```python
class HoldingDetailsExtractor:
    """持仓明细数据提取器"""
    
    def extract_stock_holdings(self, parsed_data: Dict) -> List[StockHolding]:
        """提取股票持仓明细"""
        # 按行业分类、前十大重仓股、港股通投资等
        pass
    
    def extract_bond_holdings(self, parsed_data: Dict) -> List[BondHolding]:
        """提取债券持仓明细"""
        # 按品种分类、前五大债券、信用评级分布等
        pass
    
    def extract_trading_records(self, parsed_data: Dict) -> List[TradingRecord]:
        """提取交易记录"""
        # 重大买入卖出、换手率等
        pass
```

#### 2.3 财务指标数据提取
```python
class FinancialMetricsExtractor:
    """财务指标数据提取器"""
    
    def extract_investment_income(self, parsed_data: Dict) -> List[InvestmentIncome]:
        """提取投资收益数据"""
        pass
    
    def extract_fee_structure(self, parsed_data: Dict) -> List[FeeStructure]:
        """提取费用结构数据"""
        pass
```

### 3. LLM辅助解析系统

#### 3.1 复杂结构识别
```python
class LLMAssistedParser:
    """LLM辅助解析器"""
    
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.ollama_client = ollama.Client()
        self.model_name = model_name
    
    def identify_table_structure(self, html_table: str) -> TableStructure:
        """识别复杂表格结构"""
        prompt = self._build_table_analysis_prompt(html_table)
        response = self.ollama_client.generate(model=self.model_name, prompt=prompt)
        return self._parse_structure_response(response)
    
    def validate_extracted_data(self, data: Dict, context: str) -> ValidationResult:
        """验证提取数据的合理性"""
        pass
    
    def handle_parsing_exceptions(self, error_context: str, html_snippet: str) -> ParseSuggestion:
        """处理解析异常情况"""
        pass
```

#### 3.2 数据验证增强
```python
class IntelligentDataValidator:
    """智能数据验证器"""
    
    def validate_asset_allocation_consistency(self, allocations: List[AssetAllocation]) -> ValidationReport:
        """验证资产配置数据一致性"""
        # 使用LLM验证比例总和、逻辑关系等
        pass
    
    def detect_anomalous_values(self, financial_data: List[FinancialMetric]) -> List[Anomaly]:
        """检测异常数值"""
        pass
```

## 数据质量保证体系

### 1. 多层次数据验证

#### 1.1 结构验证
```python
from pydantic import BaseModel, validator
from typing import List, Optional
from decimal import Decimal

class AssetAllocation(BaseModel):
    """资产配置数据模型"""
    asset_type: str
    market_value: Decimal
    net_value_ratio: Decimal
    
    @validator('net_value_ratio')
    def validate_ratio(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('净值比例必须在0-1之间')
        return v

class StockHolding(BaseModel):
    """股票持仓数据模型"""
    stock_code: str
    stock_name: str
    shares_held: int
    market_value: Decimal
    net_value_ratio: Decimal
    
    @validator('stock_code')
    def validate_stock_code(cls, v):
        # 验证股票代码格式
        import re
        if not re.match(r'^\d{6}$', v):
            raise ValueError('股票代码格式错误')
        return v
```

#### 1.2 业务逻辑验证
```python
class BusinessLogicValidator:
    """业务逻辑验证器"""
    
    def validate_allocation_sum(self, allocations: List[AssetAllocation]) -> bool:
        """验证资产配置比例总和"""
        total_ratio = sum(a.net_value_ratio for a in allocations)
        return abs(total_ratio - 1.0) < 0.01  # 允许1%的误差
    
    def validate_holding_consistency(self, holdings: List[StockHolding], total_stock_value: Decimal) -> bool:
        """验证持仓明细与总值的一致性"""
        holdings_sum = sum(h.market_value for h in holdings)
        return abs(holdings_sum - total_stock_value) / total_stock_value < 0.05
    
    def validate_temporal_consistency(self, current_data: Dict, previous_data: Dict) -> List[str]:
        """验证时间序列数据一致性"""
        inconsistencies = []
        # 检查基金规模变化的合理性
        # 检查持仓变化的合理性
        return inconsistencies
```

### 2. 异常处理和恢复机制

#### 2.1 解析异常处理
```python
class ParsingExceptionHandler:
    """解析异常处理器"""
    
    def handle_table_parsing_error(self, table_html: str, error: Exception) -> Optional[List[Dict]]:
        """处理表格解析错误"""
        try:
            # 尝试LLM辅助解析
            return self.llm_assistant.parse_problematic_table(table_html)
        except Exception as llm_error:
            # 记录错误并返回部分数据
            logger.error(f"LLM辅助解析也失败: {llm_error}")
            return self._extract_partial_data(table_html)
    
    def handle_data_format_error(self, raw_value: str, expected_type: type) -> Any:
        """处理数据格式错误"""
        # 尝试多种格式转换方法
        # 使用LLM理解和转换复杂格式
        pass
```

#### 2.2 数据修复机制
```python
class DataRepairService:
    """数据修复服务"""
    
    def repair_missing_values(self, incomplete_data: Dict) -> Dict:
        """修复缺失值"""
        # 基于历史数据推断
        # 基于同类基金数据推断
        # LLM辅助推理
        pass
    
    def repair_inconsistent_data(self, inconsistent_data: Dict) -> Dict:
        """修复不一致数据"""
        pass
```

### 3. 数据质量监控

#### 3.1 质量指标定义
```python
class DataQualityMetrics:
    """数据质量指标"""
    
    def calculate_completeness_score(self, parsed_data: Dict) -> float:
        """计算数据完整性得分"""
        required_fields = self._get_required_fields(parsed_data['report_type'])
        present_fields = self._count_present_fields(parsed_data)
        return present_fields / len(required_fields)
    
    def calculate_accuracy_score(self, parsed_data: Dict) -> float:
        """计算数据准确性得分"""
        # 基于业务规则验证
        # 基于历史数据对比
        pass
    
    def calculate_consistency_score(self, parsed_data: Dict) -> float:
        """计算数据一致性得分"""
        pass
```

#### 3.2 实时监控系统
```python
class QualityMonitoringService:
    """质量监控服务"""
    
    def monitor_parsing_success_rate(self) -> Dict:
        """监控解析成功率"""
        pass
    
    def monitor_data_quality_trends(self) -> Dict:
        """监控数据质量趋势"""
        pass
    
    def generate_quality_alerts(self) -> List[Alert]:
        """生成质量告警"""
        pass
```

## 性能要求

### 1. 解析性能指标
- **单个报告解析时间**：< 30秒（年报），< 10秒（季报）
- **批量处理能力**：> 100个报告/小时
- **内存使用**：< 2GB（单个解析进程）
- **CPU使用率**：< 80%（多进程并行）

### 2. 数据质量指标
- **解析成功率**：> 95%
- **数据完整性**：> 90%（核心字段）
- **数据准确性**：> 98%（数值型数据）
- **异常检测率**：< 5%（误报率）

## 交付物要求

### 1. 代码结构
```
src/
├── parsers/
│   ├── __init__.py
│   ├── base_parser.py
│   ├── xbrl_parser.py
│   ├── html_parser.py
│   ├── llm_assistant.py
│   └── extractors/
│       ├── asset_allocation_extractor.py
│       ├── holding_extractor.py
│       └── financial_metrics_extractor.py
├── models/
│   ├── __init__.py
│   ├── data_models.py
│   └── validation_models.py
├── quality/
│   ├── __init__.py
│   ├── validators.py
│   ├── exception_handlers.py
│   ├── repair_service.py
│   └── monitoring.py
└── utils/
    ├── __init__.py
    ├── data_cleaning.py
    └── format_converters.py
```

### 2. 配置文件
- **解析器配置**：字段映射、验证规则
- **LLM配置**：模型参数、提示模板
- **质量阈值配置**：各类质量指标的阈值设置

### 3. 测试用例
- **单元测试**：覆盖率 > 90%
- **集成测试**：端到端解析流程测试
- **性能测试**：大批量数据处理测试
- **质量测试**：数据质量验证测试

### 4. 文档交付
- **API文档**：详细的接口说明
- **配置文档**：配置项说明和示例
- **部署文档**：环境要求和部署步骤
- **运维文档**：监控指标和故障处理

## 验收标准

1. **功能完整性**：能够解析所有类型的XBRL报告
2. **数据质量**：满足上述质量指标要求
3. **性能达标**：满足性能指标要求
4. **代码质量**：通过代码审查，符合编码规范
5. **测试覆盖**：通过所有测试用例
6. **文档完整**：提供完整的技术文档

## 风险控制

1. **技术风险**：XBRL格式变化、LLM服务不稳定
2. **质量风险**：数据解析错误、业务逻辑验证不足
3. **性能风险**：大批量处理性能瓶颈
4. **维护风险**：代码复杂度过高、依赖库版本冲突

## 项目里程碑

- **Week 1-2**：技术栈搭建和基础框架开发
- **Week 3-4**：核心解析器开发和LLM集成
- **Week 5-6**：数据质量保证体系实现
- **Week 7-8**：性能优化和测试完善
- **Week 9-10**：文档编写和交付准备

## 参考文档

本需求文档基于以下分析文档制定，开发团队应详细阅读：

1. **数据库设计方案**：`reference/development_docs/database_schema_design.sql`
   - 完整的数据库表结构设计
   - 索引策略和性能优化方案
   - 数据关系和约束定义

2. **解析器架构设计**：`reference/development_docs/parser_architecture_design.md`
   - 模块化解析器架构详细说明
   - 各组件的职责和接口定义
   - 扩展性和维护性设计原则

3. **数据分析框架**：`reference/development_docs/data_analysis_framework.md`
   - 数据价值最大化策略
   - 分析模块设计和实现方案
   - 可视化和API接口规范

4. **XBRL报告样本**：`tests/fixtures/`目录
   - 真实的基金报告样本文件
   - 不同报告类型的结构差异
   - 数据提取的重点和难点

## 开发指导原则

1. **数据驱动**：基于真实样本数据设计解析逻辑
2. **质量优先**：确保数据准确性和完整性
3. **可扩展性**：支持新报告类型和数据字段的扩展
4. **智能化**：充分利用LLM提升解析准确性
5. **监控完善**：建立全面的质量监控和告警机制
