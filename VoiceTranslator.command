#!/bin/bash
# 더블클릭으로 실행되는 런처 (Finder 에서 더블클릭)
# 최초 실행 시 자동 설치까지 진행합니다.
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "==== 최초 실행: 설치를 시작합니다 ===="
  ./install.sh || { echo "설치 실패. 위 메시지를 확인하세요."; read -r -p "엔터를 누르면 닫힙니다..."; exit 1; }
fi

# API 키 확인
if [ ! -f ".env" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ ! -f "$HOME/Library/Application Support/VoiceTranslator/config" ]; then
  echo ""
  echo "⚠️  API 키가 설정되지 않았습니다."
  echo "   .env.example 을 .env 로 복사한 뒤 ANTHROPIC_API_KEY 를 넣으세요:"
  echo "       cp .env.example .env"
  echo ""
  read -r -p "엔터를 누르면 닫힙니다..."
  exit 1
fi

source .venv/bin/activate
python voice_translate.py
