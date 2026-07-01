/**
 * Expert Settings - Configuration panel for tax law monitoring system
 * Simple and intuitive controls for busy professionals
 */

class ExpertSettings {
    constructor() {
        this.jobHistoryLimit = 30;
        this.visibleJobHistoryCount = 5;
        this.siteNames = {
            'tax_tribunal': '조세심판원',
            'nts_authority': '국세청(유권해석)',
            'nts_precedent': '국세청(판례)',
            'moef': '기획재정부',
            'mois': '행정안전부',
            'bai': '감사원',
            'scourt_major_decisions': '전국법원 주요판결',
            'scourt_scheduled_decisions': '대법원 선고예정 판결'
        };
        
        this.defaultSettings = {
            defaultInterval: 6,
            maxRetries: 3,
            timeout: 30,
            notificationThreshold: 1
        };
        
        this.currentSettings = { ...this.defaultSettings };
        this.siteSchedules = {};
        this.systemStatus = null;
        this.jobHistory = [];
        
        // 브라우저 알림 관련 설정
        this.browserNotificationEnabled = this.loadNotificationSetting();
        this.notificationPermission = 'default';
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initBrowserNotifications();
        this.loadInitialData();
        
        console.log('전문가 설정 초기화 완료');
    }
    
    setupEventListeners() {
        // Save button
        document.getElementById('saveBtn')?.addEventListener('click', () => {
            this.saveSettings();
        });
        
        // Reset button
        document.getElementById('resetBtn')?.addEventListener('click', () => {
            this.resetToDefaults();
        });
        
        // Scheduler toggle
        document.getElementById('toggleSchedulerBtn')?.addEventListener('click', () => {
            this.toggleScheduler();
        });

        document.getElementById('refreshUpdatesBtn')?.addEventListener('click', () => {
            this.loadLatestUpdates();
        });

        document.getElementById('clearHistoryBtn')?.addEventListener('click', () => {
            this.clearJobHistory();
        });

        document.getElementById('instantCrawlBtn')?.addEventListener('click', () => {
            this.startInstantCrawling();
        });

        // 브라우저 알림 토글
        document.getElementById('browserNotificationToggle')?.addEventListener('change', (e) => {
            this.toggleBrowserNotifications(e.target.checked);
        });
        
        // 브라우저 알림 권한 요청
        document.getElementById('requestBrowserNotificationBtn')?.addEventListener('click', () => {
            this.requestNotificationPermission();
        });
        
        // 터널 관리
        document.getElementById('refresh-tunnel-status')?.addEventListener('click', () => {
            this.refreshTunnelStatus();
        });
        
        // ngrok 제어
        document.getElementById('ngrok-start')?.addEventListener('click', () => {
            this.controlTunnel('ngrok', 'start');
        });
        document.getElementById('ngrok-stop')?.addEventListener('click', () => {
            this.controlTunnel('ngrok', 'stop');
        });
        document.getElementById('ngrok-copy')?.addEventListener('click', () => {
            this.copyTunnelUrl('ngrok');
        });
        
        // Form inputs change detection
        document.querySelectorAll('.form-input, .toggle-input').forEach(input => {
            input.addEventListener('change', () => {
                this.markAsChanged();
            });
        });
    }
    
