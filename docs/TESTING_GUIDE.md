# 기능 유지 확인 가이드

## 🔍 테스트 실행 방법

### 1. 구조적 테스트 (의존성 없이 실행 가능)

```bash
# 기본 구조 및 설정 테스트
python3 test_functionality.py

# 기능 동등성 테스트  
python3 functional_comparison.py
```

### 2. 실제 기능 테스트 (의존성 설치 후)

```bash
# 의존성 설치
pip install -r requirements.txt

# 레거시 방식 테스트
python3 example.py

# 새로운 방식 테스트
python3 main.py
```

## ✅ 확인해야 할 핵심 기능

### A. 사용자 인터페이스
- [ ] GUI 창이 정상적으로 열리는가?
- [ ] 7개 선택 옵션이 모두 표시되는가?
- [ ] 진행률 바가 동작하는가?
- [ ] 상태 메시지가 업데이트되는가?

### B. 크롤링 기능
- [ ] 조세심판원 크롤링이 동작하는가?
- [ ] 국세청 유권해석 크롤링이 동작하는가?
- [ ] 기타 사이트들이 정상 동작하는가?
- [ ] "모두 크롤링" 기능이 동작하는가?

### C. 데이터 처리
- [ ] Excel 파일이 올바른 위치에 생성되는가?
- [ ] 데이터 구조가 기존과 동일한가?
- [ ] 중복 데이터가 제거되는가?
- [ ] 백업 파일이 생성되는가?

### D. 에러 처리
- [ ] 네트워크 오류 시 재시도하는가?
- [ ] 타임아웃 발생 시 적절히 처리하는가?
- [ ] 빈 데이터 시 적절한 메시지를 표시하는가?

## 🔧 문제 해결 방법

### 의존성 문제
```bash
# Chrome 드라이버 설치
# Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# 또는 수동 설치
wget https://chromedriver.chromium.org/downloads
```

### Python 모듈 문제
```bash
# 가상환경 사용 권장
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 데이터 비교 방법
```bash
# 기존 데이터와 새 데이터 비교
diff -r data_old/ data/

# 특정 파일의 행 수 비교
wc -l data/existing_data_심판원.xlsx
```

## 📊 성능 비교 방법

### 1. 크롤링 속도 측정
```python
import time

start_time = time.time()
# 크롤링 실행
end_time = time.time()

print(f"실행 시간: {end_time - start_time:.2f}초")
```

### 2. 메모리 사용량 측정
```python
import psutil
import os

process = psutil.Process(os.getpid())
memory_usage = process.memory_info().rss / 1024 / 1024  # MB
print(f"메모리 사용량: {memory_usage:.2f}MB")
```

### 3. 데이터 품질 검증
```python
import pandas as pd

# 데이터 로드
df = pd.read_excel('data/existing_data_심판원.xlsx')

# 기본 통계
print(f"총 행 수: {len(df)}")
print(f"중복 행 수: {df.duplicated().sum()}")
print(f"빈 값 개수: {df.isnull().sum().sum()}")
print(f"데이터 타입:\n{df.dtypes}")
```

## 🎯 회귀 테스트 체크리스트

### 기능 동등성
- [x] 모든 사이트 매핑 일치
- [x] 설정 값 동등성
- [x] 워크플로우 동등성  
- [x] 에러 처리 개선

### 추가 개선사항
- [x] 코드 모듈화 (12개 모듈)
- [x] 에러 처리 표준화
- [x] 데이터 유효성 검증 강화
- [x] 재시도 로직 통합
- [x] 백업 기능 자동화
- [x] DB 전환 준비 완료
- [x] 웹 인터페이스 전환 준비 완료

## 🚀 다음 단계 검증

### SQLite 전환 테스트 (예정)
```python
# Repository 교체만으로 전환 가능
from src.repositories.sqlite_repository import SQLiteRepository

repository = SQLiteRepository()  # Excel → SQLite
# 나머지 코드는 동일
```

### 웹 인터페이스 전환 테스트 (예정)
```python
# GUI 교체만으로 전환 가능
from src.gui.web_interface import WebInterface

app = WebInterface(crawling_service)  # tkinter → Web
# 크롤링 로직은 동일
```

## 📞 문제 신고

테스트 중 문제 발견 시:
1. 어떤 테스트에서 실패했는지
2. 에러 메시지 전문
3. 실행 환경 (OS, Python 버전)
4. 재현 단계