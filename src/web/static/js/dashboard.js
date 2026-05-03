/**
 * Tax Law Monitoring Dashboard - Modern Expert UI
 * Professional dashboard for busy tax law experts
 */

class ExpertDashboard {
    constructor() {
        this.currentTimeFilter = 24; // Default: last 24 hours
        this.siteColors = {
            'tax_tribunal': '#4F46E5',
            'nts_authority': '#059669',
            'nts_precedent': '#D97706',
            'moef': '#8B5CF6',
            'mois': '#DC2626',
            'bai': '#6B7280',
            'scourt_major_decisions': '#0F766E'
        };
        
        this.siteNames = {
            'tax_tribunal': '조세심판원',
            'nts_authority': '국세청(유권해석)',
            'nts_precedent': '국세청(판례)',
            'moef': '기획재정부',
            'mois': '행정안전부',
            'bai': '감사원',
            'scourt_major_decisions': '전국법원 주요판결'
        };
        this.websocket = null;
        this.refreshInterval = null;
        
        // 브라우저 알림 관련 설정
        this.browserNotificationEnabled = this.loadNotificationSetting();
        this.notificationPermission = 'default';
        this.isPageVisible = true;
        this.lastNotificationTime = new Map(); // 사이트별 마지막 알림 시간
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initBrowserNotifications();
        this.connectWebSocket();
        this.loadInitialData();
        this.startAutoRefresh();
        
        console.log('전문가 대시보드 초기화 완료');
    }
    
