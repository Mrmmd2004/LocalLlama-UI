<a id="english"></a>

<p align="center"><b>English</b> &nbsp;|&nbsp; <a href="#فارسی">🇮🇷 فارسی</a></p>

# JizzAI — a modern desktop chat UI for llama.cpp

**JizzAI** is a lightweight Windows desktop app for chatting with local LLMs (GGUF models) through
[llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`. Everything runs offline on your own PC —
no cloud, no account, no API key. JizzAI does not contain a model itself: it is a friendly front-end that starts
`llama-server` for you, lets you pick models from a folder, and gives you a clean chat window with history,
file attachments and full control over the engine settings.

English + Persian (RTL) interface · dark/light theme · chat history · drag & drop files

**Version 2.8.0 · Windows 10/11 · 64-bit (x64)**

![chat](screenshots/chat-code.png)

## ⬇️ Download

Ready-made builds are in the **[Releases](../../releases)** section of this repository — no Python needed.
Pick one of the three x64 builds:

| File | What it is | Best for |
|---|---|---|
| `JizzAI-<version>-Setup.exe` | Normal installer (Start-menu entry, optional desktop icon, uninstaller) | Everyday use |
| `JizzAI-<version>-Portable.exe` | **One single exe** — double-click and it runs. No install, no extraction. Settings and chats are kept in a `data` folder next to it | A USB stick, trying it out |
| `JizzAI-<version>-Portable.zip` | Portable folder — unzip anywhere and run `JizzAI.exe` (starts faster than the single exe) | Portable use with llama.cpp already bundled |

The Setup and the zip come with llama.cpp inside. The single `Portable.exe` is kept small: choose your llama.cpp
folder (or zip) once in **Settings**, or put a `llama` folder next to the exe.

## 🧩 Add the engine and a model (required)

JizzAI is only the chat window. To actually chat you need two things, both free, and both are added once in **Settings (⚙)**:

**1. The engine – llama.cpp** (it runs the model)
- Download from the [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) → open the newest release → under *Assets* take the Windows zip:
  - `llama-…-bin-win-cpu-x64.zip` – works on every PC (CPU only). Best choice if you are not sure.
  - `llama-…-bin-win-vulkan-x64.zip` – uses most GPUs (NVIDIA / AMD / Intel) for more speed.
  - `llama-…-bin-win-cuda-…-x64.zip` – NVIDIA GPUs only (may need the matching `cudart` zip from the same release).
- You do **not** need to extract it: in Settings choose the zip or the extracted folder as the **llama.cpp folder** (or just drag it onto the JizzAI window). `llama-server.exe` is found automatically.
- Builds that already include llama.cpp (Setup and Portable.zip) can skip this step.

**2. A model – a `.gguf` file**
- Download from [Hugging Face](https://huggingface.co/models?library=gguf&sort=trending) (search for “GGUF”). A good small start is
  [Gemma 3 1B (GGUF)](https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main) — pick a file such as `…Q4_K_M.gguf`.
- Rule of thumb: the file size should be smaller than your free RAM (or VRAM when using a GPU build). Smaller models and lower quantisations (Q4) are faster and lighter.
- Put your models in one folder (sub-folders are fine), then in Settings set it as the **Models folder** — or drag a single `.gguf` onto the window.
- Vision (images): download the model **and** its `mmproj` file and keep them in the same folder; JizzAI picks it up automatically.

Then press **Start model** and chat.

## Features

- **Local & private** – runs `llama-server` on `127.0.0.1`; your chats are saved on your PC only
- **Pick your llama.cpp** – choose the extracted llama.cpp folder (or the zip) — `llama-server.exe` is found automatically, even in sub-folders
- **Models folder browser** – choose a folder once; every `.gguf` model inside it and its sub-folders is listed
  (split models like `*-00001-of-00003.gguf` are listed once)
- **One-click model switch** – the 🧠 button next to the message box lists your models; pick one and (if the model is running) restart it with the new one
- **Vision models** – the matching `mmproj` file next to a model is selected automatically; attach images to chat
- **Code blocks with Copy button** and syntax colouring (Python, C/C++, JS/TS, Java, Go, Rust, Bash, SQL, JSON, HTML …)
- **Thinking models** – reasoning is shown in a collapsible "Thought process" section; a thinking mode and token budget can be set
- **Attach files** – drag & drop or 📎: text, code, `.docx`, `.pdf` (needs `pypdf`), images
- **Chat history** – search, rename, delete, delete all, export to Markdown / save as file
- **Engine settings** – batch sizes, threads, GPU layers, parallel slots, flash attention, KV-cache type, model loading mode
  (mmap / mlock / none / dio), context shift, LoRA adapter, chat template and any extra `llama-server` argument
- **Sampling & output control** – Temperature, Top-K / Top-P / Min-P, repeat & presence penalties, Mirostat, DRY, XTC, seed,
  ready-made presets (Precise / Balanced / Creative), forced JSON output, stop sequences, GBNF grammar, extra request parameters
- **Speed & token stats** – tokens per second, token counts and context usage shown under each answer (can be turned off)
- **Open llama-server's own web page** from inside the app
- **Smart behavior options** – auto-start the model when you press Send, auto-scroll while the answer is written, automatic chat titles, adjustable text size, max answer length, and a *scroll to latest message* button
- **Persian / English UI**, dark / light theme
- **64-bit (x64) builds** – installer, single-file portable exe and portable zip

| Model picker | Settings |
|---|---|
| ![picker](screenshots/model-picker.png) | ![settings](screenshots/settings.png) |

## Quick start

1. Download and run a build from **[Releases](../../releases)** (see above)
2. Download a **GGUF model**, for example
   [Gemma 3 1B (GGUF)](https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main) from [Hugging Face](https://huggingface.co/)
3. If your build has no llama.cpp inside, download **llama.cpp** for Windows from the
   [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) (e.g. `llama-bXXXX-bin-win-cpu-x64.zip`)
4. Open **Settings (⚙)** → set the **llama.cpp folder** (or zip) and the **Models folder** → click **Start model** → chat!

## Run from source

1. Install [Python 3.10+](https://www.python.org/downloads/) (Windows, **64-bit / x64**)
2. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python jizzai.py
   ```

## Build the exe / installer yourself (x64)

Use **64-bit Python**. Put `jizzai.py`, `build.py`, `jizzai.iss`, `make_icon.py`, `icon.ico` and the llama.cpp zip
(`llama-bXXXX-bin-win-cpu-x64.zip`) in one folder, then:

```bash
python build.py
```

It creates, in `output/`:

- `JizzAI-<version>-Setup.exe` – the installer (needs [Inno Setup](https://jrsoftware.org/isinfo.php))
- `JizzAI-<version>-Portable.zip` – portable folder with llama.cpp bundled
- `JizzAI-<version>-Portable.exe` – single-file portable exe

Useful options: `--skip-installer` (no Inno Setup needed), `--skip-portable`, `--skip-single`,
`--single-llama` (pack llama.cpp inside the single exe — bigger and slower to start), `--no-llama`, `--clean`.
All options are listed at the top of `build.py`.

## Tips

- Drag a **models folder** or a **llama.cpp folder / zip** onto the window — JizzAI recognises which one it is
- Drag a single `.gguf` onto the window to select it as the model (`mmproj` files are detected by name)
- Portable mode: the single `Portable.exe` always keeps settings and chats in `data/` next to it; for the zip, a `portable.flag` file next to the exe does the same
- Images need a vision model **and** its `mmproj` file
- Requires 64-bit Windows (x64); 32-bit Windows is not supported

## Links

- GitHub: [Mrmmd2004](https://github.com/Mrmmd2004)
- Telegram: [@Clubapp8](https://t.me/Clubapp8)

---

## فارسی

<p align="center"><a href="#english">🇬🇧 English</a> &nbsp;|&nbsp; <b>فارسی</b></p>

<div dir="rtl">

# JizzAI — رابط گفتگوی مدرن دسکتاپ برای llama.cpp

**JizzAI** یک برنامه‌ی سبک دسکتاپ برای ویندوز است که با آن می‌توانی با مدل‌های هوش مصنوعی محلی (فرمت GGUF) از طریق `llama-server` برنامه‌ی
[llama.cpp](https://github.com/ggml-org/llama.cpp) گفتگو کنی. همه‌چیز آفلاین و روی کامپیوتر خودت اجرا می‌شود؛
بدون سرویس ابری، بدون حساب کاربری و بدون کلید API. JizzAI خودش مدلی ندارد؛ یک رابط ساده است که `llama-server` را برایت اجرا می‌کند،
مدل‌ها را از یک پوشه لیست می‌کند و یک پنجره‌ی گفتگوی تمیز با تاریخچه، پیوست فایل و کنترل کامل تنظیمات موتور در اختیارت می‌گذارد.

رابط فارسی و انگلیسی · پوسته‌ی تیره و روشن · تاریخچه‌ی گفتگو · کشیدن و رها کردن فایل

**نسخه‌ی ۲.۸.۰ · ویندوز ۱۰/۱۱ · ۶۴ بیتی (x64)**

![chat](screenshots/chat-code.png)

### ⬇️ دانلود

نسخه‌های آماده در بخش **[Releases](../../releases)** همین مخزن قرار دارند و نیازی به نصب پایتون نیست.
یکی از این سه نسخه‌ی x64 را بردار:

| فایل | توضیح | مناسب برای |
|---|---|---|
| `JizzAI-<version>-Setup.exe` | نصاب معمولی (منوی استارت، آیکون دسکتاپ اختیاری، حذف‌کننده) | استفاده‌ی همیشگی |
| `JizzAI-<version>-Portable.exe` | **یک فایل exe تکی** — دابل‌کلیک کن و اجرا می‌شود؛ بدون نصب و بدون استخراج. تنظیمات و گفتگوها در پوشه‌ی `data` کنار آن ذخیره می‌شوند | فلش و امتحان کردن |
| `JizzAI-<version>-Portable.zip` | پوشه‌ی پرتابل — هرجا استخراج کن و `JizzAI.exe` را اجرا کن (سریع‌تر از exe تکی بالا می‌آید) | استفاده‌ی پرتابل همراه llama.cpp آماده |

نصاب و zip همراه llama.cpp هستند. `Portable.exe` تکی سبک نگه داشته شده: یک بار در **تنظیمات** پوشه (یا zip) برنامه‌ی llama.cpp را انتخاب کن،
یا پوشه‌ی `llama` را کنار exe بگذار.

### 🧩 افزودن موتور و مدل (ضروری)

JizzAI فقط پنجره‌ی گفتگوست. برای گفتگو واقعاً به دو چیز رایگان نیاز داری که هر دو فقط یک بار در **تنظیمات (⚙)** اضافه می‌شوند:

**۱. موتور – llama.cpp** (اجرای مدل را انجام می‌دهد)
- از [صفحه‌ی releases برنامه‌ی llama.cpp](https://github.com/ggml-org/llama.cpp/releases) آخرین نسخه را باز کن ← در بخش *Assets* فایل zip ویندوز را بردار:
  - `llama-…-bin-win-cpu-x64.zip` – روی همه‌ی کامپیوترها کار می‌کند (فقط CPU). اگر مطمئن نیستی این را بردار.
  - `llama-…-bin-win-vulkan-x64.zip` – از بیشتر کارت‌های گرافیک (NVIDIA / AMD / Intel) برای سرعت بیشتر استفاده می‌کند.
  - `llama-…-bin-win-cuda-…-x64.zip` – فقط کارت‌های NVIDIA (ممکن است zip مربوط به `cudart` از همان نسخه هم لازم باشد).
- لازم نیست استخراجش کنی: در تنظیمات zip یا پوشه‌ی استخراج‌شده را به‌عنوان **پوشه‌ی llama.cpp** بده (یا فقط روی پنجره‌ی JizzAI بکشش). `llama-server.exe` خودکار پیدا می‌شود.
- نسخه‌هایی که llama.cpp داخلشان هست (Setup و Portable.zip) این مرحله را لازم ندارند.

**۲. مدل – فایل `.gguf`**
- از [Hugging Face](https://huggingface.co/models?library=gguf&sort=trending) دانلود کن (عبارت «GGUF» را جستجو کن). یک شروع خوب و سبک
  [Gemma 3 1B (GGUF)](https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main) است — فایلی مثل `…Q4_K_M.gguf` را بردار.
- قاعده‌ی سرانگشتی: حجم فایل باید از رم آزادت (یا VRAM اگر نسخه‌ی GPU می‌زنی) کمتر باشد. مدل‌های کوچک‌تر و کوانتیزه‌ی پایین‌تر (Q4) سریع‌تر و سبک‌ترند.
- مدل‌ها را در یک پوشه بگذار (زیرپوشه هم مشکلی ندارد) و در تنظیمات آن را به‌عنوان **پوشه‌ی مدل‌ها** بده — یا یک فایل `.gguf` را روی پنجره بکش.
- مدل بینایی (تصویر): هم مدل و **هم** فایل `mmproj` آن را دانلود کن و کنار هم در یک پوشه بگذار؛ JizzAI خودکار پیدایش می‌کند.

بعد **اجرای مدل** را بزن و گفتگو کن.

### امکانات

- **محلی و خصوصی** – `llama-server` روی `127.0.0.1` اجرا می‌شود و گفتگوها فقط روی کامپیوتر خودت ذخیره می‌شوند
- **انتخاب llama.cpp** – پوشه‌ی استخراج‌شده (یا فایل zip) را بده؛ `llama-server.exe` حتی داخل زیرپوشه‌ها هم خودکار پیدا می‌شود
- **مرورگر پوشه‌ی مدل‌ها** – یک بار پوشه را انتخاب کن؛ همه‌ی فایل‌های `.gguf` داخل آن و زیرپوشه‌هایش لیست می‌شوند
  (مدل‌های تکه‌تکه مثل `*-00001-of-00003.gguf` فقط یک بار نمایش داده می‌شوند)
- **تعویض مدل با یک کلیک** – دکمه‌ی 🧠 کنار جعبه‌ی پیام مدل‌ها را لیست می‌کند؛ یکی را انتخاب کن و اگر مدل در حال اجراست، با مدل جدید دوباره اجرا می‌شود
- **مدل‌های بینایی** – فایل `mmproj` کنار مدل خودکار انتخاب می‌شود و می‌توانی تصویر ارسال کنی
- **کدها در باکس جدا با دکمه‌ی کپی** و رنگ‌بندی (Python، C/C++، JS/TS، Java، Go، Rust، Bash، SQL، JSON، HTML و …)
- **مدل‌های متفکر** – فرایند فکر کردن در بخش جمع‌شونده‌ی «فرایند فکر کردن» نمایش داده می‌شود؛ حالت و بودجه‌ی تفکر هم قابل تنظیم است
- **پیوست فایل** – کشیدن و رها کردن یا 📎: متن، کد، `.docx`، `.pdf` (نیازمند `pypdf`) و تصویر
- **تاریخچه‌ی گفتگو** – جستجو، تغییر نام، حذف، حذف همه، خروجی Markdown و ذخیره به‌عنوان فایل
- **تنظیمات موتور** – اندازه‌ی batch، تعداد thread، لایه‌های GPU، اسلات‌های موازی، flash attention، نوع کش KV، روش بارگذاری مدل
  (mmap / mlock / none / dio)، context shift، آداپتور LoRA، قالب گفتگو و هر آرگومان اضافه‌ی `llama-server`
- **نمونه‌برداری و کنترل خروجی** – دما، Top-K / Top-P / Min-P، جریمه‌ی تکرار و حضور، Mirostat، DRY، XTC، seed،
  پیش‌تنظیم‌های آماده (دقیق / متعادل / خلاق)، اجبار خروجی JSON، رشته‌های توقف، گرامر GBNF و پارامترهای اضافه‌ی درخواست
- **آمار سرعت و توکن** – توکن بر ثانیه، تعداد توکن و میزان استفاده از context زیر هر پاسخ (قابل خاموش کردن)
- **باز کردن صفحه‌ی وب خود llama-server** از داخل برنامه
- **گزینه‌های رفتار برنامه** – اجرای خودکار مدل با زدن ارسال، اسکرول خودکار هنگام نوشته شدن پاسخ، نام‌گذاری خودکار گفتگوها، تنظیم اندازه‌ی متن، حداکثر طول پاسخ و دکمه‌ی «رفتن به آخرین پیام»
- **رابط فارسی / انگلیسی** و پوسته‌ی تیره / روشن
- **نسخه‌های ۶۴ بیتی (x64)** – نصاب، exe پرتابل تک‌فایلی و zip پرتابل

| انتخاب مدل | تنظیمات |
|---|---|
| ![picker](screenshots/model-picker.png) | ![settings](screenshots/settings.png) |

### شروع سریع

1. یک نسخه را از بخش **[Releases](../../releases)** دانلود و اجرا کن (بالا را ببین)
2. یک **مدل GGUF** دانلود کن، مثلاً
   [Gemma 3 1B (GGUF)](https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main) از [Hugging Face](https://huggingface.co/)
3. اگر نسخه‌ات llama.cpp ندارد، نسخه‌ی ویندوز **llama.cpp** را از
   [صفحه‌ی releases](https://github.com/ggml-org/llama.cpp/releases) دانلود کن (مثلاً `llama-bXXXX-bin-win-cpu-x64.zip`)
4. **تنظیمات (⚙)** را باز کن ← **پوشه‌ی llama.cpp** (یا zip) و **پوشه‌ی مدل‌ها** را بده ← **اجرای مدل** را بزن ← گفتگو کن!

### اجرا از سورس

1. [Python 3.10+](https://www.python.org/downloads/) (ویندوز، **۶۴ بیتی / x64**) را نصب کن
2. نیازمندی‌ها را نصب کن:
   ```bash
   pip install -r requirements.txt
   ```
3. اجرا کن:
   ```bash
   python jizzai.py
   ```

### ساخت exe و نصاب توسط خودت (x64)

از **پایتون ۶۴ بیتی** استفاده کن. فایل‌های `jizzai.py`، `build.py`، `jizzai.iss`، `make_icon.py`، `icon.ico` و zip برنامه‌ی llama.cpp
(`llama-bXXXX-bin-win-cpu-x64.zip`) را در یک پوشه بگذار و اجرا کن:

```bash
python build.py
```

در پوشه‌ی `output/` این فایل‌ها ساخته می‌شوند:

- `JizzAI-<version>-Setup.exe` – نصاب (نیازمند [Inno Setup](https://jrsoftware.org/isinfo.php))
- `JizzAI-<version>-Portable.zip` – پوشه‌ی پرتابل همراه llama.cpp
- `JizzAI-<version>-Portable.exe` – exe پرتابل تک‌فایلی

گزینه‌های کاربردی: `--skip-installer` (بدون نیاز به Inno Setup)، `--skip-portable`، `--skip-single`،
`--single-llama` (گذاشتن llama.cpp داخل exe تکی — حجیم‌تر و دیرتر بالا می‌آید)، `--no-llama` و `--clean`.
همه‌ی گزینه‌ها ابتدای `build.py` توضیح داده شده‌اند.

### نکته‌ها

- **پوشه‌ی مدل‌ها** یا **پوشه / zip برنامه‌ی llama.cpp** را روی پنجره بکش؛ JizzAI تشخیص می‌دهد کدام است
- یک فایل `.gguf` را روی پنجره بکش تا به‌عنوان مدل انتخاب شود (فایل‌های `mmproj` از روی نامشان تشخیص داده می‌شوند)
- حالت پرتابل: `Portable.exe` تکی همیشه تنظیمات و گفتگوها را در پوشه‌ی `data/` کنار خودش نگه می‌دارد؛ در نسخه‌ی zip فایل `portable.flag` کنار exe همین کار را می‌کند
- برای تصویر به یک مدل بینایی **و** فایل `mmproj` آن نیاز است
- به ویندوز ۶۴ بیتی (x64) نیاز دارد؛ ویندوز ۳۲ بیتی پشتیبانی نمی‌شود

### لینک‌ها

- GitHub: [Mrmmd2004](https://github.com/Mrmmd2004)
- Telegram: [@Clubapp8](https://t.me/Clubapp8)

</div>
