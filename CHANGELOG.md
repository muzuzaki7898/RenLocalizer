# Changelog

## [2.6.2] - 2026-02-01
### 🔧 Gemini Fix & Critical Safety Patch
- **Gemini Model Update:** Changed the default Gemini model from `gemini-2.0-flash-exp` (experimental) to `gemini-2.5-flash` (latest stable). This resolves issues where the API key would not work due to model access restrictions.
- **Zero-Tolerance Syntax Check:** Added a strict "Unbalanced Bracket Detector" to the integrity check phase. If a translation ends with an open bracket, it is immediately rejected.
- **Data Integrity (Atomic Save):** Implemented "Atomic Write" strategy for configuration files. `config.json` is now written to a temporary file first and safely renamed, ensuring zero data corruption even if the PC crashes or power is lost during save.
- **Thread-Safe Architecture:** Added `threading.Lock` to `ConfigManager` and a global `isBusy` lock to the Backend. This prevents race conditions and ensures thread safety across the entire application.
- **Refactoring & Reliability:** Extracted critical syntax protection logic into `SyntaxGuard`, fixed validation logic for escaped brackets (`[[`), and verified system stability with extensive edge-case stress tests.
- **Performance Boost (No Stuttering):** Moved heavy I/O operations (SDK Cleanup, UnRPA, Cache Loading) to background threads. This eliminates UI freezes/stuttering during large project operations.
- **Concurrency Safety:** Implemented a backend Locking Mechanism (`isBusy`) to prevent users from accidentally starting multiple heavy tasks simultaneously, which could cause crashes or data corruption.
- **Theme Independence:** The application now strictly ignores system-wide theme settings (like Windows Light Mode) and enforces the user's preferred theme (Default: Dark) from `config.json` immediately at startup.
- **Security Hardening:** Implemented centralized log masking for API keys AND automatic input sanitization (whitespace trimming) for all user settings.
- **Micro-Optimization:** Moved Regex compilation out of hot loops in `ai_translator.py`, significantly reducing CPU overhead during batch processing.
- **AI Hallucination Cleanup:** Implemented a pre-processor that fixes common AI formatting glitches like double-open-brackets (`[ [v0]`) before they can cause syntax errors.
- **Enhanced Google Translate Protection:** Specifically targeted improvements for Google Translate's tendency to corrupt bracket syntax (e.g., adding spaces `[ variable ]` or breaking interpolation chains). The new validation logic now catches these subtle corruptions that previously passed basic checks.
- **Advanced AST Code Validation:** Implemented Python's Abstract Syntax Tree (AST) analysis to validate the *semantic* correctness of restored placeholders. If a placeholder contains invalid Python syntax (e.g. `[player name]` instead of `[player_name]`), it is rejected even if the brackets are balanced.
- **Full Bracket Cycle Check:** Expanded the integrity check to detect "Unopened Closing Brackets" (e.g. `text]`) and nested brackets, ensuring complete structural integrity before approving any translation.
- **Smart Integrity Retry:** If a translation fails the safety check (e.g., bracket error), the system automatically retries 2 more times with different servers. This reduces the number of untranslated lines by up to 60%.

