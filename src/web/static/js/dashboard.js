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
            'bai': '#6B7280'
        };
        
        this.siteNames = {
            'tax_tribunal': '조세심판원',
            'nts_authority': '국세청(유권해석)',
            'nts_precedent': '국세청(판례)',
            'moef': '기획재정부',
            'mois': '행정안전부',
            'bai': '감사원'
        };
        this.websocket = null;
        this.refreshInterval = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
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
        
        // Refresh button
        document.getElementById('refreshUpdatesBtn')?.addEventListener('click', () => {
            this.loadLatestUpdates();
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
                this.loadStatusCards(); // 데이터 새로고침
                this.loadLatestUpdates(); // 타임라인 새로고침
                break;
            case 'crawl_complete':
                this.showToast('크롤링 완료', 'success', '데이터 수집이 성공적으로 완료되었습니다');
                this.loadStatusCards();
                this.loadLatestUpdates();
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
                this.loadStatusCards(),
                this.loadLatestUpdates()
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
            // 대시보드 데이터와 신규 데이터 수 로드
            const [dashboardResponse, newDataResponse] = await Promise.all([
                fetch('/api/dashboard'),
                fetch(`/api/new-data?hours=${this.currentTimeFilter}&limit=1000`)
            ]);
            
            const dashboardData = await dashboardResponse.json();
            const newDataData = await newDataResponse.json();
            
            this.renderStatusCards(dashboardData.sites || [], newDataData.new_data || []);
        } catch (error) {
            console.error('상태 카드 로드 실패:', error);
            this.showToast('로드 오류', 'error', '사이트 상태 데이터를 불러오는데 실패했습니다');
        }
    }
    
    renderStatusCards(sites, newDataItems) {
        const container = document.getElementById('statusCardsGrid');
        if (!container) return;
        
        container.innerHTML = '';
        
        // 사이트별로 신규 데이터 그룹화
        const newDataBySite = {};
        newDataItems.forEach(item => {
            const siteKey = item.site_key;
            if (!newDataBySite[siteKey]) {
                newDataBySite[siteKey] = [];
            }
            newDataBySite[siteKey].push(item);
        });
        
        sites.forEach(site => {
            const card = this.createStatusCard(site, newDataBySite[site.site_key] || []);
            container.appendChild(card);
        });
    }
    
    createStatusCard(site, newDataItems) {
        const card = document.createElement('div');
        card.className = 'status-card';
        card.style.setProperty('--card-color', this.siteColors[site.site_key] || '#6B7280');
        
        // 상태 결정
        let status = 'inactive';
        let statusText = '비활성';
        
        if (site.total_count > 0) {
            status = newDataItems.length > 0 ? 'active' : 'inactive';
            statusText = newDataItems.length > 0 ? '활성' : '새 데이터 없음';
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
                <div class="new-data-count">+${newDataItems.length}</div>
                <div class="new-data-label">${this.formatTimeFilter()} 신규 항목</div>
            </div>
            <div class="card-footer">
                <span class="last-update">마지막 업데이트: ${lastUpdate}</span>
                <div class="card-actions">
                    <button class="btn btn-primary btn-sm" onclick="dashboard.viewSiteData('${site.site_key}')">
                        데이터 보기
                    </button>
                </div>
            </div>
        `;
        
        // 전체 카드에 클릭 핸들러 추가
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.card-actions')) {
                this.viewSiteData(site.site_key);
            }
        });
        
        return card;
    }
    
    async loadLatestUpdates() {
        try {
            const response = await fetch('/api/notifications?limit=10');
            const data = await response.json();
            
            this.renderLatestUpdates(data.notifications || []);
        } catch (error) {
            console.error('Failed to load latest updates:', error);
            this.showToast('로드 오류', 'error', '최신 업데이트 로드에 실패했습니다');
        }
    }
    
    renderLatestUpdates(notifications) {
        const container = document.getElementById('updatesTimeline');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (notifications.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-title">최근 업데이트 없음</div>
                    <div class="empty-state-description">표시할 최근 활동이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        notifications.forEach(notification => {
            const item = this.createTimelineItem(notification);
            container.appendChild(item);
        });
    }
    
    createTimelineItem(notification) {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        
        const relativeTime = this.formatRelativeTime(new Date(notification.created_at));
        const siteKey = this.extractSiteKeyFromNotification(notification);
        const badgeColor = this.siteColors[siteKey] || '#6B7280';
        
        item.innerHTML = `
            <div class="timeline-header">
                <h4 class="timeline-title">${notification.title}</h4>
                <div class="timeline-meta">
                    ${siteKey ? `<span class="organization-badge" style="--badge-color: ${badgeColor}; --badge-text-color: white; background: ${badgeColor};">${this.getSiteName(siteKey)}</span>` : ''}
                    <span>${relativeTime}</span>
                </div>
            </div>
            <div class="timeline-description">${notification.message}</div>
        `;
        
        return item;
    }
    
    extractSiteKeyFromNotification(notification) {
        // Try to extract site key from notification context
        if (notification.metadata) {
            try {
                const metadata = typeof notification.metadata === 'string' ? 
                    JSON.parse(notification.metadata) : notification.metadata;
                return metadata.site_key;
            } catch (e) {
                // Ignore parsing errors
            }
        }
        
        // Fallback: try to match site names in the message
        const message = notification.message.toLowerCase();
        for (const [siteKey, color] of Object.entries(this.siteColors)) {
            const siteName = this.getSiteName(siteKey).toLowerCase();
            if (message.includes(siteName)) {
                return siteKey;
            }
        }
        
        return null;
    }
    
    getSiteName(siteKey) {
        const siteNames = {
            'tax_tribunal': '조세심판원',
            'nts_authority': '국세청(유권해석)',
            'nts_precedent': '국세청(판례)',
            'moef': '기획재정부',
            'mois': '행정안전부',
            'bai': '감사원'
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
    
    viewSiteData(siteKey) {
        // Navigate to data table view for this site
        window.location.href = `/data/${siteKey}`;
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
            this.loadLatestUpdates();
        }, 5 * 60 * 1000);
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
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