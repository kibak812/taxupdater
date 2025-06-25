#!/usr/bin/env python3
"""
기능 유지 확인을 위한 테스트 스크립트

의존성 없이 실행 가능한 구조 테스트와 설정 검증
"""

import sys
import os
import importlib.util

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """모듈 import 테스트"""
    print("=== 모듈 Import 테스트 ===")
    
    tests = [
        ("설정 모듈", "src.config.settings"),
        ("인터페이스", "src.interfaces.crawler_interface"),
        ("기본 크롤러", "src.crawlers.base_crawler"),
        ("Excel 저장소", "src.repositories.excel_repository"),
        ("크롤링 서비스", "src.services.crawler_service"),
    ]
    
    results = []
    for name, module_path in tests:
        try:
            module = importlib.import_module(module_path)
            print(f"✅ {name}: 성공")
            results.append((name, True, ""))
        except Exception as e:
            print(f"❌ {name}: 실패 - {e}")
            results.append((name, False, str(e)))
    
    return results

def test_configuration():
    """설정 파일 테스트"""
    print("\n=== 설정 검증 테스트 ===")
    
    try:
        from src.config.settings import (
            BASE_URL, URLS, SECTIONS, CRAWLING_CONFIG, 
            DATA_COLUMNS, KEY_COLUMNS, GUI_CONFIG
        )
        
        # 기본 설정 검증
        assert BASE_URL == "https://www.tt.go.kr", "BASE_URL 설정 오류"
        assert len(SECTIONS) == 7, "SECTIONS 개수 오류"
        assert len(URLS) == 6, "URLS 개수 오류"
        assert len(DATA_COLUMNS) == 6, "DATA_COLUMNS 개수 오류"
        assert len(KEY_COLUMNS) == 6, "KEY_COLUMNS 개수 오류"
        
        print("✅ 모든 설정이 올바르게 로드됨")
        print(f"   - 크롤링 대상 사이트: {len(URLS)}개")
        print(f"   - 심판원 세목: {len(SECTIONS)}개")
        print(f"   - GUI 옵션: {len(GUI_CONFIG['site_options'])}개")
        
        return True
    except Exception as e:
        print(f"❌ 설정 검증 실패: {e}")
        return False

def test_data_structure():
    """데이터 구조 일관성 테스트"""
    print("\n=== 데이터 구조 일관성 테스트 ===")
    
    try:
        from src.config.settings import DATA_COLUMNS, KEY_COLUMNS
        
        # 각 사이트의 키 컬럼이 데이터 컬럼에 포함되어 있는지 확인
        for site_key, key_column in KEY_COLUMNS.items():
            if site_key in DATA_COLUMNS:
                columns = DATA_COLUMNS[site_key]
                assert key_column in columns, f"{site_key}의 키 컬럼 '{key_column}'이 데이터 컬럼에 없음"
                print(f"✅ {site_key}: 키 컬럼 '{key_column}' 검증 완료")
            else:
                print(f"⚠️  {site_key}: 데이터 컬럼 정의 없음")
        
        return True
    except Exception as e:
        print(f"❌ 데이터 구조 검증 실패: {e}")
        return False

def test_interface_compatibility():
    """인터페이스 호환성 테스트"""
    print("\n=== 인터페이스 호환성 테스트 ===")
    
    try:
        from src.interfaces.crawler_interface import CrawlerInterface, DataRepositoryInterface
        from src.crawlers.base_crawler import BaseCrawler
        from src.repositories.excel_repository import ExcelRepository
        
        # 인터페이스 구현 검증
        assert issubclass(BaseCrawler, CrawlerInterface), "BaseCrawler가 CrawlerInterface를 구현하지 않음"
        assert issubclass(ExcelRepository, DataRepositoryInterface), "ExcelRepository가 DataRepositoryInterface를 구현하지 않음"
        
        print("✅ 모든 인터페이스가 올바르게 구현됨")
        return True
    except Exception as e:
        print(f"❌ 인터페이스 호환성 검증 실패: {e}")
        return False

def test_legacy_compatibility():
    """레거시 호환성 테스트"""
    print("\n=== 레거시 호환성 테스트 ===")
    
    try:
        # example.py의 주요 함수들이 여전히 존재하는지 확인
        from example import (
            safe_request, load_existing_data, compare_data, 
            crawl_dynamic_site, crawl_nts_precedents
        )
        
        print("✅ 레거시 함수들이 여전히 사용 가능")
        
        # execute_crawling 함수 존재 확인
        from example import execute_crawling
        print("✅ 공통 크롤링 함수 사용 가능")
        
        return True
    except Exception as e:
        print(f"❌ 레거시 호환성 검증 실패: {e}")
        return False

def test_file_structure():
    """파일 구조 테스트"""
    print("\n=== 파일 구조 테스트 ===")
    
    required_files = [
        "src/config/settings.py",
        "src/interfaces/crawler_interface.py",
        "src/crawlers/base_crawler.py",
        "src/crawlers/tax_tribunal_crawler.py",
        "src/crawlers/nts_authority_crawler.py",
        "src/repositories/excel_repository.py",
        "src/services/crawler_service.py",
        "src/gui/main_window.py",
        "main.py",
        "example.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - 파일 없음")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  누락된 파일: {len(missing_files)}개")
        return False
    else:
        print(f"\n✅ 모든 필수 파일 존재 ({len(required_files)}개)")
        return True

def main():
    """메인 테스트 실행"""
    print("🔍 Tax Law Crawler 기능 유지 확인 테스트")
    print("=" * 50)
    
    test_results = []
    
    # 각 테스트 실행
    tests = [
        ("파일 구조", test_file_structure),
        ("모듈 Import", test_imports),
        ("설정 검증", test_configuration),
        ("데이터 구조", test_data_structure),
        ("인터페이스 호환성", test_interface_compatibility),
        ("레거시 호환성", test_legacy_compatibility)
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 예외 발생: {e}")
            test_results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name}: {status}")
    
    print(f"\n총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {total - passed}개")
    print(f"성공률: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과! 기능이 잘 유지되고 있습니다.")
        return True
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패. 문제를 확인해 주세요.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)