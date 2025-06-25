import sys
import os
from tkinter import messagebox

# 상위 디렉토리 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class CrawlingService:
    """크롤링 오케스트레이션 서비스"""
    
    def __init__(self, crawler_functions, data_service):
        """
        크롤링 서비스 초기화
        
        Args:
            crawler_functions: 크롤러 함수들의 딕셔너리
            data_service: 데이터 처리 서비스
        """
        self.crawler_functions = crawler_functions
        self.data_service = data_service
    
    def execute_crawling(self, choice, progress, status_message, is_periodic=False):
        """공통 크롤링 실행 로직"""
        summary_messages = []
        prefix = "주기적 크롤링 " if is_periodic else ""

        # 심판원 크롤링
        if choice == "1" or choice == "7":
            msg = self._execute_tax_tribunal_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)

        # 국세청 유권해석 크롤링
        if choice == "2" or choice == "7":
            msg = self._execute_nts_authority_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)
                
        # 기획재정부 크롤링
        if choice == "3" or choice == "7":
            msg = self._execute_moef_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)

        # 국세청 판례 크롤링
        if choice == "4" or choice == "7":
            msg = self._execute_nts_precedent_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)

        # 행정안전부 유권해석 크롤링
        if choice == "5" or choice == "7":
            msg = self._execute_mois_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)

        # 감사원 심사결정례 크롤링
        if choice == "6" or choice == "7":
            msg = self._execute_bai_crawling(progress, status_message, prefix)
            if choice == "7":
                summary_messages.append(msg)
            else:
                self._show_message(msg)
        
        # 전체 크롤링 결과 표시
        if choice == "7":
            if summary_messages:
                result_prefix = "주기적 크롤링 결과:\n" if is_periodic else ""
                self._show_message(result_prefix + "\n".join(summary_messages))
            else:
                self._show_message(f"{prefix}: 처리된 항목이 없습니다.")
        elif choice not in ["1", "2", "3", "4", "5", "6"]:
            self._show_message("잘못된 선택입니다. 유효한 옵션을 선택해 주세요.")
    
    def _execute_tax_tribunal_crawling(self, progress, status_message, prefix):
        """조세심판원 크롤링 실행"""
        site_name = "심판원"
        try:
            existing_data = self.data_service.load_existing_data(site_name)
            all_new_data = []
            
            # SECTIONS는 example.py에서 가져와야 함 - 임시로 하드코딩
            sections = ["20", "11", "50", "12", "40", "95", "99"]
            total_sections = len(sections)
            
            for idx, section in enumerate(sections):
                section_data = self.crawler_functions['crawl_data'](
                    site_name, section, 20, progress=progress, 
                    status_message=status_message, current_section_index=idx, 
                    total_sections=total_sections
                )
                all_new_data.append(section_data)
            
            if all_new_data:
                import pandas as pd
                new_data = pd.concat(all_new_data, ignore_index=True)
                if not new_data.empty:
                    new_entries = self.data_service.compare_data(existing_data, new_data, key_column="청구번호")
                    if not new_entries.empty:
                        self.data_service.save_updated_data(site_name, new_entries)
                        self.data_service.update_existing_data(site_name, new_data)
                        return f"{prefix}(심판원): 새로운 심판례 {len(new_entries)} 개 발견."
                    else:
                        return f"{prefix}(심판원): 새로운 심판례 없음."
                else:
                    return f"{prefix}(심판원): 크롤링 결과 데이터 없음."
            else:
                return f"{prefix}(심판원): 크롤링 중 오류 또는 데이터 없음."
        except Exception as e:
            return f"{prefix}(심판원): 오류 발생 - {str(e)}"
    
    def _execute_nts_authority_crawling(self, progress, status_message, prefix):
        """국세청 유권해석 크롤링 실행"""
        site_name = "국세청"
        try:
            dynamic_data = self.crawler_functions['crawl_dynamic_site'](progress=progress, status_message=status_message)
            existing_data = self.data_service.load_existing_data(site_name)
            if not dynamic_data.empty:
                new_entries = self.data_service.compare_data(existing_data, dynamic_data, key_column="문서번호")
                if not new_entries.empty:
                    self.data_service.save_updated_data(site_name, new_entries)
                    self.data_service.update_existing_data(site_name, dynamic_data)
                    return f"{prefix}(국세청 유권해석): 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    return f"{prefix}(국세청 유권해석): 새로운 유권해석 없음."
            else:
                return f"{prefix}(국세청 유권해석): 크롤링 결과 데이터 없음."
        except Exception as e:
            return f"{prefix}(국세청 유권해석): 오류 발생 - {str(e)}"
    
    def _execute_moef_crawling(self, progress, status_message, prefix):
        """기획재정부 크롤링 실행"""
        site_name = "기획재정부"
        try:
            moef_data = self.crawler_functions['crawl_moef_site'](progress=progress, status_message=status_message)
            existing_data = self.data_service.load_existing_data(site_name)
            if not moef_data.empty:
                new_entries = self.data_service.compare_data(existing_data, moef_data, key_column="문서번호")
                if not new_entries.empty:
                    self.data_service.save_updated_data(site_name, new_entries)
                    self.data_service.update_existing_data(site_name, moef_data)
                    return f"{prefix}(기획재정부): 새로운 해석 {len(new_entries)} 개 발견."
                else:
                    return f"{prefix}(기획재정부): 새로운 해석 없음."
            else:
                return f"{prefix}(기획재정부): 크롤링 결과 데이터 없음."
        except Exception as e:
            return f"{prefix}(기획재정부): 오류 발생 - {str(e)}"
    
    def _execute_nts_precedent_crawling(self, progress, status_message, prefix):
        """국세청 판례 크롤링 실행"""
        site_name = "국세청_판례"
        try:
            nts_precedent_data = self.crawler_functions['crawl_nts_precedents'](progress=progress, status_message=status_message)
            existing_data = self.data_service.load_existing_data(site_name)
            if not nts_precedent_data.empty:
                new_entries = self.data_service.compare_data(existing_data, nts_precedent_data, key_column="문서번호")
                if not new_entries.empty:
                    self.data_service.save_updated_data(site_name, new_entries)
                    self.data_service.update_existing_data(site_name, nts_precedent_data)
                    return f"{prefix}(국세청 판례): 새로운 판례 {len(new_entries)} 개 발견."
                else:
                    return f"{prefix}(국세청 판례): 새로운 판례 없음."
            else:
                return f"{prefix}(국세청 판례): 크롤링 결과 데이터 없음."
        except Exception as e:
            return f"{prefix}(국세청 판례): 오류 발생 - {str(e)}"
    
    def _execute_mois_crawling(self, progress, status_message, prefix):
        """행정안전부 크롤링 실행"""
        site_name = "행정안전부"
        try:
            existing_data = self.data_service.load_existing_data(site_name)
            mois_data = self.crawler_functions['crawl_mois_site'](progress=progress, status_message=status_message)
            if not mois_data.empty:
                new_entries = self.data_service.compare_data(existing_data, mois_data, key_column="문서번호")
                if not new_entries.empty:
                    self.data_service.save_updated_data(site_name, new_entries)
                    self.data_service.update_existing_data(site_name, mois_data)
                    return f"{prefix}(행정안전부): 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    return f"{prefix}(행정안전부): 새로운 유권해석 없음."
            else:
                return f"{prefix}(행정안전부): 크롤링 결과 데이터 없음."
        except Exception as e:
            return f"{prefix}(행정안전부): 오류 발생 - {str(e)}"
    
    def _execute_bai_crawling(self, progress, status_message, prefix):
        """감사원 크롤링 실행"""
        site_name = "감사원"
        try:
            existing_data = self.data_service.load_existing_data(site_name)
            bai_data = self.crawler_functions['crawl_bai_site'](progress=progress, status_message=status_message)
            if not bai_data.empty:
                new_entries = self.data_service.compare_data(existing_data, bai_data, key_column="문서번호")
                if not new_entries.empty:
                    self.data_service.save_updated_data(site_name, new_entries)
                    self.data_service.update_existing_data(site_name, bai_data)
                    return f"{prefix}(감사원): 새로운 심사결정례 {len(new_entries)} 개 발견."
                else:
                    return f"{prefix}(감사원): 새로운 심사결정례 없음."
            else:
                return f"{prefix}(감사원): 크롤링 결과 데이터 없음."
        except Exception as e:
            return f"{prefix}(감사원): 오류 발생 - {str(e)}"
    
    def _show_message(self, message):
        """메시지 표시"""
        messagebox.showinfo("크롤링 완료", message)