# 🖥️ Command Line Interface (CLI) Usage

The RenLocalizer CLI (`run_cli.py`) is designed for automation, remote server usage, or advanced batch processing.

---

## 🚀 Basic Usage
Launch the CLI without arguments to enter the **Interactive Mode**:
```bash
python run_cli.py
```

---

## 🛠️ Direct Commands (Automation)
For automation, pass arguments directly. 

### **Example: Translate Project to Spanish**
```bash
python run_cli.py "/path/to/game" --target-lang es --engine local_llm --mode full
```

### 📋 Argument Reference

| Argument | Description |
| :--- | :--- |
| `--target-lang` | Code of the target language (e.g., `tr`, `es`, `ru`). |
| `--engine` | `google`, `deepl`, `openai`, `gemini`, `local_llm`. |
| `--mode` | `full` (Extract + Translate) or `translate` (Translate existing files). |
| `--deep-scan` | Enable AST-based deep scanning. |
| `--rpyc-reader` | Read directly from binary RPYC files. |
| `--force-ui` | Force translation of all UI elements. |

---

## 🌟 Modes Explained

*   **Full Mode (`--mode full`):** The comprehensive workflow. It expects a game directory or EXE. It extracts RPA archives, normalizes encodings, and translates everything.
*   **Translate Mode (`--mode translate`):** For projects that are already unpacked. It scans for `.rpy` / `.rpymc` files and performs the text translation.

---

## 🤖 Server & Headless Usage
The CLI version is lightweight and doesn't require a GUI. You can run it on a Linux VPS or in a **GitHub Action**:

```bash
# Example script for a cloud server
python run_cli.py "./GameProject" \
  --target-lang tr \
  --engine gemini \
  --mode full \
  --deep-scan
```

---

## 📋 Logs & Troubleshooting
In case of failure, the CLI writes a detailed diagnostic report to **`error_output.txt`** in the project root. Check this file to see which file or line caused the issue.
