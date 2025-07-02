/**
 * Expert Data Table - Professional data view for tax law experts
 * Focus on quick scanning and efficient data analysis
 */

class ExpertDataTable {
    constructor() {
        this.siteKey = window.siteConfig.siteKey;
        this.siteName = window.siteConfig.siteName;
        this.siteColor = window.siteConfig.siteColor;
        
        // 사이트별 컴럼명 매핑
        this.siteColumnNames = {
            'tax_tribunal': {
                documentColumn: '청구번호',
                dateColumn: '결정일'
            },
            'nts_authority': {
                documentColumn: '문서번호',
                dateColumn: '생산일자'
            },
            'nts_precedent': {
                documentColumn: '문서번호',
                dateColumn: '생산일자'
            },
            'moef': {
                documentColumn: '문서번호',
                dateColumn: '회신일자'
            },
            'mois': {
                documentColumn: '문서번호',
                dateColumn: '생산일자'
            },
            'bai': {
                documentColumn: '문서번호',
                dateColumn: '결정일자'
            }
        };
        
        this.currentPage = 1;
        this.itemsPerPage = 50;
        this.searchQuery = '';
        this.sortColumn = 'collected_date';
        this.sortDirection = 'desc';
        this.totalPages = 0;
        this.totalCount = 0;
        
        this.searchTimeout = null;
        this.data = [];
        
        this.init();
    }
    
    updateTableHeaders() {
        // 사이트별 컴럼 헤더 업데이트
        const siteColumns = this.siteColumnNames[this.siteKey];
        if (siteColumns) {
            const documentHeader = document.querySelector('th[data-column="document_number"]');
            const dateHeader = document.querySelector('th[data-column="published_date"]');
            
            if (documentHeader) {
                documentHeader.textContent = siteColumns.documentColumn;
            }
            if (dateHeader) {
                dateHeader.textContent = siteColumns.dateColumn;
            }
        }
    }
    
    init() {
        this.parseUrlParams();
        this.setupEventListeners();
        this.loadData();
        
        console.log(`Expert Data Table initialized for ${this.siteName}`);
    }
    
    parseUrlParams() {
        // URL 파라미터 파싱
        const urlParams = new URLSearchParams(window.location.search);
        this.filterType = urlParams.get('filter');
        this.filterDays = urlParams.get('days');
        this.filterStartDate = urlParams.get('start');
        this.filterEndDate = urlParams.get('end');
    }
    
    setupEventListeners() {
        // Search input
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }
        
        // Refresh button
        document.getElementById('refreshBtn')?.addEventListener('click', () => {
            this.loadData();
        });
        
        // Export button
        document.getElementById('exportBtn')?.addEventListener('click', () => {
            this.exportData();
        });
        
