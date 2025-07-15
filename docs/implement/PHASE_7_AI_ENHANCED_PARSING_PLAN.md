# Phase 7: AI-Enhanced Hybrid Parsing Engine Implementation Plan

## 1. Project & Goal

**Project:** Implement a next-generation parsing engine for fund reports.

**Core Goal:** Drastically improve the accuracy, completeness, and robustness of data extraction from heterogeneous XBRL/HTML fund reports. Move beyond the current fragile, rule-based system to a solution that can intelligently handle diverse document structures and formats, maximizing the value of our downloaded data.

## 2. Current Situation & Problem Analysis

Our current parser, `src/parsers/xbrl_parser.py`, represents a solid first-generation attempt using rule-based and keyword-driven logic with BeautifulSoup. While it successfully established a baseline, recent comprehensive testing against our `tests/fixtures` library has revealed critical shortcomings:

*   **Low Accuracy:** The extraction of key-value data (like `fund_code`, `net_asset_value`) is inconsistent and fails frequently.
*   **Zero Table Recognition:** The `SmartTableParser` is currently unable to correctly identify and parse any of the critical data tables (asset allocation, top holdings, etc.).
*   **Fragility:** The system is highly sensitive to minor variations in HTML structure, tag naming, and text formatting. Any deviation from the anticipated patterns causes parsing to fail silently or return incorrect data.
*   **High Maintenance Overhead:** This rule-based approach requires constant, manual updates to regex patterns and navigation logic for every new report format encountered. This is not scalable.

**Conclusion:** The current system proves that a purely rule-based approach is insufficient for the complexity and variability of real-world financial reports. We are successfully downloading reports, but failing to extract their value, which undermines the core mission of the project.

## 3. Proposed Solution: A Hybrid, AI-Enhanced Parsing Engine

We will evolve our parser from a simple, rule-based script into a sophisticated, multi-stage hybrid engine. This engine will combine the speed and precision of rule-based methods with the contextual understanding and adaptability of a Large Language Model (LLM).

This approach allows us to use the best tool for each task: use rules for what is simple and structured, and AI for what is complex and unstructured.

### 3.1. High-Level Architecture

The new `XBRLParser.parse_file` method will orchestrate a three-stage pipeline:

1.  **Stage 1: Pre-processing & Cleaning:** Sanitize and simplify the raw HTML to create a clean, navigable DOM for subsequent stages.
2.  **Stage 2: Rule-Based Heuristic Extraction (The "Fast Path"):** Attempt to extract data using our improved structural and keyword-based methods. This will quickly capture data from well-structured, known formats.
3.  **Stage 3: AI-Powered Contextual Extraction (The "Intelligent Path"):** For any data that could not be confidently extracted in Stage 2, we will leverage an LLM. The model will be given targeted sections of the HTML and a clear schema, and asked to extract the missing information.

### 3.2. Implementation Guidance for the Development Team

#### **Task 1: Enhance the Rule-Based Engine (`SmartTableParser` and `_find_value_by_label`)**

This is a prerequisite for the AI stage. A better rule-based engine reduces reliance on the more expensive AI calls.

*   **Objective:** Improve the success rate of the existing parser to at least 50-60% on the fixture set.
*   **Key Actions:**
    1.  **Refine `identify_table_type`:**
        *   Implement a more sophisticated scoring algorithm. Consider factors like header keyword density, presence of numerical data, and table structure.
        *   Instead of a hardcoded exclusion list, use it to negatively weight a table's score.
        *   Add logging to output the "best guess" and score for each table encountered during a run of `verify_parser_logic.py`. This will be invaluable for debugging.
    2.  **Refine `_find_value_by_label`:**
        *   Expand the list of label patterns (e.g., for `total_net_assets`, add "资产净值(元)", "期末基金资产净值" etc.).
        *   Add more navigation strategies. Analyze the fixture files to identify 2-3 more common HTML patterns for label-value pairs.

#### **Task 2: Integrate the AI-Powered Extraction Stage**

*   **Objective:** Create a new module/class responsible for interacting with an LLM to fill in the gaps left by the rule-based parser.
*   **Key Actions:**
    1.  **Choose an LLM Provider:** Select a suitable API (e.g., OpenAI, Anthropic, or a self-hosted model) based on cost, speed, and context window size. This should be configurable via environment variables.
    2.  **Develop a `prompt_for_extraction` function:**
        *   **Input:**
            *   `html_chunk`: A relevant snippet of HTML (e.g., the content of a `<div>` or `<table>`).
            *   `target_schema`: A description of the data you want to extract (e.g., `{"fund_code": "string", "net_asset_value": "decimal"}`).
            *   `instruction`: A clear prompt, e.g., "Extract the following data from the provided HTML. Respond ONLY with a valid JSON object."
        *   **Output:** A JSON object containing the extracted data.
    3.  **Integrate into `XBRLParser.parse_file`:**
        *   After running the rule-based methods, check which fields in the `FundReport` object are still `None`.
        *   For each missing piece of data, intelligently select a relevant chunk of the source HTML to send to the LLM. **Do not send the entire document.** For example, to find `total_net_assets`, find the part of the document that contains the text "资产净值".
        *   Call `prompt_for_extraction` with the appropriate chunk and schema.
        *   Validate and merge the results from the LLM back into the `FundReport` object.

