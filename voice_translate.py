"""
Text Translator — 한국어 텍스트 → 영어/스페인어
사용법:
  - 하단 입력창에 한국어 입력 후 🇺🇸 영어 번역 / 🇪🇸 스페인어 번역 버튼 클릭
결과는 logs/YYYY-MM-DD.md 에 자동 저장됨.
"""

import os
import sys
import random
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, font, messagebox

from anthropic import Anthropic


# ────────── 설정 ──────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT_EN = """너는 한국어 사용자를 위한 영어 학습 도우미다.
사용자가 보낸 한국어 단어 또는 문장을 영어로 번역한다.
아래 두 줄 형식을 정확히 지켜 출력하고, 다른 말이나 제목·라벨은 붙이지 마라:

번역: <가장 자연스러운 영어 표현 하나>
유의사항: <이 표현을 쓸 때 유의할 점을 한국어로 간결히. 헷갈리기 쉬운 유사 표현/단어가 있으면 그 차이를 함께>

스페인어는 절대 출력하지 마라.
"""

SYSTEM_PROMPT_ES = """너는 한국어 사용자를 위한 스페인어 학습 도우미다.
사용자가 보낸 한국어 단어 또는 문장을 España 표준 스페인어로 번역한다.
아래 두 줄 형식을 정확히 지켜 출력하고, 다른 말이나 제목·라벨은 붙이지 마라:

번역: <가장 자연스러운 스페인어 표현 하나>
유의사항: <이 표현을 쓸 때 유의할 점을 한국어로 간결히. 헷갈리기 쉬운 유사 표현/단어가 있으면 그 차이를 함께>

영어는 절대 출력하지 마라.
"""

DAILY_CONVERSATION_PROMPT = """너는 스페인어/영어 학습용 대화 콘텐츠를 만드는 작가다.
사용자가 지정한 주제와 문장 수에 맞춰 자연스러운 대화 하나를 만들어라.

요구사항:
- 두 사람 A와 B의 대화. 발화 수와 대화 주제는 사용자가 지정한 값을 정확히 따른다.
- 같은 내용을 스페인어와 영어로 각각 작성 (영어는 스페인어의 자연스러운 번역)
- España 표준 스페인어 사용

아래 형식을 정확히 지켜서 출력해라. 스페인어 대화 전체를 먼저 모아서 쓰고,
그 다음에 같은 내용의 영어 대화 전체를 모아서 써라. 다른 설명이나 인사말은 붙이지 마라:

## 주제: <주제를 한국어로>

### 🇪🇸 Español
1. A: <스페인어 문장>
2. B: <스페인어 문장>
... (지정된 문장 수만큼 이어서)

