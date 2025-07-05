"""
백업 서비스 - GitHub Gist 또는 외부 저장소에 데이터 백업
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Any
import sqlite3
import pandas as pd
from pathlib import Path

class BackupService:
    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        self.gist_id = os.environ.get('BACKUP_GIST_ID')
        
    def backup_to_gist(self, db_path: str):
        """SQLite 데이터를 GitHub Gist에 JSON으로 백업"""
        if not self.github_token:
            print("GitHub token이 없어 백업을 건너뜁니다.")
            return
            
        conn = sqlite3.connect(db_path)
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn).name.tolist()
        
        backup_data = {}
        for table in tables:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            backup_data[table] = df.to_dict('records')
        
        conn.close()
        
        # Gist 업데이트
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        gist_data = {
            'description': f'Tax Updater Backup - {datetime.now().isoformat()}',
            'files': {
                'backup.json': {
                    'content': json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
                }
            }
        }
        
        if self.gist_id:
            # 기존 Gist 업데이트
            response = requests.patch(
                f'https://api.github.com/gists/{self.gist_id}',
                headers=headers,
                json=gist_data
            )
        else:
            # 새 Gist 생성
            response = requests.post(
                'https://api.github.com/gists',
                headers=headers,
                json=gist_data
            )
            
        if response.status_code in [200, 201]:
            print(f"백업 성공: {response.json()['html_url']}")
        else:
            print(f"백업 실패: {response.status_code}")
            
    def restore_from_gist(self, db_path: str):
        """GitHub Gist에서 데이터 복원"""
        if not self.gist_id:
            print("복원할 Gist ID가 없습니다.")
            return
            
        response = requests.get(f'https://api.github.com/gists/{self.gist_id}')
        if response.status_code != 200:
            print("Gist 로드 실패")
            return
            
        gist_data = response.json()
        backup_content = gist_data['files']['backup.json']['content']
        backup_data = json.loads(backup_content)
        
        conn = sqlite3.connect(db_path)
        
        for table_name, records in backup_data.items():
            if records:
                df = pd.DataFrame(records)
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                
        conn.close()
        print("복원 완료")