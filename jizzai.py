"""
JizzAI - modern local-LLM chat UI for llama.cpp (llama-server)
English (default) + Persian (RTL), chat history, drag & drop files.

    pip install PyQt6            (optional for PDF files: pip install pypdf)
    python jizzai.py
"""
import sys, os, re, json, html, base64, zipfile, mimetypes, time, uuid
import urllib.request, urllib.error

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QProcess, QTimer, QUrl
from PyQt6.QtGui import (QTextOption, QKeyEvent, QGuiApplication, QPalette, QColor, QIcon, QFontMetrics,
                         QSyntaxHighlighter, QTextCharFormat, QFont, QDesktopServices)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QPlainTextEdit, QTextBrowser, QLabel, QSpinBox,
    QDoubleSpinBox, QFileDialog, QListWidget, QListWidgetItem, QMessageBox,
    QFrame, QToolButton, QScrollArea, QDialog, QComboBox, QMenu, QInputDialog,
    QSizePolicy, QAbstractItemView, QCheckBox,
)

APP_NAME = "JizzAI"
APP_VERSION = "1.8.0"
# folder of the running app (works for python jizzai.py and for the PyInstaller exe)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
# portable mode: a "portable.flag" file next to the exe keeps settings + chats inside <app>\data
PORTABLE = os.path.exists(os.path.join(APP_DIR, "portable.flag"))
DATA_DIR = os.path.join(APP_DIR, "data") if PORTABLE else os.path.join(os.path.expanduser("~"), ".jizzai")
BUNDLED_LLAMA = os.path.join(APP_DIR, "llama")
# bundled read-only resources (icon): PyInstaller unpacks them to sys._MEIPASS
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
ICON_PATH = next((os.path.join(d, "icon.ico") for d in (RES_DIR, APP_DIR, os.path.join(APP_DIR, "_internal"))
                  if os.path.isfile(os.path.join(d, "icon.ico"))), "")
CHAT_DIR = os.path.join(DATA_DIR, "chats")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
OLD_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".jizzai.json")

TEXT_EXT = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".tsv", ".html", ".htm",
    ".css", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".log", ".c", ".cpp", ".h",
    ".java", ".cs", ".go", ".rs", ".sql", ".sh", ".bat", ".srt", ".tex",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_CHARS = 200_000

# ------------------------------------------------------------------ i18n
LANG = "en"
TR = {
    "en": {
        "new_chat": "New chat", "search": "Search chats…", "settings": "Settings",
        "start_model": "Start model", "stop_model": "Stop model",
        "st_stopped": "Model stopped", "st_loading": "Loading model…",
        "st_ready": "Ready", "st_error": "Failed to start",
        "placeholder": "Message JizzAI…   (Enter to send · Shift+Enter for new line)",
        "attach": "Attach files", "you": "You", "copy": "Copy", "copied": "Copied ✓",
        "welcome_title": "How can I help you today?",
        "welcome_sub": "Start the model, then chat. Drag & drop documents, code, PDFs or images anywhere.",
        "drop_here": "Drop files here", "rename": "Rename", "delete": "Delete",
        "export": "Export as Markdown", "rename_label": "Chat title:",
        "delete_confirm": "Delete this chat permanently?",
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
    },
    "fa": {
        "new_chat": "گفتگوی جدید", "search": "جستجو در گفتگوها…", "settings": "تنظیمات",
        "start_model": "اجرای مدل", "stop_model": "توقف مدل",
        "st_stopped": "مدل متوقف است", "st_loading": "در حال بارگذاری مدل…",
        "st_ready": "آماده", "st_error": "اجرا نشد",
        "placeholder": "پیامت را به JizzAI بنویس…   (Enter ارسال · Shift+Enter خط جدید)",
        "attach": "پیوست فایل", "you": "شما", "copy": "کپی", "copied": "کپی شد ✓",
        "welcome_title": "امروز چه کمکی از من برمی‌آید؟",
        "welcome_sub": "مدل را اجرا کن و شروع کن. اسناد، کد، PDF یا تصویر را هر جا خواستی بکش و رها کن.",
        "drop_here": "فایل‌ها را اینجا رها کن", "rename": "تغییر نام", "delete": "حذف",
        "export": "خروجی Markdown", "rename_label": "عنوان گفتگو:",
        "delete_confirm": "این گفتگو برای همیشه حذف شود؟",
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
    },
}


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


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


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


