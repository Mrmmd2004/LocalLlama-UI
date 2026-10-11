<p align="center">
  <img src="assets/banner.png" alt="8AI banner" width="100%">
</p>

<h1 align="center">8AI</h1>

<p align="center">
  A modern desktop chat app for running local LLMs with <a href="https://github.com/ggml-org/llama.cpp">llama.cpp</a>.<br>
  Fully offline · English + Persian (RTL) · Windows
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
</p>

[فارسی](README.fa.md)

<p align="center">
  <img src="assets/screenshot.png" alt="8AI screenshot" width="90%">
</p>

## Features

- Chat with any **GGUF** model through `llama-server` (llama.cpp) — nothing leaves your PC
- **English and Persian** interface (Persian switches the layout to right-to-left)
- Chat history with search, rename, delete and **export to Markdown**
- **Drag & drop** files: text/code, PDF, DOCX, XLSX, PPTX, ZIP and images (vision models)
- Dark / light theme, adjustable text size
- Sampling presets (precise / balanced / creative) and advanced parameters (top-k, top-p, min-p, mirostat, DRY, XTC, seed…)
- Shows the model's "thinking" separately from the answer, plus live status and speed stats
- Models folder scanner — pick any `.gguf` from a list, `mmproj` vision file is detected automatically
- Optional auto-start of the model when you press Send, and automatic chat titles
- **Portable mode** — keeps settings and chats next to the exe

## Requirements

| What | Version |
|------|---------|
| **Python** | **3.10 or newer** (3.12 recommended — see `.python-version`) |
| OS | Windows 10 / 11 |
| llama.cpp | a Windows build that contains `llama-server.exe` ([releases](https://github.com/ggml-org/llama.cpp/releases)) |
| Model | any `.gguf` file, e.g. [Gemma 3 1B](https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/tree/main) |

Check your Python version:

```bash
python --version
```

## Run from source

```bash
git clone https://github.com/Mrmmd2004/8AI.git
cd 8AI

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python 8ai.py
```

Then open **Settings** and choose:

1. **Engine** → the llama.cpp folder or zip (`llama-server.exe` is found automatically)
2. **Models** → the folder that contains your `.gguf` files
3. Press **Start model** and chat.

For images, use a vision model and set its `mmproj` file in Settings.

## Build the .exe / installer

```bash
pip install -r requirements-build.txt
python build.py
```

`build.py` creates, inside `output/`:

| File | What it is |
|------|------------|
| `8AI-<ver>-Setup.exe` | Installer (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)) |
| `8AI-<ver>-Portable.exe` | One single exe, no install |
| `8AI-<ver>-Portable.zip` | Portable folder |

Useful options: `--llama PATH`, `--no-llama`, `--skip-installer`, `--skip-portable`, `--skip-single`, `--clean`, `--version X.Y.Z`.
Run `python build.py -h` for the full list.

## Project structure

```
8AI/
├── 8ai.py                 # the whole app (PyQt6)
├── build.py               # one-command builder (PyInstaller + Inno Setup)
├── 8ai.iss                # Inno Setup script
├── make_icon.py           # generates icon.ico / icon.png
├── icon.ico  icon.png     # app icon
├── assets/                # README images (banner + screenshot)
├── requirements.txt       # run from source
├── requirements-build.txt # build the exe
└── .python-version        # recommended Python
```

## Where is my data?

- Normal install: `C:\Users\<you>\.8ai\` (settings + chats)
- Portable: the `data` folder next to the exe
- Crashes are logged to `crash.log` in the same folder

## Links

- GitHub: [Mrmmd2004](https://github.com/Mrmmd2004)
- Telegram: [@Clubapp8](https://t.me/Clubapp8)

## License

[MIT](LICENSE)