## 4. Success Criteria & Verification

*   **Primary Metric:** The `verify_parser_logic.py` script must show **>95% success rate** in populating all key fields (`fund_code`, `fund_name`, `net_asset_value`, `total_net_assets`) across the entire `tests/fixtures` dataset.
*   **Secondary Metric:** The script must show **>90% success rate** in correctly identifying and extracting data from at least two of the three table types (asset allocation, top holdings, industry).
*   **Code Quality:** The AI interaction logic must be well-encapsulated, and API keys must be managed securely via environment variables, not hardcoded.

This hybrid approach will deliver a state-of-the-art parsing system that is both efficient and highly accurate, finally unlocking the true value of our data pipeline.

---

## Appendix A: Local LLM (Ollama) Implementation Guide

This section provides a concrete guide for the development team to implement the AI-powered extraction stage using a local Ollama instance.

### 1. Model Selection

For structured data extraction, we need a model with strong instruction-following and JSON output capabilities.

*   **Primary Recommendation:** `llama3:8b`
    *   **Why:** Excellent balance of performance, speed, and context window. It has proven to be highly effective at generating structured JSON according to a schema.
    *   **Command:** `ollama pull llama3:8b`
*   **Alternative (Lightweight):** `phi3:mini`
    *   **Why:** A smaller, faster model that is surprisingly powerful. A great option if performance on lower-spec machines is a priority.
    *   **Command:** `ollama pull phi3:mini`

The team should start with `llama3:8b`.

### 2. Python Implementation (`prompt_for_extraction`)

We will use the official `ollama` Python library for clean and simple integration.

**Installation:**
```bash
poetry add ollama
```

**Example `prompt_for_extraction` function:**

This function should be added to a new utility file, e.g., `src/utils/ai_utils.py`.

```python
import ollama
from typing import Dict, Any

def prompt_for_extraction(html_chunk: str, target_schema: str, model: str = "llama3:8b") -> Dict[str, Any]:
    """
    Uses a local Ollama model to extract structured data from an HTML chunk.

    Args:
        html_chunk: A string containing the HTML snippet to parse.
        target_schema: A string describing the desired JSON output format.
        model: The Ollama model to use.

    Returns:
        A dictionary containing the extracted data, or an empty dictionary on failure.
    """
    system_prompt = f"""
    You are an expert data extraction assistant. Your task is to analyze the provided HTML snippet
    and extract the required information.

    You MUST respond ONLY with a valid JSON object that strictly adheres to the following schema.
    Do not include any explanations, apologies, or markdown formatting.

    JSON Schema:
    {target_schema}
    """

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt,
                },
                {
                    'role': 'user',
                    'content': f"Here is the HTML snippet to analyze:\n\n{html_chunk}",
                },
            ],
            format='json' # This is the crucial parameter for forcing JSON output
        )
        
        # The ollama library automatically parses the JSON string
        return response['message']['content']

    except Exception as e:
        # In a production system, add proper logging here
        print(f"Error during AI extraction: {e}")
        return {}

```

### 3. Integration into `XBRLParser`

The development team will need to modify `XBRLParser._parse_basic_info` to call this new function.

**Example Logic:**

```python
# Inside XBRLParser._parse_basic_info...
# After running the rule-based methods...

if not report.net_asset_value:
    # Define the schema for the specific data point
    nav_schema = '{"net_asset_value": "decimal or null"}'
    
    # Intelligently select the HTML chunk
    # (This logic can be improved, e.g., finding the 20 lines before and after the keyword)
    text_to_search = "份额净值"
    if text_to_search in soup.get_text():
        # This is a placeholder for more intelligent chunking logic
        html_chunk = soup.prettify() # Simplified for this example
        
        # Call the AI utility
        from src.utils.ai_utils import prompt_for_extraction # Import would be at top of file
        ai_result = prompt_for_extraction(html_chunk, nav_schema)
        
        if ai_result.get("net_asset_value"):
            try:
                report.net_asset_value = Decimal(ai_result["net_asset_value"])
            except (InvalidOperation, TypeError):
                self.logger.warning("AI returned an invalid decimal for net_asset_value")

# ... repeat for other missing fields ...
```

This detailed guide provides the development team with a clear, actionable starting point for implementing the AI-enhanced parsing features.
