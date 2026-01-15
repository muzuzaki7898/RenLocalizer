# Changelog



## [2.5.0] - 2026-01-14
### 🚀 New Features (Major)
- **Force Runtime Translation:** Added "Force Runtime Translation" (Zorla Çeviri) feature. This dynamically injects a `01_renlocalizer_runtime.rpy` script into the game folder. It hooks into Ren'Py's `config.replace_text` to translate strings lacking the `!t` flag at runtime, ensuring 100% translation coverage for dynamic strings without manual code edits.
- **Improved Placeholder Protection:** Fixed a critical issue where Python variables inside Ren'Py bracket expressions (e.g., `[page['episode']]`) were being corrupted by translation. Expanded technical string filtering to protect internal property access and complex dictionary patterns.

### 🛠️ Core Fixes (Quest System & Parsing)
- **Quest Text Extraction Fix:** Resolved a critical issue where multi-line quest descriptions embedded in Python data structures (lists/dictionaries) were being skipped or incorrectly parsed.
- **Improved Trailing Text Cleanup:** Fixed a bug in the parser that caused trailing commas or brackets to leak into extracted strings, preventing valid translations.
- **Untranslated Text Detection:** Fixed a logic error where empty translations (`new ""`) in existing files were sometimes treated as "translated," preventing them from being processed.
- **Global Deduplication:** Implemented aggressive deduplication for `strings.rpy` generation to prevent file bloating (reduced file size by ~70% in large projects) and eliminate duplicate translation requests.
- **ID Generation Stability:** Enhanced the Translation ID generation algorithm to be more robust against escape sequences and newline variations.

### 🗺️ Cross-Platform & UI
- **Cross-Platform Game Selection:** Enhanced game path selection to be fully compatible with Windows, macOS, and Linux.
- **Platform-Aware Filtering:** Added specific file filters and dialog titles for different operating systems (.exe for Windows, .app/.sh for macOS, .sh/binary for Linux).
- **Browse Folder Support:** Added a "Browse Folder" option for direct directory selection, improving flexibility for game project identification.
- **Intelligent Root Detection:** Improved pipeline logic to automatically locate the `game/` subdirectory regardless of the initial selection (executable or folder).
- **Localization Expansion:** Updated all 8 supported languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) with new localization keys for cross-platform selection, platform-specific placeholders, and titles.

### ⚡ Core & Performance (Major Update)
- **Smart Skip (Incremental Translation):** Added the ability to automatically detect and skip already translated lines (where the `new` string is not empty). This allows for lightning-fast incremental updates when a game version changes, saving API costs and time.
- **Resume System:** Implemented a persistent progress tracking system. If the translation is interrupted (power outage, manual stop), you can now resume exactly where you left off.
- **Aggressive Translation Retry:** Specialized retry mechanism for LLM engines. If the initial translation returns the original text, the engine now automatically retries with a "Force Translation" prompt.
- **Maintenance:** Permanently removed legacy "Output Format" selection. The system now defaults to the most stable `old_new` format to ensure 100% compatibility with Ren'Py script updates.
- **Robust Config Loading:** Implemented a filtering mechanism that ignores unknown configuration keys in the JSON file. This prevents "unexpected keyword argument" crashes when downgrading versions or moving between builds with different settings.

### � Performance & UI Responsiveness
- **UI Throttling (Anti-Freeze):** Implemented a log buffering system with a `QTimer` (200ms) to prevent UI freezing during high-frequency logging. The application now remains fully responsive (draggable/clickable) even while processing thousands of files per second.
- **Multithreading GIL Yields:** Added microscopic `time.sleep` yields in tight parsing and file generation loops. This allows the Python Global Interpreter Lock (GIL) to release more frequently, ensuring the UI thread stays alive and smooth during heavy CPU-bound tasks like scanning tens of thousands of script lines.
- **Regex Optimization:** Optimized core translation logic by pre-compiling overhead-heavy regular expression patterns. This significantly reduces CPU usage during the "protection" and "restoration" phases of translation.
- **Efficiency:** Optimized translation file generation by caching relative path calculations, reducing redundant OS calls during massive project writes.
- **Signal Multi-threading Efficiency:** Reduced main-thread overhead by eliminating redundant "debug" level signal emissions in tight processing loops.

