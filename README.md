# RenLocalizer 2.0

![RenLocalizer Banner](https://raw.githubusercontent.com/Lord0fTurk/RenLocalizer/main/docs/banner.png)

**Advanced Ren'Py Translator & Localizer**  
*Professional-grade localization tool for Ren'Py visual novels, powered by AI and robust parsing.*

RenLocalizer is a sophisticated, cross-platform tool designed to automate the translation and localization of Ren'Py games. It combines traditional machine translation (Google, DeepL) with state-of-the-art LLMs (OpenAI, Gemini, Local LLMs) and a powerful context-aware parser to deliver high-quality translations while preserving game logic.

> **Status:** Active Development (v2.4.9)  
> **Supported Platforms:** Windows, macOS, Linux

---

## 🚀 Key Features

### 🤖 AI-Powered Translation
- **Local LLM Support:** Run completely offline using **Ollama**, **LM Studio**, or any OpenAI-compatible local server. (Unlock uncensored translations with models like `dolphin-mistral`).
- **OpenAI & OpenRouter:** seamless integration with GPT-3.5, GPT-4, and OpenRouter's vast model library.
- **Google Gemini:** Utilize Google's powerful Gemini Pro models.
- **Traditional Engines:** Google Translate (Web/API) and DeepL API support.
- **Smart Context:** AI prompts are engineered to understand Ren'Py context (dialogue vs. UI vs. code).

### 🛠️ Robust Parsing & Extraction
- **Native UnRPA Integration:** Built-in, cross-platform RPA archive extraction using the `unrpa` library. **No longer Windows-only!**
- **RPYC Decompilation:** Reads directly from compiled `.rpyc` files when source `.rpy` files are missing or obfuscated.
- **Deep Scan:** AST-based scanning to find hidden translatable strings in `init python` blocks and complex variable assignments.
- **Safe Injection:** intelligently handles Ren'Py control codes, interpolation variables (`[player_name]`), and style tags to prevent game crashes.

### ⚡ Performance & Workflow
- **Multi-Threaded Pipeline:** Configure up to 256 threads for blazing fast traditional translations.
- **Smart Batching:** Dynamic batching algorithms to maximize API throughput.
- **Proxy Rotation:** Built-in proxy manager to handle rate limits for free tier usage.
- **Dictionary & Glossary:** Enforce specific terminology across the entire game.

### 🖥️ Modern UI & CLI
- **Fluent Design:** A beautiful, responsive dark-mode GUI built with `PyQt6-Fluent-Widgets`.
- **Command Line Interface:** Full-featured CLI for headless servers, automation scripts, or power users.
- **Project Health Check:** Automated diagnostics to find potential issues in your project structure.

---

## 📥 Installation

### Pre-built Executables
Download the latest release for your platform from the [Releases Page](https://github.com/Lord0fTurk/RenLocalizer/releases).
- **Windows:** `RenLocalizer.exe` (GUI) / `RenLocalizerCLI.exe` (CLI)
- **macOS/Linux:** Run from source or use the provided build scripts.

### Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Lord0fTurk/RenLocalizer.git
   cd RenLocalizer
   ```

2. **Set up environment:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python run.py       # GUI Mode
   python run_cli.py   # CLI Mode
   ```

---

## 📖 Usage Guide

### GUI Mode
1. **Select Game:** Drag & drop your game's EXE or folder.
2. **Scan:** The tool detects RPA archives and extracts them automatically if needed.
3. **Configure:** Choose your target language and translation engine (e.g., Local LLM).
4. **Translate:** Click "Start Translation". Real-time progress and logs are shown.

### CLI Mode
New in v2.4: The CLI now supports full automatic extraction and translation on **all platforms**.

**Interactive Menu:**
```bash
python run_cli.py
```

**Direct Command:**
```bash
# Translate a game directory to Turkish using Local LLM
python run_cli.py "/path/to/game" --target-lang tr --engine local_llm --mode full

# Translate existing files using Google Translate
python run_cli.py "/path/to/project" --target-lang es --engine google --mode translate
```

**Supported CLI Options:**
| Option | Description |
|--------|-------------|
| `--mode` | `full` (Extract+Translate), `translate` (Text only), `auto` (Detect) |
| `--engine` | `google`, `deepl`, `openai`, `gemini`, `local_llm` |
| `--target-lang` | Target language code (e.g., `tr`, `es`, `ru`) |
| `--deep-scan` | Enable AST-based deep scanning for hidden text |

---

## ⚙️ Configuration

Settings are saved in `config.json`. You can also configure them via the GUI Settings page.

**Key AI Settings:**
- **Provider:** OpenAI, Gemini, Local
- **Model:** `gpt-3.5`, `gemini-pro`, `llama3`, etc.
- **Base URL:** Customizable for OpenRouter or LocalAI (e.g., `http://localhost:11434/v1`).
- **Safety:** Temperature, Timeout, Retries.

---

## 🤝 Contributing & Support

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- **Report Issues:** Use the [GitHub Issues](https://github.com/Lord0fTurk/RenLocalizer/issues) tab.
- **Support Us:** If you find this tool useful, consider supporting development on [Patreon](https://www.patreon.com/Lord0fTurk).

## 📄 License
Licensed under the **GPL-3.0 License**. See [LICENSE](LICENSE) for details.

---
*Created by the RenLocalizer Team.*
