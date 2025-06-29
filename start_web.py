#!/usr/bin/env python3
"""
Tax Law Crawler Web Interface 시작 스크립트

사용법:
    python start_web.py

웹 브라우저에서 http://localhost:8000 으로 접속하세요.
"""

import subprocess
import sys
import os
from pathlib import Path

# 로깅 시스템 초기화
sys.path.append(os.path.dirname(__file__))
from src.config.logging_config import setup_logging, get_logger
setup_logging(log_level="INFO", log_to_file=True)
logger = get_logger(__name__)

def main():
    """웹 서버 시작"""
    logger.info("세금 법령 크롤링 웹 인터페이스 시작 중...")
    logger.info("=" * 60)
    
    # 현재 디렉토리 확인
    current_dir = Path(__file__).parent
    os.chdir(current_dir)
    
    # 가상환경 활성화 명령어 구성
    venv_path = current_dir / "taxupdater_venv"
    if not venv_path.exists():
        logger.error("가상환경을 찾을 수 없습니다.")
        logger.info("먼저 다음 명령어로 의존성을 설치해주세요:")
        logger.info("  python -m venv taxupdater_venv")
        logger.info("  source taxupdater_venv/bin/activate")
        logger.info("  pip install -r requirements.txt")
        return 1
    
    try:
        # 웹 서버 시작
        logger.info("FastAPI 웹 서버 시작 중...")
        logger.info("접속 주소: http://localhost:8000")
        logger.info("실시간 모니터링 활성화됨")
        logger.info("종료하려면 Ctrl+C를 누르세요")
        logger.info("=" * 60)
        
        # 가상환경의 uvicorn 실행
        python_exe = venv_path / "bin" / "python"
        uvicorn_cmd = [
            str(python_exe), "-m", "uvicorn",
            "src.web.app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ]
        
        subprocess.run(uvicorn_cmd, check=True)
        
    except KeyboardInterrupt:
        logger.info("웹 서버가 정상적으로 종료되었습니다.")
        return 0
    except subprocess.CalledProcessError as e:
        logger.error(f"웹 서버 시작 실패: {e}")
        logger.info("문제 해결 방법:")
        logger.info("1. 의존성 재설치: pip install -r requirements.txt")
        logger.info("2. 포트 확인: 8000번 포트가 사용 중인지 확인")
        logger.info("3. 권한 확인: 파일 읽기 권한 확인")
        return 1
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())