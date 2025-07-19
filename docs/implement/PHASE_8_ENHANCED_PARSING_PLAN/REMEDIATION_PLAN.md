# 解析器模块深度重构与修复计划 (Remediation Plan)

## 1. 执行摘要 (Executive Summary)

经过对 `parser` 模块的全面代码审计，我们得出以下核心结论：**当前系统缺乏真正解析XBRL和iXBRL的能力，其解析流程完全建立在脆弱的“屏幕抓取”(Screen Scraping)技术之上。** 这种实现方式不仅无法利用XBRL作为机器可读标准的优势，还为系统带来了巨大的维护成本和数据质量风险。

本计划旨在彻底解决此问题。我们将用一个**基于行业标准库(Arelle)的、健壮的、可维护的解析引擎**替换当前的伪实现。此举将显著提升数据解析的准确性、可靠性和效率，彻底偿还当前的技术债。

## 2. 问题分析 (Problem Analysis)

审计揭示了以下四个层面的问题：

1.  **`FundXBRLParser` 的根本性设计错误**:
    *   该模块名为XBRL解析器，但其内部完全使用`BeautifulSoup`进行文本关键词匹配和抓取，是典型的屏幕抓取实现，**不是一个XBRL解析器**。这是最严重的技术债。

2.  **`OptimizedHTMLParser` 的功能错位**:
    *   这是一个纯粹的HTML抓取器，它无法识别和处理iXBRL中的内联结构化数据。将它作为iXBRL的备用解析方案是无效的。

3.  **`ParserFacade` 的路由逻辑缺陷**:
    *   `ParserFacade` 的顶层架构设计优良，但其路由逻辑存在致命缺陷。它错误地将iXBRL文件直接传递给为纯XML设计的`FundXBRLParser`，**缺少了从HTML中“提取”嵌入式XBRL数据的关键步骤**，导致解析必然失败。

4.  **`FormatDetector` 的决策逻辑脆弱**:
    *   该模块基于`if/elif`的顺序进行判断，当一个iXBRL文件同时具备HTML和XBRL的特征时，容易产生误判。它未能利用自己计算出的“置信度分数”来做出更科学的决策。

## 3. 新一代解析架构 (Proposed Architecture)

为了解决上述问题，我们提出以下分层、清晰的新架构：



### 3.1. 核心处理流程 (v2.0 - 引入AI备用方案)

1.  **格式检测 (FormatDetector)**: 接收文件，通过内容嗅探，并基于**置信度分数**（而非顺序判断）输出最可能的格式：`XBRL`, `iXBRL`, `HTML`, 或 `Unknown`。

2.  **解析门面 (ParserFacade)**: 作为总指挥，根据格式执行不同路由：
    *   **如果格式是 `iXBRL`**:
        1.  首先，将文件交给 **`iXBRLExtractor` (新组件)**。
        2.  `iXBRLExtractor` 使用`lxml`库高效解析HTML，找到并提取出完整的、内嵌的XBRL文档，将其保存为一个临时的纯XML文件。
        3.  然后，`ParserFacade`将这个**临时的纯XML文件**交给 **`ArelleParser` (新核心)** 进行解析。
    *   **如果格式是 `XBRL`**:
        1.  直接将原始文件交给 **`ArelleParser`** 进行解析。
    *   **如果格式是 `HTML` 或 `Unknown` (或以上步骤全部失败)**:
        1.  首先，将其交给 **`OptimizedHTMLParser` (角色回归)** 作为常规备用方案，进行尽力而为的屏幕抓取。
        2.  如果 `OptimizedHTMLParser` 也解析失败或返回数据质量过低，则启动**最终备用方案**：将文件交给 **`LLMAssistantParser` (新组件)**。

### 3.2. 关键组件职责

*   **`ArelleParser` (新核心)**:
    *   **职责**: 唯一负责解析**纯净XBRL/XML数据**的组件。
    *   **实现**: 封装对业界标准的Arelle库（通过其命令行工具或Python API）的调用。Arelle能够深刻理解XBRL的分类标准、上下文、单元和事实，确保解析的准确性。它将解析结果输出为结构化的JSON，供我们轻松消费。
    *   **替换**: 它将彻底取代充满误导性的`FundXBRLParser`。

*   **`iXBRLExtractor` (新组件)**:
    *   **职责**: 唯一负责处理iXBRL“外壳”的组件。
    *   **实现**: 使用高性能的`lxml`库，通过XPath精确查找并剥离出iXBRL文件中的`<body>`部分内嵌的XBRL根元素（如`<xbrli:xbrl>`），并将其序列化为纯净的XML数据。