### 🔍 Parser Optimization & Accuracy
- **Smart Directory Targeting:** The parser now automatically prioritizes the `game/` folder when a project root is selected, ensuring only relevant assets are scanned.
- **Strict File Type Enforcement:** Restricted scanning to core Ren'Py files (`.rpy`, `.rpyc`, `.rpym`, `.rpymc`). Other common but non-essential files (JSON, CSV, TXT, etc.) are now skipped to prevent "translation noise".
- **Advanced System Filter:** Added comprehensive exclusion rules for internal folders like `cache/`, `renpy/`, `saves/`, `tmp/`, and `python-packages/`.
- **Binary/Corrupted String Filter (RPYC Safety):** Added robust detection and filtering for corrupted strings from `.rpyc` files:
    - Unicode Replacement Character (`\ufffd`) detection.
    - Private Use Area character filtering (`\uE000-\uF8FF`).
    - Control character detection (`\x00-\x1F`, `\x7F-\x9F`).
    - High ratio of non-printable character analysis (>30% threshold).
    - Low alphabetic content detection (<20% ratio).
    - Short string corruption pattern matching for strings like `"z�X�"`, `"|d�T"`, `"qu�p��"`.
- **Python Code / Docstring Detection (Critical Fix):** New filter to prevent game-breaking translations of embedded code:
    - Detects Python keywords: `def`, `class`, `for`, `if`, `import`, `return`, `raise`, `try`, `except`, `while`, `lambda`, `with`.
    - Filters Ren'Py module calls like `renpy.store.x`, `renpy.block_rollback()`.
    - Skips string concatenation expressions: `"inventory/"+i.img+".png"`.
    - Protects internal dict access patterns: `_saved_keymap[key]`.
    - Filters boolean/None assignments: `x = True`, `y = False`, `z = None`.
- **Python Built-in Function Calls Filter:** Added detection for Python built-in function calls (`str()`, `int()`, `len()`, etc.) that should never be translated.
- **Default Dict/List String Extraction (Quest System Fix):** New extraction capability for strings inside `default` statement dict/list literals:
    - Handles `default quest = {"anna": ["Start by helping her..."]}` patterns.
    - Extracts translatable quest descriptions, schedule entries, and objectives.
    - Intelligent filtering to skip dict keys, short technical strings, and file paths.
- **Short Technical Words:** Added filter for common programming identifiers (`img`, `id`, `val`, `cfg`, etc.) that should never be translated.
- **Enhanced Technical String Filtering (Official Documentation Update):**
    - **Documentation-Driven Expansion:** Significantly expanded the `renpy_technical_terms` list based on a deep dive into official Ren'Py documentation, including transitions, motion commands, and engine keywords.
    - **Advanced Screen Language Filtering:** Added support for advanced UI elements like `hotspot`, `hotbar`, `areapicker`, `draggroup`, `showif`, and `vpgrid`.
    - **Deep Python Integration Safety:** Added comprehensive filtering for Python technical types (`Callable`, `Literal`, `Self`) and a full set of internal exception classes (`AssertionError`, `TypeError`, etc.) to prevent code-leaks in translation.
    - **Smart Heuristics:**
        - **Internal Identifier Protection:** Now automatically skips all underscore-prefixed strings (e.g., `_history`, `_confirm`) which are reserved for Ren'Py's internal use.
        - **System File Filtering:** Automatically skips strings derived from internal indexing files (starting with `00`).
        - **Namespace Awareness:** Strengthened detection for `config.`, `gui.`, `preferences.`, and `style.` namespaces.
    - **CamelCase & Dot-notation Detection:** Improved detection to automatically skip technical identifiers, module attributes, and code-like strings.


### 🌐 Expanded Language Support
- **Massive Source Language Expansion:** Increased the number of supported source languages from 37 to over 90, covering nearly every major language for a truly global translation experience.
- **Improved Native Names:** Standardized native language names in the UI for better accessibility.