    async loadInitialData() {
        try {
            await Promise.all([
                this.loadSystemStatus(),
                this.loadSiteSchedules(),
                this.loadSettings(),
                this.loadTunnelStatus(),
                this.loadNtfySettings(),
                this.loadLatestUpdates()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showToast('로드 오류', 'error', '설정 데이터 로드에 실패했습니다');
        }
    }
    
    async loadSystemStatus() {
        try {
            const data = await TaxUI.fetchJson('/api/system-status');
            this.systemStatus = data;
            
            const isRunning = data.scheduler_status?.scheduler_running || false;
            this.updateSchedulerStatus(isRunning);
            this.updateOperationsSummary();
            
        } catch (error) {
            console.error('Failed to load system status:', error);
            this.updateSchedulerStatus(false);
            this.updateOperationsSummary();
        }
    }
    
    updateSchedulerStatus(isRunning) {
        const indicator = document.getElementById('schedulerStatusIndicator');
        const text = document.getElementById('schedulerStatusText');
        const button = document.getElementById('toggleSchedulerBtn');
        
        if (indicator) {
            indicator.className = `status-indicator ${isRunning ? '' : 'stopped'}`;
        }
        
        if (text) {
            text.textContent = isRunning ?
                '실행 중' :
                '중지됨';
        }
        
        if (button) {
            button.textContent = isRunning ? '중지' : '시작';
            button.disabled = false;
            button.className = `btn btn-sm ${isRunning ? 'btn-danger-outline' : 'btn-success'}`;
        }
    }
    
    async loadSiteSchedules() {
        try {
            const data = await TaxUI.fetchJson('/api/schedules');

            this.siteSchedules = {};
            if (data.schedules) {
                data.schedules.forEach(schedule => {
                    this.siteSchedules[schedule.site_key] = schedule;
                });
            }
            
            this.syncSettingsFromSchedules();
            this.renderSiteList();
            this.updateOperationsSummary();
            
        } catch (error) {
            console.error('Failed to load site schedules:', error);
            this.renderSiteList(); // Render with empty data
            this.updateOperationsSummary();
        }
    }
    
    renderSiteList() {
        const container = document.getElementById('siteList');
        if (!container) return;
        
        container.innerHTML = '';
        
        const siteKeys = Object.keys(TaxUI.SITE_COLORS);

        if (siteKeys.length === 0) {
            container.innerHTML = `
                <div class="source-empty">
                    <div class="empty-state-title">사용 가능한 소스 없음</div>
                    <div class="empty-state-description">현재 등록된 크롤링 소스가 없습니다.</div>
                </div>
            `;
            return;
        }

        siteKeys.forEach(siteKey => {
            const schedule = this.siteSchedules[siteKey];
            const siteItem = this.createSiteItem(siteKey, schedule);
            container.appendChild(siteItem);
        });
    }
    
    generateCronExpression(hours) {
        /**
         * 시간 간격을 cron 표현식으로 변환
         * @param {number} hours - 시간 간격 (1-168시간)
         * @returns {string} cron 표현식
         */
        if (hours < 1 || hours > 168) {
            throw new Error('시간 간격은 1시간과 168시간 사이여야 합니다');
        }
        
        if (hours >= 24) {
            // 24시간 이상인 경우 일 단위로 변환
            const days = Math.floor(hours / 24);
            const remainingHours = hours % 24;
            
            if (remainingHours === 0) {
                // 정확히 일 단위인 경우 (24, 48, 72시간 등)
                return `0 0 */${days} * *`;
            } else {
                // 일 단위가 아닌 경우 시간 단위로 처리
                return `0 */${hours} * * *`;
            }
        } else {
            // 24시간 미만인 경우 시간 단위
            return `0 */${hours} * * *`;
        }
    }

    getIntervalHoursFromCron(cronExpression) {
        if (!cronExpression || typeof cronExpression !== 'string') return null;

        const parts = cronExpression.trim().split(/\s+/);
        if (parts.length !== 5) return null;

        const [minute, hour, day] = parts;
        if (minute !== '0') return null;

        if (hour === '*') return 1;

        const hourlyMatch = hour.match(/^\*\/(\d+)$/);
        if (hourlyMatch) {
            return parseInt(hourlyMatch[1], 10);
        }

        const dailyMatch = day.match(/^\*\/(\d+)$/);
        if (hour === '0' && dailyMatch) {
            return parseInt(dailyMatch[1], 10) * 24;
        }

        return null;
    }

    syncSettingsFromSchedules() {
        const enabledSchedules = Object.values(this.siteSchedules || {}).filter(schedule => schedule.enabled);
        const intervalCounts = new Map();
        const thresholdCounts = new Map();

        enabledSchedules.forEach(schedule => {
            const interval = this.getIntervalHoursFromCron(schedule.cron_expression);
            if (interval) {
                intervalCounts.set(interval, (intervalCounts.get(interval) || 0) + 1);
            }

            const threshold = Number(schedule.notification_threshold);
            if (Number.isFinite(threshold)) {
                thresholdCounts.set(threshold, (thresholdCounts.get(threshold) || 0) + 1);
            }
        });

        const dominantInterval = this.getDominantSettingValue(intervalCounts);
        if (dominantInterval) {
            this.currentSettings.defaultInterval = dominantInterval;
            this.setInputValue('defaultInterval', dominantInterval);
        }

        const dominantThreshold = this.getDominantSettingValue(thresholdCounts);
        if (dominantThreshold) {
            this.currentSettings.notificationThreshold = dominantThreshold;
            this.setInputValue('notificationThreshold', dominantThreshold);
        }
    }

    getDominantSettingValue(counts) {
        let selectedValue = null;
        let selectedCount = 0;

        counts.forEach((count, value) => {
            if (count > selectedCount || (count === selectedCount && value < selectedValue)) {
                selectedValue = value;
                selectedCount = count;
            }
        });

        return selectedValue;
    }

    createSiteItem(siteKey, schedule) {
        const item = document.createElement('div');
        item.className = 'source-tile';
        
        const siteName = this.siteNames[siteKey] || siteKey;
        const siteColor = TaxUI.SITE_COLORS[siteKey] || '#6B7280';
        item.style.setProperty('--setting-accent', siteColor);
        
        const isEnabled = schedule?.enabled || false;
        const cronExpression = schedule?.cron_expression || this.generateCronExpression(this.currentSettings.defaultInterval);
        const nextRun = schedule?.scheduler_status?.next_run;
        const isRunning = schedule?.scheduler_status?.running || false;
        
        let nextRunText = '스케줄 없음';
        if (isEnabled) {
            nextRunText = nextRun ?
                this.formatDateTime(nextRun) :
                `스케줄됨: ${cronExpression}`;
        }

        const statusInfo = this.getSourceStatus(schedule, isEnabled, isRunning);
        
        item.innerHTML = `
            <div class="source-tile-header">
                <div class="source-name-cell">
                    <div class="site-indicator"></div>
                    <div class="settings-row-copy">
                        <div class="settings-row-title">${siteName}</div>
                        <div class="settings-row-description">${isEnabled ? '자동 모니터링' : '일시 중지'}</div>
                    </div>
                </div>
            </div>
            <div class="source-tile-body">
                <div class="source-metric">
                    <span class="source-label">다음 실행</span>
                    <span class="source-next-run">${nextRunText}</span>
                </div>
                <div class="source-metric">
                    <span class="source-label">최근 상태</span>
                    <span class="source-status ${statusInfo.className}">${statusInfo.text}</span>
                    <span class="source-meta">${statusInfo.meta}</span>
                </div>
            </div>
            <label class="toggle-switch source-toggle-cell">
                <input type="checkbox" class="toggle-input site-toggle" data-site-key="${siteKey}" ${isEnabled ? 'checked' : ''}>
                <span class="toggle-slider"></span>
            </label>
        `;
        
        // Add event listener for toggle
        const toggle = item.querySelector('.site-toggle');
        toggle.addEventListener('change', (e) => {
            this.handleSiteToggle(siteKey, e.target.checked);
        });
        
        return item;
    }

    getSourceStatus(schedule, isEnabled, isRunning) {
        if (!isEnabled) {
            return { text: '비활성', className: 'is-muted', meta: '자동 실행 안 함' };
        }

        if (isRunning) {
            return { text: '실행 중', className: 'is-running', meta: '현재 크롤링 중' };
        }

        const lastFailure = schedule?.last_failure ? new Date(schedule.last_failure) : null;
        const lastSuccess = schedule?.last_success ? new Date(schedule.last_success) : null;

        if (lastFailure && (!lastSuccess || lastFailure > lastSuccess)) {
            return { text: '최근 실패', className: 'is-error', meta: this.formatRelativeTime(lastFailure) };
        }

        if (lastSuccess) {
            return { text: '정상', className: 'is-success', meta: this.formatRelativeTime(lastSuccess) };
        }

        return { text: '대기', className: 'is-warning', meta: '아직 실행 이력 없음' };
    }
    
    async handleSiteToggle(siteKey, enabled) {
        try {
            if (enabled) {
                // Enable site with current default schedule
                const scheduleData = {
                    site_key: siteKey,
                    cron_expression: this.generateCronExpression(this.currentSettings.defaultInterval),
                    enabled: true,
                    priority: 0,
                    notification_threshold: this.currentSettings.notificationThreshold
                };
                
                await TaxUI.fetchJson('/api/schedules', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(scheduleData)
                });

                this.showToast('스케줄 활성화', 'success', `${this.siteNames[siteKey]} 모니터링이 활성화되었습니다`);

            } else {
                // Disable site
                await TaxUI.fetchJson(`/api/schedules/${siteKey}`, {
                    method: 'DELETE'
                });

                this.showToast('스케줄 비활성화', 'success', `${this.siteNames[siteKey]} 모니터링이 비활성화되었습니다`);
            }
            
            // Reload site schedules to update UI
            await this.loadSiteSchedules();
            
        } catch (error) {
            console.error('Failed to toggle site:', error);
            this.showToast('전환 실패', 'error', '모니터링 스케줄 업데이트에 실패했습니다');
            
            // Revert toggle state
            const toggle = document.querySelector(`[data-site-key="${siteKey}"]`);
            if (toggle) {
                toggle.checked = !enabled;
            }
        }
    }
    
    async toggleScheduler() {
        const button = document.getElementById('toggleSchedulerBtn');
        if (!button) return;
        
        try {
            button.disabled = true;
            button.textContent = '처리 중...';
            
            // 먼저 시스템 상태를 확인하여 실제 스케줄러 상태 가져오기
            const statusResponse = await fetch('/api/system-status');
            if (!statusResponse.ok) {
                throw new Error('시스템 상태 확인 실패');
            }
            
            const statusData = await statusResponse.json();
            const isCurrentlyRunning = statusData.scheduler_status?.scheduler_running || false;
            
            console.log('현재 스케줄러 상태:', isCurrentlyRunning ? '실행 중' : '중지됨');
            
            // 실제 상태에 따라 적절한 엔드포인트 호출
            const endpoint = isCurrentlyRunning ? '/api/scheduler/stop' : '/api/scheduler/start';
            const response = await fetch(endpoint, { method: 'POST' });
            
            if (!response.ok) {
                throw new Error('스케줄러 상태 변경 실패');
            }
            
            const result = await response.json();
            
            // already_stopped나 already_running도 성공으로 처리
            if (result.status === 'already_stopped' || result.status === 'already_running') {
                console.log('스케줄러가 이미 해당 상태입니다:', result.message);
            }
            
            this.showToast('스케줄러 업데이트', 'success', result.message);
            
            // 시스템 상태 다시 로드하여 UI 업데이트
            await this.loadSystemStatus();
            
        } catch (error) {
            console.error('Failed to toggle scheduler:', error);
            this.showToast('스케줄러 오류', 'error', error.message || '스케줄러 상태 업데이트에 실패했습니다');
            
            // 버튼 상태 복구를 위해 시스템 상태 다시 로드
            await this.loadSystemStatus();
        }
    }
    
    loadSettings() {
        // Load settings from localStorage or use defaults
        const savedSettings = localStorage.getItem('expertSettings');
        if (savedSettings) {
            try {
                this.currentSettings = { ...this.defaultSettings, ...JSON.parse(savedSettings) };
            } catch (error) {
                console.warn('Failed to parse saved settings, using defaults');
                this.currentSettings = { ...this.defaultSettings };
            }
        }
        
        this.applySettingsToForm();
    }
    
    applySettingsToForm() {
        this.setInputValue('defaultInterval', this.currentSettings.defaultInterval);
        this.setInputValue('maxRetries', this.currentSettings.maxRetries);
        this.setInputValue('timeout', this.currentSettings.timeout);
        this.setInputValue('notificationThreshold', this.currentSettings.notificationThreshold);
    }
    
    getSettingsFromForm() {
        return {
            defaultInterval: this.getNumberInputValue('defaultInterval', this.defaultSettings.defaultInterval),
            maxRetries: this.getNumberInputValue('maxRetries', this.currentSettings.maxRetries),
            timeout: this.getNumberInputValue('timeout', this.currentSettings.timeout),
            notificationThreshold: this.getNumberInputValue('notificationThreshold', this.defaultSettings.notificationThreshold)
        };
    }

    setInputValue(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.value = value;
        }
    }

