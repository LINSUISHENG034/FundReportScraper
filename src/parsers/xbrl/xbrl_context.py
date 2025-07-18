"""XBRL上下文解析器

负责解析XBRL报告中所有上下文（context）并提供查询功能。
"""

from datetime import datetime
from typing import Dict, Optional, List
from lxml import etree
from src.core.logging import get_logger

logger = get_logger(__name__)


class XBRLContext:
    """XBRL上下文解析器
    
    负责解析XBRL报告中所有上下文（context）并提供查询功能。
    """
    
    def __init__(self, document: etree._Element):
        """初始化XBRL上下文解析器
        
        Args:
            document: 已解析的lxml Element对象
        """
        self.document = document
        self.contexts: Dict[str, Dict] = {}
        self._parsed = False
        
    def parse_contexts(self) -> None:
        """解析文档中的所有上下文"""
        logger.info("开始解析XBRL上下文")
        
        try:
            # 使用local-name()使其对命名空间前缀不敏感
            context_elements = self.document.xpath("//*[local-name()='context']")
            
            for context_elem in context_elements:
                context_data = self._extract_context_data(context_elem)
                if context_data and context_data.get('id'):
                    self.contexts[context_data['id']] = context_data
            
            self._parsed = True
            logger.info(f"上下文解析完成，共解析 {len(self.contexts)} 个上下文")
            
        except Exception as e:
            logger.error(f"解析上下文失败: {e}", exc_info=True)
            raise
    
    def _extract_context_data(self, context_elem) -> Optional[Dict]:
        """从元素中提取上下文数据"""
        context_id = context_elem.get('id')
        if not context_id:
            return None
        
        entity_elem = self._get_child_element(context_elem, 'entity')
        period_elem = self._get_child_element(context_elem, 'period')
        scenario_elem = self._get_child_element(context_elem, 'scenario')
        
        return {
            'id': context_id,
            'entity': self._extract_entity_data(entity_elem) if entity_elem is not None else None,
            'period': self._extract_period_data(period_elem) if period_elem is not None else None,
            'scenario': self._extract_scenario_data(scenario_elem) if scenario_elem is not None else None,
        }
    
    def _extract_entity_data(self, entity_elem) -> Dict:
        """从元素中提取实体数据"""
        identifier_elem = self._get_child_element(entity_elem, 'identifier')
        if identifier_elem is None:
            return {'identifier': None, 'scheme': None}
            
        return {
            'identifier': identifier_elem.text.strip() if identifier_elem.text else None,
            'scheme': identifier_elem.get('scheme')
        }
    
    def _extract_period_data(self, period_elem) -> Dict:
        """从元素中提取期间数据"""
        instant_elem = self._get_child_element(period_elem, 'instant')
        if instant_elem is not None:
            instant_text = instant_elem.text.strip() if instant_elem.text else None
            return {
                'type': 'instant',
                'instant': self._parse_date(instant_text),
                'startDate': None,
                'endDate': None,
            }
            
        # 尝试标准XBRL格式（驼峰命名法）
        start_elem = self._get_child_element(period_elem, 'startDate')
        end_elem = self._get_child_element(period_elem, 'endDate')
        
        # 如果没找到，尝试HTML格式（小写）
        if start_elem is None:
            start_elem = self._get_child_element(period_elem, 'startdate')
        if end_elem is None:
            end_elem = self._get_child_element(period_elem, 'enddate')
            
        if start_elem is not None and end_elem is not None:
            start_text = start_elem.text.strip() if start_elem.text else None
            end_text = end_elem.text.strip() if end_elem.text else None
            return {
                'type': 'duration',
                'instant': None,
                'startDate': self._parse_date(start_text),
                'endDate': self._parse_date(end_text),
            }
            
        return {'type': None, 'instant': None, 'startDate': None, 'endDate': None}

    def _extract_scenario_data(self, scenario_elem) -> Dict:
        """从元素中提取场景数据"""
        scenario_data = {'explicitMembers': [], 'typedMembers': []}
        
        # 使用local-name()来查找，忽略命名空间前缀
        explicit_members = scenario_elem.xpath(".//*[local-name()='explicitMember']")
        for member in explicit_members:
            dimension = member.get('dimension')
            value = member.text.strip() if member.text else None
            if dimension and value:
                scenario_data['explicitMembers'].append({'dimension': dimension, 'value': value})
        
        typed_members = scenario_elem.xpath(".//*[local-name()='typedMember']")
        for member in typed_members:
            dimension = member.get('dimension')
            if dimension:
                scenario_data['typedMembers'].append({
                    'dimension': dimension,
                    'content': etree.tostring(member, encoding='unicode')
                })
        
        return scenario_data
    
    def _get_child_element(self, parent, child_name):
        """获取指定名称的第一个子元素，忽略命名空间"""
        children = parent.xpath(f"./*[local-name()='{child_name}']")
        return children[0] if children else None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            解析后的datetime对象
        """
        if not date_str:
            return None
        
        try:
            # 尝试多种日期格式
            date_formats = [
                '%Y-%m-%d',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning(f"无法解析日期格式: {date_str}")
            return None
            
        except Exception as e:
            logger.warning(f"解析日期失败 {date_str}: {e}")
            return None
    
    def get_context_details(self, context_id: str) -> Optional[Dict]:
        """根据上下文ID返回其所有解析后的信息
        
        Args:
            context_id: 上下文ID
            
        Returns:
            包含上下文所有信息的字典，如果未找到则返回None
        """
        if not self._parsed:
            raise RuntimeError("上下文尚未解析，请先调用parse_contexts()")
        
        return self.contexts.get(context_id)
    
    def get_contexts_by_entity(self, entity_identifier: str) -> List[Dict]:
        """根据实体标识符获取所有相关上下文
        
        Args:
            entity_identifier: 实体标识符（如基金代码）
            
        Returns:
            匹配的上下文列表
        """
        if not self._parsed:
            raise RuntimeError("上下文尚未解析，请先调用parse_contexts()")
        
        results = []
        for context_data in self.contexts.values():
            entity = context_data.get('entity', {})
            if entity.get('identifier') == entity_identifier:
                results.append(context_data)
        
        return results
    
    def get_contexts_by_period_type(self, period_type: str) -> List[Dict]:
        """根据期间类型获取上下文
        
        Args:
            period_type: 期间类型（'instant' 或 'duration'）
            
        Returns:
            匹配的上下文列表
        """
        if not self._parsed:
            raise RuntimeError("上下文尚未解析，请先调用parse_contexts()")
        
        results = []
        for context_data in self.contexts.values():
            period = context_data.get('period', {})
            if period.get('type') == period_type:
                results.append(context_data)
        
        return results
    
    def get_all_contexts(self) -> Dict[str, Dict]:
        """获取所有已解析的上下文
        
        Returns:
            所有上下文的字典
        """
        if not self._parsed:
            raise RuntimeError("上下文尚未解析，请先调用parse_contexts()")
        
        return self.contexts.copy()
    
    @property
    def is_parsed(self) -> bool:
        """检查上下文是否已解析"""
        return self._parsed
    
    @property
    def context_count(self) -> int:
        """获取已解析的上下文数量"""
        return len(self.contexts)
