#!/usr/bin/env bash
# Render.com 빌드 스크립트

set -o errexit

# Python 의존성 설치
pip install -r requirements.txt

# 데이터 디렉토리 생성
mkdir -p data
mkdir -p data/backups

echo "Build completed successfully!"