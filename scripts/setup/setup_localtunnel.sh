#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 LocalTunnel 기반 자동 배포 설정${NC}"
echo ""

# 기존 ngrok 서비스 정리
echo -e "${YELLOW}기존 ngrok 서비스 정리 중...${NC}"
systemctl --user stop ngrok 2>/dev/null || true
systemctl --user disable ngrok 2>/dev/null || true

# localtunnel 설치 확인
if ! command -v lt &> /dev/null; then
    echo -e "${YELLOW}localtunnel 설치 중...${NC}"
    npm install -g localtunnel
else
    echo -e "${GREEN}✅ localtunnel이 이미 설치되어 있습니다.${NC}"
fi

# 현재 경로 확인
CURRENT_DIR=$(pwd)

# localtunnel 서비스 파일 수정
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" localtunnel.service

# systemd 사용자 디렉토리 생성
mkdir -p ~/.config/systemd/user/

# 서비스 파일 복사
cp localtunnel.service ~/.config/systemd/user/

# systemd 리로드
systemctl --user daemon-reload

echo -e "${GREEN}✅ LocalTunnel 서비스 설정 완료!${NC}"
echo ""

# 서비스 시작
echo -e "${YELLOW}서비스 시작 중...${NC}"
systemctl --user start taxupdater localtunnel

# 자동 시작 설정
echo -e "${YELLOW}부팅 시 자동 시작 설정 중...${NC}"
systemctl --user enable taxupdater localtunnel

echo ""
echo -e "${GREEN}🎉 설정 완료!${NC}"
echo ""
echo -e "${BLUE}📍 고정 접속 URL:${NC}"
echo -e "   ${GREEN}https://taxupdater-monitor.loca.lt${NC}"
echo ""
echo -e "${YELLOW}💡 주요 장점:${NC}"
echo "   ✅ URL이 절대 변경되지 않음"
echo "   ✅ 재부팅 후 자동으로 동일한 URL로 복구"
echo "   ✅ 복잡한 URL 관리 불필요"
echo "   ✅ 북마크 저장 가능"
echo ""
echo -e "${YELLOW}🛠️  관리 명령어:${NC}"
echo "   systemctl --user status taxupdater localtunnel    # 상태 확인"
echo "   systemctl --user restart taxupdater localtunnel   # 재시작"
echo "   systemctl --user stop taxupdater localtunnel      # 중지"
echo "   journalctl --user -u localtunnel -f               # 실시간 로그"
echo ""
echo -e "${GREEN}🌐 지금 바로 접속해보세요: https://taxupdater-monitor.loca.lt${NC}"