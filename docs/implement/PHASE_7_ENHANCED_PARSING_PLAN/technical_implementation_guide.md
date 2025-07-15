# 技术实施指南

## 专业XBRL库集成方案

### 1. XBRL库选择和配置

#### 1.1 推荐的XBRL库
```python
# requirements.txt 中的XBRL相关依赖
arelle>=2.20.0              # 专业XBRL处理库，SEC官方推荐
python-xbrl>=1.1.0          # 轻量级XBRL解析库
lxml>=4.9.0                 # XML解析性能优化
beautifulsoup4>=4.11.0      # HTML结构解析
pandas>=1.5.0               # 数据处理和分析
```

#### 1.2 Arelle集成示例
```python
from arelle import Cntlr, ModelManager, FileSource
from arelle.ModelDocument import ModelDocument
import logging

class ArelleXBRLParser:
    """基于Arelle的专业XBRL解析器"""
    
    def __init__(self):
        # 初始化Arelle控制器
        self.controller = Cntlr.Cntlr(logFileName="arelle.log")
        self.model_manager = ModelManager.initialize(self.controller)
        
        # 配置日志级别
        logging.getLogger("arelle").setLevel(logging.WARNING)
    
    def parse_xbrl_file(self, file_path: str) -> Dict:
        """解析XBRL文件并提取标准化数据"""
        try:
            # 加载XBRL文档
            file_source = FileSource.FileSource(file_path)
            model_xbrl = self.model_manager.load(file_source)
            
            if model_xbrl is None:
                raise ValueError(f"无法加载XBRL文件: {file_path}")
            
            # 提取基本信息
            basic_info = self._extract_basic_info(model_xbrl)
            
            # 提取财务数据
            financial_data = self._extract_financial_facts(model_xbrl)
            
            # 提取表格数据
            table_data = self._extract_table_data(model_xbrl)
            
            return {
                'basic_info': basic_info,
                'financial_data': financial_data,
                'table_data': table_data,
                'parsing_status': 'SUCCESS'
            }
            
        except Exception as e:
            logging.error(f"XBRL解析失败: {e}")
            return {
                'parsing_status': 'FAILED',
                'error_message': str(e)
            }
        finally:
            if 'model_xbrl' in locals() and model_xbrl:
                model_xbrl.close()
    
    def _extract_basic_info(self, model_xbrl) -> Dict:
        """提取基金基本信息"""
        basic_info = {}
        
        # 提取实体信息
        for fact in model_xbrl.facts:
            if fact.concept.name in ['FundName', 'FundCode', 'ReportDate']:
                basic_info[fact.concept.name] = fact.value
        
        return basic_info
    
    def _extract_financial_facts(self, model_xbrl) -> List[Dict]:
        """提取财务事实数据"""
        financial_facts = []
        
        for fact in model_xbrl.facts:
            if fact.isNumeric:
                financial_facts.append({
                    'concept': fact.concept.name,
                    'value': fact.value,
                    'unit': fact.unit.id if fact.unit else None,
                    'context': fact.context.id if fact.context else None,
                    'period': self._extract_period(fact.context) if fact.context else None
                })
        
        return financial_facts
    
    def _extract_table_data(self, model_xbrl) -> List[Dict]:
        """提取表格结构数据"""
        # 处理XBRL表格和维度数据
        table_data = []
        
        # 遍历表格链接
        for table_linkrole in model_xbrl.relationshipSet("Table-rendering").linkRoleUris:
            table_info = {
                'linkrole': table_linkrole,
                'axes': [],
                'facts': []
            }
            
            # 提取表格轴和事实
            # ... 具体实现根据XBRL表格结构
            
            table_data.append(table_info)
        
        return table_data
```

### 2. LLM辅助解析集成

