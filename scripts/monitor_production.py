#!/usr/bin/env python3
"""
生产环境监控脚本
Production Monitoring Script

持续监控生产环境的运行状态，确保系统稳定运行
"""

import os
import sys
import time
import json
import psutil
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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

class ProductionMonitor:
    """生产环境监控器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.settings = get_settings()
        self.monitoring_data = []
        self.alert_thresholds = {
            'cpu_usage': 80.0,           # CPU使用率阈值 (%)
            'memory_usage': 85.0,        # 内存使用率阈值 (%)
            'disk_usage': 90.0,          # 磁盘使用率阈值 (%)
            'api_response_time': 5.0,    # API响应时间阈值 (秒)
            'error_rate': 5.0,           # 错误率阈值 (%)
            'queue_length': 100          # 任务队列长度阈值
        }
        
        # 配置结构化日志
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
        
        self.logger = structlog.get_logger("production_monitor")
        
    def log(self, level: str, message: str, **kwargs):
        """记录日志"""
        colors = {
            'INFO': Color.BLUE,
            'SUCCESS': Color.GREEN,
            'WARNING': Color.YELLOW,
            'ERROR': Color.RED,
            'ALERT': Color.RED,
            'TITLE': Color.PURPLE
        }
        color = colors.get(level, Color.NC)
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{color}[{timestamp} {level}]{Color.NC} {message}")
        
        # 同时记录到结构化日志
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, **kwargs)
    
    def check_system_resources(self) -> Dict[str, Any]:
        """检查系统资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 网络IO
            network = psutil.net_io_counters()
            
            resource_data = {
                'timestamp': datetime.now().isoformat(),
                'cpu_usage': cpu_percent,
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory_percent
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk_percent
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            }
            
            # 检查资源使用率告警
            alerts = []
            if cpu_percent > self.alert_thresholds['cpu_usage']:
                alerts.append(f"CPU使用率过高: {cpu_percent:.1f}%")
                self.log('ALERT', f"🚨 CPU使用率告警: {cpu_percent:.1f}%")
            
            if memory_percent > self.alert_thresholds['memory_usage']:
                alerts.append(f"内存使用率过高: {memory_percent:.1f}%")
                self.log('ALERT', f"🚨 内存使用率告警: {memory_percent:.1f}%")
            
            if disk_percent > self.alert_thresholds['disk_usage']:
                alerts.append(f"磁盘使用率过高: {disk_percent:.1f}%")
                self.log('ALERT', f"🚨 磁盘使用率告警: {disk_percent:.1f}%")
            
            resource_data['alerts'] = alerts
            
            if not alerts:
                self.log('SUCCESS', 
                    f"系统资源正常 - CPU: {cpu_percent:.1f}%, "
                    f"内存: {memory_percent:.1f}%, "
                    f"磁盘: {disk_percent:.1f}%"
                )
            
            return resource_data
            
        except Exception as e:
            self.log('ERROR', f"系统资源检查失败: {str(e)}")
            return {'error': str(e)}
    
    def check_docker_services(self) -> Dict[str, Any]:
        """检查Docker服务状态"""
        try:
            result = subprocess.run(
                ['docker-compose', '-f', 'docker-compose.prod.yml', 'ps', '--format', 'json'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 解析JSON输出
                services_data = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            service = json.loads(line)
                            services_data.append(service)
                        except json.JSONDecodeError:
                            continue
                
                # 分析服务状态
                service_status = {}
                total_services = len(services_data)
                running_services = 0
                
                for service in services_data:
                    service_name = service.get('Service', 'unknown')
                    service_state = service.get('State', 'unknown')
                    
                    service_status[service_name] = {
                        'state': service_state,
                        'status': service.get('Status', ''),
                        'ports': service.get('Ports', ''),
                        'running': service_state == 'running'
                    }
                    
                    if service_state == 'running':
                        running_services += 1
                        self.log('SUCCESS', f"✓ {service_name} 服务运行正常")
                    else:
                        self.log('ERROR', f"✗ {service_name} 服务状态异常: {service_state}")
                
                docker_data = {
                    'timestamp': datetime.now().isoformat(),
                    'total_services': total_services,
                    'running_services': running_services,
                    'service_status': service_status,
                    'health_rate': (running_services / total_services * 100) if total_services > 0 else 0
                }
                
                if running_services < total_services:
                    self.log('ALERT', f"🚨 服务异常告警: {running_services}/{total_services} 服务运行中")
                
                return docker_data
            else:
                self.log('ERROR', f"Docker服务检查失败: {result.stderr}")
                return {'error': result.stderr}
                
        except Exception as e:
            self.log('ERROR', f"Docker服务检查异常: {str(e)}")
            return {'error': str(e)}
    
    def check_api_health(self) -> Dict[str, Any]:
        """检查API服务健康状况"""
        api_data = {
            'timestamp': datetime.now().isoformat(),
            'endpoints': {},
            'overall_health': True,
            'response_times': []
        }
        
        # 测试的API端点
        endpoints = [
            ('/health', '健康检查'),
            ('/api/v1/funds/', '基金列表'),
            ('/api/v1/reports/', '报告列表'),
            ('/api/v1/tasks/', '任务列表'),
            ('/api/v1/tasks/stats/summary', '任务统计')
        ]
        
        for endpoint, description in endpoints:
            try:
                start_time = time.time()
                response = requests.get(
                    f"http://localhost:{self.settings.API_PORT}{endpoint}",
                    timeout=10
                )
                response_time = time.time() - start_time
                
                endpoint_status = {
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'healthy': response.status_code == 200,
                    'description': description
                }
                
                if response.status_code == 200:
                    self.log('SUCCESS', f"✓ {description} ({endpoint}): {response_time:.3f}s")
                else:
                    self.log('ERROR', f"✗ {description} ({endpoint}): {response.status_code}")
                    api_data['overall_health'] = False
                
                # 检查响应时间告警
                if response_time > self.alert_thresholds['api_response_time']:
                    self.log('ALERT', f"🚨 API响应时间告警: {endpoint} - {response_time:.3f}s")
                    endpoint_status['slow_response'] = True
                
                api_data['endpoints'][endpoint] = endpoint_status
                api_data['response_times'].append(response_time)
                
            except requests.RequestException as e:
                self.log('ERROR', f"✗ {description} ({endpoint}): 请求失败 - {str(e)}")
                api_data['endpoints'][endpoint] = {
                    'error': str(e),
                    'healthy': False,
                    'description': description
                }
                api_data['overall_health'] = False
        
        # 计算平均响应时间
        if api_data['response_times']:
            api_data['avg_response_time'] = sum(api_data['response_times']) / len(api_data['response_times'])
            api_data['max_response_time'] = max(api_data['response_times'])
        
        return api_data
    
    def check_database_status(self) -> Dict[str, Any]:
        """检查数据库状态"""
        try:
            # 通过Docker检查PostgreSQL状态
            result = subprocess.run(
                ['docker-compose', '-f', 'docker-compose.prod.yml', 'exec', '-T', 'postgres', 
                 'psql', '-U', 'funduser_prod', '-d', 'fundreport_prod', '-c', 
                 'SELECT COUNT(*) as total_funds FROM funds; SELECT COUNT(*) as total_reports FROM reports;'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.log('SUCCESS', "✓ 数据库连接正常")
                
                # 简单解析数据统计
                lines = result.stdout.strip().split('\n')
                db_data = {
                    'timestamp': datetime.now().isoformat(),
                    'connected': True,
                    'status': 'healthy'
                }
                
                # 尝试解析数据行数（简化处理）
                try:
                    for line in lines:
                        if line.strip().isdigit():
                            # 这是一个简化的实现，实际应该更精确地解析
                            break
                except:
                    pass
                
                return db_data
            else:
                self.log('ERROR', f"✗ 数据库连接失败: {result.stderr}")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'connected': False,
                    'error': result.stderr
                }
                
        except Exception as e:
            self.log('ERROR', f"数据库状态检查异常: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'connected': False,
                'error': str(e)
            }
    
    def check_celery_status(self) -> Dict[str, Any]:
        """检查Celery任务队列状态"""
        try:
            # 通过Redis检查任务队列
            result = subprocess.run(
                ['docker-compose', '-f', 'docker-compose.prod.yml', 'exec', '-T', 'redis',
                 'redis-cli', 'LLEN', 'celery'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            celery_data = {
                'timestamp': datetime.now().isoformat()
            }
            
            if result.returncode == 0:
                queue_length = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
                celery_data.update({
                    'queue_length': queue_length,
                    'queue_healthy': True
                })
                
                if queue_length > self.alert_thresholds['queue_length']:
                    self.log('ALERT', f"🚨 任务队列告警: {queue_length} 个待处理任务")
                    celery_data['queue_alert'] = True
                else:
                    self.log('SUCCESS', f"✓ 任务队列正常: {queue_length} 个待处理任务")
                
            else:
                self.log('ERROR', f"✗ 任务队列检查失败: {result.stderr}")
                celery_data.update({
                    'queue_healthy': False,
                    'error': result.stderr
                })
            
            return celery_data
            
        except Exception as e:
            self.log('ERROR', f"Celery状态检查异常: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'queue_healthy': False,
                'error': str(e)
            }
    
    def check_log_files(self) -> Dict[str, Any]:
        """检查日志文件状态"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'log_files': {}
        }
        
        # 检查的日志文件
        log_files = [
            'logs/api.log',
            'logs/celery_worker.log',
            'logs/celery_beat.log'
        ]
        
        for log_file in log_files:
            log_path = self.project_root / log_file
            
            if log_path.exists():
                try:
                    stat = log_path.stat()
                    file_size = stat.st_size
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    # 检查最近的错误日志
                    recent_errors = 0
                    try:
                        with open(log_path, 'r') as f:
                            # 读取最后1000行
                            lines = f.readlines()[-1000:]
                            for line in lines:
                                if 'ERROR' in line.upper() or 'CRITICAL' in line.upper():
                                    recent_errors += 1
                    except:
                        pass
                    
                    log_data['log_files'][log_file] = {
                        'exists': True,
                        'size': file_size,
                        'modified': modified_time.isoformat(),
                        'recent_errors': recent_errors
                    }
                    
                    if recent_errors > 10:
                        self.log('ALERT', f"🚨 日志错误告警: {log_file} 最近有 {recent_errors} 个错误")
                    else:
                        self.log('SUCCESS', f"✓ {log_file}: {file_size} bytes, {recent_errors} 错误")
                        
                except Exception as e:
                    log_data['log_files'][log_file] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                log_data['log_files'][log_file] = {
                    'exists': False
                }
                self.log('WARNING', f"⚠ 日志文件不存在: {log_file}")
        
        return log_data
    
    def generate_monitoring_report(self, monitoring_data: Dict[str, Any]) -> str:
        """生成监控报告"""
        timestamp = datetime.now()
        
        # 计算整体健康分数
        health_score = 100
        alerts = []
        
        # 系统资源检查
        if 'system' in monitoring_data and 'alerts' in monitoring_data['system']:
            health_score -= len(monitoring_data['system']['alerts']) * 10
            alerts.extend(monitoring_data['system']['alerts'])
        
        # Docker服务检查
        if 'docker' in monitoring_data:
            health_rate = monitoring_data['docker'].get('health_rate', 0)
            if health_rate < 100:
                health_score -= (100 - health_rate)
                alerts.append(f"Docker服务健康率: {health_rate:.1f}%")
        
        # API健康检查
        if 'api' in monitoring_data:
            if not monitoring_data['api'].get('overall_health', False):
                health_score -= 20
                alerts.append("API服务异常")
        
        # 生成报告内容
        report_content = f"""# 生产环境监控报告
## Production Environment Monitoring Report

**监控时间**: {timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}  
**系统健康分数**: {max(health_score, 0)}/100  
**告警数量**: {len(alerts)}

---

## 📊 系统概览

### 整体状态
"""
        
        if health_score >= 90:
            report_content += "✅ **系统状态优秀** - 所有组件运行正常\n"
        elif health_score >= 70:
            report_content += "⚠️ **系统状态良好** - 存在少量问题需要关注\n"
        elif health_score >= 50:
            report_content += "🔧 **系统状态一般** - 存在多个问题需要处理\n"
        else:
            report_content += "🚨 **系统状态严重** - 需要立即处理严重问题\n"
        
        # 告警摘要
        if alerts:
            report_content += f"\n### 🚨 当前告警\n"
            for alert in alerts:
                report_content += f"- {alert}\n"
        else:
            report_content += f"\n### ✅ 无告警\n"
        
        # 详细监控数据
        if 'system' in monitoring_data:
            system_data = monitoring_data['system']
            report_content += f"""
---

## 💻 系统资源

- **CPU使用率**: {system_data.get('cpu_usage', 0):.1f}%
- **内存使用率**: {system_data.get('memory', {}).get('percent', 0):.1f}%
- **磁盘使用率**: {system_data.get('disk', {}).get('percent', 0):.1f}%
- **可用内存**: {system_data.get('memory', {}).get('available', 0) / (1024**3):.1f} GB
- **可用磁盘**: {system_data.get('disk', {}).get('free', 0) / (1024**3):.1f} GB
"""
        
        if 'docker' in monitoring_data:
            docker_data = monitoring_data['docker']
            report_content += f"""
---

## 🐳 Docker服务

- **运行服务**: {docker_data.get('running_services', 0)}/{docker_data.get('total_services', 0)}
- **健康率**: {docker_data.get('health_rate', 0):.1f}%

### 服务状态详情
"""
            
            for service, status in docker_data.get('service_status', {}).items():
                status_icon = "✅" if status.get('running', False) else "❌"
                report_content += f"- {status_icon} **{service}**: {status.get('state', 'unknown')}\n"
        
        if 'api' in monitoring_data:
            api_data = monitoring_data['api']
            report_content += f"""
---

## 🌐 API服务

- **整体健康**: {"✅ 正常" if api_data.get('overall_health', False) else "❌ 异常"}
- **平均响应时间**: {api_data.get('avg_response_time', 0):.3f}s
- **最大响应时间**: {api_data.get('max_response_time', 0):.3f}s

### API端点状态
"""
            
            for endpoint, status in api_data.get('endpoints', {}).items():
                if 'error' in status:
                    report_content += f"- ❌ **{endpoint}**: 错误 - {status['error']}\n"
                else:
                    status_icon = "✅" if status.get('healthy', False) else "❌"
                    response_time = status.get('response_time', 0)
                    report_content += f"- {status_icon} **{endpoint}**: {response_time:.3f}s\n"
        
        if 'database' in monitoring_data:
            db_data = monitoring_data['database']
            report_content += f"""
---

## 🗄️ 数据库

- **连接状态**: {"✅ 正常" if db_data.get('connected', False) else "❌ 异常"}
- **数据库状态**: {db_data.get('status', '未知')}
"""
        
        if 'celery' in monitoring_data:
            celery_data = monitoring_data['celery']
            report_content += f"""
---

## ⚙️ 任务队列

- **队列状态**: {"✅ 正常" if celery_data.get('queue_healthy', False) else "❌ 异常"}
- **待处理任务**: {celery_data.get('queue_length', 0)} 个
"""
        
        report_content += f"""
---

## 📋 建议行动

### 立即处理 (健康分数 < 70)
"""
        
        if health_score < 70:
            if health_score < 50:
                report_content += "1. 🚨 **立即检查系统状态** - 健康分数过低\n"
                report_content += "2. 🔧 **优先处理告警项目** - 根据告警信息排查问题\n"
                report_content += "3. 📞 **联系技术支持** - 如需帮助请及时联系\n"
            else:
                report_content += "1. ⚠️ **关注告警信息** - 处理当前告警项目\n"
                report_content += "2. 🔍 **分析性能数据** - 识别潜在瓶颈\n"
                report_content += "3. 📈 **优化系统配置** - 根据监控数据调整\n"
        else:
            report_content += "- ✅ 当前系统状态良好，继续保持监控\n"
        
        report_content += f"""
### 定期维护
1. **日志清理**: 定期清理过大的日志文件
2. **资源监控**: 持续关注CPU、内存、磁盘使用情况
3. **服务检查**: 确保所有Docker服务正常运行
4. **数据备份**: 定期执行数据库和文件备份

---

## 📞 联系信息

**监控负责人**: 运维团队  
**技术支持**: 基金报告平台开发组  
**紧急联系**: 7x24小时值班电话  

---

**监控状态**: 实时监控中  
**下次检查**: {(timestamp + timedelta(minutes=5)).strftime('%H:%M:%S')}  
**报告频率**: 每5分钟
"""
        
        return report_content
    
    def run_single_check(self) -> Dict[str, Any]:
        """运行单次监控检查"""
        self.log('INFO', "开始生产环境监控检查...")
        
        monitoring_data = {}
        
        # 系统资源检查
        self.log('INFO', "检查系统资源...")
        monitoring_data['system'] = self.check_system_resources()
        
        # Docker服务检查
        self.log('INFO', "检查Docker服务...")
        monitoring_data['docker'] = self.check_docker_services()
        
        # API健康检查
        self.log('INFO', "检查API服务...")
        monitoring_data['api'] = self.check_api_health()
        
        # 数据库状态检查
        self.log('INFO', "检查数据库状态...")
        monitoring_data['database'] = self.check_database_status()
        
        # Celery任务队列检查
        self.log('INFO', "检查任务队列...")
        monitoring_data['celery'] = self.check_celery_status()
        
        # 日志文件检查
        self.log('INFO', "检查日志文件...")
        monitoring_data['logs'] = self.check_log_files()
        
        # 生成监控报告
        report_content = self.generate_monitoring_report(monitoring_data)
        
        # 保存监控数据
        monitoring_data['timestamp'] = datetime.now().isoformat()
        monitoring_data['report_content'] = report_content
        
        return monitoring_data
    
    def run_continuous_monitoring(self, interval: int = 300, duration: Optional[int] = None):
        """运行持续监控"""
        self.log('TITLE', '=' * 60)
        self.log('TITLE', '生产环境持续监控开始')
        self.log('TITLE', f'监控间隔: {interval}秒, 持续时间: {"无限制" if duration is None else f"{duration}秒"}')
        self.log('TITLE', '=' * 60)
        
        start_time = time.time()
        check_count = 0
        
        try:
            while True:
                check_count += 1
                self.log('INFO', f"\n第 {check_count} 次监控检查 (运行时间: {int(time.time() - start_time)}秒)")
                
                # 执行监控检查
                monitoring_data = self.run_single_check()
                self.monitoring_data.append(monitoring_data)
                
                # 保存监控数据到文件
                data_file = self.project_root / f"logs/monitoring_{datetime.now().strftime('%Y%m%d')}.jsonl"
                data_file.parent.mkdir(exist_ok=True)
                
                with open(data_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(monitoring_data, ensure_ascii=False) + '\n')
                
                # 如果有告警，保存告警报告
                if 'system' in monitoring_data and monitoring_data['system'].get('alerts'):
                    alert_file = self.project_root / f"reports/监控告警_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    alert_file.parent.mkdir(exist_ok=True)
                    
                    with open(alert_file, 'w', encoding='utf-8') as f:
                        f.write(monitoring_data['report_content'])
                    
                    self.log('ALERT', f"告警报告已保存: {alert_file}")
                
                # 检查是否达到持续时间限制
                if duration and (time.time() - start_time) >= duration:
                    self.log('INFO', f"监控持续时间达到限制 ({duration}秒)，停止监控")
                    break
                
                # 等待下次检查
                self.log('INFO', f"下次检查将在 {interval} 秒后开始...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.log('WARNING', '\n监控被用户中断')
        except Exception as e:
            self.log('ERROR', f'监控过程发生错误: {str(e)}')
        
        # 生成监控摘要
        total_time = time.time() - start_time
        self.log('INFO', f"\n监控结束 - 总时间: {int(total_time)}秒, 检查次数: {check_count}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生产环境监控脚本')
    parser.add_argument('--interval', type=int, default=300, help='监控间隔(秒) (默认: 300)')
    parser.add_argument('--duration', type=int, help='监控持续时间(秒) (默认: 无限制)')
    parser.add_argument('--single', action='store_true', help='只运行单次检查')
    
    args = parser.parse_args()
    
    monitor = ProductionMonitor()
    
    try:
        if args.single:
            # 单次监控检查
            result = monitor.run_single_check()
            
            # 输出简要结果
            print("\n" + "="*50)
            print("监控检查完成")
            print("="*50)
            
            # 保存报告
            report_file = monitor.project_root / f"reports/监控报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            report_file.parent.mkdir(exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(result['report_content'])
            
            print(f"监控报告已保存: {report_file}")
            
            sys.exit(0)
        else:
            # 持续监控
            monitor.run_continuous_monitoring(args.interval, args.duration)
            sys.exit(0)
            
    except KeyboardInterrupt:
        monitor.log('WARNING', '\n监控被用户中断')
        sys.exit(1)
    except Exception as e:
        monitor.log('ERROR', f'\n监控过程发生错误: {str(e)}')
        sys.exit(2)

if __name__ == '__main__':
    main()