    getNumberInputValue(id, fallback) {
        const element = document.getElementById(id);
        if (!element) return fallback;

        const value = parseInt(element.value, 10);
        return Number.isNaN(value) ? fallback : value;
    }
    
    async saveSettings() {
        try {
            const newSettings = this.getSettingsFromForm();
            
            // 설정 유효성 검사
            if (newSettings.defaultInterval < 1 || newSettings.defaultInterval > 168) {
                throw new Error('크롤링 주기는 1시간과 168시간 사이여야 합니다');
            }
            
            if (newSettings.maxRetries < 1 || newSettings.maxRetries > 10) {
                throw new Error('최대 재시도 횟수는 1회와 10회 사이여야 합니다');
            }
            
            if (newSettings.timeout < 10 || newSettings.timeout > 300) {
                throw new Error('제한시간은 10초와 300초 사이여야 합니다');
            }
            
            // Save to localStorage
            localStorage.setItem('expertSettings', JSON.stringify(newSettings));
            this.currentSettings = newSettings;
            
            // Show success message
            this.showSuccessMessage();
            this.showToast('설정 저장', 'success', '설정이 성공적으로 저장되었습니다');
            
            // Update notification settings for enabled sites
            await this.updateExistingSchedules();
            
        } catch (error) {
            console.error('Failed to save settings:', error);
            this.showToast('저장 실패', 'error', error.message || '설정 저장에 실패했습니다');
        }
    }
    
