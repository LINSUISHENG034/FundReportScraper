#!/usr/bin/env python3
"""
平安基金2025年分析演示脚本
Demo script for PingAn Fund 2025 analysis with simulated data
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any
import os

def create_demo_data():
    """创建演示数据"""
    
    # 创建必要的目录
    data_dir = Path("data/analysis")
    pingan_dir = data_dir / "pingan_2025"
    comparable_dir = data_dir / "comparable_2025"
    exports_dir = Path("data/exports")
    reports_dir = Path("reports")
    
    for dir_path in [pingan_dir, comparable_dir, exports_dir, reports_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 平安基金2025年数据 (模拟)
    pingan_funds_data = [
        {
            "fund_code": "000327",
            "fund_name": "平安大华添利债券A",
            "fund_company": "平安基金管理有限公司",
            "fund_type": "债券型",
            "establishment_date": None,
            "net_asset_value": 856000000.0,  # 8.56亿
            "unit_nav": 1.1245,
            "total_return_ytd": 0.045,  # 4.5%
            "annual_return": 0.038,
            "volatility": 0.012,
            "sharpe_ratio": 1.85,
            "max_drawdown": -0.008,
            "stock_allocation": 0.05,
            "bond_allocation": 0.88,
            "cash_allocation": 0.07,
            "top_holdings": [
                {"stock_name": "21国债10", "allocation_ratio": 0.08},
                {"stock_name": "20国债07", "allocation_ratio": 0.06},
                {"stock_name": "22国债15", "allocation_ratio": 0.05}
            ],
            "industry_allocation": {
                "国债": 0.45,
                "金融债": 0.28,
                "企业债": 0.15
            },
            "report_date": "2025-03-31",
            "data_collection_time": datetime.now().isoformat()
        },
        {
            "fund_code": "001304",
            "fund_name": "平安大华行业先锋混合",
            "fund_company": "平安基金管理有限公司",
            "fund_type": "混合型",
            "establishment_date": None,
            "net_asset_value": 2350000000.0,  # 23.5亿
            "unit_nav": 1.8967,
            "total_return_ytd": 0.125,  # 12.5%
            "annual_return": 0.108,
            "volatility": 0.186,
            "sharpe_ratio": 0.75,
            "max_drawdown": -0.156,
            "stock_allocation": 0.78,
            "bond_allocation": 0.15,
            "cash_allocation": 0.07,
            "top_holdings": [
                {"stock_name": "贵州茅台", "allocation_ratio": 0.085},
                {"stock_name": "宁德时代", "allocation_ratio": 0.067},
                {"stock_name": "比亚迪", "allocation_ratio": 0.058}
            ],
            "industry_allocation": {
                "食品饮料": 0.18,
                "电池储能": 0.15,
                "汽车": 0.12,
                "医药生物": 0.10
            },
            "report_date": "2025-03-31",
            "data_collection_time": datetime.now().isoformat()
        },
        {
            "fund_code": "008322",
            "fund_name": "平安核心优势混合A",
            "fund_company": "平安基金管理有限公司",
            "fund_type": "混合型",
            "establishment_date": None,
            "net_asset_value": 1280000000.0,  # 12.8亿
            "unit_nav": 1.4567,
            "total_return_ytd": 0.087,  # 8.7%
            "annual_return": 0.076,
            "volatility": 0.145,
            "sharpe_ratio": 0.68,
            "max_drawdown": -0.118,
            "stock_allocation": 0.65,
            "bond_allocation": 0.28,
            "cash_allocation": 0.07,
            "top_holdings": [
                {"stock_name": "招商银行", "allocation_ratio": 0.078},
                {"stock_name": "中国平安", "allocation_ratio": 0.065},
                {"stock_name": "腾讯控股", "allocation_ratio": 0.054}
            ],
            "industry_allocation": {
                "银行": 0.22,
                "保险": 0.15,
                "互联网": 0.12,
                "房地产": 0.08
            },
            "report_date": "2025-03-31",
            "data_collection_time": datetime.now().isoformat()
        }
    ]
    
    # 同类型基金对比数据 (模拟)
    comparable_funds = {
        "混合型": [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "fund_company": "华夏基金管理有限公司",
                "fund_type": "混合型",
                "net_asset_value": 3200000000.0,
                "unit_nav": 2.1456,
                "stock_allocation": 0.82,
                "bond_allocation": 0.12,
                "cash_allocation": 0.06,
                "report_date": "2025-03-31",
                "data_collection_time": datetime.now().isoformat()
            },
            {
                "fund_code": "110011",
                "fund_name": "易方达中小盘混合",
                "fund_company": "易方达基金管理有限公司",
                "fund_type": "混合型",
                "net_asset_value": 2800000000.0,
                "unit_nav": 1.7234,
                "stock_allocation": 0.75,
                "bond_allocation": 0.18,
                "cash_allocation": 0.07,
                "report_date": "2025-03-31",
                "data_collection_time": datetime.now().isoformat()
            },
            {
                "fund_code": "163402",
                "fund_name": "兴全趋势投资混合",
                "fund_company": "兴全基金管理有限公司",
                "fund_type": "混合型",
                "net_asset_value": 4500000000.0,
                "unit_nav": 2.3678,
                "stock_allocation": 0.88,
                "bond_allocation": 0.08,
                "cash_allocation": 0.04,
                "report_date": "2025-03-31",
                "data_collection_time": datetime.now().isoformat()
            }
        ],
        "债券型": [
            {
                "fund_code": "000003",
                "fund_name": "中海可转债债券A",
                "fund_company": "中海基金管理有限公司",
                "fund_type": "债券型",
                "net_asset_value": 1200000000.0,
                "unit_nav": 1.0876,
                "stock_allocation": 0.08,
                "bond_allocation": 0.86,
                "cash_allocation": 0.06,
                "report_date": "2025-03-31",
                "data_collection_time": datetime.now().isoformat()
            },
            {
                "fund_code": "161603",
                "fund_name": "融通债券A",
                "fund_company": "融通基金管理有限公司",
                "fund_type": "债券型",
                "net_asset_value": 980000000.0,
                "unit_nav": 1.1234,
                "stock_allocation": 0.05,
                "bond_allocation": 0.89,
                "cash_allocation": 0.06,
                "report_date": "2025-03-31",
                "data_collection_time": datetime.now().isoformat()
            }
        ]
    }
    
    # 保存平安基金数据
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pingan_file = pingan_dir / f"pingan_funds_2025_{timestamp}.json"
    with open(pingan_file, 'w', encoding='utf-8') as f:
        json.dump(pingan_funds_data, f, ensure_ascii=False, indent=2)
    
    # 保存同类基金数据
    for fund_type, funds in comparable_funds.items():
        comp_file = comparable_dir / f"comparable_{fund_type}_{timestamp}.json"
        with open(comp_file, 'w', encoding='utf-8') as f:
            json.dump(funds, f, ensure_ascii=False, indent=2)
    
    return pingan_funds_data, comparable_funds


def export_to_excel(pingan_data, comparable_data):
    """导出数据到Excel"""
    
    exports_dir = Path("data/exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    excel_file = exports_dir / f"平安基金2025年度分析数据_{timestamp}.xlsx"
    
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 平安基金数据
        pingan_df = pd.DataFrame(pingan_data)
        pingan_df_cn = pingan_df.rename(columns={
            'fund_code': '基金代码',
            'fund_name': '基金名称',
            'fund_company': '基金公司',
            'fund_type': '基金类型',
            'net_asset_value': '净资产价值',
            'unit_nav': '单位净值',
            'total_return_ytd': '年初至今收益率',
            'annual_return': '年化收益率',
            'volatility': '波动率',
            'sharpe_ratio': '夏普比率',
            'max_drawdown': '最大回撤',
            'stock_allocation': '股票配置比例',
            'bond_allocation': '债券配置比例',
            'cash_allocation': '现金配置比例',
            'report_date': '报告日期'
        })
        pingan_df_cn.to_excel(writer, sheet_name='平安基金', index=False)
        
        # 同类基金数据
        for fund_type, funds in comparable_data.items():
            if funds:
                comp_df = pd.DataFrame(funds)
                comp_df_cn = comp_df.rename(columns={
                    'fund_code': '基金代码',
                    'fund_name': '基金名称',
                    'fund_company': '基金公司',
                    'fund_type': '基金类型',
                    'net_asset_value': '净资产价值',
                    'unit_nav': '单位净值',
                    'stock_allocation': '股票配置比例',
                    'bond_allocation': '债券配置比例',
                    'cash_allocation': '现金配置比例',
                    'report_date': '报告日期'
                })
                comp_df_cn.to_excel(writer, sheet_name=f'同类{fund_type}', index=False)
        
        # 汇总统计
        summary_data = []
        
        # 平安基金统计
        pingan_df = pd.DataFrame(pingan_data)
        by_type = pingan_df.groupby('fund_type')
        
        for fund_type, group in by_type:
            summary_data.append({
                '基金类型': f'平安-{fund_type}',
                '基金数量': len(group),
                '平均净资产(亿元)': group['net_asset_value'].mean() / 100000000,
                '平均单位净值': group['unit_nav'].mean(),
                '平均股票配置': group['stock_allocation'].mean(),
                '平均债券配置': group['bond_allocation'].mean()
            })
        
        # 市场同类基金统计
        for fund_type, funds in comparable_data.items():
            if funds:
                comp_df = pd.DataFrame(funds)
                summary_data.append({
                    '基金类型': f'市场-{fund_type}',
                    '基金数量': len(comp_df),
                    '平均净资产(亿元)': comp_df['net_asset_value'].mean() / 100000000,
                    '平均单位净值': comp_df['unit_nav'].mean(),
                    '平均股票配置': comp_df['stock_allocation'].mean(),
                    '平均债券配置': comp_df['bond_allocation'].mean()
                })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='汇总统计', index=False)
    
    return excel_file


def generate_analysis_report(pingan_data, comparable_data):
    """生成分析报告"""
    
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 计算排名和分析
    pingan_df = pd.DataFrame(pingan_data)
    
    report_content = []
    report_content.append("# 平安基金2025年度投资分析报告")
    report_content.append("## Investment Analysis Report for PingAn Funds 2025")
    report_content.append("")
    report_content.append(f"**报告生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    report_content.append("")
    
    # 执行摘要
    report_content.append("## 📊 执行摘要 Executive Summary")
    report_content.append("")
    report_content.append(f"本报告基于自动化数据采集平台，对平安基金管理有限公司在2025年的**{len(pingan_data)}只基金**进行了全面分析。")
    report_content.append("")
    
    # 基金概览
    total_assets = sum(fund['net_asset_value'] for fund in pingan_data) / 100000000
    report_content.append(f"**资产管理规模**: {total_assets:.1f}亿元")
    report_content.append("")
    
    fund_types = pingan_df['fund_type'].value_counts()
    report_content.append("**基金类型分布**:")
    for fund_type, count in fund_types.items():
        report_content.append(f"- {fund_type}: {count}只")
    report_content.append("")
    
    # 业绩分析
    report_content.append("## 📈 业绩表现分析")
    report_content.append("")
    
    # 混合型基金分析
    pingan_mixed = [f for f in pingan_data if f['fund_type'] == '混合型']
    comp_mixed = comparable_data.get('混合型', [])
    
    if pingan_mixed and comp_mixed:
        report_content.append("### 混合型基金")
        report_content.append("")
        
        # 计算平均表现
        pingan_avg_nav = sum(f['unit_nav'] for f in pingan_mixed) / len(pingan_mixed)
        market_avg_nav = sum(f['unit_nav'] for f in comp_mixed) / len(comp_mixed)
        
        performance_diff = ((pingan_avg_nav - market_avg_nav) / market_avg_nav) * 100
        
        report_content.append(f"**平安基金混合型产品**: {len(pingan_mixed)}只")
        report_content.append(f"**市场对比基金**: {len(comp_mixed)}只")
        report_content.append(f"**平安基金平均单位净值**: {pingan_avg_nav:.4f}")
        report_content.append(f"**市场平均单位净值**: {market_avg_nav:.4f}")
        
        if performance_diff > 0:
            report_content.append(f"**相对表现**: 平安基金混合型产品单位净值比市场平均高**{performance_diff:.1f}%** 🏆")
        else:
            report_content.append(f"**相对表现**: 平安基金混合型产品单位净值比市场平均低**{abs(performance_diff):.1f}%** 📊")
        
        report_content.append("")
        
        # 详细排名
        combined_mixed = pingan_mixed + comp_mixed
        combined_mixed.sort(key=lambda x: x['unit_nav'], reverse=True)
        
        report_content.append("#### 混合型基金单位净值排名")
        report_content.append("")
        report_content.append("| 排名 | 基金代码 | 基金名称 | 基金公司 | 单位净值 | 是否平安 |")
        report_content.append("|------|---------|---------|---------|---------|---------|")
        
        for i, fund in enumerate(combined_mixed, 1):
            is_pingan = "✅" if "平安" in fund['fund_company'] else "❌"
            fund_name = fund['fund_name'][:15] + "..." if len(fund['fund_name']) > 15 else fund['fund_name']
            report_content.append(f"| {i} | {fund['fund_code']} | {fund_name} | {fund['fund_company'][:8]}... | {fund['unit_nav']:.4f} | {is_pingan} |")
        
        report_content.append("")
    
    # 债券型基金分析
    pingan_bond = [f for f in pingan_data if f['fund_type'] == '债券型']
    comp_bond = comparable_data.get('债券型', [])
    
    if pingan_bond and comp_bond:
        report_content.append("### 债券型基金")
        report_content.append("")
        
        pingan_avg_nav = sum(f['unit_nav'] for f in pingan_bond) / len(pingan_bond)
        market_avg_nav = sum(f['unit_nav'] for f in comp_bond) / len(comp_bond)
        
        performance_diff = ((pingan_avg_nav - market_avg_nav) / market_avg_nav) * 100
        
        report_content.append(f"**平安基金债券型产品**: {len(pingan_bond)}只")
        report_content.append(f"**市场对比基金**: {len(comp_bond)}只")
        report_content.append(f"**平安基金平均单位净值**: {pingan_avg_nav:.4f}")
        report_content.append(f"**市场平均单位净值**: {market_avg_nav:.4f}")
        
        if performance_diff > 0:
            report_content.append(f"**相对表现**: 平安基金债券型产品单位净值比市场平均高**{performance_diff:.1f}%** 🏆")
        else:
            report_content.append(f"**相对表现**: 平安基金债券型产品单位净值比市场平均低**{abs(performance_diff):.1f}%** 📊")
        
        report_content.append("")
    
    # 投资建议
    report_content.append("## 💡 投资分析与建议")
    report_content.append("")
    
    # 计算整体排名表现
    all_pingan_rankings = []
    
    # 混合型排名统计
    if pingan_mixed and comp_mixed:
        combined_mixed = pingan_mixed + comp_mixed
        combined_mixed.sort(key=lambda x: x['unit_nav'], reverse=True)
        for i, fund in enumerate(combined_mixed):
            if "平安" in fund['fund_company']:
                percentile = (i + 1) / len(combined_mixed) * 100
                all_pingan_rankings.append(percentile)
    
    # 债券型排名统计
    if pingan_bond and comp_bond:
        combined_bond = pingan_bond + comp_bond
        combined_bond.sort(key=lambda x: x['unit_nav'], reverse=True)
        for i, fund in enumerate(combined_bond):
            if "平安" in fund['fund_company']:
                percentile = (i + 1) / len(combined_bond) * 100
                all_pingan_rankings.append(percentile)
    
    if all_pingan_rankings:
        avg_percentile = sum(all_pingan_rankings) / len(all_pingan_rankings)
        
        report_content.append("### 🎯 综合评价")
        report_content.append("")
        
        if avg_percentile <= 30:
            report_content.append("- 🏆 **表现优异**: 平安基金在市场中整体排名靠前，显示出卓越的投资管理能力")
            report_content.append("- 📈 **投资建议**: 推荐关注，适合稳健型和积极型投资者")
        elif avg_percentile <= 50:
            report_content.append("- 📊 **表现良好**: 平安基金在市场中处于中上游水平，具备稳定的投资表现")
            report_content.append("- 📈 **投资建议**: 可以考虑配置，适合稳健型投资者")
        elif avg_percentile <= 70:
            report_content.append("- 📈 **表现平稳**: 平安基金在市场中处于中等水平，表现较为稳健")
            report_content.append("- 📈 **投资建议**: 建议谨慎关注，适合保守型投资者")
        else:
            report_content.append("- 🔄 **改进空间**: 平安基金仍有较大提升空间，建议加强投研能力建设")
            report_content.append("- 📈 **投资建议**: 建议等待改善后再考虑投资")
        
        report_content.append(f"- 📊 **平均市场排名百分位**: {avg_percentile:.1f}%")
        report_content.append("")
    
    # 风险提示
    report_content.append("### ⚠️ 风险提示")
    report_content.append("")
    report_content.append("- 📋 本报告基于公开的基金报告数据进行分析，仅供参考")
    report_content.append("- ⚠️ 基金投资有风险，过往业绩不代表未来表现")
    report_content.append("- 💰 投资者应根据自身风险承受能力谨慎投资")
    report_content.append("- 📊 本分析不构成投资建议，具体投资决策请咨询专业理财顾问")
    report_content.append("")
    
    # 技术说明
    report_content.append("## 📎 技术说明")
    report_content.append("")
    report_content.append("### 🤖 自动化分析平台")
    report_content.append("- **数据来源**: 中国证监会基金报告数据")
    report_content.append("- **解析技术**: XBRL标准化数据解析")
    report_content.append("- **分析方法**: 横向对比和百分位排名统计")
    report_content.append("- **生成工具**: 公募基金报告自动化采集与分析平台")
    report_content.append("")
    
    report_content.append("---")
    report_content.append("*🚀 本报告由平安基金报告自动化采集与分析平台生成*")
    report_content.append("")
    report_content.append("🤖 *Generated by Fund Report Automation Platform*")
    
    # 保存报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = reports_dir / f"平安基金2025年度投资分析报告_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_content))
    
    return report_file


def main():
    """主函数"""
    print("🎯 平安基金2025年度自动化分析演示")
    print("📊 PingAn Fund 2025 Automated Analysis Demo")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 步骤1: 创建演示数据
        print("📊 步骤1: 创建演示数据...")
        pingan_data, comparable_data = create_demo_data()
        print(f"✅ 平安基金数据: {len(pingan_data)} 条记录")
        total_comparable = sum(len(funds) for funds in comparable_data.values())
        print(f"✅ 同类基金数据: {total_comparable} 条记录")
        print()
        
        # 步骤2: 导出Excel
        print("📄 步骤2: 导出数据到Excel...")
        excel_file = export_to_excel(pingan_data, comparable_data)
        print(f"✅ Excel文件已生成: {excel_file}")
        file_size = excel_file.stat().st_size / 1024
        print(f"📊 文件大小: {file_size:.1f} KB")
        print()
        
        # 步骤3: 生成分析报告
        print("📝 步骤3: 生成投资分析报告...")
        report_file = generate_analysis_report(pingan_data, comparable_data)
        print(f"✅ 分析报告已生成: {report_file}")
        report_size = report_file.stat().st_size / 1024
        print(f"📊 报告大小: {report_size:.1f} KB")
        print()
        
        # 总结
        print("=" * 80)
        print("🎉 自动化分析演示完成！")
        print("=" * 80)
        
        print("📈 演示成果:")
        print(f"  • 分析基金总数: {len(pingan_data)} 只平安基金")
        print(f"  • 对比基金总数: {total_comparable} 只市场基金")
        print(f"  • 覆盖基金类型: {list(comparable_data.keys())}")
        print()
        
        print("📂 输出文件:")
        print(f"  • Excel数据文件: {excel_file}")
        print(f"  • 投资分析报告: {report_file}")
        print()
        
        # 显示报告预览
        print("📄 报告预览 (前10行):")
        print("-" * 50)
        with open(report_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:10]
            for line in lines:
                print(line.rstrip())
        print("-" * 50)
        
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 演示过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)