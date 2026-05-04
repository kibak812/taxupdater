from fastapi import APIRouter, HTTPException

from src.web.context import WebAppContext, get_configured_ngrok_url


def create_tunnel_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.get("/api/tunnel-status")
    async def get_tunnel_status():
        try:
            import requests
            import subprocess

            configured_ngrok_url = get_configured_ngrok_url()
            tunnel_status = {
                "ngrok": {
                    "status": "unknown",
                    "url": None,
                    "configured_url": configured_ngrok_url or None,
                    "is_static": False,
                }
            }

            try:
                result = subprocess.run(
                    ["pgrep", "-x", "ngrok"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    tunnel_status["ngrok"]["status"] = "active"
                    try:
                        response = requests.get("http://localhost:4040/api/tunnels", timeout=3)
                        if response.status_code == 200:
                            tunnels = response.json().get("tunnels", [])
                            if tunnels:
                                public_url = tunnels[0].get("public_url")
                                tunnel_status["ngrok"]["url"] = public_url
                                tunnel_status["ngrok"]["is_static"] = bool(
                                    configured_ngrok_url and public_url == configured_ngrok_url
                                )
                                if configured_ngrok_url and public_url != configured_ngrok_url:
                                    tunnel_status["ngrok"]["status"] = "active_dynamic"
                    except Exception:
                        pass
                else:
                    tunnel_status["ngrok"]["status"] = (
                        "static_unconfigured" if not configured_ngrok_url else "inactive"
                    )
            except Exception as e:
                tunnel_status["ngrok"]["status"] = f"error: {str(e)}"

            return tunnel_status
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 상태 확인 실패: {str(e)}")

    @router.post("/api/tunnel/start/{tunnel_type}")
    async def start_tunnel(tunnel_type: str):
        try:
            import shutil
            import subprocess

            if tunnel_type == "ngrok":
                if shutil.which("systemctl"):
                    result = subprocess.run(
                        ["systemctl", "--user", "start", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        return {"message": "ngrok이 시작되었습니다", "success": True}
                    raise HTTPException(status_code=500, detail=f"ngrok 시작 실패: {result.stderr}")

                if not shutil.which("ngrok"):
                    raise HTTPException(status_code=500, detail="ngrok이 설치되어 있지 않습니다")

                log_path = context.project_root / "logs" / "ngrok.log"
                log_path.parent.mkdir(exist_ok=True)
                log_file = open(log_path, "a")
                command = ["ngrok", "http", "8001"]
                configured_ngrok_url = get_configured_ngrok_url()
                if configured_ngrok_url:
                    command.extend(["--url", configured_ngrok_url])
                subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=str(context.project_root),
                    start_new_session=True,
                )
                return {"message": "ngrok 시작 명령을 실행했습니다", "success": True}

            raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 시작 실패: {str(e)}")

    @router.post("/api/tunnel/stop/{tunnel_type}")
    async def stop_tunnel(tunnel_type: str):
        try:
            import shutil
            import subprocess

            if tunnel_type == "ngrok":
                if shutil.which("systemctl"):
                    result = subprocess.run(
                        ["systemctl", "--user", "stop", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                else:
                    result = subprocess.run(
                        ["pkill", "-x", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                if result.returncode in (0, 1):
                    return {"message": "ngrok이 중지되었습니다", "success": True}
                raise HTTPException(status_code=500, detail=f"ngrok 중지 실패: {result.stderr}")

            raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 중지 실패: {str(e)}")

    return router