#### 2.1 Ollama客户端配置
```python
import ollama
import json
from typing import Dict, List, Optional
import asyncio

class OllamaLLMAssistant:
    """Ollama LLM辅助解析器"""
    
    def __init__(self, model_name: str = "qwen2.5:7b", host: str = "http://localhost:11434"):
        self.client = ollama.Client(host=host)
        self.model_name = model_name
        self._ensure_model_available()
    
    def _ensure_model_available(self):
        """确保模型可用"""
        try:
            models = self.client.list()
            available_models = [model['name'] for model in models['models']]
            
            if self.model_name not in available_models:
                print(f"正在下载模型 {self.model_name}...")
                self.client.pull(self.model_name)
                print("模型下载完成")
                
        except Exception as e:
            print(f"模型检查失败: {e}")
            raise
    
    async def analyze_table_structure(self, html_table: str) -> Dict:
        """分析复杂表格结构"""
        prompt = f"""
        请分析以下HTML表格的结构，识别表头、数据行和列的含义：

        {html_table[:2000]}  # 限制输入长度

        请以JSON格式返回分析结果，包含：
        1. headers: 表头信息
        2. data_types: 各列的数据类型
        3. structure_type: 表格类型（如：资产配置表、持仓明细表等）
        4. extraction_strategy: 建议的数据提取策略

        返回格式：
        {{
            "headers": ["列名1", "列名2", ...],
            "data_types": ["text", "number", "percentage", ...],
            "structure_type": "表格类型",
            "extraction_strategy": "提取策略描述"
        }}
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': 0.1}  # 降低随机性
            )
            
            # 解析JSON响应
            result_text = response['response']
            # 提取JSON部分
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = result_text[json_start:json_end]
                return json.loads(json_text)
            else:
                return self._fallback_structure_analysis(html_table)
                
        except Exception as e:
            print(f"LLM表格分析失败: {e}")
            return self._fallback_structure_analysis(html_table)
    
    async def validate_extracted_data(self, data: Dict, context: str) -> Dict:
        """验证提取数据的合理性"""
        prompt = f"""
        请验证以下基金报告数据的合理性：

        数据类型：{context}
        数据内容：{json.dumps(data, ensure_ascii=False, indent=2)}

        请检查：
        1. 数值是否在合理范围内
        2. 比例数据是否加总为100%
        3. 是否存在明显的异常值
        4. 数据格式是否正确

        返回JSON格式的验证结果：
        {{
            "is_valid": true/false,
            "issues": ["问题描述1", "问题描述2", ...],
            "suggestions": ["修复建议1", "修复建议2", ...],
            "confidence": 0.95
        }}
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': 0.1}
            )
            
            result_text = response['response']
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = result_text[json_start:json_end]
                return json.loads(json_text)
            else:
                return {'is_valid': True, 'issues': [], 'suggestions': [], 'confidence': 0.5}
                
        except Exception as e:
            print(f"LLM数据验证失败: {e}")
            return {'is_valid': True, 'issues': [], 'suggestions': [], 'confidence': 0.0}
    
    def _fallback_structure_analysis(self, html_table: str) -> Dict:
        """备用的表格结构分析"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_table, 'html.parser')
        headers = []
        
        # 尝试提取表头
        header_row = soup.find('tr', class_='cc') or soup.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        return {
            'headers': headers,
            'data_types': ['text'] * len(headers),
            'structure_type': 'unknown',
            'extraction_strategy': 'standard_table_parsing'
        }
```

