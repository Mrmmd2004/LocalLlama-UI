"""
8AI - modern local-LLM chat UI for llama.cpp (llama-server)
English (default) + Persian (RTL), chat history, drag & drop files.

    pip install PyQt6            (optional for PDF files: pip install pypdf)
    python 8ai.py
"""
import sys, os, re, json, html, base64, zipfile, mimetypes, time, uuid, shlex, subprocess
import urllib.request, urllib.error
import socket, faulthandler, traceback, threading

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QProcess, QTimer, QUrl, QRectF, QPointF, QSize
from PyQt6.QtGui import (QTextOption, QKeyEvent, QGuiApplication, QPalette, QColor, QIcon, QFontMetrics,
                         QSyntaxHighlighter, QTextCharFormat, QFont, QDesktopServices,
                         QPainter, QPixmap, QPen, QPainterPath, QTextDocument)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QPlainTextEdit, QTextBrowser, QLabel, QSpinBox,
    QDoubleSpinBox, QFileDialog, QListWidget, QListWidgetItem, QMessageBox,
    QFrame, QToolButton, QScrollArea, QDialog, QComboBox, QMenu, QInputDialog,
    QSizePolicy, QAbstractItemView, QCheckBox, QStackedWidget,
)

APP_NAME = "8AI"
APP_VERSION = "2.8.1"
# folder of the running app (works for python 8ai.py and for the PyInstaller exe)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
# bundled read-only resources (icon): PyInstaller unpacks them to sys._MEIPASS
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
# portable mode: a "portable.flag" file next to the exe (portable zip), or the single-file portable exe
# (it carries "portable_exe.flag" inside), keeps settings + chats in <app>\data next to the exe
PORTABLE = (os.path.exists(os.path.join(APP_DIR, "portable.flag"))
            or os.path.exists(os.path.join(RES_DIR, "portable_exe.flag")))
DATA_DIR = os.path.join(APP_DIR, "data") if PORTABLE else os.path.join(os.path.expanduser("~"), ".8ai")
# llama.cpp shipped with the app: "llama" folder next to the exe, else the one packed inside the single exe
BUNDLED_LLAMA = next((d for d in (os.path.join(APP_DIR, "llama"), os.path.join(RES_DIR, "llama"))
                      if os.path.isfile(os.path.join(d, "llama-server.exe"))), os.path.join(APP_DIR, "llama"))
ICON_PATH = next((os.path.join(d, "icon.ico") for d in (RES_DIR, APP_DIR, os.path.join(APP_DIR, "_internal"))
                  if os.path.isfile(os.path.join(d, "icon.ico"))), "")
CHAT_DIR = os.path.join(DATA_DIR, "chats")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
OLD_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".8ai.json")

# ---- crash guard: PyQt6 kills the whole app silently when a slot raises and sys.excepthook is the default.
# Install our own hook (log + red banner instead of closing) and a faulthandler for real native crashes.
CRASH_LOG = os.path.join(DATA_DIR, "crash.log")
_MAIN = [None]
_CRASH_FH = []


def _log_crash(text):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write("\n=== %s  8AI %s ===\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), APP_VERSION, text))
    except Exception:
        pass


def install_crash_guard():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        fh = open(CRASH_LOG, "a", encoding="utf-8")
        _CRASH_FH.append(fh)
        faulthandler.enable(file=fh, all_threads=True)
    except Exception:
        pass

    def hook(et, ev, tb):
        txt = "".join(traceback.format_exception(et, ev, tb))
        _log_crash(txt)
        w = _MAIN[0]
        if w is not None:
            try:
                QTimer.singleShot(0, lambda: w.show_error("Internal error (saved to %s): %s: %s" % (CRASH_LOG, et.__name__, ev)))
            except Exception:
                pass
    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)


TEXT_EXT = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".tsv", ".html", ".htm",
    ".css", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".log", ".c", ".cpp", ".h",
    ".java", ".cs", ".go", ".rs", ".sql", ".sh", ".bat", ".srt", ".tex",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_CHARS = 200_000

# llama-server sampling parameters. Only the ones you set are sent with a request; the others stay at the
# model's / server's own defaults.   key, kind, lowest valid value, highest, step, decimals
SAMPLING = [
    ("top_k", "int", 0, 1000, 1, 0),
    ("top_p", "float", 0.0, 1.0, 0.01, 2),
    ("min_p", "float", 0.0, 1.0, 0.01, 2),
    ("typical_p", "float", 0.0, 1.0, 0.01, 2),
    ("repeat_penalty", "float", 0.5, 2.0, 0.01, 2),
    ("repeat_last_n", "int", -1, 65536, 16, 0),
    ("presence_penalty", "float", -2.0, 2.0, 0.1, 1),
    ("frequency_penalty", "float", -2.0, 2.0, 0.1, 1),
    ("mirostat", "int", 0, 2, 1, 0),
    ("mirostat_tau", "float", 0.0, 20.0, 0.5, 1),
    ("mirostat_eta", "float", 0.0, 1.0, 0.01, 2),
    ("dry_multiplier", "float", 0.0, 5.0, 0.1, 1),
    ("xtc_probability", "float", 0.0, 1.0, 0.05, 2),
    ("seed", "int", -1, 2147483647, 1, 0),
]
PRESETS = {
    "default": {"temp": 0.7},
    "precise": {"temp": 0.2, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "repeat_penalty": 1.05},
    "balanced": {"temp": 0.7, "top_p": 0.95, "top_k": 40, "min_p": 0.05},
    "creative": {"temp": 1.0, "top_p": 0.98, "top_k": 80, "min_p": 0.02, "repeat_penalty": 1.1},
}
SHOW_STATS = True

# ------------------------------------------------------------------ i18n
LANG = "en"
TR = {
    "en": {
        "new_chat": "New chat", "search": "Search chats…", "settings": "Settings",
        "start_model": "Start model", "stop_model": "Stop model",
        "st_stopped": "Model stopped", "st_loading": "Loading model…",
        "st_ready": "Ready", "st_error": "Failed to start",
        "placeholder": "Message 8AI…   (Enter to send · Shift+Enter for new line)",
        "attach": "Attach files", "you": "You", "copy": "Copy", "copied": "Copied ✓",
        "welcome_title": "How can I help you today?",
        "welcome_sub": "Start the model, then chat. Drag & drop documents, code, PDFs or images anywhere.",
        "drop_here": "Drop files here", "rename": "Rename", "delete": "Delete",
        "export": "Export as Markdown", "rename_label": "Chat title:",
        "delete_confirm": "Delete this chat permanently?",
        "delete_all": "Delete all history", "open_web": "Open web page (llama-server)", "web_need_model": "Start the model first.", "save_file": "Save as file", "delete_all_confirm": "Delete ALL chats permanently? This cannot be undone.",
        "need_model": "Start the model first and wait until it is ready.",
        "no_server": "llama-server.exe not found. Choose the llama.cpp folder or zip in Settings.",
        "no_model": "Choose a GGUF model in Settings.",
        "unsupported": "Unsupported file type.",
        "pdf_needs": "Install pypdf to read PDFs:  pip install pypdf",
        "need_mmproj": "Images need a vision model plus its mmproj file (set it in Settings).",
        "truncated": "(truncated)", "file_label": "File",
        "describe_image": "Describe this image.",
        "untitled": "New chat", "extracting": "Extracting zip…",
        "default_sys": "You are a helpful assistant.",
        "language": "Language", "theme": "Theme",
        "theme_dark": "Dark", "theme_light": "Light",
        "llama_path": "llama.cpp (folder or zip)", "model": "Model (GGUF)",
        "mmproj": "mmproj (vision, optional)", "ctx": "Context length",
        "threads": "Threads", "port": "Port",
        "temp": "Temperature", "sys_prompt": "System prompt",
        "save": "Save", "cancel": "Cancel", "browse": "Browse…",
        "restart_note": "Restart the model to apply engine changes.",
        "model_selected": "Model selected: {name}",
        "server_crashed": "llama-server stopped unexpectedly.",
        "st_files": "Attaching {n} file(s) to your message",
        "st_send": "Sending your message to the model",
        "st_prompt": "Reading your prompt ({pct}%)",
        "st_wait": "Processing your message",
        "st_think": "Thinking", "st_write": "Writing the answer",
        "thought": "Thought process",
        "llama_folder": "Folder…", "llama_zip": "Zip…",
        "llama_ok": "✓ llama-server.exe found: {path}",
        "llama_bad": "✗ llama-server.exe not found in this path",
        "models_dir": "Models folder (all subfolders are scanned)",
        "models_found": "{n} model(s) found",
        "models_none": "No GGUF model found in this folder",
        "scanning": "Scanning…",
        "models_btn": "Models", "models_btn_tip": "Choose a model from your models folder",
        "models_title": "Choose a model", "models_search": "Search models…",
        "models_rescan": "Rescan", "models_folder": "Change folder…",
        "models_use": "Use this model", "models_empty": "No models yet — choose your models folder.",
        "models_no_dir": "Models folder not set. Choose it now?",
        "models_missing_dir": "The models folder no longer exists.",
        "restart_ask": "The model is running. Restart it with “{name}”?",
        "model_none": "No model",
        "mmproj_auto": "Vision file (mmproj) found next to the model and selected: {name}",
        "version": "Version",
        "download": "Download:",
        "scroll_down": "Scroll to latest message", "toggle_sidebar": "Show / hide chats",
        "auto_start": "Starting the model… your message will be sent as soon as it is ready (press ■ to cancel).",
        "opt_autoscroll": "Auto-scroll while the answer is being written",
        "opt_autostart": "Start the model automatically when I press Send",
        "opt_autotitle": "Name new chats automatically (short summary)",
        "font_size": "Text size (pt)", "max_tokens": "Max answer length (tokens, 0 = no limit)",
        "behavior": "Behavior",
        "set_general": "General", "set_engine": "Engine", "set_models": "Models",
        "set_chat": "Chat & answers", "set_behavior": "Behavior", "set_about": "About",
        "sub_general": "Language, theme and text size.",
        "sub_engine": "Where llama.cpp is and how the local server runs.",
        "sub_models": "Where your models are and which one to use.",
        "sub_chat": "How the model answers you.",
        "sub_behavior": "Small automations that make the app more convenient.",
        "sub_about": "Version and project links.",
        "sec_appearance": "Appearance", "sec_llama": "llama.cpp", "sec_server": "Server",
        "sec_mdir": "Models folder", "sec_model": "Active model", "sec_gen": "Generation",
        "sec_sys": "System prompt", "sec_auto": "Automation", "sec_links": "Project",
        "hint_lang": "Interface language. Persian switches the layout to right-to-left.",
        "hint_theme": "Dark or light colors.",
        "hint_font": "Size of the text in chats and menus.",
        "hint_llama": "The extracted folder or the zip of llama.cpp; llama-server.exe is found automatically.",
        "hint_ctx": "How much conversation the model can remember. Higher values use more RAM.",
        "hint_threads": "CPU threads used by the model. About half of your CPU cores is a good start.",
        "hint_port": "Local port used by llama-server (127.0.0.1).",
        "hint_mdir": "Every .gguf file in this folder and its sub-folders is listed.",
        "hint_model": "Pick one from your models folder or type its path.",
        "hint_mmproj": "Only needed for models that can see images.",
        "hint_temp": "Lower = more precise, higher = more creative.",
        "hint_maxtok": "Limits how long an answer can be. 0 means no limit.",
        "hint_sys": "Instructions the model follows in every chat.",
    },
    "fa": {
        "new_chat": "گفتگوی جدید", "search": "جستجو در گفتگوها…", "settings": "تنظیمات",
        "start_model": "اجرای مدل", "stop_model": "توقف مدل",
        "st_stopped": "مدل متوقف است", "st_loading": "در حال بارگذاری مدل…",
        "st_ready": "آماده", "st_error": "اجرا نشد",
        "placeholder": "پیامت را به 8AI بنویس…   (Enter ارسال · Shift+Enter خط جدید)",
        "attach": "پیوست فایل", "you": "شما", "copy": "کپی", "copied": "کپی شد ✓",
        "welcome_title": "امروز چه کمکی از من برمی‌آید؟",
        "welcome_sub": "مدل را اجرا کن و شروع کن. اسناد، کد، PDF یا تصویر را هر جا خواستی بکش و رها کن.",
        "drop_here": "فایل‌ها را اینجا رها کن", "rename": "تغییر نام", "delete": "حذف",
        "export": "خروجی Markdown", "rename_label": "عنوان گفتگو:",
        "delete_confirm": "این گفتگو برای همیشه حذف شود؟",
        "delete_all": "حذف همه تاریخچه", "open_web": "باز کردن صفحه وب (llama-server)", "web_need_model": "اول مدل را اجرا کن.", "save_file": "ذخیره به‌عنوان فایل", "delete_all_confirm": "همه گفتگوها برای همیشه حذف شوند؟ این کار قابل بازگشت نیست.",
        "need_model": "اول مدل را اجرا کن و صبر کن آماده شود.",
        "no_server": "llama-server.exe پیدا نشد. در تنظیمات پوشه یا zip برنامه llama.cpp را انتخاب کن.",
        "no_model": "در تنظیمات یک مدل GGUF انتخاب کن.",
        "unsupported": "نوع فایل پشتیبانی نمی‌شود.",
        "pdf_needs": "برای خواندن PDF دستور  pip install pypdf  را اجرا کنید.",
        "need_mmproj": "برای تصویر به یک مدل بینایی و فایل mmproj آن نیاز است (در تنظیمات).",
        "truncated": "(بریده شده)", "file_label": "فایل",
        "describe_image": "این تصویر را توضیح بده.",
        "untitled": "گفتگوی جدید", "extracting": "در حال استخراج zip…",
        "default_sys": "تو یک دستیار هوشمند فارسی‌زبان هستی.",
        "language": "زبان", "theme": "پوسته",
        "theme_dark": "تیره", "theme_light": "روشن",
        "llama_path": "llama.cpp (پوشه یا zip)", "model": "مدل (GGUF)",
        "mmproj": "mmproj (بینایی، اختیاری)", "ctx": "طول context",
        "threads": "تعداد thread", "port": "پورت",
        "temp": "دما (temperature)", "sys_prompt": "پرامپت سیستم",
        "save": "ذخیره", "cancel": "انصراف", "browse": "انتخاب…",
        "restart_note": "برای اعمال تغییرات موتور، مدل را دوباره اجرا کن.",
        "model_selected": "مدل انتخاب شد: {name}",
        "server_crashed": "llama-server به‌طور ناگهانی متوقف شد.",
        "st_files": "در حال پیوست {n} فایل به پیام",
        "st_send": "در حال ارسال پیام به مدل",
        "st_prompt": "در حال خواندن پرامپت ({pct}%)",
        "st_wait": "در حال پردازش پیام",
        "st_think": "در حال فکر کردن", "st_write": "در حال نوشتن پاسخ",
        "thought": "فرایند فکر کردن",
        "llama_folder": "پوشه…", "llama_zip": "zip…",
        "llama_ok": "✓ llama-server.exe پیدا شد: {path}",
        "llama_bad": "✗ llama-server.exe در این مسیر پیدا نشد",
        "models_dir": "پوشه مدل‌ها (همه زیرپوشه‌ها هم بررسی می‌شوند)",
        "models_found": "{n} مدل پیدا شد",
        "models_none": "هیچ مدل GGUF در این پوشه پیدا نشد",
        "scanning": "در حال جستجو…",
        "models_btn": "مدل‌ها", "models_btn_tip": "انتخاب مدل از پوشه مدل‌ها",
        "models_title": "انتخاب مدل", "models_search": "جستجوی مدل…",
        "models_rescan": "جستجوی دوباره", "models_folder": "تغییر پوشه…",
        "models_use": "استفاده از این مدل", "models_empty": "هنوز مدلی نیست — پوشه مدل‌ها را انتخاب کن.",
        "models_no_dir": "پوشه مدل‌ها تنظیم نشده. الان انتخاب کنی؟",
        "models_missing_dir": "پوشه مدل‌ها دیگر وجود ندارد.",
        "restart_ask": "مدل در حال اجراست. با «{name}» دوباره اجرا شود؟",
        "model_none": "بدون مدل",
        "mmproj_auto": "فایل بینایی (mmproj) کنار مدل پیدا و انتخاب شد: {name}",
        "version": "نسخه",
        "download": "دانلود:",
        "scroll_down": "رفتن به آخرین پیام", "toggle_sidebar": "نمایش / پنهان کردن گفتگوها",
        "auto_start": "در حال اجرای مدل… به‌محض آماده شدن، پیامت ارسال می‌شود (برای لغو ■ را بزن).",
        "opt_autoscroll": "اسکرول خودکار هنگام نوشته شدن پاسخ",
        "opt_autostart": "با زدن ارسال، اگر مدل خاموش بود خودکار اجرا شود",
        "opt_autotitle": "نام‌گذاری خودکار گفتگوهای جدید (خلاصه کوتاه)",
        "font_size": "اندازه متن (pt)", "max_tokens": "حداکثر طول پاسخ (توکن، ۰ = بدون محدودیت)",
        "behavior": "رفتار برنامه",
        "set_general": "عمومی", "set_engine": "موتور", "set_models": "مدل‌ها",
        "set_chat": "گفتگو و پاسخ", "set_behavior": "رفتار برنامه", "set_about": "درباره",
        "sub_general": "زبان، پوسته و اندازه متن.",
        "sub_engine": "محل llama.cpp و نحوه اجرای سرور محلی.",
        "sub_models": "محل مدل‌ها و انتخاب مدل فعال.",
        "sub_chat": "نحوه پاسخ دادن مدل به تو.",
        "sub_behavior": "امکانات خودکار کوچک برای راحتی بیشتر.",
        "sub_about": "نسخه و لینک‌های پروژه.",
        "sec_appearance": "ظاهر", "sec_llama": "llama.cpp", "sec_server": "سرور",
        "sec_mdir": "پوشه مدل‌ها", "sec_model": "مدل فعال", "sec_gen": "تولید پاسخ",
        "sec_sys": "پرامپت سیستم", "sec_auto": "خودکارسازی", "sec_links": "پروژه",
        "hint_lang": "زبان رابط. با فارسی، چیدمان از راست به چپ می‌شود.",
        "hint_theme": "رنگ‌بندی تیره یا روشن.",
        "hint_font": "اندازه متن در گفتگوها و منوها.",
        "hint_llama": "پوشه استخراج‌شده یا zip برنامه llama.cpp؛ llama-server.exe خودکار پیدا می‌شود.",
        "hint_ctx": "مدل چقدر از گفتگو را به یاد می‌آورد. مقدار بیشتر، رم بیشتری مصرف می‌کند.",
        "hint_threads": "تعداد هسته‌های پردازنده برای مدل. حدود نصف هسته‌ها شروع خوبی است.",
        "hint_port": "پورت محلی llama-server (127.0.0.1).",
        "hint_mdir": "همه فایل‌های .gguf این پوشه و زیرپوشه‌هایش لیست می‌شوند.",
        "hint_model": "یکی را از پوشه مدل‌ها انتخاب کن یا مسیرش را بنویس.",
        "hint_mmproj": "فقط برای مدل‌هایی که تصویر می‌بینند لازم است.",
        "hint_temp": "کمتر = دقیق‌تر، بیشتر = خلاق‌تر.",
        "hint_maxtok": "حداکثر طول پاسخ را محدود می‌کند. ۰ یعنی بدون محدودیت.",
        "hint_sys": "دستورالعملی که مدل در همه گفتگوها رعایت می‌کند.",
    },
}


