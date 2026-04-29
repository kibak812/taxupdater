import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any
import sys

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import DataRepositoryInterface
from src.config.settings import FILE_CONFIG, DATA_COLUMNS, KEY_COLUMNS


class ExcelRepository(DataRepositoryInterface):
    """
    Excel 기반 데이터 저장소
    
    현재 Excel 파일 시스템을 유지하면서도 향후 SQLite나 PostgreSQL로
    쉽게 전환할 수 있도록 Repository 패턴으로 추상화
    """
    
    def __init__(self):
        self.data_folder = FILE_CONFIG["data_folder"]
        self.existing_file_template = FILE_CONFIG["existing_file_template"]
        self.updated_folder_template = FILE_CONFIG["updated_folder_template"]
        
        # 데이터 폴더 생성
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
    
    def load_existing_data(self, site_key: str) -> pd.DataFrame:
        """기존 데이터 로드"""
        site_name = self._get_site_name_from_key(site_key)
        existing_file = os.path.join(
            self.data_folder, 
            self.existing_file_template.format(site_name=site_name)
        )
        
        if os.path.exists(existing_file):
            try:
                return pd.read_excel(existing_file)
            except Exception as e:
                print(f"기존 데이터 로드 실패 ({existing_file}): {e}")
                return self._create_empty_dataframe(site_key)
        
        return self._create_empty_dataframe(site_key)
    
    def save_data(self, site_key: str, data: pd.DataFrame, is_incremental: bool = True) -> bool:
        """데이터 저장"""
        try:
            site_name = self._get_site_name_from_key(site_key)
            main_file = os.path.join(
                self.data_folder,
                self.existing_file_template.format(site_name=site_name)
            )
            
            if is_incremental and os.path.exists(main_file):
                # 증분 저장: 기존 데이터와 병합
                existing_data = self.load_existing_data(site_key)
                key_column = KEY_COLUMNS.get(site_key, "문서번호")
                
                # 중복 제거하여 병합
                new_entries = data[~data[key_column].isin(existing_data[key_column])]
                combined_data = pd.concat([existing_data, new_entries], ignore_index=True)
                
                # 키 컬럼으로 정렬
                combined_data = combined_data.sort_values(by=key_column, ascending=False)
                combined_data = combined_data.reset_index(drop=True)
                
                combined_data.to_excel(main_file, index=False)
                print(f"증분 저장 완료: {len(new_entries)}개 신규 항목 추가")
                
                return True
            else:
                # 전체 저장
                data.to_excel(main_file, index=False)
                print(f"전체 저장 완료: {len(data)}개 항목")
                return True
                
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
            return False
    
    def compare_and_get_new_entries(self, site_key: str, new_data: pd.DataFrame, key_column: str) -> pd.DataFrame:
        """신규 데이터 추출"""
        existing_data = self.load_existing_data(site_key)
        
        if existing_data.empty:
            return new_data
        
        if key_column not in existing_data.columns or key_column not in new_data.columns:
            raise KeyError(f"키 컬럼 '{key_column}'이 데이터에 존재하지 않습니다.")
        
        # 디버깅 정보
        print(f"[DEBUG] {site_key} 데이터 비교:")
        print(f"  기존 데이터: {len(existing_data)}개")
        print(f"  새 데이터: {len(new_data)}개")
        
        existing_keys = set(existing_data[key_column].astype(str))
        new_keys = set(new_data[key_column].astype(str))
        
        new_only = new_keys - existing_keys
        print(f"  신규 데이터: {len(new_only)}개")
        
        # 신규 항목만 추출
        new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
        print(f"  최종 신규 항목: {len(new_entries)}개")
        
        return new_entries
    
    def backup_data(self, site_key: str, data: pd.DataFrame) -> str:
        """데이터 백업"""
        try:
            site_name = self._get_site_name_from_key(site_key)
            backup_folder = self.updated_folder_template.format(site_name=site_name)
            
            if not os.path.exists(backup_folder):
                os.makedirs(backup_folder)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_folder, f"backup_{timestamp}.xlsx")
            
            data.to_excel(backup_file, index=False)
            print(f"백업 완료: {backup_file}")
            
            return backup_file
            
        except Exception as e:
            print(f"백업 실패: {e}")
            return ""
    
    def get_statistics(self, site_key: str) -> Dict[str, Any]:
        """데이터 통계 정보 반환"""
        try:
            data = self.load_existing_data(site_key)
            
            if data.empty:
                return {"total_count": 0, "last_updated": None}
            
            site_name = self._get_site_name_from_key(site_key)
            main_file = os.path.join(
                self.data_folder,
                self.existing_file_template.format(site_name=site_name)
            )
            
            # 파일 수정 시간
            last_updated = None
            if os.path.exists(main_file):
                last_updated = datetime.fromtimestamp(os.path.getmtime(main_file))
            
            # 기본 통계
            stats = {
                "total_count": len(data),
                "last_updated": last_updated,
                "columns": list(data.columns),
                "file_size_mb": round(os.path.getsize(main_file) / 1024 / 1024, 2) if os.path.exists(main_file) else 0
            }
            
            # 날짜 컬럼이 있는 경우 날짜 범위 추가
            date_columns = [col for col in data.columns if '일자' in col or '일' in col]
            if date_columns:
                for col in date_columns:
                    try:
                        date_series = pd.to_datetime(data[col], errors='coerce')
                        valid_dates = date_series.dropna()
                        if not valid_dates.empty:
                            stats[f"{col}_range"] = {
                                "earliest": valid_dates.min(),
                                "latest": valid_dates.max()
                            }
                    except Exception:
                        continue
            
            return stats
            
        except Exception as e:
            print(f"통계 정보 조회 실패: {e}")
            return {"total_count": 0, "last_updated": None, "error": str(e)}
    
    def _create_empty_dataframe(self, site_key: str) -> pd.DataFrame:
        """빈 데이터프레임 생성"""
        columns = DATA_COLUMNS.get(site_key, [])
        return pd.DataFrame(columns=columns)
    
    def _get_site_name_from_key(self, site_key: str) -> str:
        """사이트 키를 사이트 이름으로 변환"""
        key_to_name_mapping = {
            "tax_tribunal": "심판원",
            "nts_authority": "국세청",
            "nts_precedent": "국세청_판례",
            "moef": "기획재정부",
            "mois": "행정안전부",
            "bai": "감사원"
        }
        return key_to_name_mapping.get(site_key, site_key)


