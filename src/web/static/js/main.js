// Tax Law Crawler Web Interface - JavaScript
// 세금 법령 크롤링 시스템 웹 인터페이스 클라이언트 사이드 로직

class TaxCrawlerApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.init();
    }

    async init() {
        console.log('Tax Crawler App 초기화 중...');
        
        // WebSocket 연결
        this.connectWebSocket();
        
        // 대시보드 데이터 로드
        if (document.getElementById('dashboard')) {
            await this.loadDashboardData();
            // 30초마다 대시보드 새로고침
            setInterval(() => this.loadDashboardData(), 30000);
        }

        // 크롤링 진행현황 로드
        if (document.getElementById('crawlProgress')) {
            await this.loadCrawlProgress();
            // 30초마다 진행현황 새로고침
            setInterval(() => this.loadCrawlProgress(), 30000);
        }
        
        // 사이트별 데이터 로드
        if (document.getElementById('siteData')) {
            await this.loadSiteData();
        }
        
        // 이벤트 리스너 등록
        this.setupEventListeners();
        
        console.log('Tax Crawler App 초기화 완료');
    }

    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/crawl`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket 연결 성공');
                this.isConnected = true;
                this.showNotification('실시간 모니터링 연결됨', 'success');
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket 연결 종료');
                this.isConnected = false;
                // 3초 후 재연결 시도
                setTimeout(() => this.connectWebSocket(), 3000);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.showNotification('실시간 연결 오류 발생', 'error');
            };
            
        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
        }
    }

    handleWebSocketMessage(data) {
        console.log('WebSocket 메시지:', data);
        
        switch (data.type) {
            case 'crawl_start':
                this.showNotification(`크롤링 시작: ${this.getCrawlChoiceName(data.choice)}`, 'info');
                this.updateCrawlStatus('진행 중...', 0);
                this.showCrawlStatusContainer(true);
                break;
                
            case 'crawl_progress':
                this.updateCrawlProgress(data.progress);
                break;
                
            case 'crawl_status':
                this.updateCrawlStatus(data.status, data.progress || null);
                break;
                
            case 'crawl_complete':
                this.showNotification(`크롤링 완료: ${this.getCrawlChoiceName(data.choice)}`, 'success');
                this.updateCrawlStatus('완료', 100);
                this.loadCrawlProgress(); // 진행현황 새로고침
                this.showCrawlStatusContainer(false, 3000); // 3초 후 숨김
                // 대시보드 새로고침
                setTimeout(() => this.loadDashboardData(), 2000);
                break;
                
            case 'crawl_error':
                this.showNotification(`크롤링 오류: ${data.error}`, 'error');
                this.updateCrawlStatus('오류 발생', null);
                this.showCrawlStatusContainer(false, 5000); // 5초 후 숨김
                break;
        }
    }

    getCrawlChoiceName(choice) {
        const choices = {
            '1': '조세심판원',
            '2': '국세청',
            '3': '기획재정부',
            '4': '국세청 판례',
            '5': '행정안전부',
            '6': '감사원',
            '7': '전체 사이트'
        };
        return choices[choice] || '알 수 없음';
    }

    async loadDashboardData() {
        try {
            console.log('대시보드 데이터 로딩...');
            
            const response = await fetch('/api/dashboard');
            if (!response.ok) throw new Error('대시보드 데이터 로드 실패');
            
            const data = await response.json();
            this.renderDashboard(data);
            
            console.log('대시보드 데이터 로드 완료:', data);
            
        } catch (error) {
            console.error('대시보드 로드 오류:', error);
            this.showNotification('대시보드 로드 실패', 'error');
        }
    }

    renderDashboard(data) {
        const dashboard = document.getElementById('dashboard');
        if (!dashboard) return;
        
        dashboard.innerHTML = data.sites.map(site => `
            <div class="site-card" style="--site-color: ${site.color}">
                <div class="site-header">
                    <div class="site-name">${site.site_name}</div>
                    <div class="site-status status-${site.status}">
                        ${site.status === 'success' ? '활성' : '빈 데이터'}
                    </div>
                </div>
                
                <div class="site-stats">
                    <div class="stat-item">
                        <span class="stat-label">총 데이터</span>
                        <span class="stat-value">${site.total_count.toLocaleString()}개</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">마지막 업데이트</span>
                        <span class="stat-value">${this.formatDateTime(site.last_updated)}</span>
                    </div>
                </div>
                
                <div class="actions">
                    <button class="btn btn-primary crawl-btn" onclick="app.startCrawling('${site.site_key}')">
                        <span class="btn-text">크롤링</span>
                        <span class="loading" style="display: none;"></span>
                    </button>
                    <a href="/sites/${site.site_key}" class="view-btn" title="상세보기">📄</a>
                </div>
            </div>
        `).join('');
        
        // 통계 업데이트
        this.updateStats(data.sites);
    }

    updateStats(sites) {
        const totalRecords = sites.reduce((sum, site) => sum + site.total_count, 0);
        const activeSites = sites.filter(site => site.status === 'success').length;
        
        const statsElement = document.querySelector('.stats-overview');
        if (statsElement) {
            statsElement.innerHTML = `
                <h3>전체 현황</h3>
                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="stat-number">${totalRecords.toLocaleString()}</span>
                        <span class="stat-description">총 수집 데이터</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-number">${activeSites}</span>
                        <span class="stat-description">활성 사이트</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-number">${sites.length}</span>
                        <span class="stat-description">모니터링 사이트</span>
                    </div>
                </div>
            `;
        }
    }

    async loadSiteData() {
        const siteKey = this.getSiteKeyFromURL();
        if (!siteKey) return;
        
        try {
            console.log(`사이트 데이터 로딩: ${siteKey}`);
            
            const urlParams = new URLSearchParams(window.location.search);
            const page = urlParams.get('page') || 1;
            const search = urlParams.get('search') || '';
            
            const response = await fetch(`/api/sites/${siteKey}/data?page=${page}&search=${encodeURIComponent(search)}`);
            if (!response.ok) throw new Error('사이트 데이터 로드 실패');
            
            const data = await response.json();
            this.renderSiteData(data);
            
            console.log('사이트 데이터 로드 완료:', data);
            
        } catch (error) {
            console.error('사이트 데이터 로드 오류:', error);
            this.showNotification('사이트 데이터 로드 실패', 'error');
        }
    }

    renderSiteData(data) {
        const container = document.getElementById('siteData');
        if (!container) return;
        
        // 테이블 헤더 생성
        const columns = data.data.length > 0 ? Object.keys(data.data[0]) : [];
        
        container.innerHTML = `
            <div class="data-table">
                <div class="table-header">
                    <h3>${data.site_name} 데이터 (총 ${data.pagination.total_count.toLocaleString()}개)</h3>
                    <div class="table-controls">
                        <input type="text" class="search-input" placeholder="검색..." 
                               value="${data.search}" onkeypress="app.handleSearchKeypress(event)">
                        <button class="btn btn-secondary btn-sm" onclick="app.exportData('${data.site_key}')">
                            📤 Excel 내보내기
                        </button>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            ${columns.map(col => `<th>${col}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${data.data.map(row => `
                            <tr>
                                ${columns.map(col => `<td>${this.escapeHtml(row[col] || '')}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                
                ${this.renderPagination(data.pagination)}
            </div>
        `;
    }

    renderPagination(pagination) {
        if (pagination.total_pages <= 1) return '';
        
        const currentPage = pagination.page;
        const totalPages = pagination.total_pages;
        
        let pages = [];
        
        // 이전 버튼
        if (pagination.has_prev) {
            pages.push(`<a href="?page=${currentPage - 1}" class="page-btn">‹ 이전</a>`);
        }
        
        // 페이지 번호들
        for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
            const active = i === currentPage ? 'active' : '';
            pages.push(`<a href="?page=${i}" class="page-btn ${active}">${i}</a>`);
        }
        
        // 다음 버튼
        if (pagination.has_next) {
            pages.push(`<a href="?page=${currentPage + 1}" class="page-btn">다음 ›</a>`);
        }
        
        return `
            <div class="pagination">
                ${pages.join('')}
            </div>
        `;
    }

    async startCrawling(siteKey) {
        try {
            console.log(`크롤링 시작: ${siteKey}`);
            
            // 버튼 상태 변경 (안전한 방법)
            const buttons = document.querySelectorAll(`.crawl-btn`);
            let targetButton = null;
            
            // 현재 클릭된 버튼 찾기
            buttons.forEach(btn => {
                const onclick = btn.getAttribute('onclick');
                if (onclick && onclick.includes(siteKey)) {
                    targetButton = btn;
                }
            });
            
            if (targetButton) {
                const btnText = targetButton.querySelector('.btn-text');
                const loading = targetButton.querySelector('.loading');
                
                if (btnText) btnText.textContent = '진행 중...';
                if (loading) loading.style.display = 'inline-block';
                targetButton.disabled = true;
            }
            
            const response = await fetch(`/api/crawl/${siteKey}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) throw new Error('크롤링 시작 실패');
            
            const result = await response.json();
            this.showNotification(result.message, 'success');
            
        } catch (error) {
            console.error('크롤링 시작 오류:', error);
            this.showNotification('크롤링 시작 실패', 'error');
            
            // 버튼 상태 복원 (안전한 방법)
            const buttons = document.querySelectorAll(`.crawl-btn`);
            buttons.forEach(btn => {
                const onclick = btn.getAttribute('onclick');
                if (onclick && onclick.includes(siteKey)) {
                    const btnText = btn.querySelector('.btn-text');
                    const loading = btn.querySelector('.loading');
                    
                    if (btnText) btnText.textContent = '크롤링';
                    if (loading) loading.style.display = 'none';
                    btn.disabled = false;
                }
            });
        }
    }

    async startAllCrawling() {
        try {
            console.log('전체 크롤링 시작');
            
            const response = await fetch('/api/crawl/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) throw new Error('전체 크롤링 시작 실패');
            
            const result = await response.json();
            this.showNotification(result.message, 'success');
            
        } catch (error) {
            console.error('전체 크롤링 시작 오류:', error);
            this.showNotification('전체 크롤링 시작 실패', 'error');
        }
    }

    async startInstantCrawling() {
        try {
            console.log('즉시 탐색 시작');
            
            // 버튼 비활성화
            const btn = document.getElementById('instantCrawlBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '⏳ 탐색 중...';
            }
            
            const response = await fetch('/api/crawl/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) throw new Error('즉시 탐색 시작 실패');
            
            const result = await response.json();
            this.showNotification('즉시 탐색을 시작했습니다. 진행상황을 확인하세요.', 'success');
            
        } catch (error) {
            console.error('즉시 탐색 오류:', error);
            this.showNotification('즉시 탐색 시작 실패', 'error');
        } finally {
            // 버튼 복원
            const btn = document.getElementById('instantCrawlBtn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🚀 즉시 탐색';
            }
        }
    }

    async loadCrawlProgress() {
        try {
            console.log('크롤링 진행현황 로드 중...');
            
            const response = await fetch('/api/job-history?limit=10');
            if (!response.ok) throw new Error('진행현황 로드 실패');
            
            const data = await response.json();
            this.renderCrawlProgress(data.job_history || []);
            
        } catch (error) {
            console.error('진행현황 로드 오류:', error);
            this.showNotification('진행현황 로드 실패', 'error');
        }
    }

    renderCrawlProgress(history) {
        const container = document.getElementById('crawlProgress');
        if (!container) return;

        if (history.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📊</div>
                    <div class="empty-state-title">진행현황 없음</div>
                    <div class="empty-state-description">아직 크롤링 실행 기록이 없습니다.</div>
                </div>
            `;
            return;
        }

        container.innerHTML = history.map(job => {
            const startTime = new Date(job.start_time);
            const timeStr = startTime.toLocaleDateString('ko-KR') + ' ' + 
                           startTime.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
            
            let statusIcon = '●';
            let statusClass = 'status-success';
            if (job.status === 'failed') {
                statusIcon = '×';
                statusClass = 'status-error';
            } else if (job.status === 'running') {
                statusIcon = '◯';
                statusClass = 'status-running';
            }

            let resultInfo = '';
            if (job.total_crawled !== undefined && job.new_count !== undefined) {
                const duplicates = job.total_crawled - job.new_count;
                resultInfo = `${job.total_crawled}개 수집, ${job.new_count}개 신규, ${duplicates}개 중복`;
            }

            return `
                <div class="timeline-item">
                    <div class="timeline-icon ${statusClass}">${statusIcon}</div>
                    <div class="timeline-content">
                        <div class="timeline-title">${job.site_name} 크롤링 ${job.status === 'success' ? '완료' : job.status === 'failed' ? '실패' : '실행 중'}</div>
                        ${resultInfo ? `<div class="timeline-description">${resultInfo}</div>` : ''}
                        <div class="timeline-meta">
                            <span>실행 시간: ${timeStr}</span>
                            ${job.error_message ? `<span style="color: #EF4444;">오류: ${job.error_message}</span>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    async clearCrawlProgress() {
        if (!confirm('크롤링 진행현황을 모두 삭제하시겠습니까?')) {
            return;
        }

        try {
            const response = await fetch('/api/job-history', {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('진행현황 삭제 실패');

            const result = await response.json();
            this.showNotification('진행현황이 삭제되었습니다.', 'success');
            this.loadCrawlProgress(); // 목록 새로고침

        } catch (error) {
            console.error('진행현황 삭제 오류:', error);
            this.showNotification('진행현황 삭제 실패', 'error');
        }
    }

    handleSearchKeypress(event) {
        if (event.key === 'Enter') {
            const searchValue = event.target.value;
            const currentUrl = new URL(window.location);
            currentUrl.searchParams.set('search', searchValue);
            currentUrl.searchParams.set('page', '1'); // 검색 시 첫 페이지로
            window.location.href = currentUrl.toString();
        }
    }

    exportData(siteKey) {
        // 현재는 간단한 알림만 표시
        this.showNotification('Excel 내보내기 기능은 향후 구현 예정입니다.', 'info');
    }

    setupEventListeners() {
        // 전체 크롤링 버튼
        const allCrawlBtn = document.getElementById('allCrawlBtn');
        if (allCrawlBtn) {
            allCrawlBtn.addEventListener('click', () => this.startAllCrawling());
        }
        
        // 즉시 탐색 버튼
        const instantCrawlBtn = document.getElementById('instantCrawlBtn');
        if (instantCrawlBtn) {
            instantCrawlBtn.addEventListener('click', () => this.startInstantCrawling());
        }
        
        // 새로고침 버튼
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDashboardData());
        }

        // 진행현황 새로고침 버튼
        const refreshProgressBtn = document.getElementById('refreshProgressBtn');
        if (refreshProgressBtn) {
            refreshProgressBtn.addEventListener('click', () => this.loadCrawlProgress());
        }

        // 진행현황 삭제 버튼
        const clearProgressBtn = document.getElementById('clearProgressBtn');
        if (clearProgressBtn) {
            clearProgressBtn.addEventListener('click', () => this.clearCrawlProgress());
        }
    }

    updateCrawlStatus(status, progress = null) {
        // 크롤링 상태를 화면에 표시
        const statusElement = document.getElementById('crawlStatus');
        if (statusElement) {
            let statusText = status;
            if (progress !== null && progress >= 0) {
                statusText += ` (${progress}%)`;
            }
            statusElement.textContent = statusText;
        }
        
        // 진행률도 업데이트
        if (progress !== null) {
            this.updateCrawlProgress(progress);
        }
        
        // 모든 크롤링 버튼의 상태 업데이트
        document.querySelectorAll('.crawl-btn').forEach(btn => {
            if (status === '완료' || status === '오류 발생') {
                const btnText = btn.querySelector('.btn-text');
                const loading = btn.querySelector('.loading');
                
                if (btnText) btnText.textContent = '크롤링';
                if (loading) loading.style.display = 'none';
                btn.disabled = false;
            }
        });
    }

    updateCrawlProgress(progress) {
        // 진행률 바 업데이트
        const progressBar = document.getElementById('crawlProgress');
        if (progressBar) {
            progressBar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
            progressBar.style.background = progress >= 100 ? '#10B981' : '#3B82F6';
        }
    }

    showCrawlStatusContainer(show, hideAfter = null) {
        const container = document.getElementById('crawlStatusContainer');
        if (container) {
            if (show) {
                container.style.display = 'block';
                // 진행률 초기화
                this.updateCrawlProgress(0);
            } else if (hideAfter) {
                // 지정된 시간 후 숨김
                setTimeout(() => {
                    container.style.display = 'none';
                }, hideAfter);
            } else {
                container.style.display = 'none';
            }
        }
    }

    showNotification(message, type = 'info') {
        // 기존 알림 제거
        const existing = document.querySelector('.notification');
        if (existing) existing.remove();
        
        // 새 알림 생성
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="background: none; border: none; font-size: 1.2rem; cursor: pointer;">×</button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // 애니메이션으로 표시
        setTimeout(() => notification.classList.add('show'), 100);
        
        // 5초 후 자동 제거
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    formatDateTime(dateString) {
        if (!dateString) return '정보 없음';
        
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diff = now - date;
            
            // 1분 미만
            if (diff < 60000) {
                return '방금 전';
            }
            // 1시간 미만
            else if (diff < 3600000) {
                const minutes = Math.floor(diff / 60000);
                return `${minutes}분 전`;
            }
            // 24시간 미만
            else if (diff < 86400000) {
                const hours = Math.floor(diff / 3600000);
                return `${hours}시간 전`;
            }
            // 그 외
            else {
                return date.toLocaleDateString('ko-KR') + ' ' + date.toLocaleTimeString('ko-KR', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
            }
        } catch (error) {
            return dateString;
        }
    }

    getSiteKeyFromURL() {
        const pathParts = window.location.pathname.split('/');
        if (pathParts[1] === 'sites') {
            return pathParts[2];
        }
        return null;
    }

    escapeHtml(text) {
        if (typeof text !== 'string') text = String(text);
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 앱 초기화
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new TaxCrawlerApp();
    window.app = app; // 전역으로 노출
});

// 전역 함수들 (HTML에서 직접 호출용)
window.startCrawling = (siteKey) => app.startCrawling(siteKey);
window.startAllCrawling = () => app.startAllCrawling();
window.handleSearchKeypress = (event) => app.handleSearchKeypress(event);
window.exportData = (siteKey) => app.exportData(siteKey);