TR["en"].update({'sec_perf': 'Performance & memory', 'sec_extra': 'Model extras', 'sec_sampling': 'Sampling', 'sec_think': 'Thinking', 'sec_struct': 'Output control', 'default_val': 'Default', 'on_val': 'On', 'off_val': 'Off', 'e_batch': 'Batch size', 'h_e_batch': 'Prompt tokens processed at once. Larger reads long prompts faster but uses more RAM.', 'e_ubatch': 'Micro-batch size', 'h_e_ubatch': 'Physical batch size inside the engine. The default is usually fine.', 'e_thrb': 'Prompt-reading threads', 'h_e_thrb': 'Threads used while reading the prompt (default: same as Threads).', 'e_ngl': 'GPU layers', 'h_e_ngl': 'Layers run on the GPU. Only works with a GPU build of llama.cpp (CUDA / Vulkan); the CPU build ignores it.', 'e_par': 'Parallel slots', 'h_e_par': 'How many requests the server can answer at the same time.', 'e_flash': 'Flash attention', 'h_e_flash': 'Faster, lighter attention on supported models. Required for a quantized V cache.', 'e_ck': 'KV cache type (K)', 'e_cv': 'KV cache type (V)', 'h_e_kv': 'q8_0 / q4_0 shrink the memory used by long contexts, with a small quality cost.', 'e_load': 'Model loading mode', 'h_e_load': 'mmap = map the file from disk (default). mlock = keep the model in RAM so it is never swapped out (needs enough free RAM). none = read the whole file into RAM. dio = DirectIO.', 'load_mmap': 'mmap', 'load_mlock': 'mlock (stay in RAM)', 'load_mmap_mlock': 'mmap + mlock', 'load_none': 'none (read fully into RAM)', 'load_dio': 'dio (DirectIO)', 'e_ctxshift': 'Context shift', 'h_e_ctxshift': 'When the context is full, drop the oldest tokens and keep going instead of stopping.', 'e_lora': 'LoRA adapter (.gguf)', 'h_e_lora': 'Optional fine-tune adapter applied on top of the model.', 'e_tpl': 'Chat template', 'h_e_tpl': "Name of a built-in template (e.g. chatml, llama3). Empty = the model's own template.", 'e_tbud': 'Thinking budget (tokens)', 'h_e_tbud': 'Caps how long a thinking model may think. 0 turns thinking off. Default = unlimited.', 'e_args': 'Extra llama-server arguments', 'h_e_args': 'Any other llama-server flag, for example:  --n-cpu-moe 8  --cache-ram 2048', 's_preset': 'Preset', 'h_s_preset': 'Fills Temperature and the sampling values below. Press Save to apply.', 'preset_ph': 'Choose a preset…', 'p_default': 'Server defaults', 'p_precise': 'Precise', 'p_balanced': 'Balanced', 'p_creative': 'Creative', 's_top_k': 'Top-K', 'h_top_k': 'Only the K most likely tokens are considered. 0 = off.', 's_top_p': 'Top-P', 'h_top_p': 'Considers the smallest group of tokens whose probabilities add up to P.', 's_min_p': 'Min-P', 'h_min_p': 'Drops tokens that are less likely than this fraction of the best one.', 's_typical_p': 'Typical-P', 'h_typical_p': 'Prefers tokens with a typical amount of surprise. 1 = off.', 's_repeat_penalty': 'Repeat penalty', 'h_repeat_penalty': 'Above 1 discourages repeating words. 1 = off.', 's_repeat_last_n': 'Repeat window', 'h_repeat_last_n': 'How many recent tokens the repeat penalty looks at. -1 = whole context, 0 = off.', 's_presence_penalty': 'Presence penalty', 'h_presence_penalty': 'Positive values push the model toward new topics.', 's_frequency_penalty': 'Frequency penalty', 'h_frequency_penalty': 'Positive values discourage words that were already used often.', 's_mirostat': 'Mirostat', 'h_mirostat': 'Alternative sampler that keeps the answer at a steady level of surprise. 0 = off, 1 or 2 = version.', 's_mirostat_tau': 'Mirostat target (tau)', 'h_mirostat_tau': 'Target surprise. Lower = more focused.', 's_mirostat_eta': 'Mirostat learning rate (eta)', 'h_mirostat_eta': 'How fast Mirostat adapts.', 's_dry_multiplier': 'DRY repetition penalty', 'h_dry_multiplier': 'Stronger protection against repeated phrases. 0 = off.', 's_xtc_probability': 'XTC probability', 'h_xtc_probability': 'Chance of skipping the top choices to add variety. 0 = off.', 's_seed': 'Seed', 'h_seed': 'A fixed number gives repeatable answers. -1 = random.', 'think_mode': 'Thinking', 'h_think_mode': 'For models that can think (Qwen3, DeepSeek-R1, Gemma…). Default lets the model decide.', 'json_mode': 'Force JSON output', 'h_json_mode': 'The model can only answer with valid JSON.', 'stop_seqs': 'Stop sequences', 'h_stop_seqs': 'Generation stops as soon as one of these appears. One per line.', 'grammar': 'GBNF grammar', 'h_grammar': 'Advanced: restricts the answer to a grammar. Takes priority over JSON mode.', 'extra_json': 'Extra request parameters (JSON)', 'h_extra_json': 'Any other llama-server parameter as a JSON object, for example {"dynatemp_range": 0.5}', 'bad_json': 'Extra request parameters must be a valid JSON object.', 'opt_stats': 'Show speed and token counts under each answer', 'stat_tps': '{v} tok/s', 'stat_tokens': '{n} tokens', 'stat_prompt': 'prompt {n}', 'stat_ctx': 'context {used} / {ctx}', 'stat_used': 'context {used}'})
TR["fa"].update({'sec_perf': 'کارایی و حافظه', 'sec_extra': 'امکانات مدل', 'sec_sampling': 'نمونه\u200cبرداری (Sampling)', 'sec_think': 'تفکر', 'sec_struct': 'کنترل خروجی', 'default_val': 'پیش\u200cفرض', 'on_val': 'روشن', 'off_val': 'خاموش', 'e_batch': 'اندازه batch', 'h_e_batch': 'تعداد توکن\u200cهای پرامپت که هم\u200cزمان پردازش می\u200cشوند. مقدار بیشتر، خواندن پرامپت\u200cهای بلند را سریع\u200cتر می\u200cکند ولی رم بیشتری می\u200cخواهد.', 'e_ubatch': 'اندازه micro-batch', 'h_e_ubatch': 'اندازه batch فیزیکی داخل موتور؛ معمولاً پیش\u200cفرض خوب است.', 'e_thrb': 'thread برای خواندن پرامپت', 'h_e_thrb': 'تعداد thread هنگام پردازش پرامپت (پیش\u200cفرض: همان «تعداد thread»).', 'e_ngl': 'لایه\u200cهای GPU', 'h_e_ngl': 'تعداد لایه\u200cهایی که روی GPU اجرا می\u200cشود. فقط با نسخه GPU برنامه llama.cpp \u200f(CUDA / Vulkan) کار می\u200cکند؛ نسخه CPU آن را نادیده می\u200cگیرد.', 'e_par': 'اسلات\u200cهای موازی', 'h_e_par': 'تعداد درخواست\u200cهایی که سرور هم\u200cزمان پاسخ می\u200cدهد.', 'e_flash': 'Flash attention', 'h_e_flash': 'attention سریع\u200cتر و سبک\u200cتر روی مدل\u200cهای سازگار. برای کش V فشرده\u200cشده لازم است.', 'e_ck': 'نوع کش KV (بخش K)', 'e_cv': 'نوع کش KV (بخش V)', 'h_e_kv': 'q8_0 و q4_0 حافظه مصرفی contextهای بلند را کم می\u200cکنند، با افت کیفیت اندک.', 'e_load': 'روش بارگذاری مدل', 'h_e_load': 'mmap = نگاشت فایل از دیسک (پیش\u200cفرض). mlock = مدل در رم بماند و هرگز به دیسک منتقل نشود (رم آزاد کافی لازم است). none = کل فایل در رم خوانده شود. dio = DirectIO.', 'load_mmap': 'mmap', 'load_mlock': 'mlock (ماندن در رم)', 'load_mmap_mlock': 'mmap + mlock', 'load_none': 'none (خواندن کامل در رم)', 'load_dio': 'dio (DirectIO)', 'e_ctxshift': 'Context shift', 'h_e_ctxshift': 'وقتی context پر شد، قدیمی\u200cترین توکن\u200cها حذف می\u200cشوند و گفتگو ادامه پیدا می\u200cکند.', 'e_lora': 'آداپتور LoRA \u200f(.gguf)', 'h_e_lora': 'آداپتور fine-tune اختیاری که روی مدل اعمال می\u200cشود.', 'e_tpl': 'قالب گفتگو (chat template)', 'h_e_tpl': 'نام یک قالب داخلی (مثل chatml یا llama3). خالی = قالب خود مدل.', 'e_tbud': 'بودجه تفکر (توکن)', 'h_e_tbud': 'حداکثر طول فکر کردن مدل\u200cهای متفکر. ۰ یعنی تفکر خاموش. پیش\u200cفرض = بدون محدودیت.', 'e_args': 'آرگومان\u200cهای اضافه llama-server', 'h_e_args': 'هر پرچم دیگر llama-server، مثلاً:  --n-cpu-moe 8  --cache-ram 2048', 's_preset': 'پیش\u200cتنظیم', 'h_s_preset': 'دما و مقادیر نمونه\u200cبرداری زیر را پر می\u200cکند. برای اعمال، ذخیره را بزن.', 'preset_ph': 'یک پیش\u200cتنظیم انتخاب کن…', 'p_default': 'پیش\u200cفرض سرور', 'p_precise': 'دقیق', 'p_balanced': 'متعادل', 'p_creative': 'خلاق', 's_top_k': 'Top-K', 'h_top_k': 'فقط K توکن محتمل\u200cتر بررسی می\u200cشود. ۰ = خاموش.', 's_top_p': 'Top-P', 'h_top_p': 'کوچک\u200cترین گروه توکن\u200cهایی که مجموع احتمالشان به P برسد بررسی می\u200cشود.', 's_min_p': 'Min-P', 'h_min_p': 'توکن\u200cهایی که از این نسبتِ بهترین گزینه کم\u200cاحتمال\u200cترند حذف می\u200cشوند.', 's_typical_p': 'Typical-P', 'h_typical_p': 'توکن\u200cهایی با میزان «غافلگیری» معمول را ترجیح می\u200cدهد. ۱ = خاموش.', 's_repeat_penalty': 'جریمه تکرار', 'h_repeat_penalty': 'بیشتر از ۱ جلوی تکرار کلمات را می\u200cگیرد. ۱ = خاموش.', 's_repeat_last_n': 'پنجره تکرار', 'h_repeat_last_n': 'جریمه تکرار به چند توکن اخیر نگاه کند. -1 = کل context، ۰ = خاموش.', 's_presence_penalty': 'جریمه حضور', 'h_presence_penalty': 'مقدار مثبت، مدل را به سمت موضوعات تازه می\u200cبرد.', 's_frequency_penalty': 'جریمه فراوانی', 'h_frequency_penalty': 'مقدار مثبت، کلماتی را که زیاد استفاده شده\u200cاند کمتر می\u200cکند.', 's_mirostat': 'Mirostat', 'h_mirostat': 'نمونه\u200cبردار جایگزین که میزان غافلگیری پاسخ را ثابت نگه می\u200cدارد. ۰ = خاموش، ۱ یا ۲ = نسخه.', 's_mirostat_tau': 'هدف Mirostat (tau)', 'h_mirostat_tau': 'میزان غافلگیری هدف. کمتر = متمرکزتر.', 's_mirostat_eta': 'نرخ یادگیری Mirostat (eta)', 'h_mirostat_eta': 'سرعت تطبیق Mirostat.', 's_dry_multiplier': 'جریمه تکرار DRY', 'h_dry_multiplier': 'محافظت قوی\u200cتر در برابر تکرار عبارت\u200cها. ۰ = خاموش.', 's_xtc_probability': 'احتمال XTC', 'h_xtc_probability': 'احتمال کنار گذاشتن گزینه\u200cهای برتر برای تنوع بیشتر. ۰ = خاموش.', 's_seed': 'Seed', 'h_seed': 'عدد ثابت = پاسخ\u200cهای تکرارپذیر. -1 = تصادفی.', 'think_mode': 'تفکر', 'h_think_mode': 'برای مدل\u200cهایی که می\u200cتوانند فکر کنند (Qwen3، DeepSeek-R1، Gemma و…). پیش\u200cفرض یعنی خود مدل تصمیم بگیرد.', 'json_mode': 'اجبار خروجی JSON', 'h_json_mode': 'مدل فقط می\u200cتواند با JSON معتبر پاسخ دهد.', 'stop_seqs': 'رشته\u200cهای توقف', 'h_stop_seqs': 'با دیده شدن هرکدام، تولید پاسخ متوقف می\u200cشود. در هر خط یکی.', 'grammar': 'گرامر GBNF', 'h_grammar': 'پیشرفته: پاسخ را به یک گرامر محدود می\u200cکند. بر حالت JSON اولویت دارد.', 'extra_json': 'پارامترهای اضافه درخواست (JSON)', 'h_extra_json': 'هر پارامتر دیگر llama-server به\u200cصورت یک شیء JSON، مثلاً {"dynatemp_range": 0.5}', 'bad_json': 'پارامترهای اضافه باید یک شیء JSON معتبر باشند.', 'opt_stats': 'نمایش سرعت و تعداد توکن زیر هر پاسخ', 'stat_tps': '{v} توکن بر ثانیه', 'stat_tokens': '{n} توکن', 'stat_prompt': 'پرامپت {n}', 'stat_ctx': 'context \u200f{used} / {ctx}', 'stat_used': 'context \u200f{used}'})
TR["en"]["reset_defaults"] = "Reset to defaults"
TR["en"]["reset_ask"] = "Reset ALL settings to their defaults?\n\nYour language, model, models folder, llama.cpp path and chats are kept. Everything else (engine, sampling, theme, font size...) goes back to the original values."
TR["fa"]["reset_defaults"] = "بازگشت به پیش‌فرض"
TR["fa"]["reset_ask"] = "همه‌ی تنظیمات به حالت اولیه برگردد؟\n\nزبان، مدل، پوشه‌ی مدل‌ها، مسیر llama.cpp و چت‌ها حفظ می‌شوند. بقیه‌ی تنظیمات (موتور، sampling، تم، اندازه‌ی فونت و...) به مقدار اولیه برمی‌گردند."
TR["en"]["model_still_old"] = "The OLD model is still running. Restart the model to use the new one."
TR["fa"]["model_still_old"] = "مدل قبلی هنوز در حال اجراست. برای استفاده از مدل جدید، مدل را دوباره اجرا کن."


def t(key, **kw):
    s = TR.get(LANG, TR["en"]).get(key) or TR["en"].get(key, key)
    return s.format(**kw) if kw else s


# ------------------------------------------------------------------ themes
PALETTES = {
    "dark": dict(
        bg="#0f1115", panel="#14171d", card="#1a1e26", border="#272c36", text="#e8eaed",
        muted="#8b93a1", accent="#6c8cff", user_bg="#232b42", hover="#222733",
        danger="#ef5350", ok="#43c59e", warn="#f0b429", code_bg="#0b0d11",
        code_fg="#e6edf3", overlay="rgba(108,140,255,0.16)", on_accent="#ffffff",
        syn_kw="#c586c0", syn_str="#ce9178", syn_com="#6a9955", syn_num="#b5cea8",
        syn_fn="#dcdcaa", syn_ty="#4ec9b0", syn_bi="#569cd6", syn_dec="#d7ba7d"),
    "light": dict(
        bg="#f5f6f9", panel="#ffffff", card="#ffffff", border="#e1e4ea", text="#1b1f27",
        muted="#6b7280", accent="#4f6df5", user_bg="#e6ecff", hover="#eceff4",
        danger="#d93636", ok="#1f9d78", warn="#b7791f", code_bg="#f0f2f5",
        code_fg="#1b1f27", overlay="rgba(79,109,245,0.12)", on_accent="#ffffff",
        syn_kw="#af00db", syn_str="#a31515", syn_com="#008000", syn_num="#098658",
        syn_fn="#795e26", syn_ty="#267f99", syn_bi="#0000ff", syn_dec="#b5651d"),
}


