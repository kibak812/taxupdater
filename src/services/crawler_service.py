import sys
import os
from typing import Dict, Any, List, Optional, Callable
import pandas as pd

# 웹 전용 환경 - tkinter 지원 제거

# 상위 디렉토리 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import CrawlerInterface, DataRepositoryInterface
from src.services.legacy_notification_service import NotificationService as LegacyNotificationService
from src.config.logging_config import get_logger
import sqlite3
from datetime import datetime
import json
import asyncio


class CrawlingService:
    """
    크롤링 오케스트레이션 서비스
    
    핵심 목적: 대상 사이트의 새로운 데이터 업로드를 누락없이 탐지하고
    정확한 새로운 데이터 식별을 통한 실시간 알림 시스템
    """
    
    def __init__(self, crawlers: Dict[str, CrawlerInterface], repository: DataRepositoryInterface):
        """
        크롤링 서비스 초기화
        
        Args:
            crawlers: 사이트별 크롤러 인스턴스 딕셔너리
            repository: 데이터 저장소 인스턴스
        """
        self.crawlers = crawlers
        self.repository = repository
        self.legacy_notification_service = LegacyNotificationService()
        self.logger = get_logger(__name__)
        
        # 새로운 모니터링 시스템용 notification_service는 필요할 때 import
        self._notification_service = None
    
    @property
    def notification_service(self):
        """지연 로딩을 통한 notification_service 접근"""
        if self._notification_service is None:
            try:
                from src.services.notification_service import NotificationService
                self._notification_service = NotificationService()
            except ImportError:
                self.logger.warning("새로운 알림 서비스를 로드할 수 없습니다. 레거시 서비스를 사용합니다.")
                self._notification_service = self.legacy_notification_service
        return self._notification_service
    
    def execute_crawling(self, choice: str, progress: Optional[Callable], status_message: Optional[Callable], is_periodic: bool = False) -> Dict[str, Any]:
        """
        example.py 기반 새로운 데이터 탐지에 특화된 크롤링 실행 로직
        
        핵심: 누락없는 데이터 수집과 정확한 새로운 데이터 식별
        
        Args:
            choice: 사용자 선택 ("1"-"7")
            progress: 진행률 콜백
            status_message: 상태 메시지 콜백
            is_periodic: 주기적 실행 여부
        """
        summary_results = []
        prefix = "주기적 크롤링 " if is_periodic else ""
        
        # 선택에 따른 크롤러 매핑
        crawler_mapping = {
            "1": ["tax_tribunal"],
            "2": ["nts_authority"],
            "3": ["moef"],
            "4": ["nts_precedent"],
            "5": ["mois"],
            "6": ["bai"],
            "7": list(self.crawlers.keys())  # 실제 사용 가능한 모든 크롤러
        }
        
        # 개별 사이트 선택인 경우 해당 크롤러가 사용 가능한지 확인
        if choice in ["1", "2", "3", "4", "5", "6"]:
            target_crawler = crawler_mapping[choice][0]
            if target_crawler not in self.crawlers:
                error_msg = f"선택된 크롤러 '{target_crawler}'가 사용 불가능합니다."
                self.logger.error(error_msg)
                self._show_message(error_msg)
                return
            selected_crawlers = [target_crawler]
        elif choice == "7":
            # 전체 크롤링인 경우만 사용 가능한 크롤러 필터링
            selected_crawlers = [c for c in self.crawlers.keys()]
        else:
            selected_crawlers = []
        
        if not selected_crawlers:
            self._show_message("잘못된 선택입니다. 유효한 옵션을 선택해 주세요.")
            return {"status": "error", "message": "잘못된 선택", "results": []}
        
        self.logger.info(f"크롤링 시작: {len(selected_crawlers)}개 사이트 대상")
        self.logger.info("=" * 60)
        
        # 선택된 크롤러들 순차 실행
        for idx, crawler_key in enumerate(selected_crawlers):
            if crawler_key in self.crawlers:
                self.logger.info(f"[{idx+1}/{len(selected_crawlers)}] {crawler_key} 크롤링 시작...")
                
                result = self._execute_single_crawler_with_detailed_logging(
                    crawler_key, progress, status_message, prefix, 
                    current_index=idx, total_count=len(selected_crawlers)
                )
                
                summary_results.append(result)
                
                # 새로운 데이터 로깅 및 알림 발송
                if result.get('status') == 'success' and result.get('new_count', 0) > 0:
                    session_id = f"{crawler_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    self.log_new_data_and_notify(
                        crawler_key, 
                        result.get('new_entries', pd.DataFrame()), 
                        session_id
                    )
                
                # 개별 사이트 완료 시 즉시 알림 (전체 크롤링이 아닌 경우) - 레거시 알림
                if choice != "7":
                    alert_message = self.legacy_notification_service.create_new_data_alert(
                        crawler_key, result.get('new_entries', pd.DataFrame()), 
                        result.get('crawling_stats', {})
                    )
                    self._show_message(alert_message)
            else:
                error_result = {
                    'site_key': crawler_key,
                    'status': 'error',
                    'error_message': f"크롤러 '{crawler_key}'를 찾을 수 없습니다.",
                    'new_count': 0
                }
                summary_results.append(error_result)
        
        # 전체 크롤링 종합 요약 (choice == "7"인 경우)
        if choice == "7":
            # TODO: create_batch_crawling_summary 함수 구현 필요
            # summary_message = self.notification_service.create_batch_crawling_summary(summary_results)
            # self._show_message(summary_message)
            
            # 임시로 간단한 요약 메시지 생성
            total_sites = len(summary_results)
            success_sites = len([r for r in summary_results if r.get('status') == 'success'])
            self._show_message(f"전체 크롤링 완료: {success_sites}/{total_sites} 사이트 성공")
            
            # 모니터링 상태 보고서도 생성
            repository_stats = {}
            for crawler_key in selected_crawlers:
                if crawler_key in self.crawlers:
                    stats = self.repository.get_statistics(crawler_key)
                    repository_stats[crawler_key] = stats
            
            monitoring_report = self.notification_service.create_monitoring_status_report(repository_stats)
            self.logger.info(f"\n{monitoring_report}")
        
        self.logger.info("전체 크롤링 완료!")
        self.logger.info("=" * 60)
        
        # 크롤링 결과 반환
        return {
            "status": "success",
            "message": "크롤링 완료",
            "results": summary_results,
            "total_sites": len(selected_crawlers),
            "total_new_count": sum(result.get('new_count', 0) for result in summary_results if result.get('status') == 'success')
        }
    
    def _execute_single_crawler_with_detailed_logging(self, crawler_key: str, progress: Optional[Callable], status_message: Optional[Callable], 
                                                    prefix: str, current_index: int = 0, total_count: int = 1) -> Dict[str, Any]:
        """
        example.py 스타일의 상세한 새로운 데이터 탐지 로직
        
        핵심: 누락없는 데이터 수집과 정확한 새로운 데이터 식별
        """
        try:
            crawler = self.crawlers[crawler_key]
            site_name = crawler.get_site_name()
            key_column = crawler.get_key_column()
            
            # 상태 메시지 업데이트
            if status_message:
                status_message.config(text=f"{site_name} 데이터 크롤링 중...")
                status_message.update()
            
            self.logger.info(f"{site_name} 크롤링 상세 로그:")
            self.logger.info("-" * 50)
            
            # 1단계: 기존 데이터 로드 및 분석
            self.logger.info("[1/4] 기존 데이터 로드 중...")
            existing_data = self.repository.load_existing_data(crawler_key)
            self.logger.info(f"  기존 데이터: {len(existing_data)}개")
            
            if not existing_data.empty:
                existing_keys = set(existing_data[key_column].astype(str))
                self.logger.info(f"  기존 키 개수: {len(existing_keys)}")
                self.logger.debug(f"  기존 키 샘플: {list(existing_keys)[:3]}")
            
            # 2단계: 새 데이터 크롤링
            self.logger.info(f"[2/4] {site_name} 사이트 크롤링 중...")
            if status_message:
                status_message.config(text=f"{site_name} 사이트에서 최신 데이터 수집 중...")
                status_message.update()
            
            new_data = crawler.crawl(progress_callback=progress, status_callback=status_message)
            
            # 데이터 유효성 검증
            if not crawler.validate_data(new_data):
                error_msg = f"  ❌ {site_name}: 크롤링된 데이터가 유효하지 않습니다."
                self.logger.error(error_msg)
                return {
                    'site_key': crawler_key,
                    'status': 'error',
                    'error_message': '데이터 유효성 검증 실패',
                    'new_count': 0,
                    'total_crawled': 0
                }
            
            if new_data.empty:
                error_msg = f"  ⚠️  {site_name}: 크롤링 결과 데이터 없음."
                self.logger.error(error_msg)
                return {
                    'site_key': crawler_key,
                    'status': 'error',
                    'error_message': '크롤링 결과 없음',
                    'new_count': 0,
                    'total_crawled': 0
                }
            
            self.logger.info(f"  크롤링 완료: {len(new_data)}개 항목 수집")
            
            # 3단계: example.py 스타일의 상세한 새로운 데이터 탐지 로직
            self.logger.info("[3/4] 새로운 데이터 탐지 및 분석...")
            if status_message:
                status_message.config(text=f"{site_name} 새로운 데이터 분석 중...")
                status_message.update()
            
            # example.py의 compare_data 로직을 정확히 재현
            self.logger.debug("  [DEBUG] compare_data 스타일 분석:")
            self.logger.debug(f"    기존 데이터: {len(existing_data)}개")
            self.logger.debug(f"    새 데이터: {len(new_data)}개")
            
            if existing_data.empty:
                new_entries = new_data
                self.logger.info(f"    기존 데이터 없음, 모든 {len(new_data)}개가 신규 데이터")
            else:
                # 키 집합 분석 (example.py와 동일한 방식)
                existing_keys = set(existing_data[key_column].astype(str))
                new_keys = set(new_data[key_column].astype(str))
                
                self.logger.debug(f"    기존 키 개수: {len(existing_keys)}")
                self.logger.debug(f"    새 키 개수: {len(new_keys)}")
                self.logger.debug(f"    기존 키 샘플: {list(existing_keys)[:3]}")
                self.logger.debug(f"    새 키 샘플: {list(new_keys)[:3]}")
                
                # 차집합 계산 (example.py와 동일)
                new_only = new_keys - existing_keys
                existing_only = existing_keys - new_keys
                common = existing_keys & new_keys
                
                self.logger.info(f"    새 데이터에만 있는 키: {len(new_only)}개")
                self.logger.debug(f"    기존 데이터에만 있는 키: {len(existing_only)}개")
                self.logger.debug(f"    공통 키: {len(common)}개")
                
                if len(new_only) > 0:
                    self.logger.info(f"    새 키 샘플: {list(new_only)[:5]}")
                if len(existing_only) > 0:
                    self.logger.debug(f"    기존 전용 키 샘플: {list(existing_only)[:5]}")
                
                # SQLite Repository의 고성능 비교 로직 사용
                new_entries = self.repository.compare_and_get_new_entries(
                    crawler_key, new_data, key_column
                )
                
                self.logger.info(f"    최종 새 항목: {len(new_entries)}개")
            
            # 4단계: 데이터 저장 및 백업
            self.logger.info("[4/4] 데이터 저장 및 백업...")
            crawling_stats = {
                'total_crawled': len(new_data),
                'existing_count': len(existing_data),
                'new_count': len(new_entries),
                'success_rate': 100.0,
                'site_name': site_name
            }
            
            if not new_entries.empty:
                if status_message:
                    status_message.config(text=f"{site_name} 새로운 데이터 {len(new_entries)}개 저장 중...")
                    status_message.update()
                
                # 백업 생성
                backup_path = self.repository.backup_data(crawler_key, new_entries)
                self.logger.info(f"  백업 완료: {backup_path}")
                
                # 데이터 저장 (기존 데이터에 신규 데이터 추가)
                save_success = self.repository.save_data(crawler_key, new_entries, is_incremental=True)
                
                if save_success:
                    self.logger.info(f"  저장 완료: {len(new_entries)}개 신규 항목")
                    
                    # 샘플 새 데이터 정보 출력
                    samples = self._get_new_data_samples(new_entries, crawler_key, 3)
                    if samples:
                        self.logger.info(f"  신규 데이터 샘플: {', '.join(samples)}")
                else:
                    self.logger.error("  저장 실패")
                    return {
                        'site_key': crawler_key,
                        'status': 'error',
                        'error_message': '데이터 저장 실패',
                        'new_count': len(new_entries),
                        'total_crawled': len(new_data)
                    }
            else:
                self.logger.info("  새로운 데이터 없음 (모든 데이터가 기존에 존재)")
            
            # 진행률 업데이트 (웹 환경 전용)
            if progress and hasattr(progress, 'value'):
                overall_progress = int(((current_index + 1) / total_count) * 100)
                progress.value = overall_progress
                progress.update()
            
            if status_message and hasattr(status_message, 'config'):
                status_message.config(text=f"{site_name} 완료: 신규 {len(new_entries)}개")
                status_message.update()
            
            self.logger.info(f"  {site_name} 크롤링 완료!")
            self.logger.info(f"    전체 수집: {len(new_data)}개")
            self.logger.info(f"    신규 발견: {len(new_entries)}개")
            self.logger.info(f"    중복 제외: {len(new_data) - len(new_entries)}개")
            
            return {
                'site_key': crawler_key,
                'status': 'success',
                'new_count': len(new_entries),
                'total_crawled': len(new_data),
                'existing_count': len(existing_data),
                'new_entries': new_entries,
                'crawling_stats': crawling_stats,
                'key_samples': self._get_new_data_samples(new_entries, crawler_key, 5)
            }
                
        except Exception as e:
            error_msg = f"  ❌ {crawler_key} 크롤링 중 오류 발생: {str(e)}"
            print(error_msg)
            
            # 오류 알림 생성
            error_alert = self.notification_service.create_error_alert(
                crawler_key, 
                {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'retry_count': 0,
                    'next_retry': '수동 재시도 필요'
                }
            )
            self.logger.error(f"\n{error_alert}")
            
            return {
                'site_key': crawler_key,
                'status': 'error',
                'error_message': str(e),
                'new_count': 0,
                'total_crawled': 0
            }
    
    def get_crawler_statistics(self) -> Dict[str, Any]:
        """모든 크롤러의 통계 정보 반환"""
        stats = {}
        for crawler_key, crawler in self.crawlers.items():
            try:
                site_name = crawler.get_site_name()
                repo_stats = self.repository.get_statistics(crawler_key)
                stats[site_name] = repo_stats
            except Exception as e:
                stats[crawler_key] = {"error": str(e)}
        return stats
    
    def get_monitoring_summary(self) -> str:
        """전체 모니터링 현황 요약 반환"""
        repository_stats = {}
        for crawler_key in self.crawlers.keys():
            stats = self.repository.get_statistics(crawler_key)
            repository_stats[crawler_key] = stats
        
        return self.notification_service.create_monitoring_status_report(repository_stats)
    
    def test_new_data_detection(self, crawler_key: str) -> Dict[str, Any]:
        """새로운 데이터 탐지 기능 테스트 (개발/디버깅용)"""
        if crawler_key not in self.crawlers:
            return {"error": f"크롤러 '{crawler_key}'를 찾을 수 없습니다."}
        
        self.logger.info(f"{crawler_key} 새로운 데이터 탐지 테스트")
        self.logger.info("=" * 50)
        
        try:
            # 실제 크롤링 실행하여 새로운 데이터 탐지 테스트
            result = self._execute_single_crawler_with_detailed_logging(
                crawler_key, None, None, "테스트: ", 0, 1
            )
            
            test_result = {
                "crawler_key": crawler_key,
                "test_status": "success",
                "new_data_detected": result.get('new_count', 0),
                "total_crawled": result.get('total_crawled', 0),
                "detection_accuracy": "정상" if result.get('status') == 'success' else "오류",
                "test_timestamp": pd.Timestamp.now()
            }
            
            self.logger.info("테스트 결과:")
            self.logger.info(f"  새로운 데이터 탐지: {test_result['new_data_detected']}개")
            self.logger.info(f"  전체 수집: {test_result['total_crawled']}개")
            self.logger.info(f"  탐지 정확도: {test_result['detection_accuracy']}")
            
            return test_result
            
        except Exception as e:
            error_result = {
                "crawler_key": crawler_key,
                "test_status": "error",
                "error_message": str(e),
                "test_timestamp": pd.Timestamp.now()
            }
            self.logger.error(f"테스트 실패: {str(e)}")
            return error_result
    
    def _show_message(self, message: str) -> None:
        """메시지 표시 (웹 환경 전용)"""
        self.logger.info(f"[알림] 크롤링 완료: {message}")
    
    def log_new_data_and_notify(self, site_key: str, new_entries: pd.DataFrame, session_id: str = None) -> None:
        """새로운 데이터를 로그에 기록하고 알림 발송"""
        if new_entries.empty:
            return
        
        try:
            # 사이트별 키 컬럼 매핑
            key_column_mapping = {
                "tax_tribunal": "청구번호",
                "nts_authority": "문서번호", 
                "nts_precedent": "문서번호",
                "moef": "문서번호",
                "mois": "문서번호",
                "bai": "문서번호"
            }
            
            key_column = key_column_mapping.get(site_key, "문서번호")
            current_time = datetime.now()
            
            # new_data_log 테이블에 개별 데이터 기록
            with sqlite3.connect(self.repository.db_path) as conn:
                for _, row in new_entries.iterrows():
                    data_id = str(row.get(key_column, "unknown"))
                    data_title = str(row.get("제목", ""))[:200]  # 제목 길이 제한
                    data_category = str(row.get("세목", ""))
                    data_date = str(row.get("생산일자", row.get("결정일자", row.get("회신일자", ""))))
                    
                    # 데이터 요약 생성
                    data_summary = self._create_data_summary(row, site_key)
                    
                    # 태그 생성
                    tags = self._generate_tags(row, site_key)
                    
                    # 메타데이터 생성
                    metadata = {
                        "crawl_session_id": session_id,
                        "original_data": dict(row.head(5)),  # 처음 5개 컬럼만 저장
                        "site_key": site_key
                    }
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO new_data_log 
                        (site_key, data_id, data_type, data_title, data_summary,
                         data_category, data_date, crawl_session_id, discovered_at,
                         tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        site_key,
                        data_id,
                        "record",
                        data_title,
                        data_summary,
                        data_category,
                        data_date,
                        session_id,
                        current_time.isoformat(),
                        json.dumps(tags, ensure_ascii=False),
                        json.dumps(metadata, ensure_ascii=False)
                    ))
                
                inserted_count = conn.total_changes
                self.logger.info(f"새로운 데이터 로그 기록: {inserted_count}개")
            
            # 알림 발송 (비동기)
            if hasattr(self.notification_service, 'send_new_data_notification'):
                try:
                    # asyncio 이벤트 루프가 있는 경우에만 알림 발송
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self.notification_service.send_new_data_notification(
                                site_key, len(new_entries), session_id
                            )
                        )
                    else:
                        # 이벤트 루프가 없는 경우 새 루프 생성하여 실행
                        asyncio.run(
                            self.notification_service.send_new_data_notification(
                                site_key, len(new_entries), session_id
                            )
                        )
                except Exception as e:
                    self.logger.warning(f"알림 발송 실패: {e}")
            
        except Exception as e:
            self.logger.error(f"새로운 데이터 로깅 실패: {e}")
    
    def _create_data_summary(self, row: pd.Series, site_key: str) -> str:
        """데이터 요약 생성"""
        try:
            if site_key == "tax_tribunal":
                return f"{row.get('세목', '')} - {row.get('유형', '')} ({row.get('결정일', '')})"
            elif site_key in ["nts_authority", "nts_precedent"]:
                return f"{row.get('세목', '')} 관련 ({row.get('생산일자', '')})"
            elif site_key == "moef":
                return f"기획재정부 해석 ({row.get('회신일자', '')})"
            elif site_key == "mois":
                return f"{row.get('세목', '')} 유권해석 ({row.get('생산일자', '')})"
            elif site_key == "bai":
                return f"{row.get('청구분야', '')} 심사 ({row.get('결정일자', '')})"
            else:
                return str(row.get("제목", ""))[:100]
        except Exception:
            return "데이터 요약 생성 실패"
    
    def _generate_tags(self, row: pd.Series, site_key: str) -> List[str]:
        """데이터 태그 생성"""
        tags = [site_key]
        
        try:
            # 세목 태그
            if "세목" in row and row["세목"]:
                tags.append(f"세목:{row['세목']}")
            
            # 청구분야 태그 (감사원)
            if "청구분야" in row and row["청구분야"]:
                tags.append(f"분야:{row['청구분야']}")
            
            # 유형 태그 (조세심판원)
            if "유형" in row and row["유형"]:
                tags.append(f"유형:{row['유형']}")
            
            # 시간 태그
            current_time = datetime.now()
            tags.append(f"발견:{current_time.strftime('%Y-%m')}")
            
            # 중요도 태그 (제목에 특정 키워드가 있는 경우)
            title = str(row.get("제목", "")).lower()
            important_keywords = ["긴급", "중요", "신설", "개정", "폐지", "특례"]
            
            for keyword in important_keywords:
                if keyword in title:
                    tags.append("중요")
                    break
            
        except Exception as e:
            self.logger.warning(f"태그 생성 중 오류: {e}")
        
        return tags[:10]  # 최대 10개 태그
    
    def _get_new_data_samples(self, new_entries: pd.DataFrame, site_key: str, limit: int = 3) -> List[str]:
        """새로운 데이터 샘플 생성"""
        if new_entries.empty:
            return []
        
        try:
            # 사이트별 키 컬럼 매핑
            key_column_mapping = {
                "tax_tribunal": "청구번호",
                "nts_authority": "문서번호", 
                "nts_precedent": "문서번호",
                "moef": "문서번호",
                "mois": "문서번호",
                "bai": "문서번호"
            }
            
            key_column = key_column_mapping.get(site_key, "문서번호")
            samples = []
            
            # 제한된 수만큼 샘플 생성
            for i in range(min(limit, len(new_entries))):
                row = new_entries.iloc[i]
                key_value = str(row.get(key_column, "unknown"))
                title = str(row.get("제목", ""))[:50]  # 제목 50자 제한
                
                if title:
                    sample = f"{key_value} ({title}...)"
                else:
                    sample = key_value
                
                samples.append(sample)
            
            return samples
            
        except Exception as e:
            self.logger.warning(f"샘플 생성 중 오류: {e}")
            return []