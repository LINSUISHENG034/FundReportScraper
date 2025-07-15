"""
测试新的XBRL解析器系统
Test script for the new XBRL parser system
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.parsers.parser_facade import XBRLParserFacade
from src.utils.model_utils import orm_to_dict
import json


def test_new_parser():
    """测试新的解析器系统"""
    print("=== 测试新的XBRL解析器系统 ===\n")
    
    # 初始化解析器门面
    try:
        parser_facade = XBRLParserFacade(enable_ai_enhancement=True)
        print(f"✓ 解析器门面初始化成功")
        print(f"可用解析器: {[p.value for p in parser_facade.get_available_parsers()]}\n")
    except Exception as e:
        print(f"✗ 解析器门面初始化失败: {e}")
        return
    
    # 测试文件目录
    fixtures_dir = project_root / "tests" / "fixtures"
    if not fixtures_dir.exists():
        print(f"✗ 测试文件目录不存在: {fixtures_dir}")
        return
    
    # 获取测试文件
    xbrl_files = list(fixtures_dir.glob("*.xbrl"))
    if not xbrl_files:
        print(f"✗ 未找到测试文件")
        return
    
    print(f"找到 {len(xbrl_files)} 个测试文件\n")
    
    # 测试前几个文件
    test_files = xbrl_files[:3]  # 只测试前3个文件
    
    results = []
    
    for file_path in test_files:
        print(f">>> 测试文件: {file_path.name}")
        
        try:
            # 使用新的解析器系统
            parse_result = parser_facade.parse_file(file_path)
            
            if parse_result.success:
                print(f"✓ 解析成功 (解析器: {parse_result.parser_type.value})")
                
                # 转换为字典以便显示
                if parse_result.fund_report:
                    report_dict = orm_to_dict(parse_result.fund_report)
                    
                    # 显示关键信息
                    summary = {
                        "fund_code": report_dict.get("fund_code"),
                        "fund_name": report_dict.get("fund_name"),
                        "net_asset_value": report_dict.get("net_asset_value"),
                        "total_net_assets": report_dict.get("total_net_assets"),
                        "asset_allocations_count": len(report_dict.get("asset_allocations", [])),
                        "top_holdings_count": len(report_dict.get("top_holdings", [])),
                        "industry_allocations_count": len(report_dict.get("industry_allocations", [])),
                        "completeness_score": parse_result.metadata.get("completeness_score", 0),
                        "processing_time": f"{parse_result.metadata.get('processing_time', 0):.3f}s"
                    }
                    
                    print(json.dumps(summary, indent=2, ensure_ascii=False))
                    results.append({"file": file_path.name, "status": "成功", "data": summary})
                else:
                    print("✗ 解析结果为空")
                    results.append({"file": file_path.name, "status": "失败", "data": None})
            else:
                print(f"✗ 解析失败: {', '.join(parse_result.errors)}")
                results.append({"file": file_path.name, "status": "失败", "errors": parse_result.errors})
            
            # 显示警告
            if parse_result.warnings:
                print(f"⚠ 警告: {', '.join(parse_result.warnings)}")
            
        except Exception as e:
            print(f"✗ 解析异常: {e}")
            results.append({"file": file_path.name, "status": "异常", "error": str(e)})
        
        print()
    
    # 显示总体统计
    print("=== 测试结果统计 ===")
    successful = sum(1 for r in results if r["status"] == "成功")
    failed = len(results) - successful
    
    print(f"总文件数: {len(results)}")
    print(f"成功: {successful}")
    print(f"失败: {failed}")
    print(f"成功率: {successful/len(results)*100:.1f}%")
    
    # 显示性能指标
    metrics = parser_facade.get_parsing_metrics()
    print(f"\n=== 性能指标 ===")
    print(f"总处理文件数: {metrics.total_files_processed}")
    print(f"成功解析数: {metrics.successful_parses}")
    print(f"失败解析数: {metrics.failed_parses}")
    print(f"成功率: {metrics.success_rate*100:.1f}%")
    print(f"平均处理时间: {metrics.average_processing_time:.3f}s")
    print(f"格式分布: {metrics.format_distribution}")
    print(f"解析器使用: {metrics.parser_usage}")


if __name__ == "__main__":
    test_new_parser()