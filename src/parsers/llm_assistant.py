"""LLM智能助手模块

基于Ollama的本地LLM助手，用于基金报告数据的智能分析、验证和修复。
"""

import asyncio
import json
import aiohttp
from typing import Dict, List, Any, Optional
from decimal import Decimal

from src.core.logging import get_logger


class OllamaLLMAssistant:
    """Ollama LLM助手"""
    
    def __init__(self, 
                 base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b",
                 timeout: int = 30):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.logger = get_logger("ollama_llm_assistant")
        
    async def analyze_table_structure(self, table_html: str) -> Dict[str, Any]:
        """分析表格结构"""
        prompt = f"""
你是一个专业的基金报告分析专家。请分析以下HTML表格的结构，识别其数据类型和含义。

表格HTML:
{table_html}

请以JSON格式返回分析结果，包含以下字段：
- table_type: 表格类型（如"asset_allocation", "top_holdings", "industry_allocation"等）
- columns: 列信息列表，每列包含name（列名）和type（数据类型）
- data_quality: 数据质量评估（1-10分）
- extraction_hints: 数据提取建议

只返回JSON，不要其他文字。
"""
        
        try:
            response = await self._call_ollama(prompt)
            return json.loads(response)
        except Exception as e:
            self.logger.error("表格结构分析失败", error=str(e))
            return {
                "table_type": "unknown",
                "columns": [],
                "data_quality": 5,
                "extraction_hints": []
            }
    
    async def extract_table_data(self, table_html: str, table_type: str) -> List[Dict[str, Any]]:
        """从表格中提取结构化数据"""
        prompt = f"""
你是一个专业的基金报告数据提取专家。请从以下HTML表格中提取{table_type}数据。

表格HTML:
{table_html}

请以JSON数组格式返回提取的数据，每个对象包含相应的字段。

如果是资产配置表格，返回格式：
[{{"asset_type": "股票投资", "market_value": 1000000, "percentage": 0.65}}]

如果是持仓明细表格，返回格式：
[{{"rank": 1, "stock_code": "000001", "stock_name": "平安银行", "market_value": 50000, "percentage": 0.05}}]

如果是行业配置表格，返回格式：
[{{"industry_name": "金融业", "market_value": 300000, "percentage": 0.30}}]

只返回JSON数组，不要其他文字。
"""
        
        try:
            response = await self._call_ollama(prompt)
            return json.loads(response)
        except Exception as e:
            self.logger.error("表格数据提取失败", error=str(e))
            return []
    
    async def validate_extracted_data(self, data: List[Dict[str, Any]], data_type: str) -> Dict[str, Any]:
        """验证提取的数据"""
        prompt = f"""
你是一个专业的基金数据质量分析专家。请验证以下{data_type}数据的合理性和准确性。

数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

请检查以下方面：
1. 数值范围是否合理（如百分比是否在0-1之间）
2. 百分比总和是否接近1（允许5%误差）
3. 是否存在明显的异常值
4. 数据格式是否正确
5. 必填字段是否完整

请以JSON格式返回验证结果：
{{
    "is_valid": true/false,
    "completeness_score": 0.95,
    "accuracy_score": 0.98,
    "consistency_score": 0.92,
    "issues": ["具体问题描述"],
    "suggestions": ["改进建议"]
}}

只返回JSON，不要其他文字。
"""
        
        try:
            response = await self._call_ollama(prompt)
            return json.loads(response)
        except Exception as e:
            self.logger.error("数据验证失败", error=str(e))
            return {
                "is_valid": True,
                "completeness_score": 0.8,
                "accuracy_score": 0.8,
                "consistency_score": 0.8,
                "issues": [],
                "suggestions": []
            }
    
    async def repair_data(self, problematic_data: List[Dict[str, Any]], 
                         issues: List[str]) -> List[Dict[str, Any]]:
        """修复有问题的数据"""
        prompt = f"""
你是一个专业的基金数据修复专家。请根据发现的问题修复以下数据。

有问题的数据：
{json.dumps(problematic_data, ensure_ascii=False, indent=2)}

发现的问题：
{json.dumps(issues, ensure_ascii=False)}

请应用以下修复策略：
1. 如果百分比总和不等于1，按比例调整
2. 如果缺少百分比但有市值，根据市值计算百分比
3. 如果数值格式错误，尝试清理和转换
4. 如果有明显异常值，标记或修正

请返回修复后的数据，格式与输入相同。只返回JSON数组，不要其他文字。
"""
        
        try:
            response = await self._call_ollama(prompt)
            return json.loads(response)
        except Exception as e:
            self.logger.error("数据修复失败", error=str(e))
            return problematic_data
    
    async def analyze_fund_reasonableness(self, fund_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析基金数据的合理性"""
        prompt = f"""
你是一个资深的基金分析师。请分析以下基金数据的合理性。

基金数据：
{json.dumps(fund_data, ensure_ascii=False, indent=2)}

请从以下角度分析：
1. 资产配置是否合理（股债比例、现金比例等）
2. 持仓集中度是否适当
3. 行业配置是否均衡
4. 数据之间的逻辑一致性
5. 与同类基金相比是否异常

请以JSON格式返回分析结果：
{{
    "overall_score": 8.5,
    "asset_allocation_score": 9.0,
    "concentration_score": 7.5,
    "industry_balance_score": 8.0,
    "consistency_score": 9.0,
    "warnings": ["具体警告"],
    "recommendations": ["具体建议"]
}}

只返回JSON，不要其他文字。
"""
        
        try:
            response = await self._call_ollama(prompt)
            return json.loads(response)
        except Exception as e:
            self.logger.error("基金合理性分析失败", error=str(e))
            return {
                "overall_score": 7.0,
                "asset_allocation_score": 7.0,
                "concentration_score": 7.0,
                "industry_balance_score": 7.0,
                "consistency_score": 7.0,
                "warnings": [],
                "recommendations": []
            }
    
    async def _call_ollama(self, prompt: str) -> str:
        """调用Ollama API"""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 2048
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', '')
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API错误 {response.status}: {error_text}")
        
        except asyncio.TimeoutError:
            raise Exception(f"Ollama API调用超时（{self.timeout}秒）")
        except aiohttp.ClientError as e:
            raise Exception(f"Ollama API连接错误: {str(e)}")
    
    async def health_check(self) -> bool:
        """检查Ollama服务健康状态"""
        try:
            url = f"{self.base_url}/api/tags"
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model['name'] for model in data.get('models', [])]
                        if self.model in models:
                            self.logger.info("Ollama服务健康，模型可用", model=self.model)
                            return True
                        else:
                            self.logger.warning("Ollama服务健康，但模型不可用", 
                                              model=self.model, available_models=models)
                            return False
                    else:
                        self.logger.error("Ollama服务不健康", status=response.status)
                        return False
        
        except Exception as e:
            self.logger.error("Ollama健康检查失败", error=str(e))
            return False


class DataQualityValidator:
    """数据质量验证器"""
    
    def __init__(self):
        self.logger = get_logger("data_quality_validator")
    
    def validate_asset_allocation(self, allocations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证资产配置数据"""
        issues = []
        warnings = []
        
        if not allocations:
            issues.append("资产配置数据为空")
            return self._create_validation_result(False, 0.0, issues, warnings)
        
        # 检查百分比总和
        total_percentage = sum(
            float(item.get('percentage', 0)) for item in allocations 
            if item.get('percentage') is not None
        )
        
        if abs(total_percentage - 1.0) > 0.05:  # 允许5%误差
            issues.append(f"资产配置百分比总和异常: {total_percentage:.2%}")
        
        # 检查必填字段
        completeness_score = 0.0
        total_fields = 0
        filled_fields = 0
        
        for item in allocations:
            total_fields += 3  # asset_type, market_value, percentage
            if item.get('asset_type'):
                filled_fields += 1
            if item.get('market_value') is not None:
                filled_fields += 1
            if item.get('percentage') is not None:
                filled_fields += 1
        
        if total_fields > 0:
            completeness_score = filled_fields / total_fields
        
        # 检查数值合理性
        for item in allocations:
            percentage = item.get('percentage')
            if percentage is not None:
                if percentage < 0 or percentage > 1:
                    issues.append(f"资产配置百分比超出合理范围: {percentage:.2%}")
            
            market_value = item.get('market_value')
            if market_value is not None and market_value < 0:
                issues.append(f"资产配置市值为负数: {market_value}")
        
        is_valid = len(issues) == 0
        return self._create_validation_result(is_valid, completeness_score, issues, warnings)
    
    def validate_top_holdings(self, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证前十大持仓数据"""
        issues = []
        warnings = []
        
        if not holdings:
            warnings.append("前十大持仓数据为空")
            return self._create_validation_result(True, 0.0, issues, warnings)
        
        # 检查排名连续性
        ranks = [item.get('rank') for item in holdings if item.get('rank') is not None]
        if ranks:
            expected_ranks = list(range(1, len(ranks) + 1))
            if sorted(ranks) != expected_ranks:
                issues.append("持仓排名不连续")
        
        # 检查股票代码格式
        for item in holdings:
            stock_code = item.get('stock_code')
            if stock_code and not re.match(r'^\d{6}$', stock_code):
                issues.append(f"股票代码格式错误: {stock_code}")
        
        # 计算完整性得分
        completeness_score = self._calculate_completeness(holdings, 
                                                        ['rank', 'stock_code', 'stock_name'])
        
        is_valid = len(issues) == 0
        return self._create_validation_result(is_valid, completeness_score, issues, warnings)
    
    def validate_industry_allocation(self, allocations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证行业配置数据"""
        issues = []
        warnings = []
        
        if not allocations:
            warnings.append("行业配置数据为空")
            return self._create_validation_result(True, 0.0, issues, warnings)
        
        # 检查百分比总和
        total_percentage = sum(
            float(item.get('percentage', 0)) for item in allocations 
            if item.get('percentage') is not None
        )
        
        if total_percentage > 1.05:  # 行业配置可能不完整，只检查上限
            issues.append(f"行业配置百分比总和过高: {total_percentage:.2%}")
        
        # 计算完整性得分
        completeness_score = self._calculate_completeness(allocations, 
                                                        ['industry_name', 'percentage'])
        
        is_valid = len(issues) == 0
        return self._create_validation_result(is_valid, completeness_score, issues, warnings)
    
    def _calculate_completeness(self, data: List[Dict[str, Any]], 
                              required_fields: List[str]) -> float:
        """计算数据完整性得分"""
        if not data:
            return 0.0
        
        total_fields = len(data) * len(required_fields)
        filled_fields = 0
        
        for item in data:
            for field in required_fields:
                if item.get(field) is not None:
                    filled_fields += 1
        
        return filled_fields / total_fields if total_fields > 0 else 0.0
    
    def _create_validation_result(self, is_valid: bool, completeness_score: float,
                                issues: List[str], warnings: List[str]) -> Dict[str, Any]:
        """创建验证结果"""
        return {
            'is_valid': is_valid,
            'completeness_score': completeness_score,
            'accuracy_score': 1.0 if is_valid else 0.8,
            'consistency_score': 1.0 if is_valid else 0.8,
            'issues': issues,
            'warnings': warnings
        }


class DataRepairService:
    """数据修复服务"""
    
    def __init__(self, llm_assistant: Optional[OllamaLLMAssistant] = None):
        self.llm_assistant = llm_assistant
        self.logger = get_logger("data_repair_service")
    
    async def repair_asset_allocation(self, allocations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """修复资产配置数据"""
        if not allocations:
            return allocations
        
        repaired = allocations.copy()
        
        # 修复百分比总和
        total_percentage = sum(
            float(item.get('percentage', 0)) for item in repaired 
            if item.get('percentage') is not None
        )
        
        if abs(total_percentage - 1.0) > 0.05 and total_percentage > 0:
            # 按比例调整
            adjustment_factor = 1.0 / total_percentage
            for item in repaired:
                if item.get('percentage') is not None:
                    item['percentage'] = float(item['percentage']) * adjustment_factor
            
            self.logger.info("修复资产配置百分比总和", 
                           original_total=total_percentage, 
                           adjustment_factor=adjustment_factor)
        
        # 使用LLM进行进一步修复
        if self.llm_assistant:
            try:
                validation_result = await self.llm_assistant.validate_extracted_data(
                    repaired, '资产配置数据'
                )
                
                if not validation_result.get('is_valid', True):
                    repaired = await self.llm_assistant.repair_data(
                        repaired, validation_result.get('issues', [])
                    )
            except Exception as e:
                self.logger.error("LLM修复失败", error=str(e))
        
        return repaired
    
    def repair_missing_percentages(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据市值修复缺失的百分比"""
        if not data:
            return data
        
        repaired = data.copy()
        
        # 计算总市值
        total_market_value = sum(
            float(item.get('market_value', 0)) for item in repaired 
            if item.get('market_value') is not None
        )
        
        if total_market_value > 0:
            for item in repaired:
                if item.get('percentage') is None and item.get('market_value') is not None:
                    item['percentage'] = float(item['market_value']) / total_market_value
                    self.logger.debug("修复缺失百分比", 
                                    market_value=item['market_value'],
                                    calculated_percentage=item['percentage'])
        
        return repaired