def build_style(p, pt=10.5):
    return f"""
* {{ font-family: 'Segoe UI Variable','Segoe UI','Vazirmatn','Tahoma'; font-size: {pt}pt; }}
QMainWindow, QDialog, #Central {{ background:{p['bg']}; }}
QWidget {{ color:{p['text']}; }}
#Sidebar {{ background:{p['panel']}; }}
#TopBar {{ background:{p['bg']}; }}
#Logo {{ color:{p['accent']}; font-size:17pt; font-weight:700; }}
#PageTitle {{ font-size:11.5pt; font-weight:600; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit#Plain {{
    background:{p['card']}; border:1px solid {p['border']}; border-radius:10px; padding:7px 10px;
    selection-background-color:{p['accent']}; selection-color:{p['on_accent']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit#Plain:focus {{
    border:1px solid {p['accent']}; }}
QComboBox QAbstractItemView {{ background:{p['card']}; border:1px solid {p['border']};
    selection-background-color:{p['accent']}; selection-color:{p['on_accent']}; }}
QPushButton {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:10px; padding:8px 16px; }}
QPushButton:hover {{ background:{p['hover']}; }}
QPushButton#Primary {{ background:{p['accent']}; color:{p['on_accent']}; border:none; font-weight:600; }}
QPushButton#Primary:hover {{ background:{p['accent']}; }}
QPushButton[danger="true"] {{ background:{p['danger']}; color:white; border:none; }}
QToolButton {{ background:transparent; border:none; border-radius:10px; padding:6px 8px; }}
QToolButton:hover {{ background:{p['hover']}; }}
QListWidget#SettingsNav {{ background:{p['panel']}; border:none; outline:none; border-radius:14px; padding:8px; }}
QListWidget#SettingsNav::item {{ padding:10px 12px; border-radius:10px; margin:2px 0; }}
QListWidget#SettingsNav::item:hover {{ background:{p['hover']}; }}
QListWidget#SettingsNav::item:selected {{ background:{p['overlay']}; color:{p['accent']}; font-weight:600; }}
#SectionTitle {{ font-size:17pt; font-weight:700; }}
#CardTitle {{ color:{p['muted']}; font-size:9pt; font-weight:700; padding-left:4px; }}
#SettingsCard {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:14px; }}
#RowSep {{ background:{p['border']}; border:none; }}
#FieldLabel {{ font-weight:600; }}
#Hint {{ color:{p['muted']}; font-size:9pt; }}
#CodeBlock {{ background:{p['code_bg']}; border:1px solid {p['border']}; border-radius:12px; }}
#CodeHead {{ background:{p['hover']}; border-top-left-radius:11px; border-top-right-radius:11px; border-bottom:1px solid {p['border']}; }}
QPlainTextEdit#CodeText {{ background:transparent; border:none; color:{p['code_fg']}; padding:4px 8px;
    font-family:Consolas,'Cascadia Mono','Courier New',monospace; font-size:10pt; }}
QToolButton#LinkBtn {{ color:{p['accent']}; font-weight:600; padding:2px 6px; border-radius:6px; }}
QToolButton#LinkBtn:hover {{ background:{p['overlay']}; }}
QToolButton#ModelBtn {{ background:{p['hover']}; border-radius:14px; padding:6px 12px; font-size:9.5pt; }}
QToolButton#ModelBtn:hover {{ background:{p['overlay']}; color:{p['accent']}; }}
QToolButton#Send {{ background:{p['accent']}; color:{p['on_accent']}; border-radius:18px;
    min-width:36px; max-width:36px; min-height:36px; max-height:36px; font-size:13pt; font-weight:700; }}
#Composer {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:20px; }}
QPlainTextEdit#InputBox {{ background:transparent; border:none; padding:6px; }}
#UserBubble {{ background:{p['user_bg']}; border-radius:18px; }}
#AiCard {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:18px; }}
#MsgName {{ color:{p['muted']}; font-weight:600; font-size:9pt; }}
#Chip {{ background:{p['hover']}; border-radius:12px; }}
#Err {{ background:{p['danger']}; color:white; border-radius:10px; padding:8px 12px; }}
#Overlay {{ background:{p['overlay']}; border:2px dashed {p['accent']}; border-radius:20px;
    color:{p['accent']}; font-size:17pt; font-weight:600; }}
#Welcome {{ background:transparent; }}
#WelcomeTitle {{ font-size:22pt; font-weight:700; }}
#WelcomeSub {{ color:{p['muted']}; font-size:11pt; }}
#Muted {{ color:{p['muted']}; }}
QListWidget#ChatList {{ background:transparent; border:none; outline:none; }}
QListWidget#ChatList::item {{ padding:10px 12px; border-radius:10px; margin:1px 0; }}
QListWidget#ChatList::item:hover {{ background:{p['hover']}; }}
QListWidget#ChatList::item:selected {{ background:{p['hover']}; color:{p['accent']}; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{p['border']}; border-radius:4px; min-height:30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:transparent; height:8px; }}
QScrollBar::handle:horizontal {{ background:{p['border']}; border-radius:4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QToolButton#ScrollDown {{ background:{p['card']}; color:{p['accent']}; border:1px solid {p['border']};
    border-radius:18px; font-size:14pt; font-weight:700; padding:0; }}
QToolButton#ScrollDown:hover {{ background:{p['accent']}; color:{p['on_accent']}; }}
QMenu {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:8px; padding:4px; }}
QMenu::item {{ padding:7px 18px; border-radius:6px; }}
QMenu::item:selected {{ background:{p['hover']}; }}
QToolTip {{ background:{p['card']}; color:{p['text']}; border:1px solid {p['border']}; }}
"""


# ------------------------------------------------------------------ helpers
def is_rtl(s):
    for ch in s:
        if ch.isalpha():
            return "\u0590" <= ch <= "\u08ff" or "\ufb1d" <= ch <= "\ufeff"
    return False


def render_text(text, p):
    parts = re.split(r"(```.*?(?:```|$))", text, flags=re.S)
    out = []
    for part in parts:
        if part.startswith("```"):
            body = part[3:]
            if body.endswith("```"):
                body = body[:-3]
            if "\n" in body and re.match(r"^\w*$", body.split("\n", 1)[0].strip()):
                body = body.split("\n", 1)[1]
            out.append(
                '<pre dir="ltr" style="white-space:pre-wrap; background-color:%s; color:%s; '
                'font-family:Consolas,monospace; margin:6px 0;">%s</pre>'
                % (p["code_bg"], p["code_fg"], html.escape(body.strip("\n")))
            )
            continue
        for line in part.split("\n"):
            if not line.strip():
                continue
            rtl = is_rtl(line)
            side = "right" if rtl else "left"
            indent = ""
            m_h = re.match(r"^\s*#{1,6}\s+(.*)$", line)
            m_b = re.match(r"^\s*[-*\u2022]\s+(.*)$", line)
            if m_h:
                e = "<b>%s</b>" % html.escape(m_h.group(1))
            else:
                if m_b:
                    line = "\u2022 " + m_b.group(1)
                    indent = "margin-%s:14px;" % side
                e = html.escape(line)
                e = re.sub(r"`([^`]+)`", r'<code style="background-color:%s">\1</code>' % p["code_bg"], e)
                e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
            out.append(
                '<p dir="%s" align="%s" style="margin-top:3px; margin-bottom:3px; %s">%s</p>'
                % ("rtl" if rtl else "ltr", side, indent, e)
            )
    return "".join(out)


def split_blocks(text):
    """Split a message into [("text", str)] and [("code", lang, body)] segments (open fences too, for streaming)."""
    out = []
    for part in re.split(r"(```.*?(?:```|$))", text, flags=re.S):
        if part.startswith("```"):
            body = part[3:]
            if body.endswith("```"):
                body = body[:-3]
            lang = ""
            if "\n" in body:
                first, rest = body.split("\n", 1)
                if re.match(r"^[\w+#.-]*$", first.strip()):
                    lang, body = first.strip(), rest
            elif not part.endswith("```") or len(part) <= 3:
                if re.match(r"^[\w+#.-]*$", body.strip()):
                    lang, body = body.strip(), ""     # fence just opened: "```pyth"
            out.append(("code", lang, body.strip("\n")))
        elif part.strip():
            out.append(("text", part))
    return out


def make_stats(raw, ctx=None):
    """Condense the timings / usage of llama-server's last streamed chunk into a small dict."""
    tm, us = raw.get("tm") or {}, raw.get("us") or {}
    n = int(tm.get("predicted_n") or us.get("completion_tokens") or 0)
    pr = int(tm.get("prompt_n") or us.get("prompt_tokens") or 0)
    st = {"n": n, "prompt": pr}
    if tm.get("predicted_per_second"):
        st["tps"] = round(float(tm["predicted_per_second"]), 1)
    if tm:
        st["used"] = int(tm.get("cache_n") or 0) + pr + n
    elif us.get("total_tokens"):
        st["used"] = int(us["total_tokens"])
    if ctx:
        st["ctx"] = int(ctx)
    return st if (n or pr) else None


def fmt_stats(st):
    if not st:
        return ""
    parts = []
    if st.get("tps"):
        parts.append(t("stat_tps", v=st["tps"]))
    if st.get("n"):
        parts.append(t("stat_tokens", n=st["n"]))
    if st.get("prompt"):
        parts.append(t("stat_prompt", n=st["prompt"]))
    if st.get("used"):
        if st.get("ctx"):
            parts.append(t("stat_ctx", used="{:,}".format(st["used"]), ctx="{:,}".format(st["ctx"])))
        else:
            parts.append(t("stat_used", used="{:,}".format(st["used"])))
    return "  ·  ".join(parts)


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    """Plain-text (tab separated) dump of every sheet of an .xlsx file - no extra library needed."""
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    out = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(x.text or "" for x in si.iter("{%s}t" % ns["m"])))
        titles = []
        if "xl/workbook.xml" in names:
            titles = [sh.get("name") for sh in ET.fromstring(z.read("xl/workbook.xml")).iter("{%s}sheet" % ns["m"])]
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
        for i, n in enumerate(sheets):
            out.append("## " + (titles[i] if i < len(titles) else "Sheet%d" % (i + 1)))
            for row in ET.fromstring(z.read(n)).iter("{%s}row" % ns["m"]):
                cells = []
                for c in row.findall("m:c", ns):
                    idx = _col_index(c.get("r") or "A1")
                    while len(cells) < idx:
                        cells.append("")
                    v = c.find("m:v", ns)
                    if c.get("t") == "s" and v is not None:
                        val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                    elif c.get("t") == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                    else:
                        val = v.text if v is not None and v.text else ""
                    cells.append(val)
                out.append("\t".join(cells).rstrip("\t"))
            out.append("")
    return "\n".join(out)


def read_pptx(path):
    """Text of every slide of a .pptx file (and the speaker notes)."""
    out = []
    with zipfile.ZipFile(path) as z:
        def num(n):
            return int(re.search(r"(\d+)\.xml", n).group(1))
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=num)
        for i, n in enumerate(slides, 1):
            xml = z.read(n).decode("utf-8", "replace")
            xml = re.sub(r"</a:p>", "\n", xml)
            out.append("## Slide %d\n%s" % (i, html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()))
            nn = "ppt/notesSlides/notesSlide%d.xml" % num(n)
            if nn in z.namelist():
                x = re.sub(r"</a:p>", "\n", z.read(nn).decode("utf-8", "replace"))
                note = html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
                if note:
                    out.append("(notes) " + note)
    return "\n\n".join(out)


def read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(t("pdf_needs"))
    return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)


def load_attachment(path):
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext in IMAGE_EXT:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"name": name, "kind": "image", "data": "data:%s;base64,%s" % (mime, b64)}
    if ext == ".docx":
        text = read_docx(path)
    elif ext == ".pdf":
        text = read_pdf(path)
    elif ext == ".xlsx":
        text = read_xlsx(path)
    elif ext == ".pptx":
        text = read_pptx(path)
    else:
        with open(path, "rb") as f:
            raw = f.read(MAX_CHARS * 4)
        if ext not in TEXT_EXT and b"\x00" in raw[:4096]:
            raise RuntimeError(t("unsupported"))
        text = raw.decode("utf-8", "replace")
    return {"name": name, "kind": "text", "data": text[:MAX_CHARS], "truncated": len(text) > MAX_CHARS}


def strip_images(history):
    out = []
    for m in history:
        c = m["content"]
        if isinstance(c, list):
            c = "".join(x.get("text", "") for x in c if x.get("type") == "text") + "\n[image omitted]"
        out.append({"role": m["role"], "content": c})
    return out


def find_server_exe(path, max_depth=3):
    """Return the full path of llama-server.exe for a folder / exe path (searches sub-folders too)."""
    path = (path or "").strip().strip('"')
    if not path:
        return None
    if os.path.isfile(path):
        return path if os.path.basename(path).lower() == "llama-server.exe" else None
    if not os.path.isdir(path):
        return None
    base_depth = path.rstrip("\\/").count(os.sep)
    for dp, dn, fn in os.walk(path):
        if "llama-server.exe" in (f.lower() for f in fn):
            real = next(f for f in fn if f.lower() == "llama-server.exe")
            return os.path.join(dp, real)
        if dp.count(os.sep) - base_depth >= max_depth:
            dn[:] = []
    return None


SHARD_RE = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)


def scan_models(root, should_stop=lambda: False, limit=5000):
    """Walk `root` (and every sub-folder) and return GGUF models + mmproj files.
    Split models (xxx-00001-of-00003.gguf) are listed once, with the summed size."""
    models, mmprojs = [], []
    if not root or not os.path.isdir(root):
        return models, mmprojs
    for dp, dn, fn in os.walk(root):
        if should_stop():
            break
        dn[:] = [d for d in dn if not d.startswith(".") and d.lower() not in ("$recycle.bin", "system volume information")]
        ggufs = [f for f in fn if f.lower().endswith(".gguf")]
        for f in sorted(ggufs, key=str.lower):
            full = os.path.join(dp, f)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if "mmproj" in f.lower():
                mmprojs.append({"path": full, "name": f, "size": size})
                continue
            m = SHARD_RE.search(f)
            if m:
                if int(m.group(1)) != 1:
                    continue                      # only the first shard is loaded by llama.cpp
                prefix = f[: m.start()]
                for g in ggufs:
                    mg = SHARD_RE.search(g)
                    if mg and g != f and g[: mg.start()] == prefix:
                        try:
                            size += os.path.getsize(os.path.join(dp, g))
                        except OSError:
                            pass
            rel = os.path.relpath(dp, root)
            models.append({"path": full, "name": f, "size": size, "folder": "" if rel == "." else rel})
            if len(models) >= limit:
                return models, mmprojs
    models.sort(key=lambda m: (m["folder"].lower(), m["name"].lower()))
    return models, mmprojs


def fmt_size(n):
    return "%.2f GB" % (n / 1073741824) if n >= 1073741824 else "%.0f MB" % (n / 1048576)


_MM_IGNORE = {"gguf", "mmproj", "instruct", "chat", "it", "base", "bf16", "f16", "f32", "fp16", "imatrix",
              "unsloth", "the", "model", "vision", "ud", "thinking"}


def _mm_tokens(name):
    n = name.lower().replace(".gguf", "")
    sizes = set(re.findall(r"(?<![a-z0-9.])[ae]?(\d+(?:\.\d+)?)b(?![a-z])", n.replace("_", "-")))
    words = {w for w in re.split(r"[^a-z0-9]+", n)
             if len(w) >= 3 and w not in _MM_IGNORE and not re.fullmatch(r"(iq|q)\d.*|\d+(\.\d+)?b|\d+", w)}
    return sizes, words


def find_mmproj_for(model_path, mmprojs):
    """Best mmproj for a model: same folder, same model size (7B / 27B ...) and same family.
    Returns None when nothing matches for sure - a wrong mmproj makes llama-server refuse to start."""
    folder = os.path.dirname(model_path)
    same = [m for m in mmprojs if os.path.dirname(m["path"]) == folder]
    if not same:
        return None
    msz, mw = _mm_tokens(os.path.basename(model_path))
    best, best_key = None, None
    for m in same:
        psz, pw = _mm_tokens(m["name"])
        if msz and psz and not (msz & psz):
            continue                                  # different model size -> different n_embd -> will not load
        shared = len(mw & pw)
        size_ok = bool(msz and psz)
        if shared == 0 and not size_ok:
            if len(same) > 1 or pw:
                continue                              # nothing ties it to this model
        key = (-shared, 0 if size_ok else 1, m["size"])
        if best_key is None or key < best_key:
            best, best_key = m, key
    return best["path"] if best else None


def classify_dir(p):
    """A dropped folder is either a llama.cpp folder, a models folder, or neither."""
    if find_server_exe(p, 2):
        return "llama"
    for _dp, _dn, fn in os.walk(p):
        if any(f.lower().endswith(".gguf") for f in fn):
            return "models"
    return None


