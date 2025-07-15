"""
AI-powered data extraction utilities for fund report parsing.
Uses local Ollama models to extract structured data from HTML content.
"""

import json
import re
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from src.core.logging import get_logger

logger = get_logger("ai_utils")


def prompt_for_extraction(html_chunk: str, target_schema: str, model: str = "llama3:latest") -> Dict[str, Any]:
    """
    Uses a local Ollama model to extract structured data from an HTML chunk.

    Args:
        html_chunk: A string containing the HTML snippet to parse.
        target_schema: A string describing the desired JSON output format.
        model: The Ollama model to use.

    Returns:
        A dictionary containing the extracted data, or an empty dictionary on failure.
    """
    if not OLLAMA_AVAILABLE:
        logger.warning("Ollama not available, skipping AI extraction")
        return {}
    
    # Limit HTML chunk size to prevent context overflow
    if len(html_chunk) > 8000:
        html_chunk = html_chunk[:8000] + "..."
    
    system_prompt = f"""
    You are an expert data extraction assistant for Chinese fund reports. Your task is to analyze the provided HTML snippet
    and extract the required information.

    You MUST respond ONLY with a valid JSON object that strictly adheres to the following schema.
    Do not include any explanations, apologies, or markdown formatting.

    JSON Schema:
    {target_schema}

    Important notes:
    - Look for Chinese financial terms like "基金代码", "基金名称", "份额净值", "资产净值", etc.
    - Numbers may be formatted with commas or Chinese number formatting
    - If a value cannot be found, use null
    - For decimal values, extract only the numeric part
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
            format='json'  # This forces JSON output
        )
        
        # Parse the JSON response
        result = response['message']['content']
        if isinstance(result, str):
            result = json.loads(result)
        
        logger.debug("ai_extraction_success", extracted_fields=list(result.keys()))
        return result

    except Exception as e:
        logger.warning("ai_extraction_error", error=str(e))
        return {}


def extract_relevant_html_chunk(soup: BeautifulSoup, search_terms: list, context_lines: int = 10) -> str:
    """
    Extract a relevant chunk of HTML containing the search terms with surrounding context.
    
    Args:
        soup: BeautifulSoup object of the HTML document
        search_terms: List of terms to search for
        context_lines: Number of lines of context to include around matches
        
    Returns:
        HTML string containing relevant content
    """
    relevant_elements = []
    
    for term in search_terms:
        # Find elements containing the search term
        elements = soup.find_all(text=re.compile(term, re.IGNORECASE))
        for element in elements:
            # Get the parent element for better context
            parent = element.parent
            if parent and parent not in relevant_elements:
                relevant_elements.append(parent)
                
                # Also include nearby siblings for context
                for sibling in parent.find_next_siblings(limit=context_lines):
                    if sibling not in relevant_elements:
                        relevant_elements.append(sibling)
                
                for sibling in parent.find_previous_siblings(limit=context_lines):
                    if sibling not in relevant_elements:
                        relevant_elements.append(sibling)
    
    if not relevant_elements:
        # If no specific matches, return a general chunk from the beginning
        body = soup.find('body') or soup
        all_text_elements = body.find_all(text=True)
        if all_text_elements:
            # Get first few elements that contain meaningful text
            meaningful_elements = []
            for elem in all_text_elements[:50]:  # Limit to first 50 text elements
                if elem.parent and len(elem.strip()) > 5:
                    if elem.parent not in meaningful_elements:
                        meaningful_elements.append(elem.parent)
                    if len(meaningful_elements) >= 10:
                        break
            relevant_elements = meaningful_elements
    
    # Create a new soup with just the relevant elements
    if relevant_elements:
        # Create a container div
        container = soup.new_tag("div")
        for elem in relevant_elements:
            container.append(elem.extract())
        return str(container)
    
    return str(soup)[:2000]  # Fallback to first 2000 chars


def enhance_basic_info_extraction(soup: BeautifulSoup, current_report: Any) -> Dict[str, Any]:
    """
    Use AI to enhance basic information extraction for missing fields.
    
    Args:
        soup: BeautifulSoup object of the HTML document
        current_report: Current FundReport object with partially extracted data
        
    Returns:
        Dictionary with AI-extracted values for missing fields
    """
    missing_fields = {}
    ai_results = {}
    
    # Check which basic fields are missing
    if not current_report.net_asset_value:
        missing_fields['net_asset_value'] = 'decimal'
    if not current_report.total_net_assets:
        missing_fields['total_net_assets'] = 'decimal'
    if not current_report.fund_code:
        missing_fields['fund_code'] = 'string'
    if not current_report.fund_name:
        missing_fields['fund_name'] = 'string'
    
    if not missing_fields:
        return {}
    
    # Create schema for missing fields
    schema_parts = []
    for field, field_type in missing_fields.items():
        if field_type == 'decimal':
            schema_parts.append(f'"{field}": "number or null"')
        else:
            schema_parts.append(f'"{field}": "string or null"')
    
    schema = "{" + ", ".join(schema_parts) + "}"
    
    # Extract relevant HTML chunk
    search_terms = [
        "基金代码", "基金主代码", "基金名称", "基金简称", 
        "份额净值", "单位净值", "资产净值", "基金资产净值",
        "报告期末基金份额净值", "报告期末基金资产净值"
    ]
    
    html_chunk = extract_relevant_html_chunk(soup, search_terms)
    
    # Call AI extraction
    ai_results = prompt_for_extraction(html_chunk, schema)
    
    logger.info("ai_basic_info_extraction", 
                missing_fields=list(missing_fields.keys()),
                extracted_fields=list(ai_results.keys()))
    
    return ai_results


def enhance_table_extraction(soup: BeautifulSoup, table_type: str) -> Dict[str, Any]:
    """
    Use AI to extract table data when rule-based parsing fails.
    
    Args:
        soup: BeautifulSoup object of the HTML document
        table_type: Type of table to extract ('asset_allocation', 'top_holdings', 'industry_allocation')
        
    Returns:
        Dictionary with extracted table data
    """
    if table_type == "asset_allocation":
        search_terms = ["资产配置", "投资组合", "资产类别", "大类资产", "股票", "债券", "现金"]
        schema = """{
            "asset_allocations": [
                {
                    "asset_type": "string",
                    "market_value": "number or null",
                    "percentage": "number or null"
                }
            ]
        }"""
    elif table_type == "top_holdings":
        search_terms = ["前十大", "重仓股", "前10大", "主要持仓", "股票投资", "持股"]
        schema = """{
            "top_holdings": [
                {
                    "security_name": "string",
                    "security_code": "string or null",
                    "market_value": "number or null",
                    "percentage": "number or null",
                    "rank": "number"
                }
            ]
        }"""
    elif table_type == "industry_allocation":
        search_terms = ["行业配置", "行业分布", "行业投资", "申万行业", "行业分类"]
        schema = """{
            "industry_allocations": [
                {
                    "industry_name": "string",
                    "market_value": "number or null",
                    "percentage": "number or null"
                }
            ]
        }"""
    else:
        return {}
    
    # Extract relevant HTML chunk
    html_chunk = extract_relevant_html_chunk(soup, search_terms, context_lines=15)
    
    # Call AI extraction
    ai_results = prompt_for_extraction(html_chunk, schema)
    
    logger.info("ai_table_extraction", 
                table_type=table_type,
                extracted_count=len(ai_results.get(table_type.replace('_', '_'), [])))
    
    return ai_results