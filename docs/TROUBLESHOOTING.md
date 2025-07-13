# 문제 해결 가이드

이 문서는 예규판례 모니터링 시스템 운영 중 발생할 수 있는 문제와 해결 방법을 다룹니다.

## 목차
- [일반적인 문제](#일반적인-문제)
- [크롤링 관련 문제](#크롤링-관련-문제)
- [데이터베이스 문제](#데이터베이스-문제)
- [UI/UX 문제](#uiux-문제)
- [배포 환경 문제](#배포-환경-문제)

---

## 일반적인 문제

### 서비스가 시작되지 않을 때
**증상**: 웹 서버가 시작되지 않거나 접속이 되지 않음

**해결 방법**:
1. 포트 사용 확인
   ```bash
   lsof -i :8001
   ```
2. 가상환경 활성화 확인
   ```bash
   source taxupdater_venv/bin/activate
   ```
3. 의존성 설치 확인
   ```bash
   pip install -r requirements.txt
   ```

### 메모리 부족 문제
**증상**: 크롤링 중 메모리 오류 발생

**해결 방법**:
1. Chrome 드라이버 프로세스 종료
   ```bash
   pkill -f chromedriver
   ```
2. 크롤링 범위 축소 (settings.py)
   ```python
   CRAWLING_CONFIG = {
       "max_pages": 10,  # 20에서 축소
       "max_items": 2000,  # 5000에서 축소
   }
   ```

## 크롤링 관련 문제

### 크롤링 진행현황이 표시되지 않을 때
**문제점**: 스케줄러 서비스를 통한 정확한 로그 생성 필요

**해결 방법**:
```python
# 변경 전 (문제): 직접 크롤링 서비스 호출
crawling_service.execute_crawling("7", None, None, is_periodic=False)

# 변경 후 (해결): 스케줄러 서비스를 통한 체계적 로깅
scheduler_service._execute_all_sites_crawl()
```

### WebSocketProgress 에러
**문제점**: `progress['value']` 형식 사용 시 에러

**해결 방법**:
```python
# WebSocketProgress 객체는 .value 속성 사용
progress.value = percentage  # ✓ 올바른 방식
progress['value'] = percentage  # ✗ 잘못된 방식 (tkinter 스타일)
```

### 스케줄러 토글 버그
**문제점**: "스케줄러가 이미 중지되어 있습니다" 메시지 오류

**해결 방법**:
```javascript
// 실제 시스템 상태 기반 판단
async toggleScheduler() {
    const statusResponse = await fetch('/api/system-status');
    const statusData = await statusResponse.json();
    const isCurrentlyRunning = statusData.scheduler_status?.scheduler_running || false;
    
    const endpoint = isCurrentlyRunning ? '/api/scheduler/stop' : '/api/scheduler/start';
}
```

### 스케줄 주기 변경 문제
**문제점**: 크롤링 주기 변경 후 "다음 실행" 시간 미반영

**해결 방법**:
```javascript
// 동적 cron 표현식 생성
generateCronExpression(hours) {
    if (hours >= 24) {
        const days = Math.floor(hours / 24);
        return `0 0 */${days} * *`;  // 일 단위
    } else {
        return `0 */${hours} * * *`;  // 시간 단위
    }
}
```

## 데이터베이스 문제

### SQLite UNIQUE Constraint 에러
**문제점**: PRIMARY KEY 충돌 시 데이터 저장 실패

**해결 방법**:
```python
# INSERT OR IGNORE 방식으로 자동 처리
try:
    new_entries.to_sql(table_name, conn, if_exists='append', index=False)
except sqlite3.IntegrityError:
    self._insert_with_ignore(conn, table_name, new_entries, key_column)
```

### 마이그레이션 실패
**문제점**: Fly.io 배포 환경에서 모니터링 시스템 테이블 누락

**해결 방법**:
1. 자동 마이그레이션 시스템
   ```python
   from src.database.migrations import DatabaseMigration
   migration = DatabaseMigration(repository.db_path)
   if migration.get_migration_status()['migration_needed']:
       migration.migrate_to_monitoring_system()
   ```

2. 수동 마이그레이션
   ```bash
   fly ssh console
   python src/database/migrations.py
   ```

### 타임스탬프 누락
**문제점**: 시간 기반 필터링 및 통계 기능 정확도 저하

**해결 방법**:
```python
# Repository 레벨에서 자동 주입
from datetime import datetime
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
if 'created_at' not in data.columns:
    data['created_at'] = timestamp
if 'updated_at' not in data.columns:
    data['updated_at'] = timestamp
```

## UI/UX 문제

### WebSocket 연결 상태 표시 문제
**문제점**: "실시간 연결 상태: 연결 끊어짐" 표시

**해결 방법**:
```javascript
// window.app을 전역으로 노출
document.addEventListener('DOMContentLoaded', () => {
    app = new TaxCrawlerApp();
    window.app = app; // 전역으로 노출하여 HTML에서 접근 가능
});
```

### 데이터 카운트 불일치
**문제점**: 대시보드 카드 숫자와 실제 데이터 개수 불일치

**해결 방법**:
1. 단일 데이터 소스 사용
   ```javascript
   // 각 사이트 테이블에서 직접 조회
   fetch(`/api/sites/recent-counts?hours=${this.currentTimeFilter}`)
   ```

2. 일관된 쿼리 사용
   ```python
   # created_at/updated_at 기준 통일
   SELECT COUNT(*) FROM [{table_name}] 
   WHERE {time_column} > datetime('now', '-{hours} hours')
   ```

### 마지막 업데이트 시간 표시 오류
**문제점**: 모든 사이트가 동일한 시간 표시

**해결 방법**:
```python
# 실제 데이터의 최신 시간 조회
if 'created_at' in existing_columns or 'updated_at' in existing_columns:
    time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
    cursor.execute(f"SELECT MAX({time_column}) FROM [{table_name}]")
    actual_last_updated = cursor.fetchone()[0]
```

## 배포 환경 문제

### Fly.io 500 에러
**문제점**: 모니터링 기능 관련 API 500 에러

**원인**:
1. 데이터베이스 테이블 누락
2. 서비스 초기화 실패
3. None 상태에서 메서드 호출 시도

**해결 방법**:
```python
# 안전한 서비스 초기화
try:
    scheduler_service = SchedulerService(db_path=repository.db_path)
    notification_service = NotificationService(db_path=repository.db_path)
except Exception as e:
    logger.error(f"모니터링 시스템 초기화 실패: {e}")
    scheduler_service = None
    notification_service = None
```

### LocalTunnel 연결 문제
**문제점**: 터널이 연결되지 않거나 중단됨

**해결 방법**:
1. 서비스 상태 확인
   ```bash
   systemctl --user status localtunnel
   ```

2. 서비스 재시작
   ```bash
   systemctl --user restart localtunnel
   ```

3. 로그 확인
   ```bash
   journalctl --user -u localtunnel -f
   ```

4. 필요 시 수동 실행으로 디버깅
   ```bash
   lt --port 8001 --subdomain taxupdater-monitor
   ```

---

## 관련 문서
- 기술적 세부사항: [TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)
- 배포 가이드: [DEPLOYMENT.md](./DEPLOYMENT.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)