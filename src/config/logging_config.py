# -*- coding: utf-8 -*-
"""
중앙 로깅 설정 모듈

TaxUpdater 시스템의 모든 로깅을 표준화하고 중앙에서 관리하는 모듈입니다.
콘솔과 파일 출력을 동시에 지원하며, 로그 레벨별로 적절한 포맷을 제공합니다.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    중앙 로깅 시스템 초기화
    
    Args:
        log_level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        log_to_file: 파일 로깅 활성화 여부
        log_dir: 로그 파일 디렉토리
        max_bytes: 로그 파일 최대 크기 (바이트)
        backup_count: 로그 파일 백업 개수
    """
    
    # 로그 레벨 설정
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 로그 포맷 설정
    console_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 로깅 설정
    if log_to_file:
        # 로그 디렉토리 생성
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # 파일 핸들러 설정 (회전 로그)
        log_file = log_path / f"taxupdater_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # 에러 전용 파일 핸들러
        error_log_file = log_path / f"taxupdater_error_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=str(error_log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
    
    # 로깅 시스템 초기화 완료 메시지
    logger = logging.getLogger(__name__)
    logger.info(f"로깅 시스템 초기화 완료 - 레벨: {log_level}, 파일 로깅: {log_to_file}")
    
    # 외부 라이브러리 로깅 레벨 조정
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 반환
    
    Args:
        name: 로거 이름 (보통 __name__ 사용)
    
    Returns:
        설정된 로거 인스턴스
    """
    return logging.getLogger(name)


def log_function_call(func):
    """
    함수 호출 로깅 데코레이터
    
    디버깅 목적으로 함수 호출 시작/종료를 자동 로깅
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"함수 호출 시작: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"함수 호출 완료: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"함수 호출 오류: {func.__name__} - {e}")
            raise
    return wrapper


def log_crawler_progress(site_name: str, current: int, total: int, message: str = "") -> None:
    """
    크롤링 진행률 전용 로깅
    
    Args:
        site_name: 사이트 이름
        current: 현재 진행 수
        total: 전체 수
        message: 추가 메시지
    """
    logger = logging.getLogger("crawler.progress")
    progress_percent = int((current / total * 100)) if total > 0 else 0
    log_message = f"[{site_name}] {progress_percent}% ({current}/{total})"
    if message:
        log_message += f" - {message}"
    logger.info(log_message)


def log_data_operation(operation: str, site_key: str, count: int, details: str = "") -> None:
    """
    데이터 작업 전용 로깅
    
    Args:
        operation: 작업 종류 (save, load, compare 등)
        site_key: 사이트 키
        count: 데이터 개수
        details: 추가 세부사항
    """
    logger = logging.getLogger("data.operation")
    log_message = f"[{operation.upper()}] {site_key}: {count}개"
    if details:
        log_message += f" - {details}"
    logger.info(log_message)