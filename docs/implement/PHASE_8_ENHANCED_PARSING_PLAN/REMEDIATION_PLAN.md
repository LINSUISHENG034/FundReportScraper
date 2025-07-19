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



### 3.1. 核心处理流程

1.  **格式检测 (FormatDetector)**: 接收文件，通过内容嗅探，并基于**置信度分数**（而非顺序判断）输出最可能的格式：`XBRL`, `iXBRL`, `HTML`, 或 `Unknown`。

2.  **解析门面 (ParserFacade)**: 作为总指挥，根据格式执行不同路由：
    *   **如果格式是 `iXBRL`**:
        1.  首先，将文件交给 **`iXBRLExtractor` (新组件)**。
        2.  `iXBRLExtractor` 使用`lxml`库高效解析HTML，找到并提取出完整的、内嵌的XBRL文档，将其保存为一个临时的纯XML文件。
        3.  然后，`ParserFacade`将这个**临时的纯XML文件**交给 **`ArelleParser` (新核心)** 进行解析。
    *   **如果格式是 `XBRL`**:
        1.  直接将原始文件交给 **`ArelleParser`** 进行解析。
    *   **如果格式是 `HTML` 或 `Unknown`**:
        1.  将其交给 **`OptimizedHTMLParser` (角色回归)** 作为最后的备用方案，进行尽力而为的屏幕抓取。

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

### **阶段一：构建核心 `ArelleParser`**
*   **任务**: 创建一个新的`ArelleParser`类，封装对Arelle的调用。
*   **步骤**:
    1.  研究并确定是使用Arelle的命令行工具还是Python库。命令行更稳定解耦，推荐优先考虑。
    2.  编写Python代码，通过`subprocess`调用Arelle命令行，并传递文件路径和输出JSON的参数。
    3.  编写逻辑，将Arelle输出的JSON数据映射并填充到我们的`FundReport` Pydantic模型中。
        *   **重要警告**: 此步骤并非简单的键值映射。Arelle的输出是基于XBRL上下文（Context）和事实（Fact）的复杂结构。映射逻辑必须能够处理维度、表格和时间序列数据。
        *   **权威指南**: 此映射逻辑的实现，**必须严格遵循** `PHASE_1.1_SPRINT_PLAN.md` 中定义的精确编码和上下文解析策略。该文档是本阶段任务的唯一技术实现标准。
    4.  **验证**: 使用`tests/fixtures/`下的纯`.xbrl`文件对`ArelleParser`进行单元测试，确保其能正确解析，特别是能够完整解析出财报的资产配置、前十大持仓和行业分配等核心表格数据。

### **阶段二：开发 `iXBRLExtractor`**
*   **任务**: 创建`iXBRLExtractor`，实现从iXBRL文件中剥离XBRL数据的功能。
*   **步骤**:
    1.  使用`lxml.etree`库来解析HTML内容。
    2.  使用XPath表达式（如 `//body//*[local-name()='xbrl']`）来定位内嵌的XBRL根元素。
    3.  将找到的XML子树序列化为一个字符串。
    4.  将该字符串写入一个临时文件，并返回文件路径。
    5.  **验证**: 使用一个已知的iXBRL文件进行测试，确保提取出的临时文件是格式正确的纯XML。

### **阶段三：重构 `ParserFacade` 路由逻辑**
*   **任务**: 修改`ParserFacade`以实现新的架构流程。
*   **步骤**:
    1.  在`ParserFacade`中实例化新的`ArelleParser`和`iXBRLExtractor`。
    2.  修改`parse_file`或`parse_content_async`方法中的路由逻辑，严格遵循“3.1 核心处理流程”中定义的规则。
    3.  移除对旧的`FundXBRLParser`的调用。

### **阶段四：优化 `FormatDetector`**
*   **任务**: 提升格式检测的准确性。
*   **步骤**:
    1.  修改`detect_format`方法。
    2.  让它在内部调用`get_format_confidence`方法。
    3.  比较`XBRL`, `iXBRL`, `HTML`的置信度分数，返回分数最高的那个格式作为最终结果。

### **阶段五：清理与整合测试**
*   **任务**: 移除旧代码，确保系统端到端正常工作。
*   **步骤**:
    1.  删除`src/parsers/fund_xbrl_parser.py`文件。
    2.  审查并重命名`OptimizedHTMLParser`为`LegacyHTMLScraper`，以准确反映其功能。
    3.  创建集成测试，覆盖三种主要路径：纯XBRL文件、iXBRL文件、纯HTML文件。验证每种文件都能被正确路由到相应的解析器并产出预期结果。

## 5. 预期收益 (Expected Outcome)

完成此重构计划后，我们将获得：
*   **一个真正健壮的解析引擎**: 能够可靠、准确地处理行业标准的XBRL和iXBRL文件。
*   **大幅提升的数据质量**: 从机器可读的结构化数据源提取信息，而不是依赖脆弱的文本匹配。
*   **显著降低的维护成本**: 新架构清晰、解耦，未来扩展或修复将变得非常容易。
*   **彻底的技术债偿还**: 移除了项目中最核心的一个设计缺陷，为后续开发奠定了坚实的基础。
