import os
import pandas as pd
from datetime import datetime
import sys

# 상위 디렉토리 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.config.settings import FILE_CONFIG, DATA_COLUMNS, KEY_COLUMNS


class DataService:
    """데이터 처리 서비스"""
    
    def __init__(self):
        self.data_folder = FILE_CONFIG["data_folder"]
        self.existing_file_template = FILE_CONFIG["existing_file_template"]
        self.updated_folder_template = FILE_CONFIG["updated_folder_template"]
    
    def load_existing_data(self, site_name):
        """기존 데이터 로드"""
        existing_file = os.path.join(self.data_folder, self.existing_file_template.format(site_name=site_name))
        
        if os.path.exists(existing_file):
            return pd.read_excel(existing_file)
        
        # 기존 파일이 없는 경우 빈 DataFrame 반환
        columns = DATA_COLUMNS.get(self._get_site_key(site_name), [])
        return pd.DataFrame(columns=columns)
    
    def compare_data(self, existing_data, new_data, key_column):
        """새로운 데이터와 기존 데이터 비교"""
        if key_column not in existing_data.columns or key_column not in new_data.columns:
            raise KeyError(f"Both datasets must contain '{key_column}' column to compare data.")
        
        # 디버깅 정보
        print(f"[DEBUG] compare_data:")
        print(f"  기존 데이터: {len(existing_data)}개")
        print(f"  새 데이터: {len(new_data)}개")
        
        existing_keys = set(existing_data[key_column].astype(str))
        new_keys = set(new_data[key_column].astype(str))
        
        print(f"  기존 키 개수: {len(existing_keys)}")
        print(f"  새 키 개수: {len(new_keys)}")
        
        # 차집합 계산
        new_only = new_keys - existing_keys
        print(f"  새 데이터에만 있는 키: {len(new_only)}개")
        
        if len(new_only) > 0:
            print(f"  새 키 샘플: {list(new_only)[:5]}")
        
        # 원래 로직
        new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
        print(f"  최종 새 항목: {len(new_entries)}개")
        
        return new_entries
    
    def save_updated_data(self, site_name, updated_data):
        """업데이트된 데이터를 저장"""
        if not updated_data.empty:
            updated_folder = self.updated_folder_template.format(site_name=site_name)
            if not os.path.exists(updated_folder):
                os.makedirs(updated_folder)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            updated_file = os.path.join(updated_folder, f"updated_cases_{timestamp}.xlsx")
            updated_data.to_excel(updated_file, index=False)
            print(f"업데이트된 사례가 {updated_file}에 저장되었습니다.")
    
    def update_existing_data(self, site_name, new_data):
        """기존 데이터에 새 데이터를 추가"""
        key_column = KEY_COLUMNS.get(self._get_site_key(site_name), "문서번호")
        existing_file = os.path.join(self.data_folder, self.existing_file_template.format(site_name=site_name))
        
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        if os.path.exists(existing_file):
            # 기존 데이터 로드
            existing_data = pd.read_excel(existing_file)
            
            # 기존 데이터와 새 데이터에서 중복되지 않는 항목만 추가
            new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
            
            # 기존 데이터와 새 데이터 병합
            updated_data = pd.concat([existing_data, new_entries], ignore_index=True)
        else:
            # 기존 파일이 없는 경우 새 데이터를 그대로 사용
            updated_data = new_data
        
        # 병합된 데이터 저장
        updated_data.to_excel(existing_file, index=False)
        print(f"기존 데이터에 새 데이터가 추가되어 {existing_file}에 저장되었습니다.")
    
    def _get_site_key(self, site_name):
        """사이트 이름을 설정 키로 변환"""
        site_key_mapping = {
            "심판원": "tax_tribunal",
            "국세청": "nts_authority",
            "국세청_판례": "nts_precedent",
            "기획재정부": "moef",
            "행정안전부": "mois",
            "감사원": "bai"
        }
        return site_key_mapping.get(site_name, site_name)