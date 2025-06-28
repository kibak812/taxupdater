#!/bin/bash
source taxupdater_venv/bin/activate
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload