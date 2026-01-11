# Troubleshooting & FAQ

Most issues in RenLocalizer can be resolved by checking the logs or the diagnostic tool.

## 🆘 Common Errors

### 1. "No translatable texts found"
- **Cause:** The game might be using obfuscated RPYC files without source RPY files.
- **Solution:** Enable **RPYC Reader** in Settings. This will read the binary bytecode directly.

### 2. "Already exists" errors in Ren'Py
- **Cause:** RenLocalizer might have accidentally scanned the `tl/` directory and created "Translation of a Translation."
- **Solution:** Version 2.4.10+ automatically excludes the `tl/` folder. Ensure you are on the latest version and delete any duplicate `.rpy` files in your `game/tl/` directory.

### 3. "AI Safety Filter" (Gemini/OpenAI)
- **Cause:** The game contains adult, violent, or "unsafe" content that the default AI filter blocks.
- **Solution:** 
  - For Gemini: Set Safety Level to `BLOCK_NONE`.
  - For OpenAI: Use an "Uncensored" model via OpenRouter.
  - Or use a **Local LLM** which has no built-in filters.

### 4. Broken characters (Mojibake)
- **Cause:** Source files use a legacy or non-UTF8 encoding (like Shift-JIS or Windows-1254).
- **Solution:** RenLocalizer automatically attempts to normalize encodings. If it fails, open the file in Notepad++ and manually convert it to **UTF-8 with BOM**.

## 🔍 How to Debug
If you experience a crash:
1.  Check the **Console** (if running from source) or the **Log Panel** in the GUI.
2.  Open **`error_output.txt`** in the project root. It contains the full traceback of the error.
3.  Run **Tools > Project Health Check**. It will scan your game folder for missing files or invalid paths.

## ❔ FAQ
- **Q: Does it work with Ren'Py 6?** Yes, but RPYC/RPYMC support is optimized for Ren'Py 7.x and 8.x.
- **Q: Can I translate APKs?** Not directly. You must first extract the APK (as it's just a ZIP file) and point RenLocalizer to the extracted folder.
- **Q: How do I update?** Just download the new version and replace the old files. Your `config.json` is safe to keep.
