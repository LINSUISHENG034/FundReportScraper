"""FactExtractor单元测试"""

import pytest
from decimal import Decimal
from lxml import etree

from src.parsers.xbrl.fact_extractor import FactExtractor


class TestFactExtractor:
    """FactExtractor测试类"""
    
    @pytest.fixture
    def sample_xbrl_xml(self):
        """创建示例XBRL XML内容"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:cfi="http://www.csrc.gov.cn/2024/cfi"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
    
    <!-- 数值型事实 -->
    <cfi:TotalAssets contextRef="c-1" unitRef="CNY" decimals="-2">1000000.00</cfi:TotalAssets>
    <cfi:TotalLiabilities contextRef="c-1" unitRef="CNY" decimals="-2">500000.00</cfi:TotalLiabilities>
    <cfi:NetAssetValue contextRef="c-2" unitRef="CNY" decimals="-4">1.2345</cfi:NetAssetValue>
    
    <!-- 文本型事实 -->
    <cfi:FundName contextRef="c-1">测试基金</cfi:FundName>
    <cfi:FundCode contextRef="c-1">001056</cfi:FundCode>
    <cfi:ReportingDate contextRef="c-1">2024-12-31</cfi:ReportingDate>
    
    <!-- 布尔型事实 -->
    <cfi:IsAudited contextRef="c-1">true</cfi:IsAudited>
    <cfi:HasDerivatives contextRef="c-1">false</cfi:HasDerivatives>
    
    <!-- 带有不同命名空间的事实 -->
    <xbrli:context id="c-1"/>
    <xbrli:context id="c-2"/>
    
    <!-- 单位定义 -->
    <xbrli:unit id="CNY">
        <xbrli:measure>iso4217:CNY</xbrli:measure>
    </xbrli:unit>
    
</xbrl>'''
    
    @pytest.fixture
    def sample_xbrl_html(self):
        """创建示例XBRL HTML内容（模拟实际文件格式）"""
        return '''<html>
<body>
    <!-- 数值型事实 -->
    <span name="cfi:TotalAssets" contextref="c-1" unitref="CNY" decimals="-2">1000000.00</span>
    <span name="cfi:TotalLiabilities" contextref="c-1" unitref="CNY" decimals="-2">500000.00</span>
    
    <!-- 文本型事实 -->
    <span name="cfi:FundName" contextref="c-1">测试基金</span>
    <span name="cfi:FundCode" contextref="c-1">001056</span>
    
    <!-- 布尔型事实 -->
    <span name="cfi:IsAudited" contextref="c-1">true</span>
    
</body>
</html>'''
    
    def test_init_with_lxml_html(self, sample_xbrl_html):
        """测试使用lxml解析HTML初始化"""
        root = etree.HTML(sample_xbrl_html)
        extractor = FactExtractor(root)
        
        assert extractor.document == root
        assert not extractor.is_extracted
        assert extractor.fact_count == 0
    
    def test_init_with_lxml(self, sample_xbrl_xml):
        """测试使用lxml初始化"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        
        assert extractor.document == root
        assert not extractor.is_extracted
        assert extractor.fact_count == 0
    
    def test_extract_facts_lxml(self, sample_xbrl_xml):
        """测试使用lxml提取事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        assert extractor.is_extracted
        assert extractor.fact_count == 8  # 8个事实元素
        
        # 测试数值型事实
        total_assets = extractor.get_facts_by_name('cfi:TotalAssets')
        assert len(total_assets) == 1
        fact = total_assets[0]
        assert fact['name'] == 'cfi:TotalAssets'
        assert fact['value'] == Decimal('1000000.00')
        assert fact['contextRef'] == 'c-1'
        assert fact['unitRef'] == 'CNY'
        assert fact['decimals'] == '-2'
        assert fact['type'] == 'numeric'
        assert fact['namespace'] == 'cfi'
        
        # 测试文本型事实
        fund_name = extractor.get_facts_by_name('cfi:FundName')
        assert len(fund_name) == 1
        fact = fund_name[0]
        assert fact['name'] == 'cfi:FundName'
        assert fact['value'] == '测试基金'
        assert fact['type'] == 'text'
        
        # 测试布尔型事实
        is_audited = extractor.get_facts_by_name('cfi:IsAudited')
        assert len(is_audited) == 1
        fact = is_audited[0]
        assert fact['value'] is True
        assert fact['type'] == 'boolean'
    
    def test_extract_facts_html(self, sample_xbrl_html):
        """测试使用lxml解析HTML提取事实"""
        root = etree.HTML(sample_xbrl_html)
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        assert extractor.is_extracted
        assert extractor.fact_count == 5  # 5个事实元素
        
        # 测试数值型事实
        total_assets = extractor.get_facts_by_name('cfi:TotalAssets')
        assert len(total_assets) == 1
        fact = total_assets[0]
        assert fact['value'] == Decimal('1000000.00')
        assert fact['type'] == 'numeric'
    
    def test_get_facts_by_name_nonexistent(self, sample_xbrl_xml):
        """测试获取不存在的事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        facts = extractor.get_facts_by_name('nonexistent:Fact')
        assert len(facts) == 0
    
    def test_get_facts_by_name_before_extract(self, sample_xbrl_xml):
        """测试在提取前获取事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        
        with pytest.raises(RuntimeError, match="事实尚未提取"):
            extractor.get_facts_by_name('cfi:TotalAssets')
    
    def test_get_facts_by_context(self, sample_xbrl_xml):
        """测试根据上下文获取事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        # 测试c-1上下文的事实
        c1_facts = extractor.get_facts_by_context('c-1')
        assert len(c1_facts) == 7  # c-1上下文有7个事实
        
        # 测试c-2上下文的事实
        c2_facts = extractor.get_facts_by_context('c-2')
        assert len(c2_facts) == 1  # c-2上下文有1个事实
        
        # 测试不存在的上下文
        nonexistent_facts = extractor.get_facts_by_context('c-999')
        assert len(nonexistent_facts) == 0
    
    def test_get_facts_by_namespace(self, sample_xbrl_xml):
        """测试根据命名空间获取事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        # 测试cfi命名空间的事实
        cfi_facts = extractor.get_facts_by_namespace('cfi')
        assert len(cfi_facts) == 8  # 所有事实都是cfi命名空间
        
        # 测试不存在的命名空间
        unknown_facts = extractor.get_facts_by_namespace('unknown')
        assert len(unknown_facts) == 0
    
    def test_get_numeric_facts(self, sample_xbrl_xml):
        """测试获取数值型事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        numeric_facts = extractor.get_numeric_facts()
        assert len(numeric_facts) == 3  # 3个数值型事实
        
        # 验证所有返回的事实都是数值型
        for fact in numeric_facts:
            assert fact['type'] == 'numeric'
            assert isinstance(fact['value'], Decimal)
    
    def test_get_text_facts(self, sample_xbrl_xml):
        """测试获取文本型事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        text_facts = extractor.get_text_facts()
        assert len(text_facts) == 3  # 3个文本型事实
        
        # 验证所有返回的事实都是文本型
        for fact in text_facts:
            assert fact['type'] == 'text'
            assert isinstance(fact['value'], str)
    
    def test_get_all_facts(self, sample_xbrl_xml):
        """测试获取所有事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        all_facts = extractor.get_all_facts()
        assert isinstance(all_facts, list)
        assert len(all_facts) == 8
    
    def test_get_all_facts_before_extract(self, sample_xbrl_xml):
        """测试在提取前获取所有事实"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        
        with pytest.raises(RuntimeError, match="事实尚未提取"):
            extractor.get_all_facts()
    
    def test_get_fact_statistics(self, sample_xbrl_xml):
        """测试获取事实统计信息"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        stats = extractor.get_fact_statistics()
        assert isinstance(stats, dict)
        assert stats['total_facts'] == 8
        assert stats['numeric_facts'] == 3
        assert stats['text_facts'] == 3
        assert stats['boolean_facts'] == 2
        assert stats['other_facts'] == 0
        
        # 检查命名空间统计
        assert 'namespaces' in stats
        assert 'cfi' in stats['namespaces']
        assert stats['namespaces']['cfi'] == 8
        
        # 检查上下文统计
        assert 'contexts' in stats
        assert 'c-1' in stats['contexts']
        assert 'c-2' in stats['contexts']
        assert stats['contexts']['c-1'] == 7
        assert stats['contexts']['c-2'] == 1
    
    def test_get_fact_statistics_before_extract(self, sample_xbrl_xml):
        """测试在提取前获取统计信息"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        
        with pytest.raises(RuntimeError, match="事实尚未提取"):
            extractor.get_fact_statistics()
    
    def test_determine_fact_type(self):
        """测试事实类型判断"""
        root = etree.fromstring('<root></root>')
        extractor = FactExtractor(root)
        
        # 测试数值型
        assert extractor._determine_fact_type('123.45', 'CNY', '-2') == 'numeric'
        assert extractor._determine_fact_type('1000', 'CNY', '0') == 'numeric'
        assert extractor._determine_fact_type('-500.00', 'CNY', '-2') == 'numeric'
        
        # 测试布尔型
        assert extractor._determine_fact_type('true', None, None) == 'boolean'
        assert extractor._determine_fact_type('false', None, None) == 'boolean'
        assert extractor._determine_fact_type('1', None, None) == 'boolean'
        assert extractor._determine_fact_type('0', None, None) == 'boolean'
        
        # 测试文本型
        assert extractor._determine_fact_type('测试文本', None, None) == 'text'
        assert extractor._determine_fact_type('2024-12-31', None, None) == 'text'
        assert extractor._determine_fact_type('ABC123', None, None) == 'text'
        
        # 测试空值
        assert extractor._determine_fact_type('', None, None) == 'text'
        assert extractor._determine_fact_type(None, None, None) == 'text'
    
    def test_parse_numeric_value(self):
        """测试数值解析"""
        root = etree.fromstring('<root></root>')
        extractor = FactExtractor(root)
        
        # 测试正常数值
        assert extractor._parse_numeric_value('123.45') == Decimal('123.45')
        assert extractor._parse_numeric_value('1000') == Decimal('1000')
        assert extractor._parse_numeric_value('-500.00') == Decimal('-500.00')
        
        # 测试科学计数法
        assert extractor._parse_numeric_value('1.23E+5') == Decimal('123000')
        assert extractor._parse_numeric_value('1.23e-2') == Decimal('0.0123')
        
        # 测试无效数值
        assert extractor._parse_numeric_value('abc') is None
        assert extractor._parse_numeric_value('') is None
        assert extractor._parse_numeric_value(None) is None
    
    def test_parse_boolean_value(self):
        """测试布尔值解析"""
        root = etree.fromstring('<root></root>')
        extractor = FactExtractor(root)
        
        # 测试true值
        assert extractor._parse_boolean_value('true') is True
        assert extractor._parse_boolean_value('True') is True
        assert extractor._parse_boolean_value('TRUE') is True
        assert extractor._parse_boolean_value('1') is True
        
        # 测试false值
        assert extractor._parse_boolean_value('false') is False
        assert extractor._parse_boolean_value('False') is False
        assert extractor._parse_boolean_value('FALSE') is False
        assert extractor._parse_boolean_value('0') is False
        
        # 测试无效值
        assert extractor._parse_boolean_value('maybe') is None
        assert extractor._parse_boolean_value('') is None
        assert extractor._parse_boolean_value(None) is None
    
    def test_extract_namespace(self):
        """测试命名空间提取"""
        root = etree.fromstring('<root></root>')
        extractor = FactExtractor(root)
        
        # 测试带命名空间的标签
        assert extractor._extract_namespace('cfi:TotalAssets') == 'cfi'
        assert extractor._extract_namespace('xbrli:context') == 'xbrli'
        assert extractor._extract_namespace('iso4217:CNY') == 'iso4217'
        
        # 测试不带命名空间的标签
        assert extractor._extract_namespace('TotalAssets') is None
        assert extractor._extract_namespace('context') is None
        
        # 测试无效输入
        assert extractor._extract_namespace('') is None
        assert extractor._extract_namespace(None) is None
    
    def test_multiple_extract_calls(self, sample_xbrl_xml):
        """测试多次调用extract_facts"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        extractor = FactExtractor(root)
        
        # 第一次提取
        extractor.extract_facts()
        first_count = extractor.fact_count
        
        # 第二次提取
        extractor.extract_facts()
        second_count = extractor.fact_count
        
        # 事实数量应该相同（重新提取）
        assert first_count == second_count
        assert extractor.is_extracted
    
    def test_empty_document(self):
        """测试空文档"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
</xbrl>'''
        
        root = etree.fromstring(xml_content.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        assert extractor.is_extracted
        assert extractor.fact_count == 0
    
    def test_facts_without_context_or_unit(self):
        """测试处理没有上下文或单位的事实"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:cfi="http://www.csrc.gov.cn/2024/cfi">
    <cfi:FundName>测试基金</cfi:FundName>
    <cfi:TotalAssets unitRef="CNY">1000000</cfi:TotalAssets>
    <cfi:NetAssets contextRef="c-1">500000</cfi:NetAssets>
</xbrl>'''
        
        root = etree.fromstring(xml_content.encode('utf-8'))
        extractor = FactExtractor(root)
        extractor.extract_facts()
        
        assert extractor.fact_count == 3
        
        # 检查没有上下文的事实
        fund_name = extractor.get_facts_by_name('cfi:FundName')[0]
        assert fund_name['contextRef'] is None
        assert fund_name['unitRef'] is None
        
        # 检查只有单位的事实
        total_assets = extractor.get_facts_by_name('cfi:TotalAssets')[0]
        assert total_assets['contextRef'] is None
        assert total_assets['unitRef'] == 'CNY'
        
        # 检查只有上下文的事实
        net_assets = extractor.get_facts_by_name('cfi:NetAssets')[0]
        assert net_assets['contextRef'] == 'c-1'
        assert net_assets['unitRef'] is None