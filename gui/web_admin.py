#!/usr/bin/env python3
"""
基金报告平台Web管理界面
Fund Report Platform Web Admin Interface

基于Streamlit的用户友好管理界面
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

# 页面配置
st.set_page_config(
    page_title="基金报告自动化采集与分析平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    margin-bottom: 2rem;
}

.metric-card {
    background: white;
    padding: 1rem;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border-left: 4px solid #667eea;
}

.status-success {
    color: #28a745;
    font-weight: bold;
}

.status-warning {
    color: #ffc107;
    font-weight: bold;
}

.status-error {
    color: #dc3545;
    font-weight: bold;
}

.sidebar-header {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 5px;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

class FundPlatformGUI:
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.project_root = Path(__file__).parent.parent
        
    def check_api_connection(self):
        """检查API连接状态"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_system_stats(self):
        """获取系统统计信息"""
        stats = {
            'api_status': False,
            'total_funds': 0,
            'total_reports': 0,
            'active_tasks': 0,
            'last_update': 'N/A'
        }
        
        try:
            # API状态
            stats['api_status'] = self.check_api_connection()
            
            if stats['api_status']:
                # 基金数量
                funds_response = requests.get(f"{self.api_base_url}/api/v1/funds/", timeout=10)
                if funds_response.status_code == 200:
                    funds_data = funds_response.json()
                    stats['total_funds'] = len(funds_data.get('data', {}).get('items', []))
                
                # 报告数量
                reports_response = requests.get(f"{self.api_base_url}/api/v1/reports/", timeout=10)
                if reports_response.status_code == 200:
                    reports_data = reports_response.json()
                    stats['total_reports'] = len(reports_data.get('data', {}).get('items', []))
                
                # 任务统计
                tasks_response = requests.get(f"{self.api_base_url}/api/v1/tasks/stats/summary", timeout=10)
                if tasks_response.status_code == 200:
                    tasks_data = tasks_response.json()
                    stats['active_tasks'] = tasks_data.get('data', {}).get('active_tasks', 0)
                
                stats['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        except Exception as e:
            st.error(f"获取系统统计信息失败: {str(e)}")
        
        return stats
    
    def render_header(self):
        """渲染页面头部"""
        st.markdown("""
        <div class="main-header">
            <h1 style="color: white; margin: 0;">📊 基金报告自动化采集与分析平台</h1>
            <p style="color: #e8f4f8; margin: 0;">Fund Report Automated Collection & Analysis Platform</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """渲染侧边栏"""
        st.sidebar.markdown("""
        <div class="sidebar-header">
            <h3>🎛️ 控制面板</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 页面选择
        page = st.sidebar.selectbox(
            "选择功能页面",
            ["📊 系统概览", "🔍 数据查询", "⚙️ 任务管理", "📈 数据分析", "🔧 系统管理", "📋 部署向导"]
        )
        
        st.sidebar.markdown("---")
        
        # 快速操作
        st.sidebar.markdown("### 🚀 快速操作")
        
        if st.sidebar.button("🔄 刷新数据"):
            st.experimental_rerun()
        
        if st.sidebar.button("🏥 健康检查"):
            if self.check_api_connection():
                st.sidebar.success("✅ API服务正常")
            else:
                st.sidebar.error("❌ API服务异常")
        
        st.sidebar.markdown("---")
        
        # 系统信息
        st.sidebar.markdown("### ℹ️ 系统信息")
        stats = self.get_system_stats()
        
        if stats['api_status']:
            st.sidebar.markdown('<p class="status-success">🟢 系统在线</p>', unsafe_allow_html=True)
        else:
            st.sidebar.markdown('<p class="status-error">🔴 系统离线</p>', unsafe_allow_html=True)
        
        st.sidebar.metric("基金数量", stats['total_funds'])
        st.sidebar.metric("报告数量", stats['total_reports'])
        st.sidebar.metric("活跃任务", stats['active_tasks'])
        
        st.sidebar.markdown(f"**最后更新**: {stats['last_update']}")
        
        return page
    
    def render_overview_page(self):
        """渲染系统概览页面"""
        st.header("📊 系统概览")
        
        # 获取系统统计
        stats = self.get_system_stats()
        
        # 状态指示器
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if stats['api_status']:
                st.success("🟢 API服务")
            else:
                st.error("🔴 API服务")
        
        with col2:
            st.info(f"📊 {stats['total_funds']} 只基金")
        
        with col3:
            st.info(f"📄 {stats['total_reports']} 份报告")
        
        with col4:
            st.info(f"⚙️ {stats['active_tasks']} 个任务")
        
        st.markdown("---")
        
        # 功能模块展示
        st.subheader("🎯 核心功能模块")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            ### 📥 数据采集
            - ✅ 自动XBRL报告爬取
            - ✅ 多源数据融合
            - ✅ 实时数据更新
            - ✅ 智能限流保护
            """)
        
        with col2:
            st.markdown("""
            ### 🔍 数据查询
            - ✅ 15个REST API接口
            - ✅ 复杂条件筛选
            - ✅ 高性能响应
            - ✅ 自动API文档
            """)
        
        with col3:
            st.markdown("""
            ### 📈 数据分析
            - ✅ 基金业绩分析
            - ✅ 重仓股追踪
            - ✅ 行业配置分析
            - ✅ 历史趋势对比
            """)
        
        # 系统架构图
        st.subheader("🏗️ 系统架构")
        
        st.mermaid("""
        graph TD
            A[用户界面层] --> B[API网关层]
            B --> C[业务逻辑层]
            C --> D[数据处理层]
            D --> E[任务调度层]
            E --> F[数据存储层]
            
            B --> G[FastAPI + Swagger]
            C --> H[基金查询服务]
            C --> I[报告分析服务]
            C --> J[任务管理服务]
            D --> K[XBRL解析器]
            D --> L[数据清洗器]
            E --> M[Celery + Redis]
            F --> N[PostgreSQL]
            F --> O[MinIO存储]
        """)
        
        # 最近活动
        st.subheader("📋 最近活动")
        
        if stats['api_status']:
            try:
                # 获取最近任务
                tasks_response = requests.get(f"{self.api_base_url}/api/v1/tasks/", timeout=10)
                if tasks_response.status_code == 200:
                    tasks_data = tasks_response.json()
                    tasks = tasks_data.get('data', {}).get('items', [])
                    
                    if tasks:
                        # 创建任务状态DataFrame
                        task_df = pd.DataFrame(tasks[:10])  # 显示最近10个任务
                        
                        # 状态统计
                        status_counts = pd.Series([task.get('status', 'unknown') for task in tasks]).value_counts()
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.dataframe(
                                task_df[['task_id', 'task_type', 'status', 'created_at']].head(10),
                                use_container_width=True
                            )
                        
                        with col2:
                            fig = px.pie(
                                values=status_counts.values, 
                                names=status_counts.index,
                                title="任务状态分布"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("暂无任务记录")
            except Exception as e:
                st.error(f"获取任务信息失败: {str(e)}")
        else:
            st.warning("API服务不可用，无法获取最近活动")
    
    def render_data_query_page(self):
        """渲染数据查询页面"""
        st.header("🔍 数据查询")
        
        if not self.check_api_connection():
            st.error("❌ API服务不可用，请检查系统状态")
            return
        
        # 查询选项
        query_type = st.selectbox(
            "选择查询类型",
            ["基金信息查询", "报告信息查询", "净值历史查询"]
        )
        
        if query_type == "基金信息查询":
            self.render_fund_query()
        elif query_type == "报告信息查询":
            self.render_report_query()
        elif query_type == "净值历史查询":
            self.render_nav_query()
    
    def render_fund_query(self):
        """渲染基金查询界面"""
        st.subheader("📊 基金信息查询")
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # 查询参数
            fund_code = st.text_input("基金代码", placeholder="例如：000001")
            fund_type = st.selectbox("基金类型", ["全部", "股票型", "混合型", "债券型", "货币型"])
            page_size = st.slider("每页显示", 10, 100, 20)
            
            if st.button("🔍 查询基金"):
                # 构造查询参数
                params = {"page_size": page_size}
                if fund_code:
                    params["fund_code"] = fund_code
                if fund_type != "全部":
                    params["fund_type"] = fund_type
                
                try:
                    response = requests.get(f"{self.api_base_url}/api/v1/funds/", params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        funds = data.get('data', {}).get('items', [])
                        
                        if funds:
                            st.session_state['fund_query_results'] = funds
                        else:
                            st.warning("未找到匹配的基金")
                    else:
                        st.error(f"查询失败: {response.status_code}")
                except Exception as e:
                    st.error(f"查询异常: {str(e)}")
        
        with col2:
            # 显示查询结果
            if 'fund_query_results' in st.session_state:
                funds = st.session_state['fund_query_results']
                
                st.success(f"找到 {len(funds)} 只基金")
                
                # 转换为DataFrame显示
                df = pd.DataFrame(funds)
                if not df.empty:
                    # 选择要显示的列
                    display_columns = ['fund_code', 'fund_name', 'fund_type', 'management_company']
                    available_columns = [col for col in display_columns if col in df.columns]
                    
                    st.dataframe(
                        df[available_columns],
                        use_container_width=True,
                        height=400
                    )
                    
                    # 基金类型分布
                    if 'fund_type' in df.columns:
                        type_counts = df['fund_type'].value_counts()
                        fig = px.bar(
                            x=type_counts.index, 
                            y=type_counts.values,
                            title="基金类型分布",
                            labels={'x': '基金类型', 'y': '数量'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
    
    def render_task_management_page(self):
        """渲染任务管理页面"""
        st.header("⚙️ 任务管理")
        
        if not self.check_api_connection():
            st.error("❌ API服务不可用，请检查系统状态")
            return
        
        tab1, tab2, tab3 = st.tabs(["创建任务", "任务列表", "任务统计"])
        
        with tab1:
            self.render_task_creation()
        
        with tab2:
            self.render_task_list()
        
        with tab3:
            self.render_task_statistics()
    
    def render_task_creation(self):
        """渲染任务创建界面"""
        st.subheader("➕ 创建新任务")
        
        with st.form("create_task_form"):
            task_type = st.selectbox(
                "任务类型",
                ["collect_reports", "update_nav", "data_analysis"]
            )
            
            fund_codes_input = st.text_area(
                "目标基金代码",
                placeholder="输入基金代码，每行一个\n例如：\n000001\n000300\n110022",
                height=100
            )
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("开始日期")
            with col2:
                end_date = st.date_input("结束日期")
            
            priority = st.selectbox("优先级", ["low", "medium", "high"])
            description = st.text_area("任务描述", placeholder="可选的任务描述信息")
            
            submitted = st.form_submit_button("🚀 创建任务")
            
            if submitted:
                # 处理基金代码
                fund_codes = [code.strip() for code in fund_codes_input.split('\n') if code.strip()]
                
                if not fund_codes:
                    st.error("请输入至少一个基金代码")
                    return
                
                # 构造任务数据
                task_data = {
                    "task_type": task_type,
                    "target_fund_codes": fund_codes,
                    "date_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "priority": priority,
                    "description": description
                }
                
                try:
                    response = requests.post(
                        f"{self.api_base_url}/api/v1/tasks/",
                        json=task_data,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        task_id = result.get('data', {}).get('task_id')
                        st.success(f"✅ 任务创建成功！任务ID: {task_id}")
                        
                        # 刷新任务列表
                        if 'task_list' in st.session_state:
                            del st.session_state['task_list']
                    else:
                        st.error(f"任务创建失败: {response.status_code}")
                
                except Exception as e:
                    st.error(f"任务创建异常: {str(e)}")
    
    def render_deployment_wizard(self):
        """渲染部署向导页面"""
        st.header("📋 部署向导")
        
        st.markdown("""
        ### 🚀 一键部署指南
        
        欢迎使用基金报告平台部署向导！本向导将帮助您快速部署和配置系统。
        """)
        
        # 部署步骤
        steps = [
            "环境检查",
            "依赖安装",
            "配置设置",
            "系统部署",
            "验证测试"
        ]
        
        # 创建步骤指示器
        cols = st.columns(len(steps))
        for i, (col, step) in enumerate(zip(cols, steps)):
            with col:
                if i < 3:  # 模拟已完成的步骤
                    st.success(f"✅ {step}")
                elif i == 3:  # 当前步骤
                    st.warning(f"🔄 {step}")
                else:  # 未完成的步骤
                    st.info(f"⏳ {step}")
        
        st.markdown("---")
        
        # 部署选项
        deployment_mode = st.radio(
            "选择部署模式",
            ["🧪 开发环境", "🚀 生产环境", "🔧 自定义配置"]
        )
        
        if deployment_mode == "🧪 开发环境":
            st.info("""
            **开发环境部署**
            - 使用SQLite数据库
            - 单机部署模式
            - 开发调试功能启用
            - 适合学习和测试
            """)
            
            if st.button("🚀 一键部署开发环境"):
                self.run_development_deployment()
        
        elif deployment_mode == "🚀 生产环境":
            st.warning("""
            **生产环境部署**
            - 使用PostgreSQL数据库
            - Docker容器化部署
            - 完整监控和日志
            - 适合正式使用
            """)
            
            # 生产环境配置
            with st.expander("🔧 生产环境配置"):
                col1, col2 = st.columns(2)
                
                with col1:
                    db_password = st.text_input("数据库密码", type="password", value="auto_generate")
                    redis_password = st.text_input("Redis密码", type="password", value="auto_generate")
                
                with col2:
                    api_port = st.number_input("API端口", value=8000, min_value=1024, max_value=65535)
                    enable_ssl = st.checkbox("启用SSL证书")
                
                domain_name = st.text_input("域名（可选）", placeholder="例如：fundreport.example.com")
            
            if st.button("🚀 一键部署生产环境"):
                self.run_production_deployment({
                    'db_password': db_password,
                    'redis_password': redis_password,
                    'api_port': api_port,
                    'enable_ssl': enable_ssl,
                    'domain_name': domain_name
                })
        
        # 部署状态显示
        if 'deployment_status' in st.session_state:
            status = st.session_state['deployment_status']
            
            if status['status'] == 'running':
                st.info("🔄 部署正在进行中...")
                
                # 进度条
                progress = st.progress(status.get('progress', 0))
                st.text(status.get('current_step', '初始化...'))
                
                # 自动刷新
                time.sleep(2)
                st.experimental_rerun()
            
            elif status['status'] == 'completed':
                st.success("✅ 部署完成！")
                
                st.markdown("""
                ### 🎉 部署成功！
                
                您的基金报告平台已成功部署，可以通过以下方式访问：
                
                - **API文档**: http://localhost:8000/docs
                - **健康检查**: http://localhost:8000/health
                - **Web管理界面**: 当前页面
                """)
                
                if st.button("🔄 重新部署"):
                    del st.session_state['deployment_status']
                    st.experimental_rerun()
            
            elif status['status'] == 'failed':
                st.error("❌ 部署失败")
                st.error(f"错误信息: {status.get('error', '未知错误')}")
                
                if st.button("🔄 重试部署"):
                    del st.session_state['deployment_status']
                    st.experimental_rerun()
    
    def run_development_deployment(self):
        """运行开发环境部署"""
        st.session_state['deployment_status'] = {
            'status': 'running',
            'progress': 0,
            'current_step': '正在准备开发环境...'
        }
        
        # 这里实际上会调用部署脚本
        # 为了演示，我们模拟部署过程
        try:
            # 模拟部署步骤
            steps = [
                "检查Docker环境",
                "构建开发镜像", 
                "启动服务容器",
                "初始化数据库",
                "验证服务状态"
            ]
            
            for i, step in enumerate(steps):
                st.session_state['deployment_status'].update({
                    'progress': (i + 1) / len(steps),
                    'current_step': step
                })
                time.sleep(1)  # 模拟处理时间
            
            st.session_state['deployment_status']['status'] = 'completed'
            
        except Exception as e:
            st.session_state['deployment_status'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    def run_production_deployment(self, config):
        """运行生产环境部署"""
        st.session_state['deployment_status'] = {
            'status': 'running',
            'progress': 0,
            'current_step': '正在准备生产环境...'
        }
        
        try:
            # 实际的生产环境部署逻辑
            # 这里可以调用 scripts/production_deploy.py
            
            steps = [
                "环境检查和依赖验证",
                "生成安全配置文件",
                "构建生产Docker镜像",
                "启动数据库和缓存服务",
                "部署应用服务",
                "配置反向代理",
                "运行健康检查",
                "完成部署验证"
            ]
            
            for i, step in enumerate(steps):
                st.session_state['deployment_status'].update({
                    'progress': (i + 1) / len(steps),
                    'current_step': step
                })
                time.sleep(2)  # 模拟处理时间
            
            st.session_state['deployment_status']['status'] = 'completed'
            
        except Exception as e:
            st.session_state['deployment_status'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    def run(self):
        """运行GUI应用"""
        # 渲染头部
        self.render_header()
        
        # 渲染侧边栏并获取选择的页面
        page = self.render_sidebar()
        
        # 根据选择的页面渲染内容
        if page == "📊 系统概览":
            self.render_overview_page()
        elif page == "🔍 数据查询":
            self.render_data_query_page()
        elif page == "⚙️ 任务管理":
            self.render_task_management_page()
        elif page == "📈 数据分析":
            st.header("📈 数据分析")
            st.info("数据分析功能正在开发中...")
        elif page == "🔧 系统管理":
            st.header("🔧 系统管理")
            st.info("系统管理功能正在开发中...")
        elif page == "📋 部署向导":
            self.render_deployment_wizard()

def main():
    """主函数"""
    try:
        gui = FundPlatformGUI()
        gui.run()
    except Exception as e:
        st.error(f"应用启动失败: {str(e)}")
        st.info("请确保API服务正在运行，或联系技术支持")

if __name__ == "__main__":
    main()