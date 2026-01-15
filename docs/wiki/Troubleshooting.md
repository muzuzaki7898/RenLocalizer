# 🆘 Troubleshooting & FAQ

Most issues in RenLocalizer can be resolved by checking the logs or the diagnostic tools. Here are the most common solutions.

---

## 🚩 Common Errors

### 1. "No translatable texts found"
*   **Cause:** The game uses compiled RPYC files only.
*   **Solution:** Enable **RPYC Reader** in Settings to extract text directly from binary bytecode.

### 2. "Already exists" errors in Ren'Py
*   **Cause:** Duplicate translation definitions (scanning the `tl/` folder twice).
*   **Solution:** Delete the `game/tl/` folder and re-run the translation. Ensure you are on v2.4.10+, which has an automatic exclusion filter.

### 3. AI Safety Filter Blocks (Gemini/GPT)
*   **Cause:** Content safety policies of the provider.
*   **Solution:** 
    *   Set Gemini Safety to `BLOCK_NONE`.
    *   Use a **Local LLM** (No filters).
    *   Use **OpenRouter** with an "Uncensored" model.

### 4. Broken characters / Mojibake
*   **Cause:** Original files aren't UTF-8 (Common in Japanese/Russian games).
*   **Solution:** RenLocalizer tries to fix this automatically. If it fails, open the file in **Notepad++** and "Convert to UTF-8 with BOM" manually.

### 5. Some strings (Quests/Menus) are still in English
*   **Cause:** The game code uses dynamic variables without translation flags (`!t`).
*   **Solution:** Enable **Force Runtime Translation** in Settings. This will dynamically translate these strings while the game is running.

---

## 🔍 How to Debug a Crash
If the app closes or throws a fatal error:

1.  **Check the Console:** (If running from source) View real-time error messages.
2.  **View `error_output.txt`:** This file in the root folder contains the full technical "Traceback".
3.  **Run Health Check:** Go to **Tools > Project Health Check** to scan for missing dependencies or invalid paths.

---

## ❔ FAQ

*   **Q: Does it work with Ren'Py 6?** 
    *   A: Yes, but some advanced features like the RPYC Reader are optimized for Ren'Py 7/8.
*   **Q: Can I translate APKs?** 
    *   A: Not directly. Extract the APK using 7-Zip/WinRAR first, translate the folder, and re-pack.
*   **Q: How do I update?** 
    *   A: Replace the old files with the new ones. Your **`config.json`** is safe to keep.
*   **Q: Is it free?**
    *   A: Yes! RenLocalizer is open-source (GPL-3.0).

---
> 🚩 **Still Stuck?** [Open an issue on GitHub](https://github.com/Lord0fTurk/RenLocalizer/issues) with your `error_output.txt` attached.