### ⚙️ Translation Engine Improvements
- **DeepL Improvements:**
  - Added 3-attempt exponential backoff retry for transient network errors.
  - New "Formality" setting (Formal/Informal) for supported languages.
  - Fixed critical undefined variable bug in exception handler.
- **DeepL Tag Protection:** Automatically fixes spacing errors inside Ren'Py tags (e.g., `{ i }` → `{i}`).
- **AI Token Tracking:** OpenAI and Gemini now log token usage for better cost monitoring.
- **Optimization:** Implemented centralized request deduplication to prevent redundant API calls across all engines.
- **Resilience:** Added "Mirror Health Check" system for Google Translate to automatically detecting and bypassing failing endpoints.
- **Google Batch Fix:** Fixed a critical `AttributeError: _endpoint_failures` that occurred during multi-endpoint batch translation.
- **Mirror Ban Logic:** Implemented a temporary ban system (5 minutes) for Google Translate mirrors that consistently return 429 (Too Many Requests) or other errors, ensuring the pipeline quickly shifts to healthy mirrors.
- **Smart Concurrency:** Introduced adaptive rate-limit handling for OpenAI/Gemini that dynamically adjusts concurrency upon encountering 429 errors.

### 🖥️ Local LLM & Jan.ai
- **Jan.ai Support:** Added Jan.ai as a built-in preset in Local LLM settings (URL: `http://localhost:1337/v1`).
- **Uncensored Model Presets:** Categorized model dropdown for NSFW VN translation (Sansürsüz, LM Studio, Standart).
- **Separated Model Input:** Free-text model name input with a separate preset dropdown.

### 🍱 Localization & UI
- **Engine Transparency:** Added "(Experimental)" labels to non-Google engines.
- **Localized LLM Categories:** "Uncensored", "LM Studio", and "Standard" categories are now fully localized in all 8 supported languages.
- **DeepL Formality UI:** New setting card in API Keys section.
- **Global Label Sync:** Comprehensive update for `tr`, `en`, `de`, `es`, `ru`, `fr`, `zh-CN`, and `fa` locales.
- **Settings UI Localization Fix:** Fixed hardcoded Turkish fallback strings in Settings Interface (AI Settings, Proxy Settings, Advanced sections) that were appearing in English mode.

## [2.4.10] - 2026-01-11
### 🛡️ Ren'Py Engine Protection & Stability
- **Engine Isolation:** Explicitly excluded `renpy/common` and internal `renpy/` directories from scanning to prevent engine-level scripts from being corrupted by translation.
- **Automatic Cleanup:** Added a post-extraction cleanup step to remove any accidental engine-level translation files from the `tl/` directory.
- **Smart Technical Filtering:** Integrated advanced regex detection and symbol density heuristics to automatically skip internal Ren'Py code and technical regex patterns.

### 🌐 Translation Pipeline & API Management
- **Advanced API Quota Handling:**
  - Implemented a dedicated `quota_exceeded` flag in `TranslationResult` for more robust error handling.
  - Replaced brittle string matching for API limits with proper status code and boolean checks for DeepL, OpenAI, and Gemini.
  - The system now gracefully stops translation and provides a localized warning when API limits are reached.
- **Localized Stage Logging:**
  - Completely localized the pipeline stage labels (e.g., `[🌐 Translating...]`, `[✅ Validating...]`).
  - Improved `ConfigManager.get_log_text()` to support default values and cleaner error reporting.
  - Refined error log formatting to handle cases where file or line information is missing.

