"""TaxonomyManager单元测试"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from lxml import etree

from src.parsers.xbrl.taxonomy_manager import TaxonomyManager


class TestTaxonomyManager:
    """TaxonomyManager测试类"""
    
    @pytest.fixture
    def temp_taxonomy_dir(self):
        """创建临时分类标准目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            taxonomy_dir = Path(temp_dir) / "taxonomy"
            taxonomy_dir.mkdir()
            
            # 创建模拟的XSD文件
            xsd_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xbrli="http://www.xbrl.org/2003/instance"
           xmlns:cfi="http://www.csrc.gov.cn/2024/cfi"
           targetNamespace="http://www.csrc.gov.cn/2024/cfi">
    
    <xs:element id="cfi:Assets" name="Assets" type="xbrli:monetaryItemType" 
                substitutionGroup="xbrli:item" abstract="false"/>
    
    <xs:element id="cfi:FinancialAssetsAtFairValueThroughProfitOrLoss" 
                name="FinancialAssetsAtFairValueThroughProfitOrLoss" 
                type="xbrli:monetaryItemType" 
                substitutionGroup="xbrli:item" abstract="false"/>
                
    <xs:element id="cfi:Liabilities" name="Liabilities" type="xbrli:monetaryItemType" 
                substitutionGroup="xbrli:item" abstract="false"/>
                
</xs:schema>'''
            
            xsd_file = taxonomy_dir / "cfi.xsd"
            xsd_file.write_text(xsd_content, encoding='utf-8')
            
            # 创建模拟的标签文件
            lab_content = '''<?xml version="1.0" encoding="UTF-8"?>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase"
           xmlns:xlink="http://www.w3.org/1999/xlink"
           xmlns:xml="http://www.w3.org/XML/1998/namespace">
    
    <labelLink xlink:type="extended">
        <loc xlink:type="locator" xlink:href="cfi.xsd#cfi:Assets" xlink:label="cfi:Assets_loc"/>
        <label xlink:type="resource" xlink:label="cfi:Assets_label" 
               xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="zh-CN">资产总计</label>
        <labelArc xlink:type="arc" xlink:from="cfi:Assets_loc" xlink:to="cfi:Assets_label"/>
        
        <loc xlink:type="locator" xlink:href="cfi.xsd#cfi:FinancialAssetsAtFairValueThroughProfitOrLoss" 
             xlink:label="cfi:FinancialAssetsAtFairValueThroughProfitOrLoss_loc"/>
        <label xlink:type="resource" xlink:label="cfi:FinancialAssetsAtFairValueThroughProfitOrLoss_label" 
               xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="zh-CN">交易性金融资产</label>
        <labelArc xlink:type="arc" xlink:from="cfi:FinancialAssetsAtFairValueThroughProfitOrLoss_loc" 
                  xlink:to="cfi:FinancialAssetsAtFairValueThroughProfitOrLoss_label"/>
                  
        <loc xlink:type="locator" xlink:href="cfi.xsd#cfi:Liabilities" xlink:label="cfi:Liabilities_loc"/>
        <label xlink:type="resource" xlink:label="cfi:Liabilities_label" 
               xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="zh-CN">负债总计</label>
        <labelArc xlink:type="arc" xlink:from="cfi:Liabilities_loc" xlink:to="cfi:Liabilities_label"/>
    </labelLink>
    
