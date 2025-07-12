#!/usr/bin/env python3
"""
平安基金2025年度分析报告生成器
PingAn Fund 2025 Analysis Report Generator
"""

import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import statistics

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import get_logger

logger = get_logger(__name__)


class FundAnalysisReportGenerator:
    """基金分析报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.data_dir = Path("data/analysis")
        self.output_dir = Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("report_generator.initialized")
    
    def load_analysis_data(self) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """加载分析数据"""
        # 加载平安基金数据
        pingan_files = list(self.data_dir.glob("pingan_2025/pingan_funds_2025_*.json"))
        pingan_data = []
        
        if pingan_files:
            latest_pingan_file = max(pingan_files, key=lambda f: f.stat().st_mtime)
            with open(latest_pingan_file, 'r', encoding='utf-8') as f:
                pingan_data = json.load(f)
        
        # 加载同类基金数据
        comparable_data = {}
        comparable_files = list(self.data_dir.glob("comparable_2025/comparable_*.json"))
        
        for comp_file in comparable_files:
            file_name_parts = comp_file.stem.split('_')
            if len(file_name_parts) >= 3:
                fund_type = file_name_parts[1]
                with open(comp_file, 'r', encoding='utf-8') as f:
                    comparable_data[fund_type] = json.load(f)
        
        return pingan_data, comparable_data
    
    def analyze_fund_performance(self, pingan_data: List[Dict], comparable_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """分析基金业绩表现"""
        analysis_result = {
            'pingan_summary': {},
            'type_analysis': {},
            'ranking_analysis': {},
            'risk_analysis': {},
            'asset_allocation_analysis': {}
        }
        
        # 平安基金汇总分析
        if pingan_data:
            pingan_df = pd.DataFrame(pingan_data)
            
            analysis_result['pingan_summary'] = {
                'total_funds': len(pingan_data),
                'fund_types': pingan_df['fund_type'].value_counts().to_dict(),
                'avg_net_asset_value': pingan_df['net_asset_value'].mean() if 'net_asset_value' in pingan_df.columns else None,
                'avg_unit_nav': pingan_df['unit_nav'].mean() if 'unit_nav' in pingan_df.columns else None,
                'total_net_assets': pingan_df['net_asset_value'].sum() if 'net_asset_value' in pingan_df.columns else None
            }
        
        # 按类型分析
        for fund_type, comp_funds in comparable_data.items():
            if not comp_funds:
                continue
                
            # 平安基金在该类型中的数据
            pingan_type_funds = [f for f in pingan_data if f.get('fund_type') == fund_type]
            
            if not pingan_type_funds:
                continue
            
            comp_df = pd.DataFrame(comp_funds)
            pingan_type_df = pd.DataFrame(pingan_type_funds)
            
            # 计算排名
            rankings = self._calculate_rankings(pingan_type_df, comp_df, fund_type)
            
            analysis_result['type_analysis'][fund_type] = {
                'pingan_fund_count': len(pingan_type_funds),
                'comparable_fund_count': len(comp_funds),
                'pingan_avg_unit_nav': pingan_type_df['unit_nav'].mean() if 'unit_nav' in pingan_type_df.columns else None,
                'market_avg_unit_nav': comp_df['unit_nav'].mean() if 'unit_nav' in comp_df.columns else None,
                'pingan_avg_net_assets': pingan_type_df['net_asset_value'].mean() if 'net_asset_value' in pingan_type_df.columns else None,
                'market_avg_net_assets': comp_df['net_asset_value'].mean() if 'net_asset_value' in comp_df.columns else None,
                'rankings': rankings
            }
        
        return analysis_result
    
    def _calculate_rankings(self, pingan_df: pd.DataFrame, market_df: pd.DataFrame, fund_type: str) -> Dict[str, Any]:
        """计算基金排名"""
        rankings = {}
        
        # 合并数据进行排名比较
        combined_data = []
        
        # 添加平安基金数据
        for _, fund in pingan_df.iterrows():
            combined_data.append({
                'fund_code': fund.get('fund_code'),
                'fund_name': fund.get('fund_name'),
                'fund_company': fund.get('fund_company'),
                'unit_nav': fund.get('unit_nav'),
                'net_asset_value': fund.get('net_asset_value'),
                'stock_allocation': fund.get('stock_allocation'),
                'is_pingan': True
            })
        
        # 添加市场同类基金数据
        for _, fund in market_df.iterrows():
            combined_data.append({
                'fund_code': fund.get('fund_code'),
                'fund_name': fund.get('fund_name'),
                'fund_company': fund.get('fund_company'),
                'unit_nav': fund.get('unit_nav'),
                'net_asset_value': fund.get('net_asset_value'),
                'stock_allocation': fund.get('stock_allocation'),
                'is_pingan': False
            })
        
        if not combined_data:
            return rankings
        
        combined_df = pd.DataFrame(combined_data)
        
        # 按不同指标排名
        ranking_metrics = ['unit_nav', 'net_asset_value']
        
        for metric in ranking_metrics:
            if metric in combined_df.columns and combined_df[metric].notna().any():
                # 降序排列（高到低）
                sorted_df = combined_df.sort_values(by=metric, ascending=False, na_position='last')
                sorted_df = sorted_df.reset_index(drop=True)
                
                pingan_rankings = []
                for idx, row in sorted_df.iterrows():
                    if row['is_pingan']:
                        pingan_rankings.append({
                            'fund_code': row['fund_code'],
                            'fund_name': row['fund_name'],
                            'rank': idx + 1,
                            'total_funds': len(sorted_df),
                            'percentile': (idx + 1) / len(sorted_df) * 100,
                            'value': row[metric]
                        })
                
                rankings[metric] = pingan_rankings
        
        return rankings
    
    def generate_markdown_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成Markdown格式的分析报告"""
        report_content = []
        
        # 报告标题
        report_content.append("# 平安基金2025年度投资分析报告")
        report_content.append("## Investment Analysis Report for PingAn Funds 2025")
        report_content.append("")
        report_content.append(f"**报告生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
        report_content.append("")
        
        # 执行摘要
        report_content.append("## 📊 执行摘要 Executive Summary")
        report_content.append("")
        
        pingan_summary = analysis_result.get('pingan_summary', {})
        total_funds = pingan_summary.get('total_funds', 0)
        fund_types = pingan_summary.get('fund_types', {})
        total_net_assets = pingan_summary.get('total_net_assets', 0)
        
        report_content.append(f"本报告对平安基金管理有限公司在2025年的**{total_funds}只基金**进行了全面分析，并与市场同类基金进行了横向对比。")
        report_content.append("")
        
        if total_net_assets:
            report_content.append(f"**总资产规模**: {total_net_assets/100000000:.1f}亿元")
        
        if fund_types:
            report_content.append("**基金类型分布**:")
            for fund_type, count in fund_types.items():
                report_content.append(f"- {fund_type}: {count}只")
        
        report_content.append("")
        
        # 主要发现
        report_content.append("### 🎯 主要发现 Key Findings")
        report_content.append("")
        
        # 分析各类型基金表现
        type_analysis = analysis_result.get('type_analysis', {})
        
        for fund_type, analysis in type_analysis.items():
            pingan_count = analysis.get('pingan_fund_count', 0)
            market_count = analysis.get('comparable_fund_count', 0)
            
            if pingan_count > 0:
                report_content.append(f"**{fund_type}基金**:")
                report_content.append(f"- 平安基金数量: {pingan_count}只")
                report_content.append(f"- 市场对比基金: {market_count}只")
                
                # 单位净值比较
                pingan_avg_nav = analysis.get('pingan_avg_unit_nav')
                market_avg_nav = analysis.get('market_avg_unit_nav')
                
                if pingan_avg_nav and market_avg_nav:
                    performance_diff = ((pingan_avg_nav - market_avg_nav) / market_avg_nav) * 100
                    if performance_diff > 0:
                        report_content.append(f"- 平安基金平均单位净值({pingan_avg_nav:.4f})比市场平均高**{performance_diff:.1f}%**")
                    else:
                        report_content.append(f"- 平安基金平均单位净值({pingan_avg_nav:.4f})比市场平均低**{abs(performance_diff):.1f}%**")
                
                report_content.append("")
        
        # 详细分析
        report_content.append("## 📈 详细业绩分析 Detailed Performance Analysis")
        report_content.append("")
        
        for fund_type, analysis in type_analysis.items():
            rankings = analysis.get('rankings', {})
            
            if not rankings:
                continue
                
            report_content.append(f"### {fund_type}基金市场排名")
            report_content.append("")
            
            # 单位净值排名
            if 'unit_nav' in rankings:
                report_content.append("#### 单位净值排名 (Unit NAV Ranking)")
                report_content.append("")
                report_content.append("| 基金代码 | 基金名称 | 单位净值 | 市场排名 | 百分位 |")
                report_content.append("|---------|---------|---------|---------|--------|")
                
                for ranking in rankings['unit_nav']:
                    fund_code = ranking['fund_code']
                    fund_name = ranking['fund_name'][:20] + "..." if len(ranking['fund_name']) > 20 else ranking['fund_name']
                    value = ranking['value']
                    rank = ranking['rank']
                    total = ranking['total_funds']
                    percentile = ranking['percentile']
                    
                    report_content.append(f"| {fund_code} | {fund_name} | {value:.4f} | {rank}/{total} | {percentile:.1f}% |")
                
                report_content.append("")
            
            # 资产规模排名
            if 'net_asset_value' in rankings:
                report_content.append("#### 资产规模排名 (Assets Under Management Ranking)")
                report_content.append("")
                report_content.append("| 基金代码 | 基金名称 | 净资产价值(亿元) | 市场排名 | 百分位 |")
                report_content.append("|---------|---------|----------------|---------|--------|")
                
                for ranking in rankings['net_asset_value']:
                    fund_code = ranking['fund_code']
                    fund_name = ranking['fund_name'][:20] + "..." if len(ranking['fund_name']) > 20 else ranking['fund_name']
                    value = ranking['value'] / 100000000 if ranking['value'] else 0  # 转换为亿元
                    rank = ranking['rank']
                    total = ranking['total_funds']
                    percentile = ranking['percentile']
                    
                    report_content.append(f"| {fund_code} | {fund_name} | {value:.2f} | {rank}/{total} | {percentile:.1f}% |")
                
                report_content.append("")
        
        # 投资建议和总结
        report_content.append("## 💡 投资分析与建议 Investment Analysis & Recommendations")
        report_content.append("")
        
        report_content.append("### 优势分析 Strengths")
        report_content.append("")
        
        # 计算整体表现
        total_rankings = []
        for fund_type, analysis in type_analysis.items():
            rankings = analysis.get('rankings', {})
            if 'unit_nav' in rankings:
                for ranking in rankings['unit_nav']:
                    total_rankings.append(ranking['percentile'])
        
        if total_rankings:
            avg_percentile = statistics.mean(total_rankings)
            if avg_percentile <= 30:
                report_content.append("- 🏆 **表现优异**: 平安基金在市场中整体排名靠前，显示出良好的投资管理能力")
            elif avg_percentile <= 60:
                report_content.append("- 📊 **表现稳健**: 平安基金在市场中处于中上游水平，具备稳定的投资表现")
            else:
                report_content.append("- 📈 **发展潜力**: 平安基金仍有较大提升空间，建议加强投研能力建设")
        
        report_content.append("")
        
        # 风险提示
        report_content.append("### 风险提示 Risk Disclaimer")
        report_content.append("")
        report_content.append("- 📋 本报告基于公开的基金报告数据进行分析，仅供参考")
        report_content.append("- ⚠️ 基金投资有风险，过往业绩不代表未来表现")
        report_content.append("- 💰 投资者应根据自身风险承受能力谨慎投资")
        report_content.append("- 📊 本分析不构成投资建议，具体投资决策请咨询专业理财顾问")
        report_content.append("")
        
        # 附录
        report_content.append("## 📎 附录 Appendix")
        report_content.append("")
        report_content.append("### 数据来源")
        report_content.append("- 中国证监会基金报告数据")
        report_content.append("- 公开披露的基金定期报告")
        report_content.append("- 基金公司官方网站")
        report_content.append("")
        
        report_content.append("### 分析方法")
        report_content.append("- 基于XBRL标准化数据解析")
        report_content.append("- 横向对比分析方法")
        report_content.append("- 百分位排名统计")
        report_content.append("")
        
        report_content.append("---")
        report_content.append("*本报告由平安基金报告自动化采集与分析平台生成*")
        report_content.append("")
        report_content.append("🤖 *Generated by Fund Report Automation Platform*")
        
        return "\n".join(report_content)
    
    def save_report(self, report_content: str, file_name: str) -> bool:
        """保存报告到文件"""
        try:
            report_file = self.output_dir / file_name
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info("report_saved", file_path=str(report_file))
            return True
            
        except Exception as e:
            logger.error("report_save_error", error=str(e))
            return False


def main():
    """主函数"""
    print("🚀 平安基金2025年度分析报告生成")
    print("=" * 60)
    
    generator = FundAnalysisReportGenerator()
    
    try:
        # 加载数据
        print("📊 加载分析数据...")
        pingan_data, comparable_data = generator.load_analysis_data()
        
        if not pingan_data:
            print("❌ 未找到平安基金数据")
            return False
        
        print(f"✅ 平安基金数据: {len(pingan_data)} 条记录")
        
        total_comparable = sum(len(data) for data in comparable_data.values())
        print(f"✅ 同类基金数据: {total_comparable} 条记录")
        print(f"✅ 覆盖基金类型: {list(comparable_data.keys())}")
        
        # 分析数据
        print("\n📈 执行业绩分析...")
        analysis_result = generator.analyze_fund_performance(pingan_data, comparable_data)
        
        # 生成报告
        print("\n📝 生成分析报告...")
        report_content = generator.generate_markdown_report(analysis_result)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"平安基金2025年度投资分析报告_{timestamp}.md"
        
        if generator.save_report(report_content, report_filename):
            print(f"✅ 报告已生成: {generator.output_dir / report_filename}")
            
            # 输出报告概要
            print(f"\n📊 报告概要:")
            total_funds = analysis_result['pingan_summary'].get('total_funds', 0)
            print(f"  • 分析基金总数: {total_funds} 只")
            
            type_analysis = analysis_result.get('type_analysis', {})
            print(f"  • 涵盖基金类型: {len(type_analysis)} 类")
            
            for fund_type, analysis in type_analysis.items():
                pingan_count = analysis.get('pingan_fund_count', 0)
                market_count = analysis.get('comparable_fund_count', 0)
                print(f"    - {fund_type}: 平安{pingan_count}只 vs 市场{market_count}只")
            
            # 显示报告文件大小
            report_file = generator.output_dir / report_filename
            file_size = report_file.stat().st_size / 1024  # KB
            print(f"  • 报告文件大小: {file_size:.1f} KB")
            
            return True
        else:
            print("❌ 报告保存失败")
            return False
            
    except Exception as e:
        print(f"❌ 报告生成过程发生错误: {e}")
        logger.error("main_report_generation_error", error=str(e))
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)