### 🍱 Localization & Global Support
- **Full Sync across 8 Languages:** Fully synchronized and updated `tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, and `fa` locale files.
- **Pipeline Log Localization:** Added missing keys for all pipeline stages and API errors across all supported languages.
- **Persian (FA) Locale Fix:** Restructured the `fa.json` file to fix duplicate keys and missing pipeline log sections.

### 🔍 Parsing & Extraction Improvements
- **Better Dialogue Support:**
  - Added support for dot-separated character names (e.g., `persistent.player_name`).
  - Enhanced narrator dialogue detection to support trailing transitions (e.g., `"Hello" with dissolve`).
  - Relaxed strict length filters for non-Latin languages to capture short but meaningful dialogues (e.g., Russian "Я", "Да").
- **Scanning Robustness:** Synchronized dot-separated character name support across both Regex and AST-based extraction pipelines.

### 🌐 Translation Engine Improvements
- **Smart Retry for Unchanged Translations (Optional):** Added "Agresif Çeviri" (Aggressive Translation) toggle in settings. When enabled, the system automatically retries unchanged translations with Lingva Translate and alternative Google endpoints. This significantly reduces the number of untranslated strings, especially for Cyrillic (Russian) to other language pairs. Disabled by default for optimal speed.
- **Enhanced Placeholder Protection:** Fixed a critical bug where nested bracket patterns like `[page['episode']]` or `[comment['author']]` were being incorrectly translated. The new parser properly handles dictionary access patterns, method calls, and nested quotes inside variable interpolations.
- **Technical String Filter:** Added filter for Ren'Py internal identifiers (e.g., `renpy.dissolve`, `renpy.mask renpy.texture`) to prevent them from appearing in translation output.

### 🐛 Bug Fixes & Stability
- **ConfigManager TypeError:** Fixed `TypeError` in `get_log_text()` call by adding proper default parameter support.
- **Duplicate Key Clean-up:** Removed redundant `error_api_quota` keys from root level in all locale files to prevent conflicts.
- **RPYC Reader AST Module Support:** Fixed `Disallowed global: _ast.Module` error when reading `.rpymc` (screen cache) files by whitelisting Python's `_ast` module in the safe unpickler.
- **Pipeline UnboundLocalError Fix:** Resolved a crash where the variable `tl_dir` was accessed before definition during the engine cleanup phase.
- **Duplicate Translation Entry Fix:** Resolved Ren'Py "already exists" errors by excluding the `tl/` directory from scanning and implementing deduplication against pre-existing translation files.
- **Update Checker Fix:** Resolved a critical crash that occurred when the GitHub update check returned inconsistent or erroneous metadata.
- **CLI RPA Robustness:** Fixed an issue where RPA extraction would fail in CLI mode when the game path points to a directory instead of an executable.
- **Font Warning Mitigation:** Resolved multiple `QFont` console warnings by removing and standardizing legacy font settings.

## [2.4.9] - 2026-01-09
### 🚀 AI Performance & Batch Processing
- **Batch Translation Support:** Added batch translation for OpenAI, Gemini, and Local LLM engines.
  - Significantly improved translation speed (5-10x) and reduced API costs.
  - Implemented an XML-based smart tagging system to protect Ren'Py syntax during batch operations.
- **Refactored AI Settings UI:** Reorganized AI settings into three main categories:
  - **Model Parameters:** Temperature and Max Tokens settings.
  - **Connection Settings:** Timeout and retry count settings.
  - **Speed & Performance:** Concurrency and request delay control.
- **Rate Limiting & Stability:** Integrated semaphore-based concurrency control and jittered delay mechanisms to minimize API rate limit issues.

### 🍱 Localization & Language Support
- **Full Sync:** Synchronized all localization files (`tr`, `en`, `de`, `fr`, `es`, `fa`, `ru`, `zh-CN`) to 100% completeness.
- **Turkish Improvements:** Completed 14+ missing critical keys in `tr.json`, ensuring the UI is fully localized in Turkish.
- **Enhanced System Prompts:** Updated AI system prompts across all languages to maintain a professional localizer tone and ensure uncensored translation of NSFW content.

### 🛠️ CI/CD & Infrastructure
- **Windows Build Automation:** GitHub Actions (`release.yml`) now automatically builds and releases Windows packages.
- **Python Stability:** Standardized Python version to `3.12` in CI/CD pipelines for better compatibility and stability.
- **Code Cleanup:** Removed and standardized legacy Turkish debug logs within the translation pipeline.

## [2.4.8] - 2026-01-08
### 🚀 New Features: Local LLM Support
- **Full Local LLM Integration:** Added dedicated "Local LLM" engine in translation options.
  - Supports **Ollama**, **LM Studio**, and other OpenAI-compatible local endpoints.
  - No API key required (uses "local" as placeholder).
  - Default model: `llama3.2`, Default URL: `http://localhost:11434/v1`.