    async updateExistingSchedules() {
        // Update cron expression and notification threshold for all enabled schedules
        const enabledSites = Object.keys(this.siteSchedules).filter(
            siteKey => this.siteSchedules[siteKey].enabled
        );
        
        console.log(`Updating ${enabledSites.length} enabled schedules with new interval: ${this.currentSettings.defaultInterval} hours`);
        
        for (const siteKey of enabledSites) {
            try {
                const schedule = this.siteSchedules[siteKey];
                const newCronExpression = this.generateCronExpression(this.currentSettings.defaultInterval);
                
                const scheduleData = {
                    site_key: siteKey,
                    cron_expression: newCronExpression, // Use new cron expression based on current interval
                    enabled: true,
                    priority: schedule.priority || 0,
                    notification_threshold: this.currentSettings.notificationThreshold
                };
                
                console.log(`Updating schedule for ${siteKey}: ${schedule.cron_expression} → ${newCronExpression}`);

                await TaxUI.fetchJson('/api/schedules', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(scheduleData)
                });

            } catch (error) {
                console.warn(`Failed to update schedule for ${siteKey}:`, error);
                this.showToast('스케줄 업데이트 실패', 'warning', `${this.siteNames[siteKey]} 스케줄 업데이트에 실패했습니다`);
            }
        }
        
