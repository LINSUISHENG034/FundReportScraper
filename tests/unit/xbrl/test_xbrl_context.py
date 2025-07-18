"""XBRLContext单元测试"""

import pytest
from datetime import datetime
from lxml import etree

from src.parsers.xbrl.xbrl_context import XBRLContext


class TestXBRLContext:
    """XBRLContext测试类"""
    
    @pytest.fixture
    def sample_xbrl_xml(self):
        """创建示例XBRL XML内容"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:cfi="http://www.csrc.gov.cn/2024/cfi">
    
    <xbrli:context id="c-1">
        <xbrli:entity>
            <xbrli:identifier scheme="http://www.csrc.gov.cn/fund">001056</xbrli:identifier>
        </xbrli:entity>
        <xbrli:period>
            <xbrli:startDate>2024-01-01</xbrli:startDate>
            <xbrli:endDate>2024-12-31</xbrli:endDate>
        </xbrli:period>
    </xbrli:context>
    
    <xbrli:context id="c-2">
        <xbrli:entity>
            <xbrli:identifier scheme="http://www.csrc.gov.cn/fund">001056</xbrli:identifier>
        </xbrli:entity>
        <xbrli:period>
            <xbrli:instant>2024-12-31</xbrli:instant>
        </xbrli:period>
    </xbrli:context>
    
    <xbrli:context id="c-3">
        <xbrli:entity>
            <xbrli:identifier scheme="http://www.csrc.gov.cn/fund">001056</xbrli:identifier>
        </xbrli:entity>
        <xbrli:period>
            <xbrli:instant>2024-12-31</xbrli:instant>
        </xbrli:period>
        <xbrli:scenario>
            <xbrldi:explicitMember dimension="cfi:InvestmentTypeDimension">cfi:EquityInvestment</xbrldi:explicitMember>
            <xbrldi:typedMember dimension="cfi:IndustryDimension">
                <cfi:IndustryCode>C39</cfi:IndustryCode>
            </xbrldi:typedMember>
        </xbrli:scenario>
    </xbrli:context>
    
</xbrl>'''
    
    @pytest.fixture
    def sample_xbrl_html(self):
        """创建示例XBRL HTML内容（模拟实际文件格式）"""
        return '''<html>
<body>
    <context id="c-1">
        <entity>
            <identifier scheme="http://www.csrc.gov.cn/fund">001056</identifier>
        </entity>
        <period>
            <startdate>2024-01-01</startdate>
            <enddate>2024-12-31</enddate>
        </period>
    </context>
    
    <context id="c-2">
        <entity>
            <identifier scheme="http://www.csrc.gov.cn/fund">001056</identifier>
        </entity>
        <period>
            <instant>2024-12-31</instant>
        </period>
    </context>
</body>
</html>'''
    
    def test_init_with_lxml_html(self, sample_xbrl_html):
        """测试使用lxml解析HTML初始化"""
        root = etree.HTML(sample_xbrl_html)
        context_parser = XBRLContext(root)
        
        assert context_parser.document == root
        assert not context_parser.is_parsed
        assert context_parser.context_count == 0
    
    def test_init_with_lxml(self, sample_xbrl_xml):
        """测试使用lxml初始化"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        
        assert context_parser.document == root
        assert not context_parser.is_parsed
        assert context_parser.context_count == 0
    
    def test_parse_contexts_lxml(self, sample_xbrl_xml):
        """测试使用lxml解析上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        assert context_parser.is_parsed
        assert context_parser.context_count == 3
        
        # 测试duration类型的上下文
        c1 = context_parser.get_context_details('c-1')
        assert c1 is not None
        assert c1['id'] == 'c-1'
        assert c1['entity']['identifier'] == '001056'
        assert c1['entity']['scheme'] == 'http://www.csrc.gov.cn/fund'
        assert c1['period']['type'] == 'duration'
        assert c1['period']['startDate'] == datetime(2024, 1, 1)
        assert c1['period']['endDate'] == datetime(2024, 12, 31)
        
        # 测试instant类型的上下文
        c2 = context_parser.get_context_details('c-2')
        assert c2 is not None
        assert c2['period']['type'] == 'instant'
        assert c2['period']['instant'] == datetime(2024, 12, 31)
    
    def test_parse_contexts_html(self, sample_xbrl_html):
        """测试使用lxml解析HTML上下文"""
        root = etree.HTML(sample_xbrl_html)
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        assert context_parser.is_parsed
        assert context_parser.context_count == 2
        
        # 测试duration类型的上下文
        c1 = context_parser.get_context_details('c-1')
        assert c1 is not None
        assert c1['entity']['identifier'] == '001056'
        assert c1['period']['type'] == 'duration'
        assert c1['period']['startDate'] == datetime(2024, 1, 1)
        assert c1['period']['endDate'] == datetime(2024, 12, 31)
    
    def test_parse_contexts_with_scenario(self, sample_xbrl_xml):
        """测试解析包含场景信息的上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        # 测试包含场景信息的上下文
        c3 = context_parser.get_context_details('c-3')
        assert c3 is not None
        assert c3['scenario'] is not None
        
        # 检查显式成员
        explicit_members = c3['scenario']['explicitMembers']
        assert len(explicit_members) == 1
        assert explicit_members[0]['dimension'] == 'cfi:InvestmentTypeDimension'
        assert explicit_members[0]['value'] == 'cfi:EquityInvestment'
        
        # 检查类型化成员
        typed_members = c3['scenario']['typedMembers']
        assert len(typed_members) == 1
        assert typed_members[0]['dimension'] == 'cfi:IndustryDimension'
    
    def test_get_context_details_nonexistent(self, sample_xbrl_xml):
        """测试获取不存在的上下文详情"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        context = context_parser.get_context_details('nonexistent')
        assert context is None
    
    def test_get_context_details_before_parse(self, sample_xbrl_xml):
        """测试在解析前获取上下文详情"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        
        with pytest.raises(RuntimeError, match="上下文尚未解析"):
            context_parser.get_context_details('c-1')
    
    def test_get_contexts_by_entity(self, sample_xbrl_xml):
        """测试根据实体标识符获取上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        contexts = context_parser.get_contexts_by_entity('001056')
        assert len(contexts) == 3
        
        # 测试不存在的实体
        contexts = context_parser.get_contexts_by_entity('999999')
        assert len(contexts) == 0
    
    def test_get_contexts_by_period_type(self, sample_xbrl_xml):
        """测试根据期间类型获取上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        # 测试duration类型
        duration_contexts = context_parser.get_contexts_by_period_type('duration')
        assert len(duration_contexts) == 1
        assert duration_contexts[0]['id'] == 'c-1'
        
        # 测试instant类型
        instant_contexts = context_parser.get_contexts_by_period_type('instant')
        assert len(instant_contexts) == 2
        
        # 测试不存在的类型
        unknown_contexts = context_parser.get_contexts_by_period_type('unknown')
        assert len(unknown_contexts) == 0
    
    def test_get_all_contexts(self, sample_xbrl_xml):
        """测试获取所有上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        all_contexts = context_parser.get_all_contexts()
        assert isinstance(all_contexts, dict)
        assert len(all_contexts) == 3
        assert 'c-1' in all_contexts
        assert 'c-2' in all_contexts
        assert 'c-3' in all_contexts
    
    def test_get_all_contexts_before_parse(self, sample_xbrl_xml):
        """测试在解析前获取所有上下文"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        
        with pytest.raises(RuntimeError, match="上下文尚未解析"):
            context_parser.get_all_contexts()
    
    def test_parse_date_formats(self):
        """测试解析不同的日期格式"""
        # 创建一个简单的上下文解析器来测试日期解析
        root = etree.fromstring('<root></root>')
        context_parser = XBRLContext(root)
        
        # 测试标准日期格式
        date1 = context_parser._parse_date('2024-12-31')
        assert date1 == datetime(2024, 12, 31)
        
        # 测试带时间的格式
        date2 = context_parser._parse_date('2024-12-31T23:59:59')
        assert date2 == datetime(2024, 12, 31, 23, 59, 59)
        
        # 测试带时区的格式
        date3 = context_parser._parse_date('2024-12-31T23:59:59Z')
        assert date3 == datetime(2024, 12, 31, 23, 59, 59)
        
        # 测试无效格式
        date4 = context_parser._parse_date('invalid-date')
        assert date4 is None
        
        # 测试空字符串
        date5 = context_parser._parse_date('')
        assert date5 is None
        
        # 测试None
        date6 = context_parser._parse_date(None)
        assert date6 is None
    
    def test_context_without_id(self):
        """测试处理没有id的上下文"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
    <xbrli:context>
        <xbrli:entity>
            <xbrli:identifier scheme="http://www.csrc.gov.cn/fund">001056</xbrli:identifier>
        </xbrli:entity>
        <xbrli:period>
            <xbrli:instant>2024-12-31</xbrli:instant>
        </xbrli:period>
    </xbrli:context>
</xbrl>'''
        
        root = etree.fromstring(xml_content.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        # 应该忽略没有id的上下文
        assert context_parser.context_count == 0
    
    def test_context_with_missing_elements(self):
        """测试处理缺少元素的上下文"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
    <xbrli:context id="c-incomplete">
        <!-- 缺少entity和period -->
    </xbrli:context>
</xbrl>'''
        
        root = etree.fromstring(xml_content.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        # 应该能解析，但entity和period为None
        context = context_parser.get_context_details('c-incomplete')
        assert context is not None
        assert context['entity'] is None
        assert context['period'] is None
    
    def test_multiple_parse_calls(self, sample_xbrl_xml):
        """测试多次调用parse_contexts"""
        root = etree.fromstring(sample_xbrl_xml.encode('utf-8'))
        context_parser = XBRLContext(root)
        
        # 第一次解析
        context_parser.parse_contexts()
        first_count = context_parser.context_count
        
        # 第二次解析
        context_parser.parse_contexts()
        second_count = context_parser.context_count
        
        # 上下文数量应该相同（重新解析）
        assert first_count == second_count
        assert context_parser.is_parsed
    
    def test_empty_document(self):
        """测试空文档"""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
</xbrl>'''
        
        root = etree.fromstring(xml_content.encode('utf-8'))
        context_parser = XBRLContext(root)
        context_parser.parse_contexts()
        
        assert context_parser.is_parsed
        assert context_parser.context_count == 0