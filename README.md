# Text Translator

한국어 텍스트를 영어와 스페인어로 번역해주는 학습용 데스크톱 앱.

- 번역과 설명은 **Claude (Anthropic API)** 가 생성 — 격식/비격식, España/Latinoamérica 구분, 유의어 nuance 포함
- 모든 결과는 `logs/YYYY-MM-DD.md` 에 자동 저장
- 결과창에서 마우스로 선택한 단어/구를 **단어장**(`logs/vocab.md`) 또는 **대화 모음**(`logs/conversation.md`) 에 저장 가능

## 실행 환경

macOS. 마이크·접근성 권한이 필요 없는 텍스트 전용 앱이라 터미널이나 더블클릭 런처로 바로 실행하면 된다.

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

- 입력창은 **여러 줄 입력**(기본 5줄) 가능. 한국어를 적고
  **🇺🇸 영어 번역** 또는 **🇪🇸 스페인어 번역** 버튼을 누르면 해당 언어로만 번역

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

- `CLAUDE_MODEL` — 번역에 쓰는 Claude 모델 ID
- `SYSTEM_PROMPT_EN` / `SYSTEM_PROMPT_ES` — 영어/스페인어 번역 출력 형식·스타일 지시
