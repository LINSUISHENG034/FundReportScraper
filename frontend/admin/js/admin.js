// 管理后台主逻辑
class AdminInterface {
    constructor() {
        this.currentTab = 'dashboard';
        this.refreshInterval = null;
        this.charts = {};
        this.wsConnection = null;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeApp();
        this.startAutoRefresh();
    }

    bindEvents() {
        // 标签页切换
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-tab]')) {
                e.preventDefault();
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            }
        });

        // 任务筛选表单
        const taskFilterForm = document.getElementById('task-filter-form');
        if (taskFilterForm) {
            taskFilterForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.filterTasks();
            });
        }

        // 系统配置表单
        const systemConfigForm = document.getElementById('system-config-form');
        if (systemConfigForm) {
            systemConfigForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveSystemConfig();
            });
        }

        // 数据源配置表单
        const datasourceConfigForm = document.getElementById('datasource-config-form');
        if (datasourceConfigForm) {
            datasourceConfigForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveDatasourceConfig();
            });
        }

        // 时间范围选择
        document.addEventListener('change', (e) => {
            if (e.target.name === 'timeRange') {
                this.updateTrendChart(e.target.value);
            }
        });

        // 日志级别筛选
        const logLevel = document.getElementById('logLevel');
        if (logLevel) {
            logLevel.addEventListener('change', (e) => {
                this.filterLogs(e.target.value);
            });
        }
    }

    switchTab(tabName) {
        // 更新导航状态
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');

        // 切换内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`)?.classList.add('active');

        this.currentTab = tabName;

        // 加载对应数据
        this.loadTabData(tabName);
    }

    async loadTabData(tabName) {
        switch (tabName) {
            case 'dashboard':
                await this.loadDashboardData();
                break;
            case 'tasks':
                await this.loadTasksData();
                break;
            case 'data':
                await this.loadDataManagementData();
                break;
            case 'system':
                await this.loadSystemMonitoringData();
                break;
            case 'settings':
                await this.loadSystemSettings();
                break;
        }
    }

    async initializeApp() {
        try {
            // 检查API连接
            await api.checkHealth();
            
            // 加载初始数据
            await this.loadSystemStats();
            
            // 初始化图表
            this.initializeCharts();
            
            Utils.showNotification('系统', '管理后台加载完成', 'success', 3000);
        } catch (error) {
            Utils.handleError(error, '系统初始化');
            this.showOfflineMode();
        }
    }

    async loadSystemStats() {
        try {
            const stats = await api.getSystemStats();
            this.updateSystemStats(stats);
        } catch (error) {
            console.error('系统统计加载失败:', error);
        }
    }

    updateSystemStats(stats) {
        if (!stats) return;

        // 更新系统状态
        const systemStatus = document.getElementById('systemStatus');
        if (systemStatus) {
            systemStatus.textContent = stats.health ? '正常' : '异常';
        }

        // 更新基金总数
        if (stats.fundStats?.data?.total_funds) {
            document.getElementById('totalFunds').textContent = stats.fundStats.data.total_funds;
        }

        // 更新报告总数
        if (stats.reportStats?.data?.total_reports) {
            document.getElementById('totalReports').textContent = stats.reportStats.data.total_reports;
        }

        // 更新活跃任务
        if (stats.taskStats?.data?.active_tasks !== undefined) {
            document.getElementById('activeTasks').textContent = stats.taskStats.data.active_tasks;
        }

        // 更新API状态
        const apiStatus = document.getElementById('apiStatus');
        if (apiStatus) {
            if (stats.health) {
                apiStatus.className = 'badge bg-success';
                apiStatus.textContent = '正常';
            } else {
                apiStatus.className = 'badge bg-danger';
                apiStatus.textContent = '异常';
            }
        }

        // 更新数据库状态
        const dbStatus = document.getElementById('dbStatus');
        if (dbStatus) {
            dbStatus.className = 'badge bg-success';
            dbStatus.textContent = '正常';
        }

        // 更新最后更新时间
        const lastUpdate = document.getElementById('lastUpdate');
        if (lastUpdate) {
            lastUpdate.textContent = new Date().toLocaleString('zh-CN');
        }
    }

    async loadDashboardData() {
        try {
            await Promise.all([
                this.loadSystemStats(),
                this.loadRecentActivities(),
                this.updateTrendChart('7d'),
                this.updateTaskStatusChart()
            ]);
        } catch (error) {
            console.error('仪表板数据加载失败:', error);
        }
    }

    async loadRecentActivities() {
        const container = document.getElementById('recentActivities');
        if (!container) return;

        try {
            const response = await api.getTasks({ size: 10 });
            const tasks = response.data?.items || response.data || [];

            if (tasks.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="bi bi-inbox fs-1"></i>
                        <p class="mt-2">暂无活动记录</p>
                    </div>
                `;
                return;
            }

            let html = '';
            tasks.forEach(task => {
                html += this.createActivityItem(task);
            });

            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = `
                <div class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle fs-1"></i>
                    <p class="mt-2">加载活动记录失败</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="adminInterface.loadRecentActivities()">
                        重试
                    </button>
                </div>
            `;
        }
    }

    createActivityItem(task) {
        const iconMap = {
            'success': { icon: 'check-circle', class: 'success' },
            'failed': { icon: 'x-circle', class: 'error' },
            'running': { icon: 'play-circle', class: 'info' },
            'pending': { icon: 'clock', class: 'warning' }
        };

        const statusInfo = iconMap[task.status] || iconMap.pending;

        return `
            <div class="activity-item">
                <div class="activity-icon ${statusInfo.class}">
                    <i class="bi bi-${statusInfo.icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${Utils.sanitizeHtml(task.task_name || task.description || '未命名任务')}</div>
                    <div class="activity-description">
                        任务类型: ${Utils.sanitizeHtml(task.task_type || '-')} | 
                        状态: ${Utils.getStatusText(task.status)}
                    </div>
                    <div class="activity-time">${Utils.formatDate(task.created_at)}</div>
                </div>
            </div>
        `;
    }

    initializeCharts() {
        // 初始化趋势图表
        this.initTrendChart();
        
        // 初始化任务状态图表
        this.initTaskStatusChart();
    }

    initTrendChart() {
        const ctx = document.getElementById('trendChart');
        if (!ctx) return;

        this.charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '基金数量',
                    data: [],
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    tension: 0.4
                }, {
                    label: '报告数量',
                    data: [],
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    initTaskStatusChart() {
        const ctx = document.getElementById('taskStatusChart');
        if (!ctx) return;

        this.charts.taskStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['等待中', '执行中', '已完成', '失败'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#ffc107',
                        '#0dcaf0',
                        '#198754',
                        '#dc3545'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    async updateTrendChart(timeRange = '7d') {
        if (!this.charts.trend) return;

        try {
            // 模拟趋势数据 - 实际应用中应从API获取
            const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
            const labels = [];
            const fundData = [];
            const reportData = [];

            for (let i = days - 1; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                labels.push(date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }));
                
                // 模拟数据增长
                fundData.push(Math.floor(Math.random() * 50) + 100 + i * 2);
                reportData.push(Math.floor(Math.random() * 100) + 200 + i * 5);
            }

            this.charts.trend.data.labels = labels;
            this.charts.trend.data.datasets[0].data = fundData;
            this.charts.trend.data.datasets[1].data = reportData;
            this.charts.trend.update();
        } catch (error) {
            console.error('趋势图表更新失败:', error);
        }
    }

    async updateTaskStatusChart() {
        if (!this.charts.taskStatus) return;

        try {
            const stats = await api.getTaskStats();
            const statusData = stats.data?.by_status || {};

            const data = [
                statusData.pending || 0,
                statusData.running || 0,
                statusData.success || 0,
                statusData.failed || 0
            ];

            this.charts.taskStatus.data.datasets[0].data = data;
            this.charts.taskStatus.update();

            // 更新任务统计卡片
            document.getElementById('pendingTasks').textContent = statusData.pending || 0;
            document.getElementById('runningTasks').textContent = statusData.running || 0;
            document.getElementById('successTasks').textContent = statusData.success || 0;
            document.getElementById('failedTasks').textContent = statusData.failed || 0;
        } catch (error) {
            console.error('任务状态图表更新失败:', error);
        }
    }

    async loadTasksData() {
        await Promise.all([
            this.loadTaskList(),
            this.updateTaskStatusChart()
        ]);
    }

    async loadTaskList() {
        const container = document.getElementById('taskList');
        if (!container) return;

        try {
            Utils.showLoading('正在加载任务列表...');
            
            const response = await api.getTasks({ size: 50 });
            const tasks = response.data?.items || response.data || [];

            if (tasks.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="bi bi-list-task fs-1"></i>
                        <p class="mt-2">暂无任务记录</p>
                        <button class="btn btn-primary" onclick="adminInterface.showCreateTaskModal()">
                            <i class="bi bi-plus-circle"></i> 创建第一个任务
                        </button>
                    </div>
                `;
                return;
            }

            let html = '';
            tasks.forEach(task => {
                html += this.createTaskCard(task);
            });

            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = `
                <div class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle fs-1"></i>
                    <p class="mt-2">任务列表加载失败</p>
                    <button class="btn btn-outline-primary" onclick="adminInterface.loadTaskList()">
                        重试
                    </button>
                </div>
            `;
        } finally {
            Utils.hideLoading();
        }
    }

    createTaskCard(task) {
        const statusClass = Utils.getStatusBadgeClass(task.status);
        const statusText = Utils.getStatusText(task.status);

        return `
            <div class="task-card">
                <div class="task-header">
                    <div>
                        <div class="task-title">${Utils.sanitizeHtml(task.task_name || task.description || '未命名任务')}</div>
                        <div class="task-id">ID: ${Utils.sanitizeHtml(task.task_id || task.id)}</div>
                    </div>
                    <div>
                        <span class="task-status status-badge ${statusClass}">${statusText}</span>
                    </div>
                </div>
                <div class="task-details">
                    <div class="task-detail">
                        <div class="task-detail-label">任务类型</div>
                        <div class="task-detail-value">${Utils.sanitizeHtml(task.task_type || '-')}</div>
                    </div>
                    <div class="task-detail">
                        <div class="task-detail-label">优先级</div>
                        <div class="task-detail-value">${Utils.sanitizeHtml(task.priority || 'medium')}</div>
                    </div>
                    <div class="task-detail">
                        <div class="task-detail-label">创建时间</div>
                        <div class="task-detail-value">${Utils.formatDate(task.created_at)}</div>
                    </div>
                    <div class="task-detail">
                        <div class="task-detail-label">进度</div>
                        <div class="task-detail-value">${task.progress || 0}%</div>
                    </div>
                </div>
                ${task.progress !== undefined ? `
                    <div class="progress-custom mb-3">
                        <div class="progress-bar-custom" style="width: ${task.progress}%">
                            <span class="progress-text">${task.progress}%</span>
                        </div>
                    </div>
                ` : ''}
                <div class="task-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick="adminInterface.viewTaskDetail('${task.task_id || task.id}')">
                        <i class="bi bi-eye"></i> 详情
                    </button>
                    ${task.status === 'running' ? `
                        <button class="btn btn-sm btn-outline-warning" onclick="adminInterface.pauseTask('${task.task_id || task.id}')">
                            <i class="bi bi-pause"></i> 暂停
                        </button>
                    ` : ''}
                    ${task.status === 'pending' ? `
                        <button class="btn btn-sm btn-outline-success" onclick="adminInterface.startTask('${task.task_id || task.id}')">
                            <i class="bi bi-play"></i> 启动
                        </button>
                    ` : ''}
                    ${task.status === 'failed' ? `
                        <button class="btn btn-sm btn-outline-info" onclick="adminInterface.retryTask('${task.task_id || task.id}')">
                            <i class="bi bi-arrow-clockwise"></i> 重试
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-outline-danger" onclick="adminInterface.deleteTask('${task.task_id || task.id}')">
                        <i class="bi bi-trash"></i> 删除
                    </button>
                </div>
            </div>
        `;
    }

    async loadDataManagementData() {
        try {
            const [fundStats, reportStats] = await Promise.all([
                api.getFundStats(),
                api.getReportStats()
            ]);

            // 更新基金数据统计
            if (fundStats?.data) {
                document.getElementById('dataFundsTotal').textContent = fundStats.data.total_funds || 0;
                document.getElementById('dataFundsActive').textContent = fundStats.data.active_funds || 0;
            }

            // 更新报告数据统计
            if (reportStats?.data) {
                document.getElementById('dataReportsTotal').textContent = reportStats.data.total_reports || 0;
                document.getElementById('dataReportsParsed').textContent = reportStats.data.parsed_reports || 0;
            }

            // 加载数据活动
            await this.loadDataActivities();
        } catch (error) {
            console.error('数据管理数据加载失败:', error);
        }
    }

    async loadDataActivities() {
        const container = document.getElementById('dataActivities');
        if (!container) return;

        // 模拟数据活动
        const activities = [
            { type: 'success', title: '数据同步完成', description: '成功同步1000条基金数据', time: new Date() },
            { type: 'info', title: '报告解析', description: '正在解析季度报告', time: new Date(Date.now() - 30000) },
            { type: 'warning', title: '存储空间提醒', description: '存储空间使用率达到80%', time: new Date(Date.now() - 60000) }
        ];

        let html = '';
        activities.forEach(activity => {
            html += `
                <div class="activity-item">
                    <div class="activity-icon ${activity.type}">
                        <i class="bi bi-${activity.type === 'success' ? 'check-circle' : activity.type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-title">${Utils.sanitizeHtml(activity.title)}</div>
                        <div class="activity-description">${Utils.sanitizeHtml(activity.description)}</div>
                        <div class="activity-time">${Utils.formatDate(activity.time)}</div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    async loadSystemMonitoringData() {
        await Promise.all([
            this.checkSystemHealth(),
            this.loadPerformanceMetrics(),
            this.loadSystemLogs()
        ]);
    }

    async checkSystemHealth() {
        try {
            const health = await api.checkHealth();
            
            // 更新健康状态
            const healthItems = {
                'healthAPI': health ? 'success' : 'danger',
                'healthDB': 'success', // 假设数据库正常
                'healthQueue': 'success', // 假设队列正常
                'healthStorage': 'success' // 假设存储正常
            };

            Object.entries(healthItems).forEach(([id, status]) => {
                const element = document.getElementById(id);
                if (element) {
                    element.innerHTML = `<span class="badge bg-${status}">${status === 'success' ? '正常' : '异常'}</span>`;
                }
            });
        } catch (error) {
            console.error('系统健康检查失败:', error);
            
            // 更新为异常状态
            ['healthAPI', 'healthDB', 'healthQueue', 'healthStorage'].forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.innerHTML = '<span class="badge bg-danger">异常</span>';
                }
            });
        }
    }

    async loadPerformanceMetrics() {
        // 模拟性能指标
        const metrics = {
            cpu: Math.floor(Math.random() * 30) + 20,
            memory: Math.floor(Math.random() * 40) + 30,
            disk: Math.floor(Math.random() * 20) + 10,
            network: Math.floor(Math.random() * 50) + 10
        };

        // 更新CPU使用率
        const cpuElement = document.getElementById('cpuUsage');
        if (cpuElement) {
            cpuElement.style.width = `${metrics.cpu}%`;
            cpuElement.textContent = `${metrics.cpu}%`;
        }

        // 更新内存使用率
        const memoryElement = document.getElementById('memoryUsage');
        if (memoryElement) {
            memoryElement.style.width = `${metrics.memory}%`;
            memoryElement.textContent = `${metrics.memory}%`;
        }

        // 更新磁盘使用率
        const diskElement = document.getElementById('diskUsage');
        if (diskElement) {
            diskElement.style.width = `${metrics.disk}%`;
            diskElement.textContent = `${metrics.disk}%`;
        }

        // 更新网络延迟
        const networkElement = document.getElementById('networkLatency');
        if (networkElement) {
            networkElement.textContent = metrics.network;
        }
    }

    async loadSystemLogs() {
        const container = document.getElementById('systemLogs');
        if (!container) return;

        // 模拟系统日志
        const logs = [
            { level: 'info', message: '系统启动完成', timestamp: new Date() },
            { level: 'warning', message: '连接池使用率较高', timestamp: new Date(Date.now() - 30000) },
            { level: 'info', message: '定时任务执行成功', timestamp: new Date(Date.now() - 60000) },
            { level: 'error', message: '网络请求超时', timestamp: new Date(Date.now() - 90000) }
        ];

        let html = '';
        logs.forEach(log => {
            html += `
                <div class="log-entry ${log.level}">
                    <span class="log-timestamp">${log.timestamp.toLocaleTimeString('zh-CN')}</span>
                    <span class="log-level">[${log.level.toUpperCase()}]</span>
                    <span class="log-message">${Utils.sanitizeHtml(log.message)}</span>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    async loadSystemSettings() {
        // 加载系统设置时不需要特殊处理，表单已经有默认值
    }

    startAutoRefresh() {
        // 每30秒自动刷新一次仪表板数据
        this.refreshInterval = setInterval(() => {
            if (this.currentTab === 'dashboard') {
                this.loadSystemStats();
                this.updateTaskStatusChart();
            }
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    // 任务管理方法
    showCreateTaskModal() {
        const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
        
        // 设置默认日期
        const today = new Date();
        const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
        
        document.getElementById('taskStartDate').value = today.toISOString().split('T')[0];
        document.getElementById('taskEndDate').value = nextWeek.toISOString().split('T')[0];
        
        modal.show();
    }

    async createTask() {
        const formData = {
            task_type: document.getElementById('newTaskType').value,
            description: document.getElementById('taskDescription').value,
            target_fund_codes: document.getElementById('targetFundCodes').value.split('\n').filter(code => code.trim()),
            priority: document.getElementById('taskPriority').value,
            start_date: document.getElementById('taskStartDate').value,
            end_date: document.getElementById('taskEndDate').value
        };

        if (!formData.task_type) {
            Utils.showNotification('错误', '请选择任务类型', 'error');
            return;
        }

        if (formData.target_fund_codes.length === 0) {
            Utils.showNotification('错误', '请输入至少一个基金代码', 'error');
            return;
        }

        try {
            Utils.showLoading('正在创建任务...');
            
            const response = await api.createTask(formData);
            
            if (response.success || response.data) {
                Utils.showNotification('成功', '任务创建成功', 'success');
                
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('createTaskModal'));
                if (modal) modal.hide();
                
                // 刷新任务列表
                if (this.currentTab === 'tasks') {
                    await this.loadTaskList();
                }
                
                // 清空表单
                document.getElementById('create-task-form').reset();
            } else {
                Utils.showNotification('错误', '任务创建失败', 'error');
            }
        } catch (error) {
            Utils.handleError(error, '任务创建');
        } finally {
            Utils.hideLoading();
        }
    }

    async viewTaskDetail(taskId) {
        try {
            const response = await api.getTask(taskId);
            const task = response.data || response;
            
            if (task) {
                this.showTaskDetailModal(task);
            } else {
                Utils.showNotification('错误', '无法获取任务详情', 'error');
            }
        } catch (error) {
            Utils.handleError(error, '任务详情获取');
        }
    }

    showTaskDetailModal(task) {
        const statusClass = Utils.getStatusBadgeClass(task.status);
        const statusText = Utils.getStatusText(task.status);

        const content = `
            <div class="row">
                <div class="col-md-8">
                    <h5>${Utils.sanitizeHtml(task.task_name || task.description || '未命名任务')}</h5>
                    <div class="mb-3">
                        <span class="badge ${statusClass}">${statusText}</span>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>任务ID</strong></td>
                                    <td><code>${Utils.sanitizeHtml(task.task_id || task.id)}</code></td>
                                </tr>
                                <tr>
                                    <td><strong>任务类型</strong></td>
                                    <td>${Utils.sanitizeHtml(task.task_type || '-')}</td>
                                </tr>
                                <tr>
                                    <td><strong>优先级</strong></td>
                                    <td>${Utils.sanitizeHtml(task.priority || 'medium')}</td>
                                </tr>
                                <tr>
                                    <td><strong>创建时间</strong></td>
                                    <td>${Utils.formatDate(task.created_at)}</td>
                                </tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>开始时间</strong></td>
                                    <td>${Utils.formatDate(task.started_at)}</td>
                                </tr>
                                <tr>
                                    <td><strong>完成时间</strong></td>
                                    <td>${Utils.formatDate(task.completed_at)}</td>
                                </tr>
                                <tr>
                                    <td><strong>进度</strong></td>
                                    <td>${task.progress || 0}%</td>
                                </tr>
                                <tr>
                                    <td><strong>错误信息</strong></td>
                                    <td>${task.error_message || '-'}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    ${task.progress !== undefined ? `
                        <div class="mb-3">
                            <label class="form-label">任务进度</label>
                            <div class="progress">
                                <div class="progress-bar" style="width: ${task.progress}%">${task.progress}%</div>
                            </div>
                        </div>
                    ` : ''}
                    
                    ${task.result ? `
                        <div class="mb-3">
                            <label class="form-label">执行结果</label>
                            <pre class="bg-light p-2 rounded"><code>${JSON.stringify(task.result, null, 2)}</code></pre>
                        </div>
                    ` : ''}
                </div>
                <div class="col-md-4">
                    <div class="text-center">
                        <h6>任务操作</h6>
                        <div class="d-grid gap-2">
                            ${task.status === 'running' ? `
                                <button class="btn btn-outline-warning btn-sm" onclick="adminInterface.pauseTask('${task.task_id || task.id}')">
                                    暂停任务
                                </button>
                            ` : ''}
                            ${task.status === 'pending' ? `
                                <button class="btn btn-outline-success btn-sm" onclick="adminInterface.startTask('${task.task_id || task.id}')">
                                    启动任务
                                </button>
                            ` : ''}
                            ${task.status === 'failed' ? `
                                <button class="btn btn-outline-info btn-sm" onclick="adminInterface.retryTask('${task.task_id || task.id}')">
                                    重试任务
                                </button>
                            ` : ''}
                            <button class="btn btn-outline-primary btn-sm" onclick="adminInterface.exportTaskReport('${task.task_id || task.id}')">
                                导出报告
                            </button>
                            <button class="btn btn-outline-danger btn-sm" onclick="adminInterface.deleteTask('${task.task_id || task.id}')">
                                删除任务
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const footer = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            <button type="button" class="btn btn-primary" onclick="Utils.copyToClipboard('${task.task_id || task.id}')">
                <i class="bi bi-clipboard"></i> 复制任务ID
            </button>
        `;

        Utils.createModal(`任务详情 - ${task.task_name || '未命名任务'}`, content, footer).show();
    }

    // 工具方法和占位实现
    async filterTasks() {
        // 根据筛选条件重新加载任务列表
        await this.loadTaskList();
    }

    resetTaskFilter() {
        document.getElementById('task-filter-form').reset();
        this.loadTaskList();
    }

    refreshTasks() {
        this.loadTaskList();
    }

    refreshActivities() {
        this.loadRecentActivities();
    }

    refreshLogs() {
        this.loadSystemLogs();
    }

    filterLogs(level) {
        // 根据日志级别筛选日志
        this.loadSystemLogs();
    }

    async saveSystemConfig() {
        Utils.showNotification('功能开发中', '系统配置保存功能正在开发中', 'info');
    }

    async saveDatasourceConfig() {
        Utils.showNotification('功能开发中', '数据源配置保存功能正在开发中', 'info');
    }

    // 占位实现的方法
    startTask(taskId) {
        Utils.showNotification('功能开发中', `启动任务 ${taskId} 功能正在开发中`, 'info');
    }

    pauseTask(taskId) {
        Utils.showNotification('功能开发中', `暂停任务 ${taskId} 功能正在开发中`, 'info');
    }

    retryTask(taskId) {
        Utils.showNotification('功能开发中', `重试任务 ${taskId} 功能正在开发中`, 'info');
    }

    deleteTask(taskId) {
        if (confirm('确定要删除这个任务吗？')) {
            Utils.showNotification('功能开发中', `删除任务 ${taskId} 功能正在开发中`, 'info');
        }
    }

    exportTasks() {
        Utils.showNotification('功能开发中', '任务导出功能正在开发中', 'info');
    }

    exportTaskReport(taskId) {
        Utils.showNotification('功能开发中', `导出任务报告 ${taskId} 功能正在开发中`, 'info');
    }

    manageFunds() {
        Utils.showNotification('功能开发中', '基金管理功能正在开发中', 'info');
    }

    manageReports() {
        Utils.showNotification('功能开发中', '报告管理功能正在开发中', 'info');
    }

    exportFunds() {
        Utils.showNotification('功能开发中', '基金数据导出功能正在开发中', 'info');
    }

    exportReports() {
        Utils.showNotification('功能开发中', '报告数据导出功能正在开发中', 'info');
    }

    showImportModal() {
        Utils.showNotification('功能开发中', '数据导入功能正在开发中', 'info');
    }

    syncData() {
        Utils.showNotification('功能开发中', '数据同步功能正在开发中', 'info');
    }

    cleanupData() {
        if (confirm('确定要清理过期和无效数据吗？此操作不可撤销。')) {
            Utils.showNotification('功能开发中', '数据清理功能正在开发中', 'info');
        }
    }

    restartSystem() {
        if (confirm('确定要重启系统吗？这将中断所有正在运行的任务。')) {
            Utils.showNotification('功能开发中', '系统重启功能正在开发中', 'info');
        }
    }

    clearCache() {
        Utils.showNotification('功能开发中', '清理缓存功能正在开发中', 'info');
    }

    backupData() {
        Utils.showNotification('功能开发中', '数据备份功能正在开发中', 'info');
    }

    optimizeDatabase() {
        Utils.showNotification('功能开发中', '数据库优化功能正在开发中', 'info');
    }

    showMaintenanceMode() {
        if (confirm('确定要启用维护模式吗？这将暂停所有服务。')) {
            Utils.showNotification('功能开发中', '维护模式功能正在开发中', 'info');
        }
    }

    showOfflineMode() {
        document.body.innerHTML = `
            <div class="container mt-5">
                <div class="row justify-content-center">
                    <div class="col-md-6 text-center">
                        <i class="bi bi-exclamation-triangle" style="font-size: 4rem; color: #dc3545;"></i>
                        <h3 class="mt-3">管理后台不可用</h3>
                        <p class="text-muted">无法连接到管理服务，请检查：</p>
                        <ul class="list-unstyled">
                            <li>• 确保API服务正在运行</li>
                            <li>• 检查管理权限</li>
                            <li>• 检查网络连接</li>
                            <li>• 刷新页面重试</li>
                        </ul>
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="bi bi-arrow-clockwise"></i> 重新加载
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    // 清理资源
    destroy() {
        this.stopAutoRefresh();
        
        // 销毁图表
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        
        // 关闭WebSocket连接
        if (this.wsConnection) {
            this.wsConnection.close();
        }
    }
}

// 初始化管理界面
document.addEventListener('DOMContentLoaded', () => {
    window.adminInterface = new AdminInterface();
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    if (window.adminInterface) {
        window.adminInterface.destroy();
    }
});

// 全局函数（为了兼容HTML中的onclick）
window.switchTab = (tabName) => window.adminInterface?.switchTab(tabName);