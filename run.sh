#!/bin/bash
# Voice Translator 실행 스크립트
set -e
cd "$(dirname "$0")"

# 최초 실행인데 venv 가 없으면 설치부터
if [ ! -d ".venv" ]; then
  echo "가상환경이 없어 설치를 먼저 진행합니다..."
  ./install.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python voice_translate.py
