/**
 * Tax law monitoring dashboard
 * Primary flow: choose a period, scan sources with new items, then inspect the items.
 */

class ExpertDashboard {
    constructor() {
        this.currentTimeFilter = 24;
        this.customRange = null;
        this.selectedSiteKey = null;
        this.websocket = null;
        this.refreshInterval = null;

        this.siteColors = {
            tax_tribunal: '#4F46E5',
            nts_authority: '#059669',
            nts_precedent: '#D97706',
            moef: '#8B5CF6',
            mois: '#DC2626',
            bai: '#6B7280',
            scourt_major_decisions: '#0F766E',
            scourt_scheduled_decisions: '#B45309'
        };

        this.siteNames = {
            tax_tribunal: '심판원 결정례',
            nts_authority: '국세청 유권해석',
            nts_precedent: '국세청 판례',
            moef: '기획재정부',
            mois: '행정안전부',
            bai: '감사원',
            scourt_major_decisions: '전국법원 주요판결',
            scourt_scheduled_decisions: '대법원 선고예정'
        };

        this.sourceOrder = [
            'nts_authority',
            'nts_precedent',
            'tax_tribunal',
            'moef',
            'mois',
            'bai',
            'scourt_major_decisions',
            'scourt_scheduled_decisions'
        ];

        this.dashboardData = { sites: [], last_refresh: null };
        this.recentCounts = {};
        this.newData = [];
        this.scheduleData = { schedules: [] };

        this.browserNotificationEnabled = this.loadNotificationSetting();
        this.notificationPermission = 'default';
        this.isPageVisible = true;
        this.lastNotificationTime = new Map();

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initBrowserNotifications();
        this.connectWebSocket();
        this.loadInitialData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        document.querySelectorAll('.filter-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (btn.dataset.range === 'custom') {
                    this.showCustomRange();
                    return;
                }
                this.setTimeFilter(parseInt(btn.dataset.hours, 10));
            });
        });

        document.getElementById('applyDateRange')?.addEventListener('click', () => {
            this.applyCustomDateRange();
        });

        document.getElementById('settingsBtn')?.addEventListener('click', () => {
            window.location.href = '/settings';
        });

        document.getElementById('refreshDashboardBtn')?.addEventListener('click', () => {
            this.loadDashboardData();
        });

        document.addEventListener('visibilitychange', () => {
            this.isPageVisible = !document.hidden;
        });
    }

    async connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/crawl`;

            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                this.updateConnectionStatus(true);
            };

            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('WebSocket message parsing error:', error);
                }
            };

            this.websocket.onclose = () => {
                this.updateConnectionStatus(false);
                setTimeout(() => {
                    this.connectWebSocket();
                }, 5000);
            };

            this.websocket.onerror = () => {
                this.updateConnectionStatus(false);
            };
        } catch (error) {
            this.updateConnectionStatus(false);
        }
    }

    updateConnectionStatus(isConnected) {
        const statusElement = document.getElementById('connectionStatus');
        const dotElement = statusElement?.querySelector('.indicator-dot');
        const textElement = statusElement?.querySelector('span');

        if (!statusElement || !dotElement || !textElement) return;

        statusElement.classList.toggle('is-offline', !isConnected);
        dotElement.style.background = isConnected ? '#059669' : '#DC2626';
        textElement.textContent = isConnected ? '연결됨' : '끊김';
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'notification':
                this.showToast('새로운 업데이트', 'success', message.title);
                this.showBrowserNotification(message.title, message.message, {
                    site_key: message.site_key,
                    urgency_level: message.urgency_level,
                    new_data_count: message.new_data_count,
                    notification_type: message.notification_type
                });
                this.loadDashboardData(false);
                break;
            case 'crawl_complete':
                this.loadDashboardData(false);
                break;
            case 'crawl_error':
                this.showToast('수집 오류', 'error', `오류: ${message.error}`);
                break;
        }
    }

    async loadInitialData() {
        await this.loadDashboardData(true);
    }

    async loadDashboardData(showLoader = true) {
        if (showLoader) {
            this.showLoading(true);
        }

        try {
            const hours = this.getQueryHours();
            const [dashboardData, newDataData, scheduleData] =
                await Promise.all([
                    this.fetchJson('/api/dashboard'),
                    this.fetchJson(`/api/new-data?hours=${hours}&limit=1000`),
                    this.fetchOptionalJson('/api/schedules', {
                        schedules: [],
                        scheduler_running: false
                    })
                ]);

            this.dashboardData = dashboardData || { sites: [] };
            this.newData = newDataData?.new_data || [];
            this.recentCounts = this.buildRecentCounts(this.newData);
            this.scheduleData = scheduleData || { schedules: [] };

            this.renderDashboard();
        } catch (error) {
            console.error('대시보드 데이터 로드 실패:', error);
            this.showToast('로드 오류', 'error', '대시보드 데이터를 불러오지 못했습니다');
            this.renderFailureState();
        } finally {
            this.showLoading(false);
        }
    }

    async fetchJson(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`${url} ${response.status}`);
        }
        return response.json();
    }

    async fetchOptionalJson(url, fallback) {
        try {
            const response = await fetch(url);
            if (!response.ok) return fallback;
            return response.json();
        } catch (error) {
            return fallback;
        }
    }

    setTimeFilter(hours) {
        this.currentTimeFilter = hours;
        this.customRange = null;
        this.selectedSiteKey = null;

        document.querySelectorAll('.filter-btn').forEach((btn) => {
            btn.classList.toggle('active', parseInt(btn.dataset.hours, 10) === hours);
        });

        const picker = document.getElementById('dateRangePicker');
        if (picker) picker.hidden = true;

        this.loadDashboardData();
    }

    showCustomRange() {
        document.querySelectorAll('.filter-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.range === 'custom');
        });

        const picker = document.getElementById('dateRangePicker');
        if (picker) {
            picker.hidden = false;
            document.getElementById('startDate')?.focus();
        }
    }

    applyCustomDateRange() {
        const startDate = document.getElementById('startDate')?.value;
        const endDate = document.getElementById('endDate')?.value;

        if (!startDate || !endDate) {
            this.showToast('기간 선택', 'warning', '시작일과 종료일을 선택해주세요');
            return;
        }

        const start = new Date(`${startDate}T00:00:00`);
        const end = new Date(`${endDate}T23:59:59`);

        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) {
            this.showToast('기간 오류', 'error', '기간을 다시 확인해주세요');
            return;
        }

        this.customRange = { startDate, endDate, start, end };
        this.selectedSiteKey = null;
        this.currentTimeFilter = Math.max(24, Math.ceil((Date.now() - start.getTime()) / 3600000));
        this.loadDashboardData();
    }

    renderDashboard() {
        this.renderSourceOverview();
        this.renderRecentItems();
        this.updateHeaderOperationalStatus();
    }

    renderSourceOverview() {
        const summary = document.getElementById('sourceFilterSummary');
        const container = document.getElementById('sourceFilterList');
        if (!container) return;

        const sources = this.getOrderedSources();
        const sourcesWithNew = sources.filter((site) => this.getRecentCount(site.site_key) > 0);
        const totalNew = this.getTotalNewCount();

        if (summary) {
            summary.innerHTML = '';
            summary.appendChild(this.createSourceFilterButton({
                siteKey: null,
                label: '전체',
                subLabel: sourcesWithNew.length ? `${sourcesWithNew.length}개 출처` : '신규 없음',
                count: totalNew,
                color: '#1B365D',
                latestLabel: this.getLatestDiscoveryLabel()
            }));
        }

        container.innerHTML = '';

        if (!sources.length) {
            container.innerHTML = '<div class="source-filter-empty">선택한 기간에 새 항목 없음</div>';
            return;
        }

        sources.forEach((site) => {
            const count = this.getRecentCount(site.site_key);
            container.appendChild(this.createSourceFilterButton({
                siteKey: site.site_key,
                label: this.getSiteName(site.site_key, site.site_name),
                subLabel: count > 0 ? '신규' : '신규 없음',
                count,
                color: this.getSiteColor(site.site_key),
                latestLabel: this.getLatestDiscoveryLabel(site.site_key),
                isQuiet: count === 0
            }));
        });
    }

    createSourceFilterButton({ siteKey, label, subLabel, count, color, latestLabel = '', isQuiet = false }) {
        const button = document.createElement('button');
        const isActive = this.selectedSiteKey === siteKey;

        button.type = 'button';
        button.className = `source-filter-item${isActive ? ' active' : ''}${isQuiet ? ' is-quiet' : ''}`;
        button.style.setProperty('--source-color', color);
        button.setAttribute('aria-pressed', String(isActive));
        const metaLabel = count > 0 && latestLabel
            ? `${subLabel} · ${latestLabel}`
            : subLabel;

        button.innerHTML = `
            <span class="source-filter-main">
                <span class="source-color-dot"></span>
                <span class="source-filter-name">${this.escapeHtml(label)}</span>
            </span>
            <span class="source-filter-meta">${this.escapeHtml(metaLabel)}</span>
            <span class="source-filter-count">${count}</span>
        `;

        button.addEventListener('click', () => {
            this.selectedSiteKey = siteKey;
            this.renderSourceOverview();
            this.renderRecentItems();
        });

        return button;
    }

    renderRecentItems() {
        const tbody = document.getElementById('recentItemsTableBody');
        if (!tbody) return;

        const visibleItems = this.getVisibleNewData();
        const title = this.selectedSiteKey
            ? `${this.getSiteName(this.selectedSiteKey)} 신규 항목`
            : '신규 항목';

        this.setText('recentItemsTitle', title);
        tbody.innerHTML = '';

        if (!visibleItems.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="table-empty">새 항목 없음</td>
                </tr>
            `;
            return;
        }

        visibleItems.slice(0, 40).forEach((item) => {
            const row = document.createElement('tr');
            row.className = item.is_important ? 'is-important' : '';
            row.tabIndex = 0;
            row.addEventListener('click', () => this.viewSiteData(item.site_key, true));
            row.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    this.viewSiteData(item.site_key, true);
                }
            });

            const titleText = this.escapeHtml(item.data_title || item.data_id || '제목 없음');
            const source = this.escapeHtml(this.getSiteName(item.site_key, item.site_name));
            const category = this.escapeHtml(item.data_category || '일반');
            const dateLabel = this.escapeHtml(this.formatDocumentDate(item));

            row.innerHTML = `
                <td><span class="source-badge" style="--source-color: ${this.getSiteColor(item.site_key)}">${source}</span></td>
                <td class="muted-cell">${category}</td>
                <td class="title-cell"><span class="title-text">${titleText}</span></td>
                <td class="date-cell">${dateLabel}</td>
                <td class="action-cell">
                    <button class="row-action" aria-label="데이터 보기" title="데이터 보기">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
                            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                </td>
            `;

            row.querySelector('.row-action')?.addEventListener('click', (event) => {
                event.stopPropagation();
                this.viewSiteData(item.site_key, true);
            });

            tbody.appendChild(row);
        });
    }

    renderFailureState() {
        const recentBody = document.getElementById('recentItemsTableBody');
        const sourceSummary = document.getElementById('sourceFilterSummary');
        const sourceFilters = document.getElementById('sourceFilterList');

        if (recentBody) {
            recentBody.innerHTML = '<tr><td colspan="5" class="table-empty">데이터 로드 실패</td></tr>';
        }
        if (sourceFilters) {
            sourceFilters.innerHTML = '<div class="source-filter-empty">데이터 로드 실패</div>';
        }
        if (sourceSummary) {
            sourceSummary.innerHTML = '<div class="source-filter-empty">데이터 로드 실패</div>';
        }
    }

    updateHeaderOperationalStatus() {
        const nextRun = this.getNextRun();
        this.setText('headerScheduleStatus', nextRun ? `다음 ${this.formatCompactTime(nextRun)}` : '다음 --');
    }

    getOrderedSources() {
        return [...(this.dashboardData.sites || [])]
            .sort((a, b) => {
                const aIndex = this.sourceOrder.indexOf(a.site_key);
                const bIndex = this.sourceOrder.indexOf(b.site_key);
                if (aIndex !== -1 || bIndex !== -1) {
                    return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
                }
                return this.getSiteName(a.site_key, a.site_name)
                    .localeCompare(this.getSiteName(b.site_key, b.site_name), 'ko-KR');
            });
    }

    getVisibleNewData() {
        if (!this.selectedSiteKey) return this.newData;
        return this.newData.filter((item) => item.site_key === this.selectedSiteKey);
    }

    getLatestDiscoveryLabel(siteKey = null) {
        const items = siteKey
            ? this.newData.filter((item) => item.site_key === siteKey)
            : this.newData;

        const latest = items
            .map((item) => item.discovered_at ? new Date(item.discovered_at) : null)
            .filter((date) => date && !Number.isNaN(date.getTime()))
            .sort((a, b) => b - a)[0];

        return latest ? this.formatRelativeTime(latest) : '신규 없음';
    }

    buildRecentCounts(items) {
        return items.reduce((counts, item) => {
            const siteKey = item.site_key;
            if (!siteKey) return counts;

            if (!counts[siteKey]) {
                counts[siteKey] = {
                    count: 0,
                    site_name: this.getSiteName(siteKey, item.site_name)
                };
            }

            counts[siteKey].count += 1;
            return counts;
        }, {});
    }

    getRecentCount(siteKey) {
        return this.recentCounts?.[siteKey]?.count || 0;
    }

    getTotalNewCount() {
        return Object.values(this.recentCounts || {}).reduce((sum, item) => sum + (item.count || 0), 0);
    }

    getNextRun() {
        const nextRuns = (this.scheduleData.schedules || [])
            .filter((schedule) => Boolean(schedule.enabled))
            .map((schedule) => schedule.scheduler_status?.next_run ? new Date(schedule.scheduler_status.next_run) : null)
            .filter((date) => date && !Number.isNaN(date.getTime()) && date.getTime() > Date.now())
            .sort((a, b) => a - b);

        return nextRuns[0] || null;
    }

    getSiteName(siteKey, fallback = '') {
        return this.siteNames[siteKey] || fallback || siteKey;
    }

    getSiteColor(siteKey) {
        return this.siteColors[siteKey] || '#6B7280';
    }

    getQueryHours() {
        return Math.max(1, this.currentTimeFilter || 24);
    }

    formatTimeFilter() {
        if (this.customRange) {
            return `${this.customRange.startDate} ~ ${this.customRange.endDate}`;
        }
        if (this.currentTimeFilter === 24) return '최근 24시간';
        if (this.currentTimeFilter === 72) return '최근 3일';
        if (this.currentTimeFilter === 168) return '최근 7일';

        const days = Math.ceil(this.currentTimeFilter / 24);
        return `최근 ${days}일`;
    }

    formatDocumentDate(item) {
        if (item.data_date) return item.data_date;
        if (item.discovered_at) return this.formatCompactDate(new Date(item.discovered_at));
        return '--';
    }

    formatRelativeTime(date) {
        if (!date || Number.isNaN(date.getTime())) return '--';

        const diffInMinutes = Math.floor((Date.now() - date.getTime()) / 60000);

        if (diffInMinutes < 1) return '방금 전';
        if (diffInMinutes < 60) return `${diffInMinutes}분 전`;

        const diffInHours = Math.floor(diffInMinutes / 60);
        if (diffInHours < 24) return `${diffInHours}시간 전`;

        const diffInDays = Math.floor(diffInHours / 24);
        if (diffInDays < 7) return `${diffInDays}일 전`;

        return this.formatCompactDate(date);
    }

    formatCompactDate(date) {
        if (!date || Number.isNaN(date.getTime())) return '--';
        return date.toLocaleDateString('ko-KR', {
            month: '2-digit',
            day: '2-digit'
        });
    }

    formatCompactTime(date) {
        if (!date || Number.isNaN(date.getTime())) return '--';
        return date.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }

    viewSiteData(siteKey, isFiltered = false) {
        if (!siteKey) return;

        if (isFiltered) {
            let url = `/data/${siteKey}?filter=recent`;

            if (this.customRange) {
                url = `/data/${siteKey}?filter=range&start=${this.customRange.startDate}&end=${this.customRange.endDate}`;
            } else if (this.currentTimeFilter === 24) {
                url += '&days=1';
            } else if (this.currentTimeFilter === 72) {
                url += '&days=3';
            } else if (this.currentTimeFilter === 168) {
                url += '&days=7';
            } else {
                url += `&days=${Math.ceil(this.currentTimeFilter / 24)}`;
            }

            window.location.href = url;
            return;
        }

        window.location.href = `/data/${siteKey}`;
    }

    setText(id, text) {
        const element = document.getElementById(id);
        if (element) element.textContent = text;
    }

    escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    showToast(title, type, message) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div><strong>${this.escapeHtml(title)}</strong></div>
            <div>${this.escapeHtml(message)}</div>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 5000);
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (!overlay) return;
        overlay.classList.toggle('show', Boolean(show));
    }

    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.loadDashboardData(false);
        }, 5 * 60 * 1000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    async initBrowserNotifications() {
        if (!('Notification' in window)) {
            this.notificationPermission = 'unsupported';
            return;
        }

        this.notificationPermission = Notification.permission;
    }

    async requestNotificationPermission() {
        if (!('Notification' in window)) {
            this.showToast('알림 지원 안됨', 'error', '브라우저에서 알림을 지원하지 않습니다');
            return;
        }

        try {
            const permission = await Notification.requestPermission();
            this.notificationPermission = permission;

            if (permission === 'granted') {
                this.browserNotificationEnabled = true;
                this.saveNotificationSetting(true);
                this.showToast('알림 허용', 'success', '브라우저 알림이 활성화되었습니다');
            } else {
                this.browserNotificationEnabled = false;
                this.saveNotificationSetting(false);
                this.showToast('알림 비활성', 'warning', '브라우저 알림을 사용할 수 없습니다');
            }
        } catch (error) {
            this.showToast('권한 오류', 'error', '알림 권한 요청 중 오류가 발생했습니다');
        }
    }

    toggleBrowserNotifications(enabled) {
        this.browserNotificationEnabled = enabled;
        this.saveNotificationSetting(enabled);

        if (enabled && this.notificationPermission !== 'granted') {
            this.requestNotificationPermission();
        } else {
            this.showToast(
                enabled ? '브라우저 알림 활성화' : '브라우저 알림 비활성화',
                'info',
                enabled ? '새로운 데이터 발견 시 브라우저 알림을 받습니다' : '브라우저 알림이 비활성화되었습니다'
            );
        }
    }

    showBrowserNotification(title, message, data = {}) {
        if (!this.shouldShowBrowserNotification(data)) {
            return false;
        }

        try {
            const notification = new Notification(title, {
                body: message,
                icon: '/static/favicon.ico',
                badge: '/static/favicon.ico',
                tag: data.site_key || 'taxupdater',
                data,
                requireInteraction: data.urgency_level === 'high',
                silent: false
            });

            notification.onclick = (event) => {
                event.preventDefault();
                window.focus();

                if (data.site_key && !['system', 'all_sites'].includes(data.site_key)) {
                    window.location.href = `/data/${data.site_key}`;
                }

                notification.close();
            };

            if (data.urgency_level !== 'high') {
                setTimeout(() => {
                    notification.close();
                }, 8000);
            }

            return true;
        } catch (error) {
            return false;
        }
    }

    shouldShowBrowserNotification(data = {}) {
        if (this.notificationPermission !== 'granted') return false;
        if (!this.browserNotificationEnabled) return false;
        if (this.isPageVisible) return false;

        if (data.site_key && this.isNotificationTooFrequent(data.site_key)) {
            return false;
        }

        return true;
    }

    isNotificationTooFrequent(siteKey) {
        const now = Date.now();
        const lastTime = this.lastNotificationTime.get(siteKey);
        const minInterval = 5 * 60 * 1000;

        if (lastTime && now - lastTime < minInterval) {
            return true;
        }

        this.lastNotificationTime.set(siteKey, now);
        return false;
    }

    loadNotificationSetting() {
        try {
            const saved = localStorage.getItem('taxupdater_browser_notifications');
            return saved ? JSON.parse(saved) : false;
        } catch (error) {
            return false;
        }
    }

    saveNotificationSetting(enabled) {
        try {
            localStorage.setItem('taxupdater_browser_notifications', JSON.stringify(enabled));
        } catch (error) {
            return false;
        }
        return true;
    }

    destroy() {
        this.stopAutoRefresh();
        if (this.websocket) {
            this.websocket.close();
        }
    }
}

let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    dashboard = new ExpertDashboard();
    window.dashboard = dashboard;
});

window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.destroy();
    }
});
