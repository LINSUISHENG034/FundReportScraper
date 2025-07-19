### **【指令】解析器重构 - 阶段一：核心 `ArelleParser` 架构升级任务清单**

**目标：** 构建一个健壮、可维护、面向未来的XBRL解析引擎，彻底取代旧的、基于`lxml`的脆弱实现。

---

### **【重要】环境准备 (Environment Setup)**

**背景:** 在集成 `arelle-release` 包时，发现其依赖的 `lxml` 库版本 (`<6`) 与项目主环境的 `lxml` 版本 (`>=6`) 存在严重冲突。为解决此问题，我们采用依赖隔离策略，为 Arelle 创建一个独立的虚拟环境。

**开发团队必须在开始编码前完成以下环境设置：**

1.  **创建隔离环境目录:**
    ```bash
    # 在项目根目录下执行
    mkdir -p tools/arelle_env
    ```

2.  **创建并激活虚拟环境:**
    ```bash
    # 在项目根目录下执行
    python -m venv tools/arelle_env/.venv
    ```

3.  **安装 Arelle:**
    ```bash
    # 在项目根目录下执行 (Windows)
    tools/arelle_env/.venv/Scripts/pip install arelle-release

    # 在项目根目录下执行 (macOS/Linux)
    tools/arelle_env/.venv/bin/pip install arelle-release
    ```

4.  **验证安装:**
    ```bash
    # 在项目根目录下执行 (Windows)
    tools/arelle_env/.venv/Scripts/arelleCmdLine --version

    # 在项目根目录下执行 (macOS/Linux)
    tools/arelle_env/.venv/bin/arelleCmdLine --version
    ```
    *预期输出应为 Arelle 的版本号，例如 `Arelle(r) 2.37.37 (64bit)`。*

**代码实现说明:** 在 `ArelleParser` 的实现中，所有对 Arelle 的调用都必须通过 `subprocess` 指向这个隔离环境中的 `arelleCmdLine` 可执行文件。

---

**任务分解 (Action Items):**

**1. 【清理】移除旧核心解析逻辑**
    -   **任务描述:** 定位并彻底删除 `src/parsers/arelle_parser.py` 文件中所有与旧的、基于 `lxml` 的原生解析相关的代码。这包括但不限于 `_extract_facts_with_native_parser` 方法及其所有调用链。
    -   **验收标准:**
        -   `_extract_facts_with_native_parser` 方法被完全删除。
        -   代码中不再有任何直接使用 `lxml` 对 XBRL 文件进行底层事实提取的逻辑。
        -   Arelle 命令行或其 Python API 成为获取 XBRL 事实的 **唯一** 来源。

**2. 【架构】实现动态分类标准策略加载**
    -   **任务描述:** 将 XBRL `concept_mappings` (概念映射) 规则从代码中剥离，实现动态加载。
    -   **具体步骤:**
        1.  在 `config/` 目录下创建新目录 `xbrl_taxonomies/`。
        2.  研究 `reference/XBRL分类标准框架/` 下的文档，为不同版本的分类标准（例如 `csrc_v2.1`）创建对应的 JSON 映射文件（例如 `csrc_v2.1.json`），并存放于上述新目录。
        3.  在 `ArelleParser` 中实现新逻辑：在解析任何 XBRL 文件之前，必须先读取其 XML 头部的 `<link:schemaRef>` 标签，获取其分类标准的 URL 或标识符。
        4.  根据获取到的标识符，动态地、有选择性地从 `config/xbrl_taxonomies/` 目录加载正确的映射规则 JSON 文件供后续使用。
    -   **验收标准:**
        -   `ArelleParser` 不再硬编码任何 `concept_mappings`。
        -   解析器能够成功识别 `tests/fixtures/` 中不同报告的 `schemaRef` 并加载对应的（或默认的）映射文件。

**3. 【重构】简化核心解析与映射逻辑**
    -   **任务描述:** 重写 `ArelleParser` 内部处理由 Arelle 返回的结构化数据（JSON）的逻辑，使其更清晰、更直接。
    -   **具体要求:**
        1.  重构 `_map_top_holdings`, `_map_asset_allocations` 等表格映射方法。
        2.  新的实现逻辑必须是清晰的三步：**按 `contextRef` 分组 -> 对组内数据进行聚合 -> 将聚合结果映射到数据模型**。
        3.  **严禁**保留任何复杂的辅助函数或“后备”聚合方法（如 `_map_asset_allocations_aggregated`），这些是旧的、脆弱设计的产物。
    -   **验收标准:**
        -   表格映射方法的代码行数显著减少，逻辑一目了然。
        -   代码中没有复杂的、嵌套的辅助函数调用。

**4. 【规范】消除所有硬编码与“猜测”逻辑**
    -   **任务描述:** 提升代码的确定性和可维护性，移除所有不必要的默认值和推断逻辑。
    -   **具体要求:**
        1.  在进行数据映射时，如果 Arelle 的输出中没有找到某个字段对应的事实（Fact），则在我们的数据模型中该字段的值必须初始化为 `None`。**禁止**使用任何硬编码的默认值（例如，将报告类型默认为 `ReportType.QUARTERLY`）。
        2.  彻底移除所有基于报告日期来“猜测”报告类型的逻辑。报告类型应直接从 XBRL 的元数据中获取，如果获取不到，则为 `None`。
    -   **验收标准:**
        -   代码中搜索不到除 `None` 以外的硬编码默认值。
        -   日期推断逻辑被完全删除。

**5. 【测试】重构单元测试**
    -   **任务描述:** 由于 `parser` 模块已大规模重构，旧的单元测试已失效。需要为重构后的 `ArelleParser` 编写全新的、全面的单元测试。
    -   **具体要求:**
        1.  **删除** `tests/unit/test_parsers.py`（或相关文件）中所有针对旧解析器逻辑的测试用例。
        2.  利用 `tests/fixtures/` 目录下的所有 `.xbrl` 文件作为新测试的输入。
        3.  为每个核心表格（如前十大持仓、资产配置等）编写专门的测试函数。
        4.  断言重构后的解析器能够准确、完整地从样本文件中解析出所有关键数据。
    -   **验收标准:**
        -   旧的、无关的解析器测试已被移除。
        -   `pytest` 测试套件能够顺利执行并通过所有为 `ArelleParser` 编写的新测试用例。
        -   测试覆盖率满足项目质量要求。
