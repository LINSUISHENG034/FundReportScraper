"""
增强版批量下载脚本 - 支持完整的6个搜索参数
Enhanced Batch Download Script - Supporting All 6 Search Parameters

基于真实测试结果，支持CSRC网站的完整搜索功能
"""

import asyncio
import json
import time
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional
import aiohttp
from datetime import date

# 导入我们的参数枚举模块
from fund_search_parameters import (
    FundSearchCriteria, 
    ReportType, 
    FundType, 
    SearchPresets
)


class EnhancedFundReportProcessor:
    """增强版基金报告处理器"""
    
    def __init__(self):
        self.base_url = "http://eid.csrc.gov.cn/fund/disclose/advanced_search_xbrl.do"
        self.instance_url = "http://eid.csrc.gov.cn/fund/disclose/instance_html_view.do"
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def search_reports(self, criteria: FundSearchCriteria) -> List[Dict]:
        """根据搜索条件获取报告列表"""
        print(f"🔍 搜索条件: {criteria.get_description()}")
        
        # 构建aoData参数
        ao_data = criteria.to_ao_data_list()
        ao_data_json = json.dumps(ao_data)
        
        # 构建请求参数
        timestamp = int(time.time() * 1000)
        params = {
            'aoData': ao_data_json,
            '_': timestamp
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    # 强制解析JSON，忽略Content-Type
                    text = await response.text()
                    try:
                        data = json.loads(text)
                        reports = data.get('aaData', [])
                        print(f"✅ 找到 {len(reports)} 条报告")
                        return reports
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON解析失败: {e}")
                        print(f"   响应内容前200字符: {text[:200]}")
                        return []
                else:
                    print(f"❌ 请求失败: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            return []
    
    async def search_all_pages(self, criteria: FundSearchCriteria, max_pages: Optional[int] = None) -> List[Dict]:
        """获取所有页面的报告"""
        all_reports = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                print(f"⏹️ 达到最大页数限制: {max_pages}")
                break
                
            # 更新搜索条件的页码
            current_criteria = FundSearchCriteria(
                year=criteria.year,
                report_type=criteria.report_type,
                fund_type=criteria.fund_type,
                fund_company_short_name=criteria.fund_company_short_name,
                fund_code=criteria.fund_code,
                fund_short_name=criteria.fund_short_name,
                start_upload_date=criteria.start_upload_date,
                end_upload_date=criteria.end_upload_date,
                page=page,
                page_size=criteria.page_size
            )
            
            reports = await self.search_reports(current_criteria)
            
            if not reports:
                print(f"📄 第 {page} 页无数据，搜索结束")
                break
                
            all_reports.extend(reports)
            print(f"📄 第 {page} 页: {len(reports)} 条报告")
            
            # 如果返回的报告数少于页面大小，说明是最后一页
            if len(reports) < criteria.page_size:
                print(f"📄 已到最后一页")
                break
                
            page += 1
            await asyncio.sleep(1)  # 避免请求过快
            
        print(f"🎯 总计获取: {len(all_reports)} 条报告")
        return all_reports
    
    async def download_report(self, report: Dict, save_dir: Path) -> bool:
        """下载单个报告"""
        try:
            upload_info_id = report['uploadInfoId']  # 使用字典键
            fund_code = report['fundCode']           # 使用字典键

            # 构建下载URL（使用正确的instance_html_view.do端点）
            download_url = f"{self.instance_url}?instanceid={upload_info_id}"

            # 生成文件名
            timestamp = int(time.time())
            filename = f"{fund_code}_REPORT_{timestamp}.xbrl"
            file_path = save_dir / filename
            
            async with self.session.get(download_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # 保存文件
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    print(f"✅ 下载成功: {filename}")
                    return True
                else:
                    print(f"❌ 下载失败: {fund_code}, 状态码: {response.status}")
                    return False

        except Exception as e:
            print(f"❌ 下载异常: {report.get('fundCode', 'Unknown')}, 错误: {e}")
            return False
    
    async def batch_download(self, reports: List[Dict], save_dir: Path, max_concurrent: int = 3) -> Dict:
        """批量下载报告"""
        save_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 保存目录: {save_dir}")
        print(f"📊 开始批量下载 {len(reports)} 个报告...")
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(report):
            async with semaphore:
                return await self.download_report(report, save_dir)
        
        # 执行批量下载
        start_time = time.time()
        results = await asyncio.gather(
            *[download_with_semaphore(report) for report in reports],
            return_exceptions=True
        )
        end_time = time.time()
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        failed_count = len(reports) - success_count
        
        stats = {
            'total': len(reports),
            'success': success_count,
            'failed': failed_count,
            'duration': end_time - start_time
        }
        
        print(f"\n📊 下载统计:")
        print(f"   总数: {stats['total']}")
        print(f"   成功: {stats['success']}")
        print(f"   失败: {stats['failed']}")
        print(f"   耗时: {stats['duration']:.2f}秒")
        
        return stats


# 测试函数
async def test_enhanced_search():
    """测试增强版搜索功能"""
    print("=== 测试增强版搜索功能 ===")
    
    async with EnhancedFundReportProcessor() as processor:
        
        # 测试1: 基本年度报告搜索
        print("\n1. 测试基本年度报告搜索")
        criteria1 = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            page_size=10
        )
        reports1 = await processor.search_reports(criteria1)
        print(f"   结果: {len(reports1)} 条报告")
        
        # 测试2: 按基金公司搜索
        print("\n2. 测试按基金公司搜索")
        criteria2 = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            fund_company_short_name="工银瑞信",
            page_size=10
        )
        reports2 = await processor.search_reports(criteria2)
        print(f"   结果: {len(reports2)} 条报告")
        
        # 测试3: 按基金类型搜索
        print("\n3. 测试按基金类型搜索")
        criteria3 = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            fund_type=FundType.QDII,
            page_size=10
        )
        reports3 = await processor.search_reports(criteria3)
        print(f"   结果: {len(reports3)} 条报告")
        
        # 测试4: 按基金代码搜索
        print("\n4. 测试按基金代码搜索")
        criteria4 = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            fund_code="001648",
            page_size=10
        )
        reports4 = await processor.search_reports(criteria4)
        print(f"   结果: {len(reports4)} 条报告")
        
        # 测试5: 组合条件搜索
        print("\n5. 测试组合条件搜索")
        criteria5 = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            fund_company_short_name="工银瑞信",
            fund_type=FundType.MIXED,
            page_size=10
        )
        reports5 = await processor.search_reports(criteria5)
        print(f"   结果: {len(reports5)} 条报告")