        // Reload schedules to reflect changes in UI
        await this.loadSiteSchedules();
        this.updateOperationsSummary();
        this.showToast('스케줄 업데이트', 'success', `${enabledSites.length}개 사이트의 스케줄이 업데이트되었습니다`);
    }
    
    resetToDefaults() {
        if (confirm('모든 설정을 기본값으로 초기화하시겠습니까?')) {
            this.currentSettings = { ...this.defaultSettings };
            this.applySettingsToForm();
            this.markAsChanged();
            this.showToast('설정 초기화', 'info', '설정이 기본값으로 초기화되었습니다');
        }
    }

    async loadLatestUpdates() {
        try {
            const data = await TaxUI.fetchJson(`/api/job-history?limit=${this.jobHistoryLimit}`);

            this.jobHistory = data.job_history || [];
            this.renderLatestUpdates(this.jobHistory);
            this.updateOperationsSummary();
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
                this.jobHistory = [];
                this.renderLatestUpdates([]);
                this.updateOperationsSummary();
            } else {
                this.showToast('삭제 실패', 'error', data.detail || '진행현황 삭제에 실패했습니다');
            }
        } catch (error) {
            console.error('Failed to clear job history:', error);
            this.showToast('삭제 실패', 'error', '진행현황 삭제 중 오류가 발생했습니다');
        }
    }

    async startInstantCrawling() {
        const btn = document.getElementById('instantCrawlBtn');

        try {
            if (btn) {
                btn.disabled = true;
                btn.textContent = '탐색 시작 중...';
            }

            await TaxUI.fetchJson('/api/crawl/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            this.showToast('즉시 탐색 시작', 'success', '전체 사이트 크롤링을 시작했습니다.');
            setTimeout(() => this.loadLatestUpdates(), 1500);
        } catch (error) {
            console.error('Failed to start instant crawling:', error);
            this.showToast('탐색 실패', 'error', '즉시 탐색 시작에 실패했습니다.');
        } finally {
            this.restoreInstantCrawlButton();
        }
    }

    restoreInstantCrawlButton() {
        const btn = document.getElementById('instantCrawlBtn');
        if (!btn) return;

        btn.disabled = false;
        btn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            전체 즉시 탐색
        `;
    }

    renderLatestUpdates(jobHistory) {
        const container = document.getElementById('updatesTimeline');
        if (!container) return;

        container.innerHTML = '';
        container.classList.remove('scrollable');
        container.style.removeProperty('--timeline-visible-height');

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

        jobHistory.slice(0, this.jobHistoryLimit).forEach(job => {
            const item = this.createJobTimelineItem(job);
            container.appendChild(item);
        });

        requestAnimationFrame(() => {
            this.updateTimelineScrollLimit(container, jobHistory.length);
        });
    }

    updateTimelineScrollLimit(container, itemCount) {
        if (itemCount <= this.visibleJobHistoryCount) return;

        const visibleItems = Array.from(container.querySelectorAll('.timeline-item'))
            .slice(0, this.visibleJobHistoryCount);
        const visibleHeight = visibleItems.reduce((height, item) => height + item.offsetHeight, 0);

        if (visibleHeight > 0) {
            container.style.setProperty('--timeline-visible-height', `${visibleHeight}px`);
            container.classList.add('scrollable');
        }
    }

    createJobTimelineItem(job) {
        const item = document.createElement('div');
        item.className = 'timeline-item';

        const startTime = new Date(job.start_time);
        const relativeTime = this.formatRelativeTime(startTime);
        const siteKey = job.site_key;
        const badgeColor = TaxUI.SITE_COLORS[siteKey] || '#6B7280';
        item.style.setProperty('--badge-color', badgeColor);
        item.style.setProperty('--badge-text-color', 'white');

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
        }

        let duration = '';
        if (job.end_time) {
            const endTime = new Date(job.end_time);
            const durationMs = endTime - startTime;
            const seconds = Math.round(durationMs / 1000);
            duration = `${seconds}초`;
        }

        let resultInfo = '';
        if (job.total_crawled !== undefined || job.new_count !== undefined) {
            const parts = [];
            if (job.total_crawled !== undefined) {
                parts.push(`${job.total_crawled}개 수집`);
            }
            if (job.new_count !== undefined) {
                parts.push(`${job.new_count}개 신규`);
            }
            if (job.new_count !== undefined && job.total_crawled !== undefined) {
                const duplicates = job.total_crawled - job.new_count;
                if (duplicates > 0) {
                    parts.push(`${duplicates}개 중복`);
                }
            }
            resultInfo = parts.join(', ');
        }

        item.innerHTML = `
            <div class="timeline-header">
                <h4 class="timeline-title">
                    ${statusIcon} ${this.getSiteName(siteKey)} 크롤링 ${statusText}
                </h4>
                <div class="timeline-meta">
                    <span class="organization-badge">
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

    getSiteName(siteKey) {
        return this.siteNames[siteKey] || siteKey;
    }

    updateOperationsSummary() {
        const schedules = Object.values(this.siteSchedules || {});
        const enabledSchedules = schedules.filter(schedule => Boolean(schedule.enabled));

        const activeSourcesCount = document.getElementById('activeSourcesCount');
        if (activeSourcesCount) {
            activeSourcesCount.textContent = `${enabledSchedules.length} / ${Object.keys(TaxUI.SITE_COLORS).length}`;
        }

        const nextRunSummary = document.getElementById('nextRunSummary');
        if (nextRunSummary) {
            const nextRun = enabledSchedules
                .map(schedule => ({
                    siteKey: schedule.site_key,
                    date: schedule.scheduler_status?.next_run ? new Date(schedule.scheduler_status.next_run) : null
                }))
                .filter(item => item.date && !Number.isNaN(item.date.getTime()))
                .sort((a, b) => a.date - b.date)[0];

            nextRunSummary.textContent = nextRun
                ? `${this.getSiteName(nextRun.siteKey)} ${this.formatDateTime(nextRun.date)}`
                : '예정 없음';
        }

        const latestRunStatus = document.getElementById('latestRunStatus');
        const latestRunMeta = document.getElementById('latestRunMeta');
        if (latestRunStatus && latestRunMeta) {
            const latestJob = this.jobHistory
                .slice()
                .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))[0];

            if (!latestJob) {
                latestRunStatus.textContent = '이력 없음';
                latestRunStatus.className = 'operation-value';
                latestRunMeta.textContent = '-';
                return;
            }

            const statusInfo = this.getJobStatusInfo(latestJob.status);
            latestRunStatus.textContent = `${this.getSiteName(latestJob.site_key)} ${statusInfo.text}`;
            latestRunStatus.className = `operation-value ${statusInfo.className}`;
            latestRunMeta.textContent = `${this.formatRelativeTime(new Date(latestJob.start_time))} · ${this.formatJobResult(latestJob)}`;
        }
    }

    getJobStatusInfo(status) {
        if (status === 'completed' || status === 'success') {
            return { text: '완료', className: 'is-success' };
        }
        if (status === 'failed') {
            return { text: '실패', className: 'is-error' };
        }
        if (status === 'partial_success') {
            return { text: '부분 성공', className: 'is-warning' };
        }
        return { text: '실행 중', className: 'is-running' };
    }

    formatJobResult(job) {
        const parts = [];
        if (job.total_crawled !== undefined) parts.push(`${job.total_crawled}개 수집`);
        if (job.new_count !== undefined) parts.push(`${job.new_count}개 신규`);
        return parts.length ? parts.join(', ') : '결과 집계 전';
    }

    formatDateTime(value) {
        const date = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(date.getTime())) return '-';

        return date.toLocaleString('ko-KR', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
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

    markAsChanged() {
        // Visual feedback that settings have changed
        const saveBtn = document.getElementById('saveBtn');
        if (saveBtn) {
            saveBtn.textContent = '변경사항 저장';
            saveBtn.classList.add('btn-warning');
            saveBtn.classList.remove('btn-primary');
        }
    }
    
    showSuccessMessage() {
        const successMessage = document.getElementById('successMessage');
        if (successMessage) {
            successMessage.hidden = false;
            
            setTimeout(() => {
                successMessage.hidden = true;
            }, 5000);
        }
        
        // Reset save button
        const saveBtn = document.getElementById('saveBtn');
        if (saveBtn) {
            saveBtn.textContent = '설정 저장';
            saveBtn.classList.remove('btn-warning');
            saveBtn.classList.add('btn-primary');
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
        const toggle = document.getElementById('browserNotificationToggle');
        const permissionBtn = document.getElementById('requestBrowserNotificationBtn');
        const statusElement = document.getElementById('browserNotificationStatus');
        
        if (toggle) {
            toggle.checked = this.browserNotificationEnabled;
            toggle.disabled = permission === 'denied' || permission === 'unsupported';
        }
        
        if (permissionBtn) {
            permissionBtn.hidden = permission !== 'default';
        }
        
        if (statusElement) {
            statusElement.className = `notification-status ${permission}`;
            
            switch (permission) {
                case 'granted':
                    statusElement.textContent = '허용됨';
                    break;
                case 'denied':
                    statusElement.textContent = '거부됨';
                    break;
                case 'default':
                    statusElement.textContent = '미설정';
                    break;
                case 'unsupported':
                    statusElement.textContent = '지원 안됨';
                    break;
                default:
                    statusElement.textContent = '확인 중...';
            }
        }
    }
    
    loadNotificationSetting() {
        return TaxUI.loadNotificationSetting();
    }

    saveNotificationSetting(enabled) {
        TaxUI.saveNotificationSetting(enabled);
    }

    async loadNtfySettings() {
        try {
            const settings = await TaxUI.fetchJson('/api/ntfy-settings');
            this.updateNtfySummary(settings);
            this.setText('ntfyTopicValue', settings.explicit_url_configured ? 'NTFY_URL 사용' : (settings.topic || '미설정'));
            this.setText('ntfyServerValue', settings.server_url || 'https://ntfy.sh');
            this.setText('ntfyItemLimitValue', `${settings.item_limit || 5}건`);
            this.setText('ntfyDashboardValue', settings.click_url || settings.dashboard_url || 'http://localhost:8001');
        } catch (error) {
            console.error('ntfy 설정 로드 실패:', error);
            this.updateNtfySummary({ configured: false, enabled: false });
        }
    }

    updateNtfySummary(settings) {
        const summary = document.getElementById('ntfySummaryStatus');
        if (!summary) return;

        if (!settings.configured) {
            summary.textContent = 'NTFY_TOPIC 또는 NTFY_URL 환경 변수가 필요합니다';
            summary.className = 'settings-row-description is-warning';
            return;
        }

        if (settings.enabled) {
            const authText = settings.auth_configured ? '인증 설정됨' : '공개 토픽';
            summary.textContent = `${settings.explicit_url_configured ? '사용자 지정 URL' : settings.topic} · 활성화됨 · ${authText}`;
            summary.className = 'settings-row-description is-success';
        } else {
            summary.textContent = '환경 변수는 있으나 NTFY_ENABLED=false 상태입니다';
            summary.className = 'settings-row-description';
        }
    }

    setText(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    }
    
    showStatusMessage(element, type, message) {
        if (!element) return;
        
        element.className = `status-message ${type}`;
        element.textContent = message;
        element.hidden = false;
        
        // 5초 후 자동 숨김
        setTimeout(() => {
            element.hidden = true;
        }, 5000);
    }
    
    showToast(title, type, message) {
        TaxUI.showToast(title, type, message);
    }

    // 터널 관리 메서드들
    async loadTunnelStatus() {
        try {
            const status = await TaxUI.fetchJson('/api/tunnel-status');
            this.updateTunnelUI(status);
        } catch (error) {
            console.error('터널 상태 로드 실패:', error);
            this.showToast('터널 오류', 'error', '터널 상태를 가져올 수 없습니다');
        }
    }

    async refreshTunnelStatus() {
        const button = document.getElementById('refresh-tunnel-status');
        if (button) {
            button.disabled = true;
            button.textContent = '새로고침 중...';
        }

        try {
            await this.loadTunnelStatus();
            this.showToast('새로고침 완료', 'success', '터널 상태가 업데이트되었습니다');
        } catch (error) {
            this.showToast('새로고침 실패', 'error', '터널 상태 새로고침에 실패했습니다');
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = '터널 상태 새로고침';
            }
        }
    }

    updateTunnelUI(status) {
        const ngrokStatus = document.getElementById('ngrok-status');
        const ngrokConfiguredUrl = document.getElementById('ngrok-configured-url');
        const ngrokUrl = document.getElementById('ngrok-url');
        const ngrokStart = document.getElementById('ngrok-start');
        const ngrokStop = document.getElementById('ngrok-stop');
        const ngrokCopy = document.getElementById('ngrok-copy');

        if (ngrokStatus) {
            const ngrokData = status.ngrok;
            const setStatus = (text, tone) => {
                ngrokStatus.textContent = text;
                ngrokStatus.className = `settings-row-status ${tone}`;
            };
            const setControls = ({ start, stop, copy }) => {
                if (ngrokStart) ngrokStart.hidden = !start;
                if (ngrokStop) ngrokStop.hidden = !stop;
                if (ngrokCopy) ngrokCopy.hidden = !copy;
            };
            const setCurrentUrl = (url) => {
                if (!ngrokUrl) return;
                if (url) {
                    ngrokUrl.textContent = `현재 URL: ${url}`;
                    ngrokUrl.dataset.copyUrl = url;
                    ngrokUrl.hidden = false;
                } else {
                    ngrokUrl.hidden = true;
                }
            };

            if (ngrokConfiguredUrl) {
                if (ngrokData.configured_url) {
                    ngrokConfiguredUrl.textContent = `고정 URL: ${ngrokData.configured_url}`;
                } else {
                    ngrokConfiguredUrl.textContent = '고정 URL 미설정';
                }
                ngrokConfiguredUrl.hidden = false;
            }

            if (ngrokData.status === 'active') {
                setStatus(ngrokData.is_static ? '실행 중 (고정 URL)' : '실행 중', 'is-success');
                setCurrentUrl(ngrokData.url);
                setControls({ start: false, stop: true, copy: Boolean(ngrokData.url) });
            } else if (ngrokData.status === 'active_dynamic') {
                setStatus('실행 중 (임시 URL)', 'is-warning');
                setCurrentUrl(ngrokData.url);
                setControls({ start: false, stop: true, copy: Boolean(ngrokData.url) });
            } else if (ngrokData.status === 'connecting') {
                setStatus('연결 중', 'is-warning');
                setCurrentUrl(null);
                setControls({ start: false, stop: true, copy: false });
            } else if (ngrokData.status === 'static_unconfigured') {
                setStatus('고정 URL 미설정', 'is-warning');
                setCurrentUrl(null);
                setControls({ start: true, stop: false, copy: false });
            } else {
                setStatus('중지됨', 'is-danger');
                setCurrentUrl(null);
                setControls({ start: true, stop: false, copy: false });
            }
        }
    }

    async controlTunnel(tunnelType, action) {
        const button = document.getElementById(`${tunnelType}-${action}`);
        const originalText = button.textContent;
        
        try {
            button.disabled = true;
            button.textContent = `${action === 'start' ? '시작' : '중지'} 중...`;

            const response = await fetch(`/api/tunnel/${action}/${tunnelType}`, {
                method: 'POST'
            });

            const result = await response.json();
            
            if (result.success) {
                this.showToast('터널 제어', 'success', result.message);
                // 상태 업데이트
                setTimeout(() => this.loadTunnelStatus(), 2000);
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            this.showToast('터널 오류', 'error', error.message);
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    copyTunnelUrl(tunnelType) {
        const urlElement = document.getElementById(`${tunnelType}-url`);
        if (urlElement && urlElement.textContent) {
            const url = urlElement.dataset.copyUrl || urlElement.textContent;
            navigator.clipboard.writeText(url)
                .then(() => {
                    this.showToast('URL 복사됨', 'success', '터널 URL이 클립보드에 복사되었습니다');
                })
                .catch(() => {
                    this.showToast('복사 실패', 'error', 'URL 복사에 실패했습니다');
                });
        }
    }
}

// Initialize settings when DOM is loaded
let expertSettings;

document.addEventListener('DOMContentLoaded', () => {
    expertSettings = new ExpertSettings();
    window.expertSettings = expertSettings; // Make it globally accessible
});