def find_mmproj_for(model_path, mmprojs):
    """mmproj file sitting in the same folder as the model (best match by name)."""
    folder = os.path.dirname(model_path)
    same = [m for m in mmprojs if os.path.dirname(m["path"]) == folder]
    if not same:
        return None
    stem = os.path.basename(model_path).lower().replace(".gguf", "")
    same.sort(key=lambda m: (0 if any(w in m["name"].lower() for w in stem.split("-")[:2]) else 1, m["size"]))
    return same[0]["path"]


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
                    ch = obj.get("choices") or []
                    if ch:
                        delta = ch[0].get("delta") or {}
                        rc = delta.get("reasoning_content")
                        if rc:
                            self.reasoning.emit(rc)
                        piece = delta.get("content")
                        if piece:
                            self.chunk.emit(piece)
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
        self.textChanged.connect(self._on_change)
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
        lines = max(1, int(self.document().size().height()))
        cap = max(80, min(180, int(self.window().height() * 0.25)))
        self.setFixedHeight(min(cap, max(40, lines * self.fontMetrics().lineSpacing() + 18)))

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

    def resizeEvent(self, e):
        super().resizeEvent(e)
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
        self.btn = QToolButton()
        self.btn.setText(t("copy"))
        self.btn.setMinimumWidth(86)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self.copy_code)
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

    def copy_code(self):
        QGuiApplication.clipboard().setText(self.code or "")
        self.btn.setText(t("copied"))
        QTimer.singleShot(1400, lambda: self.btn.setText(t("copy")))


