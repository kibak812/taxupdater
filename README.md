# Tax Law Updater

세금 관련 법령 및 해석 자료를 자동으로 수집하는 크롤링 시스템

## 기능

- 조세심판원 심판례 수집
- 국세법령정보시스템 유권해석 수집
- 국세법령정보시스템 판례 수집
- 기획재정부 해석 사례 수집
- 행정안전부 유권해석 수집
- 감사원 심사결정례 수집
- 주기적 자동 크롤링

## 요구사항

- Python 3.7+
- Chrome/Chromium 브라우저
- ChromeDriver

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
python example.py
```

## 프로젝트 구조

현재 단일 파일 구조로 되어 있으며, 리팩토링을 통해 모듈화 예정입니다.