#!/usr/bin/env python3
"""
WebSocket을 통한 실시간 알림 테스트
웹 서버가 실행 중일 때 WebSocket으로 알림 메시지를 전송하는 테스트
"""

import asyncio
import websockets
import json
from datetime import datetime


async def test_websocket_notification():
    """WebSocket 알림 테스트"""
    uri = "ws://localhost:8001/ws/crawl"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"WebSocket 연결됨: {uri}")
            
            # 1. 연결 확인
            print("\n1. WebSocket 연결 테스트")
            print("-" * 50)
            print("✅ WebSocket 연결 성공")
            
            # 2. 새로운 데이터 알림 메시지 전송
            print("\n2. 새로운 데이터 알림 메시지 전송")
            print("-" * 50)
            
            notification_message = {
                "type": "notification",
                "notification_id": 999,
                "site_key": "tax_tribunal",
                "notification_type": "new_data",
                "title": "새로운 데이터 발견: 조세심판원",
                "message": "조세심판원에서 15개의 새로운 데이터가 발견되었습니다.",
                "urgency_level": "high",
                "new_data_count": 15,
                "metadata": {
                    "site_name": "조세심판원",
                    "test": True
                },
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(notification_message))
            print(f"✅ 알림 메시지 전송 완료: {notification_message['title']}")
            
            # 3. 크롤링 완료 메시지 전송
            print("\n3. 크롤링 완료 메시지 전송")
            print("-" * 50)
            
            complete_message = {
                "type": "crawl_complete",
                "site_key": "nts_authority",
                "message": "국세청 유권해석 크롤링이 성공적으로 완료되었습니다",
                "new_data_count": 8,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(complete_message))
            print(f"✅ 크롤링 완료 메시지 전송: 국세청 유권해석")
            
            # 4. 에러 알림 메시지 전송
            print("\n4. 에러 알림 메시지 전송")
            print("-" * 50)
            
            error_message = {
                "type": "crawl_error",
                "site_key": "moef",
                "error": "연결 시간 초과 - 서버 응답 없음",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(error_message))
            print(f"✅ 에러 메시지 전송: 기획재정부")
            
            # 5. 서버 응답 대기
            print("\n5. 서버 응답 대기 (5초)")
            print("-" * 50)
            
            try:
                # 5초 동안 서버 응답 대기
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📨 서버 응답: {response}")
            except asyncio.TimeoutError:
                print("⏱️ 5초 동안 서버 응답 없음 (정상)")
            
            print("\n✅ WebSocket 알림 테스트 완료")
            
    except websockets.exceptions.ConnectionRefused:
        print("❌ WebSocket 연결 실패: 서버가 실행 중이 아닙니다")
        print("   웹 서버가 실행 중인지 확인하세요 (./run.sh)")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


async def monitor_websocket_messages():
    """WebSocket 메시지 모니터링 (수신만)"""
    uri = "ws://localhost:8001/ws/crawl"
    
    print("\n=== WebSocket 메시지 모니터링 ===")
    print("(Ctrl+C로 종료)")
    print("-" * 50)
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ 모니터링 시작: {uri}\n")
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 메시지 수신:")
                    print(f"  타입: {data.get('type')}")
                    
                    if data.get('type') == 'notification':
                        print(f"  제목: {data.get('title')}")
                        print(f"  메시지: {data.get('message')}")
                        print(f"  신규 데이터: {data.get('new_data_count')}개")
                        print(f"  긴급도: {data.get('urgency_level')}")
                    elif data.get('type') == 'crawl_complete':
                        print(f"  사이트: {data.get('site_key')}")
                        print(f"  메시지: {data.get('message')}")
                    elif data.get('type') == 'crawl_error':
                        print(f"  사이트: {data.get('site_key')}")
                        print(f"  에러: {data.get('error')}")
                    
                    print("-" * 50)
                    
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 파싱 불가능한 메시지: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("\n❌ WebSocket 연결이 끊어졌습니다")
                    break
                    
    except websockets.exceptions.ConnectionRefused:
        print("❌ WebSocket 연결 실패: 서버가 실행 중이 아닙니다")
    except KeyboardInterrupt:
        print("\n\n모니터링 종료")


if __name__ == "__main__":
    print("=== 예규판례 모니터링 시스템 - WebSocket 알림 테스트 ===\n")
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # 모니터링 모드
        asyncio.run(monitor_websocket_messages())
    else:
        # 테스트 메시지 전송 모드
        asyncio.run(test_websocket_notification())