### 🐛 Bug Fixes (2026-02-01 Hotfix)
- **Aggressive Retry Setting Fix:** Fixed a critical bug where the "Aggressive Retry" setting was not being read from config. The code was looking for `aggressive_retry` instead of the correct `aggressive_retry_translation` property name, causing the feature to always be disabled regardless of user settings.
- **Placeholder Spacing Auto-Fix:** Added automatic cleanup for AI-induced placeholder spacing issues. Google Translate and some AI models would corrupt `[[t0]]` to `[[ t0 ]]`, breaking Ren'Py syntax. The system now auto-fixes these during the restore phase.
- **Duplicate Config Entry:** Removed a duplicate `enable_fuzzy_match` definition in `TranslationSettings` that could cause unpredictable behavior.
- **Cache Clear Confirmation:** Updated the cache clearing confirmation message in all 8 locales to explicitly mention the filename (`translation_cache.json`), preventing accidental data loss by making the action clearer to users.
- **Smart Masking (Google Translate Fixed):** Replaced default bracket masking (`[[v0]]`) with word-based masking (`X_RPY_v0_X`) specifically for Google Translate. This completely solves the issue where Google would corrupt syntax by inserting spaces inside brackets.
- **Locale UI Standardization:** Fixed all missing interface strings across every supported language (`de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) and standardized the JSON structure to fully match the English reference.


## [2.6.1] - 2026-01-29
### 🛡️ Advanced Integrity Protection (3-Layer)
- **3-Layer Syntax Restoration (Enhanced):** Implemented a robust system to repair Ren'Py syntax corrupted by translation engines:
    1.  **Exact Match:** Perfect preservation.
    2.  **Flexible Regex:** Fixes common typos like `[ variable ]` (spaces) or `[[ tag ]]` (AI hallucinations).
    3.  **Fuzzy Match (RapidFuzz):** Uses advanced string similarity to rescue heavily corrupted tags (e.g. `[vo]` instead of `[v0]`) when confidence is high (>85%).
- **Strict Validation:** Added a final "Integrity Check" step. If a translation is still missing critical variables after repair, it is **rejected** and reverted to original text.
- **Applied Globally:** This protection now covers ALL engines (Google, OpenAI, Gemini, LocalLLM).

### 🛠️ Fixes & Improvements
- **Fuzzy Match Toggle:** Added a new setting in "Translation Filters" to enable/disable the Fuzzy Match feature. This gives users full control over the "autocorrect" behavior.
- **DeepL API Fix:** Resolved "Legacy authentication" error by migrating to header-based authentication for DeepL API.
- **LLM Placeholder Stability:** Improved prompt templates for `OpenAI`, `Gemini`, and `LocalLLM` engines to strictly prevent placeholder corruption (e.g. `[player_name]`).
- **Build Icon Fix:** Resolved an issue where application icons and UI assets were missing in the PyInstaller-built executable. The app now correctly resolves asset paths in both dev and frozen modes.
- **UI Language List:** Language dropdowns now display English names in parentheses for better readability (e.g., `Türkçe (Turkish)`, `中文 (Chinese Simplified)`).
- **QML Component Loading:** Fixed component loading issues in the frozen build by explicitly adding import paths.
- **Dependency Optimization:** Cleaned up build dependencies by removing heavy libraries (pandas heavy collection, PyQt5, tkinter, matplotlib) from the executable, resulting in a cleaner and potentially smaller build.

## [2.6.0] - 2026-01-27
### 🧠 Smart Language Detection (Google Translate)
- **Intelligent Source Language Detection:** When source language is set to "Auto Detect", the system now analyzes 15 random text samples at the start of translation to determine the actual source language with high confidence.
- **Majority Voting Algorithm:** Uses a voting system across multiple samples to prevent misdetection when games have mixed-language content (e.g., an English game with some Russian dialogue).
- **70% Confidence Threshold:** Source language is only locked if at least 70% of samples agree on the same language. If confidence is below threshold, falls back to per-request auto-detection.
- **Target Language Safety Check:** If detected source language equals the target language (which would be nonsensical), the system automatically falls back to auto mode.
- **Fixes "Untranslated Short Text" Issue:** Short texts like "OK", "Yes", character names, and ellipsis (`...`) are now correctly translated because the source language is known upfront.

### 🐛 Critical Bug Fixes & Stability (v2.6.0 Hotfix)
- **Startup Freeze (RPYC Parsing):** Fixed a major issue where the application would hang for minutes on startup when scanning large projects. The parser now intelligently delegates binary `.rpyc` files to a specialized reader instead of attempting to text-parse them.
- **Data Integrity:** Ensured 100% extraction coverage by making the binary `.rpyc` scanner mandatory, capturing up to 60% more translatable content in games with missing source code.
- **Smart Resume System:** Fixed the "loss of progress" issue. The translation engine now checks the in-memory cache before generating translation files, pre-filling known translations instantly instead of starting from scratch.
- **"Event Loop Closed" Fix:** Resolved a technical conflict where "Smart Language Detection" was inadvertently closing the main translation engine's connection pool, causing "Event loop is closed" errors and phantom bans.
- **App Icon Fix:** Implemented a forceful icon refresh strategy to ensure the application icon and taskbar icon appear correctly on Windows systems.

### 🌟 New Features
- **Cache Explorer:** Added a powerful new tool in the Tools menu to view, search, edit, and delete translation cache entries manually.
- **Glossary Import/Export:** You can now export your glossary to JSON, Excel, or CSV and import it back, making it easy to share glossaries between projects.

### 🚨 Improved Error Handling (API Keys)
- **User-Friendly Error Messages:** Added clear, localized error messages for missing API keys (OpenAI, Gemini). Instead of ambiguous crashes or technical tracebacks, the system now explicitly warns users: *"Gemini API key missing! Please add in Settings."*
- **Preventative Checks:** The translation engine now validates API keys *before* attempting initialization, ensuring smoother stability.
- **DeepSeek Engine Removed:** Removed the standalone DeepSeek engine option as it is fully redundant with the "OpenAI / OpenRouter" compatible mode. Users can still use DeepSeek models via the OpenAI engine setting.

### 🌍 UI Localization
- **New Strings:** Added localized error messages for API key failures to all supporting languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`).

