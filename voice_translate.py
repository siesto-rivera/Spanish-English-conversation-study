"""
Voice Translator — 한국어 음성/텍스트 → 영어/스페인어
사용법:
  - 🎤 녹음 버튼 클릭 (또는 창 포커스 상태에서 F9)
  - 또는 하단 입력창에 한국어 입력 후 Enter
결과는 logs/YYYY-MM-DD.md 에 자동 저장됨.
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, font, messagebox

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from anthropic import Anthropic


# ────────── 설정 ──────────
SAMPLE_RATE = 16000
WHISPER_MODEL_SIZE = "medium"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """너는 한국어 사용자를 위한 영어/스페인어 학습 도우미다.
사용자가 보낸 한국어 단어 또는 문장을 다음 형식으로 답한다.

🇰🇷 입력: <맞춤법/띄어쓰기 정리한 원문>

🇺🇸 English
- 가장 자연스러운 표현 (필요 시 격식/비격식 둘 다)
- 의미 차이가 있는 유의어 1-2개와 nuance 설명

🇪🇸 Español
- España 표준
- Latinoamérica 표준 (España와 다를 때만 표기)
- 격식/비격식 구분이 필요하면 둘 다
- 발음이 헷갈리는 단어는 [한글 발음] 병기

규칙:
- 단어 하나 → 동의어 2-3개 + 짧은 예문 1개씩
- 문장 → 직역과 자연스러운 의역 둘 다
- 설명은 한국어로 간결하게
"""

# 경로
SCRIPT_DIR = Path(__file__).parent
LOCAL_ENV = SCRIPT_DIR / ".env"
LOGS_DIR = SCRIPT_DIR / "logs"
VOCAB_FILE = LOGS_DIR / "vocab.md"
CONVERSATION_FILE = LOGS_DIR / "conversation.md"
CONFIG_DIR = Path.home() / "Library" / "Application Support" / "VoiceTranslator"
CONFIG_FILE = CONFIG_DIR / "config"

READY_MSG = "🎤 버튼 클릭으로 녹음 / 또는 아래 입력창에 한국어 입력 후 Enter"
RECORDING_MSG = "🔴 녹음 중… (다시 누르면 종료)"
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
        self.recording = False
        self.audio_chunks = []
        self.stream = None
        self.claude = Anthropic(api_key=api_key)

        print(f"[init] Whisper '{WHISPER_MODEL_SIZE}' 로딩 중…")
        self.whisper = WhisperModel(WHISPER_MODEL_SIZE, device="auto", compute_type="int8")
        print("[init] Whisper 로딩 완료")

        # UI
        self.root = tk.Tk()
        self.root.title("Voice Translator — KO → EN / ES")
        self.root.geometry("960x720")
        self.root.minsize(820, 520)

        self.status = tk.Label(
            self.root, text=READY_MSG,
            font=("Helvetica", 13), pady=8,
        )
        self.status.pack()

        # 녹음 버튼 (큰 버튼)
        self.record_btn = tk.Button(
            self.root,
            text="🎤  녹음 시작",
            font=("Helvetica", 15, "bold"),
            command=self.toggle,
            height=2,
        )
        self.record_btn.pack(fill=tk.X, padx=10, pady=(0, 8))

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

        # 텍스트 입력 영역
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        self.entry = tk.Entry(input_frame, font=("Helvetica", 13))
        self.entry.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=4)
        self.entry.bind("<Return>", lambda e: self.submit_text())

        tk.Button(
            input_frame, text="번역 ↵",
            command=self.submit_text,
        ).pack(side=tk.LEFT, padx=(6, 0))

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
            btn_frame, text="🗑️ 화면 비우기",
            command=self.clear_screen,
        ).pack(side=tk.LEFT, padx=4)

        # 시작 시 입력창에 포커스
        self.entry.focus_set()

        # 창 포커스 상태에서 F9 단축키도 지원 (권한 불필요)
        self.root.bind_all("<F9>", lambda e: self.toggle())

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
    def submit_text(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        threading.Thread(target=lambda: self._translate(text), daemon=True).start()

    # ── 음성 녹음 ──
    def toggle(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.recording = True
        self.audio_chunks = []
        self.set_status(RECORDING_MSG)
        self.record_btn.config(text="⏹  녹음 종료 (클릭)")

        def cb(indata, frames, time_info, status):
            if self.recording:
                self.audio_chunks.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=cb
        )
        self.stream.start()

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.set_status("⏳ 음성 인식 중…")
        self.record_btn.config(text="🎤  녹음 시작")
        threading.Thread(target=self.process_voice, daemon=True).start()

    def process_voice(self):
        """녹음된 음성을 Whisper로 인식한 뒤 번역 호출"""
        if not self.audio_chunks:
            self.set_status(READY_MSG)
            return

        audio = np.concatenate(self.audio_chunks, axis=0).flatten().astype(np.float32)

        segments, _info = self.whisper.transcribe(
            audio, language="ko", beam_size=5, vad_filter=True
        )
        ko_text = " ".join(s.text for s in segments).strip()

        if not ko_text:
            self.set_status("⚠️  음성을 인식하지 못했습니다.")
            return

        self._translate(ko_text)

    # ── 공통 번역 로직 (음성/텍스트 모두 사용) ──
    def _translate(self, ko_text: str):
        self.append(f"\n▶ 입력: {ko_text}\n\n")
        self.set_status("🤖 Claude 호출 중…")

        try:
            msg = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": ko_text}],
            )
            response = "".join(b.text for b in msg.content if b.type == "text")
            self.append(f"{response}\n{'─' * 70}\n")
            self.save_to_log(ko_text, response)
        except Exception as e:
            self.append(f"[오류] {e}\n")

        self.set_status(READY_MSG)

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

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    key = load_api_key()
    if not key:
        show_config_error()
        sys.exit(1)
    VoiceTranslator(key).run()