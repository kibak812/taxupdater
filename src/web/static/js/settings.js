/**
 * Expert Settings - Configuration panel for tax law monitoring system
 * Simple and intuitive controls for busy professionals
 */

class ExpertSettings {
    constructor() {
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
        
        this.defaultSettings = {
            defaultInterval: 6,
            maxRetries: 3,
            timeout: 30,
            realtimeNotifications: true,
            notificationThreshold: 1
        };
        
        this.currentSettings = { ...this.defaultSettings };
        this.siteSchedules = {};
        
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
        
        // 브라우저 알림 토글
        document.getElementById('browserNotificationToggle')?.addEventListener('change', (e) => {
            this.toggleBrowserNotifications(e.target.checked);
        });
        
        // 브라우저 알림 권한 요청
        document.getElementById('requestBrowserNotificationBtn')?.addEventListener('click', () => {
            this.requestNotificationPermission();
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
                this.loadSettings()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showToast('로드 오류', 'error', '설정 데이터 로드에 실패했습니다');
        }
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/system-status');
            const data = await response.json();
            
            const isRunning = data.scheduler_status?.scheduler_running || false;
            this.updateSchedulerStatus(isRunning);
            
        } catch (error) {
            console.error('Failed to load system status:', error);
            this.updateSchedulerStatus(false);
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
                '스케줄러 실행 중 - 자동 모니터링 활성' : 
                '스케줄러 중지 - 모니터링 일시 중지';
        }
        
        if (button) {
            button.textContent = isRunning ? '스케줄러 중지' : '스케줄러 시작';
            button.disabled = false;
            button.className = `btn btn-sm ${isRunning ? 'btn-warning' : 'btn-success'}`;
        }
    }
    
    async loadSiteSchedules() {
        try {
            const response = await fetch('/api/schedules');
            const data = await response.json();
            
            this.siteSchedules = {};
            if (data.schedules) {
                data.schedules.forEach(schedule => {
                    this.siteSchedules[schedule.site_key] = schedule;
                });
            }
            
            this.renderSiteList();
            
        } catch (error) {
            console.error('Failed to load site schedules:', error);
            this.renderSiteList(); // Render with empty data
        }
    }
    
    renderSiteList() {
        const container = document.getElementById('siteList');
        if (!container) return;
        
        container.innerHTML = '';
        
        // Get all available sites from colors mapping
        Object.keys(this.siteColors).forEach(siteKey => {
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

    createSiteItem(siteKey, schedule) {
        const item = document.createElement('div');
        item.className = 'site-item';
        
        const siteName = this.siteNames[siteKey] || siteKey;
        const siteColor = this.siteColors[siteKey] || '#6B7280';
        
        const isEnabled = schedule?.enabled || false;
        const cronExpression = schedule?.cron_expression || this.generateCronExpression(this.currentSettings.defaultInterval);
        const nextRun = schedule?.scheduler_status?.next_run;
        
        let statusText = '스케줄 없음';
        if (isEnabled) {
            statusText = nextRun ? 
                `다음 실행: ${new Date(nextRun).toLocaleString('ko-KR')}` : 
                `스케줄됨: ${cronExpression}`;
        }
        
        item.innerHTML = `
            <div class="site-info">
                <div class="site-indicator" style="background: ${siteColor};"></div>
                <div>
                    <div class="site-name">${siteName}</div>
                    <div class="site-status">${statusText}</div>
                </div>
            </div>
            <label class="toggle-switch">
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
                
                const response = await fetch('/api/schedules', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(scheduleData)
                });
                
                if (!response.ok) {
                    throw new Error('Failed to enable schedule');
                }
                
                this.showToast('스케줄 활성화', 'success', `${this.siteNames[siteKey]} 모니터링이 활성화되었습니다`);
                
            } else {
                // Disable site
                const response = await fetch(`/api/schedules/${siteKey}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error('Failed to disable schedule');
                }
                
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
        // Apply settings to form fields
        document.getElementById('defaultInterval').value = this.currentSettings.defaultInterval;
        document.getElementById('maxRetries').value = this.currentSettings.maxRetries;
        document.getElementById('timeout').value = this.currentSettings.timeout;
        document.getElementById('realtimeNotifications').checked = this.currentSettings.realtimeNotifications;
        document.getElementById('notificationThreshold').value = this.currentSettings.notificationThreshold;
    }
    
    getSettingsFromForm() {
        return {
            defaultInterval: parseInt(document.getElementById('defaultInterval').value),
            maxRetries: parseInt(document.getElementById('maxRetries').value),
            timeout: parseInt(document.getElementById('timeout').value),
            realtimeNotifications: document.getElementById('realtimeNotifications').checked,
            notificationThreshold: parseInt(document.getElementById('notificationThreshold').value)
        };
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
                
                const response = await fetch('/api/schedules', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(scheduleData)
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
            } catch (error) {
                console.warn(`Failed to update schedule for ${siteKey}:`, error);
                this.showToast('스케줄 업데이트 실패', 'warning', `${this.siteNames[siteKey]} 스케줄 업데이트에 실패했습니다`);
            }
        }
        
        // Reload schedules to reflect changes in UI
        await this.loadSiteSchedules();
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
            successMessage.style.display = 'block';
            
            setTimeout(() => {
                successMessage.style.display = 'none';
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
            permissionBtn.style.display = permission === 'default' ? 'inline-block' : 'none';
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
}

// Initialize settings when DOM is loaded
let expertSettings;

document.addEventListener('DOMContentLoaded', () => {
    expertSettings = new ExpertSettings();
    window.expertSettings = expertSettings; // Make it globally accessible
});