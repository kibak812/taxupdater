/**
 * 세금 법령 자동 모니터링 시스템 - JavaScript
 * 실시간 모니터링, 스케줄 관리, 알림 센터 등의 기능을 제공
 */

class MonitoringApp {
    constructor() {
        this.currentTab = 'monitoring';
        this.websocket = null;
        this.websocketReconnectDelay = 5000;
        this.refreshIntervals = new Map();
        this.siteInfo = {};
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialData();
        this.startPeriodicRefresh();
        
        console.log('🔍 모니터링 시스템 초기화 완료');
    }
    
    setupEventListeners() {
        // 탭 네비게이션
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            });
        });
        
        // 새로고침 버튼들
        document.getElementById('refreshDashboardBtn')?.addEventListener('click', () => {
            this.loadDashboardData();
        });
        
        document.getElementById('refreshSchedulesBtn')?.addEventListener('click', () => {
            this.loadSchedules();
        });
        
        document.getElementById('refreshNotificationsBtn')?.addEventListener('click', () => {
            this.loadNotifications();
        });
        
        document.getElementById('refreshNewDataBtn')?.addEventListener('click', () => {
            this.loadNewData();
        });
        
        // 스케줄러 제어
        document.getElementById('startAllSchedulerBtn')?.addEventListener('click', () => {
            this.startScheduler();
        });
        
        // 스케줄 관리
        document.getElementById('addScheduleBtn')?.addEventListener('click', () => {
            this.showScheduleModal();
        });
        
        document.getElementById('scheduleModalClose')?.addEventListener('click', () => {
            this.hideScheduleModal();
        });
        
        document.getElementById('scheduleModalCancel')?.addEventListener('click', () => {
            this.hideScheduleModal();
        });
        
        document.getElementById('scheduleModalSave')?.addEventListener('click', () => {
            this.saveSchedule();
        });
        
        // 알림 필터
        document.getElementById('notificationFilter')?.addEventListener('change', () => {
            this.loadNotifications();
        });
        
        document.getElementById('markAllReadBtn')?.addEventListener('click', () => {
            this.markAllNotificationsRead();
        });
        
        // 새로운 데이터 필터
        document.getElementById('newDataSiteFilter')?.addEventListener('change', () => {
            this.loadNewData();
        });
        
        document.getElementById('newDataTimeFilter')?.addEventListener('change', () => {
            this.loadNewData();
        });
        
        // 모달 외부 클릭 시 닫기
        document.getElementById('scheduleModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'scheduleModal') {
                this.hideScheduleModal();
            }
        });
    }
    
    async connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/crawl`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('✅ WebSocket 연결 성공');
                this.updateConnectionStatus(true);
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('WebSocket 메시지 파싱 오류:', error);
                }
            };
            
            this.websocket.onclose = () => {
                console.warn('⚠️ WebSocket 연결 끊어짐');
                this.updateConnectionStatus(false);
                
                // 자동 재연결
                setTimeout(() => {
                    this.connectWebSocket();
                }, this.websocketReconnectDelay);
            };
            
            this.websocket.onerror = (error) => {
                console.error('❌ WebSocket 오류:', error);
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('WebSocket 연결 초기화 실패:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    updateConnectionStatus(isConnected) {
        const indicator = document.getElementById('connectionIndicator');
        const text = document.getElementById('connectionText');
        
        if (indicator && text) {
            if (isConnected) {
                indicator.className = 'connection-indicator connected';
                text.textContent = '실시간 연결 상태: 연결됨 ✅';
            } else {
                indicator.className = 'connection-indicator disconnected';
                text.textContent = '실시간 연결 상태: 연결 끊어짐 ❌';
            }
        }
    }
    
    handleWebSocketMessage(message) {
        console.log('📨 WebSocket 메시지:', message);
        
        switch (message.type) {
            case 'notification':
                this.handleNotificationMessage(message);
                break;
            case 'crawl_start':
                this.handleCrawlStart(message);
                break;
            case 'crawl_progress':
                this.handleCrawlProgress(message);
                break;
            case 'crawl_status':
                this.handleCrawlStatus(message);
                break;
            case 'crawl_complete':
                this.handleCrawlComplete(message);
                break;
            case 'crawl_error':
                this.handleCrawlError(message);
                break;
        }
    }
    
    handleNotificationMessage(message) {
        // 새로운 알림을 토스트로 표시
        this.showToast(message.title, message.urgency_level, message.message);
        
        // 알림 카운터 업데이트
        this.updateNotificationCounter();
        
        // 현재 알림 탭이 활성화되어 있으면 새로고침
        if (this.currentTab === 'notifications') {
            this.loadNotifications();
        }
    }
    
    handleCrawlStart(message) {
        this.showToast('크롤링 시작', 'info', `크롤링이 시작되었습니다.`);
    }
    
    handleCrawlProgress(message) {
        // 진행률 표시 (필요한 경우)
        console.log(`크롤링 진행률: ${message.progress}%`);
    }
    
    handleCrawlStatus(message) {
        // 상태 메시지 표시
        console.log(`크롤링 상태: ${message.status}`);
    }
    
    handleCrawlComplete(message) {
        this.showToast('크롤링 완료', 'success', '크롤링이 성공적으로 완료되었습니다.');
        
        // 대시보드 데이터 새로고침
        if (this.currentTab === 'monitoring') {
            this.loadDashboardData();
        }
    }
    
    handleCrawlError(message) {
        this.showToast('크롤링 오류', 'error', `크롤링 중 오류가 발생했습니다: ${message.error}`);
    }
    
    switchTab(tabName) {
        // 모든 탭 콘텐츠 숨기기
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        // 모든 탭 버튼 비활성화
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        
        // 선택된 탭 활성화
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        this.currentTab = tabName;
        
        // 탭별 데이터 로드
        this.loadTabData(tabName);
    }
    
    loadTabData(tabName) {
        switch (tabName) {
            case 'monitoring':
                this.loadDashboardData();
                break;
            case 'schedules':
                this.loadSchedules();
                break;
            case 'notifications':
                this.loadNotifications();
                break;
            case 'new-data':
                this.loadNewData();
                break;
            case 'system':
                this.loadSystemStatus();
                this.loadJobHistory();
                break;
        }
    }
    
    async loadInitialData() {
        try {
            // 사이트 정보 로드
            await this.loadSiteInfo();
            
            // 초기 대시보드 데이터 로드
            await this.loadDashboardData();
            
        } catch (error) {
            console.error('초기 데이터 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '초기 데이터를 불러오는데 실패했습니다.');
        }
    }
    
    async loadSiteInfo() {
        try {
            const response = await fetch('/api/dashboard');
            const data = await response.json();
            
            if (data.sites) {
                this.siteInfo = {};
                data.sites.forEach(site => {
                    this.siteInfo[site.site_key] = site;
                });
            }
            
        } catch (error) {
            console.error('사이트 정보 로드 실패:', error);
        }
    }
    
    async loadDashboardData() {
        try {
            const [dashboardResponse, statsResponse, schedulesResponse, notificationsResponse] = await Promise.all([
                fetch('/api/dashboard'),
                fetch('/api/stats'),
                fetch('/api/schedules'),
                fetch('/api/notifications?limit=10')
            ]);
            
            const dashboardData = await dashboardResponse.json();
            const statsData = await statsResponse.json();
            const schedulesData = await schedulesResponse.json();
            const notificationsData = await notificationsResponse.json();
            
            this.updateOverallStats(dashboardData, statsData, schedulesData, notificationsData);
            this.updateSitesGrid(dashboardData.sites || []);
            this.updateRecentActivity(notificationsData.notifications || []);
            
        } catch (error) {
            console.error('대시보드 데이터 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '대시보드 데이터를 불러오는데 실패했습니다.');
        }
    }
    
    updateOverallStats(dashboardData, statsData, schedulesData, notificationsData) {
        // 총 데이터 수
        const totalDataElement = document.getElementById('totalDataCount');
        if (totalDataElement) {
            totalDataElement.textContent = (statsData.total_records || 0).toLocaleString();
        }
        
        // 활성 스케줄 수
        const activeScheduleElement = document.getElementById('activeScheduleCount');
        if (activeScheduleElement && schedulesData.schedules) {
            const activeCount = schedulesData.schedules.filter(s => s.enabled).length;
            activeScheduleElement.textContent = activeCount;
        }
        
        // 읽지 않은 알림 수
        const unreadNotificationElement = document.getElementById('unreadNotificationCount');
        if (unreadNotificationElement && notificationsData.notifications) {
            const unreadCount = notificationsData.notifications.filter(n => !n.read_at).length;
            unreadNotificationElement.textContent = unreadCount;
        }
        
        // 새로운 데이터 수 (별도 로드)
        this.loadNewDataCount();
    }
    
    async loadNewDataCount() {
        try {
            const response = await fetch('/api/new-data?hours=24&limit=1000');
            const data = await response.json();
            
            const newDataElement = document.getElementById('newDataCount');
            if (newDataElement) {
                newDataElement.textContent = data.total_count || 0;
            }
            
        } catch (error) {
            console.error('새로운 데이터 수 로드 실패:', error);
        }
    }
    
    updateSitesGrid(sites) {
        const container = document.getElementById('sitesGrid');
        if (!container) return;
        
        container.innerHTML = '';
        
        sites.forEach(site => {
            const card = this.createSiteMonitoringCard(site);
            container.appendChild(card);
        });
    }
    
    createSiteMonitoringCard(site) {
        const card = document.createElement('div');
        card.className = 'site-monitoring-card fade-in';
        
        // 상태 결정
        let status = 'inactive';
        let statusText = '비활성';
        
        if (site.total_count > 0) {
            status = 'active';
            statusText = '활성';
        }
        
        // 마지막 업데이트 시간 포맷
        const lastUpdated = site.last_updated ? 
            new Date(site.last_updated).toLocaleString('ko-KR') : 
            '없음';
        
        card.innerHTML = `
            <div class="site-monitoring-header">
                <div class="site-monitoring-name">${site.site_name}</div>
                <div class="site-monitoring-status ${status}">${statusText}</div>
            </div>
            <div class="site-monitoring-info">
                <div class="site-info-item">
                    <span class="site-info-label">수집 데이터</span>
                    <span class="site-info-value">${site.total_count.toLocaleString()}건</span>
                </div>
                <div class="site-info-item">
                    <span class="site-info-label">마지막 업데이트</span>
                    <span class="site-info-value">${lastUpdated}</span>
                </div>
            </div>
            <div class="site-monitoring-actions">
                <button class="btn btn-sm btn-primary" onclick="monitoringApp.triggerManualCrawl('${site.site_key}')">
                    🚀 수동 크롤링
                </button>
                <button class="btn btn-sm btn-secondary" onclick="monitoringApp.editSiteSchedule('${site.site_key}')">
                    ⏰ 스케줄 편집
                </button>
                <a href="/sites/${site.site_key}" class="btn btn-sm btn-secondary">
                    📊 상세 보기
                </a>
            </div>
        `;
        
        return card;
    }
    
    updateRecentActivity(notifications) {
        const container = document.getElementById('recentActivity');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (notifications.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-title">최근 활동 없음</div>
                    <div class="empty-state-description">최근 활동 내역이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        notifications.slice(0, 10).forEach(notification => {
            const item = this.createTimelineItem(notification);
            container.appendChild(item);
        });
    }
    
    createTimelineItem(notification) {
        const item = document.createElement('div');
        item.className = 'timeline-item fade-in';
        
        const iconClass = this.getNotificationIconClass(notification.notification_type);
        const iconEmoji = this.getNotificationIconEmoji(notification.notification_type);
        const timeAgo = this.formatTimeAgo(new Date(notification.created_at));
        
        item.innerHTML = `
            <div class="timeline-icon ${iconClass}">
                ${iconEmoji}
            </div>
            <div class="timeline-content">
                <div class="timeline-title">${notification.title}</div>
                <div class="timeline-description">${notification.message}</div>
                <div class="timeline-meta">
                    <span>${timeAgo}</span>
                    <span>${notification.urgency_level}</span>
                </div>
            </div>
        `;
        
        return item;
    }
    
    getNotificationIconClass(type) {
        const classMap = {
            'new_data': 'new-data',
            'error': 'error',
            'system': 'system',
            'schedule': 'system'
        };
        return classMap[type] || 'system';
    }
    
    getNotificationIconEmoji(type) {
        const emojiMap = {
            'new_data': '🆕',
            'error': '❌',
            'system': '⚙️',
            'schedule': '⏰'
        };
        return emojiMap[type] || '📢';
    }
    
    formatTimeAgo(date) {
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
    
    async loadSchedules() {
        try {
            const response = await fetch('/api/schedules');
            const data = await response.json();
            
            this.updateSchedulesContainer(data.schedules || []);
            
        } catch (error) {
            console.error('스케줄 데이터 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '스케줄 데이터를 불러오는데 실패했습니다.');
        }
    }
    
    updateSchedulesContainer(schedules) {
        const container = document.getElementById('schedulesContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (schedules.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⏰</div>
                    <div class="empty-state-title">스케줄 없음</div>
                    <div class="empty-state-description">설정된 크롤링 스케줄이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        schedules.forEach(schedule => {
            const item = this.createScheduleItem(schedule);
            container.appendChild(item);
        });
    }
    
    createScheduleItem(schedule) {
        const item = document.createElement('div');
        item.className = 'schedule-item fade-in';
        
        const nextRun = schedule.scheduler_status?.next_run ? 
            new Date(schedule.scheduler_status.next_run).toLocaleString('ko-KR') : 
            '예정 없음';
        
        const statusClass = schedule.enabled ? 'success' : 'secondary';
        const statusText = schedule.enabled ? '활성' : '비활성';
        
        item.innerHTML = `
            <div class="schedule-info">
                <div class="schedule-site-name">${schedule.site_name}</div>
                <div class="schedule-details">
                    크론: ${schedule.cron_expression} | 다음 실행: ${nextRun}
                </div>
            </div>
            <div class="schedule-status">
                <span class="badge badge-${statusClass}">${statusText}</span>
            </div>
            <div class="schedule-actions">
                <button class="btn btn-sm btn-primary" onclick="monitoringApp.editSchedule('${schedule.site_key}')">
                    ✏️ 편집
                </button>
                <button class="btn btn-sm btn-secondary" onclick="monitoringApp.triggerManualCrawl('${schedule.site_key}')">
                    ▶️ 실행
                </button>
                ${schedule.enabled ? 
                    `<button class="btn btn-sm btn-warning" onclick="monitoringApp.disableSchedule('${schedule.site_key}')">⏸️ 중지</button>` :
                    `<button class="btn btn-sm btn-success" onclick="monitoringApp.enableSchedule('${schedule.site_key}')">▶️ 시작</button>`
                }
            </div>
        `;
        
        return item;
    }
    
    async loadNotifications() {
        try {
            const filter = document.getElementById('notificationFilter')?.value || '';
            const url = filter ? `/api/notifications?notification_type=${filter}` : '/api/notifications';
            
            const response = await fetch(url);
            const data = await response.json();
            
            this.updateNotificationsContainer(data.notifications || []);
            
        } catch (error) {
            console.error('알림 데이터 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '알림 데이터를 불러오는데 실패했습니다.');
        }
    }
    
    updateNotificationsContainer(notifications) {
        const container = document.getElementById('notificationsContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (notifications.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔔</div>
                    <div class="empty-state-title">알림 없음</div>
                    <div class="empty-state-description">표시할 알림이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        notifications.forEach(notification => {
            const item = this.createNotificationItem(notification);
            container.appendChild(item);
        });
    }
    
    createNotificationItem(notification) {
        const item = document.createElement('div');
        item.className = `notification-item fade-in ${notification.read_at ? '' : 'unread'}`;
        
        const iconClass = this.getNotificationIconClass(notification.notification_type);
        const iconEmoji = this.getNotificationIconEmoji(notification.notification_type);
        const timeAgo = this.formatTimeAgo(new Date(notification.created_at));
        
        item.innerHTML = `
            <div class="notification-icon ${iconClass}">
                ${iconEmoji}
            </div>
            <div class="notification-content">
                <div class="notification-title">${notification.title}</div>
                <div class="notification-message">${notification.message}</div>
                <div class="notification-meta">
                    <span>${timeAgo}</span>
                    <div class="notification-actions">
                        ${!notification.read_at ? 
                            `<button class="btn btn-xs btn-primary" onclick="monitoringApp.markNotificationRead(${notification.notification_id})">읽음</button>` :
                            '<span class="text-secondary">읽음</span>'
                        }
                    </div>
                </div>
            </div>
        `;
        
        return item;
    }
    
    async loadNewData() {
        try {
            const siteFilter = document.getElementById('newDataSiteFilter')?.value || '';
            const timeFilter = document.getElementById('newDataTimeFilter')?.value || '24';
            
            let url = `/api/new-data?hours=${timeFilter}`;
            if (siteFilter) {
                url += `&site_key=${siteFilter}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            this.updateNewDataContainer(data.new_data || []);
            
        } catch (error) {
            console.error('새로운 데이터 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '새로운 데이터를 불러오는데 실패했습니다.');
        }
    }
    
    updateNewDataContainer(newDataList) {
        const container = document.getElementById('newDataContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (newDataList.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🆕</div>
                    <div class="empty-state-title">새로운 데이터 없음</div>
                    <div class="empty-state-description">선택한 기간 동안 새로운 데이터가 없습니다.</div>
                </div>
            `;
            return;
        }
        
        newDataList.forEach(data => {
            const item = this.createNewDataItem(data);
            container.appendChild(item);
        });
    }
    
    createNewDataItem(data) {
        const item = document.createElement('div');
        item.className = `new-data-item fade-in ${data.is_important ? 'important' : ''}`;
        
        const discoveredTime = this.formatTimeAgo(new Date(data.discovered_at));
        
        item.innerHTML = `
            <div class="new-data-info">
                <div class="new-data-title">${data.data_title || data.data_id}</div>
                <div class="new-data-meta">
                    <span>📍 ${data.site_name}</span>
                    <span>🕒 ${discoveredTime}</span>
                    ${data.data_category ? `<span>📂 ${data.data_category}</span>` : ''}
                    ${data.data_date ? `<span>📅 ${data.data_date}</span>` : ''}
                </div>
                ${data.data_summary ? `<div class="new-data-summary">${data.data_summary}</div>` : ''}
                ${data.tags && data.tags.length > 0 ? `
                    <div class="new-data-tags">
                        ${data.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
        `;
        
        return item;
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/system-status');
            const data = await response.json();
            
            this.updateSystemStatusGrid(data.system_status || []);
            
        } catch (error) {
            console.error('시스템 상태 로드 실패:', error);
            this.showToast('데이터 로드 오류', 'error', '시스템 상태를 불러오는데 실패했습니다.');
        }
    }
    
    updateSystemStatusGrid(systemStatuses) {
        const container = document.getElementById('systemStatusGrid');
        if (!container) return;
        
        container.innerHTML = '';
        
        // 사이트별로 그룹화
        const groupedStatuses = {};
        systemStatuses.forEach(status => {
            if (!groupedStatuses[status.site_key]) {
                groupedStatuses[status.site_key] = [];
            }
            groupedStatuses[status.site_key].push(status);
        });
        
        Object.entries(groupedStatuses).forEach(([siteKey, statuses]) => {
            const card = this.createSystemStatusCard(siteKey, statuses);
            container.appendChild(card);
        });
    }
    
    createSystemStatusCard(siteKey, statuses) {
        const card = document.createElement('div');
        card.className = 'system-status-card fade-in';
        
        const siteName = statuses[0]?.site_name || siteKey;
        const mainStatus = statuses.find(s => s.component_type === 'crawler') || statuses[0];
        
        const healthScore = mainStatus?.health_score || 0;
        const healthClass = healthScore >= 80 ? 'good' : healthScore >= 60 ? 'warning' : 'poor';
        
        card.innerHTML = `
            <div class="system-status-header">
                <div class="system-component-name">${siteName}</div>
                <div class="health-score">
                    <span>${healthScore}%</span>
                    <div class="health-bar">
                        <div class="health-fill ${healthClass}" style="width: ${healthScore}%"></div>
                    </div>
                </div>
            </div>
            <div class="system-metrics">
                <div class="metric-item">
                    <span class="metric-label">상태</span>
                    <span class="metric-value">${mainStatus?.status || 'unknown'}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">마지막 확인</span>
                    <span class="metric-value">${mainStatus?.last_check ? 
                        new Date(mainStatus.last_check).toLocaleString('ko-KR') : '없음'}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">연속 오류</span>
                    <span class="metric-value">${mainStatus?.consecutive_errors || 0}회</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">응답 시간</span>
                    <span class="metric-value">${mainStatus?.response_time_ms || 0}ms</span>
                </div>
            </div>
        `;
        
        return card;
    }
    
    async loadJobHistory() {
        try {
            const response = await fetch('/api/job-history');
            const data = await response.json();
            
            this.updateJobHistoryContainer(data.job_history || []);
            
        } catch (error) {
            console.error('작업 이력 로드 실패:', error);
        }
    }
    
    updateJobHistoryContainer(jobHistory) {
        const container = document.getElementById('jobHistoryContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (jobHistory.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📊</div>
                    <div class="empty-state-title">작업 이력 없음</div>
                    <div class="empty-state-description">실행된 작업이 없습니다.</div>
                </div>
            `;
            return;
        }
        
        jobHistory.forEach(job => {
            const item = this.createJobHistoryItem(job);
            container.appendChild(item);
        });
    }
    
    createJobHistoryItem(job) {
        const item = document.createElement('div');
        item.className = 'job-history-item fade-in';
        
        const lastRun = job.last_run ? 
            new Date(job.last_run).toLocaleString('ko-KR') : 
            '없음';
        
        const successRate = job.success_count && job.failure_count ? 
            Math.round((job.success_count / (job.success_count + job.failure_count)) * 100) : 
            100;
        
        item.innerHTML = `
            <div class="job-info">
                <div class="job-site-name">${job.site_name}</div>
                <div class="job-details">
                    마지막 실행: ${lastRun} | 성공률: ${successRate}% | 평균 소요시간: ${job.avg_crawl_time || 0}초
                </div>
            </div>
            <div class="job-status">
                <div class="job-status-indicator ${job.last_success ? 'success' : 'failure'}"></div>
                <span>${job.last_success ? '정상' : '오류'}</span>
            </div>
        `;
        
        return item;
    }
    
    // 액션 메서드들
    async triggerManualCrawl(siteKey) {
        try {
            const response = await fetch(`/api/schedules/${siteKey}/trigger`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ delay_seconds: 0 })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showToast('크롤링 시작', 'success', result.message);
            } else {
                this.showToast('크롤링 실행 실패', 'error', result.detail);
            }
            
        } catch (error) {
            console.error('수동 크롤링 실행 실패:', error);
            this.showToast('크롤링 실행 실패', 'error', '크롤링을 시작할 수 없습니다.');
        }
    }
    
    async startScheduler() {
        try {
            const response = await fetch('/api/scheduler/start', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                this.showToast('스케줄러 시작', 'success', result.message);
                this.loadSchedules(); // 스케줄 상태 새로고침
            } else {
                this.showToast('스케줄러 시작 실패', 'error', result.detail);
            }
            
        } catch (error) {
            console.error('스케줄러 시작 실패:', error);
            this.showToast('스케줄러 시작 실패', 'error', '스케줄러를 시작할 수 없습니다.');
        }
    }
    
    async markNotificationRead(notificationId) {
        try {
            const response = await fetch(`/api/notifications/${notificationId}/read`, { method: 'POST' });
            
            if (response.ok) {
                this.loadNotifications(); // 알림 목록 새로고침
                this.updateNotificationCounter(); // 카운터 업데이트
            }
            
        } catch (error) {
            console.error('알림 읽음 처리 실패:', error);
        }
    }
    
    async markAllNotificationsRead() {
        try {
            const response = await fetch('/api/notifications');
            const data = await response.json();
            
            const unreadNotifications = data.notifications.filter(n => !n.read_at);
            
            for (const notification of unreadNotifications) {
                await fetch(`/api/notifications/${notification.notification_id}/read`, { method: 'POST' });
            }
            
            this.loadNotifications(); // 알림 목록 새로고침
            this.updateNotificationCounter(); // 카운터 업데이트
            this.showToast('알림 처리 완료', 'success', '모든 알림을 읽음 처리했습니다.');
            
        } catch (error) {
            console.error('모든 알림 읽음 처리 실패:', error);
            this.showToast('알림 처리 실패', 'error', '알림 처리 중 오류가 발생했습니다.');
        }
    }
    
    async updateNotificationCounter() {
        try {
            const response = await fetch('/api/notifications?unread_only=true');
            const data = await response.json();
            
            const unreadNotificationElement = document.getElementById('unreadNotificationCount');
            if (unreadNotificationElement) {
                unreadNotificationElement.textContent = data.total_count || 0;
            }
            
        } catch (error) {
            console.error('알림 카운터 업데이트 실패:', error);
        }
    }
    
    showScheduleModal(siteKey = null) {
        const modal = document.getElementById('scheduleModal');
        const title = document.getElementById('scheduleModalTitle');
        const siteSelect = document.getElementById('scheduleSiteKey');
        
        if (!modal) return;
        
        // 사이트 옵션 채우기
        siteSelect.innerHTML = '';
        Object.values(this.siteInfo).forEach(site => {
            const option = document.createElement('option');
            option.value = site.site_key;
            option.textContent = site.site_name;
            siteSelect.appendChild(option);
        });
        
        if (siteKey) {
            title.textContent = '스케줄 편집';
            siteSelect.value = siteKey;
            siteSelect.disabled = true;
            // 기존 스케줄 데이터 로드
            this.loadScheduleForEdit(siteKey);
        } else {
            title.textContent = '새 스케줄 추가';
            siteSelect.disabled = false;
            // 폼 초기화
            document.getElementById('scheduleForm').reset();
        }
        
        modal.classList.add('show');
    }
    
    hideScheduleModal() {
        const modal = document.getElementById('scheduleModal');
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    async loadScheduleForEdit(siteKey) {
        try {
            const response = await fetch(`/api/schedules/${siteKey}`);
            const schedule = await response.json();
            
            document.getElementById('scheduleCronExpression').value = schedule.cron_expression || '';
            document.getElementById('scheduleEnabled').checked = schedule.enabled || false;
            document.getElementById('schedulePriority').value = schedule.priority || 0;
            document.getElementById('scheduleNotificationThreshold').value = schedule.notification_threshold || 1;
            
        } catch (error) {
            console.error('스케줄 데이터 로드 실패:', error);
        }
    }
    
    async saveSchedule() {
        try {
            const formData = {
                site_key: document.getElementById('scheduleSiteKey').value,
                cron_expression: document.getElementById('scheduleCronExpression').value,
                enabled: document.getElementById('scheduleEnabled').checked,
                priority: parseInt(document.getElementById('schedulePriority').value),
                notification_threshold: parseInt(document.getElementById('scheduleNotificationThreshold').value)
            };
            
            const response = await fetch('/api/schedules', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showToast('스케줄 저장 완료', 'success', result.message);
                this.hideScheduleModal();
                this.loadSchedules(); // 스케줄 목록 새로고침
            } else {
                this.showToast('스케줄 저장 실패', 'error', result.detail);
            }
            
        } catch (error) {
            console.error('스케줄 저장 실패:', error);
            this.showToast('스케줄 저장 실패', 'error', '스케줄을 저장할 수 없습니다.');
        }
    }
    
    editSchedule(siteKey) {
        this.showScheduleModal(siteKey);
    }
    
    editSiteSchedule(siteKey) {
        this.showScheduleModal(siteKey);
    }
    
    async enableSchedule(siteKey) {
        try {
            const response = await fetch('/api/schedules', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    site_key: siteKey,
                    enabled: true,
                    cron_expression: '0 */6 * * *' // 기본값
                })
            });
            
            if (response.ok) {
                this.showToast('스케줄 활성화', 'success', '스케줄이 활성화되었습니다.');
                this.loadSchedules();
            }
            
        } catch (error) {
            console.error('스케줄 활성화 실패:', error);
        }
    }
    
    async disableSchedule(siteKey) {
        try {
            const response = await fetch(`/api/schedules/${siteKey}`, { method: 'DELETE' });
            
            if (response.ok) {
                this.showToast('스케줄 비활성화', 'success', '스케줄이 비활성화되었습니다.');
                this.loadSchedules();
            }
            
        } catch (error) {
            console.error('스케줄 비활성화 실패:', error);
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
        
        // 애니메이션 적용
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // 자동 제거
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 5000);
    }
    
    startPeriodicRefresh() {
        // 모니터링 탭이 활성화되어 있을 때만 주기적으로 새로고침
        const monitoringRefresh = setInterval(() => {
            if (this.currentTab === 'monitoring') {
                this.loadDashboardData();
            }
        }, 30000); // 30초마다
        
        this.refreshIntervals.set('monitoring', monitoringRefresh);
        
        // 알림 카운터는 항상 주기적으로 업데이트
        const notificationRefresh = setInterval(() => {
            this.updateNotificationCounter();
        }, 60000); // 1분마다
        
        this.refreshIntervals.set('notifications', notificationRefresh);
    }
    
    stopPeriodicRefresh() {
        this.refreshIntervals.forEach((interval) => {
            clearInterval(interval);
        });
        this.refreshIntervals.clear();
    }
}

// 앱 초기화
let monitoringApp;

document.addEventListener('DOMContentLoaded', () => {
    monitoringApp = new MonitoringApp();
    window.monitoringApp = monitoringApp; // 전역으로 노출
});

// 페이지 언로드 시 정리
window.addEventListener('beforeunload', () => {
    if (monitoringApp) {
        monitoringApp.stopPeriodicRefresh();
        if (monitoringApp.websocket) {
            monitoringApp.websocket.close();
        }
    }
});