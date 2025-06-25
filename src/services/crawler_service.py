import sys
import os
from typing import Dict, Any, List
import pandas as pd

# tkinter import를 선택적으로 처리 (웹 환경에서는 불필요)
try:
    from tkinter import messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# 상위 디렉토리 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import CrawlerInterface, DataRepositoryInterface
from src.services.notification_service import NotificationService


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
        self.notification_service = NotificationService()
    
    def execute_crawling(self, choice: str, progress, status_message, is_periodic: bool = False):
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
            "7": ["tax_tribunal", "nts_authority", "moef", "nts_precedent", "mois", "bai"]
        }
        
        selected_crawlers = crawler_mapping.get(choice, [])
        
        if not selected_crawlers:
            self._show_message("잘못된 선택입니다. 유효한 옵션을 선택해 주세요.")
            return
        
        print(f"\n🎯 크롤링 시작: {len(selected_crawlers)}개 사이트 대상")
        print("=" * 60)
        
        # 선택된 크롤러들 순차 실행
        for idx, crawler_key in enumerate(selected_crawlers):
            if crawler_key in self.crawlers:
                print(f"\n📍 [{idx+1}/{len(selected_crawlers)}] {crawler_key} 크롤링 시작...")
                
                result = self._execute_single_crawler_with_detailed_logging(
                    crawler_key, progress, status_message, prefix, 
                    current_index=idx, total_count=len(selected_crawlers)
                )
                
                summary_results.append(result)
                
                # 개별 사이트 완료 시 즉시 알림 (전체 크롤링이 아닌 경우)
                if choice != "7":
                    alert_message = self.notification_service.create_new_data_alert(
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
            summary_message = self.notification_service.create_batch_crawling_summary(summary_results)
            self._show_message(summary_message)
            
            # 모니터링 상태 보고서도 생성
            repository_stats = {}
            for crawler_key in selected_crawlers:
                if crawler_key in self.crawlers:
                    stats = self.repository.get_statistics(crawler_key)
                    repository_stats[crawler_key] = stats
            
            monitoring_report = self.notification_service.create_monitoring_status_report(repository_stats)
            print(f"\n{monitoring_report}")
        
        print(f"\n✅ 전체 크롤링 완료!")
        print("=" * 60)
    
    def _execute_single_crawler_with_detailed_logging(self, crawler_key: str, progress, status_message, 
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
            
            print(f"\n🔍 {site_name} 크롤링 상세 로그:")
            print("-" * 50)
            
            # 1단계: 기존 데이터 로드 및 분석
            print(f"[1/4] 기존 데이터 로드 중...")
            existing_data = self.repository.load_existing_data(crawler_key)
            print(f"  📊 기존 데이터: {len(existing_data)}개")
            
            if not existing_data.empty:
                existing_keys = set(existing_data[key_column].astype(str))
                print(f"  🔑 기존 키 개수: {len(existing_keys)}")
                print(f"  📝 기존 키 샘플: {list(existing_keys)[:3]}")
            
            # 2단계: 새 데이터 크롤링
            print(f"[2/4] {site_name} 사이트 크롤링 중...")
            if status_message:
                status_message.config(text=f"{site_name} 사이트에서 최신 데이터 수집 중...")
                status_message.update()
            
            new_data = crawler.crawl(progress_callback=progress, status_callback=status_message)
            
            # 데이터 유효성 검증
            if not crawler.validate_data(new_data):
                error_msg = f"  ❌ {site_name}: 크롤링된 데이터가 유효하지 않습니다."
                print(error_msg)
                return {
                    'site_key': crawler_key,
                    'status': 'error',
                    'error_message': '데이터 유효성 검증 실패',
                    'new_count': 0,
                    'total_crawled': 0
                }
            
            if new_data.empty:
                error_msg = f"  ⚠️  {site_name}: 크롤링 결과 데이터 없음."
                print(error_msg)
                return {
                    'site_key': crawler_key,
                    'status': 'error',
                    'error_message': '크롤링 결과 없음',
                    'new_count': 0,
                    'total_crawled': 0
                }
            
            print(f"  ✅ 크롤링 완료: {len(new_data)}개 항목 수집")
            
            # 3단계: example.py 스타일의 상세한 새로운 데이터 탐지 로직
            print(f"[3/4] 새로운 데이터 탐지 및 분석...")
            if status_message:
                status_message.config(text=f"{site_name} 새로운 데이터 분석 중...")
                status_message.update()
            
            # example.py의 compare_data 로직을 정확히 재현
            print(f"  [DEBUG] compare_data 스타일 분석:")
            print(f"    기존 데이터: {len(existing_data)}개")
            print(f"    새 데이터: {len(new_data)}개")
            
            if existing_data.empty:
                new_entries = new_data
                print(f"    ➡️  기존 데이터 없음, 모든 {len(new_data)}개가 신규 데이터")
            else:
                # 키 집합 분석 (example.py와 동일한 방식)
                existing_keys = set(existing_data[key_column].astype(str))
                new_keys = set(new_data[key_column].astype(str))
                
                print(f"    기존 키 개수: {len(existing_keys)}")
                print(f"    새 키 개수: {len(new_keys)}")
                print(f"    기존 키 샘플: {list(existing_keys)[:3]}")
                print(f"    새 키 샘플: {list(new_keys)[:3]}")
                
                # 차집합 계산 (example.py와 동일)
                new_only = new_keys - existing_keys
                existing_only = existing_keys - new_keys
                common = existing_keys & new_keys
                
                print(f"    새 데이터에만 있는 키: {len(new_only)}개")
                print(f"    기존 데이터에만 있는 키: {len(existing_only)}개")
                print(f"    공통 키: {len(common)}개")
                
                if len(new_only) > 0:
                    print(f"    🆕 새 키 샘플: {list(new_only)[:5]}")
                if len(existing_only) > 0:
                    print(f"    📁 기존 전용 키 샘플: {list(existing_only)[:5]}")
                
                # SQLite Repository의 고성능 비교 로직 사용
                new_entries = self.repository.compare_and_get_new_entries(
                    crawler_key, new_data, key_column
                )
                
                print(f"    최종 새 항목: {len(new_entries)}개")
            
            # 4단계: 데이터 저장 및 백업
            print(f"[4/4] 데이터 저장 및 백업...")
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
                print(f"  💾 백업 완료: {backup_path}")
                
                # 데이터 저장 (증분 저장)
                save_success = self.repository.save_data(crawler_key, new_data, is_incremental=True)
                
                if save_success:
                    print(f"  ✅ 저장 완료: {len(new_entries)}개 신규 항목")
                    
                    # 샘플 새 데이터 정보 출력
                    samples = self.notification_service.get_new_data_samples(new_entries, crawler_key, 3)
                    if samples:
                        print(f"  📋 신규 데이터 샘플: {', '.join(samples)}")
                else:
                    print(f"  ❌ 저장 실패")
                    return {
                        'site_key': crawler_key,
                        'status': 'error',
                        'error_message': '데이터 저장 실패',
                        'new_count': len(new_entries),
                        'total_crawled': len(new_data)
                    }
            else:
                print(f"  ✅ 새로운 데이터 없음 (모든 데이터가 기존에 존재)")
            
            # 진행률 업데이트
            if progress:
                overall_progress = int(((current_index + 1) / total_count) * 100)
                progress['value'] = overall_progress
                progress.update()
            
            if status_message:
                status_message.config(text=f"{site_name} 완료: 신규 {len(new_entries)}개")
                status_message.update()
            
            print(f"  🎯 {site_name} 크롤링 완료!")
            print(f"    전체 수집: {len(new_data)}개")
            print(f"    신규 발견: {len(new_entries)}개")
            print(f"    중복 제외: {len(new_data) - len(new_entries)}개")
            
            return {
                'site_key': crawler_key,
                'status': 'success',
                'new_count': len(new_entries),
                'total_crawled': len(new_data),
                'existing_count': len(existing_data),
                'new_entries': new_entries,
                'crawling_stats': crawling_stats,
                'key_samples': self.notification_service.get_new_data_samples(new_entries, crawler_key, 5)
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
            print(f"\n{error_alert}")
            
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
        
        print(f"\n🧪 {crawler_key} 새로운 데이터 탐지 테스트")
        print("=" * 50)
        
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
            
            print(f"\n🧪 테스트 결과:")
            print(f"  새로운 데이터 탐지: {test_result['new_data_detected']}개")
            print(f"  전체 수집: {test_result['total_crawled']}개")
            print(f"  탐지 정확도: {test_result['detection_accuracy']}")
            
            return test_result
            
        except Exception as e:
            error_result = {
                "crawler_key": crawler_key,
                "test_status": "error",
                "error_message": str(e),
                "test_timestamp": pd.Timestamp.now()
            }
            print(f"\n❌ 테스트 실패: {str(e)}")
            return error_result
    
    def _show_message(self, message):
        """메시지 표시"""
        if TKINTER_AVAILABLE:
            messagebox.showinfo("크롤링 완료", message)
        else:
            print(f"[알림] 크롤링 완료: {message}")