*   **`OptimizedHTMLParser` (角色回归)**:
    *   **职责**: 回归其本来的角色——一个备用的屏幕抓取器，仅用于处理不包含任何XBRL信息的纯HTML报告。
### 3.2. 关键组件职责 (v2.0)

*   **`ArelleParser` (新核心)**:
    *   **职责**: 唯一负责解析**纯净XBRL/XML数据**的组件。
    *   **实现**:
        1.  **调用Arelle**: 必须通过`subprocess`唯一且直接地调用Arelle命令行工具，将XBRL文件解析为结构化的JSON事实列表。**严禁保留任何旧的、基于lxml的内部解析逻辑作为备用。**
        2.  **动态策略加载**: 在解析前，通过读取XBRL文件头部的`<link:schemaRef>`标签，识别文档遵循的官方分类标准版本。
        3.  根据识别出的版本，从外部配置文件（如 `config/xbrl_taxonomies/csrc_v2.1.json`）动态加载对应的`concept_mappings`映射规则。
    *   **替换**: 它将彻底取代充满误导性的`FundXBRLParser`。

*   **`iXBRLExtractor` (新组件)**:
    *   **职责**: 唯一负责处理iXBRL“外壳”的组件。
    *   **实现**: 使用高性能的`lxml`库，通过XPath精确查找并剥离出iXBRL文件中的`<body>`部分内嵌的XBRL根元素（如`<xbrli:xbrl>`），并将其序列化为纯净的XML数据。

*   **`OptimizedHTMLParser` (角色回归)**:
    *   **职责**: 回归其本来的角色——一个备用的屏幕抓取器，仅用于处理不包含任何XBRL信息的纯HTML报告。

*   **`LLMAssistantParser` (新组件 - 最终防线)**:
    *   **职责**: 作为解析流程的最后一道防线，处理所有确定性解析器都失败的“疑难杂症”文件（如格式错误的XBRL、扫描版PDF的文本内容等）。
    *   **实现**:
        1.  调用大语言模型（LLM）API。
        2.  通过精心设计的Prompt，指示LLM扮演金融分析师，从非结构化文本中提取关键信息，并以指定的JSON格式返回。
        3.  所有经此解析器输出的数据，必须在`ReportMetadata`中明确标记（如 `llm_assisted: True`）并赋予较低的置信度分数。

### 3.2. 关键组件职责

*   **`ArelleParser` (新核心)**:
    *   **职责**: 唯一负责解析**纯净XBRL/XML数据**的组件。
    *   **实现**: 封装对业界标准的Arelle库（通过其命令行工具或Python API）的调用。Arelle能够深刻理解XBRL的分类标准、上下文、单元和事实，确保解析的准确性。它将解析结果输出为结构化的JSON，供我们轻松消费。
    *   **替换**: 它将彻底取代充满误导性的`FundXBRLParser`。

*   **`iXBRLExtractor` (新组件)**:
    *   **职责**: 唯一负责处理iXBRL“外壳”的组件。
    *   **实现**: 使用高性能的`lxml`库，通过XPath精确查找并剥离出iXBRL文件中的`<body>`部分内嵌的XBRL根元素（如`<xbrli:xbrl>`），并将其序列化为纯净的XML数据。

*   **`OptimizedHTMLParser` (角色回归)**:
    *   **职责**: 回归其本来的角色——一个备用的屏幕抓取器，仅用于处理不包含任何XBRL信息的纯HTML报告。

## 4. 分步实施路线图 (Implementation Roadmap)

我们建议按照以下五个阶段，循序渐进地完成重构：

