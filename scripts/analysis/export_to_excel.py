#!/usr/bin/env python3
"""
数据导出Excel脚本
Data export to Excel script
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
from dataclasses import asdict

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import get_logger
from scripts.analysis.collect_pingan_2025_data import FundAnalysisData

logger = get_logger(__name__)


class DataExporter:
    """数据导出器"""
    
    def __init__(self):
        """初始化导出器"""
        self.data_dir = Path("data/analysis")
        self.output_dir = Path("data/exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("data_exporter.initialized")
    
    def load_json_data(self, file_path: str) -> List[Dict[str, Any]]:
        """加载JSON数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("json_data_loaded", file_path=file_path, record_count=len(data))
            return data
        except Exception as e:
            logger.error("json_load_error", file_path=file_path, error=str(e))
            return []
    
    def convert_to_dataframe(self, fund_data_list: List[Dict[str, Any]]) -> pd.DataFrame:
        """将基金数据转换为DataFrame"""
        try:
            # 展开嵌套字段
            flattened_data = []
            
            for fund_data in fund_data_list:
                flat_data = fund_data.copy()
                
                # 处理top_holdings字段
                if 'top_holdings' in flat_data and flat_data['top_holdings']:
                    # 提取前5大持仓
                    for i, holding in enumerate(flat_data['top_holdings'][:5]):
                        flat_data[f'top_holding_{i+1}_name'] = holding.get('stock_name', '')
                        flat_data[f'top_holding_{i+1}_ratio'] = holding.get('allocation_ratio', 0)
                
                # 处理industry_allocation字段
                if 'industry_allocation' in flat_data and flat_data['industry_allocation']:
                    # 提取前3大行业配置
                    sorted_industries = sorted(
                        flat_data['industry_allocation'].items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:3]
                    
                    for i, (industry, ratio) in enumerate(sorted_industries):
                        flat_data[f'top_industry_{i+1}_name'] = industry
                        flat_data[f'top_industry_{i+1}_ratio'] = ratio
                
                # 移除原始嵌套字段
                flat_data.pop('top_holdings', None)
                flat_data.pop('industry_allocation', None)
                
                flattened_data.append(flat_data)
            
            df = pd.DataFrame(flattened_data)
            
            # 数据类型转换和清理
            numeric_columns = [
                'net_asset_value', 'unit_nav', 'total_return_ytd', 'annual_return',
                'volatility', 'sharpe_ratio', 'max_drawdown', 'stock_allocation',
                'bond_allocation', 'cash_allocation'
            ]
            
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 日期列转换
            date_columns = ['establishment_date', 'report_date', 'data_collection_time']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            logger.info("dataframe_converted", row_count=len(df), column_count=len(df.columns))
            return df
            
        except Exception as e:
            logger.error("dataframe_conversion_error", error=str(e))
            return pd.DataFrame()
    
    def create_summary_statistics(self, dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """创建汇总统计表"""
        summary_data = []
        
        for fund_type, df in dfs.items():
            if df.empty:
                continue
                
            # 计算统计指标
            stats = {
                'fund_type': fund_type,
                'fund_count': len(df),
                'avg_net_asset_value': df['net_asset_value'].mean() if 'net_asset_value' in df.columns else None,
                'avg_unit_nav': df['unit_nav'].mean() if 'unit_nav' in df.columns else None,
                'avg_stock_allocation': df['stock_allocation'].mean() if 'stock_allocation' in df.columns else None,
                'avg_bond_allocation': df['bond_allocation'].mean() if 'bond_allocation' in df.columns else None,
                'avg_cash_allocation': df['cash_allocation'].mean() if 'cash_allocation' in df.columns else None,
                'max_net_asset_value': df['net_asset_value'].max() if 'net_asset_value' in df.columns else None,
                'min_net_asset_value': df['net_asset_value'].min() if 'net_asset_value' in df.columns else None,
            }
            
            summary_data.append(stats)
        
        return pd.DataFrame(summary_data)
    
    def export_to_excel(self, file_name: str) -> bool:
        """导出所有数据到Excel文件"""
        try:
            output_file = self.output_dir / file_name
            
            # 查找最新的数据文件
            pingan_files = list(self.data_dir.glob("pingan_2025/pingan_funds_2025_*.json"))
            comparable_files = list(self.data_dir.glob("comparable_2025/comparable_*.json"))
            
            if not pingan_files:
                logger.warning("no_pingan_data_files_found")
                return False
            
            # 使用最新的平安基金数据文件
            latest_pingan_file = max(pingan_files, key=lambda f: f.stat().st_mtime)
            pingan_data = self.load_json_data(str(latest_pingan_file))
            
            # 加载同类基金数据
            all_comparable_data = {}
            for comp_file in comparable_files:
                file_name_parts = comp_file.stem.split('_')
                if len(file_name_parts) >= 3:
                    fund_type = file_name_parts[1]
                    comp_data = self.load_json_data(str(comp_file))
                    if comp_data:
                        all_comparable_data[fund_type] = comp_data
            
            # 转换为DataFrame
            dataframes = {}
            
            # 平安基金数据
            if pingan_data:
                dataframes['平安基金'] = self.convert_to_dataframe(pingan_data)
            
            # 同类基金数据
            for fund_type, comp_data in all_comparable_data.items():
                dataframes[f'同类{fund_type}'] = self.convert_to_dataframe(comp_data)
            
            # 创建汇总统计
            summary_df = self.create_summary_statistics(dataframes)
            
            # 写入Excel文件
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 写入汇总统计
                if not summary_df.empty:
                    summary_df.to_excel(writer, sheet_name='汇总统计', index=False)
                
                # 写入各类型数据
                for sheet_name, df in dataframes.items():
                    if not df.empty:
                        # 调整列名为中文
                        df_chinese = df.copy()
                        column_mapping = {
                            'fund_code': '基金代码',
                            'fund_name': '基金名称',
                            'fund_company': '基金公司',
                            'fund_type': '基金类型',
                            'establishment_date': '成立日期',
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
                            'report_date': '报告日期',
                            'data_collection_time': '数据收集时间'
                        }
                        
                        # 重命名存在的列
                        for en_col, cn_col in column_mapping.items():
                            if en_col in df_chinese.columns:
                                df_chinese = df_chinese.rename(columns={en_col: cn_col})
                        
                        df_chinese.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"✅ 数据已导出至: {output_file}")
            logger.info("excel_export_successful", file_path=str(output_file))
            
            # 输出文件信息
            file_size = output_file.stat().st_size / 1024 / 1024  # MB
            print(f"📊 文件大小: {file_size:.2f} MB")
            print(f"📋 工作表数量: {len(dataframes) + 1}")  # +1 for summary
            
            return True
            
        except Exception as e:
            logger.error("excel_export_error", error=str(e))
            print(f"❌ Excel导出失败: {e}")
            return False


def main():
    """主函数"""
    print("🚀 数据导出Excel")
    print("=" * 60)
    
    exporter = DataExporter()
    
    # 生成导出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    excel_filename = f"平安基金2025年度分析数据_{timestamp}.xlsx"
    
    try:
        success = exporter.export_to_excel(excel_filename)
        
        if success:
            print("\n🎉 数据导出完成！")
            print(f"📂 输出目录: {exporter.output_dir}")
            print(f"📄 文件名称: {excel_filename}")
        else:
            print("\n❌ 数据导出失败")
            
        return success
        
    except Exception as e:
        print(f"\n❌ 导出过程发生错误: {e}")
        logger.error("main_export_error", error=str(e))
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)