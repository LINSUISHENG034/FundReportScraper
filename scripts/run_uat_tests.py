#!/usr/bin/env python3
"""
UAT测试自动化脚本
User Acceptance Testing Automation Script

执行用户验收测试的自动化验证
"""

import os
import sys
import json
import time
import asyncio
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import structlog

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings

class Color:
    """颜色常量"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class UATTester:
    """用户验收测试器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.settings = get_settings()
        self.api_base_url = f"http://localhost:{self.settings.API_PORT}"
        self.test_results = []
        self.start_time = None
        
        # 设置结构化日志
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        self.logger = structlog.get_logger("uat_tester")
        
    def log(self, level: str, message: str, **kwargs):
        """记录日志"""
        colors = {
            'INFO': Color.BLUE,
            'SUCCESS': Color.GREEN,
            'WARNING': Color.YELLOW,
            'ERROR': Color.RED,
            'TITLE': Color.PURPLE
        }
        color = colors.get(level, Color.NC)
        print(f"{color}[{level}]{Color.NC} {message}")
        
        # 同时记录到结构化日志
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, **kwargs)
    
    def add_test_result(self, test_case: str, status: bool, message: str = "", 
                       execution_time: float = 0.0, details: Dict = None):
        """添加测试结果"""
        self.test_results.append({
            'test_case': test_case,
            'status': status,
            'message': message,
            'execution_time': execution_time,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def check_system_health(self) -> bool:
        """检查系统健康状态"""
        self.log('INFO', "检查系统健康状态...")
        
        try:
            # 检查API健康检查端点
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                self.log('SUCCESS', f"API健康检查通过: {health_data}")
                return True
            else:
                self.log('ERROR', f"API健康检查失败: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            self.log('ERROR', f"无法连接到API服务: {str(e)}")
            return False
    
    def check_docker_services(self) -> bool:
        """检查Docker服务状态"""
        self.log('INFO', "检查Docker服务状态...")
        
        try:
            result = subprocess.run(
                ['docker-compose', '-f', 'docker-compose.prod.yml', 'ps'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                services_output = result.stdout
                self.log('INFO', f"Docker服务状态:\n{services_output}")
                
                # 检查关键服务是否运行
                required_services = ['postgres', 'redis', 'minio', 'api', 'celery_worker']
                running_services = 0
                
                for service in required_services:
                    if f"{service}" in services_output and "Up" in services_output:
                        running_services += 1
                        self.log('SUCCESS', f"✓ {service} 服务运行正常")
                    else:
                        self.log('ERROR', f"✗ {service} 服务未运行")
                
                return running_services >= len(required_services) * 0.8  # 至少80%的服务运行
            else:
                self.log('ERROR', f"Docker服务检查失败: {result.stderr}")
                return False
                
        except Exception as e:
            self.log('ERROR', f"Docker服务检查异常: {str(e)}")
            return False
    
    def test_api_endpoints(self) -> Dict[str, bool]:
        """测试API端点功能"""
        self.log('INFO', "测试API端点功能...")
        
        test_results = {}
        
        # 测试用例定义
        api_tests = [
            {
                'name': 'health_check',
                'method': 'GET',
                'url': '/health',
                'expected_status': 200
            },
            {
                'name': 'api_docs',
                'method': 'GET', 
                'url': '/docs',
                'expected_status': 200
            },
            {
                'name': 'funds_list',
                'method': 'GET',
                'url': '/api/v1/funds/',
                'expected_status': 200
            },
            {
                'name': 'fund_types',
                'method': 'GET',
                'url': '/api/v1/funds/types/list',
                'expected_status': 200
            },
            {
                'name': 'fund_companies',
                'method': 'GET',
                'url': '/api/v1/funds/companies/list', 
                'expected_status': 200
            },
            {
                'name': 'reports_list',
                'method': 'GET',
                'url': '/api/v1/reports/',
                'expected_status': 200
            },
            {
                'name': 'reports_stats',
                'method': 'GET',
                'url': '/api/v1/reports/stats/summary',
                'expected_status': 200
            },
            {
                'name': 'tasks_list',
                'method': 'GET',
                'url': '/api/v1/tasks/',
                'expected_status': 200
            },
            {
                'name': 'tasks_stats',
                'method': 'GET',
                'url': '/api/v1/tasks/stats/summary',
                'expected_status': 200
            }
        ]
        
        for test in api_tests:
            start_time = time.time()
            try:
                url = f"{self.api_base_url}{test['url']}"
                response = requests.request(test['method'], url, timeout=10)
                execution_time = time.time() - start_time
                
                success = response.status_code == test['expected_status']
                test_results[test['name']] = success
                
                if success:
                    self.log('SUCCESS', f"✓ {test['name']}: {response.status_code} ({execution_time:.2f}s)")
                    self.add_test_result(
                        f"API-{test['name']}", 
                        True, 
                        f"状态码: {response.status_code}",
                        execution_time,
                        {'url': test['url'], 'response_size': len(response.content)}
                    )
                else:
                    self.log('ERROR', f"✗ {test['name']}: {response.status_code} (期望: {test['expected_status']})")
                    self.add_test_result(
                        f"API-{test['name']}", 
                        False,
                        f"状态码错误: {response.status_code}",
                        execution_time
                    )
                    
            except requests.RequestException as e:
                execution_time = time.time() - start_time
                test_results[test['name']] = False
                self.log('ERROR', f"✗ {test['name']}: 请求失败 - {str(e)}")
                self.add_test_result(
                    f"API-{test['name']}", 
                    False, 
                    f"请求异常: {str(e)}",
                    execution_time
                )
        
        return test_results
    
    def test_task_creation(self) -> bool:
        """测试任务创建功能"""
        self.log('INFO', "测试任务创建功能...")
        
        try:
            # 创建测试任务
            task_data = {
                "task_type": "collect_reports",
                "target_fund_codes": ["000001", "000300"],
                "date_range": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                "priority": "high",
                "description": "UAT测试任务"
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_base_url}/api/v1/tasks/",
                json=task_data,
                timeout=10
            )
            execution_time = time.time() - start_time
            
            if response.status_code == 200:
                task_info = response.json()
                task_id = task_info.get('data', {}).get('task_id')
                
                if task_id:
                    self.log('SUCCESS', f"✓ 任务创建成功: {task_id}")
                    
                    # 查询任务状态
                    time.sleep(2)  # 等待任务开始执行
                    status_response = requests.get(
                        f"{self.api_base_url}/api/v1/tasks/{task_id}",
                        timeout=10
                    )
                    
                    if status_response.status_code == 200:
                        status_info = status_response.json()
                        self.log('INFO', f"任务状态: {status_info.get('data', {}).get('status')}")
                        
                        self.add_test_result(
                            "TASK-creation", 
                            True,
                            f"任务创建并查询成功: {task_id}",
                            execution_time,
                            {'task_id': task_id, 'status': status_info.get('data', {})}
                        )
                        return True
                    else:
                        self.log('WARNING', "任务创建成功但状态查询失败")
                        return True
                else:
                    self.log('ERROR', "任务创建响应中缺少task_id")
                    return False
            else:
                self.log('ERROR', f"任务创建失败: {response.status_code}")
                self.add_test_result(
                    "TASK-creation", 
                    False,
                    f"任务创建失败: {response.status_code}",
                    execution_time
                )
                return False
                
        except requests.RequestException as e:
            self.log('ERROR', f"任务创建请求异常: {str(e)}")
            self.add_test_result(
                "TASK-creation", 
                False,
                f"请求异常: {str(e)}"
            )
            return False
    
    def test_data_quality(self) -> Dict[str, bool]:
        """测试数据质量"""
        self.log('INFO', "测试数据质量...")
        
        quality_results = {}
        
        try:
            # 测试基金数据
            funds_response = requests.get(f"{self.api_base_url}/api/v1/funds/", timeout=10)
            if funds_response.status_code == 200:
                funds_data = funds_response.json()
                funds_list = funds_data.get('data', {}).get('items', [])
                
                if funds_list:
                    # 检查数据完整性
                    complete_records = 0
                    for fund in funds_list:
                        if all(fund.get(field) for field in ['fund_code', 'fund_name', 'fund_type']):
                            complete_records += 1
                    
                    completeness_rate = complete_records / len(funds_list)
                    quality_results['data_completeness'] = completeness_rate > 0.95
                    
                    self.log('INFO', f"基金数据完整性: {completeness_rate:.2%} ({complete_records}/{len(funds_list)})")
                    self.add_test_result(
                        "DATA-completeness",
                        quality_results['data_completeness'],
                        f"数据完整性: {completeness_rate:.2%}",
                        details={'total_records': len(funds_list), 'complete_records': complete_records}
                    )
                else:
                    quality_results['data_completeness'] = False
                    self.log('WARNING', "未找到基金数据")
            else:
                quality_results['data_completeness'] = False
                self.log('ERROR', f"基金数据查询失败: {funds_response.status_code}")
            
            # 测试报告数据
            reports_response = requests.get(f"{self.api_base_url}/api/v1/reports/", timeout=10)
            if reports_response.status_code == 200:
                reports_data = reports_response.json()
                reports_list = reports_data.get('data', {}).get('items', [])
                
                quality_results['reports_available'] = len(reports_list) > 0
                self.log('INFO', f"报告数据可用性: {len(reports_list)} 条记录")
                self.add_test_result(
                    "DATA-reports_availability",
                    quality_results['reports_available'],
                    f"报告数据: {len(reports_list)} 条记录"
                )
            else:
                quality_results['reports_available'] = False
                self.log('ERROR', f"报告数据查询失败: {reports_response.status_code}")
        
        except Exception as e:
            self.log('ERROR', f"数据质量测试异常: {str(e)}")
            quality_results['data_quality_error'] = False
        
        return quality_results
    
    def test_performance(self) -> Dict[str, bool]:
        """测试系统性能"""
        self.log('INFO', "测试系统性能...")
        
        performance_results = {}
        
        # 响应时间测试
        response_times = []
        for i in range(5):
            start_time = time.time()
            try:
                response = requests.get(f"{self.api_base_url}/api/v1/funds/", timeout=10)
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                if response.status_code == 200:
                    self.log('INFO', f"第{i+1}次请求响应时间: {response_time:.3f}s")
                else:
                    self.log('WARNING', f"第{i+1}次请求失败: {response.status_code}")
            except Exception as e:
                self.log('ERROR', f"第{i+1}次请求异常: {str(e)}")
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            performance_results['response_time'] = avg_response_time < 2.0  # 平均响应时间小于2秒
            performance_results['max_response_time'] = max_response_time < 5.0  # 最大响应时间小于5秒
            
            self.log('INFO', f"平均响应时间: {avg_response_time:.3f}s")
            self.log('INFO', f"最大响应时间: {max_response_time:.3f}s")
            
            self.add_test_result(
                "PERF-response_time",
                performance_results['response_time'],
                f"平均响应时间: {avg_response_time:.3f}s",
                avg_response_time,
                {'response_times': response_times}
            )
        else:
            performance_results['response_time'] = False
            performance_results['max_response_time'] = False
        
        return performance_results
    
    def generate_uat_report(self) -> str:
        """生成UAT测试报告"""
        self.log('INFO', "生成UAT测试报告...")
        
        # 计算测试统计
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 生成报告内容
        report_content = f"""# UAT测试执行报告
## User Acceptance Testing Report

**测试执行时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}  
**测试环境**: 准生产环境  
**测试版本**: 第五阶段 (W11)

---

## 📊 测试概览

- **总测试用例**: {total_tests}
- **通过用例**: {passed_tests}
- **失败用例**: {failed_tests}
- **成功率**: {success_rate:.1f}%

---

## 🎯 测试结果详情

### 测试用例执行结果

| 测试用例 | 状态 | 执行时间 | 说明 |
|---------|------|---------|------|
"""
        
        for result in self.test_results:
            status_icon = "✅" if result['status'] else "❌"
            execution_time = f"{result['execution_time']:.3f}s" if result['execution_time'] > 0 else "-"
            report_content += f"| {result['test_case']} | {status_icon} | {execution_time} | {result['message']} |\n"
        
        report_content += f"""
---

## 📈 测试分类统计

### API功能测试
"""
        
        api_tests = [r for r in self.test_results if r['test_case'].startswith('API-')]
        api_passed = sum(1 for r in api_tests if r['status'])
        report_content += f"- 总计: {len(api_tests)} 个接口\n"
        report_content += f"- 通过: {api_passed} 个\n"
        report_content += f"- 成功率: {(api_passed/len(api_tests)*100) if api_tests else 0:.1f}%\n\n"
        
        ### 任务管理测试
        task_tests = [r for r in self.test_results if r['test_case'].startswith('TASK-')]
        task_passed = sum(1 for r in task_tests if r['status'])
        report_content += f"### 任务管理测试\n"
        report_content += f"- 总计: {len(task_tests)} 个测试\n"
        report_content += f"- 通过: {task_passed} 个\n"
        report_content += f"- 成功率: {(task_passed/len(task_tests)*100) if task_tests else 0:.1f}%\n\n"
        
        ### 数据质量测试
        data_tests = [r for r in self.test_results if r['test_case'].startswith('DATA-')]
        data_passed = sum(1 for r in data_tests if r['status'])
        report_content += f"### 数据质量测试\n"
        report_content += f"- 总计: {len(data_tests)} 个测试\n"
        report_content += f"- 通过: {data_passed} 个\n"
        report_content += f"- 成功率: {(data_passed/len(data_tests)*100) if data_tests else 0:.1f}%\n\n"
        
        ### 性能测试
        perf_tests = [r for r in self.test_results if r['test_case'].startswith('PERF-')]
        perf_passed = sum(1 for r in perf_tests if r['status'])
        report_content += f"### 性能测试\n"
        report_content += f"- 总计: {len(perf_tests)} 个测试\n"
        report_content += f"- 通过: {perf_passed} 个\n"
        report_content += f"- 成功率: {(perf_passed/len(perf_tests)*100) if perf_tests else 0:.1f}%\n\n"
        
        report_content += f"""---

## 🔍 问题分析

### 失败的测试用例
"""
        
        failed_tests_list = [r for r in self.test_results if not r['status']]
        if failed_tests_list:
            for test in failed_tests_list:
                report_content += f"- **{test['test_case']}**: {test['message']}\n"
        else:
            report_content += "- 无失败测试用例 ✅\n"
        
        report_content += f"""
---

## 📋 验收结论

### 系统功能完整性
{"✅ 通过" if success_rate >= 90 else "❌ 未通过"} - 成功率: {success_rate:.1f}%

### 关键功能验证
- API接口功能: {"✅ 正常" if api_passed >= len(api_tests) * 0.9 else "❌ 异常"}
- 任务创建执行: {"✅ 正常" if task_passed == len(task_tests) else "❌ 异常"}
- 数据质量: {"✅ 良好" if data_passed >= len(data_tests) * 0.8 else "❌ 待改进"}
- 系统性能: {"✅ 满足要求" if perf_passed >= len(perf_tests) * 0.8 else "❌ 需优化"}

### 上线建议
"""
        
        if success_rate >= 95:
            report_content += "✅ **建议上线** - 系统功能完整，质量良好，可以进入生产环境。\n"
        elif success_rate >= 85:
            report_content += "⚠️ **条件上线** - 系统基本功能正常，建议修复关键问题后上线。\n"
        else:
            report_content += "❌ **不建议上线** - 存在较多问题，需要进一步完善后再次测试。\n"
        
        report_content += f"""
---

## 📞 联系信息

**测试负责人**: UAT测试团队  
**技术支持**: 基金报告平台开发组  
**测试时间**: {datetime.now().strftime('%Y年%m月%d日')}

---

**测试状态**: 已完成  
**下一步行动**: {"准备生产部署" if success_rate >= 85 else "修复问题并重新测试"}
"""
        
        # 保存报告
        report_file = self.project_root / f"reports/UAT测试报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.log('SUCCESS', f"UAT测试报告已生成: {report_file}")
        return str(report_file)
    
    def run_uat_tests(self) -> Dict[str, Any]:
        """运行完整的UAT测试"""
        self.start_time = time.time()
        
        self.log('TITLE', '=' * 60)
        self.log('TITLE', 'UAT测试开始：用户验收测试')
        self.log('TITLE', 'User Acceptance Testing - Stage 5')
        self.log('TITLE', '=' * 60)
        
        # 1. 系统健康检查
        self.log('INFO', '\n1. 系统健康状态检查...')
        health_ok = self.check_system_health()
        docker_ok = self.check_docker_services()
        
        if not (health_ok and docker_ok):
            self.log('ERROR', '系统健康检查失败，无法继续测试')
            return {'status': 'failed', 'reason': 'system_health_check_failed'}
        
        # 2. API端点测试
        self.log('INFO', '\n2. API端点功能测试...')
        api_results = self.test_api_endpoints()
        
        # 3. 任务创建测试
        self.log('INFO', '\n3. 任务创建功能测试...')
        task_result = self.test_task_creation()
        
        # 4. 数据质量测试
        self.log('INFO', '\n4. 数据质量测试...')
        data_quality_results = self.test_data_quality()
        
        # 5. 性能测试
        self.log('INFO', '\n5. 系统性能测试...')
        performance_results = self.test_performance()
        
        # 6. 生成测试报告
        self.log('INFO', '\n6. 生成测试报告...')
        report_file = self.generate_uat_report()
        
        # 计算总体结果
        total_time = time.time() - self.start_time
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['status'])
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 输出测试结果
        self.log('INFO', '\n' + '=' * 50)
        self.log('INFO', 'UAT测试结果汇总')
        self.log('INFO', '=' * 50)
        
        self.log('INFO', f'总测试时间: {total_time:.1f}秒')
        self.log('INFO', f'总测试用例: {total_tests}')
        self.log('INFO', f'通过用例: {passed_tests}')
        self.log('INFO', f'失败用例: {total_tests - passed_tests}')
        self.log('INFO', f'成功率: {success_rate:.1f}%')
        
        if success_rate >= 95:
            self.log('SUCCESS', '\n🎉 UAT测试全面通过！')
            self.log('SUCCESS', '✅ 系统已准备好进入生产环境')
            test_status = 'passed'
        elif success_rate >= 85:
            self.log('WARNING', '\n⚠️ UAT测试基本通过，存在少量问题')
            self.log('WARNING', '🔧 建议修复关键问题后上线')
            test_status = 'passed_with_issues'
        else:
            self.log('ERROR', '\n❌ UAT测试未通过')
            self.log('ERROR', '🛠️ 需要修复问题后重新测试')
            test_status = 'failed'
        
        # 生成测试结果JSON
        result_summary = {
            'test_status': test_status,
            'execution_time': total_time,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results,
            'report_file': report_file,
            'timestamp': datetime.now().isoformat(),
            'recommendations': {
                'ready_for_production': success_rate >= 95,
                'conditional_release': 85 <= success_rate < 95,
                'needs_improvement': success_rate < 85
            }
        }
        
        # 保存测试结果JSON
        result_file = self.project_root / f'uat_test_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_summary, f, ensure_ascii=False, indent=2)
        
        self.log('INFO', f'\n测试结果已保存: {result_file}')
        self.log('INFO', f'测试报告已保存: {report_file}')
        
        return result_summary

def main():
    """主函数"""
    tester = UATTester()
    
    try:
        result = tester.run_uat_tests()
        
        # 设置退出码
        if result['test_status'] == 'passed':
            sys.exit(0)  # 成功
        elif result['test_status'] == 'passed_with_issues':
            sys.exit(1)  # 有问题但可接受
        else:
            sys.exit(2)  # 失败
            
    except KeyboardInterrupt:
        tester.log('WARNING', '\nUAT测试被用户中断')
        sys.exit(3)
    except Exception as e:
        tester.log('ERROR', f'\nUAT测试过程发生错误: {str(e)}')
        sys.exit(4)

if __name__ == '__main__':
    main()