### **阶段一：构建核心 `ArelleParser` (v2.0 - 架构升级)**
*   **核心任务**: 构建一个健壮、可维护、面向未来的XBRL解析引擎。
*   **验收标准**:
    1.  **移除旧核心**: 必须彻底删除`arelle_parser.py`中任何对旧的、基于`lxml`的`_extract_facts_with_native_parser`的调用。Arelle必须是获取XBRL事实的**唯一**数据源。
    2.  **实现动态策略加载**:
        *   在`config/`下创建`xbrl_taxonomies/`目录。
        *   将`concept_mappings`规则外部化为版本化的JSON文件（如`csrc_v2.1.json`）。
        *   `ArelleParser`必须实现逻辑，在解析前读取XBRL文件的`<link:schemaRef>`，并据此加载正确的映射配置文件。
    3.  **简化上下文解析逻辑**:
        *   重写`_map_top_holdings`等表格解析方法，使其逻辑清晰、简洁。
        *   严禁使用复杂的辅助函数和“后备”聚合方法（如`_map_asset_allocations_aggregated`）。核心逻辑必须是直接的“按`contextID`分组 -> 聚合 -> 转换模型”。
    4.  **消除硬编码**:
        *   在映射数据时，所有未找到对应事实的字段，其初始值必须为`None`，而不是硬编码的默认值（如`ReportType.QUARTERLY`）。
        *   移除所有基于日期推断报告类型的“猜测”逻辑。
    5.  **单元测试**: 使用`tests/fixtures/`下的`.xbrl`文件进行单元测试，确保重构后的解析器能够准确、完整地解析出财报的核心表格数据。

### **阶段二：开发 `iXBRLExtractor`**
*   **任务**: 创建`iXBRLExtractor`，实现从iXBRL文件中剥离XBRL数据的功能。
*   **步骤**:
    1.  使用`lxml.etree`库来解析HTML内容。
    2.  使用XPath表达式（如 `//body//*[local-name()='xbrl']`）来定位内嵌的XBRL根元素。
    3.  将找到的XML子树序列化为一个字符串。
    4.  将该字符串写入一个临时文件，并返回文件路径。
    5.  **验证**: 使用一个已知的iXBRL文件进行测试，确保提取出的临时文件是格式正确的纯XML。

### **阶段三：重构 `ParserFacade` 路由逻辑 (v2.0)**
*   **任务**: 修改`ParserFacade`以实现新的、包含AI备用方案的架构流程。
*   **步骤**:
    1.  在`ParserFacade`中实例化新的`ArelleParser`、`iXBRLExtractor`和`LLMAssistantParser`。
    2.  修改`parse_file`或`parse_content_async`方法中的路由逻辑，严格遵循“3.1 核心处理流程 (v2.0)”中定义的规则，确保在所有确定性解析器失败后，调用`LLMAssistantParser`作为最后防线。
    3.  移除对旧的`FundXBRLParser`的调用。

### **阶段四：优化 `FormatDetector`**
*   **任务**: 提升格式检测的准确性。
*   **步骤**:
    1.  修改`detect_format`方法。
    2.  让它在内部调用`get_format_confidence`方法。
    3.  比较`XBRL`, `iXBRL`, `HTML`的置信度分数，返回分数最高的那个格式作为最终结果。

### **阶段五：实现 `LLMAssistantParser`**
*   **任务**: 开发LLM备用解析器。
*   **步骤**:
    1.  在`src/parsers/llm_assistant.py`中，实现`LLMAssistantParser`类。
    2.  编写调用大语言模型API的逻辑。
    3.  设计并测试用于提取核心财务数据的Prompt。
    4.  实现将LLM返回的JSON映射到`ComprehensiveFundReport`模型的逻辑。
    5.  确保所有从此解析器输出的数据都被正确标记（`llm_assisted: True`和低置信度分数）。

### **阶段六：清理与整合测试 (v2.0)**
*   **任务**: 移除旧代码，确保系统端到端正常工作。
*   **步骤**:
    1.  删除`src/parsers/fund_xbrl_parser.py`文件。
    2.  审查并重命名`OptimizedHTMLParser`为`LegacyHTMLScraper`，以准确反映其功能。
    3.  创建集成测试，覆盖**四种**主要路径：纯XBRL文件、iXBRL文件、纯HTML文件，以及**解析失败后回退到LLM的场景**。验证每种文件都能被正确路由并产出预期结果。

## 5. 预期收益 (Expected Outcome v2.0)

完成此重构计划后，我们将获得：
*   **一个真正健壮的解析引擎**: 能够可靠、准确地处理行业标准的XBRL和iXBRL文件。
*   **面向未来的兼容性**: 通过配置驱动的策略模式，可以轻松适配未来不断更新的XBRL技术规范，无需修改代码。
*   **大幅提升的数据质量与鲁棒性**: 不仅能从结构化数据源提取高质量信息，还能在解析失败时，利用AI大模型作为最终防线，最大限度地从疑难文件中提取价值，极大提升了系统的整体鲁B棒性。
*   **显著降低的维护成本**: 新架构清晰、解耦，未来扩展或修复将变得非常容易。
*   **彻底的技术债偿还**: 移除了项目中最核心的一个设计缺陷，为后续开发奠定了坚实的基础。
