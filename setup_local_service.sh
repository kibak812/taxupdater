#!/bin/bash
# 로컬 PC 24/7 실행 설정

echo "예규판례 모니터링 시스템 로컬 서비스 설정..."

# 1. 서비스 파일 생성
sudo tee /etc/systemd/system/taxupdater.service > /dev/null <<EOF
[Unit]
Description=예규판례 모니터링 시스템
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
Environment="PATH=$PWD/taxupdater_venv/bin:$PATH"
ExecStart=$PWD/taxupdater_venv/bin/python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 2. 자동 시작 설정
sudo systemctl daemon-reload
sudo systemctl enable taxupdater.service
sudo systemctl start taxupdater.service

# 3. 방화벽 설정 (외부 접속 허용)
sudo ufw allow 8001/tcp

echo "설정 완료!"
echo "서비스 상태: sudo systemctl status taxupdater"
echo "외부 접속: http://$(hostname -I | cut -d' ' -f1):8001"