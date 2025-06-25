import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import sys
import os

# 상위 디렉토리의 config 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.config.settings import GUI_CONFIG


class MainWindow:
    def __init__(self, crawling_service):
        """
        메인 윈도우 클래스
        
        Args:
            crawling_service: 크롤링 서비스 인스턴스
        """
        self.crawling_service = crawling_service
        self.window = None
        self.site_choice = None
        self.progress = None
        self.status_message = None
        self.time_entry = None
        
    def create_window(self):
        """GUI 윈도우 생성"""
        self.window = tk.Tk()
        self.window.title(GUI_CONFIG["title"])
        
        # 사이트 선택 라벨
        label = tk.Label(self.window, text="사이트를 선택하세요:")
        label.pack(pady=10)
        
        # 사이트 선택 콤보박스
        self.site_choice = ttk.Combobox(self.window, values=GUI_CONFIG["site_options"])
        self.site_choice.pack(pady=10)
        
        # 크롤링 시작 버튼
        crawl_button = tk.Button(self.window, text="시작", command=self.on_crawl_click)
        crawl_button.pack(pady=20)
        
        # 상태 메시지
        self.status_message = tk.Label(self.window, text="진행 상태")
        self.status_message.pack(pady=5)
        
        # 진행 상태바
        self.progress = ttk.Progressbar(self.window, length=300, mode="determinate", maximum=100)
        self.progress.pack(pady=10)
        
        # 주기적인 크롤링을 위한 시간 입력 필드
        time_label = tk.Label(self.window, text="주기 (분):")
        time_label.pack(pady=5)
        self.time_entry = tk.Entry(self.window)
        self.time_entry.pack(pady=5)
        self.time_entry.insert(0, str(GUI_CONFIG["default_interval"]))
        
        # 주기적인 크롤링 시작 버튼
        periodic_button = tk.Button(self.window, text="자동 탐색 시작", command=self.start_periodic_crawl)
        periodic_button.pack(pady=20)
        
    def on_crawl_click(self):
        """크롤링 시작 버튼 클릭 이벤트"""
        choice = self.site_choice.get().split(".")[0].strip()
        self.progress['value'] = 0
        self.progress.update()
        
        # 크롤링 서비스 호출
        self.crawling_service.execute_crawling(choice, self.progress, self.status_message, is_periodic=False)
    
    def start_periodic_crawl(self):
        """주기적 크롤링 시작"""
        choice = self.site_choice.get().split(".")[0].strip()
        
        # 첫 번째 크롤링 실행
        self.crawling_service.execute_crawling(choice, self.progress, self.status_message, is_periodic=True)
        
        # 주기적 실행 스케줄링
        self.schedule_next_crawl()
    
    def schedule_next_crawl(self):
        """다음 크롤링 스케줄링"""
        interval_str = self.time_entry.get()
        if interval_str.isdigit():
            interval = int(interval_str) * 60000  # 분을 밀리초로 변환
        else:
            self.show_message("주기 입력 오류: 숫자를 입력해주세요. 기본값 60분으로 재시도합니다.")
            interval = GUI_CONFIG["default_interval"] * 60000
        
        # 다음 실행 스케줄링
        self.window.after(interval, self.periodic_crawl_callback)
    
    def periodic_crawl_callback(self):
        """주기적 크롤링 콜백"""
        choice = self.site_choice.get().split(".")[0].strip()
        self.crawling_service.execute_crawling(choice, self.progress, self.status_message, is_periodic=True)
        # 다음 실행 스케줄링
        self.schedule_next_crawl()
    
    def show_message(self, message):
        """메시지 박스 표시"""
        messagebox.showinfo("크롤링 완료", message)
    
    def run(self):
        """GUI 실행"""
        if self.window is None:
            self.create_window()
        self.window.mainloop()