class SQLiteRepository(DataRepositoryInterface):
    """
    SQLite 기반 데이터 저장소 (향후 구현 예정)
    
    현재는 스켈레톤만 제공하며, 향후 Excel에서 SQLite로 전환할 때
    ExcelRepository와 동일한 인터페이스로 교체 가능
    """
    
    def __init__(self, db_path: str = "tax_data.db"):
        self.db_path = db_path
        # TODO: SQLite 연결 및 테이블 생성 로직 구현
        pass
    
    def load_existing_data(self, site_key: str) -> pd.DataFrame:
        # TODO: SQLite에서 데이터 로드
        raise NotImplementedError("SQLite 저장소는 향후 구현 예정입니다.")
    
    def save_data(self, site_key: str, data: pd.DataFrame, is_incremental: bool = True) -> bool:
        # TODO: SQLite에 데이터 저장
        raise NotImplementedError("SQLite 저장소는 향후 구현 예정입니다.")
    
    def compare_and_get_new_entries(self, site_key: str, new_data: pd.DataFrame, key_column: str) -> pd.DataFrame:
        # TODO: SQLite에서 신규 데이터 추출
        raise NotImplementedError("SQLite 저장소는 향후 구현 예정입니다.")
    
    def backup_data(self, site_key: str, data: pd.DataFrame) -> str:
        # TODO: SQLite 백업
        raise NotImplementedError("SQLite 저장소는 향후 구현 예정입니다.")
    
    def get_statistics(self, site_key: str) -> Dict[str, Any]:
        # TODO: SQLite 통계 조회
        raise NotImplementedError("SQLite 저장소는 향후 구현 예정입니다.")