// API管理类
class API {
    constructor(baseURL = 'http://localhost:8001') { // 默认使用测试API服务器
        this.baseURL = baseURL;
        this.timeout = 10000;
    }

    async request(url, options = {}) {
        const config = {
            timeout: this.timeout,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);

            const response = await fetch(`${this.baseURL}${url}`, {
                ...config,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请检查网络连接');
            }
            throw error;
        }
    }

    async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        return this.request(fullUrl);
    }

    async post(url, data = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(url, data = {}) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(url) {
        return this.request(url, {
            method: 'DELETE'
        });
    }

    // 健康检查
    async checkHealth() {
        return this.get('/health');
    }

    // 基金相关API
    async getFunds(params = {}) {
        return this.get('/api/v1/funds/', params);
    }

    async getFund(fundCode) {
        return this.get(`/api/v1/funds/${fundCode}`);
    }

    async getFundNavHistory(fundCode, params = {}) {
        return this.get(`/api/v1/funds/${fundCode}/nav-history`, params);
    }

    async searchFunds(searchParams) {
        const params = {};
        
        if (searchParams.fundCode) {
            params.fund_code = searchParams.fundCode;
        }
        if (searchParams.fundName) {
            params.search = searchParams.fundName;
        }
        if (searchParams.fundCompany) {
            params.search = searchParams.fundCompany; // API可能需要调整
        }
        if (searchParams.fundType) {
            params.fund_type = searchParams.fundType;
        }
        
        params.page = searchParams.page || 1;
        params.size = searchParams.size || 20;

        return this.get('/api/v1/funds/', params);
    }

    // 报告相关API
    async getReports(params = {}) {
        return this.get('/api/v1/reports/', params);
    }

    async getReport(reportId) {
        return this.get(`/api/v1/reports/${reportId}`);
    }

    async searchReports(searchParams) {
        const params = {};
        
        if (searchParams.fundCode) {
            params.fund_code = searchParams.fundCode;
        }
        if (searchParams.reportType) {
            params.report_type = searchParams.reportType;
        }
        if (searchParams.year) {
            params.year = searchParams.year;
        }
        if (searchParams.startDate) {
            params.start_date = searchParams.startDate;
        }
        if (searchParams.endDate) {
            params.end_date = searchParams.endDate;
        }
        
        params.page = searchParams.page || 1;
        params.size = searchParams.size || 20;

        return this.get('/api/v1/reports/', params);
    }

    // 任务相关API
    async getTasks(params = {}) {
        return this.get('/api/v1/tasks/', params);
    }

    async getTask(taskId) {
        return this.get(`/api/v1/tasks/${taskId}`);
    }

    async createTask(taskData) {
        return this.post('/api/v1/tasks/', taskData);
    }

    async getTaskStats() {
        return this.get('/api/v1/tasks/stats/summary');
    }

    // 统计相关API
    async getFundStats() {
        return this.get('/api/v1/funds/stats/summary');
    }

    async getReportStats() {
        return this.get('/api/v1/reports/stats/summary');
    }

    async getSystemStats() {
        try {
            const [health, fundStats, reportStats, taskStats] = await Promise.allSettled([
                this.checkHealth(),
                this.getFundStats(),
                this.getReportStats(),
                this.getTaskStats()
            ]);

            return {
                health: health.status === 'fulfilled' ? health.value : null,
                fundStats: fundStats.status === 'fulfilled' ? fundStats.value : null,
                reportStats: reportStats.status === 'fulfilled' ? reportStats.value : null,
                taskStats: taskStats.status === 'fulfilled' ? taskStats.value : null
            };
        } catch (error) {
            console.error('获取系统统计失败:', error);
            return null;
        }
    }

    // 模拟一些后端可能不存在的API
    async getFundCompanies() {
        // 如果后端没有专门的API，从基金列表中提取
        try {
            const response = await this.getFunds({ size: 1000 });
            const funds = response.data?.items || response.funds || [];
            const companies = [...new Set(funds.map(fund => fund.management_company || fund.fund_company).filter(Boolean))];
            return { success: true, data: companies };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getFundTypes() {
        // 如果后端没有专门的API，返回预定义的类型
        return {
            success: true,
            data: ['股票型', '混合型', '债券型', '货币型', '指数型', 'QDII', 'FOF']
        };
    }

    // 数据导出相关
    async exportData(exportParams) {
        const params = {
            data_type: exportParams.dataType || 'funds',
            format: exportParams.format || 'json',
            ...exportParams
        };

        if (exportParams.dataType === 'funds') {
            return this.getFunds(params);
        } else if (exportParams.dataType === 'reports') {
            return this.getReports(params);
        } else {
            throw new Error('不支持的数据类型');
        }
    }

    // 批量操作
    async batchGetFunds(fundCodes) {
        const promises = fundCodes.map(code => 
            this.getFund(code).catch(error => ({ error: error.message, fund_code: code }))
        );
        return Promise.all(promises);
    }

    async batchGetReports(fundCodes) {
        const promises = fundCodes.map(code => 
            this.getReports({ fund_code: code }).catch(error => ({ error: error.message, fund_code: code }))
        );
        return Promise.all(promises);
    }

    // 缓存管理
    createCacheKey(url, params) {
        return `${url}_${JSON.stringify(params)}`;
    }

    setCache(key, data, ttl = 300000) { // 默认5分钟缓存
        const cacheData = {
            data,
            timestamp: Date.now(),
            ttl
        };
        try {
            localStorage.setItem(`api_cache_${key}`, JSON.stringify(cacheData));
        } catch (error) {
            console.warn('缓存设置失败:', error);
        }
    }

    getCache(key) {
        try {
            const cached = localStorage.getItem(`api_cache_${key}`);
            if (!cached) return null;

            const cacheData = JSON.parse(cached);
            if (Date.now() - cacheData.timestamp > cacheData.ttl) {
                localStorage.removeItem(`api_cache_${key}`);
                return null;
            }

            return cacheData.data;
        } catch (error) {
            console.warn('缓存读取失败:', error);
            return null;
        }
    }

    clearCache() {
        try {
            const keys = Object.keys(localStorage);
            keys.forEach(key => {
                if (key.startsWith('api_cache_')) {
                    localStorage.removeItem(key);
                }
            });
        } catch (error) {
            console.warn('缓存清理失败:', error);
        }
    }

    // 带缓存的请求
    async cachedRequest(url, params = {}, useCache = true, ttl = 300000) {
        const cacheKey = this.createCacheKey(url, params);
        
        if (useCache) {
            const cached = this.getCache(cacheKey);
            if (cached) {
                return cached;
            }
        }

        const data = await this.get(url, params);
        
        if (useCache && data) {
            this.setCache(cacheKey, data, ttl);
        }

        return data;
    }

    // 重试机制
    async requestWithRetry(url, options = {}, maxRetries = 3) {
        let lastError;
        
        for (let i = 0; i < maxRetries; i++) {
            try {
                return await this.request(url, options);
            } catch (error) {
                lastError = error;
                if (i < maxRetries - 1) {
                    // 指数退避
                    const delay = Math.pow(2, i) * 1000;
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }
        
        throw lastError;
    }

    // 响应数据标准化
    normalizeResponse(response) {
        // 处理不同的API响应格式
        if (response.success !== undefined) {
            return response.success ? response.data : null;
        }
        
        if (response.data !== undefined) {
            return response.data;
        }
        
        return response;
    }

    // 错误处理
    handleError(error, context = '') {
        console.error(`API错误 ${context}:`, error);
        
        if (error.message.includes('Failed to fetch')) {
            throw new Error('网络连接失败，请检查服务器状态');
        }
        
        if (error.message.includes('timeout')) {
            throw new Error('请求超时，请稍后重试');
        }
        
        if (error.message.includes('404')) {
            throw new Error('请求的资源不存在');
        }
        
        if (error.message.includes('500')) {
            throw new Error('服务器内部错误，请稍后重试');
        }
        
        throw error;
    }
}

// 创建全局API实例
const api = new API();

// 导出API类和实例
window.API = API;
window.api = api;