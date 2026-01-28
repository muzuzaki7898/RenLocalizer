# 🛠️ Developer & Contributor Guide

This guide is for developers looking to modify RenLocalizer, add new features, or contribute to the core engine.

---

## 🏗️ Project Architecture
The project is split into logical components:

*   📂 **`src/core/`**: The heart of the application.
    *   `translation_pipeline.py`: Orchestrates the entire flow (Extract -> Parse -> Translate -> Save).
    *   `parser.py`: The high-performance Regex extractor.
    *   `rpyc_reader.py`: The binary unpickler for compiled scripts.
*   📂 **`src/gui/`**: PyQt6 + QML (Fluid Design) interface.
    *   `qml/`: Contains all .qml files for the UI.
    *   `settings_backend.py`: Bridges settings between Python and QML.
*   📂 **`src/utils/`**: Shared helpers, configuration manager, and constants.
*   📂 **`tools/`**: Standalone scripts for testing and debugging.

---

## 🧪 Testing Your Changes
Before submitting a PR, please run the following sanity checks:

1.  **Parser Smoke Test:** `python tools/parser_smoke.py` (Tests common Ren'Py patterns).
2.  **Performance Check:** `python tools/performance_test.py` (Benchmarking).
3.  **Environment Check:** `python tools/system_check.py` (Verify library compatibility).

---

## ➕ Adding a New Translation Engine
1.  Inherit from `BaseTranslator` in `src/core/translator.py`.
2.  Implement `translate_single` and `translate_batch`.
3.  Register your engine in the factory within `src/core/translator.py`.
4.  Update the UI logic in `src/backend/app_backend.py` to recognize the new engine enum.

---

## 📦 Building Standalone Executables
We use **PyInstaller** for Windows distributions.

```bash
# Install PyInstaller
pip install pyinstaller

# Build using the spec file (recommended)
pyinstaller RenLocalizer.spec
```
> 💡 **Note:** The `.spec` file handles all assets, locales, and hidden imports automatically.

---

## 🗺️ UI Localization
To add a new language to the RenLocalizer interface:
1.  Copy `locales/en.json` to `locales/YOUR_CODE.json`.
2.  Translate the strings.
3.  Restart the app—it will be detected automatically!

---
> 🚩 **Issues:** Found a bug? [Report it here](https://github.com/Lord0fTurk/RenLocalizer/issues).
