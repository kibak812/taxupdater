#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 LocalTunnel Keep-Alive 설정${NC}"
echo ""

# 기존 localtunnel 서비스 중지
echo -e "${YELLOW}기존 서비스 중지 중...${NC}"
systemctl --user stop localtunnel 2>/dev/null || true
systemctl --user disable localtunnel 2>/dev/null || true

# localtunnel 설치 확인
if ! command -v lt &> /dev/null; then
    echo -e "${YELLOW}localtunnel 설치 중...${NC}"
    npm install -g localtunnel
else
    echo -e "${GREEN}✅ localtunnel이 이미 설치되어 있습니다.${NC}"
fi

# 현재 경로 확인
CURRENT_DIR=$(pwd)

# 새로운 서비스 파일 경로 수정
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" config/localtunnel-keepalive.service

# systemd 사용자 디렉토리 생성
mkdir -p ~/.config/systemd/user/

# 새로운 서비스 파일 복사
cp config/localtunnel-keepalive.service ~/.config/systemd/user/localtunnel.service

# systemd 리로드
systemctl --user daemon-reload

echo -e "${GREEN}✅ Keep-Alive 서비스 설정 완료!${NC}"
echo ""

# 서비스 시작
echo -e "${YELLOW}서비스 시작 중...${NC}"
systemctl --user restart taxupdater
systemctl --user restart localtunnel

# 자동 시작 설정
echo -e "${YELLOW}부팅 시 자동 시작 설정 중...${NC}"
systemctl --user enable taxupdater localtunnel

# 서비스 상태 확인
sleep 3
echo ""
echo -e "${BLUE}📊 서비스 상태:${NC}"
systemctl --user status localtunnel --no-pager

echo ""
echo -e "${GREEN}🎉 Keep-Alive 설정 완료!${NC}"
echo ""
echo -e "${BLUE}📍 고정 접속 URL:${NC}"
echo -e "   ${GREEN}https://taxupdater-monitor.loca.lt${NC}"
echo ""
echo -e "${YELLOW}💡 개선사항:${NC}"
echo "   ✅ 연결 끊김 시 자동 재연결"
echo "   ✅ 2초 간격으로 연결 상태 확인"
echo "   ✅ 무제한 재시작 정책"
echo "   ✅ 네트워크 대기 설정"
echo ""
echo -e "${YELLOW}🛠️  관리 명령어:${NC}"
echo "   systemctl --user status localtunnel       # 상태 확인"
echo "   systemctl --user restart localtunnel      # 재시작"
echo "   journalctl --user -u localtunnel -f      # 실시간 로그"
echo "   journalctl --user -u localtunnel --since '5 minutes ago'  # 최근 5분 로그"
echo ""
echo -e "${GREEN}🌐 안정적인 연결 유지: https://taxupdater-monitor.loca.lt${NC}"