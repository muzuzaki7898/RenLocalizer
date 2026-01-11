# Advanced Parsing & Text Extraction

RenLocalizer uses a sophisticated multi-stage pipeline to find and extract text from Ren'Py games without breaking the underlying code.

## 1. Traditional Regex Parsing
The first layer of scanning uses highly optimized Regular Expressions to find standard Ren'Py dialogue and UI strings:
- Dialogue: `character_name "Dialogue text"`
- Direct strings: `_("Text")` or `"Text"`
- Menu items: `menu:` blocks

## 2. AST (Abstract Syntax Tree) Scanning
When simple regex isn't enough, RenLocalizer uses Python's `ast` module to analyze scripts. This allows us to:
- Find strings inside complex nested functions.
- Identify translatable text in `init python` blocks.
- Smartly distinguish between technical code and game content.

## 3. RPYC & RPYMC Readers
Ren'Py compiles human-readable `.rpy` files into binary `.rpyc` files. Many "obfuscated" games hide their source code.
- **RPYC Reader:** RenLocalizer can "unpickle" binary RPYC files to extract the original Abstract Syntax Tree. This allows translation even when the source `.rpy` file is missing.
- **RPYMC Reader:** Specifically handles screen cache files, ensuring even complex UI elements are localized.

## 4. Deep Scan Technology
Enable **Deep Scan** in settings to trigger a recursive AST analysis of the entire project.
- **What it finds:** Variable assignments, dictionary keys, and list items that are used as game text but don't follow standard `_()` localization markers.
- **Safety:** Deep Scan uses a heuristic "Technical String Filter" to ensure it doesn't accidentally translate internal Ren'Py paths or variable names (e.g., it will translate `"Health"` but skip `"renpy.dissolve"`).

## 5. Normalization & Encoding
RenLocalizer automatically detects and normalizes file encodings to **UTF-8 with BOM**. This prevents "Mojibake" (broken characters) in languages like Russian, Chinese, or Japanese.
