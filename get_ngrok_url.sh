#!/bin/bash

# ngrok 터널 URL 조회 스크립트

echo "ngrok 터널 URL 조회 중..."

# ngrok이 실행 중인지 확인
if ! pgrep -x "ngrok" > /dev/null; then
    echo "ngrok이 실행되지 않았습니다."
    echo "다음 명령어로 ngrok을 시작하세요:"
    echo "systemctl --user start ngrok"
    exit 1
fi

# ngrok API에서 터널 정보 가져오기
if command -v jq &> /dev/null; then
    # jq가 있는 경우
    URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url // empty')
else
    # jq가 없는 경우 grep과 sed 사용
    URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | head -1 | sed 's/"public_url":"//')
fi

if [ -n "$URL" ]; then
    echo ""
    echo "========================================"
    echo "  ngrok 터널 URL:"
    echo "  $URL"
    echo "========================================"
    echo ""
    echo "이 URL로 외부에서 접속할 수 있습니다."
else
    echo "ngrok 터널 URL을 가져올 수 없습니다."
    echo "ngrok이 제대로 시작되지 않았을 수 있습니다."
    echo ""
    echo "상태 확인:"
    echo "systemctl --user status ngrok"
fi