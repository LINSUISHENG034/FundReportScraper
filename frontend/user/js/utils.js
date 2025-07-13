// 工具函数
class Utils {
    static formatDate(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('zh-CN');
        } catch (e) {
            return dateString;
        }
    }

    static formatNumber(number, decimals = 2) {
        if (number === null || number === undefined) return '-';
        return Number(number).toLocaleString('zh-CN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    static formatCurrency(amount, currency = '元') {
        if (amount === null || amount === undefined) return '-';
        return `${this.formatNumber(amount)}${currency}`;
    }

    static formatPercentage(value) {
        if (value === null || value === undefined) return '-';
        return `${(value * 100).toFixed(2)}%`;
    }

    static sanitizeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    static showLoading(text = '正在处理请求...') {
        const overlay = document.getElementById('loadingOverlay');
        const loadingText = document.getElementById('loadingText');
        if (loadingText) {
            loadingText.textContent = text;
        }
        overlay.classList.remove('d-none');
    }

    static hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        overlay.classList.add('d-none');
    }

    static showNotification(title, message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = 'notification';
        
        const iconMap = {
            success: 'bi-check-circle-fill text-success',
            error: 'bi-x-circle-fill text-danger',
            warning: 'bi-exclamation-triangle-fill text-warning',
            info: 'bi-info-circle-fill text-info'
        };

        notification.innerHTML = `
            <div class="notification-header">
                <div class="d-flex align-items-center">
                    <i class="bi ${iconMap[type]} me-2"></i>
                    <strong>${this.sanitizeHtml(title)}</strong>
                </div>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">
                    <i class="bi bi-x"></i>
                </button>
            </div>
            <div class="notification-body">
                ${this.sanitizeHtml(message)}
            </div>
        `;

        document.body.appendChild(notification);
        
        // 显示动画
        setTimeout(() => notification.classList.add('show'), 100);
        
        // 自动隐藏
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
    }

    static downloadFile(data, filename, type = 'application/json') {
        const blob = new Blob([data], { type });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    static copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showNotification('成功', '内容已复制到剪贴板', 'success', 2000);
            }).catch(() => {
                this.fallbackCopyTextToClipboard(text);
            });
        } else {
            this.fallbackCopyTextToClipboard(text);
        }
    }

    static fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            const successful = document.execCommand('copy');
            if (successful) {
                this.showNotification('成功', '内容已复制到剪贴板', 'success', 2000);
            } else {
                this.showNotification('失败', '无法复制到剪贴板', 'error', 3000);
            }
        } catch (err) {
            this.showNotification('错误', '复制功能不受支持', 'error', 3000);
        }

        document.body.removeChild(textArea);
    }

    static parseQueryParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};
        for (const [key, value] of params) {
            result[key] = value;
        }
        return result;
    }

    static updateQueryParams(params) {
        const url = new URL(window.location);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                url.searchParams.set(key, params[key]);
            } else {
                url.searchParams.delete(key);
            }
        });
        window.history.replaceState({}, '', url);
    }

    static isValidFundCode(code) {
        // 基金代码通常是6位数字
        return /^\d{6}$/.test(code);
    }

    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    static validatePhone(phone) {
        const re = /^1[3-9]\d{9}$/;
        return re.test(phone);
    }

    static getStatusBadgeClass(status) {
        const statusMap = {
            'success': 'status-success',
            'completed': 'status-success',
            'running': 'status-warning',
            'pending': 'status-info',
            'failed': 'status-danger',
            'error': 'status-danger'
        };
        return statusMap[status] || 'status-info';
    }

    static getStatusText(status) {
        const statusMap = {
            'success': '成功',
            'completed': '已完成',
            'running': '运行中',
            'pending': '等待中',
            'failed': '失败',
            'error': '错误'
        };
        return statusMap[status] || status;
    }

    static createProgressBar(percentage, label = '') {
        return `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <small class="text-muted">${label}</small>
                <small class="text-muted">${percentage}%</small>
            </div>
            <div class="progress-custom">
                <div class="progress-bar-custom" style="width: ${percentage}%"></div>
            </div>
        `;
    }

    static createChart(canvasId, type, data, options = {}) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // 默认配置
        const defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        };

        return new Chart(ctx, {
            type,
            data,
            options: { ...defaultOptions, ...options }
        });
    }

    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    static generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    static createTableFromData(data, columns) {
        if (!data || data.length === 0) {
            return '<div class="empty-state"><p>暂无数据</p></div>';
        }

        let html = `
            <div class="data-table">
                <table class="table table-hover">
                    <thead>
                        <tr>
        `;

        columns.forEach(col => {
            html += `<th>${col.label}</th>`;
        });

        html += `
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                let value = row[col.key];
                if (col.formatter) {
                    value = col.formatter(value, row);
                }
                html += `<td>${value || '-'}</td>`;
            });
            html += '</tr>';
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        return html;
    }

    static exportToCSV(data, filename) {
        if (!data || data.length === 0) {
            this.showNotification('错误', '没有数据可导出', 'error');
            return;
        }

        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(header => `"${row[header] || ''}"`).join(','))
        ].join('\n');

        this.downloadFile(csvContent, filename, 'text/csv;charset=utf-8;');
    }

    static exportToJSON(data, filename) {
        if (!data) {
            this.showNotification('错误', '没有数据可导出', 'error');
            return;
        }

        const jsonContent = JSON.stringify(data, null, 2);
        this.downloadFile(jsonContent, filename, 'application/json');
    }

    static createModal(title, content, footer = '') {
        const modalId = 'modal-' + this.generateId();
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = modalId;
        modal.tabIndex = -1;

        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">${content}</div>
                    ${footer ? `<div class="modal-footer">${footer}</div>` : ''}
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bootstrapModal = new bootstrap.Modal(modal);
        
        // 模态框关闭时移除DOM元素
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });

        return bootstrapModal;
    }

    static handleError(error, context = '操作') {
        console.error(`${context}失败:`, error);
        
        let message = '发生未知错误';
        if (error.message) {
            message = error.message;
        } else if (typeof error === 'string') {
            message = error;
        }

        this.showNotification('错误', `${context}失败: ${message}`, 'error');
    }

    static retryOperation(operation, maxRetries = 3, delay = 1000) {
        return new Promise((resolve, reject) => {
            let attempts = 0;

            const attemptOperation = () => {
                attempts++;
                operation()
                    .then(resolve)
                    .catch(error => {
                        if (attempts < maxRetries) {
                            setTimeout(attemptOperation, delay * attempts);
                        } else {
                            reject(error);
                        }
                    });
            };

            attemptOperation();
        });
    }
}

// 全局错误处理
window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
    Utils.showNotification('系统错误', '页面发生错误，请刷新页面重试', 'error');
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的Promise拒绝:', event.reason);
    Utils.showNotification('网络错误', '请求失败，请检查网络连接', 'error');
});

// 导出工具类
window.Utils = Utils;