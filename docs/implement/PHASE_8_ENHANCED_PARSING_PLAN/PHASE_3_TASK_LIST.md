### **【指令】解析器重构 - 阶段三：`ParserFacade` 路由逻辑重构任务清单**

**核心目标：** 将 `ParserFacade` 从一个简单的分发器，重构为一个能够理解并执行新一代解析架构（iXBRL -> Extractor -> ArelleParser）的智能路由中心。

---

### **开发者须知**

*   **核心文件:** 本阶段的所有修改都将集中在 `src/parsers/parser_facade.py` 文件中。
*   **测试策略:** 由于本阶段重构的是核心路由逻辑，单元测试的编写会非常复杂。因此，我们将采用**集成测试**的策略，在 `tests/integration/` 目录下创建新的测试文件，通过模拟（Mock）各个解析器组件来验证 `ParserFacade` 的行为是否正确。

---

### **任务分解 (Action Items):**

**1. 【架构】集成新组件并移除旧逻辑**
    -   **任务描述:** 在 `ParserFacade` 的构造函数中，实例化新阶段所需的组件，并移除旧的、不正确的路由映射。
    -   **具体要求:**
        1.  在 `XBRLParserFacade.__init__` 方法中，导入并实例化 `iXBRLExtractor`。
            ```python
            from src.parsers.xbrl.ixbrl_extractor import iXBRLExtractor
            # ...
            self.ixbrl_extractor = iXBRLExtractor()
            ```
        2.  **彻底删除** `self._format_parser_mapping` 属性。新的路由逻辑将更加明确和直接，不再需要这个间接的映射表。
        3.  确保 `ArelleParser` 和 `OptimizedHTMLParser` 仍然被正确实例化。
    -   **验收标准:**
        -   `iXBRLExtractor` 已作为 `ParserFacade` 的一个属性被实例化。
        -   `_format_parser_mapping` 字典已被从代码中移除。

**2. 【核心】重写 `parse_content_async` 路由逻辑**
    -   **任务描述:** 这是本阶段的核心。需要完全重写 `parse_content_async` 方法，以实现“3.1 核心处理流程”中定义的新路由逻辑。
    -   **实现指南 (伪代码):**
        ```python
        async def parse_content_async(self, content: str, file_path: Optional[Path] = None, format_hint: Optional[DocumentFormat] = None) -> ParseResult:
            # 1. 格式检测 (如果未提供)
            if format_hint is None:
                format_hint = self.format_detector.detect_format(content, file_path)

            # 2. iXBRL 路径
            if format_hint == DocumentFormat.IXBRL:
                self.logger.info("iXBRL format detected. Attempting extraction...")
                # 2.1. 提取内嵌的 XBRL
                extracted_xml = self.ixbrl_extractor.extract_to_string(content)
                
                if extracted_xml:
                    self.logger.info("XBRL content extracted successfully. Passing to ArelleParser.")
                    # 2.2. 使用 ArelleParser 解析提取出的 XML
                    arelle_parser = self._parsers.get(ParserType.XBRL_NATIVE)
                    result = arelle_parser.parse_content(extracted_xml, file_path)
                    if result.success:
                        return await self._enhance_parsing_result(result, content) # 成功，返回
                
                # 2.3. 如果提取失败或 Arelle 解析失败，则降级
                self.logger.warning("iXBRL path failed. Falling back to HTML parser.")

            # 3. 纯 XBRL 路径
            if format_hint == DocumentFormat.XBRL:
                self.logger.info("Pure XBRL format detected. Using ArelleParser.")
                arelle_parser = self._parsers.get(ParserType.XBRL_NATIVE)
                result = arelle_parser.parse_content(content, file_path)
                if result.success:
                    return await self._enhance_parsing_result(result, content) # 成功，返回
                
                # 3.1. 如果 Arelle 解析失败，则降级
                self.logger.warning("Pure XBRL path failed. Falling back to HTML parser.")

            # 4. HTML / 未知 / 降级路径
            self.logger.info("Using fallback HTML parser.")
            html_parser = self._parsers.get(ParserType.HTML_LEGACY)
            if html_parser:
                result = html_parser.parse_content(content, file_path)
                if result.success:
                    return await self._enhance_parsing_result(result, content)

            # 5. (未来) LLM 最终备用方案
            # if self.llm_assistant:
            #     ...

            # 6. 所有方法都失败
            return self._create_error_result("All parsing attempts failed.")
        ```
    -   **验收标准:**
        -   `parse_content_async` 方法的逻辑与上述指南完全一致。
        -   代码能够正确处理 `iXBRL` 和 `XBRL` 两种格式，并能在失败时正确地降级到 `HTML_LEGACY` 解析器。

**3. 【测试】编写路由逻辑集成测试**
    -   **任务描述:** 创建一个新的集成测试文件，通过模拟（Mocking）来验证 `ParserFacade` 的新路由逻辑是否按预期工作。
    -   **具体要求:**
        1.  创建 `tests/integration/test_parser_facade_routing.py` 文件。
        2.  使用 `pytest.mark.parametrize` 来创建针对不同文件类型的测试场景（`iXBRL`, `XBRL`, `HTML`）。
        3.  在测试函数中，使用 `unittest.mock.patch` 来模拟 `ArelleParser`, `iXBRLExtractor`, 和 `OptimizedHTMLParser` 的 `parse_content` 或 `extract_to_string` 方法。
        4.  **测试用例 1 (iXBRL 路径):**
            *   输入一个 `iXBRL` 文件。
            *   断言 `iXBRLExtractor.extract_to_string` 被调用了 **1 次**。
            *   断言 `ArelleParser.parse_content` 被调用了 **1 次**。
            *   断言 `OptimizedHTMLParser.parse_content` 被调用了 **0 次**。
        5.  **测试用例 2 (纯 XBRL 路径):**
            *   输入一个纯 `XBRL` 文件。
            *   断言 `iXBRLExtractor.extract_to_string` 被调用了 **0 次**。
            *   断言 `ArelleParser.parse_content` 被调用了 **1 次**。
        6.  **测试用例 3 (HTML 降级路径):**
            *   输入一个纯 `HTML` 文件。
            *   断言 `OptimizedHTMLParser.parse_content` 被调用了 **1 次**。
        7.  **测试用例 4 (iXBRL 失败降级路径):**
            *   模拟 `iXBRLExtractor.extract_to_string` 返回 `None`。
            *   输入一个 `iXBRL` 文件。
            *   断言 `iXBRLExtractor.extract_to_string` 被调用了 **1 次**。
            *   断言 `OptimizedHTMLParser.parse_content` 被调用了 **1 次**。
    -   **验收标准:**
        -   新的集成测试文件已创建。
        -   所有测试用例都已实现，并通过 `pytest` 执行成功。
        -   测试明确验证了在不同输入下，正确的解析器和组件被以正确的顺序调用。
