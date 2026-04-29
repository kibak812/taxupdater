import sqlite3
from datetime import datetime

# 데이터베이스 연결
conn = sqlite3.connect('data/tax_data.db')
cursor = conn.cursor()

# 스케줄 데이터 조회
cursor.execute("SELECT site_key, cron_expression, enabled, created_at, updated_at FROM crawl_schedules")
schedules = cursor.fetchall()

print("=== 현재 스케줄 설정 ===")
for schedule in schedules:
    site_key, cron_expr, enabled, created_at, updated_at = schedule
    print(f"사이트: {site_key}")
    print(f"  Cron 표현식: {cron_expr}")
    print(f"  활성화: {enabled}")
    print(f"  생성일: {created_at}")
    print(f"  수정일: {updated_at}")
    print()

conn.close()