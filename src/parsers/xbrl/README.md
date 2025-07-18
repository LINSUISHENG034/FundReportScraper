# XBRL解析引擎API文档（XBRL API DOCUMENTATION）

本文档说明如何使用XBRL解析引擎的三个核心模块：`TaxonomyManager`、`XBRLContext`和`FactExtractor`。

## 模块概述

### TaxonomyManager (分类标准管理器)
负责加载并查询XBRL分类标准元数据的服务。

### XBRLContext (XBRL上下文解析器)
负责解析XBRL报告中所有上下文（context）并提供查询功能。

### FactExtractor (事实提取器)
负责从XBRL报告中提取所有事实（Facts）的工具。

## 使用示例

### 1. TaxonomyManager 使用方法

```python
from src.parsers.xbrl import TaxonomyManager

# 初始化分类标准管理器
taxonomy_manager = TaxonomyManager('reference/XBRL分类标准框架/')

# 加载分类标准
taxonomy_manager.load_taxonomy()

# 查询元素详情
element_details = taxonomy_manager.get_element_details('cfi:Assets')
print(f"元素名称: {element_details['name']}")
print(f"中文标签: {element_details['label']}")
print(f"数据类型: {element_details['type']}")

# 根据标签搜索元素
results = taxonomy_manager.search_elements_by_label('资产')
for element in results:
    print(f"{element['id']}: {element['label']}")

# 获取所有元素
all_elements = taxonomy_manager.get_all_elements()
print(f"共加载 {len(all_elements)} 个元素")
```

### 2. XBRLContext 使用方法

```python
from src.parsers.xbrl import XBRLContext
from bs4 import BeautifulSoup
from lxml import etree

# 使用BeautifulSoup解析
soup = BeautifulSoup(xbrl_content, 'lxml')
context_parser = XBRLContext(soup)

# 或使用lxml解析
# doc = etree.fromstring(xbrl_content)
# context_parser = XBRLContext(doc)

# 解析上下文
context_parser.parse_contexts()

# 查询特定上下文
context_details = context_parser.get_context_details('c-1')
print(f"实体标识符: {context_details['entity']['identifier']}")
print(f"期间类型: {context_details['period']['type']}")

# 根据实体标识符查询上下文
contexts = context_parser.get_contexts_by_entity('001056')
print(f"基金001056共有 {len(contexts)} 个上下文")

# 根据期间类型查询上下文
instant_contexts = context_parser.get_contexts_by_period_type('instant')
duration_contexts = context_parser.get_contexts_by_period_type('duration')

# 获取所有上下文
all_contexts = context_parser.get_all_contexts()
print(f"共解析 {len(all_contexts)} 个上下文")
```

### 3. FactExtractor 使用方法

```python
from src.parsers.xbrl import FactExtractor
from bs4 import BeautifulSoup
from lxml import etree

# 使用BeautifulSoup解析
soup = BeautifulSoup(xbrl_content, 'lxml')
fact_extractor = FactExtractor(soup)

# 或使用lxml解析
# doc = etree.fromstring(xbrl_content)
# fact_extractor = FactExtractor(doc)

# 提取所有事实
fact_extractor.extract_facts()

# 获取所有事实
all_facts = fact_extractor.get_all_facts()
print(f"共提取 {len(all_facts)} 个事实")

# 根据名称查询事实
assets_facts = fact_extractor.get_facts_by_name('cfi:Assets')
for fact in assets_facts:
    print(f"资产总计: {fact['value']} (上下文: {fact['contextRef']})")

# 根据上下文查询事实
context_facts = fact_extractor.get_facts_by_context('c-1')
print(f"上下文c-1包含 {len(context_facts)} 个事实")

# 根据命名空间查询事实
cfi_facts = fact_extractor.get_facts_by_namespace('cfi')
print(f"cfi命名空间包含 {len(cfi_facts)} 个事实")

# 获取不同类型的事实
numeric_facts = fact_extractor.get_numeric_facts()
text_facts = fact_extractor.get_text_facts()
boolean_facts = fact_extractor.get_boolean_facts()

print(f"数值型事实: {len(numeric_facts)}")
print(f"文本型事实: {len(text_facts)}")
print(f"布尔型事实: {len(boolean_facts)}")

# 获取事实统计信息
stats = fact_extractor.get_fact_statistics()
print(f"事实统计: {stats}")
```

