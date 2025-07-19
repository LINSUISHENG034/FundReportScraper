### **【指令】解析器重构 - 阶段二：`iXBRLExtractor` 开发任务清单**

**核心目标：** 创建一个高效、精准、健壮的 `iXBRLExtractor` 组件。该组件的唯一职责是从 iXBRL (Inline XBRL) HTML 文件中剥离出内嵌的、纯净的 XBRL 文档，为后续 `ArelleParser` 的解析工作提供标准、干净的输入。

---

### **开发者须知**

*   **技术选型:** 必须使用 `lxml` 库进行 HTML 解析和 XPath 查找，以确保最佳性能和对格式不规范 HTML 的容错能力。
*   **文件定位:**
    *   新组件代码应存放于 `src/parsers/xbrl/ixbrl_extractor.py`。
    *   新的单元测试应存放于 `tests/unit/test_ixbrl_extractor.py`。
*   **测试样本:** 开发团队需要从 `tests/fixtures/` 目录中识别出 iXBRL 格式的文件作为测试用例。这些文件本质上是 HTML，但内部嵌入了 XBRL 标签。

---

### **任务分解 (Action Items):**

**1. 【架构】创建 `iXBRLExtractor` 类结构**
    -   **任务描述:** 在指定路径下创建 `iXBRLExtractor` 类，并定义其核心接口。
    -   **具体要求:**
        1.  创建 `src/parsers/xbrl/ixbrl_extractor.py` 文件。
        2.  定义 `iXBRLExtractor` 类。
        3.  在构造函数 `__init__` 中，初始化一个 `lxml.etree.HTMLParser` 实例，配置为能够从潜在的格式错误中恢复 (`recover=True`)。
        4.  定义两个公共方法：
            *   `extract_to_string(self, html_content: str) -> Optional[str]:` 接收 iXBRL 文件内容字符串，返回提取出的纯净 XBRL XML 字符串。如果未找到 XBRL 内容，则返回 `None`。
            *   `extract_to_tempfile(self, html_content: str) -> Optional[Path]:` 接收 iXBRL 文件内容字符串，将提取出的 XBRL 写入一个临时文件，并返回该文件的 `pathlib.Path` 对象。如果未找到，则返回 `None`。
    -   **验收标准:**
        -   文件和类结构已按要求创建。
        -   公共方法签名已定义，并包含清晰的类型提示和文档字符串。

**2. 【核心】实现 XBRL 提取逻辑**
    -   **任务描述:** 在 `iXBRLExtractor` 类中实现使用 XPath 定位并提取内联 XBRL 数据的核心逻辑。
    -   **具体要求:**
        1.  在 `extract_to_string` 方法中，使用 `lxml.etree.fromstring` 和预初始化的 `HTMLParser` 来解析输入的 `html_content`。
        2.  使用一个健壮的 XPath 表达式来查找内嵌的 XBRL 根元素。首选表达式为 `//body//*[local-name()='xbrl']`。如果此表达式在某些样本中失效，可考虑备用表达式，如 `//*[local-name()='xbrl']`。
        3.  如果 XPath 查找到一个或多个匹配的元素，**只选择第一个**作为目标根元素。
        4.  使用 `lxml.etree.tostring` 将找到的 XBRL 根元素及其所有子元素序列化为一个 UTF-8 编码的 XML 字符串。
        5.  如果 XPath 未找到任何匹配项，则方法应返回 `None`。
        6.  `extract_to_tempfile` 方法应在内部调用 `extract_to_string`，然后将获取到的 XML 字符串写入一个由 `tempfile` 模块管理的临时文件中。
    -   **验收标准:**
        -   对于一个有效的 iXBRL 输入，`extract_to_string` 能返回一个以 `<xbrli:xbrl ...>` 或类似标签开头的、格式正确的 XML 字符串。
        -   对于一个不含内联 XBRL 的纯 HTML 输入，两个提取方法均返回 `None`。

**3. 【测试】编写并通关单元测试**
    -   **任务描述:** 为 `iXBRLExtractor` 编写全面的单元测试，确保其在各种情况下的行为都符合预期。
    -   **具体要求:**
        1.  创建 `tests/unit/test_ixbrl_extractor.py` 文件。
        2.  **测试用例 1 (成功路径):** 使用一个确认有效的 iXBRL 文件。断言 `extract_to_string` 返回的字符串是有效的 XML，并且 `extract_to_tempfile` 创建的文件内容与该字符串一致。
        3.  **测试用例 2 (失败路径 - 纯 HTML):** 使用一个不包含任何 XBRL 标签的纯 HTML 文件。断言两个提取方法均返回 `None`。
        4.  **测试用例 3 (失败路径 - 纯 XML):** 使用一个 `tests/fixtures/` 中的纯 XBRL/XML 文件。断言两个提取方法均返回 `None`（因为没有 `<body>` 标签）。
        5.  **测试用例 4 (边界情况):** 如果可能，找到一个包含多个 XBRL 实例的 iXBRL 文件，并断言该实现只提取了第一个实例。
        6.  在测试完成后，确保所有创建的临时文件都被正确清理。
    -   **验收标准:**
        -   `pytest` 测试套件能够顺利执行并通过所有为 `iXBRLExtractor` 编写的新测试用例。
        -   测试覆盖率满足项目质量要求。