### 🇺🇸 English
1. A: <영어 문장>
2. B: <영어 문장>
... (스페인어와 같은 수, 같은 순서, 같은 내용)
"""

# 주제를 비워두면 이 풀에서 무작위로 뽑는다(최근에 쓴 주제는 회피).
# LLM에 "자유롭게 선택"을 맡기면 매번 같은 주제(카페에서 친구 만나기 등)로 수렴하므로
# Python이 직접 골라서 다양성을 보장한다.
DAILY_TOPIC_POOL = [
    # 일상생활 (Vida diaria / Daily life)
    "아침 루틴 설명하기",          # La rutina de la mañana / Morning routine
    "길 묻고 안내하기",            # Pedir y dar direcciones / Asking for directions
    "날씨에 대해 이야기하기",      # Hablar del tiempo / Talking about the weather
    "집안일 분담하기",            # Las tareas del hogar / Household chores
    "이웃과 인사·잡담",           # Charlar con los vecinos / Chatting with neighbors
    # 음식·외식 (Comida / Food & dining)
    "식당에서 주문하기",          # Pedir en un restaurante / Ordering at a restaurant
    "음식 알레르기·제한 말하기",   # Alergias alimentarias / Food allergies
    "카페에서 커피 주문",         # Pedir un café / Ordering coffee
    "요리법 설명하기",            # Explicar una receta / Explaining a recipe
    "계산서 나눠 내기",           # Dividir la cuenta / Splitting the bill
    # 여행·이동 (Viajes / Travel)
    "호텔 체크인·체크아웃",       # Registrarse en el hotel / Hotel check-in
    "공항에서",                  # En el aeropuerto / At the airport
    "택시·버스 이용",            # Tomar un taxi o autobús / Taking a taxi or bus
    "기차표 예매",               # Comprar billetes de tren / Buying train tickets
    "길을 잃었을 때",            # Cuando te pierdes / When you get lost
    # 쇼핑·소비 (Compras / Shopping)
    "옷 사이즈·교환",            # Tallas y cambios de ropa / Clothing sizes and exchanges
    "시장에서 흥정",             # Regatear en el mercado / Bargaining at a market
    "환불 요청하기",             # Pedir un reembolso / Requesting a refund
    "슈퍼마켓에서",              # En el supermercado / At the supermarket
    "온라인 주문 문제 해결",      # Problemas con un pedido online / Online order issues
    # 사회적 관계 (Relaciones / Social)
    "자기소개",                  # Presentarse / Introducing yourself
    "약속 잡기·취소하기",         # Quedar y cancelar planes / Making and canceling plans
    "초대하고 초대받기",          # Invitar y aceptar invitaciones / Inviting and accepting
    "사과하기",                  # Pedir disculpas / Apologizing
    "축하·위로 건네기",          # Felicitar y dar el pésame / Congratulating and condoling
    # 직장·업무 (Trabajo / Work)
    "면접 보기",                 # Una entrevista de trabajo / Job interview
    "회의에서 의견 내기",         # Opinar en una reunión / Speaking up in a meeting
    "이메일로 일정 조율",         # Coordinar horarios por correo / Scheduling by email
    "도움 요청하기",             # Pedir ayuda a un colega / Asking a colleague for help
    "휴가 신청하기",             # Solicitar vacaciones / Requesting time off
    # 건강·응급 (Salud / Health)
    "병원에서 증상 설명",         # Describir síntomas / Describing symptoms
    "약국에서",                  # En la farmacia / At the pharmacy
    "응급 상황 신고",            # Llamar a emergencias / Calling emergency services
    "진료 예약 잡기",            # Pedir cita médica / Making a doctor's appointment
    "운동·건강 습관",            # Hábitos de salud / Health habits
    # 여가·취미 (Ocio / Leisure)
    "주말 계획",                 # Planes para el fin de semana / Weekend plans
    "영화·드라마 추천",          # Recomendar películas / Recommending movies
    "취미 소개하기",             # Hablar de tus aficiones / Talking about hobbies
    "운동 경기 보기",            # Ver un partido / Watching a game
    "음악·공연 이야기",          # Hablar de música y conciertos / Music and concerts
    # 감정·의견 (Emociones / Feelings)
    "동의·반대 표현",            # Estar de acuerdo o no / Agreeing and disagreeing
    "기쁨·실망 표현",            # Expresar alegría y decepción / Joy and disappointment
    "불만 제기하기",             # Hacer una queja / Making a complaint
    "부탁 정중히 거절하기",       # Rechazar amablemente / Politely declining
    "조언 구하고 주기",          # Pedir y dar consejos / Asking for and giving advice
    # 디지털·현대생활 (Vida moderna / Modern life)
    "휴대폰 개통·요금제",         # Contratar un plan de móvil / Phone plans
    "와이파이·기술 문제",         # Problemas técnicos / Tech and Wi-Fi issues
    "SNS·메시지로 약속 잡기",     # Quedar por mensaje / Making plans by text
    "은행 계좌·송금",            # Trámites bancarios / Banking tasks
    "집 구하기·계약",            # Buscar y alquilar piso / Finding and renting a place
    # 관광지·관광객 (Zona turística / Tourist area — 집 근처에서 마주치는 상황)
    "관광객에게 길·맛집 추천해주기",    # Recomendar sitios a turistas / Recommending places to tourists
    "사진 찍어달라는 관광객 도와주기",  # Ayudar a un turista con una foto / Helping a tourist take a photo
    "동네 명소와 역사 설명해주기",      # Explicar lugares y su historia / Explaining local landmarks
    "길 잃은 외국인 관광객 안내하기",   # Orientar a un turista perdido / Guiding a lost tourist
    "관광객에게 대중교통 이용법 알려주기",  # Explicar el transporte público / Explaining public transport
    "현지인만 아는 숨은 장소 소개하기",    # Recomendar sitios locales / Sharing hidden local spots
]

# 경로
# PyInstaller 로 .app 번들로 실행되면(frozen) 번들 안은 쓰기 불가/재설치 시 사라지므로
# 로그·설정을 ~/Library/Application Support/VoiceTranslator 아래에 둔다.
CONFIG_DIR = Path.home() / "Library" / "Application Support" / "VoiceTranslator"
CONFIG_FILE = CONFIG_DIR / "config"

if getattr(sys, "frozen", False):
    SCRIPT_DIR = CONFIG_DIR
else:
    SCRIPT_DIR = Path(__file__).parent

LOCAL_ENV = SCRIPT_DIR / ".env"
LOGS_DIR = SCRIPT_DIR / "logs"
VOCAB_FILE = LOGS_DIR / "vocab.md"
CONVERSATION_FILE = LOGS_DIR / "conversation.md"
DAILY_CONV_DIR = LOGS_DIR / "daily_conversations"
TRANSLATIONS_FILE = LOGS_DIR / "translations.md"  # 번역 결과 문장만 누적 저장

READY_MSG = "아래 입력창에 한국어를 입력하고 번역 버튼을 누르세요"
# ──────────────────────────


def load_api_key() -> str:
    """환경변수 → 스크립트 폴더의 .env → ~/Library 설정파일 순으로 찾는다."""
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key.strip()

    if LOCAL_ENV.exists():
        for line in LOCAL_ENV.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    return ""


def show_config_error():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "API 키 설정 필요",
        f"ANTHROPIC_API_KEY가 설정되어 있지 않습니다.\n\n"
        f"다음 중 한 곳에 키를 저장하세요:\n"
        f"1. 환경변수 ANTHROPIC_API_KEY\n"
        f"2. {LOCAL_ENV}\n"
        f"3. {CONFIG_FILE}\n\n"
        f"파일 형식 예시:\n"
        f"ANTHROPIC_API_KEY=sk-ant-...",
    )
    root.destroy()


class VoiceTranslator:
    def __init__(self, api_key: str):
        self.claude = Anthropic(api_key=api_key)

        # UI
        self.root = tk.Tk()
        self.root.title("Text Translator — KO → EN / ES")
        self.root.geometry("960x720")
        self.root.minsize(820, 520)

        self.status = tk.Label(
            self.root, text=READY_MSG,
            font=("Helvetica", 13), pady=8,
        )
        self.status.pack()

        # 결과 출력 영역
        text_font = font.Font(family="Menlo", size=13)
        self.text = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=text_font, padx=14, pady=14,
        )
        self.text.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 6))

        # 마우스 선택 → 복사 지원 (⌘C / Ctrl+C + 우클릭 메뉴)
        self.text.bind("<Command-c>", self._copy_selection)
        self.text.bind("<Command-C>", self._copy_selection)
        self.text.bind("<Control-c>", self._copy_selection)
        self.text.bind("<Command-a>", lambda e: (self._select_all(), "break")[1])
        self.text.bind("<Command-A>", lambda e: (self._select_all(), "break")[1])
        self.text.bind("<Control-a>", lambda e: (self._select_all(), "break")[1])
        self.text.bind("<Command-d>", self._add_selection_to_vocab)
        self.text.bind("<Command-D>", self._add_selection_to_vocab)
        self.text.bind("<Control-d>", self._add_selection_to_vocab)
        self.text.bind("<Command-Shift-d>", self._add_selection_to_conversation)
        self.text.bind("<Command-Shift-D>", self._add_selection_to_conversation)
        self.text.bind("<Control-Shift-d>", self._add_selection_to_conversation)
        self.text.bind("<Control-Shift-D>", self._add_selection_to_conversation)
        self._build_copy_menu()
        # macOS는 우클릭이 Button-2, 일반은 Button-3
        self.text.bind("<Button-2>", self._show_copy_menu)
        self.text.bind("<Button-3>", self._show_copy_menu)
        self.text.bind("<Control-Button-1>", self._show_copy_menu)
        # 키 입력은 막되, 선택/스크롤/단축키는 통과시켜 "선택 가능한 읽기 전용"으로 만든다
        self.text.bind("<Key>", self._block_keys)

        # 텍스트 입력 영역 (여러 줄, 기본 5줄)
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        self.entry = tk.Text(input_frame, font=("Helvetica", 13), height=5, wrap=tk.WORD)
        self.entry.pack(fill=tk.X, ipady=2)
        # Enter=번역 실행, Shift+Enter=줄바꿈
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Shift-Return>", lambda e: None)

        # 번역 버튼 하나: 영어·스페인어 함께
        tk.Button(
            input_frame, text="번역 (Enter)",
            font=("Helvetica", 13, "bold"),
            command=self.submit_text,
        ).pack(fill=tk.X, pady=(6, 0))

        # 하단 버튼
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=(0, 10))
        tk.Button(
            btn_frame, text="📁 로그 폴더 열기",
            command=self.open_logs_folder,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="📒 단어장 열기",
            command=self.open_vocab,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="💬 대화 열기",
            command=self.open_conversation,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="📝 오늘의 대화 생성",
            command=self.generate_today_conversation,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="📖 오늘의 대화 보기",
            command=self.view_conversations,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="📄 번역 모음 열기",
            command=self.open_translations,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="🗑️ 화면 비우기",
            command=self.clear_screen,
        ).pack(side=tk.LEFT, padx=4)

        # 시작 시 입력창에 포커스
        self.entry.focus_set()

    # ── UI 헬퍼 ──
    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status.config(text=msg))

    def append(self, msg: str):
        def _do():
            self.text.insert(tk.END, msg)
            self.text.see(tk.END)
        self.root.after(0, _do)

    def clear_screen(self):
        self.text.delete("1.0", tk.END)

    # ── 복사/읽기 전용 헬퍼 ──
    def _copy_selection(self, _event=None):
        try:
            sel = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(sel)
        return "break"

    def _build_copy_menu(self):
        self._copy_menu = tk.Menu(self.root, tearoff=0)
        self._copy_menu.add_command(label="복사", command=self._copy_selection)
        self._copy_menu.add_command(label="📒 단어장에 추가", command=self._add_selection_to_vocab)
        self._copy_menu.add_command(label="💬 대화 저장", command=self._add_selection_to_conversation)
        self._copy_menu.add_separator()
        self._copy_menu.add_command(label="모두 선택", command=self._select_all)

    def _show_copy_menu(self, event):
        try:
            self._copy_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._copy_menu.grab_release()
        return "break"

    def _select_all(self):
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        self.text.see("insert")

    def _block_keys(self, event):
        # 복사/전체선택/탐색 키는 허용, 나머지는 차단 → 선택 가능한 읽기 전용
        allowed_with_mod = {"c", "C", "a", "A"}
        if (event.state & 0x8 or event.state & 0x4) and event.keysym in allowed_with_mod:
            return None
        navigation = {
            "Left", "Right", "Up", "Down",
            "Home", "End", "Prior", "Next",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Meta_L", "Meta_R", "Command", "Alt_L", "Alt_R",
        }
        if event.keysym in navigation:
            return None
        return "break"

    # ── 텍스트 입력 처리 ──
    def _on_return(self, _event):
        """Enter → 번역 실행 (줄바꿈 방지). Shift+Enter는 별도 바인딩으로 줄바꿈."""
        self.submit_text()
        return "break"

    def submit_text(self):
        text = self.entry.get("1.0", "end-1c").strip()
        if not text:
            return
        self.entry.delete("1.0", tk.END)
        threading.Thread(target=lambda: self._translate(text), daemon=True).start()

    # ── 번역 로직: 영어 결과 → 10줄 아래 → 스페인어 결과(동일 형식) ──
    def _translate(self, ko_text: str):
        self.append(f"\n▶ 입력: {ko_text}\n")
        self.set_status("🤖 Claude 호출 중… (영어)")

        try:
            en_tr, en_block = self._translate_one(ko_text, SYSTEM_PROMPT_EN)
            self.set_status("🤖 Claude 호출 중… (스페인어)")
            es_tr, es_block = self._translate_one(ko_text, SYSTEM_PROMPT_ES)
        except Exception as e:
            self.append(f"[오류] {e}\n")
            self.set_status(READY_MSG)
            return

        # 영어 결과 → 10줄 아래 → 스페인어 결과
        combined = f"{en_block}{chr(10) * 10}{es_block}\n"
        self.append(combined)
        self.save_to_log(ko_text, combined)
        # 번역 문장만 하나의 파일에 누적 저장
        self.save_translation_sentences(en_tr, es_tr)
        self.set_status(READY_MSG)

    def _translate_one(self, ko_text: str, system_prompt: str):
        """한 언어 번역. (번역문, 표시용 블록) 튜플 반환.
        블록 형식: 번역문 → 3줄 아래 구분선 → 표현 시 유의사항."""
        msg = self.claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": ko_text}],
        )
        response = "".join(b.text for b in msg.content if b.type == "text")
        translation, notes = self._parse_response(response)
        block = f"{translation}\n\n\n----------------------------\n{notes}\n"
        return translation, block

    def save_translation_sentences(self, en_tr: str, es_tr: str):
        """번역 결과 문장만 translations.md 에 누적 저장 (입력·유의사항 제외)."""
        LOGS_DIR.mkdir(exist_ok=True)
        # 각 문장 앞에 구분 기호(- )를 붙여 문장을 명확히 구분
        lines = [f"- {t.strip()}" for t in (en_tr, es_tr) if t and t.strip()]
        if not lines:
            return
        with TRANSLATIONS_FILE.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n\n")

    @staticmethod
    def _parse_response(response: str):
        """Claude 응답에서 '번역:'/'유의사항:' 을 뽑는다. 형식이 어긋나면 통째로 번역으로 처리."""
        translation, notes = "", ""
        for line in response.splitlines():
            s = line.strip()
            if s.startswith("번역:"):
                translation = s[len("번역:"):].strip()
            elif s.startswith("유의사항:"):
                notes = s[len("유의사항:"):].strip()
        if not translation:
            translation = response.strip()
        return translation, notes

    # ── 로그 ──
    def save_to_log(self, ko_text: str, response: str):
        LOGS_DIR.mkdir(exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"{today}.md"
        timestamp = datetime.now().strftime("%H:%M")

        header = f"# {today}\n\n" if not log_file.exists() else ""
        entry = f"## {timestamp} — {ko_text}\n\n{response}\n\n---\n\n"

        with log_file.open("a", encoding="utf-8") as f:
            f.write(header + entry)

    def open_logs_folder(self):
        LOGS_DIR.mkdir(exist_ok=True)
        subprocess.run(["open", str(LOGS_DIR)])

    # ── 단어장 ──
    def _add_selection_to_vocab(self, _event=None):
        try:
            sel = self.text.get("sel.first", "sel.last").strip()
        except tk.TclError:
            sel = ""
        if not sel:
            self.set_status("⚠️  먼저 단어/문장을 선택하세요")
            return "break"

        LOGS_DIR.mkdir(exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        existing = VOCAB_FILE.read_text(encoding="utf-8") if VOCAB_FILE.exists() else ""

        # 전체 파일에서 동일 항목이 이미 있으면 중복 추가하지 않음
        if any(line.strip() == f"- {sel}" for line in existing.splitlines()):
            self.set_status(f"📒 이미 단어장에 있음: {sel[:40]}")
            return "break"

        today_marker = f"<!-- {today} -->"
        with VOCAB_FILE.open("a", encoding="utf-8") as f:
            if not existing:
                f.write(f"# 단어장\n\n{today_marker}\n")
            elif today_marker not in existing:
                sep = "" if existing.endswith("\n") else "\n"
                f.write(f"{sep}\n---\n\n{today_marker}\n")
            f.write(f"- {sel}\n")

        preview = sel if len(sel) <= 40 else sel[:40] + "…"
        self.set_status(f"📒 단어장에 추가: {preview}")
        return "break"

    def open_vocab(self):
        LOGS_DIR.mkdir(exist_ok=True)
        if not VOCAB_FILE.exists():
            VOCAB_FILE.write_text("# 단어장\n\n", encoding="utf-8")
        subprocess.run(["open", str(VOCAB_FILE)])

    def open_translations(self):
        """번역 문장만 누적한 파일을 연다."""
        LOGS_DIR.mkdir(exist_ok=True)
        if not TRANSLATIONS_FILE.exists():
            self.set_status("📄 아직 저장된 번역이 없습니다")
            return
        subprocess.run(["open", str(TRANSLATIONS_FILE)])

    # ── 대화 저장 ──
    def _add_selection_to_conversation(self, _event=None):
        try:
            sel = self.text.get("sel.first", "sel.last").strip()
        except tk.TclError:
            sel = ""
        if not sel:
            self.set_status("⚠️  먼저 저장할 영역을 선택하세요")
            return "break"

        LOGS_DIR.mkdir(exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        existing = CONVERSATION_FILE.read_text(encoding="utf-8") if CONVERSATION_FILE.exists() else ""

        today_marker = f"<!-- {today} -->"
        with CONVERSATION_FILE.open("a", encoding="utf-8") as f:
            if not existing:
                f.write(f"# 대화 모음\n\n{today_marker}\n\n")
            elif today_marker not in existing:
                sep = "" if existing.endswith("\n") else "\n"
                f.write(f"{sep}\n---\n\n{today_marker}\n\n")
            f.write(f"{sel}\n")

        preview = sel.replace("\n", " ")
        preview = preview if len(preview) <= 40 else preview[:40] + "…"
        self.set_status(f"💬 대화 저장: {preview}")
        return "break"

    def open_conversation(self):
        LOGS_DIR.mkdir(exist_ok=True)
        if not CONVERSATION_FILE.exists():
            CONVERSATION_FILE.write_text("# 대화 모음\n\n", encoding="utf-8")
        subprocess.run(["open", str(CONVERSATION_FILE)])

    # ── 오늘의 대화 ──
    def generate_today_conversation(self):
        """문장 수/주제 옵션을 물어보고 스페인어·영어 대화를 만든다.
        같은 날에 여러 번 실행하면 그 날짜 파일에 누적 저장된다."""
        DAILY_CONV_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        conv_file = DAILY_CONV_DIR / f"{today}.md"
        self._ask_generation_options(conv_file, today)

    def _ask_generation_options(self, conv_file: Path, today: str):
        """문장 수와 대화 상황을 입력받는 모달 창. 비워두면 기본값(20문장 / 임의의 주제)."""
        win = tk.Toplevel(self.root)
        win.title("오늘의 대화 옵션")
        win.geometry("440x240")
        win.transient(self.root)
        win.grab_set()

        tk.Label(
            win, text="문장 수 (비우면 20)",
            font=("Helvetica", 12),
        ).pack(anchor="w", padx=14, pady=(14, 2))
        count_entry = tk.Entry(win, font=("Helvetica", 13))
        count_entry.pack(fill=tk.X, padx=14, ipady=3)

        tk.Label(
            win, text="대화 상황 (비우면 임의의 주제)",
            font=("Helvetica", 12),
        ).pack(anchor="w", padx=14, pady=(12, 2))
        topic_entry = tk.Entry(win, font=("Helvetica", 13))
        topic_entry.pack(fill=tk.X, padx=14, ipady=3)

        def submit():
            raw_count = count_entry.get().strip()
            topic = topic_entry.get().strip()
            try:
                count = int(raw_count) if raw_count else 20
                if count <= 0:
                    count = 20
            except ValueError:
                count = 20
            win.destroy()
            self.set_status(f"🤖 오늘의 대화 생성 중… ({count}문장)")
            threading.Thread(
                target=lambda: self._do_generate_conversation(conv_file, today, count, topic),
                daemon=True,
            ).start()

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="생성", command=submit, width=10).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="취소", command=win.destroy, width=10).pack(side=tk.LEFT, padx=6)

        win.bind("<Return>", lambda _e: submit())
        win.bind("<Escape>", lambda _e: win.destroy())
        count_entry.focus_set()

    def _used_daily_topics(self) -> set:
        """저장된 모든 daily 대화 파일에서 이미 사용한 주제를 전부 모은다(중복 회피용).
        앱이 쓴 헤더(`## HH:MM — 요청: N문장 / 주제: XXX (임의)`)와
        LLM 응답 헤더(`## 주제: XXX`) 둘 다에서 주제를 추출한다."""
        used: set = set()
        marker = "주제: "
        for f in DAILY_CONV_DIR.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                if line.startswith("## ") and marker in line:
                    t = line.split(marker, 1)[1].strip()
                    if t.endswith(" (임의)"):  # 자동 선택 꼬리표 제거
                        t = t[: -len(" (임의)")]
                    if t:
                        used.add(t)
        return used

    def _pick_random_topic(self, used: set = None) -> str:
        """주제 풀에서 아직 안 쓴 주제를 무작위로 고른다. 풀이 소진되면 빈 문자열."""
        if used is None:
            used = self._used_daily_topics()
        candidates = [t for t in DAILY_TOPIC_POOL if t not in used]
        if not candidates:  # 풀을 다 소진 → LLM이 새 주제를 직접 만들도록 위임
            return ""
        return random.choice(candidates)

    @staticmethod
    def _extract_topic(response: str) -> str:
        """대화 응답의 `## 주제: XXX` 줄에서 주제 텍스트를 뽑는다(없으면 빈 문자열)."""
        marker = "주제: "
        for line in response.splitlines():
            if line.startswith("## ") and marker in line:
                return line.split(marker, 1)[1].strip()
        return ""

    def _do_generate_conversation(self, conv_file: Path, today: str, count: int, topic: str):
        # 저장된 모든 대화의 주제를 확인해 중복을 피한다
        used = self._used_daily_topics()
        chosen_topic = topic if topic else self._pick_random_topic(used)

        if chosen_topic:
            topic_line = f"- 대화 상황/주제: {chosen_topic}\n"
        else:
            # 풀 소진: LLM이 기존 주제와 겹치지 않는 새 주제를 직접 고르게 한다
            topic_line = (
                "- 대화 상황/주제: 아래 '이미 사용한 주제'와 겹치지 않는, "
                "새롭고 구체적인 일상 주제를 네가 직접 하나 골라라\n"
            )

        # 사용자가 직접 주제를 지정하지 않았으면, 이미 쓴 주제 목록을 알려 회피시킨다
        avoid_line = ""
        if not topic and used:
            avoid_line = "- 이미 사용한 주제(반드시 피할 것): " + ", ".join(sorted(used)) + "\n"

        user_msg = (
            f"오늘({today})의 대화를 만들어줘.\n"
            f"{topic_line}"
            f"{avoid_line}"
            f"- 발화 수: 총 {count}문장 (A와 B의 발화를 합쳐서 정확히 {count}개)\n"
        )
        try:
            msg = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=DAILY_CONVERSATION_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            response = "".join(b.text for b in msg.content if b.type == "text").strip()
            if not response:
                self.set_status("⚠️  오늘의 대화 생성 실패 (빈 응답)")
                return
            # 성공했을 때만 저장 → 실패 시 재시도 가능
            # 같은 날에 여러 번 생성 가능: 첫 호출이면 헤더, 이후엔 구분선 + 시간/옵션 헤더로 누적
            timestamp = datetime.now().strftime("%H:%M")
            auto_tag = "" if topic else " (임의)"
            # 풀 소진 시 LLM이 고른 실제 주제를 응답의 '## 주제:' 줄에서 뽑아 헤더에 반영
            resolved_topic = chosen_topic or self._extract_topic(response) or "새 주제"
            section_header = (
                f"## {timestamp} — 요청: {count}문장 / 주제: {resolved_topic}{auto_tag}\n\n"
            )
            if not conv_file.exists():
                conv_file.write_text(f"# 오늘의 대화 — {today}\n\n", encoding="utf-8")
            else:
                with conv_file.open("a", encoding="utf-8") as f:
                    f.write("\n---\n\n")
            with conv_file.open("a", encoding="utf-8") as f:
                f.write(section_header + response + "\n")
            self.append(f"\n📝 오늘의 대화 ({today} {timestamp})\n\n{response}\n{'─' * 70}\n")
            self.set_status(f"✅ 오늘의 대화 생성 완료 ({today} {timestamp})")
        except Exception as e:
            self.set_status("⚠️  오늘의 대화 생성 실패")
            self.append(f"[오류] {e}\n")

    def view_conversations(self):
        """생성된 오늘의 대화 목록을 날짜별로 보여주고, 선택한 날짜의 내용을 표시한다."""
        DAILY_CONV_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(DAILY_CONV_DIR.glob("*.md"), reverse=True)
        if not files:
            self.set_status("📖 아직 생성된 오늘의 대화가 없습니다")
            return

        dates = [f.stem for f in files]

        win = tk.Toplevel(self.root)
        win.title("📖 오늘의 대화 보기")
        win.geometry("860x620")

        left = tk.Frame(win)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 4), pady=10)
        tk.Label(left, text="날짜", font=("Helvetica", 12, "bold")).pack(anchor="w")
        listbox = tk.Listbox(left, width=16, font=("Helvetica", 13), activestyle="dotbox")
        listbox.pack(fill=tk.Y, expand=True)
        for d in dates:
            listbox.insert(tk.END, d)

        right = tk.Frame(win)
        right.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(4, 10), pady=10)

        # 상단 도구 모음: 현재 보이는 대화 인쇄
        toolbar = tk.Frame(right)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        current_date = tk.StringVar(value=dates[0])
        tk.Label(toolbar, textvariable=current_date, font=("Helvetica", 12, "bold")).pack(side=tk.LEFT)

        viewer = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=font.Font(family="Menlo", size=13),
            padx=14, pady=14,
        )
        viewer.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        tk.Button(
            toolbar, text="🖨️ 인쇄",
            command=lambda: self._print_viewer(viewer, current_date.get(), win),
        ).pack(side=tk.RIGHT)
        tk.Button(
            toolbar, text="🔍 미리보기",
            command=lambda: self._preview_print(viewer, current_date.get(), win),
        ).pack(side=tk.RIGHT, padx=(0, 6))

        def show_selected(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            d = dates[sel[0]]
            current_date.set(d)
            content = (DAILY_CONV_DIR / f"{d}.md").read_text(encoding="utf-8")
            viewer.config(state=tk.NORMAL)
            viewer.delete("1.0", tk.END)
            viewer.insert(tk.END, content)
            viewer.config(state=tk.DISABLED)

        listbox.bind("<<ListboxSelect>>", show_selected)
        listbox.selection_set(0)
        show_selected()

    def _preview_print(self, viewer: scrolledtext.ScrolledText, date_label: str, parent: tk.Toplevel):
        """뷰어 내용을 임시 파일로 저장 후 TextEdit으로 열어 macOS 인쇄 미리보기(Cmd+P)를 활용."""
        content = viewer.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("인쇄 미리보기", "미리볼 내용이 없습니다.", parent=parent)
            return
        import tempfile
        preview_path = Path(tempfile.gettempdir()) / f"오늘의 대화 {date_label}.txt"
        try:
            preview_path.write_text(content, encoding="utf-8")
            subprocess.run(["open", "-a", "TextEdit", str(preview_path)], check=True)
            self.set_status(f"🔍 TextEdit에서 미리보기 — ⌘P로 인쇄 ({date_label})")
        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "미리보기 실패",
                f"TextEdit을 여는 데 실패했습니다.\n\n{e}",
                parent=parent,
            )
        except OSError as e:
            messagebox.showerror(
                "미리보기 실패",
                f"임시 파일 작성에 실패했습니다.\n\n{e}",
                parent=parent,
            )

    def _print_viewer(self, viewer: scrolledtext.ScrolledText, date_label: str, parent: tk.Toplevel):
        """뷰어에 표시된 텍스트를 macOS 기본 프린터로 보낸다 (lpr)."""
        content = viewer.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("인쇄", "인쇄할 내용이 없습니다.", parent=parent)
            return
        try:
            result = subprocess.run(
                ["lpr", "-T", f"오늘의 대화 {date_label}"],
                input=content.encode("utf-8"),
                capture_output=True,
                check=True,
            )
            messagebox.showinfo(
                "인쇄", f"기본 프린터로 인쇄 작업을 보냈습니다.\n({date_label})",
                parent=parent,
            )
        except FileNotFoundError:
            messagebox.showerror(
                "인쇄 실패", "lpr 명령을 찾을 수 없습니다.", parent=parent,
            )
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", errors="ignore").strip()
            messagebox.showerror(
                "인쇄 실패",
                "기본 프린터가 설정되어 있지 않거나 인쇄 큐 오류일 수 있습니다.\n"
                "시스템 설정 > 프린터 및 스캐너에서 프린터를 확인하세요.\n\n"
                f"{err}",
                parent=parent,
            )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    key = load_api_key()
    if not key:
        show_config_error()
        sys.exit(1)
    VoiceTranslator(key).run()