#### 2.2 智能解析流程集成
```python
class HybridXBRLParser:
    """混合XBRL解析器：结合专业库和LLM"""
    
    def __init__(self):
        self.arelle_parser = ArelleXBRLParser()
        self.llm_assistant = OllamaLLMAssistant()
        self.html_parser = BeautifulSoup
    
    async def parse_report_hybrid(self, file_path: str) -> Dict:
        """混合解析策略"""
        results = {
            'xbrl_data': {},
            'html_data': {},
            'llm_enhanced_data': {},
            'final_data': {}
        }
        
        try:
            # 1. 专业XBRL库解析
            print("开始XBRL标准解析...")
            results['xbrl_data'] = self.arelle_parser.parse_xbrl_file(file_path)
            
            # 2. HTML结构解析
            print("开始HTML结构解析...")
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            results['html_data'] = await self._parse_html_content(html_content)
            
            # 3. LLM增强解析
            print("开始LLM增强解析...")
            results['llm_enhanced_data'] = await self._llm_enhance_parsing(
                results['html_data'], html_content
            )
            
            # 4. 数据融合和验证
            print("开始数据融合...")
            results['final_data'] = await self._merge_and_validate(
                results['xbrl_data'],
                results['html_data'],
                results['llm_enhanced_data']
            )
            
            return results
            
        except Exception as e:
            print(f"混合解析失败: {e}")
            results['error'] = str(e)
            return results
    
    async def _parse_html_content(self, html_content: str) -> Dict:
        """解析HTML内容"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 提取表格
        tables = soup.find_all('table', class_='bb')
        parsed_tables = []
        
        for i, table in enumerate(tables):
            table_data = {
                'table_id': i,
                'html': str(table),
                'rows': []
            }
            
            for row in table.find_all('tr'):
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if cells:  # 过滤空行
                    table_data['rows'].append(cells)
            
            parsed_tables.append(table_data)
        
        return {'tables': parsed_tables}
    
    async def _llm_enhance_parsing(self, html_data: Dict, html_content: str) -> Dict:
        """LLM增强解析"""
        enhanced_data = {'enhanced_tables': []}
        
        for table_data in html_data.get('tables', []):
            if len(table_data['rows']) > 1:  # 有数据的表格
                # LLM分析表格结构
                structure = await self.llm_assistant.analyze_table_structure(
                    table_data['html']
                )
                
                # 基于LLM分析结果提取数据
                enhanced_table = {
                    'original_table_id': table_data['table_id'],
                    'structure_analysis': structure,
                    'extracted_data': self._extract_data_by_structure(
                        table_data['rows'], structure
                    )
                }
                
                enhanced_data['enhanced_tables'].append(enhanced_table)
        
        return enhanced_data
    
    def _extract_data_by_structure(self, rows: List[List[str]], structure: Dict) -> List[Dict]:
        """根据结构分析结果提取数据"""
        if not rows or len(rows) < 2:
            return []
        
        headers = structure.get('headers', rows[0])
        data_types = structure.get('data_types', ['text'] * len(headers))
        
        extracted_data = []
        for row in rows[1:]:  # 跳过表头
            if len(row) >= len(headers):
                row_data = {}
                for i, (header, cell_value, data_type) in enumerate(zip(headers, row, data_types)):
                    row_data[header] = self._convert_cell_value(cell_value, data_type)
                extracted_data.append(row_data)
        
        return extracted_data
    
    def _convert_cell_value(self, value: str, data_type: str) -> any:
        """根据数据类型转换单元格值"""
        if not value or value == '-':
            return None
        
        try:
            if data_type == 'number':
                # 处理千分位分隔符
                clean_value = value.replace(',', '').replace('，', '')
                return float(clean_value)
            elif data_type == 'percentage':
                clean_value = value.replace('%', '').replace(',', '')
                return float(clean_value) / 100
            else:
                return value.strip()
        except:
            return value
    
    async def _merge_and_validate(self, xbrl_data: Dict, html_data: Dict, llm_data: Dict) -> Dict:
        """合并和验证数据"""
        merged_data = {
            'fund_basic_info': {},
            'asset_allocation': [],
            'stock_holdings': [],
            'bond_holdings': [],
            'financial_metrics': []
        }
        
        # 数据合并逻辑
        # 优先使用XBRL标准数据，HTML数据作为补充，LLM数据用于验证和修正
        
        # 验证合并后的数据
        for data_type, data_content in merged_data.items():
            if data_content:
                validation_result = await self.llm_assistant.validate_extracted_data(
                    data_content, data_type
                )
                merged_data[f'{data_type}_validation'] = validation_result
        
        return merged_data
```

### 3. 部署和配置指南

#### 3.1 环境配置
```bash
# 1. 安装Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. 启动Ollama服务
ollama serve

# 3. 下载推荐模型
ollama pull qwen2.5:7b
ollama pull llama3.1:8b

# 4. 安装Python依赖
pip install -r requirements.txt
```

#### 3.2 配置文件示例
```yaml
# config/parser_config.yaml
xbrl_parser:
  arelle:
    log_level: WARNING
    validate_xbrl: true
    load_dtd: false
  
llm_assistant:
  model_name: "qwen2.5:7b"
  host: "http://localhost:11434"
  timeout: 30
  max_retries: 3
  
data_quality:
  validation_thresholds:
    completeness_min: 0.8
    accuracy_min: 0.95
    consistency_min: 0.9
  
performance:
  max_concurrent_parsing: 4
  memory_limit_mb: 2048
  timeout_seconds: 300
```

这个技术实施指南提供了详细的代码示例和配置方案，确保开发团队能够高质量地实现XBRL解析器，充分利用专业库和LLM的优势。
