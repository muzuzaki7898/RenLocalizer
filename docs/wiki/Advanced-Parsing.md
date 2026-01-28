# 🔍 Advanced Parsing & Text Extraction

RenLocalizer uses a sophisticated multi-stage pipeline to extract text without breaking the underlying game logic or engine syntax.

---

## 🔹 1. Traditional Regex Parsing
The first layer of scanning uses highly optimized Regular Expressions to find standard Ren'Py dialogue and UI strings:
*   **Dialogue:** `character_name "Dialogue text"`
*   **Direct strings:** `_("Text")` or `"Text"`
*   **Menu items:** `menu:` choice blocks.

## 🔹 2. AST (Abstract Syntax Tree) Scanning
When simple patterns aren't enough, RenLocalizer analyzes the script's structure using Python's `ast` module.
*   **Capabilities:**
    *   Finds strings inside nested functions.
    *   Extracts text from `init python` blocks.
    *   Distinguishes between technical code and translatable content.

## 🔹 3. RPYC & RPYMC Readers
Many "obfuscated" games hide their source code by deleting `.rpy` files.
*   **RPYC Reader:** "Unpickles" binary RPYC files to extract the original logic. You can translate a game even if the source code is missing!
*   **RPYMC Reader:** Handles screen cache files, ensuring complex UI elements are localized.

## 🔹 4. Deep Scan Technology
Enable **Deep Scan** in settings to trigger a recursive analysis of the entire project.
*   **What it finds:** Variable assignments and list items used as game text that don't follow standard `_()` markers.
*   **Safety:** Uses a "Technical String Filter" to skip engine internals like `renpy.dissolve`.

---

## 🔹 5. Text Types Filter
Categorize and select exactly what you want to translate in **Settings > Text Types**:

*   📌 **Core:** Dialogue, Menus, Buttons.
*   📌 **Interface:** UI text, Input fields, Alt text.
*   📌 **System:** Notifications, Confirmation dialogs.
*   📌 **Config:** Game title, Version strings.

---

## 🔹 6. Normalization & Encoding
RenLocalizer automatically detects file encodings and normalizes them to **UTF-8 with BOM**. 
> 🛡️ **Benefit:** Prevents "Mojibake" (broken characters) in languages like Russian, Chinese, or Japanese.

---

## 🔹 7. ID Stability (v3 Engine)
Introduced in v2.6.0, this technology ensures that translations remain linked to the correct code block even if the script files are modified.
*   **Deterministic Hashing:** Instead of relying on line numbers (which change when you add/remove code), it generates unique IDs based on Ren'Py's internal `Label ID` mapping and the original text content.
*   **Advantage:** Perfect for "External AI Translation" (Export/Import) workflow. You can keep developing your game while someone else translates the JSON files.

---

## 🔹 8. Force Runtime Translation (Hook)
Sometime Ren'Py source code contains dynamic strings that are not wrapped in `_()` or `!t` flags. These strings often appear untranslated in games even after processing.

*   **How it Works:** 
    *   RenLocalizer injects a small script (`01_renlocalizer_runtime.rpy`) into the game folder.
    *   This script hooks into the engine's text processing pipeline (`config.replace_text`).
    *   Every time a string is displayed, it checks if a translation exists in the current language files.
*   **When to Use:** Use this if you see quest descriptions, item names, or dynamic UI elements that remain untranslated.
*   **Status:** **Disabled by default** to ensure maximum compatibility with other mods (like Zenpy). Enable it in **Settings > Translation Settings**.
