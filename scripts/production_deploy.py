#!/usr/bin/env python3
"""
生产环境部署脚本
Production Deployment Script

执行生产环境的完整部署流程
"""

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class Color:
    """颜色常量"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class ProductionDeployer:
    """生产环境部署器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.deployment_log = []
        self.start_time = None
        
    def log(self, level: str, message: str, **kwargs):
        """记录日志"""
        colors = {
            'INFO': Color.BLUE,
            'SUCCESS': Color.GREEN,
            'WARNING': Color.YELLOW,
            'ERROR': Color.RED,
            'TITLE': Color.PURPLE,
            'STEP': Color.CYAN
        }
        color = colors.get(level, Color.NC)
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"{color}[{timestamp} {level}]{Color.NC} {message}"
        print(formatted_message)
        
        # 记录到部署日志
        self.deployment_log.append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'kwargs': kwargs
        })
    
    def run_command(self, cmd: str, cwd: Optional[Path] = None, timeout: int = 300) -> Dict[str, Any]:
        """执行系统命令"""
        if cwd is None:
            cwd = self.project_root
            
        self.log('INFO', f"执行命令: {cmd}")
        
        try:
            result = subprocess.run(
                cmd.split(),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                self.log('SUCCESS', f"命令执行成功")
                return {
                    'success': True,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
            else:
                self.log('ERROR', f"命令执行失败 (退出码: {result.returncode})")
                self.log('ERROR', f"错误输出: {result.stderr}")
                return {
                    'success': False,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
                
        except subprocess.TimeoutExpired:
            self.log('ERROR', f"命令执行超时 ({timeout}秒)")
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            self.log('ERROR', f"命令执行异常: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def check_prerequisites(self) -> bool:
        """检查部署前置条件"""
        self.log('STEP', "1. 检查部署前置条件...")
        
        # 检查必要文件
        required_files = [
            'docker-compose.prod.yml',
            'Dockerfile.prod',
            'deploy.sh',
            '.env.prod.template'
        ]
        
        missing_files = []
        for file in required_files:
            if not (self.project_root / file).exists():
                missing_files.append(file)
        
        if missing_files:
            self.log('ERROR', f"缺少必要文件: {', '.join(missing_files)}")
            return False
        
        # 检查Docker和Docker Compose
        docker_check = self.run_command('docker --version')
        if not docker_check['success']:
            self.log('ERROR', "Docker未安装或不可用")
            return False
        
        compose_check = self.run_command('docker-compose --version')
        if not compose_check['success']:
            self.log('ERROR', "Docker Compose未安装或不可用")
            return False
        
        self.log('SUCCESS', "前置条件检查通过")
        return True
    
    def prepare_environment(self) -> bool:
        """准备部署环境"""
        self.log('STEP', "2. 准备部署环境...")
        
        # 检查是否有现有的生产环境配置
        env_prod_file = self.project_root / '.env.prod'
        
        if not env_prod_file.exists():
            self.log('INFO', "未找到生产环境配置，使用模板创建...")
            
            # 读取模板文件
            template_file = self.project_root / '.env.prod.template'
            if template_file.exists():
                template_content = template_file.read_text()
                
                # 生成随机密码
                import secrets
                import string
                
                def generate_password(length=32):
                    alphabet = string.ascii_letters + string.digits
                    return ''.join(secrets.choice(alphabet) for _ in range(length))
                
                # 替换模板中的占位符
                replacements = {
                    'POSTGRES_PASSWORD=your_postgres_password': f'POSTGRES_PASSWORD={generate_password()}',
                    'REDIS_PASSWORD=your_redis_password': f'REDIS_PASSWORD={generate_password()}',
                    'MINIO_SECRET_KEY=your_minio_secret': f'MINIO_SECRET_KEY={generate_password()}',
                    'SECRET_KEY=your_secret_key': f'SECRET_KEY={generate_password()}'
                }
                
                env_content = template_content
                for old, new in replacements.items():
                    env_content = env_content.replace(old, new)
                
                # 写入生产环境配置
                env_prod_file.write_text(env_content)
                self.log('SUCCESS', "生产环境配置文件已创建")
            else:
                self.log('ERROR', "找不到环境配置模板文件")
                return False
        else:
            self.log('INFO', "使用现有的生产环境配置")
        
        # 创建必要的目录
        directories = ['logs', 'data', 'exports', 'reports']
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            self.log('INFO', f"创建目录: {directory}")
        
        self.log('SUCCESS', "环境准备完成")
        return True
    
    def build_production_images(self) -> bool:
        """构建生产环境镜像"""
        self.log('STEP', "3. 构建生产环境镜像...")
        
        # 构建生产镜像
        build_result = self.run_command(
            'docker-compose -f docker-compose.prod.yml build --no-cache',
            timeout=600  # 10分钟超时
        )
        
        if not build_result['success']:
            self.log('ERROR', "Docker镜像构建失败")
            return False
        
        self.log('SUCCESS', "生产环境镜像构建完成")
        return True
    
    def deploy_services(self) -> bool:
        """部署服务"""
        self.log('STEP', "4. 部署服务...")
        
        # 停止现有服务（如果有）
        self.log('INFO', "停止现有服务...")
        stop_result = self.run_command(
            'docker-compose -f docker-compose.prod.yml down'
        )
        
        # 启动服务
        self.log('INFO', "启动生产环境服务...")
        start_result = self.run_command(
            'docker-compose -f docker-compose.prod.yml up -d',
            timeout=300
        )
        
        if not start_result['success']:
            self.log('ERROR', "服务启动失败")
            return False
        
        self.log('SUCCESS', "服务启动完成")
        return True
    
    def wait_for_services(self) -> bool:
        """等待服务启动完成"""
        self.log('STEP', "5. 等待服务启动...")
        
        # 等待服务启动的最大时间
        max_wait_time = 300  # 5分钟
        wait_interval = 10   # 每10秒检查一次
        
        services_to_check = [
            {'name': 'postgres', 'check': self.check_postgres},
            {'name': 'redis', 'check': self.check_redis},
            {'name': 'minio', 'check': self.check_minio},
            {'name': 'api', 'check': self.check_api}
        ]
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            all_ready = True
            
            for service in services_to_check:
                if not service['check']():
                    all_ready = False
                    self.log('INFO', f"等待 {service['name']} 服务启动...")
                    break
                else:
                    self.log('SUCCESS', f"✓ {service['name']} 服务已就绪")
            
            if all_ready:
                self.log('SUCCESS', "所有服务已启动并就绪")
                return True
            
            time.sleep(wait_interval)
        
        self.log('ERROR', f"服务启动超时 ({max_wait_time}秒)")
        return False
    
    def check_postgres(self) -> bool:
        """检查PostgreSQL服务"""
        try:
            result = self.run_command(
                'docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready'
            )
            return result['success']
        except:
            return False
    
    def check_redis(self) -> bool:
        """检查Redis服务"""
        try:
            result = self.run_command(
                'docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping'
            )
            return result['success'] and 'PONG' in result['stdout']
        except:
            return False
    
    def check_minio(self) -> bool:
        """检查MinIO服务"""
        try:
            response = requests.get('http://localhost:9000/minio/health/live', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def check_api(self) -> bool:
        """检查API服务"""
        try:
            response = requests.get('http://localhost:8000/health', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def initialize_database(self) -> bool:
        """初始化数据库"""
        self.log('STEP', "6. 初始化数据库...")
        
        # 运行数据库迁移
        migration_result = self.run_command(
            'docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head'
        )
        
        if not migration_result['success']:
            self.log('ERROR', "数据库迁移失败")
            return False
        
        self.log('SUCCESS', "数据库初始化完成")
        return True
    
    def verify_deployment(self) -> Dict[str, bool]:
        """验证部署结果"""
        self.log('STEP', "7. 验证部署结果...")
        
        verification_results = {}
        
        # 检查服务状态
        status_result = self.run_command(
            'docker-compose -f docker-compose.prod.yml ps'
        )
        
        if status_result['success']:
            services_output = status_result['stdout']
            required_services = ['postgres', 'redis', 'minio', 'api', 'celery_worker']
            
            for service in required_services:
                if service in services_output and 'Up' in services_output:
                    verification_results[f'{service}_running'] = True
                    self.log('SUCCESS', f"✓ {service} 服务运行正常")
                else:
                    verification_results[f'{service}_running'] = False
                    self.log('ERROR', f"✗ {service} 服务未运行")
        
        # 测试API端点
        api_endpoints = [
            ('/health', 'health_check'),
            ('/docs', 'api_docs'),
            ('/api/v1/funds/', 'funds_api'),
            ('/api/v1/reports/', 'reports_api'),
            ('/api/v1/tasks/', 'tasks_api')
        ]
        
        for endpoint, test_name in api_endpoints:
            try:
                response = requests.get(f'http://localhost:8000{endpoint}', timeout=10)
                verification_results[test_name] = response.status_code == 200
                
                if verification_results[test_name]:
                    self.log('SUCCESS', f"✓ {endpoint} 响应正常")
                else:
                    self.log('ERROR', f"✗ {endpoint} 响应异常: {response.status_code}")
            except Exception as e:
                verification_results[test_name] = False
                self.log('ERROR', f"✗ {endpoint} 请求失败: {str(e)}")
        
        return verification_results
    
    def generate_deployment_report(self, verification_results: Dict[str, bool]) -> str:
        """生成部署报告"""
        self.log('STEP', "8. 生成部署报告...")
        
        total_time = time.time() - self.start_time
        total_checks = len(verification_results)
        passed_checks = sum(1 for result in verification_results.values() if result)
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        # 生成报告内容
        report_content = f"""# 生产环境部署报告
## Production Deployment Report

**部署执行时间**: {datetime.fromtimestamp(self.start_time).strftime('%Y年%m月%d日 %H:%M:%S')}  
**完成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}  
**总用时**: {int(total_time // 60)}分{int(total_time % 60)}秒

---

## 📊 部署概览

- **部署状态**: {"✅ 成功" if success_rate >= 90 else "⚠️ 部分成功" if success_rate >= 70 else "❌ 失败"}
- **验证项目总数**: {total_checks}
- **通过项目数**: {passed_checks}
- **失败项目数**: {total_checks - passed_checks}
- **成功率**: {success_rate:.1f}%

---

## 🔍 详细验证结果

| 验证项目 | 状态 | 说明 |
|---------|------|------|
"""
        
        for check_name, result in verification_results.items():
            status_icon = "✅" if result else "❌"
            description = check_name.replace('_', ' ').title()
            report_content += f"| {description} | {status_icon} | {'正常' if result else '异常'} |\n"
        
        report_content += f"""
---

## 🚀 服务信息

### 访问地址
- **API文档**: http://localhost:8000/docs
- **API健康检查**: http://localhost:8000/health
- **MinIO管理控制台**: http://localhost:9001

### 管理命令
```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看服务日志
docker-compose -f docker-compose.prod.yml logs -f [service_name]

# 重启服务
docker-compose -f docker-compose.prod.yml restart [service_name]

# 停止所有服务
docker-compose -f docker-compose.prod.yml down

# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d
```

### 配置文件位置
- **环境配置**: `.env.prod`
- **Docker配置**: `docker-compose.prod.yml`
- **运维手册**: `docs/operations/运维手册.md`

---

## 📋 部署步骤记录

"""
        
        for i, log_entry in enumerate(self.deployment_log, 1):
            if log_entry['level'] in ['STEP', 'SUCCESS', 'ERROR']:
                timestamp = datetime.fromisoformat(log_entry['timestamp']).strftime('%H:%M:%S')
                report_content += f"{i}. [{timestamp}] {log_entry['message']}\n"
        
        report_content += f"""
---

## 🎯 后续建议

### 如果部署成功 (成功率 ≥ 90%)
1. ✅ **开始历史数据回补**: 运行 `python scripts/historical_backfill.py`
2. ✅ **配置监控告警**: 设置系统监控和日志告警
3. ✅ **定期备份**: 配置数据库和文件的定期备份
4. ✅ **用户培训**: 对终端用户进行系统使用培训

### 如果部署部分成功 (成功率 70-90%)
1. ⚠️ **排查问题**: 重点关注失败的验证项目
2. ⚠️ **修复问题**: 根据错误日志修复相关问题
3. ⚠️ **重新验证**: 问题修复后重新运行验证脚本

### 如果部署失败 (成功率 < 70%)
1. ❌ **全面排查**: 检查系统环境、配置文件、网络连接
2. ❌ **查看日志**: `docker-compose -f docker-compose.prod.yml logs`
3. ❌ **重新部署**: 修复问题后重新运行部署脚本

---

## 📞 技术支持

**部署负责人**: 生产部署团队  
**技术支持**: 基金报告平台开发组  
**紧急联系**: 运维团队值班电话  
**文档位置**: `docs/operations/运维手册.md`

---

**部署状态**: {"已完成" if success_rate >= 70 else "需要重试"}  
**系统版本**: 第五阶段生产版本  
**下一步行动**: {"开始历史数据回补和用户培训" if success_rate >= 90 else "排查并修复部署问题"}
"""
        
        # 保存报告
        report_file = self.project_root / f"reports/生产环境部署报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.log('SUCCESS', f"部署报告已生成: {report_file}")
        return str(report_file)
    
    def run_production_deployment(self) -> Dict[str, Any]:
        """运行生产环境部署"""
        self.start_time = time.time()
        
        self.log('TITLE', '=' * 60)
        self.log('TITLE', '生产环境部署开始')
        self.log('TITLE', 'Production Environment Deployment')
        self.log('TITLE', '=' * 60)
        
        # 执行部署步骤
        steps = [
            ('检查前置条件', self.check_prerequisites),
            ('准备部署环境', self.prepare_environment),
            ('构建生产镜像', self.build_production_images),
            ('部署服务', self.deploy_services),
            ('等待服务启动', self.wait_for_services),
            ('初始化数据库', self.initialize_database),
        ]
        
        for step_name, step_function in steps:
            try:
                if not step_function():
                    self.log('ERROR', f"部署步骤失败: {step_name}")
                    return {
                        'status': 'failed',
                        'failed_step': step_name,
                        'deployment_time': time.time() - self.start_time
                    }
            except Exception as e:
                self.log('ERROR', f"部署步骤异常: {step_name} - {str(e)}")
                return {
                    'status': 'error',
                    'failed_step': step_name,
                    'error': str(e),
                    'deployment_time': time.time() - self.start_time
                }
        
        # 验证部署结果
        verification_results = self.verify_deployment()
        
        # 生成部署报告
        report_file = self.generate_deployment_report(verification_results)
        
        # 计算最终结果
        total_checks = len(verification_results)
        passed_checks = sum(1 for result in verification_results.values() if result)
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        deployment_time = time.time() - self.start_time
        
        # 输出部署结果
        self.log('INFO', '\n' + '=' * 50)
        self.log('INFO', '生产环境部署结果')
        self.log('INFO', '=' * 50)
        
        self.log('INFO', f'部署用时: {int(deployment_time // 60)}分{int(deployment_time % 60)}秒')
        self.log('INFO', f'验证项目: {passed_checks}/{total_checks}')
        self.log('INFO', f'成功率: {success_rate:.1f}%')
        
        if success_rate >= 90:
            self.log('SUCCESS', '\n🎉 生产环境部署成功！')
            self.log('SUCCESS', '✅ 系统已ready，可以开始历史数据回补')
            deployment_status = 'success'
        elif success_rate >= 70:
            self.log('WARNING', '\n⚠️ 生产环境部署基本成功，存在少量问题')
            self.log('WARNING', '🔧 建议修复问题后继续使用')
            deployment_status = 'partial_success'
        else:
            self.log('ERROR', '\n❌ 生产环境部署失败')
            self.log('ERROR', '🛠️ 需要排查和修复问题')
            deployment_status = 'failed'
        
        return {
            'status': deployment_status,
            'success_rate': success_rate,
            'deployment_time': deployment_time,
            'verification_results': verification_results,
            'report_file': report_file,
            'timestamp': datetime.now().isoformat()
        }

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生产环境部署脚本')
    parser.add_argument('--force', action='store_true', help='强制部署，忽略现有服务')
    parser.add_argument('--skip-build', action='store_true', help='跳过镜像构建步骤')
    
    args = parser.parse_args()
    
    deployer = ProductionDeployer()
    
    try:
        result = deployer.run_production_deployment()
        
        # 设置退出码
        if result['status'] == 'success':
            sys.exit(0)  # 成功
        elif result['status'] == 'partial_success':
            sys.exit(1)  # 部分成功
        else:
            sys.exit(2)  # 失败
            
    except KeyboardInterrupt:
        deployer.log('WARNING', '\n生产环境部署被用户中断')
        sys.exit(3)
    except Exception as e:
        deployer.log('ERROR', f'\n生产环境部署过程发生错误: {str(e)}')
        sys.exit(4)

if __name__ == '__main__':
    main()