### 🐛 Bug Fixes
- **Windows Taskbar Icon:** Fixed an issue where the application icon would sometimes not appear immediately on the Windows Taskbar upon startup. Implemented a robust `AppUserModelID` check and forceful icon refresh.

### 🌍 UI Localization & Consistency
- **Fixed Hardcoded Strings:** Resolved multiple instances of hardcoded Turkish text in the UI (Settings, Glossary, Update Dialog) that persisted even when English was selected.
- **Locale Sync:** Fully synchronized all 8 supported languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `zh-CN`, `fa`) with the latest UI keys.
- **Icon Loading Fix:** Fixed a "double file prefix" bug (`file:///file:///`) that caused application icons to fail loading on some systems.

### 🔔 User Feedback Improvements
- **Explicit Update Check:** "Check for Updates" button now provides immediate visual feedback (Success/No Update/Error dialogs) instead of silently failing or only showing success.
- **Proxy Layout:** Improved the alignment and readability of the Proxy Settings section in the UI.

### 🎨 QML UI Framework (Major Rewrite)
- **Complete UI Modernization:** Migrated the entire user interface from Python/Qt Widgets to QML (Qt Modeling Language) for a more modern, fluid, and responsive experience.
- **Declarative Design:** UI components are now declarative and reactive, enabling smoother animations, transitions, and state management.
- **Component-Based Architecture:** Introduced reusable QML components (`NavigationBar`, `ApiField`, `SettingsPage`, etc.) for better maintainability and consistency.
- **Better Theming Support:** QML's native styling capabilities allow for easier theme customization and future dark/light mode improvements.
- **Improved Performance:** QML's hardware-accelerated rendering provides noticeably smoother scrolling and interactions, especially on large translation lists.

## [2.5.2] - 2026-01-25
### 🛡️ The "Ultra-Aggressive" Patch Engine
- **Late-Load Priority (zzz_ prefix):** All initializer and hook files now use the `zzz_` prefix, ensuring they are loaded last by the Ren'Py engine. This allows RenLocalizer to overwrite even the most stubborn hardcoded language settings.
- **Improved Initializer:** Replaced the fragile `init -999` with a more robust `init 1500` logic. This ensures the game has fully initialized its styles and internal stores before we apply the translation patch.
- **Engine-Level Force:** Added `define config.default_language` and `_preferences.language` synchronization, providing a dual-layer lock to ensure the game starts in the desired language.
- **Professional Runtime Hook:** Overhauled the runtime translation hook. It now uses a "wrapper" pattern to preserve existing game filters while adding translation support on top.
- **Language Hotkey (Shift+L):** Added a universal keyboard shortcut. If the game developer's code prevents automatic language switching, users can press `Shift+L` at any time to force-switch to the translated language. A notification confirms the change.

### 📂 Smart Directory Filtering & Cache (v2.5.2)
- **Global Translation Memory (Portable Cache):** Added a new system to store translation data in a central `cache/` folder next to the program. This keeps game projects clean, prevents accidental deletion of translations, and makes the application truly portable.
- **Exclude System Folders:** New setting (enabled by default) to automatically skip Ren'Py internal folders (`renpy/`, `common/`), cache, saves, and development folders (`.git/`, `.vscode/`).
- **Selective .rpym Scanning:** Added a setting (disabled by default) to skip `.rpym` and `.rpymc` files, reducing "translation noise" from technical modules.
- **Performance Optimized:** Directory scanning is now dynamic, adaptive, and significantly faster for large-scale projects.
- **Safety Hard-Block:** Critical engine folders are now always excluded to prevent accidental modification of Ren'Py core files.

