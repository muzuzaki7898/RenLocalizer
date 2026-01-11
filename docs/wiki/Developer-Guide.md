# Developer & Contributor Guide

This guide is for developers who want to modify RenLocalizer or build their own extensions.

## 🏗️ Project Structure
- `src/core/`: The heart of the application.
  - `translation_pipeline.py`: Coordinates the entire process.
  - `parser.py`: The Regex-based extractor.
  - `rpyc_reader.py`: The AST-based binary unpickler.
- `src/gui/`: PyQt6-based interface components.
- `src/utils/`: Common helpers, constants, and configuration logic.
- `tools/`: Independent scripts for testing and debugging specific modules.

## 🧪 Testing with Tools
Before submitting a PR, use the scripts in the `tools/` folder to verify changes:
- `python tools/parser_smoke.py`: Tests the regex parser against common patterns.
- `python tools/performance_test.py`: Benchmark translation speed.
- `python tools/system_check.py`: Verifies current environment compatibility.

## ➕ Adding a New Translation Engine
1.  Inherit from `BaseTranslator` in `src/core/translator.py`.
2.  Implement `translate_single` and `translate_batch`.
3.  Add your engine to the factory in `src/core/translator.py`.
4.  Update `src/gui/tl_translate_dialog.py` to include the new option.

## 📦 Building Executables
We use PyInstaller to create the Windows standalone versions.
```bash
pip install pyinstaller
pyinstaller RenLocalizer.spec
```
The `.spec` file is pre-configured to include all assets, locales, and necessary hidden imports.

## 🗺️ Localization for RenLocalizer
To add a new UI language:
1.  Copy `locales/en.json` to `locales/YOUR_LANG.json`.
2.  Translate all strings.
3.  The app will automatically detect the new file on startup!
