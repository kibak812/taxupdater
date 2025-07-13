#!/usr/bin/env python3
"""
LocalTunnel 연결 모니터링 및 복구 스크립트
주기적으로 연결 상태를 확인하고 필요시 재시작
"""
import subprocess
import time
import requests
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/kibaek/claude-dev/taxupdater/logs/localtunnel_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_local_service():
    """로컬 서비스 상태 확인"""
    try:
        response = requests.get('http://localhost:8001', timeout=5)
        return response.status_code == 200
    except:
        return False

def check_tunnel_connection():
    """터널 연결 상태 확인"""
    try:
        response = requests.get('https://taxupdater-monitor.loca.lt', timeout=10)
        return response.status_code == 200
    except:
        return False

def restart_localtunnel():
    """LocalTunnel 서비스 재시작"""
    logger.info("LocalTunnel 서비스 재시작 중...")
    subprocess.run(['systemctl', '--user', 'restart', 'localtunnel'], check=True)
    time.sleep(5)  # 서비스가 시작될 시간 대기

def main():
    """메인 모니터링 루프"""
    logger.info("LocalTunnel 모니터링 시작")
    
    consecutive_failures = 0
    check_interval = 30  # 30초마다 확인
    
    while True:
        try:
            # 로컬 서비스 확인
            if not check_local_service():
                logger.error("로컬 서비스가 응답하지 않습니다!")
                subprocess.run(['systemctl', '--user', 'restart', 'taxupdater'], check=True)
                time.sleep(10)
                continue
            
            # 터널 연결 확인
            if not check_tunnel_connection():
                consecutive_failures += 1
                logger.warning(f"터널 연결 실패 (연속 {consecutive_failures}회)")
                
                if consecutive_failures >= 3:
                    logger.error("터널 연결이 지속적으로 실패합니다. 서비스 재시작...")
                    restart_localtunnel()
                    consecutive_failures = 0
                    time.sleep(10)
            else:
                if consecutive_failures > 0:
                    logger.info("터널 연결 복구됨")
                consecutive_failures = 0
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("모니터링 종료")
            break
        except Exception as e:
            logger.error(f"모니터링 중 오류 발생: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()