### ⚡ UI Performance & Stability (v2.5.2)
- **Lazy Tab Loading:** Improved startup speed significantly by loading interface pages (Settings, Tools, etc.) only when they are first visited.
- **Log Buffering (Throttle):** Implemented a message throttling system to prevent the GUI from freezing or lagging during rapid translation processes.
- **NameError Fix:** Resolved a critical pipeline crash caused by a missing `sys` import in the new global cache logic.
- **Resource Optimization:** Applied best practices from modern open-source projects to ensure memory and CPU efficiency on the main UI thread.

### 🐛 Safety & Stability Fixes
- **NoneType Exception Fix:** Resolved a critical crash (`TypeError: argument of type 'NoneType' is not iterable`) caused by calling `renpy.change_language` too early in the boot sequence.
- **Automatic Cleanup:** The system now automatically detects and removes legacy `a0_` or `01_` prefix scripts to prevent file conflicts.
- **Better Encoding:** Standardized all generated `.rpy` files to use `UTF-8 with BOM`, ensuring 100% compatibility with Ren'Py 7 & 8 on all operating systems.



## [2.5.1] - 2026-01-21
### 🛠️ Critical Bug Fixes (Local LLM)
- **NameError Fix (`AI_LOCAL_URL`):** Fixed critical startup crash caused by missing `AI_LOCAL_URL` constant in `constants.py`.
- **NameError Fix (`re` module):** Fixed `NameError: name 're' is not defined` crash in `LocalLLMTranslator` by adding missing `import re` statement.
- **Abstract Class Error:** Fixed `Can't instantiate abstract class LocalLLMTranslator` error by implementing missing `_generate_completion` and `health_check` methods.
- **Integrated Glossary to AI Prompt:** Glossary terms are now dynamically injected into AI system prompts (OpenAI, Gemini, Local LLM), ensuring consistent terminology for new translations.
- **Cache Persistence Fix:** Fixed an issue where translation memory (cache) appeared empty after application restart due to incorrect path resolution.
- **Dynamic Cache Handling:** Cache path now updates immediately when switching projects or target languages.
- **Advanced Cache Management:** Added ability to clear, delete, and edit cache entries directly from the UI.
- **Improved Localization:** Added missing Turkish and English translations for new features (RPA, Glossary).
- **Cache Not Saving:** Fixed a critical bug where translations were not being saved to `translation_cache.json`. The issue was that successful results from the single-translation flow were not being added to the in-memory cache before `save_cache()` was called.

### ⚡ Local LLM Improvements
- **Per-Batch Checkpoint Save:** Cache is now saved after every translation batch (instead of every 5 batches). This ensures zero data loss even on power outage or crash.
- **Ultra-Minimal Prompt:** Drastically simplified the system prompt for local models. Removed problematic few-shot examples that small models were copying verbatim instead of translating.
- **Full Language Name Mapping:** Language codes (`tr`, `en`, `de`) are now converted to full names (`Turkish`, `English`, `German`) for better model comprehension.
- **Aggressive Response Cleanup:** Added comprehensive regex patterns to strip model "chatter" (e.g., "Translating to Turkish:", "Here is the translation:") from the output.
- **Batch Override for Local LLM:** `LocalLLMTranslator` now overrides `translate_batch` to force one-by-one translation, bypassing XML-style batching that confused smaller models.
- **Placeholder Corruption Guard:** If the model corrupts `XRPYX` placeholders, the system now falls back to the original text to prevent game-breaking translations.

### 🔔 UI/UX Improvements
- **InfoBar Warning for Local LLM:** Added a visible warning (same style as Gemini censorship warning) that appears in the top-right corner when Local LLM is selected, alerting users to potential hallucination issues with small models.
- **Settings Panel Warnings:** Added three persistent warning/tip labels to the AI Settings section:
  - ⚠️ Hallucination risk for models under 7B parameters
  - ⚠️ VRAM limitations advisory
  - 💡 Tip: Setting source language explicitly improves quality

### 🌍 Localization
- **New Keys:** Added `ai_hallucination_warning`, `ai_vram_warning`, and `ai_source_lang_warning` keys.
- **Full Sync:** Updated all 8 language files (`tr`, `en`, `de`, `es`, `fr`, `ru`, `fa`, `zh-CN`) with new warning messages.

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
