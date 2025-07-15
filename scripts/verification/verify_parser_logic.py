"""
脚本：直接验证和调试 XBRLParser 的逻辑

本脚本旨在提供一个快速的反馈循环，用于测试和优化 XBRLParser 的解析能力。
它会遍历 `tests/fixtures` 目录下的所有 XBRL 文件，使用解析器处理它们，
并以人类可读的格式打印出提取的数据。

这避免了每次为了测试解析效果而运行完整的端到端下载流程。
"""
import json
from pathlib import Path
import sys

# 将 src 目录添加到 Python 路径中，以便导入模块
# 这是一种在项目脚本中常见的做法
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.parsers.xbrl_parser import XBRLParser
from src.utils.model_utils import orm_to_dict

def main():
    """主执行函数"""
    fixtures_dir = project_root / "tests" / "fixtures"
    xbrl_files = list(fixtures_dir.glob("*.xbrl"))

    if not xbrl_files:
        print(f"错误：在 '{fixtures_dir}' 目录中未找到任何 .xbrl 文件。")
        return

    print(f"--- 开始对 {len(xbrl_files)} 个样本文件进行解析验证 ---")

    parser = XBRLParser()
    all_results = []

    for file_path in xbrl_files:
        print(f"\n>>> 正在解析文件: {file_path.name}")
        
        report_obj = parser.parse_file(file_path)
        
        if report_obj:
            # 使用 orm_to_dict 将 SQLAlchemy 对象转换为可序列化的字典
            report_dict = orm_to_dict(report_obj)
            
            # 为了更清晰的输出，我们只显示部分关键字段和表格数据的计数
            summary = {
                "fund_code": report_dict.get("fund_code"),
                "fund_name": report_dict.get("fund_name"),
                "net_asset_value": report_dict.get("net_asset_value"),
                "total_net_assets": report_dict.get("total_net_assets"),
                "asset_allocations_count": len(report_dict.get("asset_allocations", [])),
                "top_holdings_count": len(report_dict.get("top_holdings", [])),
                "industry_allocations_count": len(report_dict.get("industry_allocations", [])),
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            all_results.append({"file": file_path.name, "status": "成功", "data": summary})
        else:
            print("    解析失败，返回 None。")
            all_results.append({"file": file_path.name, "status": "失败", "data": None})

    print("\n--- 解析验证完成 ---")
    successful_count = sum(1 for r in all_results if r["status"] == "成功")
    failed_count = len(all_results) - successful_count
    print(f"结果: {successful_count} 个文件成功, {failed_count} 个文件失败。")


if __name__ == "__main__":
    main()
