import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import sys
import json

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import DataRepositoryInterface
from src.config.settings import FILE_CONFIG, DATA_COLUMNS, KEY_COLUMNS


class SQLiteRepository(DataRepositoryInterface):
    """
    SQLite 기반 데이터 저장소
    
    고성능 데이터 처리 및 새로운 데이터 탐지 최적화를 위한
    SQLite 기반 Repository 구현
    """
    
    def __init__(self, db_path: str = "data/tax_data.db"):
        self.db_path = db_path
        self.backup_folder = "data/backups"
        
        # 데이터 폴더 생성
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
        
        # 데이터베이스 초기화
        self._initialize_database()
    
    def _initialize_database(self):
        """데이터베이스 및 테이블 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 메타데이터 테이블 생성
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crawl_metadata (
                        site_key TEXT PRIMARY KEY,
                        last_crawl TIMESTAMP,
                        total_records INTEGER DEFAULT 0,
                        last_backup_path TEXT,
                        table_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 각 사이트별 테이블 생성
                for site_key, columns in DATA_COLUMNS.items():
                    self._create_site_table(cursor, site_key, columns)
                
                conn.commit()
                print(f"SQLite 데이터베이스 초기화 완료: {self.db_path}")
                
        except Exception as e:
            print(f"데이터베이스 초기화 실패: {e}")
            raise
    
    def _create_site_table(self, cursor: sqlite3.Cursor, site_key: str, columns: List[str]):
        """사이트별 테이블 생성"""
        table_name = f"{site_key}_data"
        key_column = KEY_COLUMNS.get(site_key, "문서번호")
        
        # 컬럼 정의 생성
        column_definitions = []
        for col in columns:
            if col == key_column:
                column_definitions.append(f"[{col}] TEXT PRIMARY KEY")
            else:
                column_definitions.append(f"[{col}] TEXT")
        
        # 추가 메타데이터 컬럼
        column_definitions.extend([
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ])
        
        create_sql = f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                {', '.join(column_definitions)}
            )
        """
        
        cursor.execute(create_sql)
        
        # 인덱스 생성 (성능 최적화)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON [{table_name}] (created_at DESC)")
        
        # 메타데이터 테이블에 정보 저장
        cursor.execute("""
            INSERT OR REPLACE INTO crawl_metadata (site_key, table_name, total_records)
            VALUES (?, ?, 0)
        """, (site_key, table_name))
        
        print(f"테이블 생성/확인 완료: {table_name} ({len(columns)}개 컬럼)")
    
    def load_existing_data(self, site_key: str) -> pd.DataFrame:
        """기존 데이터 로드"""
        try:
            table_name = f"{site_key}_data"
            query = f"SELECT * FROM [{table_name}] ORDER BY created_at DESC"
            
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn)
                
                # 메타데이터 컬럼 제거
                meta_columns = ['created_at', 'updated_at']
                df = df.drop(columns=[col for col in meta_columns if col in df.columns])
                
                print(f"[SQLite] {site_key} 기존 데이터 로드: {len(df)}개")
                return df
                
        except Exception as e:
            print(f"데이터 로드 실패 ({site_key}): {e}")
            return self._create_empty_dataframe(site_key)
    
    def save_data(self, site_key: str, data: pd.DataFrame, is_incremental: bool = True) -> bool:
        """데이터 저장"""
        try:
            if data.empty:
                print(f"[SQLite] {site_key}: 저장할 데이터가 없음")
                return True
            
            table_name = f"{site_key}_data"
            key_column = KEY_COLUMNS.get(site_key, "문서번호")
            
            with sqlite3.connect(self.db_path) as conn:
                if is_incremental:
                    # 증분 저장: 새로운 데이터만 INSERT
                    new_entries = self.compare_and_get_new_entries(site_key, data, key_column)
                    
                    if not new_entries.empty:
                        # 새 데이터만 삽입
                        new_entries.to_sql(table_name, conn, if_exists='append', index=False, method='multi')
                        
                        # 메타데이터 업데이트
                        self._update_metadata(conn, site_key, len(new_entries))
                        
                        print(f"[SQLite] {site_key}: {len(new_entries)}개 신규 항목 저장 완료")
                    else:
                        print(f"[SQLite] {site_key}: 새로운 데이터 없음")
                else:
                    # 전체 교체
                    data.to_sql(table_name, conn, if_exists='replace', index=False, method='multi')
                    self._update_metadata(conn, site_key, len(data), replace=True)
                    print(f"[SQLite] {site_key}: {len(data)}개 항목 전체 저장 완료")
                
                return True
                
        except Exception as e:
            print(f"데이터 저장 실패 ({site_key}): {e}")
            return False
    
    def compare_and_get_new_entries(self, site_key: str, new_data: pd.DataFrame, key_column: str) -> pd.DataFrame:
        """신규 데이터 추출 (SQL 최적화)"""
        try:
            if new_data.empty:
                return new_data
            
            table_name = f"{site_key}_data"
            
            # 새 데이터를 임시 테이블로 생성
            temp_table = f"temp_{site_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            with sqlite3.connect(self.db_path) as conn:
                # 임시 테이블에 새 데이터 저장
                new_data.to_sql(temp_table, conn, if_exists='replace', index=False)
                
                # SQL JOIN을 사용한 고성능 신규 데이터 추출
                query = f"""
                    SELECT temp.*
                    FROM [{temp_table}] temp
                    LEFT JOIN [{table_name}] existing 
                    ON temp.[{key_column}] = existing.[{key_column}]
                    WHERE existing.[{key_column}] IS NULL
                """
                
                new_entries = pd.read_sql_query(query, conn)
                
                # 임시 테이블 삭제
                conn.execute(f"DROP TABLE IF EXISTS [{temp_table}]")
                
                print(f"[SQLite] {site_key} 데이터 비교:")
                print(f"  새 데이터: {len(new_data)}개")
                print(f"  신규 항목: {len(new_entries)}개")
                
                return new_entries
                
        except Exception as e:
            print(f"신규 데이터 추출 실패 ({site_key}): {e}")
            # 폴백: pandas 방식
            existing_data = self.load_existing_data(site_key)
            if existing_data.empty:
                return new_data
            
            new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
            print(f"[Fallback] {site_key}: {len(new_entries)}개 신규 항목")
            return new_entries
    
    def backup_data(self, site_key: str, data: pd.DataFrame) -> str:
        """데이터 백업"""
        try:
            if data.empty:
                return ""
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.backup_folder, f"{site_key}_backup_{timestamp}.xlsx")
            
            data.to_excel(backup_file, index=False)
            
            # 메타데이터에 백업 경로 저장
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE crawl_metadata 
                    SET last_backup_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE site_key = ?
                """, (backup_file, site_key))
            
            print(f"[SQLite] 백업 완료: {backup_file}")
            return backup_file
            
        except Exception as e:
            print(f"백업 실패 ({site_key}): {e}")
            return ""
    
    def get_statistics(self, site_key: str) -> Dict[str, Any]:
        """데이터 통계 정보 반환"""
        try:
            table_name = f"{site_key}_data"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 기본 통계
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                total_count = cursor.fetchone()[0]
                
                # 메타데이터 조회
                cursor.execute("""
                    SELECT last_crawl, last_backup_path, created_at, updated_at
                    FROM crawl_metadata WHERE site_key = ?
                """, (site_key,))
                
                meta_result = cursor.fetchone()
                
                stats = {
                    "total_count": total_count,
                    "last_updated": meta_result[3] if meta_result else None,
                    "last_crawl": meta_result[0] if meta_result else None,
                    "last_backup": meta_result[1] if meta_result else None,
                    "database_size_mb": round(os.path.getsize(self.db_path) / 1024 / 1024, 2)
                }
                
                # 최신/오래된 데이터 조회
                if total_count > 0:
                    cursor.execute(f"""
                        SELECT MIN(created_at), MAX(created_at) 
                        FROM [{table_name}]
                    """)
                    earliest, latest = cursor.fetchone()
                    stats["data_range"] = {
                        "earliest": earliest,
                        "latest": latest
                    }
                
                return stats
                
        except Exception as e:
            print(f"통계 정보 조회 실패 ({site_key}): {e}")
            return {"total_count": 0, "last_updated": None, "error": str(e)}
    
    def _update_metadata(self, conn: sqlite3.Connection, site_key: str, added_count: int, replace: bool = False):
        """메타데이터 업데이트"""
        if replace:
            conn.execute("""
                UPDATE crawl_metadata 
                SET total_records = ?, last_crawl = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE site_key = ?
            """, (added_count, site_key))
        else:
            conn.execute("""
                UPDATE crawl_metadata 
                SET total_records = total_records + ?, last_crawl = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE site_key = ?
            """, (added_count, site_key))
    
    def _create_empty_dataframe(self, site_key: str) -> pd.DataFrame:
        """빈 데이터프레임 생성"""
        columns = DATA_COLUMNS.get(site_key, [])
        return pd.DataFrame(columns=columns)
    
    def get_database_info(self) -> Dict[str, Any]:
        """데이터베이스 전체 정보 반환"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 테이블 목록
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # 각 테이블별 레코드 수
                table_stats = {}
                for table in tables:
                    if table != 'crawl_metadata':
                        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                        count = cursor.fetchone()[0]
                        table_stats[table] = count
                
                return {
                    "database_path": self.db_path,
                    "database_size_mb": round(os.path.getsize(self.db_path) / 1024 / 1024, 2),
                    "tables": table_stats,
                    "total_records": sum(table_stats.values())
                }
                
        except Exception as e:
            return {"error": str(e)}