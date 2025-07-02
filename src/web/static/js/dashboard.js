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
        this.restoreCollapseState();
        
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
        
        // Clear history button
        document.getElementById('clearHistoryBtn')?.addEventListener('click', () => {
            this.clearJobHistory();
        });
        
        // Instant crawl button
        document.getElementById('instantCrawlBtn')?.addEventListener('click', () => {
            this.startInstantCrawling();
        });
        
        // Collapse toggle button
        document.getElementById('collapseToggle')?.addEventListener('click', () => {
            this.toggleCollapseSection();
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
                this.restoreInstantCrawlButton(); // 크롤링 완료 시 버튼 복원
                break;
            case 'crawl_error':
                this.showToast('크롤링 오류', 'error', `오류: ${message.error}`);
                this.restoreInstantCrawlButton(); // 크롤링 에러 시 버튼 복원
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
    
    async loadLatestUpdates() {
        try {
            const response = await fetch('/api/job-history?limit=10');
            const data = await response.json();
            
            this.renderLatestUpdates(data.job_history || []);
        } catch (error) {
            console.error('Failed to load crawling progress:', error);
            this.showToast('로드 오류', 'error', '크롤링 현황 로드에 실패했습니다');
        }
    }
    
    async clearJobHistory() {
        if (!confirm('크롤링 진행현황을 모두 삭제하시겠습니까?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/job-history', {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showToast('삭제 완료', 'success', data.message);
                this.loadLatestUpdates(); // 목록 새로고침
            } else {
                this.showToast('삭제 실패', 'error', data.detail || '진행현황 삭제에 실패했습니다');
            }
        } catch (error) {
            console.error('Failed to clear job history:', error);
            this.showToast('삭제 실패', 'error', '진행현황 삭제 중 오류가 발생했습니다');
        }
    }
    
    async startInstantCrawling() {
        try {
            console.log('즉시 탐색 시작');
            
            // 버튼 비활성화
            const btn = document.getElementById('instantCrawlBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
                        <path d="M12 6v6l4 2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    탐색 중...
                `;
            }
            
            const response = await fetch('/api/crawl/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) throw new Error('즉시 탐색 시작 실패');
            
            const result = await response.json();
            this.showToast('즉시 탐색 시작', 'success', '전체 사이트 크롤링을 시작했습니다. 진행상황을 확인하세요.');
            
        } catch (error) {
            console.error('즉시 탐색 오류:', error);
            this.showToast('탐색 실패', 'error', '즉시 탐색 시작에 실패했습니다.');
            // 에러 발생 시에만 즉시 복원
            this.restoreInstantCrawlButton();
        }
    }
    
    restoreInstantCrawlButton() {
        const btn = document.getElementById('instantCrawlBtn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                즉시 탐색
            `;
        }
    }
    
    renderLatestUpdates(jobHistory) {
        const container = document.getElementById('updatesTimeline');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (jobHistory.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">-</div>
                    <div class="empty-state-title">크롤링 이력 없음</div>
                    <div class="empty-state-description">최근 실행된 크롤링 작업이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        jobHistory.forEach(job => {
            const item = this.createJobTimelineItem(job);
            container.appendChild(item);
        });
    }
    
    createJobTimelineItem(job) {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        
        const startTime = new Date(job.start_time);
        const relativeTime = this.formatRelativeTime(startTime);
        const siteKey = job.site_key;
        const badgeColor = this.siteColors[siteKey] || '#6B7280';
        
        // 상태에 따른 아이콘과 색상
        let statusIcon = '◯';
        let statusClass = 'status-running';
        let statusText = '실행 중';
        
        if (job.status === 'completed' || job.status === 'success') {
            statusIcon = '●';
            statusClass = 'status-success';
            statusText = '완료';
        } else if (job.status === 'failed') {
            statusIcon = '×';
            statusClass = 'status-error';
            statusText = '실패';
        } else if (job.status === 'partial_success') {
            statusIcon = '!';
            statusClass = 'status-warning';
            statusText = '부분 성공';
        } else if (job.status === 'running') {
            statusIcon = '◯';
            statusClass = 'status-running';
            statusText = '실행 중';
        }
        
        // 실행 시간 계산
        let duration = '';
        if (job.end_time) {
            const endTime = new Date(job.end_time);
            const durationMs = endTime - startTime;
            const seconds = Math.round(durationMs / 1000);
            duration = `${seconds}초`;
        }
        
        // 결과 정보 - 상세 크롤링 통계 표시
        let resultInfo = '';
        if (job.total_crawled !== undefined || job.new_count !== undefined) {
            const parts = [];
            if (job.total_crawled !== undefined) {
                parts.push(`${job.total_crawled}개 수집`);
            }
            if (job.new_count !== undefined) {
                parts.push(`${job.new_count}개 신규`);
            }
            if (job.existing_count !== undefined && job.total_crawled !== undefined) {
                const duplicates = job.total_crawled - job.new_count;
                if (duplicates > 0) {
                    parts.push(`${duplicates}개 중복`);
                }
            }
            if (parts.length > 0) {
                resultInfo = parts.join(', ');
            }
        }
        
        item.innerHTML = `
            <div class="timeline-header">
                <h4 class="timeline-title">
                    ${statusIcon} ${this.getSiteName(siteKey)} 크롤링 ${statusText}
                </h4>
                <div class="timeline-meta">
                    <span class="organization-badge" style="--badge-color: ${badgeColor}; --badge-text-color: white; background: ${badgeColor};">
                        ${this.getSiteName(siteKey)}
                    </span>
                    <span class="job-status ${statusClass}">${statusText}</span>
                    <span>${relativeTime}</span>
                </div>
            </div>
            <div class="timeline-description">
                실행 시간: ${startTime.toLocaleString('ko-KR')}
                ${duration ? ` (소요시간: ${duration})` : ''}
                ${resultInfo ? ` | ${resultInfo}` : ''}
                ${job.error_message ? `<br><span class="error-message">오류: ${job.error_message}</span>` : ''}
            </div>
        `;
        
        return item;
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
    
    toggleCollapseSection() {
        const toggle = document.getElementById('collapseToggle');
        const content = document.getElementById('updatesTimeline');
        
        if (!toggle || !content) return;
        
        const isCollapsed = content.classList.contains('collapsed');
        
        if (isCollapsed) {
            // Expand
            content.classList.remove('collapsed');
            toggle.classList.remove('collapsed');
        } else {
            // Collapse
            content.classList.add('collapsed');
            toggle.classList.add('collapsed');
        }
        
        // Save state to localStorage
        localStorage.setItem('crawlingStatusCollapsed', !isCollapsed);
    }
    
    restoreCollapseState() {
        const isCollapsed = localStorage.getItem('crawlingStatusCollapsed') === 'true';
        
        if (isCollapsed) {
            const toggle = document.getElementById('collapseToggle');
            const content = document.getElementById('updatesTimeline');
            
            if (toggle && content) {
                content.classList.add('collapsed');
                toggle.classList.add('collapsed');
            }
        }
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