- **Advanced AI Settings:**
  - Configurable `Temperature`, `Timeout`, `Max Tokens`, and `Retry Count`.
  - Custom System Prompt support for fine-tuning translation persona.

### 🧹 Code Health & Maintenance
- **Project Structure Audit:** Conducted a comprehensive health check.
  - **Magic Numbers Refactored:** Moved hardcoded values (timeouts, token limits, window sizes) to a centralized `src/utils/constants.py`.
  - **Localization Sync:** Ensured `translation_engines` list and new AI settings are 100% localized across all 7 supported languages (tr, en, de, fr, es, ru, zh).
  - **Dynamic UI Labels:** Fixed several hardcoded text labels in Settings UI to properly use the localization system.
- **UI Cleanup:**
  - Removed obsolete "Show Detailed Help" button from About page (functionality moved to Info Center).
  - Updated OpenAI engine label to simply "OpenAI / OpenRouter" to reduce confusion.

## [2.4.7] - 2026-01-06
### 🐛 Bug Fixes
- **PyInstaller UnRPA Fix:** Fixed critical bug where RPA extraction would fail in packaged executables.
  - **Root Cause:** `sys.executable` points to the bundled `.exe` instead of Python interpreter in frozen environments.
  - **Solution:** Replaced subprocess-based `python -m unrpa` calls with direct `unrpa` library API.
- **UnRPA 2.3.0 API Compatibility:** Fixed API mismatch with unrpa library.
  - **Root Cause:** unrpa 2.3.0 doesn't have a `path` parameter - it extracts to current working directory.
  - **Solution:** Temporarily change working directory with `os.chdir()` before extraction.

