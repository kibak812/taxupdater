#!/bin/bash

# ngrok 설정 스크립트

echo "ngrok 터널링 설정을 시작합니다..."

# ngrok이 설치되어 있는지 확인
if ! command -v ngrok &> /dev/null; then
    echo "ngrok이 설치되지 않았습니다. 설치를 진행합니다..."
    
    # ngrok 다운로드 및 설치
    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
    sudo apt update
    sudo apt install ngrok -y
else
    echo "ngrok이 이미 설치되어 있습니다."
fi

# systemd 서비스 파일 생성
cat > ~/.config/systemd/user/ngrok.service << 'EOF'
[Unit]
Description=ngrok 터널 서비스
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/ngrok http 8001 --log=stdout
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

# systemd 사용자 서비스 활성화
systemctl --user daemon-reload
systemctl --user enable ngrok
systemctl --user start ngrok

echo "ngrok 서비스가 시작되었습니다."
echo ""
echo "ngrok 터널 URL을 확인하려면:"
echo "curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'"
echo ""
echo "서비스 상태 확인:"
echo "systemctl --user status ngrok"