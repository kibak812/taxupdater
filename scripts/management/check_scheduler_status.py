import sys
import os
from datetime import datetime
import pytz

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.scheduler_service import SchedulerService

# 스케줄러 서비스 초기화
scheduler_service = SchedulerService()

print("=== 스케줄러 상태 확인 ===")
print(f"스케줄러 실행 중: {scheduler_service.is_running()}")

if scheduler_service.is_running():
    jobs = scheduler_service.scheduler.get_jobs()
    print(f"등록된 작업 수: {len(jobs)}")
    print("\n=== 등록된 작업 목록 ===")
    
    timezone = pytz.timezone('Asia/Seoul')
    current_time = datetime.now(timezone)
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    for job in jobs:
        print(f"\n작업 ID: {job.id}")
        print(f"  이름: {job.name}")
        print(f"  트리거: {job.trigger}")
        print(f"  다음 실행 시간: {job.next_run_time}")
        if job.next_run_time:
            time_diff = job.next_run_time - current_time
            hours_left = int(time_diff.total_seconds() / 3600)
            minutes_left = int((time_diff.total_seconds() % 3600) / 60)
            print(f"  남은 시간: {hours_left}시간 {minutes_left}분")
else:
    print("스케줄러가 실행되지 않았습니다.")
    
print("\n=== 스케줄 상태 (DB 기준) ===")
status = scheduler_service.get_schedule_status()
if 'schedules' in status:
    for schedule in status['schedules']:
        print(f"\n사이트: {schedule['site_key']}")
        print(f"  Cron 표현식: {schedule['cron_expression']}")
        print(f"  활성화: {schedule['enabled']}")
        if 'scheduler_status' in schedule:
            print(f"  스케줄러 활성: {schedule['scheduler_status']['active']}")
            print(f"  다음 실행: {schedule['scheduler_status']['next_run']}")