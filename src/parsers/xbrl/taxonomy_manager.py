"""XBRL分类标准管理器

负责加载、解析和查询XBRL分类标准元数据。
"""

from pathlib import Path
from typing import Dict, Optional, List
from lxml import etree
from src.core.logging import get_logger

logger = get_logger(__name__)


class TaxonomyManager:
    """XBRL分类标准管理器
    
    负责加载并查询XBRL分类标准元数据的服务。
    """
    
    def __init__(self, taxonomy_root_path: str):
        """初始化分类标准管理器
        
        Args:
            taxonomy_root_path: 分类标准所在的根目录路径
        """
        self.taxonomy_root_path = Path(taxonomy_root_path)
        self.elements: Dict[str, Dict] = {}
        self.labels: Dict[str, str] = {}
        self._loaded = False
        
        if not self.taxonomy_root_path.exists():
            raise ValueError(f"分类标准目录不存在: {taxonomy_root_path}")
    
    def load_taxonomy(self) -> None:
        """加载分类标准
        
        一次性扫描所有相关文件，然后按类型处理。
        """
        logger.info(f"开始从 {self.taxonomy_root_path} 加载分类标准...")
        
        try:
            # 一次性扫描所有相关文件
            all_files = list(self.taxonomy_root_path.rglob("*.xsd")) + \
                        list(self.taxonomy_root_path.rglob("*_lab.xml"))
            
            xsd_files = [f for f in all_files if f.suffix == '.xsd']
            lab_files = [f for f in all_files if f.name.endswith('_lab.xml')]

            logger.info(f"找到 {len(xsd_files)} 个XSD文件和 {len(lab_files)} 个标签文件。")
            
            for xsd_file in xsd_files:
                self._load_xsd_file(xsd_file)
            
            for lab_file in lab_files:
                self._load_label_file(lab_file)
            
            self._merge_labels_to_elements()
            
            self._loaded = True
            logger.info(f"分类标准加载完成，共加载 {len(self.elements)} 个元素和 {len(self.labels)} 个标签。")
            
        except Exception as e:
            logger.error(f"加载分类标准失败: {e}", exc_info=True)
            raise
    
    def _load_xsd_file(self, xsd_file: Path) -> None:
        """加载单个XSD文件"""
        try:
            tree = etree.parse(str(xsd_file))
            root = tree.getroot()
            nsmap = {'xs': 'http://www.w3.org/2001/XMLSchema'}
            
            for element in root.xpath('.//xs:element', namespaces=nsmap):
                element_id = element.get('id')
                if not element_id:
                    continue
                
                self.elements[element_id] = {
                    'id': element_id,
                    'name': element.get('name'),
                    'type': element.get('type'),
                    'substitutionGroup': element.get('substitutionGroup'),
                    'abstract': element.get('abstract') == 'true',
                    'label': None
                }
        except etree.XMLSyntaxError as e:
            logger.warning(f"解析XSD文件失败 {xsd_file}: {e}")

    def _load_label_file(self, lab_file: Path) -> None:
        """加载标签文件"""
        try:
            tree = etree.parse(str(lab_file))
            root = tree.getroot()
            
            # 安全地构建命名空间映射，过滤掉空前缀
            nsmap = {k: v for k, v in root.nsmap.items() if k is not None}
            
            # 如果缺少必要的命名空间，添加默认值
            if 'link' not in nsmap:
                nsmap['link'] = 'http://www.xbrl.org/2003/linkbase'
            if 'xlink' not in nsmap:
                nsmap['xlink'] = 'http://www.w3.org/1999/xlink'
            if 'xml' not in nsmap:
                nsmap['xml'] = 'http://www.w3.org/XML/1998/namespace'
            
            # 建立 loc 标签到 element ID 的映射
            loc_map = {}
            for loc in root.xpath('.//link:loc', namespaces=nsmap):
                href = loc.get(f"{{{nsmap['xlink']}}}href")
                label = loc.get(f"{{{nsmap['xlink']}}}label")
                if href and label and '#' in href:
                    element_id = href.split('#', 1)[1]
                    loc_map[label] = element_id

            # 建立 label 标签到文本的映射
            label_map = {}
            for label in root.xpath('.//link:label', namespaces=nsmap):
                label_id = label.get(f"{{{nsmap['xlink']}}}label")
                lang = label.get(f"{{{nsmap['xml']}}}lang", "").lower()
                if label_id and label.text and ('zh' in lang or not lang):
                    label_map[label_id] = label.text.strip()

            # 通过 labelArc 连接 loc 和 label
            for arc in root.xpath('.//link:labelArc', namespaces=nsmap):
                from_ref = arc.get(f"{{{nsmap['xlink']}}}from")
                to_ref = arc.get(f"{{{nsmap['xlink']}}}to")
                if from_ref in loc_map and to_ref in label_map:
                    element_id = loc_map[from_ref]
                    self.labels[element_id] = label_map[to_ref]

        except etree.XMLSyntaxError as e:
            logger.warning(f"解析标签文件失败 {lab_file}: {e}")
        except Exception as e:
            logger.warning(f"处理标签文件时出错 {lab_file}: {e}")

    def _merge_labels_to_elements(self) -> None:
        """将标签信息高效地合并到元素信息中"""
        for element_id, label in self.labels.items():
            if element_id in self.elements:
                self.elements[element_id]['label'] = label
    
    def get_element_details(self, element_id: str) -> Optional[Dict]:
        """根据元素ID返回其所有元数据
        
        Args:
            element_id: 元素ID
            
        Returns:
            包含元素所有元数据的字典，如果未找到则返回None
        """
        if not self._loaded:
            raise RuntimeError("分类标准尚未加载，请先调用load_taxonomy()")
        
        return self.elements.get(element_id)
    
    def search_elements_by_label(self, label_keyword: str) -> List[Dict]:
        """根据标签关键词搜索元素
        
        Args:
            label_keyword: 标签关键词
            
        Returns:
            匹配的元素列表
        """
        if not self._loaded:
            raise RuntimeError("分类标准尚未加载，请先调用load_taxonomy()")
        
        results = []
        for element_data in self.elements.values():
            label = element_data.get('label', '')
            if label and label_keyword in label:
                results.append(element_data)
        
        return results
    
    def get_all_elements(self) -> Dict[str, Dict]:
        """获取所有已加载的元素
        
        Returns:
            所有元素的字典
        """
        if not self._loaded:
            raise RuntimeError("分类标准尚未加载，请先调用load_taxonomy()")
        
        return self.elements.copy()
    
    @property
    def is_loaded(self) -> bool:
        """检查分类标准是否已加载"""
        return self._loaded
    
    @property
    def element_count(self) -> int:
        """获取已加载的元素数量"""
        return len(self.elements)
