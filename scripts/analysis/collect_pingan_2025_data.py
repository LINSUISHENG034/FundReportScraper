#!/usr/bin/env python3
"""
平安基金2025年数据自动化收集脚本
Automated data collection script for PingAn funds in 2025
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.scrapers.fund_scraper import FundReportScraper
from src.parsers.xbrl_parser import XBRLParser
from src.services.data_persistence import FundDataPersistenceService
from src.storage.minio_client import MinIOClient
from src.core.logging import get_logger
from src.utils.rate_limiter import RateLimiter
from src.models.database import Fund, FundReport

logger = get_logger(__name__)


@dataclass
class FundAnalysisData:
    """基金分析数据结构"""
    fund_code: str
    fund_name: str
    fund_company: str
    fund_type: str
    establishment_date: Optional[date]
    net_asset_value: Optional[float]
    unit_nav: Optional[float]
    total_return_ytd: Optional[float]
    annual_return: Optional[float]
    volatility: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    stock_allocation: Optional[float]
    bond_allocation: Optional[float]
    cash_allocation: Optional[float]
    top_holdings: List[Dict[str, Any]]
    industry_allocation: Dict[str, float]
    report_date: date
    data_collection_time: datetime


class PingAnFundCollector:
    """平安基金数据收集器"""
    
    def __init__(self):
        """初始化收集器"""
        self.scraper = FundReportScraper()
        self.parser = XBRLParser()
        self.rate_limiter = RateLimiter(max_tokens=10, refill_rate=2.0)
        self.collected_funds = []
        
        # 平安基金公司相关基金代码
        self.pingan_fund_codes = [
            # 平安大华品牌
            "000327",  # 平安大华添利债券A
            "000328",  # 平安大华添利债券C
            "001304",  # 平安大华行业先锋混合
            "001305",  # 平安大华智慧中国灵活配置混合
            "002295",  # 平安大华新鑫先锋混合A
            "002296",  # 平安大华新鑫先锋混合C
            "003336",  # 平安大华鼎弘混合A
            "003337",  # 平安大华鼎弘混合C
            "005447",  # 平安中证光伏产业指数A
            "005448",  # 平安中证光伏产业指数C
            "006930",  # 平安惠盈纯债债券A
            "006931",  # 平安惠盈纯债债券C
            "008322",  # 平安核心优势混合A
            "008323",  # 平安核心优势混合C
            "009878",  # 平安增利六个月定期开放债券A
            "009879",  # 平安增利六个月定期开放债券C
        ]
        
        logger.info("ping_an_collector.initialized", fund_count=len(self.pingan_fund_codes))
    
    async def collect_single_fund_data(self, fund_code: str) -> Optional[FundAnalysisData]:
        """
        收集单个基金数据
        
        Args:
            fund_code: 基金代码
            
        Returns:
            基金分析数据
        """
        try:
            # 限流控制
            await self.rate_limiter.acquire()
            
            logger.info("collecting_fund_data", fund_code=fund_code)
            
            # 获取基金报告列表
            reports = await self.scraper.get_fund_reports(fund_code)
            if not reports:
                logger.warning("no_reports_found", fund_code=fund_code)
                return None
            
            # 获取最新的2025年报告
            latest_2025_report = None
            for report in reports:
                if report['report_date'].year == 2025:
                    if latest_2025_report is None or report['report_date'] > latest_2025_report['report_date']:
                        latest_2025_report = report
            
            if not latest_2025_report:
                logger.warning("no_2025_report_found", fund_code=fund_code)
                return None
            
            # 下载并解析报告
            report_content = await self.scraper.download_report(latest_2025_report['download_url'])
            if not report_content:
                logger.error("failed_to_download_report", fund_code=fund_code)
                return None
            
            # 解析XBRL数据
            self.parser.load_from_content(report_content.decode('utf-8'))
            
            fund_info = self.parser.extract_fund_basic_info()
            asset_allocation = self.parser.extract_asset_allocation()
            top_holdings = self.parser.extract_top_holdings()
            industry_allocation = self.parser.extract_industry_allocation()
            
            if not fund_info:
                logger.error("failed_to_parse_fund_info", fund_code=fund_code)
                return None
            
            # 构建分析数据
            analysis_data = FundAnalysisData(
                fund_code=fund_info.fund_code,
                fund_name=fund_info.fund_name,
                fund_company="平安基金管理有限公司",
                fund_type=self._determine_fund_type(fund_info.fund_name),
                establishment_date=None,  # 需要从其他数据源获取
                net_asset_value=float(fund_info.net_asset_value) if fund_info.net_asset_value else None,
                unit_nav=float(fund_info.unit_nav) if fund_info.unit_nav else None,
                total_return_ytd=None,  # 需要计算
                annual_return=None,  # 需要计算
                volatility=None,  # 需要计算
                sharpe_ratio=None,  # 需要计算
                max_drawdown=None,  # 需要计算
                stock_allocation=float(asset_allocation.stock_ratio) if asset_allocation and asset_allocation.stock_ratio else None,
                bond_allocation=float(asset_allocation.bond_ratio) if asset_allocation and asset_allocation.bond_ratio else None,
                cash_allocation=float(asset_allocation.cash_ratio) if asset_allocation and asset_allocation.cash_ratio else None,
                top_holdings=[asdict(holding) for holding in top_holdings] if top_holdings else [],
                industry_allocation={ind.industry_name: float(ind.allocation_ratio) for ind in industry_allocation} if industry_allocation else {},
                report_date=latest_2025_report['report_date'],
                data_collection_time=datetime.now()
            )
            
            logger.info("fund_data_collected", fund_code=fund_code, fund_name=fund_info.fund_name)
            return analysis_data
            
        except Exception as e:
            logger.error("fund_collection_failed", fund_code=fund_code, error=str(e))
            return None
    
    def _determine_fund_type(self, fund_name: str) -> str:
        """根据基金名称判断基金类型"""
        if "股票" in fund_name or "指数" in fund_name:
            return "股票型"
        elif "债券" in fund_name or "纯债" in fund_name:
            return "债券型"
        elif "混合" in fund_name:
            return "混合型"
        elif "货币" in fund_name:
            return "货币型"
        else:
            return "其他"
    
    async def collect_all_pingan_funds(self) -> List[FundAnalysisData]:
        """收集所有平安基金数据"""
        logger.info("starting_pingan_fund_collection", total_funds=len(self.pingan_fund_codes))
        
        collected_data = []
        
        for fund_code in self.pingan_fund_codes:
            try:
                fund_data = await self.collect_single_fund_data(fund_code)
                if fund_data:
                    collected_data.append(fund_data)
                    self.collected_funds.append(fund_data)
                
                # 添加延迟避免过于频繁的请求
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error("fund_collection_error", fund_code=fund_code, error=str(e))
                continue
        
        logger.info("pingan_fund_collection_completed", 
                   total_requested=len(self.pingan_fund_codes),
                   successfully_collected=len(collected_data))
        
        return collected_data
    
    def save_collected_data(self, data: List[FundAnalysisData], file_path: str) -> bool:
        """保存收集的数据到文件"""
        try:
            # 转换为可序列化的格式
            serializable_data = []
            for fund_data in data:
                fund_dict = asdict(fund_data)
                # 处理日期序列化
                if fund_dict['establishment_date']:
                    fund_dict['establishment_date'] = fund_dict['establishment_date'].isoformat()
                fund_dict['report_date'] = fund_dict['report_date'].isoformat()
                fund_dict['data_collection_time'] = fund_dict['data_collection_time'].isoformat()
                serializable_data.append(fund_dict)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            
            logger.info("data_saved_successfully", file_path=file_path, record_count=len(data))
            return True
            
        except Exception as e:
            logger.error("data_save_failed", file_path=file_path, error=str(e))
            return False


async def main():
    """主函数"""
    print("🚀 平安基金2025年数据自动化收集")
    print("=" * 60)
    
    # 创建输出目录
    output_dir = Path("data/analysis/pingan_2025")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    collector = PingAnFundCollector()
    
    try:
        # 收集平安基金数据
        print("\n📊 开始收集平安基金2025年数据...")
        pingan_data = await collector.collect_all_pingan_funds()
        
        if not pingan_data:
            print("❌ 没有收集到任何平安基金数据")
            return False
        
        # 保存数据
        data_file = output_dir / f"pingan_funds_2025_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if collector.save_collected_data(pingan_data, str(data_file)):
            print(f"✅ 平安基金数据已保存至: {data_file}")
        
        # 输出收集统计
        print(f"\n📈 数据收集统计:")
        print(f"  • 目标基金数量: {len(collector.pingan_fund_codes)}")
        print(f"  • 成功收集数量: {len(pingan_data)}")
        print(f"  • 收集成功率: {len(pingan_data)/len(collector.pingan_fund_codes)*100:.1f}%")
        
        # 按基金类型分类统计
        type_stats = {}
        for fund in pingan_data:
            fund_type = fund.fund_type
            type_stats[fund_type] = type_stats.get(fund_type, 0) + 1
        
        print(f"\n📊 基金类型分布:")
        for fund_type, count in type_stats.items():
            print(f"  • {fund_type}: {count} 只")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据收集过程发生错误: {e}")
        logger.error("main_collection_error", error=str(e))
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)