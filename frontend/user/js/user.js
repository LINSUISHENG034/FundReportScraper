// 用户界面主逻辑
class UserInterface {
    constructor() {
        this.currentTab = 'search';
        this.currentPage = 1;
        this.pageSize = 20;
        this.searchResults = [];
        this.reportResults = [];
        this.statsData = {};
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeApp();
        this.loadInitialData();
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

        // 基金搜索表单
        const fundSearchForm = document.getElementById('fund-search-form');
        if (fundSearchForm) {
            fundSearchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.searchFunds();
            });
        }

        // 报告搜索表单
        const reportSearchForm = document.getElementById('report-search-form');
        if (reportSearchForm) {
            reportSearchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.searchReports();
            });
        }

        // 自定义导出表单
        const customExportForm = document.getElementById('custom-export-form');
        if (customExportForm) {
            customExportForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.executeCustomExport();
            });
        }

        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                document.getElementById('fundCode')?.focus();
            }
        });

        // 防抖搜索
        const fundCodeInput = document.getElementById('fundCode');
        if (fundCodeInput) {
            fundCodeInput.addEventListener('input', Utils.debounce((e) => {
                if (Utils.isValidFundCode(e.target.value)) {
                    this.quickFundLookup(e.target.value);
                }
            }, 500));
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
            case 'search':
                // 搜索页面不需要预加载数据
                break;
            case 'reports':
                // 预加载最近报告
                break;
            case 'data':
                await this.loadDataCenterStats();
                await this.loadMyData();
                break;
            case 'tools':
                await this.checkSystemHealth();
                break;
        }
    }

    async initializeApp() {
        try {
            // 检查API连接
            await api.checkHealth();
            
            // 设置默认日期
            this.setDefaultDates();
            
            // 初始化组件
            this.initializeComponents();
            
            Utils.showNotification('系统', '基金报告平台加载完成', 'success', 3000);
        } catch (error) {
            Utils.handleError(error, '系统初始化');
            this.showOfflineMode();
        }
    }

    setDefaultDates() {
        const today = new Date();
        const lastYear = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
        const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());

        // 设置导出日期范围
        const exportStartDate = document.getElementById('exportStartDate');
        const exportEndDate = document.getElementById('exportEndDate');
        if (exportStartDate) exportStartDate.value = lastMonth.toISOString().split('T')[0];
        if (exportEndDate) exportEndDate.value = today.toISOString().split('T')[0];
    }

    initializeComponents() {
        // 初始化工具提示
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
            new bootstrap.Tooltip(el);
        });

        // 初始化弹出框
        document.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => {
            new bootstrap.Popover(el);
        });
    }

    async loadInitialData() {
        try {
            await this.loadSystemStats();
        } catch (error) {
            console.warn('初始数据加载失败:', error);
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

        // 更新基金总数
        if (stats.fundStats?.data?.total_funds) {
            document.getElementById('totalFunds').textContent = stats.fundStats.data.total_funds;
        }

        // 更新报告总数
        if (stats.reportStats?.data?.total_reports) {
            document.getElementById('totalReports').textContent = stats.reportStats.data.total_reports;
        }

        // 更新最新数据日期
        if (stats.reportStats?.data?.latest_report_date) {
            document.getElementById('latestDate').textContent = Utils.formatDate(stats.reportStats.data.latest_report_date);
        }

        // 更新活跃任务
        if (stats.taskStats?.data?.active_tasks !== undefined) {
            document.getElementById('activeTasks').textContent = stats.taskStats.data.active_tasks;
        }

        this.statsData = stats;
    }

    async searchFunds() {
        const formData = this.getFundSearchFormData();
        
        if (!this.validateSearchForm(formData)) {
            return;
        }

        Utils.showLoading('正在搜索基金...');

        try {
            const response = await api.searchFunds(formData);
            const funds = this.extractFundsData(response);
            
            this.searchResults = funds;
            this.displayFundResults(funds);
            
            if (funds.length > 0) {
                document.getElementById('exportBtn').disabled = false;
                Utils.showNotification('搜索完成', `找到 ${funds.length} 只基金`, 'success', 3000);
            } else {
                Utils.showNotification('搜索结果', '未找到匹配的基金', 'warning', 3000);
            }
        } catch (error) {
            Utils.handleError(error, '基金搜索');
            this.displaySearchError(error.message);
        } finally {
            Utils.hideLoading();
        }
    }

    getFundSearchFormData() {
        return {
            fundCode: document.getElementById('fundCode')?.value.trim(),
            fundName: document.getElementById('fundName')?.value.trim(),
            fundCompany: document.getElementById('fundCompany')?.value.trim(),
            fundType: document.getElementById('fundType')?.value,
            page: this.currentPage,
            size: this.pageSize
        };
    }

    validateSearchForm(formData) {
        if (!formData.fundCode && !formData.fundName && !formData.fundCompany && !formData.fundType) {
            Utils.showNotification('提示', '请输入至少一个搜索条件', 'warning');
            return false;
        }

        if (formData.fundCode && !Utils.isValidFundCode(formData.fundCode)) {
            Utils.showNotification('错误', '基金代码格式不正确（应为6位数字）', 'error');
            return false;
        }

        return true;
    }

    extractFundsData(response) {
        // 处理不同的响应格式
        if (response.data?.items) return response.data.items;
        if (response.data?.funds) return response.data.funds;
        if (response.funds) return response.funds;
        if (Array.isArray(response.data)) return response.data;
        if (Array.isArray(response)) return response;
        return [];
    }

    displayFundResults(funds) {
        const resultsContainer = document.getElementById('searchResults');
        
        if (!funds || funds.length === 0) {
            resultsContainer.innerHTML = this.getEmptyResultsHTML();
            return;
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5>搜索结果 (${funds.length} 条)</h5>
                <div>
                    <button class="btn btn-sm btn-outline-primary" onclick="userInterface.exportResults()">
                        <i class="bi bi-download"></i> 导出结果
                    </button>
                </div>
            </div>
        `;

        funds.forEach(fund => {
            html += this.createFundCard(fund);
        });

        resultsContainer.innerHTML = html;
    }

    createFundCard(fund) {
        return `
            <div class="fund-card">
                <div class="fund-header">
                    <div>
                        <div class="fund-name">${Utils.sanitizeHtml(fund.fund_name || '未知基金')}</div>
                        <span class="fund-code">${Utils.sanitizeHtml(fund.fund_code)}</span>
                    </div>
                    <div>
                        <span class="badge bg-secondary">${Utils.sanitizeHtml(fund.fund_type || '-')}</span>
                    </div>
                </div>
                <div class="fund-details">
                    <div class="fund-detail">
                        <div class="fund-detail-label">基金类型</div>
                        <div class="fund-detail-value">${Utils.sanitizeHtml(fund.fund_type || '-')}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">管理公司</div>
                        <div class="fund-detail-value">${Utils.sanitizeHtml(fund.management_company || fund.fund_company || '-')}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">成立日期</div>
                        <div class="fund-detail-value">${Utils.formatDate(fund.establishment_date)}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">最新净值</div>
                        <div class="fund-detail-value">${fund.latest_nav || fund.unit_nav || '-'}</div>
                    </div>
                </div>
                <div class="fund-actions">
                    <button class="btn btn-primary btn-sm" onclick="userInterface.viewFundDetail('${fund.fund_code}')">
                        <i class="bi bi-eye"></i> 详细信息
                    </button>
                    <button class="btn btn-outline-success btn-sm" onclick="userInterface.viewFundReports('${fund.fund_code}')">
                        <i class="bi bi-file-earmark-text"></i> 查看报告
                    </button>
                    <button class="btn btn-outline-info btn-sm" onclick="userInterface.viewNavHistory('${fund.fund_code}')">
                        <i class="bi bi-graph-up"></i> 净值历史
                    </button>
                </div>
            </div>
        `;
    }

    getEmptyResultsHTML() {
        return `
            <div class="empty-state">
                <i class="bi bi-search"></i>
                <h4>未找到相关基金</h4>
                <p>请尝试调整搜索条件或检查输入的基金代码</p>
                <div class="mt-3">
                    <button class="btn btn-outline-primary" onclick="userInterface.resetSearchForm()">
                        <i class="bi bi-arrow-clockwise"></i> 重置搜索
                    </button>
                </div>
            </div>
        `;
    }

    displaySearchError(errorMessage) {
        const resultsContainer = document.getElementById('searchResults');
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle text-danger"></i>
                <h4>搜索失败</h4>
                <p>${Utils.sanitizeHtml(errorMessage)}</p>
                <div class="mt-3">
                    <button class="btn btn-primary" onclick="userInterface.searchFunds()">
                        <i class="bi bi-arrow-clockwise"></i> 重试
                    </button>
                </div>
            </div>
        `;
    }

    async viewFundDetail(fundCode) {
        Utils.showLoading('正在加载基金详情...');

        try {
            const response = await api.getFund(fundCode);
            const fund = response.data || response;
            
            if (fund) {
                this.showFundDetailModal(fund);
            } else {
                Utils.showNotification('错误', '无法获取基金详情', 'error');
            }
        } catch (error) {
            Utils.handleError(error, '基金详情加载');
        } finally {
            Utils.hideLoading();
        }
    }

    showFundDetailModal(fund) {
        const content = `
            <div class="row">
                <div class="col-md-8">
                    <h5>${Utils.sanitizeHtml(fund.fund_name)} (${Utils.sanitizeHtml(fund.fund_code)})</h5>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>基金类型</strong></td>
                                    <td>${Utils.sanitizeHtml(fund.fund_type || '-')}</td>
                                </tr>
                                <tr>
                                    <td><strong>管理公司</strong></td>
                                    <td>${Utils.sanitizeHtml(fund.management_company || fund.fund_company || '-')}</td>
                                </tr>
                                <tr>
                                    <td><strong>基金经理</strong></td>
                                    <td>${Utils.sanitizeHtml(fund.fund_manager || '-')}</td>
                                </tr>
                                <tr>
                                    <td><strong>成立日期</strong></td>
                                    <td>${Utils.formatDate(fund.establishment_date)}</td>
                                </tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>最新净值</strong></td>
                                    <td>${fund.latest_nav || fund.unit_nav || '-'}</td>
                                </tr>
                                <tr>
                                    <td><strong>累计净值</strong></td>
                                    <td>${fund.cumulative_nav || '-'}</td>
                                </tr>
                                <tr>
                                    <td><strong>净值日期</strong></td>
                                    <td>${Utils.formatDate(fund.nav_date)}</td>
                                </tr>
                                <tr>
                                    <td><strong>基金规模</strong></td>
                                    <td>${Utils.formatCurrency(fund.fund_size)}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="text-center">
                        <h6>快速操作</h6>
                        <div class="d-grid gap-2">
                            <button class="btn btn-outline-success btn-sm" onclick="userInterface.viewFundReports('${fund.fund_code}')">
                                查看报告
                            </button>
                            <button class="btn btn-outline-info btn-sm" onclick="userInterface.viewNavHistory('${fund.fund_code}')">
                                净值历史
                            </button>
                            <button class="btn btn-outline-primary btn-sm" onclick="userInterface.addToExportList('${fund.fund_code}')">
                                添加到导出
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const footer = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            <button type="button" class="btn btn-primary" onclick="Utils.copyToClipboard('${fund.fund_code}')">
                <i class="bi bi-clipboard"></i> 复制代码
            </button>
        `;

        Utils.createModal(`基金详情 - ${fund.fund_name}`, content, footer).show();
    }

    async viewFundReports(fundCode) {
        // 切换到报告页面并搜索该基金的报告
        document.getElementById('reportFundCode').value = fundCode;
        this.switchTab('reports');
        setTimeout(() => this.searchReports(), 100);
    }

    async viewNavHistory(fundCode) {
        Utils.showLoading('正在加载净值历史...');

        try {
            const response = await api.getFundNavHistory(fundCode, { limit: 50 });
            const navHistory = response.data || response;
            
            if (navHistory && navHistory.length > 0) {
                this.showNavHistoryModal(fundCode, navHistory);
            } else {
                Utils.showNotification('提示', '该基金暂无净值历史数据', 'warning');
            }
        } catch (error) {
            Utils.handleError(error, '净值历史加载');
        } finally {
            Utils.hideLoading();
        }
    }

    showNavHistoryModal(fundCode, navHistory) {
        const tableColumns = [
            { key: 'nav_date', label: '日期', formatter: (value) => Utils.formatDate(value) },
            { key: 'unit_nav', label: '单位净值', formatter: (value) => Utils.formatNumber(value, 4) },
            { key: 'cumulative_nav', label: '累计净值', formatter: (value) => Utils.formatNumber(value, 4) },
            { key: 'daily_return', label: '日收益率', formatter: (value) => Utils.formatPercentage(value) }
        ];

        const content = `
            <div class="mb-3">
                <h6>基金代码: ${fundCode}</h6>
                <p class="text-muted">最近50个交易日净值数据</p>
            </div>
            ${Utils.createTableFromData(navHistory, tableColumns)}
        `;

        const footer = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            <button type="button" class="btn btn-primary" onclick="userInterface.exportNavHistory('${fundCode}')">
                <i class="bi bi-download"></i> 导出数据
            </button>
        `;

        Utils.createModal(`净值历史 - ${fundCode}`, content, footer).show();
    }

    async searchReports() {
        const formData = this.getReportSearchFormData();
        
        if (!formData.fundCode) {
            Utils.showNotification('提示', '请输入基金代码', 'warning');
            return;
        }

        Utils.showLoading('正在查询报告...');

        try {
            const response = await api.searchReports(formData);
            const reports = this.extractReportsData(response);
            
            this.reportResults = reports;
            this.displayReportResults(reports);
            
            if (reports.length > 0) {
                document.getElementById('analysisBtn').disabled = false;
                Utils.showNotification('查询完成', `找到 ${reports.length} 份报告`, 'success', 3000);
            } else {
                Utils.showNotification('查询结果', '该基金暂无报告数据', 'warning', 3000);
            }
        } catch (error) {
            Utils.handleError(error, '报告查询');
            this.displayReportError(error.message);
        } finally {
            Utils.hideLoading();
        }
    }

    getReportSearchFormData() {
        return {
            fundCode: document.getElementById('reportFundCode')?.value.trim(),
            reportType: document.getElementById('reportType')?.value,
            year: document.getElementById('reportYear')?.value,
            page: this.currentPage,
            size: this.pageSize
        };
    }

    extractReportsData(response) {
        if (response.data?.items) return response.data.items;
        if (response.data?.reports) return response.data.reports;
        if (response.reports) return response.reports;
        if (Array.isArray(response.data)) return response.data;
        if (Array.isArray(response)) return response;
        return [];
    }

    displayReportResults(reports) {
        const resultsContainer = document.getElementById('reportResults');
        
        if (!reports || reports.length === 0) {
            resultsContainer.innerHTML = this.getEmptyReportsHTML();
            return;
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5>报告列表 (${reports.length} 条)</h5>
                <div>
                    <button class="btn btn-sm btn-outline-success" onclick="userInterface.generateAnalysis()">
                        <i class="bi bi-graph-up-arrow"></i> 生成分析
                    </button>
                </div>
            </div>
        `;

        reports.forEach(report => {
            html += this.createReportCard(report);
        });

        resultsContainer.innerHTML = html;
    }

    createReportCard(report) {
        return `
            <div class="report-card">
                <div class="report-header">
                    <div>
                        <div class="report-title">${Utils.sanitizeHtml(report.fund_name || report.fund_code)} - ${Utils.sanitizeHtml(report.report_type || '报告')}</div>
                        <small class="text-muted">报告日期: ${Utils.formatDate(report.report_date)}</small>
                    </div>
                    <div>
                        <span class="report-type">${Utils.sanitizeHtml(report.report_type || '-')}</span>
                    </div>
                </div>
                <div class="report-info">
                    <div class="report-info-item">
                        <div class="report-info-label">基金代码</div>
                        <div class="report-info-value">${Utils.sanitizeHtml(report.fund_code)}</div>
                    </div>
                    <div class="report-info-item">
                        <div class="report-info-label">报告年份</div>
                        <div class="report-info-value">${report.report_year || '-'}</div>
                    </div>
                    <div class="report-info-item">
                        <div class="report-info-label">创建时间</div>
                        <div class="report-info-value">${Utils.formatDate(report.created_at)}</div>
                    </div>
                    <div class="report-info-item">
                        <div class="report-info-label">数据状态</div>
                        <div class="report-info-value">
                            <span class="status-indicator ${report.is_parsed ? 'status-success' : 'status-warning'}">
                                ${report.is_parsed ? '已解析' : '待解析'}
                            </span>
                        </div>
                    </div>
                </div>
                <div class="fund-actions">
                    <button class="btn btn-primary btn-sm" onclick="userInterface.viewReportDetail('${report.id || report.report_id}')">
                        <i class="bi bi-eye"></i> 查看详情
                    </button>
                    <button class="btn btn-outline-info btn-sm" onclick="userInterface.downloadReport('${report.id || report.report_id}')">
                        <i class="bi bi-download"></i> 下载报告
                    </button>
                </div>
            </div>
        `;
    }

    getEmptyReportsHTML() {
        return `
            <div class="empty-state">
                <i class="bi bi-file-earmark-text"></i>
                <h4>暂无报告数据</h4>
                <p>该基金暂无报告数据，您可以创建数据采集任务来获取报告</p>
                <div class="mt-3">
                    <button class="btn btn-primary" onclick="userInterface.createDataTask()">
                        <i class="bi bi-plus-circle"></i> 创建采集任务
                    </button>
                </div>
            </div>
        `;
    }

    displayReportError(errorMessage) {
        const resultsContainer = document.getElementById('reportResults');
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle text-danger"></i>
                <h4>查询失败</h4>
                <p>${Utils.sanitizeHtml(errorMessage)}</p>
                <div class="mt-3">
                    <button class="btn btn-primary" onclick="userInterface.searchReports()">
                        <i class="bi bi-arrow-clockwise"></i> 重试
                    </button>
                </div>
            </div>
        `;
    }

    async loadDataCenterStats() {
        try {
            const stats = await api.getSystemStats();
            this.updateSystemStats(stats);
        } catch (error) {
            console.error('数据中心统计加载失败:', error);
        }
    }

    async loadMyData() {
        const resultsContainer = document.getElementById('myDataResults');
        
        try {
            Utils.showLoading('正在加载数据...');
            
            const response = await api.getReports({ size: 50 });
            const reports = this.extractReportsData(response);
            
            if (reports && reports.length > 0) {
                this.displayMyDataResults(reports);
            } else {
                resultsContainer.innerHTML = this.getEmptyDataHTML();
            }
        } catch (error) {
            resultsContainer.innerHTML = this.getDataErrorHTML(error.message);
        } finally {
            Utils.hideLoading();
        }
    }

    displayMyDataResults(reports) {
        const resultsContainer = document.getElementById('myDataResults');
        
        // 按基金代码分组
        const groupedReports = this.groupReportsByFund(reports);
        
        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5>我的数据 (${Object.keys(groupedReports).length} 只基金，${reports.length} 份报告)</h5>
                <div>
                    <button class="btn btn-sm btn-outline-primary" onclick="userInterface.exportAllMyData()">
                        <i class="bi bi-download"></i> 导出全部
                    </button>
                </div>
            </div>
        `;

        Object.entries(groupedReports).forEach(([fundCode, fundReports]) => {
            html += this.createMyDataCard(fundCode, fundReports);
        });

        resultsContainer.innerHTML = html;
    }

    groupReportsByFund(reports) {
        const grouped = {};
        reports.forEach(report => {
            const fundCode = report.fund_code;
            if (!grouped[fundCode]) {
                grouped[fundCode] = [];
            }
            grouped[fundCode].push(report);
        });
        return grouped;
    }

    createMyDataCard(fundCode, reports) {
        const fundName = reports[0].fund_name || '未知基金';
        const latestReport = reports.sort((a, b) => new Date(b.report_date) - new Date(a.report_date))[0];
        
        return `
            <div class="fund-card">
                <div class="fund-header">
                    <div>
                        <div class="fund-name">${Utils.sanitizeHtml(fundName)}</div>
                        <span class="fund-code">${Utils.sanitizeHtml(fundCode)}</span>
                    </div>
                    <div>
                        <span class="badge bg-success">${reports.length} 份报告</span>
                    </div>
                </div>
                <div class="fund-details">
                    <div class="fund-detail">
                        <div class="fund-detail-label">最新报告</div>
                        <div class="fund-detail-value">${Utils.formatDate(latestReport.report_date)}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">报告类型</div>
                        <div class="fund-detail-value">${[...new Set(reports.map(r => r.report_type))].join(', ')}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">已解析</div>
                        <div class="fund-detail-value">${reports.filter(r => r.is_parsed).length} / ${reports.length}</div>
                    </div>
                    <div class="fund-detail">
                        <div class="fund-detail-label">数据状态</div>
                        <div class="fund-detail-value">
                            <span class="status-indicator status-success">完整</span>
                        </div>
                    </div>
                </div>
                <div class="fund-actions">
                    <button class="btn btn-primary btn-sm" onclick="userInterface.viewFundReports('${fundCode}')">
                        <i class="bi bi-eye"></i> 查看报告
                    </button>
                    <button class="btn btn-outline-success btn-sm" onclick="userInterface.exportFundData('${fundCode}')">
                        <i class="bi bi-download"></i> 导出数据
                    </button>
                    <button class="btn btn-outline-info btn-sm" onclick="userInterface.analyzeFundData('${fundCode}')">
                        <i class="bi bi-graph-up"></i> 生成分析
                    </button>
                </div>
            </div>
        `;
    }

    getEmptyDataHTML() {
        return `
            <div class="empty-state">
                <i class="bi bi-folder2-open"></i>
                <h4>暂无数据</h4>
                <p>您还没有采集任何基金数据，开始搜索基金或创建采集任务来获取数据</p>
                <div class="mt-3">
                    <button class="btn btn-primary me-2" onclick="userInterface.switchTab('search')">
                        <i class="bi bi-search"></i> 开始搜索
                    </button>
                    <button class="btn btn-outline-primary" onclick="userInterface.createDataTask()">
                        <i class="bi bi-plus-circle"></i> 创建任务
                    </button>
                </div>
            </div>
        `;
    }

    getDataErrorHTML(errorMessage) {
        return `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle text-danger"></i>
                <h4>数据加载失败</h4>
                <p>${Utils.sanitizeHtml(errorMessage)}</p>
                <div class="mt-3">
                    <button class="btn btn-primary" onclick="userInterface.loadMyData()">
                        <i class="bi bi-arrow-clockwise"></i> 重试
                    </button>
                </div>
            </div>
        `;
    }

    // 工具方法
    resetSearchForm() {
        document.getElementById('fund-search-form').reset();
        document.getElementById('searchResults').innerHTML = this.getEmptyResultsHTML();
        document.getElementById('exportBtn').disabled = true;
    }

    resetReportSearchForm() {
        document.getElementById('report-search-form').reset();
        document.getElementById('reportResults').innerHTML = this.getEmptyReportsHTML();
        document.getElementById('analysisBtn').disabled = true;
    }

    async quickSearch(type) {
        const searchMap = {
            '热门基金': { fundType: '股票型' },
            '新发基金': { fundType: '混合型' },
            '高分红基金': { fundType: '债券型' }
        };

        const params = searchMap[type] || {};
        
        // 设置表单值
        Object.keys(params).forEach(key => {
            const element = document.getElementById(key);
            if (element) element.value = params[key];
        });

        // 执行搜索
        await this.searchFunds();
    }

    async quickFundLookup(fundCode) {
        try {
            const response = await api.getFund(fundCode);
            if (response.data || response) {
                Utils.showNotification('基金信息', `找到基金: ${response.data?.fund_name || response.fund_name}`, 'info', 2000);
            }
        } catch (error) {
            // 静默失败，不显示错误
        }
    }

    showOfflineMode() {
        document.body.innerHTML = `
            <div class="container mt-5">
                <div class="row justify-content-center">
                    <div class="col-md-6 text-center">
                        <i class="bi bi-wifi-off" style="font-size: 4rem; color: #dc3545;"></i>
                        <h3 class="mt-3">服务不可用</h3>
                        <p class="text-muted">无法连接到基金报告平台服务，请检查：</p>
                        <ul class="list-unstyled">
                            <li>• 确保API服务正在运行</li>
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

    // 导出功能（占位实现）
    exportResults() {
        if (this.searchResults.length === 0) {
            Utils.showNotification('提示', '没有可导出的数据', 'warning');
            return;
        }
        Utils.exportToJSON(this.searchResults, `基金搜索结果_${new Date().toISOString().split('T')[0]}.json`);
    }

    exportAllMyData() {
        Utils.showNotification('功能开发中', '数据导出功能正在开发中', 'info');
    }

    exportFundData(fundCode) {
        Utils.showNotification('功能开发中', `基金${fundCode}数据导出功能正在开发中`, 'info');
    }

    exportNavHistory(fundCode) {
        Utils.showNotification('功能开发中', `基金${fundCode}净值历史导出功能正在开发中`, 'info');
    }

    // 其他功能（占位实现）
    generateAnalysis() {
        Utils.showNotification('功能开发中', '分析报告生成功能正在开发中', 'info');
    }

    analyzeFundData(fundCode) {
        Utils.showNotification('功能开发中', `基金${fundCode}分析功能正在开发中`, 'info');
    }

    createDataTask() {
        Utils.showNotification('功能开发中', '数据采集任务创建功能正在开发中', 'info');
    }

    checkSystemHealth() {
        window.open('/health', '_blank');
    }

    openAPIDoc() {
        window.open('/docs', '_blank');
    }

    downloadSampleData() {
        const sampleData = {
            platform: "基金报告自动化采集与分析平台",
            description: "示例基金数据",
            funds: [
                { fund_code: "000001", fund_name: "华夏成长混合", fund_type: "混合型", fund_company: "华夏基金" },
                { fund_code: "000300", fund_name: "沪深300ETF", fund_type: "指数型", fund_company: "华泰柏瑞基金" },
                { fund_code: "110022", fund_name: "易方达消费行业股票", fund_type: "股票型", fund_company: "易方达基金" }
            ],
            timestamp: new Date().toISOString()
        };
        
        Utils.exportToJSON(sampleData, `sample_fund_data_${new Date().toISOString().split('T')[0]}.json`);
    }

    showCustomExport() {
        const modal = new bootstrap.Modal(document.getElementById('customExportModal'));
        modal.show();
    }

    executeCustomExport() {
        const formData = {
            dataType: document.getElementById('exportDataType').value,
            fundCodes: document.getElementById('exportFundCodes').value.trim(),
            startDate: document.getElementById('exportStartDate').value,
            endDate: document.getElementById('exportEndDate').value
        };

        Utils.showNotification('功能开发中', '自定义数据导出功能正在开发中', 'info');
        
        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('customExportModal'));
        if (modal) modal.hide();
    }

    refreshMyData() {
        this.loadMyData();
    }

    exportAllData() {
        Utils.showNotification('功能开发中', '全部数据导出功能正在开发中', 'info');
    }

    exportRecentData() {
        Utils.showNotification('功能开发中', '最新数据导出功能正在开发中', 'info');
    }

    // 占位方法
    viewReportDetail(reportId) {
        Utils.showNotification('功能开发中', '报告详情查看功能正在开发中', 'info');
    }

    downloadReport(reportId) {
        Utils.showNotification('功能开发中', '报告下载功能正在开发中', 'info');
    }

    addToExportList(fundCode) {
        Utils.showNotification('已添加', `基金${fundCode}已添加到导出列表`, 'success', 2000);
    }
}

// 初始化用户界面
document.addEventListener('DOMContentLoaded', () => {
    window.userInterface = new UserInterface();
});

// 全局函数（为了兼容HTML中的onclick）
window.resetSearchForm = () => window.userInterface?.resetSearchForm();
window.resetReportSearch = () => window.userInterface?.resetReportSearchForm();
window.quickSearch = (type) => window.userInterface?.quickSearch(type);
window.switchTab = (tabName) => window.userInterface?.switchTab(tabName);
window.exportResults = () => window.userInterface?.exportResults();
window.exportAllData = () => window.userInterface?.exportAllData();
window.exportRecentData = () => window.userInterface?.exportRecentData();
window.showCustomExport = () => window.userInterface?.showCustomExport();
window.executeCustomExport = () => window.userInterface?.executeCustomExport();
window.refreshMyData = () => window.userInterface?.refreshMyData();
window.generateAnalysis = () => window.userInterface?.generateAnalysis();
window.createDataTask = () => window.userInterface?.createDataTask();
window.checkSystemHealth = () => window.userInterface?.checkSystemHealth();
window.openAPIDoc = () => window.userInterface?.openAPIDoc();
window.downloadSampleData = () => window.userInterface?.downloadSampleData();
window.generateReport = () => window.userInterface?.generateAnalysis();