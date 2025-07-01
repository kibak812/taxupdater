import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys
import json

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import DataRepositoryInterface
from src.config.settings import FILE_CONFIG, DATA_COLUMNS, KEY_COLUMNS
from src.config.logging_config import get_logger


class SQLiteRepository(DataRepositoryInterface):
    """
    SQLite 기반 데이터 저장소
    
    고성능 데이터 처리 및 새로운 데이터 탐지 최적화를 위한
    SQLite 기반 Repository 구현
    """
    
    def __init__(self, db_path: str = "data/tax_data.db"):
        self.db_path = db_path
        self.backup_folder = "data/backups"
        self.logger = get_logger(__name__)
        
        # 데이터 폴더 생성
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
        
        # 데이터베이스 초기화
        try:
            self._initialize_database()
            self.logger.info(f"SQLite 저장소 초기화 완료: {self.db_path}")
        except Exception as e:
            self.logger.error(f"SQLite 저장소 초기화 실패: {e}")
            raise
    
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
                self.logger.info(f"SQLite 데이터베이스 초기화 완료: {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
    
    def _create_site_table(self, cursor: sqlite3.Cursor, site_key: str, columns: List[str]):
        """사이트별 테이블 생성 및 스키마 업데이트"""
        table_name = f"{site_key}_data"
        key_column = KEY_COLUMNS.get(site_key, "문서번호")
        
        # 기존 테이블 확인
        cursor.execute(f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='{table_name}'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # 새 테이블 생성
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
                CREATE TABLE [{table_name}] (
                    {', '.join(column_definitions)}
                )
            """
            cursor.execute(create_sql)
            self.logger.info(f"새 테이블 생성: {table_name}")
        else:
            # 기존 테이블 스키마 업데이트
            self._update_table_schema(cursor, table_name, columns)
            self.logger.info(f"기존 테이블 스키마 업데이트: {table_name}")
        
        # 인덱스 생성 (컬럼 존재 확인 후)
        self._create_indexes_safely(cursor, table_name)
        
        # 메타데이터 테이블에 정보 저장
        cursor.execute("""
            INSERT OR REPLACE INTO crawl_metadata (site_key, table_name, total_records)
            VALUES (?, ?, 0)
        """, (site_key, table_name))
        
        self.logger.info(f"테이블 생성/확인 완료: {table_name} ({len(columns)}개 컬럼)")
    
    def _update_table_schema(self, cursor: sqlite3.Cursor, table_name: str, columns: List[str]):
        """기존 테이블 스키마 업데이트 (필요한 컬럼 추가)"""
        try:
            # 기존 컬럼 목록 확인
            cursor.execute(f"PRAGMA table_info([{table_name}])")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # 필요한 메타데이터 컬럼 추가
            required_meta_columns = ['created_at', 'updated_at']
            
            for meta_col in required_meta_columns:
                if meta_col not in existing_columns:
                    try:
                        # SQLite 제약사항 회피: NULL 기본값으로 컬럼 추가 후 UPDATE
                        alter_sql = f"ALTER TABLE [{table_name}] ADD COLUMN {meta_col} TIMESTAMP"
                        cursor.execute(alter_sql)
                        
                        # 기존 레코드에 현재 시간 설정
                        update_sql = f"UPDATE [{table_name}] SET {meta_col} = CURRENT_TIMESTAMP WHERE {meta_col} IS NULL"
                        cursor.execute(update_sql)
                        
                        self.logger.info(f"  컬럼 추가 성공: {meta_col}")
                    except sqlite3.Error as e:
                        self.logger.warning(f"  컬럼 추가 실패 ({meta_col}): {e}")
            
            # 데이터 컬럼들도 확인하여 누락된 것이 있으면 추가
            for col in columns:
                if col not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE [{table_name}] ADD COLUMN [{col}] TEXT"
                        cursor.execute(alter_sql)
                        self.logger.info(f"  데이터 컬럼 추가: {col}")
                    except sqlite3.Error as e:
                        self.logger.warning(f"  데이터 컬럼 추가 실패 ({col}): {e}")
                        
        except Exception as e:
            self.logger.error(f"스키마 업데이트 오류 ({table_name}): {e}")
    
    def _create_indexes_safely(self, cursor: sqlite3.Cursor, table_name: str):
        """컬럼 존재 확인 후 안전한 인덱스 생성"""
        try:
            # 컬럼 존재 확인
            cursor.execute(f"PRAGMA table_info([{table_name}])")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # created_at 컬럼이 있는 경우에만 인덱스 생성
            if 'created_at' in existing_columns:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON [{table_name}] (created_at DESC)")
                self.logger.info(f"  인덱스 생성: idx_{table_name}_created_at")
            else:
                self.logger.info(f"  created_at 컬럼 없음, 인덱스 생성 건너뜀")
                
        except Exception as e:
            self.logger.error(f"인덱스 생성 오류 ({table_name}): {e}")
    
    def load_existing_data(self, site_key: str, include_metadata: bool = False) -> pd.DataFrame:
        """기존 데이터 로드"""
        try:
            table_name = f"{site_key}_data"
            
            with sqlite3.connect(self.db_path) as conn:
                # 컬럼 존재 확인
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info([{table_name}])")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # created_at 컬럼이 있으면 정렬, 없으면 기본 정렬
                if 'created_at' in existing_columns:
                    query = f"SELECT * FROM [{table_name}] ORDER BY created_at DESC"
                else:
                    # 키 컬럼으로 정렬 (대안)
                    key_column = KEY_COLUMNS.get(site_key, "문서번호")
                    if key_column in existing_columns:
                        query = f"SELECT * FROM [{table_name}] ORDER BY [{key_column}] DESC"
                    else:
                        query = f"SELECT * FROM [{table_name}]"
                
                df = pd.read_sql_query(query, conn)
                
                # 메타데이터 컬럼 제거 (선택적)
                if not include_metadata:
                    meta_columns = ['created_at', 'updated_at']
                    df = df.drop(columns=[col for col in meta_columns if col in df.columns])
                
                self.logger.info(f"[SQLite] {site_key} 기존 데이터 로드: {len(df)}개")
                return df
                
        except Exception as e:
            self.logger.error(f"데이터 로드 실패 ({site_key}): {e}")
            return self._create_empty_dataframe(site_key)
    
    def load_filtered_data(self, site_key: str, recent_days: int = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """필터링된 데이터 로드 (시간 기반)"""
        try:
            table_name = f"{site_key}_data"
            
            with sqlite3.connect(self.db_path) as conn:
                # 컬럼 존재 확인
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info([{table_name}])")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # 기본 쿼리
                base_query = f"SELECT * FROM [{table_name}]"
                where_conditions = []
                
                # 시간 필터 적용
                if 'created_at' in existing_columns or 'updated_at' in existing_columns:
                    time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
                    
                    if recent_days:
                        # 최근 N일 필터
                        where_conditions.append(f"{time_column} >= datetime('now', '-{recent_days} days')")
                    elif start_date and end_date:
                        # 날짜 범위 필터
                        where_conditions.append(f"{time_column} >= '{start_date}'")
                        where_conditions.append(f"{time_column} <= '{end_date} 23:59:59'")
                else:
                    self.logger.warning(f"[SQLite] {site_key}: 시간 컬럼이 없어 전체 데이터 반환")
                
                # WHERE 절 구성
                if where_conditions:
                    query = base_query + " WHERE " + " AND ".join(where_conditions)
                else:
                    query = base_query
                
                # 정렬 추가
                if 'created_at' in existing_columns:
                    query += " ORDER BY created_at DESC"
                elif 'updated_at' in existing_columns:
                    query += " ORDER BY updated_at DESC"
                
                df = pd.read_sql_query(query, conn)
                
                # 메타데이터 포함 (필터링된 데이터는 항상 메타데이터 포함)
                self.logger.info(f"[SQLite] {site_key} 필터링된 데이터 로드: {len(df)}개")
                
                return df
                
        except Exception as e:
            self.logger.error(f"필터링된 데이터 로드 실패 ({site_key}): {e}")
            return self._create_empty_dataframe(site_key)
    
    def save_data(self, site_key: str, data: pd.DataFrame, is_incremental: bool = True) -> bool:
        """데이터 저장 (UNIQUE constraint 에러 방지)"""
        try:
            if data.empty:
                self.logger.info(f"[SQLite] {site_key}: 저장할 데이터가 없음")
                return True
            
            table_name = f"{site_key}_data"
            key_column = KEY_COLUMNS.get(site_key, "문서번호")
            
            with sqlite3.connect(self.db_path) as conn:
                if is_incremental:
                    # 증분 저장: 새로운 데이터만 INSERT
                    new_entries = self.compare_and_get_new_entries(site_key, data, key_column)
                    
                    if not new_entries.empty:
                        # INSERT OR IGNORE 방식으로 중복 키 에러 방지
                        try:
                            new_entries.to_sql(table_name, conn, if_exists='append', index=False, method='multi')
                        except sqlite3.IntegrityError as ie:
                            self.logger.warning(f"[SQLite] {site_key}: UNIQUE constraint 에러 발생, INSERT OR IGNORE 방식 사용")
                            # 개별 행씩 INSERT OR IGNORE 처리
                            self._insert_with_ignore(conn, table_name, new_entries, key_column)
                        
                        # 메타데이터 업데이트
                        self._update_metadata(conn, site_key, len(new_entries))
                        
                        self.logger.info(f"[SQLite] {site_key}: {len(new_entries)}개 신규 항목 저장 완료")
                    else:
                        self.logger.info(f"[SQLite] {site_key}: 새로운 데이터 없음")
                else:
                    # 전체 교체
                    data.to_sql(table_name, conn, if_exists='replace', index=False, method='multi')
                    self._update_metadata(conn, site_key, len(data), replace=True)
                    self.logger.info(f"[SQLite] {site_key}: {len(data)}개 항목 전체 저장 완료")
                
                return True
                
        except Exception as e:
            self.logger.error(f"데이터 저장 실패 ({site_key}): {e}")
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
                
                self.logger.info(f"[SQLite] {site_key} 데이터 비교:")
                self.logger.info(f"  새 데이터: {len(new_data)}개")
                self.logger.info(f"  신규 항목: {len(new_entries)}개")
                
                return new_entries
                
        except Exception as e:
            self.logger.error(f"신규 데이터 추출 실패 ({site_key}): {e}")
            # 폴백: pandas 방식
            existing_data = self.load_existing_data(site_key)
            if existing_data.empty:
                return new_data
            
            new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
            self.logger.info(f"[Fallback] {site_key}: {len(new_entries)}개 신규 항목")
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
            
            self.logger.info(f"[SQLite] 백업 완료: {backup_file}")
            return backup_file
            
        except Exception as e:
            self.logger.error(f"백업 실패 ({site_key}): {e}")
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
                
                # 최신/오래된 데이터 조회 (created_at 컬럼이 있는 경우에만)
                if total_count > 0:
                    # 컬럼 존재 확인
                    cursor.execute(f"PRAGMA table_info([{table_name}])")
                    existing_columns = {row[1] for row in cursor.fetchall()}
                    
                    if 'created_at' in existing_columns:
                        cursor.execute(f"""
                            SELECT MIN(created_at), MAX(created_at) 
                            FROM [{table_name}]
                        """)
                        earliest, latest = cursor.fetchone()
                        stats["data_range"] = {
                            "earliest": earliest,
                            "latest": latest
                        }
                    else:
                        stats["data_range"] = {
                            "earliest": None,
                            "latest": None,
                            "note": "created_at 컬럼 없음"
                        }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"통계 정보 조회 실패 ({site_key}): {e}")
            return {"total_count": 0, "last_updated": None, "error": str(e)}
    
    def _insert_with_ignore(self, conn: sqlite3.Connection, table_name: str, data: pd.DataFrame, key_column: str):
        """INSERT OR IGNORE 방식으로 중복 키 에러 방지하며 데이터 삽입"""
        try:
            cursor = conn.cursor()
            columns = list(data.columns)
            
            # 플레이스홀더 생성
            placeholders = ', '.join(['?'] * len(columns))
            column_names = ', '.join([f'[{col}]' for col in columns])
            
            insert_sql = f"""
                INSERT OR IGNORE INTO [{table_name}] ({column_names})
                VALUES ({placeholders})
            """
            
            # 데이터 삽입
            success_count = 0
            for _, row in data.iterrows():
                try:
                    cursor.execute(insert_sql, tuple(row[col] for col in columns))
                    if cursor.rowcount > 0:
                        success_count += 1
                except Exception as e:
                    self.logger.warning(f"  행 삽입 실패: {e}")
            
            conn.commit()
            self.logger.info(f"[SQLite] INSERT OR IGNORE: {success_count}/{len(data)}개 행 성공적으로 삽입")
            
        except Exception as e:
            self.logger.error(f"INSERT OR IGNORE 실패: {e}")
            raise

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
    
    def get_recent_data_counts(self, hours: int = 24) -> Dict[str, int]:
        """각 사이트별 최근 데이터 개수 조회"""
        try:
            counts = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 각 사이트별로 최근 데이터 개수 조회
                for site_key in DATA_COLUMNS.keys():
                    table_name = f"{site_key}_data"
                    
                    # 테이블 존재 확인
                    cursor.execute(f"""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='{table_name}'
                    """)
                    
                    if not cursor.fetchone():
                        counts[site_key] = 0
                        continue
                    
                    # 컬럼 존재 확인
                    cursor.execute(f"PRAGMA table_info([{table_name}])")
                    existing_columns = {row[1] for row in cursor.fetchall()}
                    
                    # 시간 컬럼이 있는 경우만 필터링
                    if 'created_at' in existing_columns or 'updated_at' in existing_columns:
                        time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
                        
                        # 최근 N시간 데이터 개수 조회
                        query = f"""
                            SELECT COUNT(*) FROM [{table_name}]
                            WHERE {time_column} >= datetime('now', '-{hours} hours')
                        """
                        
                        cursor.execute(query)
                        count = cursor.fetchone()[0]
                        counts[site_key] = count
                    else:
                        # 시간 컬럼이 없으면 0으로 처리
                        counts[site_key] = 0
                        self.logger.warning(f"[SQLite] {site_key}: 시간 컬럼이 없어 최근 데이터 조회 불가")
            
            self.logger.info(f"[SQLite] 최근 {hours}시간 데이터 개수 조회 완료: {counts}")
            return counts
                
        except Exception as e:
            self.logger.error(f"최근 데이터 개수 조회 실패: {e}")
            return {}
    
    def force_schema_update(self):
        """강제 스키마 업데이트 (수동 실행용)"""
        try:
            self.logger.info("강제 스키마 업데이트 시작...")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 각 사이트별 테이블 업데이트
                for site_key, columns in DATA_COLUMNS.items():
                    table_name = f"{site_key}_data"
                    self.logger.info(f"  {table_name} 스키마 업데이트 중...")
                    
                    # 테이블 존재 확인
                    cursor.execute(f"""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='{table_name}'
                    """)
                    
                    if cursor.fetchone():
                        self._update_table_schema(cursor, table_name, columns)
                        self._create_indexes_safely(cursor, table_name)
                    else:
                        self.logger.warning(f"    테이블 {table_name} 없음, 건너뜀")
                
                conn.commit()
            
            self.logger.info("강제 스키마 업데이트 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"강제 스키마 업데이트 실패: {e}")
            return False