async def test_batch_download():
    """测试批量下载功能"""
    print("\n=== 测试批量下载功能 ===")
    
    async with EnhancedFundReportProcessor() as processor:
        # 搜索少量报告进行下载测试
        criteria = FundSearchCriteria(
            year=2024,
            fund_type=FundType.FOF,
            report_type=ReportType.QUARTERLY_Q4,
            page_size=1  # 只下载5个进行测试2
        )
        
        reports = await processor.search_reports(criteria)
        
        if reports:
            save_dir = Path("data/SEMI_ANNUAL")
            stats = await processor.batch_download(reports, save_dir, max_concurrent=2)
            print(f"✅ 批量下载测试完成")
        else:
            print("❌ 未找到报告，无法测试下载")


async def main():
    """主函数"""
    print("🚀 增强版基金报告下载器")
    print("支持完整的6个搜索参数")
    
    while True:
        print("\n选择操作:")
        print("1. 测试搜索功能")
        print("2. 测试批量下载")
        print("3. 退出")
        
        choice = input("请选择 (1-3): ").strip()
        
        if choice == "1":
            await test_enhanced_search()
        elif choice == "2":
            await test_batch_download()
        elif choice == "3":
            print("👋 再见!")
            break
        else:
            print("❌ 无效选择，请重试")


if __name__ == "__main__":
    asyncio.run(main())
