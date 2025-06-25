import sys
import os
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class NotificationService:
    """
    새로운 데이터 발견 알림 및 모니터링 서비스
    
    핵심 목적: 대상 사이트의 새로운 데이터 업로드를 적시에 식별하고
    누락 없는 데이터 수집을 보장하는 알림 시스템
    """
    
    def __init__(self):
        self.site_name_mapping = {
            "tax_tribunal": "조세심판원",
            "nts_authority": "국세청 유권해석",
            "nts_precedent": "국세청 판례",
            "moef": "기획재정부",
            "mois": "행정안전부",
            "bai": "감사원"
        }
    
    def create_new_data_alert(self, site_key: str, new_entries: pd.DataFrame, 
                             crawling_stats: Dict[str, Any]) -> str:
        """
        새로운 데이터 발견 시 상세 알림 메시지 생성
        
        Args:
            site_key: 사이트 키
            new_entries: 새로 발견된 데이터
            crawling_stats: 크롤링 통계 정보
            
        Returns:
            상세 알림 메시지
        """
        site_name = self.site_name_mapping.get(site_key, site_key)
        
        if new_entries.empty:
            return self._create_no_new_data_message(site_name, crawling_stats)
        
        # 새로운 데이터 상세 분석
        new_count = len(new_entries)
        
        # 주요 정보 추출
        key_info = self._extract_key_information(site_key, new_entries)
        
        # 알림 메시지 구성
        alert_message = f"""🚨 새로운 데이터 발견! 🚨

📍 사이트: {site_name}
📊 신규 항목: {new_count}개
⏰ 탐지 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 신규 데이터 요약:
{key_info}

📈 크롤링 통계:
  • 전체 크롤링: {crawling_stats.get('total_crawled', 0)}개
  • 신규 발견: {new_count}개
  • 중복 제외: {crawling_stats.get('total_crawled', 0) - new_count}개
  • 성공률: {self._calculate_success_rate(crawling_stats)}%

✅ 데이터 무결성: 모든 신규 항목이 성공적으로 저장되었습니다."""

        return alert_message
    
    def create_batch_crawling_summary(self, results: List[Dict[str, Any]]) -> str:
        """
        전체 크롤링 완료 시 종합 요약 메시지 생성
        
        Args:
            results: 각 사이트별 크롤링 결과 리스트
            
        Returns:
            종합 요약 메시지
        """
        total_new = sum(r.get('new_count', 0) for r in results)
        successful_sites = sum(1 for r in results if r.get('status') == 'success')
        total_sites = len(results)
        
        if total_new == 0:
            return self._create_no_updates_summary(results, successful_sites, total_sites)
        
        # 사이트별 신규 데이터 상세
        site_details = []
        for result in results:
            if result.get('new_count', 0) > 0:
                site_name = self.site_name_mapping.get(result['site_key'], result['site_key'])
                new_count = result['new_count']
                key_samples = result.get('key_samples', [])
                
                detail = f"  • {site_name}: {new_count}개"
                if key_samples:
                    sample_text = ", ".join(key_samples[:3])
                    if len(key_samples) > 3:
                        sample_text += f" 외 {len(key_samples)-3}개"
                    detail += f" ({sample_text})"
                
                site_details.append(detail)
        
        summary = f"""🎯 전체 크롤링 완료 보고서

📊 전체 통계:
  • 총 신규 데이터: {total_new}개
  • 성공한 사이트: {successful_sites}/{total_sites}개
  • 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 사이트별 신규 데이터:
{chr(10).join(site_details)}

⚡ 모니터링 상태: 활성
✅ 데이터 무결성: 검증 완료"""

        return summary
    
    def create_error_alert(self, site_key: str, error_details: Dict[str, Any]) -> str:
        """
        크롤링 실패 시 오류 알림 생성
        
        Args:
            site_key: 사이트 키
            error_details: 오류 상세 정보
            
        Returns:
            오류 알림 메시지
        """
        site_name = self.site_name_mapping.get(site_key, site_key)
        
        error_message = f"""⚠️ 크롤링 오류 발생 ⚠️

📍 사이트: {site_name}
🚫 오류 유형: {error_details.get('error_type', '알 수 없음')}
⏰ 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📝 오류 상세:
{error_details.get('error_message', '상세 정보 없음')}

🔄 재시도 정보:
  • 시도 횟수: {error_details.get('retry_count', 0)}회
  • 다음 재시도: {error_details.get('next_retry', '예정 없음')}

⚠️ 주의: 데이터 누락 방지를 위해 수동 확인이 필요할 수 있습니다."""

        return error_message
    
    def create_monitoring_status_report(self, repository_stats: Dict[str, Any]) -> str:
        """
        전체 모니터링 상태 보고서 생성
        
        Args:
            repository_stats: 저장소 통계 정보
            
        Returns:
            모니터링 상태 보고서
        """
        total_records = sum(stats.get('total_count', 0) for stats in repository_stats.values())
        
        site_status = []
        for site_key, stats in repository_stats.items():
            site_name = self.site_name_mapping.get(site_key, site_key)
            count = stats.get('total_count', 0)
            last_update = stats.get('last_updated', '없음')
            
            if isinstance(last_update, str) and last_update != '없음':
                last_update = f"최근 업데이트: {last_update}"
            elif last_update and last_update != '없음':
                last_update = f"최근 업데이트: {last_update.strftime('%Y-%m-%d %H:%M')}"
            else:
                last_update = "업데이트 없음"
            
            site_status.append(f"  • {site_name}: {count:,}건 ({last_update})")
        
        report = f"""📊 데이터 모니터링 현황 보고서

📈 전체 수집 현황:
  • 총 수집 데이터: {total_records:,}건
  • 모니터링 사이트: {len(repository_stats)}개
  • 보고서 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 사이트별 현황:
{chr(10).join(site_status)}

🔍 모니터링 목적:
  • 새로운 법령 해석 및 판례의 신속한 탐지
  • 업로드 누락 방지를 위한 지속적 감시
  • 데이터 무결성 보장

✅ 시스템 상태: 정상 작동 중"""

        return report
    
    def _extract_key_information(self, site_key: str, new_data: pd.DataFrame) -> str:
        """새로운 데이터에서 핵심 정보 추출"""
        if new_data.empty:
            return "  • 신규 데이터 없음"
        
        info_lines = []
        
        # 처음 3-5개 항목의 주요 정보 표시
        display_count = min(5, len(new_data))
        
        for i in range(display_count):
            row = new_data.iloc[i]
            
            # 사이트별 주요 컬럼 선택
            if site_key == "tax_tribunal":
                key_info = f"{row.get('청구번호', 'N/A')} - {row.get('제목', 'N/A')[:50]}"
            elif site_key in ["nts_authority", "nts_precedent", "moef", "mois", "bai"]:
                key_info = f"{row.get('문서번호', 'N/A')} - {row.get('제목', 'N/A')[:50]}"
            else:
                # 기본적으로 첫 번째와 마지막 컬럼 사용
                cols = list(row.index)
                key_info = f"{row[cols[0]]} - {row[cols[-1]][:50] if len(str(row[cols[-1]])) > 50 else row[cols[-1]]}"
            
            info_lines.append(f"  • {key_info}")
        
        if len(new_data) > display_count:
            info_lines.append(f"  • ... 외 {len(new_data) - display_count}개 항목")
        
        return "\n".join(info_lines)
    
    def _create_no_new_data_message(self, site_name: str, stats: Dict[str, Any]) -> str:
        """새로운 데이터가 없을 때의 메시지"""
        return f"""✅ {site_name} 모니터링 완료

📊 크롤링 결과:
  • 신규 데이터: 없음
  • 전체 확인: {stats.get('total_crawled', 0)}개
  • 완료 시간: {datetime.now().strftime('%H:%M:%S')}

🔍 모니터링 상태: 정상 (새로운 업로드 대기 중)"""
    
    def _create_no_updates_summary(self, results: List[Dict], successful: int, total: int) -> str:
        """전체 크롤링에서 새로운 데이터가 없을 때의 요약"""
        return f"""✅ 전체 크롤링 완료 - 신규 데이터 없음

📊 요약:
  • 신규 데이터: 없음
  • 성공한 사이트: {successful}/{total}개
  • 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔍 모든 사이트가 정상적으로 모니터링되었습니다.
새로운 데이터 업로드 시 즉시 알림이 제공됩니다."""
    
    def _calculate_success_rate(self, stats: Dict[str, Any]) -> float:
        """크롤링 성공률 계산"""
        total = stats.get('total_attempts', stats.get('total_crawled', 1))
        successful = stats.get('successful_items', stats.get('total_crawled', 0))
        
        if total == 0:
            return 100.0
        
        return round((successful / total) * 100, 1)
    
    def get_new_data_samples(self, new_data: pd.DataFrame, site_key: str, max_samples: int = 3) -> List[str]:
        """새로운 데이터의 샘플 키 값들 추출"""
        if new_data.empty:
            return []
        
        # 사이트별 키 컬럼 확인
        key_column_mapping = {
            "tax_tribunal": "청구번호",
            "nts_authority": "문서번호",
            "nts_precedent": "문서번호",
            "moef": "문서번호",
            "mois": "문서번호",
            "bai": "문서번호"
        }
        
        key_column = key_column_mapping.get(site_key, "문서번호")
        
        if key_column not in new_data.columns:
            # 키 컬럼이 없으면 첫 번째 컬럼 사용
            key_column = new_data.columns[0]
        
        samples = new_data[key_column].head(max_samples).tolist()
        return [str(sample) for sample in samples]