def load_cfg():
    for path in (CONFIG_PATH, OLD_CONFIG_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return {}


# ------------------------------------------------------------------ workers
class HealthWorker(QThread):
    ready = pyqtSignal(bool)

    def __init__(self, port, timeout=240):
        super().__init__()
        self.port, self.timeout, self._stop = port, timeout, False

    def stop(self):
        self._stop = True

    def run(self):
        t0 = time.time()
        while not self._stop and time.time() - t0 < self.timeout:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/health" % self.port, timeout=2) as r:
                    if r.status == 200:
                        self.ready.emit(True)
                        return
            except Exception:
                pass
            self.msleep(700)
        if not self._stop:
            self.ready.emit(False)


_LIVE_SCANS = set()    # keeps a replaced scanner alive until its thread has really finished


class ScanWorker(QThread):
    found = pyqtSignal(list, list)

    def __init__(self, root):
        super().__init__()
        self.root, self._stop = root, False
        _LIVE_SCANS.add(self)
        self.finished.connect(lambda: _LIVE_SCANS.discard(self))

    def stop(self):
        self._stop = True

    def run(self):
        models, mm = scan_models(self.root, lambda: self._stop)
        if not self._stop:
            self.found.emit(models, mm)


class ChatWorker(QThread):
    chunk = pyqtSignal(str)
    reasoning = pyqtSignal(str)
    progress = pyqtSignal(int)
    connected = pyqtSignal()
    stats = pyqtSignal(dict)
    done = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, port, payload):
        super().__init__()
        self.port, self.payload, self._stop = port, payload, False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:%d/v1/chat/completions" % self.port,
                data=json.dumps(self.payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=900) as r:
                self.connected.emit()
                last_tm = last_us = None
                for raw in r:
                    if self._stop:
                        break
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except ValueError:
                        continue
                    pp = obj.get("prompt_progress")
                    if pp and pp.get("total"):
                        cache = pp.get("cache", 0)
                        denom = max(1, pp["total"] - cache)
                        pct = int(100 * max(0, pp.get("processed", 0) - cache) / denom)
                        self.progress.emit(min(100, pct))
                    if obj.get("timings"):
                        last_tm = obj["timings"]
                    if obj.get("usage"):
                        last_us = obj["usage"]
                    ch = obj.get("choices") or []
                    if ch:
                        delta = ch[0].get("delta") or {}
                        rc = delta.get("reasoning_content")
                        if rc:
                            self.reasoning.emit(rc)
                        piece = delta.get("content")
                        if piece:
                            self.chunk.emit(piece)
            if last_tm or last_us:
                self.stats.emit({"tm": last_tm or {}, "us": last_us or {}})
            self.done.emit()
        except urllib.error.HTTPError as e:
            self.failed.emit("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:500]))
        except Exception as e:
            self.failed.emit(str(e))


TITLE_SYS = (
    "You write short chat titles. Summarize what the user wants in 2 to 6 words, like the title of a chat in a "
    "sidebar (for example: 'Fix Python sorting bug', 'Trip plan for Istanbul'). Use the same language as the "
    "user's request. No quotes, no trailing punctuation, no explanation. Output only the title."
)


def clean_title(s):
    s = re.sub(r"<think>.*?(</think>|$)", "", s or "", flags=re.S).strip()
    line = next((l.strip() for l in s.splitlines() if l.strip()), "")
    line = re.sub(r"^(title|عنوان)\s*[:：]\s*", "", line, flags=re.I)
    line = line.strip(" \t\"'`*#«»“”‘’.:؛;،,-–—")
    line = re.sub(r"\s+", " ", line)
    if len(line) > 48:
        cut = line[:48]
        line = (cut.rsplit(" ", 1)[0] if " " in cut else cut) + "…"
    return line


_LIVE_TITLES = set()


class TitleWorker(QThread):
    """Asks the running model for a short chat title (one small non-streaming request)."""
    got = pyqtSignal(str, str)

    def __init__(self, port, cid, user_text, ai_text):
        super().__init__()
        self.port, self.cid, self.user_text, self.ai_text = port, cid, user_text, ai_text
        _LIVE_TITLES.add(self)
        self.finished.connect(lambda: _LIVE_TITLES.discard(self))

    def run(self):
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": TITLE_SYS},
                    {"role": "user", "content": "User request:\n%s\n\nAssistant reply (beginning):\n%s\n\nTitle:"
                                                % (self.user_text, self.ai_text)},
                ],
                "stream": False, "temperature": 0.3, "max_tokens": 200,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            req = urllib.request.Request(
                "http://127.0.0.1:%d/v1/chat/completions" % self.port,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
            msg = ((obj.get("choices") or [{}])[0].get("message")) or {}
            title = clean_title(msg.get("content") or "")
            if title:
                self.got.emit(self.cid, title)
        except Exception:
            pass


# ------------------------------------------------------------------ widgets
class InputBox(QPlainTextEdit):
    send = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("InputBox")
        self.setAcceptDrops(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._rtl = None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.textChanged.connect(self._on_change)
        # re-measure after Qt has really laid out the (wrapped) text, not just when the text changes
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._autosize())
        self.refresh_direction()
        self._autosize()

    def refresh_direction(self):
        self._rtl = None
        self._on_change()

    def _on_change(self):
        txt = self.toPlainText()
        rtl = is_rtl(txt) if txt.strip() else (LANG == "fa")
        if rtl != self._rtl:
            self._rtl = rtl
            opt = QTextOption()
            opt.setTextDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
            opt.setAlignment(Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
            self.document().setDefaultTextOption(opt)
        self._autosize()

    def _autosize(self):
        lines = max(1, int(round(self.document().size().height())))   # wrapped lines too
        pad = int(self.document().documentMargin() * 2) + 12 + 4        # doc margins + CSS padding + slack
        cap = max(140, min(360, int(self.window().height() * 0.40)))    # beyond this it scrolls
        h = min(cap, max(40, lines * self.fontMetrics().lineSpacing() + pad))
        if h != self.height():
            self.setFixedHeight(h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._autosize()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send.emit()
            return
        super().keyPressEvent(e)


class Body(QTextBrowser):
    """Rich-text body that grows to fit its content."""

    def __init__(self, pal):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenExternalLinks(True)
        self.setAcceptDrops(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background:transparent; border:none;")
        self.document().setDocumentMargin(0)
        self.document().setDefaultStyleSheet(
            "p, b, div, span { color:%s; } code { background-color:%s; }" % (pal["text"], pal["code_bg"])
        )
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.setFixedHeight(24)

    def _fit(self, *_):
        h = int(self.document().size().height()) + 4
        if h != self.height():
            self.setFixedHeight(h)

    def refit(self):
        """Make the text layout width equal the real widget width again (fixes text pushed out of view)."""
        w = self.viewport().width()
        if w > 0:
            self.document().setTextWidth(w)
        self._fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.document().setTextWidth(self.viewport().width())
        self._fit()


LINK_LLAMA = ("llama.cpp (GitHub)", "https://github.com/ggml-org/llama.cpp")
LINK_HF = ("Hugging Face", "https://huggingface.co/")
LINK_GEMMA = ("Gemma 3 1B (GGUF)", "https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main")


def link_row(*links):
    """A row of clickable download links: '⬇ Download:  [llama.cpp (GitHub)]  [Hugging Face]'."""
    w = QWidget()
    l = QHBoxLayout(w)
    l.setContentsMargins(0, 0, 0, 0)
    l.setSpacing(2)
    lb = QLabel("⬇  " + t("download"))
    lb.setObjectName("Muted")
    l.addWidget(lb)
    for name, url in links:
        b = QToolButton()
        b.setObjectName("LinkBtn")
        b.setText(name)
        b.setToolTip(url)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        l.addWidget(b)
    l.addStretch(1)
    return w


_KW_PY = set("""False None True and as assert async await break class continue def del elif else except finally for from
global if import in is lambda nonlocal not or pass raise return try while with yield match case self cls""".split())
_BI_PY = set("""print len range int str float list dict set tuple bool open input type isinstance enumerate zip map filter
sorted sum min max abs round super object Exception ValueError TypeError KeyError""".split())
_KW_C = set("""if else for while do switch case default break continue return goto try catch finally throw throws new delete
class struct union enum interface extends implements namespace using import export from package public private protected
static const final var let function async await yield typeof instanceof in of void int long short char float double
bool boolean byte string unsigned signed auto extern inline virtual override template typename this super null nullptr
true false NULL fn mut impl trait pub use mod match loop where self Self def val fun object func defer go chan map
select range type readonly abstract get set operator sizeof volatile register explicit friend constexpr echo
fmt""".split())
_KW_SH = set("""if then else elif fi for while do done case esac function in return exit export local echo cd ls cat grep sed
awk set unset source alias sudo apt pip npm git mkdir rm cp mv chmod curl wget python python3 node""".split())
_KW_SQL = set("""select from where insert into values update set delete create table alter drop index join inner left right
outer on group by order having limit offset as and or not null is in like distinct union all primary key foreign
references default unique count sum avg min max case when then else end begin commit rollback""".split())
_PY = {"py", "python", "python3", "py3"}
_SH = {"bash", "sh", "shell", "zsh", "powershell", "ps1", "bat", "cmd", "batch", "console"}
_SQL = {"sql", "mysql", "postgres", "sqlite", "psql"}
_MARKUP = {"html", "xml", "svg", "xhtml", "htm", "vue"}


class CodeHighlighter(QSyntaxHighlighter):
    """Small multi-language syntax colouring (keywords, strings, comments, numbers, calls, types)."""

    TOKEN = re.compile(
        r"(?P<bc>/\*)|(?P<tq>\"\"\"|\'\'\')|(?P<lc>//|--|\#)|(?P<str>\"(?:\\.|[^\"\\])*\"?|\'(?:\\.|[^\'\\])*\'?|`[^`]*`?)"
        r"|(?P<num>\b0[xX][0-9a-fA-F_]+\b|\b\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?\b)"
        r"|(?P<dec>@[A-Za-z_][\w.]*)|(?P<var>\$\{?[A-Za-z_]\w*\}?)"
        r"|(?P<tag></?[A-Za-z][\w:-]*|/?>)|(?P<id>[A-Za-z_][\w]*)")

    def __init__(self, doc, pal, lang=""):
        super().__init__(doc)
        self.pal = pal
        self.fmt = {}
        for k, key in (("kw", "syn_kw"), ("str", "syn_str"), ("com", "syn_com"), ("num", "syn_num"),
                       ("fn", "syn_fn"), ("ty", "syn_ty"), ("bi", "syn_bi"), ("dec", "syn_dec")):
            f = QTextCharFormat()
            f.setForeground(QColor(pal[key]))
            if k == "com":
                f.setFontItalic(True)
            self.fmt[k] = f
        self.set_lang(lang, rehighlight=False)

    def set_lang(self, lang, rehighlight=True):
        l = (lang or "").lower()
        self.kind = ("py" if l in _PY else "sh" if l in _SH else "sql" if l in _SQL else
                     "markup" if l in _MARKUP else "json" if l == "json" else "c")
        self.kw = {"py": _KW_PY, "sh": _KW_SH, "sql": _KW_SQL}.get(self.kind, _KW_C)
        if rehighlight:
            self.rehighlight()

    def _set(self, a, b, key):
        self.setFormat(a, b - a, self.fmt[key])

    def highlightBlock(self, text):
        kind = self.kind
        pos, state = 0, self.previousBlockState()
        if state in (1, 2, 3):                       # inside /* */ or triple-quote from earlier line
            end_tok = {1: "*/", 2: '"""', 3: "'''"}[state]
            i = text.find(end_tok)
            key = "com" if state == 1 else "str"
            if i < 0:
                self._set(0, len(text), key)
                self.setCurrentBlockState(state)
                return
            pos = i + len(end_tok)
            self._set(0, pos, key)
        self.setCurrentBlockState(0)
        if kind == "c" and re.match(r"\s*#\s*(include|define|ifdef|ifndef|endif|if|else|pragma|undef)\b", text):
            m = re.match(r"\s*#\s*\w+", text)
            self._set(m.start(), m.end(), "kw")
            pos = max(pos, m.end())
        for m in self.TOKEN.finditer(text, pos):
            g = m.lastgroup
            a, b = m.span()
            tok = m.group()
            if g == "bc":
                if kind in ("sh", "py", "json"):
                    continue
                i = text.find("*/", b)
                if i < 0:
                    self._set(a, len(text), "com")
                    self.setCurrentBlockState(1)
                    return
                self._set(a, i + 2, "com")
                continue
            if g == "tq":
                if kind != "py":
                    continue
                i = text.find(tok, b)
                st = 2 if tok == '"""' else 3
                if i < 0:
                    self._set(a, len(text), "str")
                    self.setCurrentBlockState(st)
                    return
                self._set(a, i + 3, "str")
                continue
            if g == "lc":
                ok = ((tok == "//" and kind in ("c",)) or (tok == "#" and kind in ("py", "sh")) or
                      (tok == "--" and kind == "sql"))
                if ok:
                    self._set(a, len(text), "com")
                    return
                continue
            if g == "str":
                self._set(a, b, "str")
            elif g == "num":
                self._set(a, b, "num")
            elif g == "dec":
                if kind == "py":
                    self._set(a, b, "dec")
            elif g == "var":
                if kind == "sh":
                    self._set(a, b, "bi")
            elif g == "tag":
                if kind == "markup":
                    self._set(a, b, "kw")
            elif g == "id":
                low = tok.lower() if kind == "sql" else tok
                if kind == "markup" or kind == "json":
                    if tok in ("true", "false", "null"):
                        self._set(a, b, "kw")
                    continue
                if low in self.kw:
                    self._set(a, b, "kw")
                elif kind == "py" and tok in _BI_PY:
                    self._set(a, b, "bi")
                elif text[b:b + 1] == "(" or text[b:b + 2] == " (" and kind == "sql" and False:
                    self._set(a, b, "fn")
                elif tok[0].isupper() and len(tok) > 1 and not tok.isupper():
                    self._set(a, b, "ty")


def make_copy_icon(color, done=False, size=18):
    """Icon for the Copy buttons: two overlapping squares (or a check mark right after copying)."""
    dpr = 2.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    qp = QPainter(pm)
    qp.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.5)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    qp.setPen(pen)
    qp.setBrush(Qt.BrushStyle.NoBrush)
    if done:
        path = QPainterPath()
        path.moveTo(QPointF(size * 0.22, size * 0.54))
        path.lineTo(QPointF(size * 0.43, size * 0.74))
        path.lineTo(QPointF(size * 0.80, size * 0.30))
        qp.drawPath(path)
    else:
        w = size * 0.56
        r = size * 0.10
        back = QRectF(size * 0.14, size * 0.14, w, w)           # square behind
        front = QRectF(size * 0.30, size * 0.30, w, w)          # square in front
        bp = QPainterPath()
        bp.addRoundedRect(back, r, r)
        fp = QPainterPath()
        fp.addRoundedRect(front.adjusted(-1.6, -1.6, 1.6, 1.6), r, r)
        qp.drawPath(bp.subtracted(fp))                           # back square minus the part hidden by the front one
        qp.drawRoundedRect(front, r, r)
    qp.end()
    return QIcon(pm)


def style_copy_button(btn, pal):
    btn.setIcon(make_copy_icon(pal["muted"]))
    btn.setIconSize(QSize(18, 18))
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    btn.setToolTip(t("copy"))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)


def flash_copied(btn, pal):
    btn.setIcon(make_copy_icon(pal["ok"], done=True))
    btn.setToolTip(t("copied"))

    def _back():
        try:
            style_copy_button(btn, pal)
        except RuntimeError:          # the message was deleted in the meantime
            pass
    QTimer.singleShot(1400, _back)


class CodeBlock(QFrame):
    """A code box with a language label and a Copy button."""

    def __init__(self, lang, code, pal):
        super().__init__()
        self.setObjectName("CodeBlock")
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName("CodeHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 4, 6, 4)
        self.lb = QLabel()
        self.lb.setObjectName("Muted")
        hl.addWidget(self.lb)
        hl.addStretch(1)
        self.pal = pal
        self.btn = QToolButton()
        style_copy_button(self.btn, pal)
        self.btn.clicked.connect(self.copy_code)
        self.btn_save = QToolButton()
        self.btn_save.setText("\U0001F4BE")
        self.btn_save.setToolTip(t("save_file"))
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_code)
        hl.addWidget(self.btn_save)
        hl.addWidget(self.btn)
        v.addWidget(head)
        self.ed = QPlainTextEdit()
        self.ed.setObjectName("CodeText")
        self.ed.setReadOnly(True)
        self.ed.setFrameShape(QFrame.Shape.NoFrame)
        self.ed.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.ed.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ed.setAcceptDrops(False)
        self.ed.horizontalScrollBar().rangeChanged.connect(lambda *_: self._fit())
        v.addWidget(self.ed)
        self.hl = CodeHighlighter(self.ed.document(), pal, lang)
        self.lang, self.code = None, None
        self.set_code(lang, code)

    def set_code(self, lang, code):
        if lang != self.lang:
            self.lang = lang
            self.lb.setText(lang or "code")
            self.hl.set_lang(lang)
        if code != self.code:
            self.code = code
            self.ed.setPlainText(code)
            self._fit()

    def showEvent(self, e):          # fonts from the stylesheet are only known once the widget is shown
        super().showEvent(e)
        self._fit()
        QTimer.singleShot(0, self._fit)

    def _fit(self):
        lines = max(1, self.ed.document().blockCount())
        bar = 16 if self.ed.horizontalScrollBar().maximum() > 0 else 0
        self.ed.setFixedHeight(lines * self.ed.fontMetrics().lineSpacing() + 22 + bar)

    _LANG_EXT = {"python": "py", "py": "py", "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
                 "json": "json", "html": "html", "css": "css", "xml": "xml", "yaml": "yaml", "yml": "yml",
                 "csv": "csv", "markdown": "md", "md": "md", "bash": "sh", "sh": "sh", "shell": "sh",
                 "bat": "bat", "sql": "sql", "c": "c", "cpp": "cpp", "c++": "cpp", "java": "java",
                 "cs": "cs", "csharp": "cs", "go": "go", "rust": "rs", "rs": "rs", "tex": "tex",
                 "ini": "ini", "text": "txt", "txt": "txt", "php": "php", "ruby": "rb", "lua": "lua",
                 "powershell": "ps1", "svg": "svg", "toml": "toml", "kotlin": "kt", "swift": "swift"}

    def save_code(self):
        ext = self._LANG_EXT.get((self.lang or "").strip().lower(), "txt")
        path, _ = QFileDialog.getSaveFileName(self, t("save_file"), "file." + ext, "*.%s;;*.*" % ext)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.code or "")
        except OSError:
            return
        self.btn_save.setText("\u2713")
        QTimer.singleShot(1400, lambda: self.btn_save.setText("\U0001F4BE"))

    def copy_code(self):
        QGuiApplication.clipboard().setText(self.code or "")
        flash_copied(self.btn, self.pal)


class MessageWidget(QFrame):
    def __init__(self, role, text, files, pal):
        super().__init__()
        if not isinstance(text, str):                 # old / multimodal chats may store a list of parts
            if isinstance(text, list):
                text = "\n".join(x.get("text", "") for x in text if isinstance(x, dict) and x.get("type") == "text")
            else:
                text = "" if text is None else str(text)
        self.role, self.text, self.pal = role, text, pal
        self.setObjectName("UserBubble" if role == "user" else "AiCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(4)

        head = QHBoxLayout()
        self.name = QLabel(t("you") if role == "user" else APP_NAME)
        self.name.setObjectName("MsgName")
        head.addWidget(self.name)
        head.addStretch(1)
        self.btn_copy = QToolButton()                 # Copy button on both your messages and the answers
        style_copy_button(self.btn_copy, pal)
        self.btn_copy.clicked.connect(self.copy_text)
        head.addWidget(self.btn_copy)
        lay.addLayout(head)

        for f in files or []:
            lb = QLabel("\U0001F4CE " + f)
            lb.setObjectName("Muted")
            lb.setWordWrap(True)
            lay.addWidget(lb)

        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.hide()
        lay.addWidget(self.status)

        self.reasoning = ""
        self._think_open = True
        self.think_wrap = QWidget()
        tl = QVBoxLayout(self.think_wrap)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(2)
        self.think_btn = QToolButton()
        self.think_btn.setObjectName("Muted")
        self.think_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.think_btn.clicked.connect(self.toggle_think)
        tl.addWidget(self.think_btn, 0, Qt.AlignmentFlag.AlignLeading)
        self.think_body = Body(dict(pal, text=pal["muted"]))
        tl.addWidget(self.think_body)
        self.think_wrap.hide()
        lay.addWidget(self.think_wrap)

        self.body = QWidget()                 # holds text paragraphs and code boxes
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(8)
        self.segs = []                        # (kind, widget)
        lay.addWidget(self.body)
        self.stats_lb = QLabel()
        self.stats_lb.setObjectName("Muted")
        self.stats_lb.setWordWrap(True)
        self.stats_lb.hide()
        lay.addWidget(self.stats_lb)
        self.set_text(text)

    def set_stats(self, s):
        self.stats_lb.setText(s)
        self.stats_lb.setVisible(bool(s))

    def set_text(self, text):
        self.text = text
        self.body.setVisible(bool(text))
        if not text:
            return
        segs = split_blocks(text)
        kinds = [x[0] for x in segs]
        have = [k for k, _w in self.segs]
        keep = 0
        while keep < min(len(kinds), len(have)) and kinds[keep] == have[keep]:
            keep += 1
        for _k, w in self.segs[keep:]:            # drop widgets whose type changed / no longer exist
            self.body_lay.removeWidget(w)
            w.deleteLater()
        self.segs = self.segs[:keep]
        for i, seg in enumerate(segs):
            if i < keep:
                w = self.segs[i][1]
            else:
                w = Body(self.pal) if seg[0] == "text" else CodeBlock(seg[1], seg[2], self.pal)
                w._last = None
                self.body_lay.addWidget(w)
                self.segs.append((seg[0], w))
            if seg[0] == "text":
                if getattr(w, "_last", None) != seg[1]:
                    w._last = seg[1]
                    w.setHtml(render_text(seg[1], self.pal))
            else:
                w.set_code(seg[1], seg[2])

    def set_status(self, s):
        self.status.setText(s)
        self.status.setVisible(bool(s))

    def set_reasoning(self, text):
        self.reasoning = text
        if not text:
            self.think_wrap.hide()
            return
        self.think_wrap.show()
        self.think_body.setHtml(render_text(text, self.pal))
        self._refresh_think()

    def toggle_think(self):
        self._think_open = not self._think_open
        self._refresh_think()

    def collapse_think(self):
        self._think_open = False
        self._refresh_think()

    def _refresh_think(self):
        self.think_body.setVisible(self._think_open)
        self.think_btn.setText(("▾ " if self._think_open else "▸ ") + t("thought"))

    def copy_text(self):
        QGuiApplication.clipboard().setText(self.text)
        flash_copied(self.btn_copy, self.pal)

    def fit(self, maxw):
        if self.role != "user":
            return
        if any(k == "code" for k, _w in self.segs):
            self.setFixedWidth(int(maxw))
            return
        ideal = 0
        try:
            for _k, w in self.segs:
                doc = QTextDocument()                 # measure on a throw-away document (no clone(): it can crash)
                doc.setDocumentMargin(0)
                doc.setDefaultFont(w.font())
                doc.setHtml(render_text(getattr(w, "_last", None) or "", self.pal))
                doc.setTextWidth(max(50, maxw - 34))
                ideal = max(ideal, doc.idealWidth())
        except Exception:
            ideal = maxw
        self.setFixedWidth(int(max(150, min(maxw, ideal + 44))))   # 150 = room for the name + Copy button
        QTimer.singleShot(0, self._refit_bodies)

    def _refit_bodies(self):
        try:
            for k, w in self.segs:
                if k == "text":
                    w.refit()
        except RuntimeError:          # widget already deleted
            pass


class ChatView(QScrollArea):
    def __init__(self, pal):
        super().__init__()
        self.pal = pal
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAcceptDrops(False)
        self.container = QWidget()
        self.container.setObjectName("Central")
        self.setWidget(self.container)
        outer = QVBoxLayout(self.container)
        outer.setContentsMargins(24, 12, 24, 20)
        self.inner = QWidget()
        self.inner.setMaximumWidth(860)
        self.inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.col = QVBoxLayout(self.inner)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(14)
        crow = QHBoxLayout()           # centred column that grows up to 860 px
        crow.setContentsMargins(0, 0, 0, 0)
        crow.addStretch(1)
        crow.addWidget(self.inner, 100)
        crow.addStretch(1)
        outer.addLayout(crow)
        outer.addStretch(1)
        self.items = []   # (holder, MessageWidget)
        self.welcome = None

        # "stick to bottom": while True the view follows new content (streaming) by itself.
        # It turns False as soon as the user scrolls up, and True again when they come back down.
        self._stick = True
        self._auto = False
        self.autoscroll = True
        self.btn_down = QToolButton(self)
        self.btn_down.setObjectName("ScrollDown")
        self.btn_down.setText("↓")
        self.btn_down.setFixedSize(36, 36)
        self.btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_down.setToolTip(t("scroll_down"))
        self.btn_down.clicked.connect(self.scroll_bottom)
        self.btn_down.hide()
        bar = self.verticalScrollBar()
        bar.rangeChanged.connect(self._on_range)
        bar.valueChanged.connect(self._on_value)

    # ---- scrolling
    def _set_bottom(self):
        bar = self.verticalScrollBar()
        self._auto = True
        bar.setValue(bar.maximum())
        self._auto = False

    def _on_range(self, _lo, _hi):
        if self._stick and self.autoscroll:
            self._set_bottom()
        self._update_btn()

    def _on_value(self, _v):
        if not self._auto:
            self._stick = self.near_bottom()
        self._update_btn()

    def _update_btn(self):
        bar = self.verticalScrollBar()
        self.btn_down.setVisible(bar.maximum() > 0 and bar.value() < bar.maximum() - 80)
        self._place_btn()

    def _place_btn(self):
        b = self.btn_down
        b.move((self.width() - b.width()) // 2, self.height() - b.height() - 14)
        b.raise_()

    def scroll_bottom(self, *_):
        self._stick = True
        self._set_bottom()
        QTimer.singleShot(0, self._set_bottom)      # once more after the layout has settled
        self._update_btn()

    def near_bottom(self, margin=24):
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum() - margin

    # ---- content
    def _drop_welcome(self):
        if self.welcome:
            self.col.removeWidget(self.welcome)
            self.welcome.deleteLater()
            self.welcome = None

    def clear(self):
        for holder, _ in self.items:
            self.col.removeWidget(holder)
            holder.deleteLater()
        self.items = []
        self._drop_welcome()
        self._stick = True

    def show_welcome(self):
        self._drop_welcome()
        w = QWidget()
        w.setObjectName("Welcome")
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 90, 0, 0)
        l.setSpacing(10)
        a = QLabel(APP_NAME)
        a.setObjectName("Logo")
        a.setStyleSheet("font-size:34pt;")          # bigger than the sidebar logo
        a.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b = QLabel(t("welcome_title"))
        b.setObjectName("WelcomeTitle")
        b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b.setWordWrap(True)
        c = QLabel(t("welcome_sub"))
        c.setObjectName("WelcomeSub")
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.setWordWrap(True)
        for x in (a, b, c):
            l.addWidget(x)
        self.welcome = w
        self.col.addWidget(w)

    def max_bubble(self):
        return int(min(self.viewport().width() - 48, 860) * 0.78)

    def add(self, role, text, files=None, stats=None):
        self._drop_welcome()
        m = MessageWidget(role, text, files, self.pal)
        if stats and role != "user" and SHOW_STATS:
            m.set_stats(fmt_stats(stats))
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            holder.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # user bubble stays on the right
            hl.addStretch(1)
            try:
                m.fit(self.max_bubble())
            except Exception:
                _log_crash(traceback.format_exc())
            self._stick = True          # a message you send is always brought into view
        hl.addWidget(m)
        self.col.addWidget(holder)
        self.items.append((holder, m))
        return m

    def remove_last(self, n=1):
        for _ in range(n):
            if self.items:
                holder, _m = self.items.pop()
                self.col.removeWidget(holder)
                holder.deleteLater()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        mb = self.max_bubble()
        for _, m in self.items:
            try:
                m.fit(mb)
            except Exception:
                _log_crash(traceback.format_exc())
        self._place_btn()


class Chip(QFrame):
    removed = pyqtSignal(object)

    def __init__(self, att):
        super().__init__()
        self.att = att
        self.setObjectName("Chip")
        l = QHBoxLayout(self)
        l.setContentsMargins(10, 3, 4, 3)
        l.setSpacing(4)
        name = att["name"] if len(att["name"]) <= 28 else att["name"][:25] + "…"
        l.addWidget(QLabel(("\U0001F5BC " if att["kind"] == "image" else "\U0001F4C4 ") + name))
        x = QToolButton()
        x.setText("✕")
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.clicked.connect(lambda: self.removed.emit(self))
        l.addWidget(x)


class SettingsDialog(QDialog):
    """Settings window like the web apps: a category list on the side and one tidy page per category.
    Every page is made of cards; every card holds rows (title + short explanation + control)."""

    def __init__(self, parent, cfg, recent, scanned=None):
        super().__init__(parent)
        self._scan = None
        self._page_lays = []
        self.reset_all = False
        self.setWindowTitle(t("settings"))
        scr = (parent.screen() if parent is not None else QGuiApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(min(720, int(scr.width() * 0.94)), min(440, int(scr.height() * 0.8)))
        root = QVBoxLayout(self)
        root.setSpacing(12)
        main = QHBoxLayout()
        main.setSpacing(14)
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setFrameShape(QFrame.Shape.NoFrame)
        self.nav.setFixedWidth(190)
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stack = QStackedWidget()
        main.addWidget(self.nav)
        main.addWidget(self.stack, 1)
        root.addLayout(main, 1)

        # ---------------------------------------------------------- General
        lay = self._new_page("set_general", "\u2699", "sub_general")
        card = self._card(lay, "sec_appearance")
        self.cb_lang = QComboBox()
        self.cb_lang.addItem("English", "en")
        self.cb_lang.addItem("فارسی", "fa")
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findData(cfg.get("lang", "en"))))
        self.cb_theme = QComboBox()
        self.cb_theme.addItem(t("theme_dark"), "dark")
        self.cb_theme.addItem(t("theme_light"), "light")
        self.cb_theme.setCurrentIndex(max(0, self.cb_theme.findData(cfg.get("theme", "dark"))))
        self.sp_font = QDoubleSpinBox()
        self.sp_font.setRange(8, 20)
        self.sp_font.setSingleStep(0.5)
        self.sp_font.setDecimals(1)
        self.sp_font.setValue(float(cfg.get("font_pt", 10.5)))
        self._field(card, "language", self.cb_lang, "hint_lang")
        self._field(card, "theme", self.cb_theme, "hint_theme")
        self._field(card, "font_size", self.sp_font, "hint_font")

        # ---------------------------------------------------------- Engine
        lay = self._new_page("set_engine", "\U0001F9E9", "sub_engine")
        card = self._card(lay, "sec_llama")
        self.lb_bin = QLabel()
        self.lb_bin.setObjectName("Muted")
        self.lb_bin.setWordWrap(True)
        self.ed_bin = QLineEdit(cfg.get("bin", ""))
        if os.path.isfile(os.path.join(BUNDLED_LLAMA, "llama-server.exe")):
            self.ed_bin.setPlaceholderText(BUNDLED_LLAMA)
        self.ed_bin.textChanged.connect(self._check_bin)
        bw = QWidget()
        bl = QHBoxLayout(bw)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(self.ed_bin, 1)
        b_fold = QPushButton(t("llama_folder"))
        b_fold.clicked.connect(self._pick_bin_folder)
        b_zip = QPushButton(t("llama_zip"))
        b_zip.clicked.connect(self._pick_bin_zip)
        bl.addWidget(b_fold)
        bl.addWidget(b_zip)
        self._field(card, "llama_path", bw, "hint_llama", wide=True,
                    extra=(self.lb_bin, link_row(LINK_LLAMA)))

        card = self._card(lay, "sec_server")
        self.sp_ctx = QSpinBox()
        self.sp_ctx.setRange(512, 262144)
        self.sp_ctx.setSingleStep(1024)
        self.sp_ctx.setValue(cfg.get("ctx", 8192))
        self.sp_thr = QSpinBox()
        self.sp_thr.setRange(1, 256)
        self.sp_thr.setValue(cfg.get("threads", max(1, (os.cpu_count() or 4) // 2)))
        self.sp_port = QSpinBox()
        self.sp_port.setRange(1024, 65535)
        self.sp_port.setValue(cfg.get("port", 8080))
        self._field(card, "ctx", self.sp_ctx, "hint_ctx")
        self._field(card, "threads", self.sp_thr, "hint_threads")
        self._field(card, "port", self.sp_port, "hint_port")

        card = self._card(lay, "sec_perf")
        self.sp_batch = self._opt_spin("int", 1, 65536, 128, 0, cfg.get("batch"))
        self.sp_ubatch = self._opt_spin("int", 1, 65536, 64, 0, cfg.get("ubatch"))
        self.sp_thrb = self._opt_spin("int", 1, 256, 1, 0, cfg.get("threads_batch"))
        self.sp_ngl = self._opt_spin("int", 0, 999, 1, 0, cfg.get("ngl"))
        self.sp_par = self._opt_spin("int", 1, 64, 1, 0, cfg.get("parallel"))
        self.cb_flash = self._combo([(t("default_val"), ""), (t("on_val"), "on"), (t("off_val"), "off")],
                                    cfg.get("flash_attn", ""))
        kv = [(t("default_val"), ""), ("f16", "f16"), ("q8_0", "q8_0"), ("q4_0", "q4_0")]
        self.cb_ck = self._combo(kv, cfg.get("cache_k", ""))
        self.cb_cv = self._combo(kv, cfg.get("cache_v", ""))
        self.cb_load = self._combo([(t("default_val"), ""), (t("load_mmap"), "mmap"), (t("load_mlock"), "mlock"),
                                    (t("load_mmap_mlock"), "mmap+mlock"), (t("load_none"), "none"),
                                    (t("load_dio"), "dio")], cfg.get("load_mode", ""))
        self.ck_shift = QCheckBox()
        self.ck_shift.setChecked(bool(cfg.get("ctx_shift", False)))
        self._field(card, "e_batch", self.sp_batch, "h_e_batch")
        self._field(card, "e_ubatch", self.sp_ubatch, "h_e_ubatch")
        self._field(card, "e_thrb", self.sp_thrb, "h_e_thrb")
        self._field(card, "e_ngl", self.sp_ngl, "h_e_ngl")
        self._field(card, "e_par", self.sp_par, "h_e_par")
        self._field(card, "e_flash", self.cb_flash, "h_e_flash")
        self._field(card, "e_ck", self.cb_ck, "h_e_kv")
        self._field(card, "e_cv", self.cb_cv)
        self._field(card, "e_load", self.cb_load, "h_e_load")
        self._field(card, "e_ctxshift", self.ck_shift, "h_e_ctxshift")

        card = self._card(lay, "sec_extra")
        self.ed_lora = QLineEdit(cfg.get("lora", ""))
        self.ed_tpl = QLineEdit(cfg.get("chat_template", ""))
        self.sp_tbud = self._opt_spin("int", 0, 262144, 256, 0, cfg.get("think_budget"))
        self.ed_args = QLineEdit(cfg.get("extra_args", ""))
        self._field(card, "e_lora", self._row(self.ed_lora, self._pick_lora), "h_e_lora", wide=True)
        self._field(card, "e_tpl", self.ed_tpl, "h_e_tpl", wide=True)
        self._field(card, "e_tbud", self.sp_tbud, "h_e_tbud")
        self._field(card, "e_args", self.ed_args, "h_e_args", wide=True)
        lay.addWidget(self._note())

        # ---------------------------------------------------------- Models
        lay = self._new_page("set_models", "\U0001F9E0", "sub_models")
        card = self._card(lay, "sec_mdir")
        self.lb_mdir = QLabel()
        self.lb_mdir.setObjectName("Muted")
        self.ed_mdir = QLineEdit(cfg.get("models_dir", ""))
        self.ed_mdir.editingFinished.connect(self._start_scan)
        self._field(card, "models_dir", self._row(self.ed_mdir, self._pick_mdir), "hint_mdir", wide=True,
                    extra=(self.lb_mdir, link_row(LINK_HF, LINK_GEMMA)))

        card = self._card(lay, "sec_model")
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cb_model.setMinimumContentsLength(30)
        self._fill_models(recent, scanned or [])
        self.cb_model.setEditText(cfg.get("model", ""))
        self.ed_mm = QLineEdit(cfg.get("mmproj", ""))
        self._field(card, "model", self._row(self.cb_model, self._pick_model), "hint_model", wide=True)
        self._field(card, "mmproj", self._row(self.ed_mm, self._pick_mm), "hint_mmproj", wide=True)
        lay.addWidget(self._note())

        # ---------------------------------------------------------- Chat & answers
        lay = self._new_page("set_chat", "\U0001F4AC", "sub_chat")
        card = self._card(lay, "sec_gen")
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(0, 2)
        self.sp_temp.setSingleStep(0.1)
        self.sp_temp.setValue(cfg.get("temp", 0.7))
        self.sp_maxtok = QSpinBox()
        self.sp_maxtok.setRange(0, 262144)
        self.sp_maxtok.setSingleStep(256)
        self.sp_maxtok.setValue(int(cfg.get("max_tokens", 0)))
        self._field(card, "temp", self.sp_temp, "hint_temp")
        self._field(card, "max_tokens", self.sp_maxtok, "hint_maxtok")
        card = self._card(lay, "sec_sys")
        self.ed_sys = QPlainTextEdit(cfg.get("system") if cfg.get("system") is not None else t("default_sys"))
        self.ed_sys.setObjectName("Plain")
        self.ed_sys.setFixedHeight(120)
        self._field(card, "sys_prompt", self.ed_sys, "hint_sys", wide=True)

        card = self._card(lay, "sec_sampling")
        self.cb_preset = QComboBox()
        self.cb_preset.addItem(t("preset_ph"), "")
        for k in PRESETS:
            self.cb_preset.addItem(t("p_" + k), k)
        self.cb_preset.activated.connect(self._apply_preset)
        self._field(card, "s_preset", self.cb_preset, "h_s_preset")
        saved = cfg.get("sampling") or {}
        self.sp_s = {}
        for key, kind, lo, hi, step, dec in SAMPLING:
            sp = self._opt_spin(kind, lo, hi, step, dec, saved.get(key))
            self.sp_s[key] = sp
            self._field(card, "s_" + key, sp, "h_" + key)

        card = self._card(lay, "sec_think")
        self.cb_think = self._combo([(t("default_val"), ""), (t("on_val"), "on"), (t("off_val"), "off")],
                                    cfg.get("think_mode", ""))
        self._field(card, "think_mode", self.cb_think, "h_think_mode")

        card = self._card(lay, "sec_struct")
        self.ck_json = QCheckBox()
        self.ck_json.setChecked(bool(cfg.get("json_mode", False)))
        self.ed_stop = QPlainTextEdit(cfg.get("stop", ""))
        self.ed_stop.setObjectName("Plain")
        self.ed_stop.setFixedHeight(70)
        self.ed_grammar = QPlainTextEdit(cfg.get("grammar", ""))
        self.ed_grammar.setObjectName("Plain")
        self.ed_grammar.setFixedHeight(90)
        self.ed_extra = QPlainTextEdit(cfg.get("extra_json", ""))
        self.ed_extra.setObjectName("Plain")
        self.ed_extra.setFixedHeight(70)
        self._field(card, "json_mode", self.ck_json, "h_json_mode")
        self._field(card, "stop_seqs", self.ed_stop, "h_stop_seqs", wide=True)
        self._field(card, "grammar", self.ed_grammar, "h_grammar", wide=True)
        self._field(card, "extra_json", self.ed_extra, "h_extra_json", wide=True)

        # ---------------------------------------------------------- Behavior
        lay = self._new_page("set_behavior", "\u26A1", "sub_behavior")
        card = self._card(lay, "sec_auto")
        self.ck_scroll = QCheckBox()
        self.ck_scroll.setChecked(bool(cfg.get("autoscroll", True)))
        self.ck_start = QCheckBox()
        self.ck_start.setChecked(bool(cfg.get("auto_start", True)))
        self.ck_title = QCheckBox()
        self.ck_title.setChecked(bool(cfg.get("auto_title", True)))
        self._field(card, "opt_autoscroll", self.ck_scroll)
        self._field(card, "opt_autostart", self.ck_start)
        self._field(card, "opt_autotitle", self.ck_title)
        self.ck_stats = QCheckBox()
        self.ck_stats.setChecked(bool(cfg.get("show_stats", True)))
        self._field(card, "opt_stats", self.ck_stats)

        # ---------------------------------------------------------- About
        lay = self._new_page("set_about", "\u2139", "sub_about")
        card = self._card(lay, "sec_links")
        ver = QLabel(APP_VERSION)
        ver.setObjectName("Muted")
        self._field(card, "version", ver)
        for name, url in (("GitHub", "https://github.com/Mrmmd2004"),
                          ("Telegram", "https://t.me/Clubapp8")):
            lb = QToolButton()
            lb.setObjectName("LinkBtn")
            lb.setText({"GitHub": "Mrmmd2004", "Telegram": "@Clubapp8"}[name])
            lb.setToolTip(url)
            lb.setCursor(Qt.CursorShape.PointingHandCursor)
            lb.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            self._field(card, name, lb)

        for pl in self._page_lays:
            pl.addStretch(1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # ---------------------------------------------------------- footer buttons
        row = QHBoxLayout()
        b_reset = QPushButton(t("reset_defaults"))
        b_reset.setAutoDefault(False)
        b_reset.clicked.connect(self._reset_clicked)
        row.addWidget(b_reset)
        row.addStretch(1)
        b_cancel = QPushButton(t("cancel"))
        b_cancel.clicked.connect(self.reject)
        b_save = QPushButton(t("save"))
        b_save.setObjectName("Primary")
        b_save.clicked.connect(self.accept)
        b_save.setDefault(True)
        row.addWidget(b_cancel)
        row.addWidget(b_save)
        root.addLayout(row)

        self._check_bin()
        if self.ed_mdir.text().strip():
            if scanned:
                self.lb_mdir.setText(t("models_found", n=len(scanned)))
            else:
                self._start_scan()
        self.resize(min(900, int(scr.width() * 0.94)), min(640, int(scr.height() * 0.9)))

    # ------------------------------------------------------------ layout helpers
    def _new_page(self, key, icon, sub_key=None):
        """Adds a nav entry + a scrollable page; returns the page's vertical layout."""
        body = QWidget()
        body.setObjectName("Central")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(2, 0, 10, 8)
        lay.setSpacing(10)
        title = QLabel(t(key))
        title.setObjectName("SectionTitle")
        lay.addWidget(title)
        if sub_key:
            sub = QLabel(t(sub_key))
            sub.setObjectName("Muted")
            sub.setWordWrap(True)
            lay.addWidget(sub)
            lay.addSpacing(6)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        sc.setWidget(body)
        self.stack.addWidget(sc)
        self.nav.addItem(QListWidgetItem("%s   %s" % (icon, t(key))))
        self._page_lays.append(lay)
        return lay

    def _card(self, lay, title_key=None):
        """A rounded card (optionally with a small heading above it); returns the card's layout."""
        if title_key:
            h = QLabel(t(title_key))
            h.setObjectName("CardTitle")
            lay.addSpacing(6)
            lay.addWidget(h)
        f = QFrame()
        f.setObjectName("SettingsCard")
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 4, 16, 4)
        v.setSpacing(0)
        lay.addWidget(f)
        return v

    def _field(self, card, label, control, hint_key=None, wide=False, extra=()):
        """One row of a card: title (+ hint) and its control. wide=True puts the control under the text."""
        if card.count():
            sep = QFrame()
            sep.setObjectName("RowSep")
            sep.setFixedHeight(1)
            card.addWidget(sep)
        w = QWidget()
        text = QVBoxLayout()
        text.setSpacing(2)
        lb = QLabel(t(label))
        lb.setObjectName("FieldLabel")
        lb.setWordWrap(True)
        text.addWidget(lb)
        if hint_key:
            hn = QLabel(t(hint_key))
            hn.setObjectName("Hint")
            hn.setWordWrap(True)
            text.addWidget(hn)
        if wide:
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 12, 0, 12)
            l.setSpacing(8)
            l.addLayout(text)
            l.addWidget(control)
            for x in extra:
                l.addWidget(x)
        else:
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 12, 0, 12)
            l.setSpacing(16)
            l.addLayout(text, 1)
            if isinstance(control, (QComboBox, QSpinBox, QDoubleSpinBox)):
                control.setFixedWidth(170)
            l.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        card.addWidget(w)

    def _note(self):
        n = QLabel(t("restart_note"))
        n.setObjectName("Hint")
        n.setWordWrap(True)
        return n

    def _row(self, widget, fn):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(widget, 1)
        b = QPushButton(t("browse"))
        b.clicked.connect(fn)
        l.addWidget(b)
        return w

    def _opt_spin(self, kind, lo, hi, step, dec, cur):
        """A number box whose lowest position reads "Default" and means: do not send this setting."""
        sp = QSpinBox() if kind == "int" else QDoubleSpinBox()
        if kind != "int":
            sp.setDecimals(dec)
        sp.setSingleStep(step)
        sp.setRange(lo - (1 if kind == "int" else step), hi)
        sp.setSpecialValueText(t("default_val"))
        sp.setValue(sp.minimum() if cur is None else cur)
        return sp

    @staticmethod
    def _opt_val(sp):
        if sp.value() <= sp.minimum() + 1e-9:
            return None
        return int(sp.value()) if isinstance(sp, QSpinBox) else round(float(sp.value()), 4)

    @staticmethod
    def _combo(items, cur):
        cb = QComboBox()
        for text, data in items:
            cb.addItem(text, data)
        cb.setCurrentIndex(max(0, cb.findData(cur)))
        return cb

    def _pick_lora(self):
        p, _ = QFileDialog.getOpenFileName(self, t("e_lora"), "", "GGUF (*.gguf)")
        if p:
            self.ed_lora.setText(os.path.normpath(p))

    def _apply_preset(self, i):
        key = self.cb_preset.itemData(i)
        if key:
            P = PRESETS[key]
            self.sp_temp.setValue(P.get("temp", 0.7))
            for k, sp in self.sp_s.items():
                sp.setValue(sp.minimum() if P.get(k) is None else P[k])
        self.cb_preset.setCurrentIndex(0)

    def _reset_clicked(self):
        if QMessageBox.question(self, APP_NAME, t("reset_ask")) == QMessageBox.StandardButton.Yes:
            self.reset_all = True
            QDialog.accept(self)          # skip validation: everything is about to be reset anyway

    def accept(self):
        txt = self.ed_extra.toPlainText().strip()
        if txt:
            try:
                ok = isinstance(json.loads(txt), dict)
            except ValueError:
                ok = False
            if not ok:
                self.nav.setCurrentRow(3)
                QMessageBox.warning(self, APP_NAME, t("bad_json"))
                return
        super().accept()

    def _pick_bin_folder(self):
        p = QFileDialog.getExistingDirectory(self, t("llama_path"), self.ed_bin.text())
        if p:
            self.ed_bin.setText(os.path.normpath(p))

    def _pick_bin_zip(self):
        p, _ = QFileDialog.getOpenFileName(self, t("llama_path"), "", "llama (*.zip)")
        if p:
            self.ed_bin.setText(os.path.normpath(p))

    def _check_bin(self, *_):
        txt = self.ed_bin.text().strip().strip('"') or (
            BUNDLED_LLAMA if os.path.isfile(os.path.join(BUNDLED_LLAMA, "llama-server.exe")) else "")
        if not txt:
            self.lb_bin.setText("")
            return
        if txt.lower().endswith(".zip"):
            self.lb_bin.setText("ZIP" if os.path.isfile(txt) else t("llama_bad"))
            return
        exe = find_server_exe(txt)
        self.lb_bin.setText(t("llama_ok", path=exe) if exe else t("llama_bad"))

    def _fill_models(self, recent, scanned):
        cur = self.cb_model.currentText()
        self.cb_model.clear()
        seen = set()
        for m in list(recent) + [x["path"] for x in scanned]:
            if m not in seen:
                seen.add(m)
                self.cb_model.addItem(m)
        self.cb_model.setEditText(cur)

    def _pick_mdir(self):
        p = QFileDialog.getExistingDirectory(self, t("models_dir"), self.ed_mdir.text())
        if p:
            self.ed_mdir.setText(os.path.normpath(p))
            self._start_scan()

    def _start_scan(self):
        root = self.ed_mdir.text().strip().strip('"')
        if self._scan:
            self._scan.stop()
        if not os.path.isdir(root):
            self.lb_mdir.setText("")
            return
        self.lb_mdir.setText(t("scanning"))
        self._scan = ScanWorker(root)
        self._scan.found.connect(self._on_scan)
        self._scan.start()

    def _on_scan(self, models, _mm):
        self.lb_mdir.setText(t("models_found", n=len(models)) if models else t("models_none"))
        recent = [self.cb_model.itemText(i) for i in range(self.cb_model.count())]
        self._fill_models(recent, models)

    def done(self, r):
        if self._scan:
            self._scan.stop()
            self._scan.wait(1500)
        super().done(r)

    def _pick_model(self):
        start = self.ed_mdir.text().strip() if os.path.isdir(self.ed_mdir.text().strip()) else ""
        p, _ = QFileDialog.getOpenFileName(self, t("model"), start, "GGUF (*.gguf)")
        if p:
            self.cb_model.setEditText(os.path.normpath(p))

    def _pick_mm(self):
        p, _ = QFileDialog.getOpenFileName(self, t("mmproj"), "", "GGUF (*.gguf)")
        if p:
            self.ed_mm.setText(p)

    def values(self):
        return {
            "lang": self.cb_lang.currentData(), "theme": self.cb_theme.currentData(),
            "bin": self.ed_bin.text().strip().strip('"'), "models_dir": self.ed_mdir.text().strip().strip('"'),
            "model": self.cb_model.currentText().strip().strip('"'),
            "mmproj": self.ed_mm.text().strip(), "ctx": self.sp_ctx.value(),
            "threads": self.sp_thr.value(), "port": self.sp_port.value(),
            "temp": self.sp_temp.value(), "system": self.ed_sys.toPlainText(),
            "autoscroll": self.ck_scroll.isChecked(), "auto_start": self.ck_start.isChecked(),
            "auto_title": self.ck_title.isChecked(), "font_pt": self.sp_font.value(),
            "max_tokens": self.sp_maxtok.value(),
            "batch": self._opt_val(self.sp_batch), "ubatch": self._opt_val(self.sp_ubatch),
            "threads_batch": self._opt_val(self.sp_thrb), "ngl": self._opt_val(self.sp_ngl),
            "parallel": self._opt_val(self.sp_par), "flash_attn": self.cb_flash.currentData(),
            "cache_k": self.cb_ck.currentData(), "cache_v": self.cb_cv.currentData(),
            "load_mode": self.cb_load.currentData(),
            "ctx_shift": self.ck_shift.isChecked(), "lora": self.ed_lora.text().strip().strip('"'),
            "chat_template": self.ed_tpl.text().strip(), "think_budget": self._opt_val(self.sp_tbud),
            "extra_args": self.ed_args.text().strip(),
            "sampling": {k: v for k, v in ((k, self._opt_val(sp)) for k, sp in self.sp_s.items()) if v is not None},
            "think_mode": self.cb_think.currentData(), "json_mode": self.ck_json.isChecked(),
            "stop": self.ed_stop.toPlainText(), "grammar": self.ed_grammar.toPlainText().strip(),
            "extra_json": self.ed_extra.toPlainText().strip(), "show_stats": self.ck_stats.isChecked(),
        }


class ModelPicker(QDialog):
    """Lists every GGUF model found in the models folder (and its sub-folders)."""

    def __init__(self, parent, root, models, current):
        super().__init__(parent)
        self.setWindowTitle(t("models_title"))
        scr = (parent.screen() if parent is not None else QGuiApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(min(640, int(scr.width() * 0.94)), min(480, int(scr.height() * 0.85)))
        self.root, self.models, self.current = root, models, current
        self.chosen = None
        self.change_dir = False
        self.rescan = False
        v = QVBoxLayout(self)
        v.setSpacing(10)
        self.lb_dir = QLabel(root or "")
        self.lb_dir.setObjectName("Muted")
        self.lb_dir.setWordWrap(True)
        v.addWidget(self.lb_dir)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("models_search"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.fill)
        v.addWidget(self.search)
        self.lst = QListWidget()
        self.lst.setObjectName("ChatList")
        self.lst.itemDoubleClicked.connect(lambda _i: self.use())
        self.lst.itemSelectionChanged.connect(self._sel)
        v.addWidget(self.lst, 1)
        self.lb_n = QLabel()
        self.lb_n.setObjectName("Muted")
        v.addWidget(self.lb_n)
        v.addWidget(link_row(LINK_HF, LINK_GEMMA))
        row = QHBoxLayout()
        b_dir = QPushButton(t("models_folder"))
        b_dir.clicked.connect(self._on_dir)
        b_scan = QPushButton(t("models_rescan"))
        b_scan.clicked.connect(self._on_scan)
        row.addWidget(b_dir)
        row.addWidget(b_scan)
        row.addStretch(1)
        b_cancel = QPushButton(t("cancel"))
        b_cancel.clicked.connect(self.reject)
        self.b_use = QPushButton(t("models_use"))
        self.b_use.setObjectName("Primary")
        self.b_use.setEnabled(False)
        self.b_use.clicked.connect(self.use)
        row.addWidget(b_cancel)
        row.addWidget(self.b_use)
        v.addLayout(row)
        self.fill()

    def fill(self, *_):
        q = self.search.text().strip().lower()
        self.lst.clear()
        shown = 0
        for m in self.models:
            hay = (m["folder"] + " " + m["name"]).lower()
            if q and q not in hay:
                continue
            title = m["name"][:-5] if m["name"].lower().endswith(".gguf") else m["name"]
            sub = ("📁 " + m["folder"] + "   ·   ") if m["folder"] else ""
            it = QListWidgetItem("%s\n%s%s" % (title, sub, fmt_size(m["size"])))
            it.setData(Qt.ItemDataRole.UserRole, m["path"])
            it.setToolTip(m["path"])
            self.lst.addItem(it)
            if m["path"] == self.current:
                it.setText("✓ " + it.text())
                self.lst.setCurrentItem(it)
            shown += 1
        self.lb_n.setText(t("models_found", n=shown) if shown else t("models_empty"))

    def _sel(self):
        self.b_use.setEnabled(bool(self.lst.selectedItems()))

    def use(self):
        it = self.lst.currentItem()
        if it:
            self.chosen = it.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _on_dir(self):
        self.change_dir = True
        self.accept()

    def _on_scan(self):
        self.rescan = True
        self.accept()


# ------------------------------------------------------------------ main window
class EightAI(QMainWindow):
    def __init__(self):
        super().__init__()
        global LANG, SHOW_STATS
        os.makedirs(CHAT_DIR, exist_ok=True)
        self.cfg = load_cfg()
        LANG = self.cfg.get("lang", "en")
        SHOW_STATS = bool(self.cfg.get("show_stats", True))
        self.pal = PALETTES.get(self.cfg.get("theme", "dark"), PALETTES["dark"])

        self.setWindowTitle(APP_NAME)
        if ICON_PATH:
            self.setWindowIcon(QIcon(ICON_PATH))
        self.models = []          # scanned GGUF models
        self.mmprojs = []         # scanned mmproj files
        self.scan = None
        self.setAcceptDrops(True)
        self._side_user = None     # None = sidebar follows the window width; True/False = user's choice
        self.pending_send = False  # message waiting for the model to finish starting
        self._titling = set()

        self.proc = None
        self.health = None
        self.worker = None
        self.state = "stopped"
        self.server_log = ""
        self.generating = False
        self.ai_text = ""        # final answer (without thinking)
        self.ai_raw = ""         # raw streamed content
        self.ai_reason = ""      # thinking text
        self.ai_reason_stream = ""
        self.ai_widget = None
        self.prompt_pct = None
        self.stage = 0
        self.spin = 0
        self.sent_files = 0
        self.think_collapsed = False
        self.pending_text = ""
        self.chips = []
        self._dirty = False
        self.chats = {}
        self.cur = self.new_chat_obj()
        self.load_all_chats()

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- sidebar
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(260)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 16, 14, 14)
        sl.setSpacing(10)
        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        sl.addWidget(logo)
        self.btn_new = QPushButton()
        self.btn_new.setObjectName("Primary")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self.start_new_chat)
        sl.addWidget(self.btn_new)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh_list())
        sl.addWidget(self.search)
        self.chat_list = QListWidget()
        self.chat_list.setObjectName("ChatList")
        self.chat_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.chat_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.chat_list.setWordWrap(False)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.list_menu)
        self.chat_list.itemClicked.connect(self.on_list_click)
        sl.addWidget(self.chat_list, 1)
        self.btn_delall = QPushButton()
        self.btn_delall.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delall.clicked.connect(self.delete_all_history)
        sl.addWidget(self.btn_delall)

        # ---- main column
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        top = QWidget()
        top.setObjectName("TopBar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(22, 12, 18, 6)
        self.btn_side = QToolButton()
        self.btn_side.setText("☰")
        self.btn_side.setStyleSheet("font-size:14pt;")
        self.btn_side.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_side.clicked.connect(self.toggle_sidebar)
        tl.addWidget(self.btn_side)
        self.btn_new_top = QToolButton()          # shown only while the chat list is hidden
        self.btn_new_top.setObjectName("ModelBtn")
        self.btn_new_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_top.clicked.connect(self.start_new_chat)
        self.btn_new_top.hide()
        tl.addWidget(self.btn_new_top)
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        tl.addWidget(self.title, 1)
        self.pill = QLabel()
        tl.addWidget(self.pill)
        self.btn_server = QPushButton()
        self.btn_server.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_server.clicked.connect(self.toggle_server)
        tl.addWidget(self.btn_server)
        self.btn_web = QToolButton()
        self.btn_web.setText("\U0001F310")
        self.btn_web.setStyleSheet("font-size:14pt;")
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.clicked.connect(self.open_web)
        tl.addWidget(self.btn_web)
        self.btn_settings = QToolButton()
        self.btn_settings.setText("⚙")
        self.btn_settings.setStyleSheet("font-size:14pt;")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        tl.addWidget(self.btn_settings)
        ml.addWidget(top)

        self.view = ChatView(self.pal)
        self.view.autoscroll = bool(self.cfg.get("autoscroll", True))
        ml.addWidget(self.view, 1)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(24, 0, 24, 18)
        bl.setSpacing(8)
        wrap = QWidget()
        wrap.setMaximumWidth(860)
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)

        self.err = QLabel()
        self.err.setObjectName("Err")
        self.err.setWordWrap(True)
        self.err.hide()
        wl.addWidget(self.err)

        self.chip_scroll = QScrollArea()
        self.chip_scroll.setWidgetResizable(True)
        self.chip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chip_scroll.setFixedHeight(46)
        self.chip_scroll.setStyleSheet("background:transparent;")
        self.chip_scroll.setAcceptDrops(False)
        chip_host = QWidget()
        chip_host.setStyleSheet("background:transparent;")
        self.chip_lay = QHBoxLayout(chip_host)
        self.chip_lay.setContentsMargins(2, 4, 2, 4)
        self.chip_lay.addStretch(1)
        self.chip_scroll.setWidget(chip_host)
        self.chip_scroll.hide()
        wl.addWidget(self.chip_scroll)

        comp = QFrame()
        comp.setObjectName("Composer")
        cl = QHBoxLayout(comp)
        cl.setContentsMargins(10, 8, 10, 8)
        self.btn_attach = QToolButton()
        self.btn_attach.setText("\U0001F4CE")
        self.btn_attach.setStyleSheet("font-size:14pt;")
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.clicked.connect(self.pick_files)
        cl.addWidget(self.btn_attach, 0, Qt.AlignmentFlag.AlignBottom)
        self.btn_models = QToolButton()
        self.btn_models.setObjectName("ModelBtn")
        self.btn_models.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_models.clicked.connect(self.open_model_picker)
        cl.addWidget(self.btn_models, 0, Qt.AlignmentFlag.AlignBottom)
        self.inp = InputBox()
        self.inp.send.connect(self.send_message)
        cl.addWidget(self.inp, 1)
        self.btn_send = QToolButton()
        self.btn_send.setObjectName("Send")
        self.btn_send.setText("↑")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self.send_or_stop)
        cl.addWidget(self.btn_send, 0, Qt.AlignmentFlag.AlignBottom)
        wl.addWidget(comp)

        brow = QHBoxLayout()           # centred composer that grows up to 860 px
        brow.setContentsMargins(0, 0, 0, 0)
        brow.addStretch(1)
        brow.addWidget(wrap, 100)
        brow.addStretch(1)
        bl.addLayout(brow)
        ml.addWidget(bottom)

        root.addWidget(side)
        root.addWidget(main, 1)

        self.overlay = QLabel(central)
        self.overlay.setObjectName("Overlay")
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay.hide()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(60)

        QApplication.instance().setStyleSheet(build_style(self.pal, self.font_pt()))
        self.retranslate()
        self.rebuild_chat()
        self.refresh_list()
        self.start_scan()
        self.apply_initial_geometry()

    # ------------------------------------------------------------ window size / sidebar
    def apply_initial_geometry(self):
        """Fit the window to the screen (small monitors) instead of a fixed 1280x820."""
        self.setMinimumSize(480, 400)
        scr = QGuiApplication.primaryScreen()
        if not scr:
            self.resize(1280, 820)
            return
        g = scr.availableGeometry()
        w, h = min(1280, int(g.width() * 0.94)), min(820, int(g.height() * 0.92))
        self.resize(w, h)
        self.move(g.x() + (g.width() - w) // 2, g.y() + (g.height() - h) // 2)
        self._auto_sidebar()
        self._sync_side_ui()

    def _auto_sidebar(self):
        side = getattr(self, "side", None)
        if side is None or self._side_user is not None:
            return
        want = self.width() >= 900
        if want == side.isHidden():
            side.setVisible(want)
        self._sync_side_ui()

    def _sync_side_ui(self):
        """When the chat list is closed, a "New chat" button appears next to the ☰ button."""
        self.btn_new_top.setVisible(self.side.isHidden())

    def toggle_sidebar(self):
        self._side_user = self.side.isHidden()      # hidden -> show, shown -> hide
        self.side.setVisible(self._side_user)
        self._sync_side_ui()

    def _close_sidebar_if_narrow(self):
        if self.width() < 900:           # small window: the chat list closes after you pick a chat
            self._side_user = None
            self.side.setVisible(False)
            self._sync_side_ui()

    # ------------------------------------------------------------ models folder / picker
    def start_scan(self, then=None):
        root = (self.cfg.get("models_dir") or "").strip()
        if self.scan:
            self.scan.stop()
        if not os.path.isdir(root):
            self.models, self.mmprojs = [], []
            return
        self.scan = ScanWorker(root)
        self.scan.found.connect(self._on_scanned)
        if then:
            self.scan.found.connect(lambda *_: then())
        self.scan.start()

    def _on_scanned(self, models, mm):
        self.models, self.mmprojs = models, mm

    def update_model_btn(self):
        m = (self.cfg.get("model") or "").strip()
        name = os.path.basename(m)[:-5] if m.lower().endswith(".gguf") else os.path.basename(m)
        name = name or t("model_none")
        fm = QFontMetrics(self.btn_models.font())
        self.btn_models.setText("\U0001F9E0  " + fm.elidedText(name, Qt.TextElideMode.ElideMiddle, 170))
        self.btn_models.setToolTip((m or t("models_btn_tip")) + "\n" + t("models_btn_tip"))

    def choose_models_dir(self):
        p = QFileDialog.getExistingDirectory(self, t("models_dir"), self.cfg.get("models_dir", ""))
        if not p:
            return False
        self.cfg["models_dir"] = os.path.normpath(p)
        self.save_cfg()
        return True

    def open_model_picker(self):
        root = (self.cfg.get("models_dir") or "").strip()
        if not root:
            if QMessageBox.question(self, APP_NAME, t("models_no_dir")) != QMessageBox.StandardButton.Yes:
                return
            if not self.choose_models_dir():
                return
            self.start_scan(then=self.open_model_picker)
            return
        if not os.path.isdir(root):
            self.show_error(t("models_missing_dir"))
            if not self.choose_models_dir():
                return
            self.start_scan(then=self.open_model_picker)
            return
        dlg = ModelPicker(self, root, self.models, (self.cfg.get("model") or "").strip())
        dlg.exec()
        if dlg.change_dir:
            if self.choose_models_dir():
                self.start_scan(then=self.open_model_picker)
        elif dlg.rescan:
            self.start_scan(then=self.open_model_picker)
        elif dlg.chosen:
            self.select_model(dlg.chosen)

    def select_model(self, path):
        self.cfg["model"] = path
        rec = [m for m in self.cfg.get("recent_models", []) if m != path]
        self.cfg["recent_models"] = ([path] + rec)[:8]
        # a vision projector must match the model: use the one next to it, otherwise clear the old one
        mm = find_mmproj_for(path, self.mmprojs)
        self.cfg["mmproj"] = mm or ""
        self.save_cfg()
        self.update_model_btn()
        self.show_info(t("model_selected", name=os.path.basename(path)))
        if mm:
            QTimer.singleShot(3100, lambda: self.show_info(t("mmproj_auto", name=os.path.basename(mm))))
        if self.proc:
            name = os.path.basename(path)
            if QMessageBox.question(self, APP_NAME, t("restart_ask", name=name)) == QMessageBox.StandardButton.Yes:
                self.restart_server()
            else:
                QTimer.singleShot(3200, lambda: self.show_error(t("model_still_old")))

    # ------------------------------------------------------------ language / theme
    def retranslate(self):
        self.btn_new.setText("＋  " + t("new_chat"))
        self.search.setPlaceholderText(t("search"))
        self.btn_delall.setText("\U0001F5D1  " + t("delete_all"))
        self.btn_settings.setToolTip(t("settings"))
        self.btn_web.setToolTip(t("open_web"))
        self.btn_attach.setToolTip(t("attach"))
        self.btn_side.setToolTip(t("toggle_sidebar"))
        self.btn_new_top.setText("＋  " + t("new_chat"))
        self.view.btn_down.setToolTip(t("scroll_down"))
        self.update_model_btn()
        self.inp.setPlaceholderText(t("placeholder"))
        self.inp.refresh_direction()
        self.overlay.setText("\U0001F4E5  " + t("drop_here"))
        self.update_state_ui()
        self.update_title()

    def apply_settings(self, new):
        global LANG, SHOW_STATS
        old = dict(self.cfg)
        self.cfg.update(new)
        SHOW_STATS = bool(self.cfg.get("show_stats", True))
        LANG = self.cfg.get("lang", "en")
        self.pal = PALETTES.get(self.cfg.get("theme", "dark"), PALETTES["dark"])
        if new["model"]:
            rec = [m for m in self.cfg.get("recent_models", []) if m != new["model"]]
            self.cfg["recent_models"] = ([new["model"]] + rec)[:8]
        self.save_cfg()
        self.view.autoscroll = bool(self.cfg.get("autoscroll", True))
        if (old.get("lang", "en") != LANG or old.get("theme", "dark") != self.cfg.get("theme", "dark")
                or old.get("font_pt", 10.5) != self.cfg.get("font_pt", 10.5)
                or old.get("show_stats", True) != self.cfg.get("show_stats", True)):
            app = QApplication.instance()
            app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if LANG == "fa" else Qt.LayoutDirection.LeftToRight)
            app.setStyleSheet(build_style(self.pal, self.font_pt()))
            self.view.pal = self.pal
            self.retranslate()
            self.rebuild_chat()
            self.refresh_list()

    RESET_KEEP = ("lang", "bin", "models_dir", "model", "mmproj", "recent_models")

    def reset_settings(self):
        """Back to the original settings. Keeps language, model/llama.cpp paths and chats."""
        global LANG, SHOW_STATS
        keep = {k: self.cfg[k] for k in self.RESET_KEEP if k in self.cfg}
        self.cfg.clear()
        self.cfg.update(keep)             # every other key missing -> the program default is used
        self.save_cfg()
        SHOW_STATS = True
        LANG = self.cfg.get("lang", "en")
        self.pal = PALETTES["dark"]
        self.view.autoscroll = True
        app = QApplication.instance()
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if LANG == "fa" else Qt.LayoutDirection.LeftToRight)
        app.setStyleSheet(build_style(self.pal, self.font_pt()))
        self.view.pal = self.pal
        self.retranslate()
        self.rebuild_chat()
        self.refresh_list()

    def font_pt(self):
        try:
            return max(8.0, min(20.0, float(self.cfg.get("font_pt", 10.5))))
        except (TypeError, ValueError):
            return 10.5

    def open_settings(self):
        dlg = SettingsDialog(self, self.cfg, self.cfg.get("recent_models", []), self.models)
        if dlg.exec():
            old_dir = self.cfg.get("models_dir", "")
            before = self._engine_snapshot()
            if dlg.reset_all:
                self.reset_settings()
            else:
                self.apply_settings(dlg.values())
            self.update_model_btn()
            if self.proc and before != self._engine_snapshot():
                name = os.path.basename(self.cfg.get("model", "") or "")
                if QMessageBox.question(self, APP_NAME, t("restart_ask", name=name)) == QMessageBox.StandardButton.Yes:
                    self.restart_server()
                else:
                    QTimer.singleShot(300, lambda: self.show_error(t("model_still_old")))
            if self.cfg.get("models_dir", "") != old_dir or not self.models:
                self.start_scan()

    def save_cfg(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------ chat storage
    @staticmethod
    def new_chat_obj():
        now = time.time()
        return {"id": uuid.uuid4().hex, "title": None, "titled": False, "created": now, "updated": now,
                "history": [], "view": []}

    def load_all_chats(self):
        for fn in os.listdir(CHAT_DIR):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(CHAT_DIR, fn), encoding="utf-8") as f:
                        c = json.load(f)
                    c.setdefault("created", c.get("updated", 0))   # old chats keep their current order
                    c.setdefault("titled", True)
                    self.chats[c["id"]] = c
                except Exception:
                    pass

    def save_current(self, touch=True, refresh=True):
        c = self.cur
        if not c["view"]:
            return
        if touch:
            c["updated"] = time.time()
        if not c["title"]:
            first = next((v for v in c["view"] if v[0] == "user"), None)
            if first:
                c["title"] = (first[1].strip().replace("\n", " ")[:45]
                              or (first[2][0] if first[2] else t("untitled")))
        data = {"id": c["id"], "title": c["title"], "titled": bool(c.get("titled")),
                "created": c.get("created", c["updated"]), "updated": c["updated"],
                "history": strip_images(c["history"]), "view": c["view"]}
        self.chats[c["id"]] = data
        self.persist(data)
        if refresh:
            self.update_title()
            self.refresh_list()

    def persist(self, c):
        try:
            with open(os.path.join(CHAT_DIR, c["id"] + ".json"), "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False)
        except OSError:
            pass

    def refresh_list(self):
        q = self.search.text().strip().lower()
        sb = self.chat_list.verticalScrollBar()
        keep = sb.value()
        self.chat_list.blockSignals(True)
        self.chat_list.clear()
        # order = creation time (newest first): chats never jump around when you open or continue them
        for c in sorted(self.chats.values(), key=lambda x: x.get("created", x.get("updated", 0)), reverse=True):
            title = c.get("title") or t("untitled")
            if q and q not in title.lower() and not any(q in (v[1] or "").lower() for v in c["view"]):
                continue
            it = QListWidgetItem(title)
            it.setData(Qt.ItemDataRole.UserRole, c["id"])
            it.setToolTip(time.strftime("%Y-%m-%d %H:%M", time.localtime(c["updated"])))
            self.chat_list.addItem(it)
            if c["id"] == self.cur["id"]:
                self.chat_list.setCurrentItem(it)
        self.chat_list.blockSignals(False)
        sb.setValue(keep)

    def select_in_list(self):
        """Highlight the current chat without rebuilding (and so without moving) the list."""
        self.chat_list.blockSignals(True)
        for i in range(self.chat_list.count()):
            it = self.chat_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == self.cur["id"]:
                self.chat_list.setCurrentItem(it)
                break
        else:
            self.chat_list.clearSelection()
            self.chat_list.setCurrentRow(-1)
        self.chat_list.blockSignals(False)

    def update_title(self):
        if self.pending_send:
            self.title.setText(t("auto_start"))
            return
        tt = self.cur.get("title") or ("" if not self.cur.get("view") else t("untitled"))
        self.title.setText(tt)
        self.title.setToolTip(tt)

    def maybe_title(self):
        """After the first answer, ask the model for a short summary title (like a chat app does)."""
        c = self.cur
        cid = c["id"]
        if (c.get("titled") or self.state != "ready" or cid in self._titling
                or not self.cfg.get("auto_title", True)):
            return
        first = next((v for v in c["view"] if v[0] == "user"), None)
        ans = next((v for v in c["view"] if v[0] == "assistant"), None)
        if not first or not ans:
            return
        u = (first[1] or "").strip() or ", ".join(first[2] or [])
        self._titling.add(cid)
        w = TitleWorker(self.port, cid, u[:1500], (ans[1] or "")[:600])
        w.got.connect(self.on_title)
        w.finished.connect(lambda cid=cid: self._titling.discard(cid))
        w.start()

    def on_title(self, cid, title):
        c = self.chats.get(cid)
        if not c or c.get("titled"):
            return                       # chat deleted, or already renamed by the user
        c["title"], c["titled"] = title, True
        if self.cur["id"] == cid:
            self.cur["title"], self.cur["titled"] = title, True
        self.persist(c)
        self.update_title()
        self.refresh_list()

    def on_list_click(self, item):
        cid = item.data(Qt.ItemDataRole.UserRole)
        if self.generating or cid == self.cur["id"]:
            return
        self.save_current(touch=False, refresh=False)
        c = self.chats.get(cid)
        if c:
            self.cur = {"id": c["id"], "title": c["title"], "titled": c.get("titled", True),
                        "created": c.get("created", c["updated"]), "updated": c["updated"],
                        "history": list(c["history"]), "view": [list(v) for v in c["view"]]}
            self.rebuild_chat()
            self.update_title()
            self.select_in_list()
            self._close_sidebar_if_narrow()

    def list_menu(self, pos):
        it = self.chat_list.itemAt(pos)
        if not it:
            if self.chats:
                m = QMenu(self)
                a = m.addAction(t("delete_all"))
                if m.exec(self.chat_list.mapToGlobal(pos)) == a:
                    self.delete_all_history()
            return
        cid = it.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        a_ren = menu.addAction(t("rename"))
        a_exp = menu.addAction(t("export"))
        a_del = menu.addAction(t("delete"))
        act = menu.exec(self.chat_list.mapToGlobal(pos))
        c = self.chats.get(cid)
        if not c or act is None:
            return
        if act == a_ren:
            text, ok = QInputDialog.getText(self, t("rename"), t("rename_label"), text=c.get("title") or "")
            if ok and text.strip():
                c["title"], c["titled"] = text.strip(), True
                if cid == self.cur["id"]:
                    self.cur["title"], self.cur["titled"] = c["title"], True
                self.persist(c)
                self.update_title()
                self.refresh_list()
        elif act == a_exp:
            self.export_chat(c)
        elif act == a_del:
            if self.generating and cid == self.cur["id"]:
                return
            if QMessageBox.question(self, APP_NAME, t("delete_confirm")) == QMessageBox.StandardButton.Yes:
                self.chats.pop(cid, None)
                try:
                    os.remove(os.path.join(CHAT_DIR, cid + ".json"))
                except OSError:
                    pass
                if cid == self.cur["id"]:
                    self.cur = self.new_chat_obj()
                    self.rebuild_chat()
                    self.update_title()
                self.refresh_list()

    def delete_all_history(self):
        if self.generating or not self.chats:
            return
        if QMessageBox.question(self, APP_NAME, t("delete_all_confirm")) != QMessageBox.StandardButton.Yes:
            return
        for cid in list(self.chats):
            try:
                os.remove(os.path.join(CHAT_DIR, cid + ".json"))
            except OSError:
                pass
        self.chats.clear()
        self.cur = self.new_chat_obj()
        self.rebuild_chat()
        self.update_title()
        self.refresh_list()

    def export_chat(self, c):
        name = re.sub(r'[\\/:*?"<>|]+', "_", c.get("title") or "chat")
        path, _ = QFileDialog.getSaveFileName(self, t("export"), name + ".md", "Markdown (*.md)")
        if not path:
            return
        lines = ["# " + (c.get("title") or "chat"), ""]
        for item in c["view"]:
            role, text, files = item[:3]
            lines.append("**%s:**" % (t("you") if role == "user" else APP_NAME))
            for f in files or []:
                lines.append("- \U0001F4CE " + f)
            lines += ["", text, ""]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError as e:
            self.show_error(str(e))

    def start_new_chat(self):
        if self.generating:
            return
        self.save_current(touch=False, refresh=False)
        self.cur = self.new_chat_obj()
        self.rebuild_chat()
        self.update_title()
        self.select_in_list()
        self.inp.setFocus()
        self._close_sidebar_if_narrow()

    def rebuild_chat(self):
        self.view.clear()
        if not self.cur["view"]:
            self.view.show_welcome()
        for item in self.cur["view"]:
            self.view.add(item[0], item[1], item[2], item[3] if len(item) > 3 else None)
        QTimer.singleShot(0, self.view.scroll_bottom)

    # ------------------------------------------------------------ attachments / DnD
    def pick_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self, t("attach"))
        for p in ps:
            self.add_attachment(p)

    def add_attachment(self, path):
        try:
            att = load_attachment(path)
        except Exception as ex:
            self.show_error("%s: %s" % (os.path.basename(path), ex))
            return
        chip = Chip(att)
        chip.removed.connect(self.remove_chip)
        self.chip_lay.insertWidget(self.chip_lay.count() - 1, chip)
        self.chips.append(chip)
        self.chip_scroll.show()

    def remove_chip(self, chip):
        if chip in self.chips:
            self.chips.remove(chip)
        self.chip_lay.removeWidget(chip)
        chip.deleteLater()
        if not self.chips:
            self.chip_scroll.hide()

    def clear_chips(self):
        for c in list(self.chips):
            self.remove_chip(c)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self.overlay.setGeometry(self.centralWidget().rect())
            self.overlay.raise_()
            self.overlay.show()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.overlay.hide()

    def dropEvent(self, e):
        self.overlay.hide()
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if not p:
                continue
            low = p.lower()
            if low.endswith(".gguf"):
                if "mmproj" in os.path.basename(low):
                    self.cfg["mmproj"] = p
                    self.save_cfg()
                    self.show_info(t("model_selected", name=os.path.basename(p)))
                else:
                    self.select_model(p)
            elif os.path.isdir(p):
                kind = classify_dir(p)
                if kind == "llama":
                    self.cfg["bin"] = p
                    self.save_cfg()
                    self.show_info(t("llama_ok", path=find_server_exe(p)))
                elif kind == "models":
                    self.cfg["models_dir"] = p
                    self.save_cfg()
                    self.start_scan(then=self.open_model_picker)
            elif low.endswith(".zip") and "llama" in os.path.basename(low):
                self.cfg["bin"] = p
                self.save_cfg()
            else:
                self.add_attachment(p)
        e.acceptProposedAction()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.centralWidget().rect())
        self._auto_sidebar()
        if hasattr(self, "inp"):
            self.inp._autosize()

    # ------------------------------------------------------------ banners
    def show_error(self, msg):
        self.err.setText("⚠  " + msg)
        self.err.show()
        QTimer.singleShot(9000, self.err.hide)

    def show_info(self, msg):
        self.title.setText(msg)
        QTimer.singleShot(3000, self.update_title)

    def set_pending(self, on):
        """A message is waiting for the model to start: the send button becomes a cancel (■)."""
        self.pending_send = on
        self.btn_send.setText("■" if (on or self.generating) else "↑")
        self.update_title()

    # ------------------------------------------------------------ server
    def resolve_server_exe(self):
        p = (self.cfg.get("bin") or "").strip().strip('"')
        if not p and os.path.isfile(os.path.join(BUNDLED_LLAMA, "llama-server.exe")):
            p = BUNDLED_LLAMA          # llama.cpp shipped with the installer / portable build
        if not p:
            return None
        if p.lower().endswith(".zip") and os.path.isfile(p):
            dest = os.path.join(DATA_DIR, "llama")
            if not find_server_exe(dest):
                self.show_info(t("extracting"))
                QApplication.processEvents()
                try:
                    with zipfile.ZipFile(p) as z:
                        z.extractall(dest)
                except (OSError, zipfile.BadZipFile):
                    return None
            self.cfg["bin"] = dest
            self.save_cfg()
            p = dest
        return find_server_exe(p)

    @property
    def port(self):
        rp = getattr(self, "_run_port", None)
        if rp and self.proc is not None:
            return rp
        return int(self.cfg.get("port", 8080))

    @staticmethod
    def _port_in_use(port):
        """True if something (e.g. an old llama-server left over from a crash) already listens on the port."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
                sk.settimeout(0.4)
                return sk.connect_ex(("127.0.0.1", int(port))) == 0
        except OSError:
            return False

    def effective_threads(self):
        return max(1, int(self.cfg.get("threads", max(1, (os.cpu_count() or 4) // 2))))

    def _free_port(self):
        base = int(self.cfg.get("port", 8080))
        for p in range(base, base + 60):
            if not self._port_in_use(p):
                return p
        return base

    ENGINE_KEYS = ("model", "mmproj", "bin", "ctx", "threads", "port", "batch", "ubatch", "threads_batch",
                   "parallel", "ngl", "flash_attn", "cache_k", "cache_v", "load_mode", "ctx_shift", "lora",
                   "chat_template", "think_budget", "extra_args")

    def _engine_snapshot(self):
        return json.dumps({k: self.cfg.get(k) for k in self.ENGINE_KEYS}, sort_keys=True, default=str)

    def restart_server(self):
        """Really restart: kill the running server, then start it again with the current settings."""
        self.stop_server()
        QTimer.singleShot(400, self.toggle_server)

    def toggle_server(self):
        if self.proc:
            self.stop_server()
            return
        exe = self.resolve_server_exe()
        model = (self.cfg.get("model") or "").strip().strip('"')
        if not exe:
            self.show_error(t("no_server"))
            return
        if not os.path.isfile(model):
            self.show_error(t("no_model"))
            return
        self._run_port = self._free_port()
        args = ["-m", model, "--host", "127.0.0.1", "--port", str(self._run_port),
                "-c", str(self.cfg.get("ctx", 8192)),
                "-t", str(self.effective_threads())]
        mm = (self.cfg.get("mmproj") or "").strip().strip('"')
        if mm and os.path.isfile(mm):
            args += ["--mmproj", mm]
        args += self.server_extra_args(exe)
        self.server_log = ""
        proc = QProcess(self)
        proc.setWorkingDirectory(os.path.dirname(exe))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyRead.connect(lambda p=proc: self._read_proc(p))
        proc.finished.connect(self.on_proc_finished)
        self.proc = proc
        proc.start(exe, args)
        self.set_state("loading")
        self.health = HealthWorker(self.port)
        self.health.ready.connect(self.on_ready)
        self.health.start()

    def server_help(self, exe):
        """Text of `llama-server --help` (cached) - used to pass only flags this llama.cpp build understands."""
        cache = getattr(self, "_help_cache", None)
        if cache and cache[0] == exe:
            return cache[1]
        txt = ""
        try:
            kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
            r = subprocess.run([exe, "--help"], capture_output=True, timeout=25,
                               cwd=os.path.dirname(exe), **kw)
            txt = (r.stdout + r.stderr).decode("utf-8", "replace")
        except Exception:
            txt = ""
        self._help_cache = (exe, txt)
        return txt

    def server_extra_args(self, exe):
        """llama-server flags built from the Engine settings (only what you changed from the default)."""
        c = self.cfg
        hlp = self.server_help(exe)

        def has(flag):                      # unknown help text -> assume the flag exists
            return (not hlp) or (flag in hlp)

        a = []
        for key, flag in (("batch", "--batch-size"), ("ubatch", "--ubatch-size"), ("threads_batch", "--threads-batch"),
                          ("parallel", "--parallel"), ("ngl", "--n-gpu-layers"),
                          ("think_budget", "--reasoning-budget")):
            v = c.get(key)
            if v is not None and int(v) >= 0 and has(flag):
                a += [flag, str(int(v))]
        if c.get("flash_attn") in ("on", "off", "auto") and has("--flash-attn"):
            a += ["--flash-attn", c["flash_attn"]]
        for key, flag in (("cache_k", "--cache-type-k"), ("cache_v", "--cache-type-v")):
            if c.get(key) and has(flag):
                a += [flag, c[key]]
        lm = c.get("load_mode") or ""
        if lm:
            if has("--load-mode"):          # newer llama.cpp builds
                a += ["--load-mode", lm]
            else:                           # older builds: --mlock / --no-mmap
                if lm in ("mlock", "mmap+mlock"):
                    a.append("--mlock")
                if lm == "none":
                    a.append("--no-mmap")
        if c.get("ctx_shift") and has("--context-shift"):
            a.append("--context-shift")
        lora = (c.get("lora") or "").strip().strip('"')
        if lora and os.path.isfile(lora):
            a += ["--lora", lora]
        if (c.get("chat_template") or "").strip():
            a += ["--chat-template", c["chat_template"].strip()]
        extra = (c.get("extra_args") or "").strip()
        if extra:
            try:
                toks = shlex.split(extra, posix=False)
            except ValueError:
                toks = extra.split()
            a += [x.strip('"') for x in toks]
        return a

    def request_params(self):
        """Per-request llama-server parameters built from the Chat settings."""
        c = self.cfg
        p = {k: v for k, v in (c.get("sampling") or {}).items() if v is not None}
        if c.get("think_mode") in ("on", "off"):
            p["chat_template_kwargs"] = {"enable_thinking": c["think_mode"] == "on"}
        stop = [s.replace("\\n", "\n") for s in (c.get("stop") or "").splitlines() if s]
        if stop:
            p["stop"] = stop
        grammar = (c.get("grammar") or "").strip()
        if grammar:
            p["grammar"] = grammar
        elif c.get("json_mode"):
            p["response_format"] = {"type": "json_object"}
        try:
            extra = json.loads(c.get("extra_json") or "{}")
        except ValueError:
            extra = {}
        if isinstance(extra, dict):
            extra.pop("messages", None)
            extra.pop("stream", None)
            p.update(extra)
        p["cache_prompt"] = True
        return p

    def _read_proc(self, p):
        self.server_log = (self.server_log + bytes(p.readAll()).decode("utf-8", "replace"))[-4000:]

    def on_ready(self, ok):
        if self.proc is None:
            return
        if ok:
            self.set_state("ready")
            if self.pending_send:        # model was started by the Send button: now really send
                self.set_pending(False)
                QTimer.singleShot(0, self.send_message)
        else:
            self.set_pending(False)
            self.set_state("error")
            self.show_error(self.server_log[-300:].strip() or t("st_error"))

    def on_proc_finished(self, *_):
        was = self.state
        self.set_pending(False)
        tail = self.server_log[-400:].strip()
        if self.health:
            self.health.stop()
        self.proc = None
        if was == "loading":
            self.set_state("error")
            self.show_error(tail or t("st_error"))
        else:
            self.set_state("stopped")
            if was == "ready":
                self.show_error(t("server_crashed"))

    def stop_server(self):
        self.set_pending(False)
        if self.health:
            self.health.stop()
        if self.proc:
            try:
                self.proc.finished.disconnect()
            except TypeError:
                pass
            self.proc.kill()
            self.proc.waitForFinished(3000)
            self.proc = None
        self.set_state("stopped")

    def set_state(self, st):
        self.state = st
        self.update_state_ui()

    def open_web(self):
        """Open llama-server's own web page in the default browser."""
        if self.proc is None:
            self.show_error(t("web_need_model"))
            return
        port = getattr(self, "_run_port", None) or int(self.cfg.get("port", 8080))
        QDesktopServices.openUrl(QUrl("http://127.0.0.1:%d/" % port))

    def update_state_ui(self):
        col = {"stopped": self.pal["muted"], "loading": self.pal["warn"],
               "ready": self.pal["ok"], "error": self.pal["danger"]}[self.state]
        self.pill.setText("●  " + t("st_" + self.state))
        self.pill.setStyleSheet("color:%s; font-weight:600; padding:0 8px;" % col)
        running = self.proc is not None
        self.btn_server.setText(t("stop_model") if running else t("start_model"))
        self.btn_server.setProperty("danger", running)
        self.btn_server.style().unpolish(self.btn_server)
        self.btn_server.style().polish(self.btn_server)

    # ------------------------------------------------------------ chatting
    def set_generating(self, on):
        self.generating = on
        self.btn_send.setText("■" if (on or self.pending_send) else "↑")
        self.btn_new.setEnabled(not on)
        self.btn_new_top.setEnabled(not on)
        self.chat_list.setEnabled(not on)

    def send_or_stop(self):
        if self.pending_send:
            self.set_pending(False)      # cancel the waiting message (text stays in the box)
        elif self.generating and self.worker:
            self.worker.stop()
        else:
            self.send_message()

    def send_message(self):
        if self.generating:
            return
        text = self.inp.toPlainText().strip()
        atts = [c.att for c in self.chips]
        if not text and not atts:
            return
        if any(a["kind"] == "image" for a in atts) and not (self.cfg.get("mmproj") or "").strip():
            self.show_error(t("need_mmproj"))
            return
        if self.state != "ready":
            if self.proc is None:
                if not self.cfg.get("auto_start", True):
                    self.show_error(t("need_model"))
                    return
                self.toggle_server()         # model is off: start it, the message goes out when it is ready
                if self.proc is None:        # could not start (the reason is already shown)
                    return
            elif self.state != "loading":
                self.show_error(t("need_model"))
                return
            self.set_pending(True)
            return

        files = [a["name"] for a in atts]
        body = text
        images = []
        for a in atts:
            if a["kind"] == "text":
                note = (" " + t("truncated")) if a.get("truncated") else ""
                body += "\n\n[%s: %s%s]\n```\n%s\n```" % (t("file_label"), a["name"], note, a["data"])
            else:
                images.append(a["data"])
        if images:
            content = [{"type": "text", "text": body or t("describe_image")}]
            content += [{"type": "image_url", "image_url": {"url": u}} for u in images]
        else:
            content = body

        self.pending_text = text
        self.cur["history"].append({"role": "user", "content": content})
        self.cur["view"].append(["user", text, files])
        self.view.add("user", text, files)
        self.ai_widget = self.view.add("assistant", "")
        self.ai_text = self.ai_raw = self.ai_reason = self.ai_reason_stream = ""
        self.prompt_pct = None
        self.stage = 0
        self.spin = 0
        self.think_collapsed = False
        self.sent_files = len(files)
        self.ai_widget.set_status(self.status_text())
        self.inp.clear()
        self.clear_chips()
        QTimer.singleShot(0, self.view.scroll_bottom)

        msgs = []
        sysmsg = self.cfg.get("system")
        sysmsg = t("default_sys") if sysmsg is None else sysmsg
        if sysmsg.strip():
            msgs.append({"role": "system", "content": sysmsg.strip()})
        msgs += self.cur["history"]
        self.set_generating(True)
        payload = {"messages": msgs, "stream": True, "return_progress": True,
                   "temperature": float(self.cfg.get("temp", 0.7))}
        if int(self.cfg.get("max_tokens", 0)) > 0:
            payload["max_tokens"] = int(self.cfg["max_tokens"])
        payload.update(self.request_params())
        self.last_stats = None
        self.worker = ChatWorker(self.port, payload)
        self.worker.stats.connect(self.on_stats)
        self.worker.chunk.connect(self.on_chunk)
        self.worker.reasoning.connect(self.on_reasoning)
        self.worker.progress.connect(self.on_progress)
        self.worker.connected.connect(self.on_connected)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_fail)
        self.worker.start()

    def on_stats(self, raw):
        ctx = None if self.cfg.get("parallel") else self.cfg.get("ctx", 8192)
        self.last_stats = make_stats(raw, ctx)

    def on_chunk(self, piece):
        self.ai_raw += piece
        self._dirty = True

    def on_reasoning(self, piece):
        self.ai_reason_stream += piece
        self._dirty = True

    def on_progress(self, pct):
        self.prompt_pct = pct

    def on_connected(self):
        self.stage = 1

    def recompute(self):
        """Split streamed content into thinking + answer (also handles inline <think> tags)."""
        inline, ans = "", self.ai_raw
        s = self.ai_raw.lstrip()
        if s.startswith("<think>"):
            rest = s[len("<think>"):]
            if "</think>" in rest:
                inline, ans = rest.split("</think>", 1)
            else:
                inline, ans = rest, ""
        parts = [x.strip() for x in (self.ai_reason_stream, inline) if x.strip()]
        self.ai_reason = "\n".join(parts)
        self.ai_text = ans.lstrip("\n")

    def status_text(self):
        if self.ai_text.strip():
            return t("st_write")
        if self.ai_reason:
            return t("st_think")
        if self.stage == 0:
            return t("st_files", n=self.sent_files) if self.sent_files else t("st_send")
        if self.prompt_pct is not None and self.prompt_pct < 100:
            return t("st_prompt", pct=self.prompt_pct)
        return t("st_wait")

    def _tick(self):
        if not self.generating or self.ai_widget is None:
            return
        self.spin += 1
        w = self.ai_widget
        if self._dirty:
            self._dirty = False
            self.recompute()
            if self.ai_reason != w.reasoning:
                w.set_reasoning(self.ai_reason)
            if self.ai_text.strip():
                if self.ai_reason and not self.think_collapsed:
                    w.collapse_think()
                    self.think_collapsed = True
                w.set_text(self.ai_text)
        if self.spin % 2 == 0:
            w.set_status(self.status_text() + "." * ((self.spin // 4) % 4))

    def _rollback(self):
        """Remove the unanswered user turn and put its text back in the input box."""
        self.view.remove_last(2)
        if self.cur["history"]:
            self.cur["history"].pop()
        if self.cur["view"]:
            self.cur["view"].pop()
        if not self.cur["view"]:
            self.view.show_welcome()
        self.inp.setPlainText(self.pending_text)

    def on_done(self):
        self._dirty = False
        self.set_generating(False)
        self.recompute()
        if not self.ai_text.strip():
            self._rollback()
            self.ai_widget = None
            return
        self.ai_widget.set_status("")
        if self.ai_reason:
            self.ai_widget.set_reasoning(self.ai_reason)
            self.ai_widget.collapse_think()
        self.ai_widget.set_text(self.ai_text)
        self.cur["history"].append({"role": "assistant", "content": self.ai_text})
        st = getattr(self, "last_stats", None)
        self.last_stats = None
        entry = ["assistant", self.ai_text, []]
        if st:
            entry.append(st)
            if SHOW_STATS:
                self.ai_widget.set_stats(fmt_stats(st))
        self.cur["view"].append(entry)
        self.ai_widget = None
        self.save_current()
        self.maybe_title()

    def on_fail(self, err):
        self._dirty = False
        self.set_generating(False)
        self._rollback()
        self.ai_widget = None
        self.show_error(err)

    def closeEvent(self, e):
        if self.scan:
            self.scan.stop()
            self.scan.wait(1000)
        self.save_current(touch=False)
        self.save_cfg()
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1500)
        if self.proc:
            self.stop_server()
        for w in list(_LIVE_TITLES):
            w.wait(500)
        e.accept()


def main():
    if os.name == "nt":
        try:    # own taskbar identity so the 8AI icon shows even when started with python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Clubapp.8AI")
        except Exception:
            pass
    install_crash_guard()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    if ICON_PATH:
        app.setWindowIcon(QIcon(ICON_PATH))
    lang = load_cfg().get("lang", "en")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if lang == "fa" else Qt.LayoutDirection.LeftToRight)
    w = EightAI()
    _MAIN[0] = w
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
