#!/bin/bash
# Voice Translator 설치 스크립트
# 대상 맥에서 한 번만 실행하면 됩니다: 가상환경 생성 + 의존성 설치
set -e

cd "$(dirname "$0")"
echo "📦 Voice Translator 설치를 시작합니다..."

# ── Python 찾기 (3.12 → 3.11 → 3.10 → python3 순) ──
PYTHON=""
for cand in python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    PYTHON="$cand"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "❌ Python3 가 없습니다. 먼저 설치하세요:"
  echo "   brew install python@3.12"
  echo "   (Homebrew 가 없으면 https://brew.sh 참고)"
  exit 1
fi

PYVER=$("$PYTHON" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
echo "🐍 사용할 Python: $PYTHON ($PYVER)"

# faster-whisper/ctranslate2 는 아주 최신 파이썬(3.14 등)에서 휠이 없을 수 있음
case "$PYVER" in
  3.9|3.10|3.11|3.12|3.13) ;;
  *)
    echo "⚠️  Python $PYVER 는 일부 패키지 휠이 없을 수 있습니다."
    echo "    문제가 생기면: brew install python@3.12 후 다시 실행하세요."
    ;;
esac

# ── 가상환경 ──
if [ ! -d ".venv" ]; then
  echo "🧪 가상환경(.venv) 생성 중..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "⬆️  pip 업그레이드..."
python -m pip install --upgrade pip >/dev/null

echo "📥 의존성 설치 중 (몇 분 걸릴 수 있습니다)..."
pip install -r requirements.txt

# ── tkinter(GUI) 확인 — Homebrew python 은 tkinter 가 기본 포함이 아님 ──
if ! python -c "import tkinter" >/dev/null 2>&1; then
  echo ""
  echo "❌ 이 Python 에는 tkinter(GUI 라이브러리)가 없어 앱 창이 뜨지 않습니다."
  echo "   해결 방법 중 하나:"
  echo "   • Homebrew python 사용 시:  brew install python-tk@$PYVER"
  echo "   • 또는 python.org 설치본 사용 (tkinter 기본 포함)"
  echo "   설치 후 이 창을 닫고 다시 실행하세요."
  exit 1
fi

echo ""
echo "✅ 설치 완료!"
echo ""
echo "다음 단계:"
echo "  1) API 키 설정 — .env.example 을 .env 로 복사하고 키를 넣으세요:"
echo "       cp .env.example .env"
echo "       그 후 .env 파일을 열어 sk-ant-... 키를 붙여넣기"
echo "  2) 실행 — VoiceTranslator.command 를 더블클릭하거나:"
echo "       ./run.sh"
echo ""
echo "※ 첫 실행 시 음성인식 모델(약 1.5GB)이 자동 다운로드됩니다."
