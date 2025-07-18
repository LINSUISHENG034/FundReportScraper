"""XBRL事实提取器

负责从XBRL报告中提取所有事实（Facts）的工具。
"""

from typing import Dict, List, Optional
from lxml import etree
from src.core.logging import get_logger

logger = get_logger(__name__)


class FactExtractor:
    """XBRL事实提取器
    
    负责从XBRL报告中提取所有事实（Facts）的工具。
    """
    
    def __init__(self, document: etree._Element):
        """初始化事实提取器
        
        Args:
            document: 已解析的lxml Element对象
        """
        self.document = document
        self.facts: List[Dict] = []
        self._extracted = False
    
    def extract_facts(self) -> List[Dict]:
        """从XBRL文档中提取所有事实
        
        Returns:
            包含所有事实的列表
        """
        try:
            logger.info("开始提取XBRL事实...")
            
            # 重新初始化事实列表
            self.facts = []
            
            # 提取事实
            self._extract_facts()
            
            self._extracted = True
            logger.info(f"事实提取完成，共提取 {len(self.facts)} 个事实")
            
            return self.facts.copy()
            
        except Exception as e:
            logger.error(f"提取事实失败: {e}")
            raise
    
    def _determine_fact_type(self, value: str, unit_ref: str = None, decimals: str = None) -> str:
        """判断事实类型
        
        Args:
            value: 事实值
            unit_ref: 单位引用
            decimals: 小数位数
            
        Returns:
            事实类型: 'numeric', 'boolean', 'text'
        """
        if not value:
            return 'text'
        
        value_str = str(value).strip()
        
        # 检查是否包含非ASCII字符（如中文），直接判断为文本
        if any(ord(char) > 127 for char in value_str):
            return 'text'
        
        # 如果有单位引用或小数位数，通常是数值型
        if unit_ref or decimals:
            return 'numeric'
        
        # 检查是否为布尔值（但不包括纯数字1和0，除非它们是单独的字符）
        if value_str.lower() in ['true', 'false']:
            return 'boolean'
        elif value_str in ['1', '0'] and len(value_str) == 1:
            return 'boolean'
        
        # 检查是否为以0开头的数字字符串（如基金代码），应该视为文本
        if value_str.startswith('0') and len(value_str) > 1 and value_str.isdigit():
            return 'text'
        
        # 尝试解析为数值
        try:
            float(value_str)
            return 'numeric'
        except (ValueError, TypeError):
            pass
        
        return 'text'
    
    def _parse_numeric_value(self, value: str):
        """解析数值
        
        Args:
            value: 字符串值
            
        Returns:
            Decimal对象或None
        """
        if not value:
            return None
        
        try:
            from decimal import Decimal
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            return None
    
    def _parse_boolean_value(self, value: str):
        """解析布尔值
        
        Args:
            value: 字符串值
            
        Returns:
            布尔值或None
        """
        if not value:
            return None
        
        value_lower = value.lower().strip()
        if value_lower in ['true', '1']:
            return True
        elif value_lower in ['false', '0']:
            return False
        
        return None
    
    def _extract_namespace(self, name: str) -> str:
        """从名称中提取命名空间
        
        Args:
            name: 元素名称
            
        Returns:
            命名空间前缀或None
        """
        if not name or ':' not in name:
            return None
        
        return name.split(':', 1)[0]
    
    def _extract_facts(self) -> None:
        """
        提取事实的核心逻辑。
        根据项目测试，一个元素被视为“事实”如果：
        1. 它有 `contextRef` (标准XBRL).
        2. 它有 `unitRef` (数值型事实).
        3. 它有 `name` 属性 (iXBRL).
        4. 它是非XBRL标准命名空间中的任何其他元素 (项目特定数据).
        """
        # This final XPath combines specific selectors for performance with a general
        # selector for custom data elements, as required by the tests.
        fact_elements = self.document.xpath(
            '//*[@contextRef] | //*[@contextref] | '
            '//*[@unitRef] | //*[@unitref] | '
            '//span[@name] | '
            '//*[namespace-uri() and '
            '    namespace-uri() != "http://www.xbrl.org/2003/instance" and '
            '    namespace-uri() != "http://www.xbrl.org/2003/linkbase" and '
            '    namespace-uri() != "http://www.w3.org/1999/xhtml"]'
        )
        
        nsmap = self.document.nsmap
        
        processed_elements = set()
        for fact_elem in fact_elements:
            # Skip duplicates and known structural elements
            if fact_elem in processed_elements or self._is_structural_element(fact_elem):
                continue
            processed_elements.add(fact_elem)
            
            fact_data = self._extract_fact_data(fact_elem, nsmap)
            if fact_data:
                self.facts.append(fact_data)

    def _is_structural_element(self, elem: etree._Element) -> bool:
        """Helper to identify and skip structural XBRL elements."""
        tag = elem.tag
        local_name = tag.split('}')[-1] if '}' in tag else tag
        
        # These elements define the structure but are not facts themselves.
        structural_tags = {'xbrl', 'context', 'unit', 'schemaRef', 'linkbaseRef', 'roleRef', 'arcroleRef'}
        
        return local_name in structural_tags

    def _extract_fact_data(self, fact_elem, nsmap: Dict) -> Optional[Dict]:
        """从lxml元素中提取单个事实的数据"""
        try:
            # Handle iXBRL 'name' attribute for fact identification
            name_attr = fact_elem.get('name')
            if name_attr:
                full_name = name_attr
                namespace_prefix, local_name = full_name.split(':', 1) if ':' in full_name else (None, full_name)
                namespace_uri = None # Cannot be determined from name attribute alone
            else:
                tag = fact_elem.tag
                if '}' in tag:
                    namespace_uri, local_name = tag.split('}', 1)
                    namespace_uri = namespace_uri[1:]
                    namespace_prefix = self._get_namespace_prefix(namespace_uri, nsmap)
                    full_name = f"{namespace_prefix}:{local_name}" if namespace_prefix else local_name
                else:
                    namespace_uri, namespace_prefix, local_name, full_name = None, None, tag, tag

            raw_value = self._extract_value(fact_elem)
            
            # Handle both XML (camelCase) and HTML (lowercase) attribute conventions
            unit_ref = fact_elem.get('unitRef') or fact_elem.get('unitref')
            decimals = fact_elem.get('decimals')
            context_ref = fact_elem.get('contextRef') or fact_elem.get('contextref')
            
            fact_type = self._determine_fact_type(raw_value, unit_ref, decimals)
            
            parsed_value = raw_value
            if fact_type == 'numeric':
                parsed_value = self._parse_numeric_value(raw_value)
            elif fact_type == 'boolean':
                parsed_value = self._parse_boolean_value(raw_value)

            return {
                'name': full_name,
                'localName': local_name,
                'namespace': namespace_prefix,
                'namespaceUri': namespace_uri,
                'value': parsed_value if parsed_value is not None else raw_value,
                'type': fact_type,
                'contextRef': context_ref,
                'unitRef': unit_ref,
                'decimals': decimals,
                'id': fact_elem.get('id'),
            }
            
        except Exception as e:
            logger.warning(f"提取单个事实数据失败: {e}", exc_info=True)
            return None
    
    def _extract_value(self, fact_elem) -> Optional[str]:
        """从lxml元素中提取值
        
        Args:
            fact_elem: lxml事实元素
            
        Returns:
            事实的文本值
        """
        try:
            # 如果元素有子元素，可能是复杂内容
            if len(fact_elem) > 0:
                # 返回完整的XML内容
                return etree.tostring(fact_elem, encoding='unicode', method='xml')
            else:
                # 返回纯文本内容
                text = fact_elem.text
                return text.strip() if text else None
                
        except Exception as e:
            logger.warning(f"提取事实值失败: {e}")
            return None
    
    def _get_namespace_prefix(self, namespace_uri: str, namespaces: Dict) -> Optional[str]:
        """根据命名空间URI获取前缀
        
        Args:
            namespace_uri: 命名空间URI
            namespaces: 命名空间字典
            
        Returns:
            命名空间前缀
        """
        # 从动态获取的命名空间中查找
        for prefix, uri in namespaces.items():
            if uri == namespace_uri:
                return prefix
        
        # 如果找不到，尝试从URI推断
        if '/' in namespace_uri:
            parts = namespace_uri.rstrip('/').split('/')
            return parts[-1] if parts else None
        
        return None
    
    
    def get_facts_by_name(self, fact_name: str) -> List[Dict]:
        """根据事实名称获取事实
        
        Args:
            fact_name: 事实名称
            
        Returns:
            匹配的事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            if fact.get('name') == fact_name or fact.get('localName') == fact_name:
                results.append(fact)
        
        return results
    
    def get_facts_by_context(self, context_ref: str) -> List[Dict]:
        """根据上下文引用获取事实
        
        Args:
            context_ref: 上下文引用ID
            
        Returns:
            匹配的事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            if fact.get('contextRef') == context_ref:
                results.append(fact)
        
        return results
    
    def get_facts_by_namespace(self, namespace: str) -> List[Dict]:
        """根据命名空间获取事实
        
        Args:
            namespace: 命名空间前缀
            
        Returns:
            匹配的事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            if fact.get('namespace') == namespace:
                results.append(fact)
        
        return results
    
    def get_numeric_facts(self) -> List[Dict]:
        """获取所有数值型事实
        
        Returns:
            数值型事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            # 基于事实类型判断
            if fact.get('type') == 'numeric':
                results.append(fact)
        
        return results
    
    def get_boolean_facts(self) -> List[Dict]:
        """获取所有布尔型事实
        
        Returns:
            布尔型事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            # 基于事实类型判断
            if fact.get('type') == 'boolean':
                results.append(fact)
        
        return results
    
    def get_text_facts(self) -> List[Dict]:
        """获取所有文本型事实
        
        Returns:
            文本型事实列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        results = []
        for fact in self.facts:
            # 基于事实类型判断
            if fact.get('type') == 'text':
                results.append(fact)
        
        return results
    
    def get_all_facts(self) -> List[Dict]:
        """获取所有已提取的事实
        
        Returns:
            所有事实的列表
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        return self.facts.copy()
    
    def get_fact_statistics(self) -> Dict:
        """获取事实统计信息
        
        Returns:
            包含统计信息的字典
        """
        if not self._extracted:
            raise RuntimeError("事实尚未提取，请先调用extract_facts()")
        
        numeric_count = len(self.get_numeric_facts())
        text_count = len(self.get_text_facts())
        boolean_count = len(self.get_boolean_facts())
        other_count = len(self.facts) - numeric_count - text_count - boolean_count
        
        stats = {
            'total_facts': len(self.facts),
            'numeric_facts': numeric_count,
            'text_facts': text_count,
            'boolean_facts': boolean_count,
            'other_facts': other_count,
            'namespaces': {},
            'contexts': {},
            'units': set()
        }
        
        # 统计每个命名空间和上下文的事实数量
        for fact in self.facts:
            # 统计命名空间
            namespace = fact.get('namespace')
            if namespace:
                stats['namespaces'][namespace] = stats['namespaces'].get(namespace, 0) + 1
            
            # 统计上下文
            context_ref = fact.get('contextRef')
            if context_ref:
                stats['contexts'][context_ref] = stats['contexts'].get(context_ref, 0) + 1
            
            # 收集单位
            unit_ref = fact.get('unitRef')
            if unit_ref:
                stats['units'].add(unit_ref)
        
        # 转换units set为list以便JSON序列化
        stats['units'] = list(stats['units'])
        
        return stats
    
    @property
    def is_extracted(self) -> bool:
        """检查事实是否已提取"""
        return self._extracted
    
    @property
    def fact_count(self) -> int:
        """获取已提取的事实数量"""
        return len(self.facts)