class MessageWidget(QFrame):
    def __init__(self, role, text, files, pal):
        super().__init__()
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
        self.btn_copy = None
        if role == "assistant":
            self.btn_copy = QToolButton()
            self.btn_copy.setText(t("copy"))
            self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.set_text(text)

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
        self.btn_copy.setText(t("copied"))
        QTimer.singleShot(1400, lambda: self.btn_copy.setText(t("copy")))

    def fit(self, maxw):
        if self.role != "user":
            return
        if any(k == "code" for k, _w in self.segs):
            self.setFixedWidth(int(maxw))
            return
        ideal = 0
        for _k, w in self.segs:
            doc = w.document()
            doc.setTextWidth(maxw - 34)
            ideal = max(ideal, doc.idealWidth())
        self.setFixedWidth(int(max(90, min(maxw, ideal + 44))))


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

    def add(self, role, text, files=None):
        self._drop_welcome()
        m = MessageWidget(role, text, files, self.pal)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            holder.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # user bubble stays on the right
            hl.addStretch(1)
            m.fit(self.max_bubble())
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
            m.fit(mb)
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
    def __init__(self, parent, cfg, recent, scanned=None):
        super().__init__(parent)
        self._scan = None
        self.setWindowTitle(t("settings"))
        scr = (parent.screen() if parent is not None else QGuiApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(min(560, int(scr.width() * 0.94)), min(320, int(scr.height() * 0.8)))
        v = QVBoxLayout(self)
        v.setSpacing(12)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.cb_lang = QComboBox()
        self.cb_lang.addItem("English", "en")
        self.cb_lang.addItem("فارسی", "fa")
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findData(cfg.get("lang", "en"))))
        self.cb_theme = QComboBox()
        self.cb_theme.addItem(t("theme_dark"), "dark")
        self.cb_theme.addItem(t("theme_light"), "light")
        self.cb_theme.setCurrentIndex(max(0, self.cb_theme.findData(cfg.get("theme", "dark"))))
        form.addRow(t("language"), self.cb_lang)
        form.addRow(t("theme"), self.cb_theme)

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
        form.addRow(t("llama_path"), bw)
        self.lb_bin = QLabel()
        self.lb_bin.setObjectName("Muted")
        self.lb_bin.setWordWrap(True)
        form.addRow("", self.lb_bin)
        form.addRow("", link_row(LINK_LLAMA))

        self.ed_mdir = QLineEdit(cfg.get("models_dir", ""))
        self.ed_mdir.editingFinished.connect(self._start_scan)
        form.addRow(t("models_dir"), self._row(self.ed_mdir, self._pick_mdir))
        self.lb_mdir = QLabel()
        self.lb_mdir.setObjectName("Muted")
        form.addRow("", self.lb_mdir)
        form.addRow("", link_row(LINK_HF, LINK_GEMMA))

        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cb_model.setMinimumContentsLength(30)
        self._fill_models(recent, scanned or [])
        self.cb_model.setEditText(cfg.get("model", ""))
        form.addRow(t("model"), self._row(self.cb_model, self._pick_model))
        self.ed_mm = QLineEdit(cfg.get("mmproj", ""))
        form.addRow(t("mmproj"), self._row(self.ed_mm, self._pick_mm))

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
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(0, 2)
        self.sp_temp.setSingleStep(0.1)
        self.sp_temp.setValue(cfg.get("temp", 0.7))
        self.sp_font = QDoubleSpinBox()
        self.sp_font.setRange(8, 20)
        self.sp_font.setSingleStep(0.5)
        self.sp_font.setDecimals(1)
        self.sp_font.setValue(float(cfg.get("font_pt", 10.5)))
        self.sp_maxtok = QSpinBox()
        self.sp_maxtok.setRange(0, 262144)
        self.sp_maxtok.setSingleStep(256)
        self.sp_maxtok.setValue(int(cfg.get("max_tokens", 0)))
        self.ck_scroll = QCheckBox(t("opt_autoscroll"))
        self.ck_scroll.setChecked(bool(cfg.get("autoscroll", True)))
        self.ck_start = QCheckBox(t("opt_autostart"))
        self.ck_start.setChecked(bool(cfg.get("auto_start", True)))
        self.ck_title = QCheckBox(t("opt_autotitle"))
        self.ck_title.setChecked(bool(cfg.get("auto_title", True)))
        form.addRow(t("behavior"), self.ck_scroll)
        form.addRow("", self.ck_start)
        form.addRow("", self.ck_title)
        form.addRow(t("font_size"), self.sp_font)
        form.addRow(t("max_tokens"), self.sp_maxtok)
        form.addRow(t("ctx"), self.sp_ctx)
        form.addRow(t("threads"), self.sp_thr)
        form.addRow(t("port"), self.sp_port)
        form.addRow(t("temp"), self.sp_temp)

        self.ed_sys = QPlainTextEdit(cfg.get("system") if cfg.get("system") is not None else t("default_sys"))
        self.ed_sys.setObjectName("Plain")
        self.ed_sys.setFixedHeight(90)
        form.addRow(t("sys_prompt"), self.ed_sys)
        body = QWidget()                      # the settings form scrolls when the screen is small
        body.setObjectName("Central")
        body.setLayout(form)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        sc.setWidget(body)
        v.addWidget(sc, 1)
        self._body = body

        note = QLabel(t("restart_note"))
        note.setObjectName("Muted")
        v.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        b_cancel = QPushButton(t("cancel"))
        b_cancel.clicked.connect(self.reject)
        b_save = QPushButton(t("save"))
        b_save.setObjectName("Primary")
        b_save.clicked.connect(self.accept)
        row.addWidget(b_cancel)
        row.addWidget(b_save)
        v.addLayout(row)

        self._check_bin()
        if self.ed_mdir.text().strip():
            if scanned:
                self.lb_mdir.setText(t("models_found", n=len(scanned)))
            else:
                self._start_scan()
        pal = getattr(parent, "pal", PALETTES["dark"])
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:%s; border:none;" % pal["border"])
        v.addWidget(sep)
        foot = QWidget()
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addStretch(1)
        ver = QLabel("%s %s   ·" % (t("version"), APP_VERSION))
        ver.setObjectName("Muted")
        fl.addWidget(ver)
        for name, url in (("GitHub: Mrmmd2004", "https://github.com/Mrmmd2004"),
                          ("Telegram: @Clubapp8", "https://t.me/Clubapp8")):
            lb = QToolButton()
            lb.setObjectName("LinkBtn")
            lb.setText(name)
            lb.setCursor(Qt.CursorShape.PointingHandCursor)
            lb.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            fl.addWidget(lb)
        fl.addStretch(1)
        v.addWidget(foot)
        self.resize(min(780, int(scr.width() * 0.94)),
                    min(body.sizeHint().height() + 190, int(scr.height() * 0.9)))

    def _row(self, widget, fn):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(widget, 1)
        b = QPushButton(t("browse"))
        b.clicked.connect(fn)
        l.addWidget(b)
        return w

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
class JizzAI(QMainWindow):
    def __init__(self):
        super().__init__()
        global LANG
        os.makedirs(CHAT_DIR, exist_ok=True)
        self.cfg = load_cfg()
        LANG = self.cfg.get("lang", "en")
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
                self.stop_server()
                QTimer.singleShot(300, self.toggle_server)

    # ------------------------------------------------------------ language / theme
    def retranslate(self):
        self.btn_new.setText("＋  " + t("new_chat"))
        self.search.setPlaceholderText(t("search"))
        self.btn_settings.setToolTip(t("settings"))
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
        global LANG
        old = dict(self.cfg)
        self.cfg.update(new)
        LANG = self.cfg.get("lang", "en")
        self.pal = PALETTES.get(self.cfg.get("theme", "dark"), PALETTES["dark"])
        if new["model"]:
            rec = [m for m in self.cfg.get("recent_models", []) if m != new["model"]]
            self.cfg["recent_models"] = ([new["model"]] + rec)[:8]
        self.save_cfg()
        self.view.autoscroll = bool(self.cfg.get("autoscroll", True))
        if (old.get("lang", "en") != LANG or old.get("theme", "dark") != self.cfg.get("theme", "dark")
                or old.get("font_pt", 10.5) != self.cfg.get("font_pt", 10.5)):
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
            self.apply_settings(dlg.values())
            self.update_model_btn()
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
        tt = self.cur.get("title") or t("untitled")
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

    def export_chat(self, c):
        name = re.sub(r'[\\/:*?"<>|]+', "_", c.get("title") or "chat")
        path, _ = QFileDialog.getSaveFileName(self, t("export"), name + ".md", "Markdown (*.md)")
        if not path:
            return
        lines = ["# " + (c.get("title") or "chat"), ""]
        for role, text, files in c["view"]:
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
        for role, text, files in self.cur["view"]:
            self.view.add(role, text, files)
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
                key = "mmproj" if "mmproj" in os.path.basename(low) else "model"
                self.cfg[key] = p
                if key == "model":
                    rec = [m for m in self.cfg.get("recent_models", []) if m != p]
                    self.cfg["recent_models"] = ([p] + rec)[:8]
                self.save_cfg()
                self.update_model_btn()
                self.show_info(t("model_selected", name=os.path.basename(p)))
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
        return int(self.cfg.get("port", 8080))

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
        args = ["-m", model, "--host", "127.0.0.1", "--port", str(self.port),
                "-c", str(self.cfg.get("ctx", 8192)),
                "-t", str(self.cfg.get("threads", max(1, (os.cpu_count() or 4) // 2)))]
        mm = (self.cfg.get("mmproj") or "").strip().strip('"')
        if mm and os.path.isfile(mm):
            args += ["--mmproj", mm]
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
        self.worker = ChatWorker(self.port, payload)
        self.worker.chunk.connect(self.on_chunk)
        self.worker.reasoning.connect(self.on_reasoning)
        self.worker.progress.connect(self.on_progress)
        self.worker.connected.connect(self.on_connected)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_fail)
        self.worker.start()

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
        self.cur["view"].append(["assistant", self.ai_text, []])
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
        try:    # own taskbar identity so the JizzAI icon shows even when started with python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Clubapp.JizzAI")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    if ICON_PATH:
        app.setWindowIcon(QIcon(ICON_PATH))
    lang = load_cfg().get("lang", "en")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if lang == "fa" else Qt.LayoutDirection.LeftToRight)
    w = JizzAI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