</linkbase>'''
            
            lab_file = taxonomy_dir / "cfi_lab.xml"
            lab_file.write_text(lab_content, encoding='utf-8')
            
            yield str(taxonomy_dir)
    
    def test_init_valid_directory(self, temp_taxonomy_dir):
        """测试使用有效目录初始化"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        assert manager.taxonomy_root_path == Path(temp_taxonomy_dir)
        assert not manager.is_loaded
        assert manager.element_count == 0
    
    def test_init_invalid_directory(self):
        """测试使用无效目录初始化"""
        with pytest.raises(ValueError, match="分类标准目录不存在"):
            TaxonomyManager("/nonexistent/path")
    
    def test_load_taxonomy_success(self, temp_taxonomy_dir):
        """测试成功加载分类标准"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        assert manager.is_loaded
        assert manager.element_count > 0
        
        # 验证加载的元素
        assets_element = manager.get_element_details('cfi:Assets')
        assert assets_element is not None
        assert assets_element['name'] == 'Assets'
        assert assets_element['type'] == 'xbrli:monetaryItemType'
        assert assets_element['label'] == '资产总计'
        assert not assets_element['abstract']
    
    def test_get_element_details_existing(self, temp_taxonomy_dir):
        """测试获取存在的元素详情"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        element = manager.get_element_details('cfi:FinancialAssetsAtFairValueThroughProfitOrLoss')
        assert element is not None
        assert element['id'] == 'cfi:FinancialAssetsAtFairValueThroughProfitOrLoss'
        assert element['name'] == 'FinancialAssetsAtFairValueThroughProfitOrLoss'
        assert element['label'] == '交易性金融资产'
    
    def test_get_element_details_nonexistent(self, temp_taxonomy_dir):
        """测试获取不存在的元素详情"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        element = manager.get_element_details('nonexistent:element')
        assert element is None
    
    def test_get_element_details_before_load(self, temp_taxonomy_dir):
        """测试在加载前获取元素详情"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        
        with pytest.raises(RuntimeError, match="分类标准尚未加载"):
            manager.get_element_details('cfi:Assets')
    
    def test_search_elements_by_label(self, temp_taxonomy_dir):
        """测试根据标签搜索元素"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        # 搜索包含"资产"的元素
        results = manager.search_elements_by_label('资产')
        assert len(results) >= 1
        
        # 验证搜索结果
        asset_found = False
        for result in results:
            if result['id'] == 'cfi:Assets':
                asset_found = True
                assert result['label'] == '资产总计'
                break
        assert asset_found
    
    def test_search_elements_by_label_no_match(self, temp_taxonomy_dir):
        """测试搜索不匹配的标签"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        results = manager.search_elements_by_label('不存在的标签')
        assert len(results) == 0
    
    def test_search_elements_before_load(self, temp_taxonomy_dir):
        """测试在加载前搜索元素"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        
        with pytest.raises(RuntimeError, match="分类标准尚未加载"):
            manager.search_elements_by_label('资产')
    
    def test_get_all_elements(self, temp_taxonomy_dir):
        """测试获取所有元素"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        all_elements = manager.get_all_elements()
        assert isinstance(all_elements, dict)
        assert len(all_elements) > 0
        assert 'cfi:Assets' in all_elements
        assert 'cfi:Liabilities' in all_elements
    
    def test_get_all_elements_before_load(self, temp_taxonomy_dir):
        """测试在加载前获取所有元素"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        
        with pytest.raises(RuntimeError, match="分类标准尚未加载"):
            manager.get_all_elements()
    
    def test_load_taxonomy_with_invalid_xsd(self, temp_taxonomy_dir):
        """测试加载包含无效XSD文件的分类标准"""
        # 创建无效的XSD文件
        invalid_xsd = Path(temp_taxonomy_dir) / "invalid.xsd"
        invalid_xsd.write_text("invalid xml content", encoding='utf-8')
        
        manager = TaxonomyManager(temp_taxonomy_dir)
        # 应该不抛出异常，但会记录警告
        manager.load_taxonomy()
        
        # 仍然应该加载有效的文件
        assert manager.is_loaded
        assert manager.element_count > 0
    
    def test_load_taxonomy_with_invalid_lab(self, temp_taxonomy_dir):
        """测试加载包含无效标签文件的分类标准"""
        # 创建无效的标签文件
        invalid_lab = Path(temp_taxonomy_dir) / "invalid_lab.xml"
        invalid_lab.write_text("invalid xml content", encoding='utf-8')
        
        manager = TaxonomyManager(temp_taxonomy_dir)
        # 应该不抛出异常，但会记录警告
        manager.load_taxonomy()
        
        # 仍然应该加载有效的文件
        assert manager.is_loaded
        assert manager.element_count > 0
    
    def test_element_without_id_or_name(self, temp_taxonomy_dir):
        """测试处理没有id或name的元素"""
        # 创建包含无效元素的XSD文件
        invalid_xsd_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xbrli="http://www.xbrl.org/2003/instance">
    <xs:element type="xbrli:monetaryItemType"/>
</xs:schema>'''
        
        invalid_xsd = Path(temp_taxonomy_dir) / "invalid_elements.xsd"
        invalid_xsd.write_text(invalid_xsd_content, encoding='utf-8')
        
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        # 应该成功加载，但忽略无效元素
        assert manager.is_loaded
    
    def test_multiple_load_calls(self, temp_taxonomy_dir):
        """测试多次调用load_taxonomy"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        
        # 第一次加载
        manager.load_taxonomy()
        first_count = manager.element_count
        
        # 第二次加载
        manager.load_taxonomy()
        second_count = manager.element_count
        
        # 元素数量应该相同（重新加载）
        assert first_count == second_count
        assert manager.is_loaded
    
    @patch('src.parsers.xbrl.taxonomy_manager.logger')
    def test_logging_during_load(self, mock_logger, temp_taxonomy_dir):
        """测试加载过程中的日志记录"""
        manager = TaxonomyManager(temp_taxonomy_dir)
        manager.load_taxonomy()
        
        # 验证日志调用
        mock_logger.info.assert_called()
        
        # 检查是否记录了开始和完成信息
        info_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("开始从" in call and "加载分类标准" in call for call in info_calls)
        assert any("分类标准加载完成" in call for call in info_calls)