    setupEventListeners() {
        // Time filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.setTimeFilter(parseInt(e.target.dataset.hours));
            });
        });
        
        // Date range picker
        document.getElementById('applyDateRange')?.addEventListener('click', () => {
            this.applyCustomDateRange();
        });
        
        // Settings button
        document.getElementById('settingsBtn')?.addEventListener('click', () => {
            window.location.href = '/settings';
        });
        
        // 페이지 가시성 추적
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
                console.log('WebSocket 연결됨');
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
                console.warn('WebSocket 연결 끊어짐');
                this.updateConnectionStatus(false);
                
                // 5초 후 자동 재연결
                setTimeout(() => {
                    this.connectWebSocket();
                }, 5000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    updateConnectionStatus(isConnected) {
        const statusElement = document.getElementById('connectionStatus');
        const dotElement = statusElement?.querySelector('.indicator-dot');
        const textElement = statusElement?.querySelector('span');
        
        if (dotElement && textElement) {
            if (isConnected) {
                dotElement.style.background = '#10B981';
                textElement.textContent = '연결됨';
            } else {
                dotElement.style.background = '#EF4444';
                textElement.textContent = '연결 끊어짐';
            }
        }
    }
    
    handleWebSocketMessage(message) {
        console.log('WebSocket message:', message);
        
        switch (message.type) {
            case 'notification':
                this.showToast('새로운 업데이트', 'success', message.title);
                
                // 브라우저 푸시 알림 표시 (페이지가 비활성화된 경우)
                this.showBrowserNotification(message.title, message.message, {
                    site_key: message.site_key,
                    urgency_level: message.urgency_level,
                    new_data_count: message.new_data_count,
                    notification_type: message.notification_type
                });
                
                this.loadStatusCards(); // 데이터 새로고침
                break;
            case 'crawl_complete':
                this.showToast('크롤링 완료', 'success', '데이터 수집이 성공적으로 완료되었습니다');
                this.loadStatusCards();
                break;
            case 'crawl_error':
                this.showToast('크롤링 오류', 'error', `오류: ${message.error}`);
                break;
        }
    }
    
    async loadInitialData() {
        this.showLoading(true);
        
        try {
            await Promise.all([
                this.loadStatusCards()
            ]);
        } catch (error) {
            console.error('초기 데이터 로드 실패:', error);
            this.showToast('로드 오류', 'error', '대시보드 데이터를 불러오는데 실패했습니다');
        } finally {
            this.showLoading(false);
        }
    }
    
    setTimeFilter(hours) {
        this.currentTimeFilter = hours;
        
        // Update active button
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-hours="${hours}"]`).classList.add('active');
        
        // Reload data with new filter
        this.loadStatusCards();
    }
    
    applyCustomDateRange() {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        
        if (startDate && endDate) {
            // 시간 차이 계산
            const start = new Date(startDate);
            const end = new Date(endDate);
            const diffHours = Math.ceil((end - start) / (1000 * 60 * 60));
            
            this.currentTimeFilter = diffHours;
            this.loadStatusCards();
            
            // 활성 필터 버튼 초기화
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
        }
    }
    
    async loadStatusCards() {
        try {
            // 대시보드 데이터와 최근 데이터 개수 로드
            const [dashboardResponse, recentCountsResponse] = await Promise.all([
                fetch('/api/dashboard'),
                fetch(`/api/sites/recent-counts?hours=${this.currentTimeFilter}`)
            ]);
            
            const dashboardData = await dashboardResponse.json();
            const recentCountsData = await recentCountsResponse.json();
            
            this.renderStatusCards(dashboardData.sites || [], recentCountsData.recent_counts || {});
        } catch (error) {
            console.error('상태 카드 로드 실패:', error);
            this.showToast('로드 오류', 'error', '사이트 상태 데이터를 불러오는데 실패했습니다');
        }
    }
    
    renderStatusCards(sites, recentCounts) {
        const container = document.getElementById('statusCardsGrid');
        if (!container) return;
        
        container.innerHTML = '';
        
        sites.forEach(site => {
            const recentCount = recentCounts[site.site_key]?.count || 0;
            const card = this.createStatusCard(site, recentCount);
            container.appendChild(card);
        });
    }
    
    createStatusCard(site, recentCount) {
        const card = document.createElement('div');
        card.className = 'status-card';
        card.style.setProperty('--card-color', this.siteColors[site.site_key] || '#6B7280');
        
        // 상태 결정
        let status = 'inactive';
        let statusText = '비활성';
        
        if (site.total_count > 0) {
            status = recentCount > 0 ? 'active' : 'inactive';
            statusText = recentCount > 0 ? '활성' : '새 데이터 없음';
        }
        
        // 마지막 업데이트 시간 포맷
        const lastUpdate = site.last_updated ? 
            this.formatRelativeTime(new Date(site.last_updated)) : 
            '없음';
        
        card.innerHTML = `
            <div class="card-header">
                <h3 class="card-organization">${this.siteNames[site.site_key] || site.site_name}</h3>
                <span class="card-status ${status}">${statusText}</span>
            </div>
            <div class="card-metrics">
                <div class="new-data-count">+${recentCount}</div>
                <div class="new-data-label">${this.formatTimeFilter()} 신규 항목</div>
            </div>
            <div class="card-footer">
                <span class="last-update">마지막 업데이트: ${lastUpdate}</span>
                <div class="card-actions">
                    <button class="btn btn-primary btn-sm" onclick="dashboard.viewSiteData('${site.site_key}', false)">
                        데이터 보기
                    </button>
                </div>
            </div>
        `;
        
        // 전체 카드에 클릭 핸들러 추가
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.card-actions')) {
                this.viewSiteData(site.site_key, true); // 카드 클릭 시 필터링된 데이터
            }
        });
        
        return card;
    }
    
    getSiteName(siteKey) {
        const siteNames = {
            'tax_tribunal': '조세심판원',
            'nts_authority': '국세청(유권해석)',
            'nts_precedent': '국세청(판례)',
            'moef': '기획재정부',
            'mois': '행정안전부',
            'bai': '감사원',
            'scourt_major_decisions': '전국법원 주요판결'
        };
        return siteNames[siteKey] || siteKey;
    }
    
    formatTimeFilter() {
        if (this.currentTimeFilter === 24) return '최근 24시간';
        if (this.currentTimeFilter === 72) return '최근 3일';
        if (this.currentTimeFilter === 168) return '최근 7일';
        
        const days = Math.ceil(this.currentTimeFilter / 24);
        return `최근 ${days}일`;
    }
    
    formatRelativeTime(date) {
        const now = new Date();
        const diffInMinutes = Math.floor((now - date) / (1000 * 60));
        
        if (diffInMinutes < 1) return '방금 전';
        if (diffInMinutes < 60) return `${diffInMinutes}분 전`;
        
        const diffInHours = Math.floor(diffInMinutes / 60);
        if (diffInHours < 24) return `${diffInHours}시간 전`;
        
        const diffInDays = Math.floor(diffInHours / 24);
        if (diffInDays < 7) return `${diffInDays}일 전`;
        
        return date.toLocaleDateString('ko-KR');
    }
    
    viewSiteData(siteKey, isFiltered = false) {
        // Navigate to data table view for this site
        if (isFiltered) {
            // 카드 클릭 - 필터링된 데이터 보기
            let url = `/data/${siteKey}?filter=recent`;
            
            if (this.currentTimeFilter === 24) {
                url += '&days=1';
            } else if (this.currentTimeFilter === 72) {
                url += '&days=3';
            } else if (this.currentTimeFilter === 168) {
                url += '&days=7';
            } else {
                // 사용자 정의 날짜 범위
                const startDate = document.getElementById('startDate')?.value;
                const endDate = document.getElementById('endDate')?.value;
                if (startDate && endDate) {
                    url = `/data/${siteKey}?filter=range&start=${startDate}&end=${endDate}`;
                } else {
                    // 일수로 계산
                    const days = Math.ceil(this.currentTimeFilter / 24);
                    url += `&days=${days}`;
                }
            }
            
            window.location.href = url;
        } else {
            // 데이터 보기 버튼 클릭 - 전체 데이터 보기
            window.location.href = `/data/${siteKey}`;
        }
    }
    
    showToast(title, type, message) {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        toast.innerHTML = `
            <div><strong>${title}</strong></div>
            <div>${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Show animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 5000);
    }
    
    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            if (show) {
                overlay.classList.add('show');
            } else {
                overlay.classList.remove('show');
            }
        }
    }
    
    startAutoRefresh() {
        // Refresh data every 5 minutes
        this.refreshInterval = setInterval(() => {
            this.loadStatusCards();
        }, 5 * 60 * 1000);
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    // 브라우저 알림 관련 메서드들
    async initBrowserNotifications() {
        // 브라우저 알림 지원 여부 확인
        if (!('Notification' in window)) {
            console.warn('브라우저에서 알림을 지원하지 않습니다');
            this.updateNotificationUI('unsupported');
            return;
        }
        
        // 현재 권한 상태 확인
        this.notificationPermission = Notification.permission;
        console.log('브라우저 알림 권한 상태:', this.notificationPermission);
        
        // UI 업데이트
        this.updateNotificationUI(this.notificationPermission);
        
        // 권한이 있고 설정이 활성화되어 있으면 알림 준비
        if (this.notificationPermission === 'granted' && this.browserNotificationEnabled) {
            console.log('브라우저 알림 활성화됨');
        }
    }
    
    async requestNotificationPermission() {
        if (!('Notification' in window)) {
            this.showToast('알림 지원 안됨', 'error', '브라우저에서 알림을 지원하지 않습니다');
            return;
        }
        
        try {
            const permission = await Notification.requestPermission();
            this.notificationPermission = permission;
            this.updateNotificationUI(permission);
            
            if (permission === 'granted') {
                this.showToast('알림 권한 허용', 'success', '브라우저 알림이 활성화되었습니다');
                // 권한을 받으면 자동으로 알림 활성화
                this.browserNotificationEnabled = true;
                this.saveNotificationSetting(true);
            } else {
                this.showToast('알림 권한 거부', 'warning', '브라우저 알림을 사용할 수 없습니다');
                this.browserNotificationEnabled = false;
                this.saveNotificationSetting(false);
            }
        } catch (error) {
            console.error('알림 권한 요청 실패:', error);
            this.showToast('권한 요청 실패', 'error', '알림 권한 요청 중 오류가 발생했습니다');
        }
    }
    
    toggleBrowserNotifications(enabled) {
        this.browserNotificationEnabled = enabled;
        this.saveNotificationSetting(enabled);
        
        if (enabled && this.notificationPermission !== 'granted') {
            // 권한이 없으면 요청
            this.requestNotificationPermission();
        } else {
            this.showToast(
                enabled ? '브라우저 알림 활성화' : '브라우저 알림 비활성화',
                'info',
                enabled ? '새로운 데이터 발견 시 브라우저 알림을 받습니다' : '브라우저 알림이 비활성화되었습니다'
            );
        }
    }
    
    updateNotificationUI(permission) {
        const toggle = document.getElementById('notificationToggle');
        const permissionBtn = document.getElementById('requestNotificationPermissionBtn');
        const statusElement = document.getElementById('notificationPermissionStatus');
        
        if (toggle) {
            toggle.checked = this.browserNotificationEnabled;
            toggle.disabled = permission === 'denied' || permission === 'unsupported';
        }
        
        if (permissionBtn) {
            permissionBtn.style.display = permission === 'default' ? 'inline-block' : 'none';
        }
        
        if (statusElement) {
            const statusMap = {
                'granted': { text: '허용됨', class: 'success' },
                'denied': { text: '거부됨', class: 'error' },
                'default': { text: '미설정', class: 'warning' },
                'unsupported': { text: '지원 안됨', class: 'error' }
            };
            
            const status = statusMap[permission] || statusMap['default'];
            statusElement.textContent = status.text;
            statusElement.className = `notification-status ${status.class}`;
        }
    }
    
    showBrowserNotification(title, message, data = {}) {
        // 브라우저 알림 표시 조건 확인
        if (!this.shouldShowBrowserNotification(data)) {
            return false;
        }
        
        try {
            const options = {
                body: message,
                icon: '/static/favicon.ico',
                badge: '/static/favicon.ico',
                tag: data.site_key || 'taxupdater',
                data: data,
                requireInteraction: data.urgency_level === 'high',
                silent: false
            };
            
            const notification = new Notification(title, options);
            
            // 알림 클릭 이벤트
            notification.onclick = (event) => {
                event.preventDefault();
                window.focus();
                
                // 사이트 키가 있으면 해당 페이지로 이동
                if (data.site_key && data.site_key !== 'system' && data.site_key !== 'all_sites') {
                    window.location.href = `/data/${data.site_key}`;
                }
                
                notification.close();
            };
            
            // 자동 닫기 (중요도가 높지 않은 경우)
            if (data.urgency_level !== 'high') {
                setTimeout(() => {
                    notification.close();
                }, 8000);
            }
            
            console.log('브라우저 알림 표시:', title);
            return true;
            
        } catch (error) {
            console.error('브라우저 알림 표시 실패:', error);
            return false;
        }
    }
    
    shouldShowBrowserNotification(data = {}) {
        // 권한이 없으면 표시하지 않음
        if (this.notificationPermission !== 'granted') {
            return false;
        }
        
        // 사용자가 비활성화했으면 표시하지 않음
        if (!this.browserNotificationEnabled) {
            return false;
        }
        
        // 페이지가 활성화되어 있으면 토스트만 표시 (브라우저 알림 중복 방지)
        if (this.isPageVisible) {
            return false;
        }
        
        // 알림 빈도 제한 (같은 사이트에서 5분 이내 중복 알림 방지)
        if (data.site_key && this.isNotificationTooFrequent(data.site_key)) {
            console.log(`알림 빈도 제한: ${data.site_key}`);
            return false;
        }
        
        return true;
    }
    
    isNotificationTooFrequent(siteKey) {
        const now = Date.now();
        const lastTime = this.lastNotificationTime.get(siteKey);
        const minInterval = 5 * 60 * 1000; // 5분
        
        if (lastTime && (now - lastTime) < minInterval) {
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
            console.error('알림 설정 로드 실패:', error);
            return false;
        }
    }
    
    saveNotificationSetting(enabled) {
        try {
            localStorage.setItem('taxupdater_browser_notifications', JSON.stringify(enabled));
        } catch (error) {
            console.error('알림 설정 저장 실패:', error);
        }
    }
    
    
    destroy() {
        this.stopAutoRefresh();
        if (this.websocket) {
            this.websocket.close();
        }
    }
}

// Initialize dashboard when DOM is loaded
let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    dashboard = new ExpertDashboard();
    window.dashboard = dashboard; // Make it globally accessible
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.destroy();
    }
});
