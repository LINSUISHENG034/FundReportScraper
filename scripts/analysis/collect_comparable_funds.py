#!/usr/bin/env python3
"""
同类型基金数据收集脚本
Comparable funds data collection script
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.scrapers.fund_scraper import FundReportScraper
from src.parsers.xbrl_parser import XBRLParser
from src.core.logging import get_logger
from src.utils.rate_limiter import RateLimiter
from scripts.analysis.collect_pingan_2025_data import FundAnalysisData, PingAnFundCollector

logger = get_logger(__name__)


class ComparableFundCollector:
    """同类型基金数据收集器"""
    
    def __init__(self):
        """初始化收集器"""
        self.scraper = FundReportScraper()
        self.parser = XBRLParser()
        self.rate_limiter = RateLimiter(max_tokens=5, refill_rate=1.0)  # 更保守的限流
        
        # 各类型代表性基金代码（用于对比分析）
        self.comparable_funds = {
            "混合型": [
                "000001",  # 华夏成长混合
                "110011",  # 易方达中小盘混合
                "163402",  # 兴全趋势投资混合
                "000746",  # 招商行业精选股票
                "001102",  # 前海开源国家比较优势混合
                "002121",  # 广发沪港深新起点股票
                "003095",  # 中欧医疗健康混合A
                "005918",  # 天弘沪深300指数增强A
            ],
            "债券型": [
                "000003",  # 中海可转债债券A
                "161603",  # 融通债券A
                "100018",  # 富国天利增长债券
                "217203",  # 招商安泰债券A
                "485105",  # 工银四季收益债券A
                "000045",  # 工银产业债债券A
                "004716",  # 南方和利定期开放债券A
            ],
            "股票型": [
                "000478",  # 建信中证红利潜力指数
                "160716",  # 嘉实基本面50指数
                "213010",  # 宝盈中证100指数增强
                "450003",  # 国富潜力组合混合
                "519066",  # 汇添富蓝筹稳健灵活配置混合
                "000308",  # 建信创新中国混合
            ]
        }
        
        logger.info("comparable_fund_collector.initialized")
    
    async def collect_comparable_funds_by_type(self, fund_type: str) -> List[FundAnalysisData]:
        """
        收集指定类型的同类基金数据
        
        Args:
            fund_type: 基金类型
            
        Returns:
            同类基金分析数据列表
        """
        if fund_type not in self.comparable_funds:
            logger.warning("unsupported_fund_type", fund_type=fund_type)
            return []
        
        fund_codes = self.comparable_funds[fund_type]
        logger.info("collecting_comparable_funds", fund_type=fund_type, fund_count=len(fund_codes))
        
        collected_data = []
        
        for fund_code in fund_codes:
            try:
                # 限流控制
                await self.rate_limiter.acquire()
                
                logger.info("collecting_comparable_fund", fund_code=fund_code, fund_type=fund_type)
                
                # 获取基金报告
                reports = await self.scraper.get_fund_reports(fund_code)
                if not reports:
                    logger.warning("no_reports_found", fund_code=fund_code)
                    continue
                
                # 获取最新的2025年报告
                latest_2025_report = None
                for report in reports:
                    if report['report_date'].year == 2025:
                        if latest_2025_report is None or report['report_date'] > latest_2025_report['report_date']:
                            latest_2025_report = report
                
                if not latest_2025_report:
                    logger.warning("no_2025_report_found", fund_code=fund_code)
                    continue
                
                # 下载并解析报告
                report_content = await self.scraper.download_report(latest_2025_report['download_url'])
                if not report_content:
                    logger.error("failed_to_download_report", fund_code=fund_code)
                    continue
                
                # 解析XBRL数据
                self.parser.load_from_content(report_content.decode('utf-8'))
                
                fund_info = self.parser.extract_fund_basic_info()
                asset_allocation = self.parser.extract_asset_allocation()
                top_holdings = self.parser.extract_top_holdings()
                industry_allocation = self.parser.extract_industry_allocation()
                
                if not fund_info:
                    logger.error("failed_to_parse_fund_info", fund_code=fund_code)
                    continue
                
                # 确定基金公司
                fund_company = self._determine_fund_company(fund_info.fund_name, fund_code)
                
                # 构建分析数据
                analysis_data = FundAnalysisData(
                    fund_code=fund_info.fund_code,
                    fund_name=fund_info.fund_name,
                    fund_company=fund_company,
                    fund_type=fund_type,
                    establishment_date=None,
                    net_asset_value=float(fund_info.net_asset_value) if fund_info.net_asset_value else None,
                    unit_nav=float(fund_info.unit_nav) if fund_info.unit_nav else None,
                    total_return_ytd=None,
                    annual_return=None,
                    volatility=None,
                    sharpe_ratio=None,
                    max_drawdown=None,
                    stock_allocation=float(asset_allocation.stock_ratio) if asset_allocation and asset_allocation.stock_ratio else None,
                    bond_allocation=float(asset_allocation.bond_ratio) if asset_allocation and asset_allocation.bond_ratio else None,
                    cash_allocation=float(asset_allocation.cash_ratio) if asset_allocation and asset_allocation.cash_ratio else None,
                    top_holdings=[fund_data.__dict__ for fund_data in top_holdings] if top_holdings else [],
                    industry_allocation={ind.industry_name: float(ind.allocation_ratio) for ind in industry_allocation} if industry_allocation else {},
                    report_date=latest_2025_report['report_date'],
                    data_collection_time=datetime.now()
                )
                
                collected_data.append(analysis_data)
                logger.info("comparable_fund_collected", fund_code=fund_code, fund_name=fund_info.fund_name)
                
                # 添加延迟
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error("comparable_fund_collection_error", fund_code=fund_code, error=str(e))
                continue
        
        logger.info("comparable_funds_collection_completed", 
                   fund_type=fund_type,
                   total_requested=len(fund_codes),
                   successfully_collected=len(collected_data))
        
        return collected_data
    
    def _determine_fund_company(self, fund_name: str, fund_code: str) -> str:
        """根据基金名称和代码确定基金公司"""
        if "华夏" in fund_name:
            return "华夏基金管理有限公司"
        elif "易方达" in fund_name:
            return "易方达基金管理有限公司"
        elif "兴全" in fund_name or "兴业全球" in fund_name:
            return "兴全基金管理有限公司"
        elif "招商" in fund_name:
            return "招商基金管理有限公司"
        elif "前海开源" in fund_name:
            return "前海开源基金管理有限公司"
        elif "广发" in fund_name:
            return "广发基金管理有限公司"
        elif "中欧" in fund_name:
            return "中欧基金管理有限公司"
        elif "天弘" in fund_name:
            return "天弘基金管理有限公司"
        elif "中海" in fund_name:
            return "中海基金管理有限公司"
        elif "融通" in fund_name:
            return "融通基金管理有限公司"
        elif "富国" in fund_name:
            return "富国基金管理有限公司"
        elif "工银" in fund_name:
            return "工银瑞信基金管理有限公司"
        elif "南方" in fund_name:
            return "南方基金管理股份有限公司"
        elif "建信" in fund_name:
            return "建信基金管理有限责任公司"
        elif "嘉实" in fund_name:
            return "嘉实基金管理有限公司"
        elif "宝盈" in fund_name:
            return "宝盈基金管理有限公司"
        elif "国富" in fund_name:
            return "国富基金管理有限公司"
        elif "汇添富" in fund_name:
            return "汇添富基金管理股份有限公司"
        else:
            # 根据基金代码前缀推断
            if fund_code.startswith("00"):
                return "未知基金公司"
            else:
                return "其他基金公司"
    
    async def collect_all_comparable_funds(self, target_fund_types: List[str]) -> Dict[str, List[FundAnalysisData]]:
        """收集所有目标类型的同类基金数据"""
        logger.info("starting_comparable_fund_collection", target_types=target_fund_types)
        
        all_data = {}
        
        for fund_type in target_fund_types:
            try:
                print(f"\n📊 收集{fund_type}基金数据...")
                comparable_data = await self.collect_comparable_funds_by_type(fund_type)
                all_data[fund_type] = comparable_data
                
                print(f"✅ {fund_type}基金收集完成: {len(comparable_data)} 只")
                
            except Exception as e:
                logger.error("fund_type_collection_error", fund_type=fund_type, error=str(e))
                all_data[fund_type] = []
                continue
        
        return all_data


async def main():
    """主函数"""
    print("🚀 同类型基金数据收集")
    print("=" * 60)
    
    # 创建输出目录
    output_dir = Path("data/analysis/comparable_2025")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    collector = ComparableFundCollector()
    
    try:
        # 收集各类型基金数据
        target_types = ["混合型", "债券型", "股票型"]
        comparable_data = await collector.collect_all_comparable_funds(target_types)
        
        # 保存各类型数据
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for fund_type, data in comparable_data.items():
            if data:
                # 保存JSON数据
                file_path = output_dir / f"comparable_{fund_type}_{timestamp}.json"
                
                # 转换为可序列化格式
                serializable_data = []
                for fund_data in data:
                    fund_dict = fund_data.__dict__.copy()
                    if fund_dict.get('establishment_date'):
                        fund_dict['establishment_date'] = fund_dict['establishment_date'].isoformat()
                    fund_dict['report_date'] = fund_dict['report_date'].isoformat()
                    fund_dict['data_collection_time'] = fund_dict['data_collection_time'].isoformat()
                    serializable_data.append(fund_dict)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ {fund_type}数据已保存至: {file_path}")
        
        # 输出统计信息
        print(f"\n📈 同类基金数据收集统计:")
        total_collected = 0
        for fund_type, data in comparable_data.items():
            count = len(data)
            total_collected += count
            print(f"  • {fund_type}: {count} 只基金")
        
        print(f"  • 总计收集: {total_collected} 只基金")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据收集过程发生错误: {e}")
        logger.error("main_comparable_collection_error", error=str(e))
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)