### 4. 综合使用示例

```python
from src.parsers.xbrl import TaxonomyManager, XBRLContext, FactExtractor
from bs4 import BeautifulSoup

# 读取XBRL文件
with open('sample.xbrl', 'r', encoding='utf-8') as f:
    xbrl_content = f.read()

# 解析文档
soup = BeautifulSoup(xbrl_content, 'lxml')

# 1. 加载分类标准
taxonomy_manager = TaxonomyManager('reference/XBRL分类标准框架/')
taxonomy_manager.load_taxonomy()

# 2. 解析上下文
context_parser = XBRLContext(soup)
context_parser.parse_contexts()

# 3. 提取事实
fact_extractor = FactExtractor(soup)
fact_extractor.extract_facts()

# 4. 综合分析
all_facts = fact_extractor.get_all_facts()
for fact in all_facts:
    # 获取元素的中文标签
    element_details = taxonomy_manager.get_element_details(fact['name'])
    chinese_label = element_details['label'] if element_details else fact['name']
    
    # 获取上下文详情
    context_details = context_parser.get_context_details(fact['contextRef'])
    entity = context_details['entity']['identifier'] if context_details else 'Unknown'
    
    print(f"{chinese_label}: {fact['value']} (基金: {entity})")
```

## API参考

### TaxonomyManager

#### 构造函数
- `__init__(taxonomy_root_path: str)`: 初始化分类标准管理器

#### 方法
- `load_taxonomy() -> None`: 加载分类标准
- `get_element_details(element_id: str) -> Optional[Dict]`: 获取元素详情
- `search_elements_by_label(label_keyword: str) -> List[Dict]`: 根据标签搜索元素
- `get_all_elements() -> Dict[str, Dict]`: 获取所有元素

#### 属性
- `is_loaded: bool`: 检查是否已加载
- `element_count: int`: 获取元素数量

### XBRLContext

#### 构造函数
- `__init__(document: Union[BeautifulSoup, etree._Element])`: 初始化上下文解析器

#### 方法
- `parse_contexts() -> None`: 解析所有上下文
- `get_context_details(context_id: str) -> Optional[Dict]`: 获取上下文详情
- `get_contexts_by_entity(entity_identifier: str) -> List[Dict]`: 根据实体查询上下文
- `get_contexts_by_period_type(period_type: str) -> List[Dict]`: 根据期间类型查询上下文
- `get_all_contexts() -> Dict[str, Dict]`: 获取所有上下文

#### 属性
- `is_parsed: bool`: 检查是否已解析
- `context_count: int`: 获取上下文数量

### FactExtractor

#### 构造函数
- `__init__(document: Union[BeautifulSoup, etree._Element])`: 初始化事实提取器

#### 方法
- `extract_facts() -> None`: 提取所有事实
- `get_all_facts() -> List[Dict]`: 获取所有事实
- `get_facts_by_name(fact_name: str) -> List[Dict]`: 根据名称查询事实
- `get_facts_by_context(context_ref: str) -> List[Dict]`: 根据上下文查询事实
- `get_facts_by_namespace(namespace: str) -> List[Dict]`: 根据命名空间查询事实
- `get_numeric_facts() -> List[Dict]`: 获取数值型事实
- `get_text_facts() -> List[Dict]`: 获取文本型事实
- `get_boolean_facts() -> List[Dict]`: 获取布尔型事实
- `get_fact_statistics() -> Dict`: 获取事实统计信息

#### 属性
- `is_extracted: bool`: 检查是否已提取
- `fact_count: int`: 获取事实数量

## 注意事项

1. **分类标准文件**: TaxonomyManager需要XSD和标签文件，如果没有实际的分类标准文件，可以使用测试中的模拟数据。

2. **文档格式**: XBRLContext和FactExtractor支持BeautifulSoup和lxml两种解析方式，建议根据文档格式选择合适的解析器。

3. **错误处理**: 所有模块都包含适当的错误处理和日志记录，使用时请注意检查返回值。

4. **性能考虑**: 对于大型XBRL文档，建议使用lxml解析器以获得更好的性能。

5. **编码问题**: 确保XBRL文档使用正确的编码（通常是UTF-8）。