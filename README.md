# Voice Translator

한국어 음성/텍스트를 영어와 스페인어로 번역해주는 학습용 데스크톱 앱.

- 음성 입력은 **faster-whisper**(로컬)로 인식
- 번역과 설명은 **Claude (Anthropic API)** 가 생성 — 격식/비격식, España/Latinoamérica 구분, 유의어 nuance 포함
- 모든 결과는 `logs/YYYY-MM-DD.md` 에 자동 저장
- 결과창에서 마우스로 선택한 단어/구를 **단어장**(`logs/vocab.md`) 또는 **대화 모음**(`logs/conversation.md`) 에 저장 가능

## 실행 환경

macOS. Automator 워크플로우로 실행하는 것을 전제로 만들어졌다.
터미널에서 직접 실행해도 동작하지만 단축키 등 일부 기능은 권한 컨텍스트에 영향을 받음.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## API 키 설정

다음 중 한 곳에 `ANTHROPIC_API_KEY` 를 두면 됨 (위에서부터 우선순위):

1. 환경변수 `ANTHROPIC_API_KEY`
2. 스크립트 폴더의 `.env`
3. `~/Library/Application Support/VoiceTranslator/config`

파일 형식:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## 사용법

```bash
python3 voice_translate.py
```

- 🎤 **녹음 버튼** 클릭 — 다시 누르면 종료
- 창 포커스 상태에서 **F9** 단축키로도 녹음 토글
- 하단 입력창에 **한국어 텍스트 + Enter** 로 음성 없이 번역만 사용 가능

### 결과창에서 사용 가능한 동작

| 동작 | 단축키 | 우클릭 메뉴 |
|---|---|---|
| 복사 | `⌘C` | 복사 |
| 모두 선택 | `⌘A` | 모두 선택 |
| 단어장에 추가 | `⌘D` | 📒 단어장에 추가 |
| 대화 저장 | `⌘⇧D` | 💬 대화 저장 |

결과창은 읽기 전용(선택만 가능). 우클릭은 macOS에서 `Ctrl+Click` 으로도 동작.

### 하단 버튼

- **📁 로그 폴더 열기** — 일별 로그 디렉터리
- **📒 단어장 열기** — `logs/vocab.md`
- **💬 대화 열기** — `logs/conversation.md`
- **🗑️ 화면 비우기** — 결과창 클리어 (저장된 로그는 유지)

## 저장 파일 구조

```
logs/
├── 2026-05-18.md       # 일별 전체 번역 로그
├── vocab.md            # 선택한 단어/구 모음 (날짜는 --- 로 구분)
└── conversation.md     # 선택한 대화/예문 모음
```

## 설정 변경

`voice_translate.py` 상단 상수에서 조정:

- `WHISPER_MODEL_SIZE` — `"tiny"`/`"base"`/`"small"`/`"medium"`/`"large"` (기본 `medium`)
- `CLAUDE_MODEL` — 번역에 쓰는 Claude 모델 ID
- `SYSTEM_PROMPT` — 번역 출력 형식/스타일 지시
