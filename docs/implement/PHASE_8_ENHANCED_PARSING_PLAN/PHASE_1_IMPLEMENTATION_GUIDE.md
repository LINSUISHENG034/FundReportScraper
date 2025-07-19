# 解析器重构 - 阶段一实施指南：构建核心 `ArelleParser`

## 1. 目标 (Objective)

本阶段的核心目标是**构建并验证一个全新的、基于Arelle标准库的`ArelleParser`核心解析器**。此解析器将成为我们新一代解析引擎的基石，专门负责处理纯净的XBRL/XML格式财报，并将其准确地映射到我们的数据库模型 (`FundReport` 及其关联表)。

完成此阶段后，我们将拥有一个可靠的、可信赖的XBRL事实提取引擎，为后续处理iXBRL和整合到上层`ParserFacade`做好准备。

## 2. 前置准备 (Prerequisites)

1.  **安装Arelle**: 团队成员需在本地开发环境中安装Arelle命令行工具。
    *   **验证**: 在终端运行 `arelleCmdLine --version` 应能成功显示版本号。
2.  **熟悉数据模型**: 团队成员需仔细阅读 `src/models/fund_data.py`，深刻理解 `FundReport`, `AssetAllocation`, `TopHolding`, `IndustryAllocation` 四个模型的数据结构、字段类型和关联关系。

## 3. 核心开发任务 (Core Development Tasks)

### 任务 1: 创建 `ArelleParser` 基础类

*   **任务描述**: 在 `src/parsers/` 目录下创建一个新文件 `arelle_parser.py`，并定义 `ArelleParser` 类。
*   **技术要求**:
    *   该类应继承自 `src/parsers/base_parser.py` 中的 `BaseParser`。
    *   实现 `can_parse` 方法：此方法应简单地返回 `True`，因为我们假设任何传递给它的文件都已经是经过预判的纯XBRL文件。
    *   实现 `parse_content` 方法的骨架，暂时留空。
*   **验收标准**:
    *   `src/parsers/arelle_parser.py` 文件被创建。
    *   `ArelleParser` 类已定义并正确继承 `BaseParser`。
    *   `can_parse` 和 `parse_content` 方法已存在。

### 任务 2: 实现Arelle命令行调用逻辑

*   **任务描述**: 在 `ArelleParser` 中实现一个私有方法 `_run_arelle_command`，用于执行Arelle命令行工具。
*   **技术要求**:
    *   使用Python的 `subprocess` 模块来调用 `arelleCmdLine`。
    *   该方法应接受一个XBRL文件路径作为输入。
    *   调用命令需包含以下关键参数：
        *   `--file`: 指定输入的XBRL文件。
        *   `--facts`: 指定输出事实列表。
        *   `--fact-list-format=json`: **强制要求**，确保输出为易于处理的JSON格式。
        *   `--log-file`: 将Arelle的日志重定向到文件，避免污染标准输出。
    *   方法需能捕获Arelle命令行的标准输出（即事实列表的JSON），并将其作为字符串返回。
    *   必须包含完善的错误处理逻辑（如Arelle未安装、命令执行失败等）。
*   **验收标准**:
    *   `_run_arelle_command` 方法已实现。
    *   使用 `tests/fixtures/001056_REPORT_1752622427.xbrl` 作为测试文件调用该方法，能成功返回一个包含事实列表的JSON字符串。
    *   在Arelle未安装或命令失败时，能抛出或捕获明确的异常。

### 任务 3: 实现数据映射核心逻辑

*   **任务描述**: 在 `ArelleParser` 中创建核心的数据转换逻辑，将Arelle输出的JSON事实列表映射到我们的`FundReport` Pydantic模型（注意：这里是Pydantic模型，非SQLAlchemy模型，以便于数据传递）。
*   **技术要求**:
    1.  **创建映射规则**: 定义一个清晰的映射关系，将XBRL概念（如 `dei:EntityRegistrantName`, `csrc-mf-general:BalanceSheetDate`）映射到`FundReport`模型的字段（如 `fund_name`, `report_period_end`）。
        *   **参考**: 需要交叉参考XBRL分类标准框架文档和`fund_data.py`模型。
    2.  **编写转换函数**:
        *   创建一个私有方法 `_map_facts_to_report`，接收事实列表JSON作为输入。
        *   遍历事实列表，根据映射规则，将事实的值填充到`FundReport`, `AssetAllocation`, `TopHolding`, `IndustryAllocation` 的Pydantic模型实例中。
        *   必须处理数据类型转换（如将字符串转换为`Decimal`或`date`）。
        *   必须处理单位和精度（Arelle输出的数值可能包含大量小数位）。
*   **验收标准**:
    *   `_map_facts_to_report` 方法已实现。
    *   输入一个已知的Arelle JSON输出，该方法能正确地创建一个填充了对应数据的、嵌套的 `FundReport` Pydantic模型实例。
    *   所有关键字段（基金代码、名称、报告期、净资产、前十大持仓等）均能被正确映射。

### 任务 4: 完善 `parse_content` 方法

*   **任务描述**: 将以上所有逻辑整合到公开的 `parse_content` 方法中。
*   **技术要求**:
    *   该方法接收XBRL文件内容（字符串）和可选的文件路径。
    *   **步骤**:
        1.  将输入内容保存到一个临时文件中。
        2.  调用 `_run_arelle_command` 处理该临时文件，获取JSON输出。
        3.  将JSON输出传递给 `_map_facts_to_report`，获得`FundReport`模型实例。
        4.  将`FundReport`实例包装在`ParseResult`对象中返回。
        5.  确保在方法结束时清理所有临时文件。
*   **验收标准**:
    *   `parse_content` 方法已完整实现。
    *   调用 `parser.parse_content(xbrl_content)` 能返回一个包含正确解析数据的 `ParseResult` 对象。

## 4. 单元测试要求 (Unit Testing)

*   **测试目标**: 必须为 `ArelleParser` 编写全面的单元测试。
*   **测试用例**:
    1.  **成功路径**: 使用 `tests/fixtures/` 目录下的至少3个不同的XBRL文件，验证 `parse_content` 能返回完整的、准确的 `FundReport` 数据。
    2.  **数据映射验证**: 对每个映射的字段（如基金名称、净资产、单个持仓等）编写断言，确保其值与XBRL文件中的源数据一致。
    3.  **异常处理**:
        *   测试当输入的不是有效的XML/XBRL时，`_run_arelle_command` 能正确处理错误。
        *   测试当Arelle命令行工具不存在时，系统能抛出清晰的`FileNotFoundError`或类似异常。
    4.  **边界情况**: 测试包含可选字段缺失的XBRL报告，确保解析器不会因此崩溃。

## 5. 最终验收 (Final Acceptance)

**阶段一被视为完成，当且仅当以下所有条件被满足：**

1.  `src/parsers/arelle_parser.py` 文件已根据上述任务要求完整实现。
2.  所有核心开发任务均已完成并通过代码审查 (Code Review)。
3.  单元测试已编写并达到85%以上的代码覆盖率。
4.  所有单元测试在CI/CD环境中持续通过。
5.  **演示**: 开发负责人需能现场演示，通过调用 `ArelleParser` 成功解析一个XBRL文件，并打印出结构完整、数据准确的 `FundReport` 对象。
