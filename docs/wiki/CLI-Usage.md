# Command Line Interface (CLI) Usage

The RenLocalizer CLI (`run_cli.py`) is a powerful way to automate translations, run on remote servers, or integrate into a build pipeline.

## 🚀 Basic Usage
You can run the CLI interactively by launching it without arguments:
```bash
python run_cli.py
```

## 🛠️ Direct Commands
For automation, use arguments. Here is a common command to translate a game folder into Spanish using a Local LLM:

```bash
python run_cli.py "/path/to/game" --target-lang es --engine local_llm --mode full
```

### 📋 Argument Reference

| Argument | Description |
|-----------|-------------|
| `--target-lang` | Target language code (e.g., `tr`, `en`, `es`, `ru`). |
| `--engine` | `google`, `deepl`, `openai`, `gemini`, `local_llm`. |
| `--mode` | `full` (Extract + Translate), `translate` (Translate existing files), `auto` (Detect). |
| `--deep-scan` | Enable AST-based deep scanning for hidden strings. |
| `--rpyc-reader` | Read directly from RPYC files (useful for obfuscated games). |
| `--force-ui` | Force translation of UI elements (buttons, labels). |

## 🌟 Modes Explained
- **Full Mode:** Expects a game directory or EXE. It extracts RPA archives, normalizes encodings, and then translates.
- **Translate Mode:** Expects a directory already containing `.rpy` or `.rpymc` files. It only performs text translation of the existing files.

## 🤖 Server Automation
The CLI version is lightweight and doesn't require a GUI (Headless). You can run it on a Linux VPS or in a GitHub Action:

```bash
# Headless translation in a script
python run_cli.py "./ProjectX" --target-lang tr --engine gemini --deepl-key YOUR_KEY --mode full
```

## 🛠️ Error Logging in CLI
In case of failure, the CLI writes a detailed diagnostic report to `error_output.txt` in the root folder. Check this file to see which file or line caused the issue.