### ✨ New Features
- **Native RPA Parser Fallback:** Added built-in RPA archive parser (`rpa_parser.py`) that works without external dependencies.
  - Automatically used when `unrpa` fails to import in frozen PyInstaller builds.
  - Supports RPA-3.0 and RPA-2.0 formats (covers 99% of Ren'Py games).
  - **Result:** RPA extraction is now guaranteed to work in all environments.

### 🐛 CLI Fixes
- **Fixed CLI `translate` Subcommand:** The CLI was incorrectly entering interactive mode even when path was provided.
  - **Root Cause:** Argparse conflict between main parser and subparser `input_path` argument.
  - **Solution:** Renamed legacy argument to avoid namespace collision.
- **Fixed CLI Directory Path Support:** CLI now accepts both `.exe` files and directory paths for `--mode full`.
  - **Root Cause:** Pipeline validation only accepted file paths, not directories.
  - **Solution:** Updated `configure()` and `_run_pipeline()` to handle both file and directory inputs.
  - **Result:** CLI can now properly extract RPA archives and translate games when given a folder path.
- **Smart Mode Detection:** CLI now automatically detects Ren'Py projects by checking for `game/` subfolder.
  - Directories with `game/` subfolder automatically use `full` mode (RPA extraction + translation).
  - Other directories use `translate` mode (direct translation of existing files).

## [2.4.6] - 2026-01-05
### 🐛 Bug Fixes
- **Update Checker Crash Fix:** Fixed a critical crash on startup caused by the update checker system.
  - **QTimer Delay:** Update check now runs 1 second after window initialization to ensure all UI components are ready.
  - **InfoBar/QMessageBox Overlap:** Removed duplicate InfoBar before QMessageBox to prevent Qt event loop conflicts.
  - **Format Placeholder Fix:** Fixed `KeyError` caused by mismatched format placeholders (`{version}` vs `{latest}/{current}`).
  - **Error Handling:** Added comprehensive try/except and null checks for robustness.

## [2.4.5] - 2026-01-05
### 🔄 Major Architecture Change: UnRPA for All Platforms
- **Unified Extraction:** Now uses `unrpa` Python library on ALL platforms (Windows, Linux, macOS) instead of unreliable batch scripts.
- **Simplified Codebase:** Removed 140+ lines of legacy Windows batch script handling code.
- **Reliable Extraction:** No more "HTTP 404" errors from UnRen download links - just `pip install unrpa`.
- **RPYC-Only Mode:** When `.rpy` files are not found, the pipeline reads directly from `.rpyc` files.
- **Ren'Py 8.x Optimized:** Fully compatible with modern Ren'Py RPAv3 archives.

### 🛠️ Tools Interface
- **Streamlined UI:** Removed old "Run UnRen" and "Redownload" buttons.
- **New Standard:** Single, reliable "RPA Arşivlerini Aç" button powered by `unrpa`.
- **Cleanup:** Removed deprecated `UnRenModeDialog`.

### 🔧 Bug Fixes
- **Fixed `force_redownload` error:** Method was missing from UnRenManager (now removed as unnecessary).
- **Custom Path Fix:** Fixed bug in `get_custom_path()` where variable was used before being defined.

### 🧹 UI Cleanup
- **Removed Output Format Setting:** Always uses stable `old_new` format now.

### 📦 Dependency
- **Required:** `pip install unrpa` (added to requirements.txt)

## [2.4.4] - 2026-01-04
### 🎨 Theme System Overhaul
- **New Themes:** Added **Green (Nature/Matrix)** and **Neon (Cyberpunk)** themes, bringing the total to 6 distinct options.
- **Improved Dark Theme:** Deepened the dark theme colors for better immersion and reduced "grayness".
- **Visual Fixes:** Resolved "blocky" black backgrounds on text labels by enforcing transparency rules (`background-color: transparent !important`).
- **Dynamic Switching:** Theme changes now apply **instantly** without requiring an application restart.
- **Fix:** Fixed a critical bug where the theme selector always reverted to "Dark" due to a `qfluentwidgets` compatibility issue with `itemData`.
- **Fix:** Eliminated `QFont::setPointSize` console warnings by refining stylesheet scoping.

## [2.4.3] - 2026-01-04
### 🐛 Bug Fixes
- **PseudoTranslator Placeholder Fix:** Fixed critical bug where `PseudoTranslator` was corrupting Ren'Py placeholders (e.g., `[player]`, `{color=#f00}`) during text transformation. The engine now splits text by placeholder markers and only applies pseudo-transformation to non-placeholder segments.

### 🧹 Cleanup
- **Removed Unused Files:** Deleted obsolete debug scripts (`debug_font.py`, `debug_themes.py`) and unused modules (`base_translator.py`, `qt_translator.py`).
- **Light Theme Fix:** Implemented comprehensive stylesheet overrides to fix the "color mess" in Light Theme, ensuring all UI elements (navigation, headers, cards) are correctly styled.

## [2.4.2] - 2026-01-03
### 📦 Build & Distribution
- **One-Dir Build:** Switched to folder-based release for better startup speed and debugging.
- **Cross-Platform Scripts:** Added `RenLocalizer.sh` and `RenLocalizerCLI.sh` for easy launching on Linux/macOS.
- **Hidden Imports:** Fixed `ModuleNotFoundError` by correctly collecting all submodules in `RenLocalizer.spec`.

### 🐛 Bug Fixes
- **Glossary Editor:** Fixed crash when opening Glossary Editor in packaged builds.

## [2.4.1] - 2026-01-02
### ✨ New Features
- **Patreon Integration:** Added a support button to the main UI.

## [2.4.0] - 2026-01-01
### 🚀 Major Update: Unreal Engine Support
- **Unreal Translation:** Added basic support for unpacking and translating Unreal Engine games (`.pak` files).
- **AES Key Handling:** Integrated AES key detection for encrypted PAK files.

## [2.3.0] - 2025-12-28
### 🌍 RPG Maker Support
- **RPG Maker MV/MZ:** Added support for translating RPG Maker JSON files.
- **RPG Maker XP/VX/Ace:** Added support for Ruby Marshal data files.

## [2.2.0] - 2025-12-26
### 🤖 CLI Deep Scan
- **Deep Scan:** Added `--deep-scan` argument to CLI for AST-based analysis of compiled scripts.

## [2.1.0] - 2025-12-24
### 💅 UI Improvements
- **Fluent Design:** Migrated to `PyQt6-Fluent-Widgets` for a modern look and feel.

## [2.0.0] - 2025-09-01
### 🎉 Initial Release
- **Core:** Ren'Py translation support, multi-engine translation (Google, Bing, DeepL), modern GUI.