        // 테이블 헤더 정렬은 updateTableHeader에서 동적으로 설정됨
    }
    
    handleSearch(query) {
        // Debounce search to avoid too many API calls
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.searchQuery = query.trim();
            this.currentPage = 1; // Reset to first page
            this.loadData();
        }, 300);
    }
    
    handleSort(column) {
        if (this.sortColumn === column) {
            // Toggle direction if same column
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            // New column, default to descending
            this.sortColumn = column;
            this.sortDirection = 'desc';
        }
        
        this.updateSortIndicators();
        this.sortData();
        this.renderTable();
    }
    
    updateSortIndicators() {
        // Remove all sort classes
        document.querySelectorAll('.data-table th').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        
        // Add sort class to current column
        const currentTh = document.querySelector(`[data-column="${this.sortColumn}"]`);
        if (currentTh) {
            currentTh.classList.add(`sort-${this.sortDirection}`);
        }
    }
    
    async loadData() {
        try {
            this.showLoadingState();
            
            let url = `/api/sites/${this.siteKey}/data?page=${this.currentPage}&limit=${this.itemsPerPage}&search=${encodeURIComponent(this.searchQuery)}`;
            
            // 필터 파라미터 추가
            if (this.filterType) {
                url += `&filter=${this.filterType}`;
                if (this.filterDays) {
                    url += `&days=${this.filterDays}`;
                }
                if (this.filterStartDate && this.filterEndDate) {
                    url += `&start=${this.filterStartDate}&end=${this.filterEndDate}`;
                }
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            this.data = result.data || [];
            this.totalCount = result.pagination?.total_count || 0;
            this.totalPages = result.pagination?.total_pages || 0;
            
            this.updateTableHeader();
            this.updateFilterStatus();
            this.sortData();
            this.renderTable();
            this.renderPagination();
            
        } catch (error) {
            console.error('Failed to load data:', error);
            this.showErrorState();
            this.showToast('로드 오류', 'error', '데이터 로드에 실패했습니다. 다시 시도해주세요.');
        }
    }
    
    sortData() {
        if (!this.data || this.data.length === 0) return;
        
        this.data.sort((a, b) => {
            let valueA = this.getSortValue(a, this.sortColumn);
            let valueB = this.getSortValue(b, this.sortColumn);
            
            // Handle null/undefined values
            if (valueA == null && valueB == null) return 0;
            if (valueA == null) return 1;
            if (valueB == null) return -1;
            
            // Convert to strings for comparison if needed
            if (typeof valueA === 'string') valueA = valueA.toLowerCase();
            if (typeof valueB === 'string') valueB = valueB.toLowerCase();
            
            let result = 0;
            if (valueA < valueB) result = -1;
            else if (valueA > valueB) result = 1;
            
            return this.sortDirection === 'asc' ? result : -result;
        });
    }
    
    getSortValue(item, column) {
        switch (column) {
            case 'organization':
                return this.siteName;
            case 'document_number':
                return item['문서번호'] || item['판례번호'] || item['청구번호'] || '';
            case 'title':
                return item['제목'] || item['심판내용'] || '';
            case 'published_date':
                return item['게시일'] || item['선고일'] || item['결정일'] || item['생산일자'] || item['회신일자'] || item['결정일자'] || '';
            case 'collected_date':
                return item['updated_at'] || item['created_at'] || '';
            // 조세심판원 전용 컬럼
            case 'tax_category':
                return item['세목'] || '';
            case 'claim_number':
                return item['청구번호'] || '';
            case 'decision_date':
                return item['결정일'] || '';
            default:
                return '';
        }
    }
    
    updateTableHeader() {
        const thead = document.querySelector('.data-table thead tr');
        if (!thead) return;
        
        if (this.siteKey === 'tax_tribunal') {
            // 조세심판원: 세목/유형, 청구번호, 제목, 결정일, 수집일
            thead.innerHTML = `
                <th class="sortable" data-column="organization">기관</th>
                <th class="sortable" data-column="tax_category">세목/유형</th>
                <th class="sortable" data-column="claim_number">청구번호</th>
                <th class="sortable" data-column="title">제목</th>
                <th class="sortable" data-column="decision_date">결정일</th>
                <th class="sortable" data-column="collected_date">수집일</th>
            `;
        } else {
            // 기타 사이트: 기존 헤더 유지
            thead.innerHTML = `
                <th class="sortable" data-column="organization">기관</th>
                <th class="sortable" data-column="document_number">문서번호</th>
                <th class="sortable" data-column="title">제목</th>
                <th class="sortable" data-column="published_date">게시일</th>
                <th class="sortable" data-column="collected_date">수집일</th>
            `;
        }
        
        // 정렬 이벤트 리스너 다시 연결
        this.attachSortListeners();
    }
    
    attachSortListeners() {
        document.querySelectorAll('.data-table th.sortable').forEach(th => {
            th.addEventListener('click', () => {
                const column = th.dataset.column;
                this.handleSort(column);
            });
        });
    }
    
    updateFilterStatus() {
        const titleElement = document.getElementById('filterTitle');
        const descriptionElement = document.getElementById('filterDescription');
        
        if (titleElement && descriptionElement) {
            let title = this.siteName;
            let description = '';
            
            // 시간 필터가 적용된 경우
            if (this.filterType === 'recent' && this.filterDays) {
                const dayText = this.filterDays == 1 ? '24시간' : `${this.filterDays}일`;
                title += ` - 최근 ${dayText} 신규 데이터`;
                description = `최근 ${dayText} 동안 수집된 `;
            } else if (this.filterType === 'range' && this.filterStartDate && this.filterEndDate) {
                title += ` - ${this.filterStartDate} ~ ${this.filterEndDate}`;
                description = `${this.filterStartDate}부터 ${this.filterEndDate}까지 수집된 `;
            } else {
                title += ' - 전체 데이터';
                description = '이 소스에서 수집된 ';
            }
            
            // 검색 조건 추가
            if (this.searchQuery) {
                title += ' (검색 결과)';
                description += `"${this.searchQuery}"와 일치하는 `;
            }
            
            description += `${this.totalCount.toLocaleString()}개 항목을 표시하고 있습니다`;
            
            titleElement.textContent = title;
            descriptionElement.textContent = description;
            
            // 필터가 적용된 경우 "전체 데이터 보기" 링크 추가
            if (this.filterType) {
                const viewAllLink = document.createElement('a');
                viewAllLink.href = `/data/${this.siteKey}`;
                viewAllLink.textContent = ' 전체 데이터 보기 →';
                viewAllLink.style.marginLeft = '10px';
                viewAllLink.style.color = 'var(--color-primary)';
                viewAllLink.style.textDecoration = 'none';
                viewAllLink.onmouseover = () => viewAllLink.style.textDecoration = 'underline';
                viewAllLink.onmouseout = () => viewAllLink.style.textDecoration = 'none';
                
                if (!descriptionElement.querySelector('a')) {
                    descriptionElement.appendChild(viewAllLink);
                }
            }
        }
    }
    
    renderTable() {
        const tbody = document.getElementById('dataTableBody');
        if (!tbody) return;
        
        // Hide loading/error states
        this.hideAllStates();
        
        if (!this.data || this.data.length === 0) {
            this.showEmptyState();
            return;
        }
        
        tbody.innerHTML = '';
        
        this.data.forEach(item => {
            const row = this.createTableRow(item);
            tbody.appendChild(row);
        });
        
        // Show the table
        document.getElementById('dataTable').style.display = 'table';
    }
    
    createTableRow(item) {
        const row = document.createElement('tr');
        
        // 사이트별 특화 컬럼 처리
        if (this.siteKey === 'tax_tribunal') {
            // 조세심판원: 세목, 유형, 청구번호, 제목, 결정일 표시
            const taxCategory = item['세목'] || '-';
            const decisionType = item['유형'] || '-';
            const claimNumber = item['청구번호'] || '-';
            const title = item['제목'] || '-';
            const decisionDate = this.formatDate(item['결정일']);
            const collectedDate = this.formatDateTime(item['updated_at'] || item['created_at']);
            const link = item['링크'] || '#';
            
            row.innerHTML = `
                <td>
                    <span class="organization-badge" style="background: ${this.siteColor}; color: white;">
                        ${this.siteName}
                    </span>
                </td>
                <td>
                    <div class="tax-info">
                        <span class="tax-category">${taxCategory}</span>
                        <span class="decision-type" style="font-size: 0.85em; color: #666; margin-left: 4px;">${decisionType}</span>
                    </div>
                </td>
                <td>
                    <span class="document-number">${claimNumber}</span>
                </td>
                <td class="document-title">
                    ${link !== '#' ? 
                        `<a href="${link}" target="_blank" title="${title}">${title}</a>` : 
                        `<span title="${title}">${title}</span>`
                    }
                </td>
                <td class="date-cell">${decisionDate}</td>
                <td class="date-cell">${collectedDate}</td>
            `;
        } else {
            // 기타 사이트: 기존 공통 포맷
            const documentNumber = item['문서번호'] || item['판례번호'] || item['청구번호'] || '-';
            const title = item['제목'] || item['심판내용'] || '-';
            const publishedDate = this.formatDate(item['게시일'] || item['선고일'] || item['결정일'] || item['생산일자'] || item['회신일자'] || item['결정일자']);
            const collectedDate = this.formatDateTime(item['updated_at'] || item['created_at']);
            const link = item['링크'] || item['원문링크'] || '#';
            
            row.innerHTML = `
                <td>
                    <span class="organization-badge" style="background: ${this.siteColor}; color: white;">
                        ${this.siteName}
                    </span>
                </td>
                <td>
                    <span class="document-number">${documentNumber}</span>
                </td>
                <td class="document-title">
                    ${link !== '#' ? 
                        `<a href="${link}" target="_blank" title="${title}">${title}</a>` : 
                        `<span title="${title}">${title}</span>`
                    }
                </td>
                <td class="date-cell">${publishedDate}</td>
                <td class="date-cell">${collectedDate}</td>
            `;
        }
        
        return row;
    }
    
    formatDate(dateString) {
        if (!dateString) return '-';
        
        try {
            // Try to parse various date formats
            let date;
            
            if (dateString.includes('.')) {
                // Format: YYYY.MM.DD
                const parts = dateString.split('.');
                if (parts.length === 3) {
                    date = new Date(parts[0], parts[1] - 1, parts[2]);
                }
            } else if (dateString.includes('-')) {
                // ISO format
                date = new Date(dateString);
            } else {
                // Try direct parsing
                date = new Date(dateString);
            }
            
            if (date && !isNaN(date.getTime())) {
                return date.toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                });
            }
        } catch (error) {
            console.warn('Date parsing failed:', dateString, error);
        }
        
        return dateString; // Return original if parsing fails
    }
    
    formatDateTime(dateString) {
        if (!dateString) return '-';
        
        try {
            // Try to parse various date formats
            let date;
            
            if (dateString.includes('.')) {
                // Format: YYYY.MM.DD
                const parts = dateString.split('.');
                if (parts.length === 3) {
                    date = new Date(parts[0], parts[1] - 1, parts[2]);
                }
            } else if (dateString.includes('-')) {
                // ISO format
                date = new Date(dateString);
            } else {
                // Try direct parsing
                date = new Date(dateString);
            }
            
            if (date && !isNaN(date.getTime())) {
                return date.toLocaleString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false  // 24시간 형식
                });
            }
        } catch (error) {
            console.warn('DateTime parsing failed:', dateString, error);
        }
        
        return dateString; // Return original if parsing fails
    }
    
    renderPagination() {
        const container = document.getElementById('pagination');
        if (!container || this.totalPages <= 1) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'flex';
        container.innerHTML = '';
        
        // 이전 버튼
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '이전';
        prevBtn.disabled = this.currentPage === 1;
        prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        container.appendChild(prevBtn);
        
        // Page numbers
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);
        
        if (startPage > 1) {
            const firstBtn = document.createElement('button');
            firstBtn.textContent = '1';
            firstBtn.addEventListener('click', () => this.goToPage(1));
            container.appendChild(firstBtn);
            
            if (startPage > 2) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '0 var(--spacing-sm)';
                container.appendChild(ellipsis);
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.textContent = i;
            pageBtn.classList.toggle('active', i === this.currentPage);
            pageBtn.addEventListener('click', () => this.goToPage(i));
            container.appendChild(pageBtn);
        }
        
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '0 var(--spacing-sm)';
                container.appendChild(ellipsis);
            }
            
            const lastBtn = document.createElement('button');
            lastBtn.textContent = this.totalPages;
            lastBtn.addEventListener('click', () => this.goToPage(this.totalPages));
            container.appendChild(lastBtn);
        }
        
        // 다음 버튼
        const nextBtn = document.createElement('button');
        nextBtn.textContent = '다음';
        nextBtn.disabled = this.currentPage === this.totalPages;
        nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        container.appendChild(nextBtn);
        
        // 페이지 정보
        const pageInfo = document.createElement('div');
        pageInfo.className = 'pagination-info';
        const startItem = (this.currentPage - 1) * this.itemsPerPage + 1;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, this.totalCount);
        pageInfo.textContent = `${this.totalCount.toLocaleString()}개 중 ${startItem}-${endItem}개 표시`;
        container.appendChild(pageInfo);
    }
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        
        this.currentPage = page;
        this.loadData();
    }
    
    showLoadingState() {
        this.hideAllStates();
        document.getElementById('loadingState').style.display = 'block';
        document.getElementById('dataTable').style.display = 'none';
        document.getElementById('pagination').style.display = 'none';
    }
    
    showErrorState() {
        this.hideAllStates();
        document.getElementById('errorState').style.display = 'block';
        document.getElementById('dataTable').style.display = 'none';
        document.getElementById('pagination').style.display = 'none';
    }
    
    showEmptyState() {
        this.hideAllStates();
        document.getElementById('emptyState').style.display = 'block';
        document.getElementById('dataTable').style.display = 'none';
        document.getElementById('pagination').style.display = 'none';
    }
    
    hideAllStates() {
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('errorState').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';
    }
    
    async exportData() {
        try {
            this.showToast('내보내기 시작', 'info', '데이터 내보내기를 준비하고 있습니다...');
            
            // Get all data (without pagination)
            const url = `/api/sites/${this.siteKey}/data?limit=10000&search=${encodeURIComponent(this.searchQuery)}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error('내보내기 실패');
            }
            
            const result = await response.json();
            const exportData = result.data || [];
            
            // Convert to CSV
            const csv = this.convertToCSV(exportData);
            
            // Download file
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url_obj = URL.createObjectURL(blob);
            link.setAttribute('href', url_obj);
            link.setAttribute('download', `${this.siteKey}_data_${new Date().toISOString().split('T')[0]}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showToast('내보내기 완료', 'success', '데이터가 성공적으로 내보내졌습니다');
            
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast('내보내기 실패', 'error', '데이터 내보내기에 실패했습니다');
        }
    }
    
    convertToCSV(data) {
        if (!data || data.length === 0) return '';
        
        // Get all unique keys from all objects
        const allKeys = new Set();
        data.forEach(item => {
            Object.keys(item).forEach(key => allKeys.add(key));
        });
        
        const headers = Array.from(allKeys);
        const csvRows = [];
        
        // Add header row
        csvRows.push(headers.map(h => `"${h}"`).join(','));
        
        // Add data rows
        data.forEach(item => {
            const row = headers.map(header => {
                const value = item[header] || '';
                return `"${String(value).replace(/"/g, '""')}"`;
            });
            csvRows.push(row.join(','));
        });
        
        return csvRows.join('\n');
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

// Initialize data table when DOM is loaded
let dataTable;

document.addEventListener('DOMContentLoaded', () => {
    dataTable = new ExpertDataTable();
    window.dataTable = dataTable; // Make it globally accessible
});