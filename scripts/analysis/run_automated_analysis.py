#!/usr/bin/env python3
"""
平安基金2025年自动化分析主控脚本
Main automation script for PingAn Fund 2025 analysis
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import get_logger

logger = get_logger(__name__)


class AutomatedAnalysisController:
    """自动化分析控制器"""
    
    def __init__(self):
        """初始化控制器"""
        self.scripts_dir = Path(__file__).parent
        self.project_root = project_root
        
        logger.info("automated_analysis_controller.initialized")
    
    async def run_script(self, script_name: str, description: str) -> bool:
        """运行指定脚本"""
        script_path = self.scripts_dir / script_name
        
        if not script_path.exists():
            logger.error("script_not_found", script_path=str(script_path))
            print(f"❌ 脚本不存在: {script_path}")
            return False
        
        print(f"\n🚀 {description}")
        print("=" * 60)
        
        try:
            # 运行Python脚本
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            
            # 输出脚本执行结果
            if result.stdout:
                print(result.stdout)
            
            if result.stderr:
                print("⚠️ 错误输出:")
                print(result.stderr)
            
            if result.returncode == 0:
                logger.info("script_executed_successfully", script_name=script_name)
                print(f"✅ {description} - 完成")
                return True
            else:
                logger.error("script_execution_failed", script_name=script_name, return_code=result.returncode)
                print(f"❌ {description} - 失败 (退出码: {result.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("script_timeout", script_name=script_name)
            print(f"⏰ {description} - 超时")
            return False
        except Exception as e:
            logger.error("script_execution_error", script_name=script_name, error=str(e))
            print(f"❌ {description} - 执行错误: {e}")
            return False
    
    async def run_full_analysis_pipeline(self) -> bool:
        """运行完整的分析管道"""
        print("🎯 平安基金2025年度自动化分析管道")
        print("📊 Fund Analysis Automation Pipeline")
        print("=" * 80)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 定义分析步骤
        analysis_steps = [
            {
                "script": "collect_pingan_2025_data.py",
                "description": "收集平安基金2025年数据",
                "required": True
            },
            {
                "script": "collect_comparable_funds.py", 
                "description": "收集同类型基金对比数据",
                "required": True
            },
            {
                "script": "export_to_excel.py",
                "description": "导出数据到Excel文件",
                "required": False
            },
            {
                "script": "generate_analysis_report.py",
                "description": "生成投资分析报告",
                "required": True
            }
        ]
        
        success_count = 0
        total_steps = len(analysis_steps)
        
        for i, step in enumerate(analysis_steps, 1):
            step_description = f"步骤 {i}/{total_steps}: {step['description']}"
            
            success = await self.run_script(step["script"], step_description)
            
            if success:
                success_count += 1
            elif step["required"]:
                print(f"\n❌ 必需步骤失败，终止分析管道")
                logger.error("required_step_failed", step=step["script"])
                return False
        
        # 分析结果总结
        print(f"\n" + "=" * 80)
        print("🎉 自动化分析管道执行完成")
        print("=" * 80)
        
        print(f"📊 执行统计:")
        print(f"  • 总步骤数: {total_steps}")
        print(f"  • 成功步骤: {success_count}")
        print(f"  • 成功率: {success_count/total_steps*100:.1f}%")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if success_count == total_steps:
            print("\n✅ 所有分析步骤执行成功！")
            print("\n📂 输出文件位置:")
            
            # 检查输出文件
            data_dir = self.project_root / "data"
            if data_dir.exists():
                print(f"  • 数据文件: {data_dir}/analysis/")
                
                exports_dir = data_dir / "exports"
                if exports_dir.exists():
                    excel_files = list(exports_dir.glob("*.xlsx"))
                    if excel_files:
                        latest_excel = max(excel_files, key=lambda f: f.stat().st_mtime)
                        print(f"  • Excel文件: {latest_excel}")
            
            reports_dir = self.project_root / "reports"
            if reports_dir.exists():
                report_files = list(reports_dir.glob("*.md"))
                if report_files:
                    latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
                    print(f"  • 分析报告: {latest_report}")
            
            return True
        else:
            print(f"\n⚠️ 部分步骤执行失败，请检查错误日志")
            return False
    
    def create_directory_structure(self):
        """创建必要的目录结构"""
        directories = [
            "data/analysis/pingan_2025",
            "data/analysis/comparable_2025", 
            "data/exports",
            "reports"
        ]
        
        for dir_path in directories:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            logger.debug("directory_created", path=str(full_path))


async def main():
    """主函数"""
    controller = AutomatedAnalysisController()
    
    try:
        # 创建目录结构
        controller.create_directory_structure()
        
        # 运行完整分析管道
        success = await controller.run_full_analysis_pipeline()
        
        return success
        
    except Exception as e:
        print(f"\n❌ 自动化分析控制器发生错误: {e}")
        logger.error("controller_error", error=str(e))
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)