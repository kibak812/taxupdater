/**
 * Shared frontend utilities (TaxUI).
 * Loaded by base.html before page scripts.
 */

(function () {
    'use strict';

    const SITE_NAMES = {
        tax_tribunal: '심판원 결정례',
        nts_authority: '국세청 유권해석',
        nts_precedent: '국세청 판례',
        moef: '기획재정부',
        mois: '행정안전부',
        bai: '감사원',
        scourt_major_decisions: '전국법원 주요판결',
        scourt_scheduled_decisions: '대법원 선고예정'
    };

    const SITE_COLORS = {
        tax_tribunal: '#4F46E5',
        nts_authority: '#059669',
        nts_precedent: '#D97706',
        moef: '#8B5CF6',
        mois: '#DC2626',
        bai: '#6B7280',
        scourt_major_decisions: '#0F766E',
        scourt_scheduled_decisions: '#B45309'
    };

    const SOURCE_ORDER = [
        'nts_authority',
        'nts_precedent',
        'tax_tribunal',
        'moef',
        'mois',
        'bai',
        'scourt_major_decisions',
        'scourt_scheduled_decisions'
    ];

    const NOTIFICATION_SETTING_KEY = 'taxupdater_browser_notifications';

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function getSiteName(siteKey, fallback = '') {
        return SITE_NAMES[siteKey] || fallback || siteKey;
    }

    function getSiteColor(siteKey) {
        return SITE_COLORS[siteKey] || '#6B7280';
    }

    function showToast(title, type, message) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div><strong>${escapeHtml(title)}</strong></div>
            <div>${escapeHtml(message)}</div>
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

    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`${url} ${response.status}`);
        }
        return response.json();
    }

    async function fetchOptionalJson(url, fallback) {
        try {
            const response = await fetch(url);
            if (!response.ok) return fallback;
            return response.json();
        } catch (error) {
            return fallback;
        }
    }

    /**
     * One-way crawl progress channel with automatic reconnect.
     * Returns { close } — close() stops reconnecting and closes the socket.
     */
    function connectCrawlSocket({ onMessage, onStatusChange, reconnectDelay = 5000 } = {}) {
        let socket = null;
        let closed = false;

        function open() {
            if (closed) return;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            try {
                socket = new WebSocket(`${protocol}//${window.location.host}/ws/crawl`);
            } catch (error) {
                onStatusChange?.(false);
                setTimeout(open, reconnectDelay);
                return;
            }

            socket.onopen = () => onStatusChange?.(true);
            socket.onmessage = (event) => {
                try {
                    onMessage?.(JSON.parse(event.data));
                } catch (error) {
                    console.error('WebSocket message parsing error:', error);
                }
            };
            socket.onclose = () => {
                onStatusChange?.(false);
                if (!closed) {
                    setTimeout(open, reconnectDelay);
                }
            };
            socket.onerror = () => onStatusChange?.(false);
        }

        open();

        return {
            close() {
                closed = true;
                socket?.close();
            }
        };
    }

    /** Normalize date-like values ("2026.06.23.", "26-6-23", ISO) to "YYYY-MM-DD". */
    function formatDateOnly(value) {
        const text = String(value || '').trim();
        if (!text || text === '-') return '';

        const compact = text
            .replace(/[.]\s*$/, '')
            .replace(/\./g, '-')
            .split(/[T\s]/)[0];
        const match = compact.match(/^(\d{2}|\d{4})-(\d{1,2})-(\d{1,2})$/);
        if (match) {
            const rawYear = match[1];
            const year = rawYear.length === 2 ? 2000 + Number(rawYear) : Number(rawYear);
            const month = Number(match[2]);
            const day = Number(match[3]);
            const date = new Date(year, month - 1, day);
            if (
                date.getFullYear() === year &&
                date.getMonth() === month - 1 &&
                date.getDate() === day
            ) {
                return [
                    String(year).padStart(4, '0'),
                    String(month).padStart(2, '0'),
                    String(day).padStart(2, '0')
                ].join('-');
            }
        }

        const parsed = new Date(text);
        if (!Number.isNaN(parsed.getTime())) {
            return [
                String(parsed.getFullYear()).padStart(4, '0'),
                String(parsed.getMonth() + 1).padStart(2, '0'),
                String(parsed.getDate()).padStart(2, '0')
            ].join('-');
        }

        return text;
    }

    function formatRelativeTime(date) {
        if (!date || Number.isNaN(date.getTime())) return '--';

        const diffInMinutes = Math.floor((Date.now() - date.getTime()) / 60000);

        if (diffInMinutes < 1) return '방금 전';
        if (diffInMinutes < 60) return `${diffInMinutes}분 전`;

        const diffInHours = Math.floor(diffInMinutes / 60);
        if (diffInHours < 24) return `${diffInHours}시간 전`;

        const diffInDays = Math.floor(diffInHours / 24);
        if (diffInDays < 7) return `${diffInDays}일 전`;

        return date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' });
    }

    function loadNotificationSetting() {
        try {
            const saved = localStorage.getItem(NOTIFICATION_SETTING_KEY);
            return saved ? JSON.parse(saved) : false;
        } catch (error) {
            return false;
        }
    }

    function saveNotificationSetting(enabled) {
        try {
            localStorage.setItem(NOTIFICATION_SETTING_KEY, JSON.stringify(enabled));
        } catch (error) {
            return false;
        }
        return true;
    }

    window.TaxUI = {
        SITE_NAMES,
        SITE_COLORS,
        SOURCE_ORDER,
        escapeHtml,
        getSiteName,
        getSiteColor,
        showToast,
        fetchJson,
        fetchOptionalJson,
        connectCrawlSocket,
        formatDateOnly,
        formatRelativeTime,
        loadNotificationSetting,
        saveNotificationSetting
    };
})();
