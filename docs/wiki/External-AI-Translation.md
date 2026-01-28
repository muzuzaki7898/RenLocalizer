# 📤 External AI Translation (Export/Import)

The **External AI Translation** feature (introduced in v2.6.0) allows you to translate game strings without using a direct API connection. This is ideal for users who prefer using web interfaces like ChatGPT, Claude, or DeepL, or for those dealing with extremely large projects where direct API costs or rate limits are a concern.

---

## 🚀 How It Works

This feature follows a "Round-trip" localization workflow:
1. **Selection:** Choose between **JSON** (API-ready) or **Simple TXT** (Chat-friendly) formats.
2. **Export:** Scan your game and generate the files along with a hidden metadata cache.
3. **Translate:** Upload files or paste text into your preferred AI tool.
4. **Import:** Bring the translated content back to update your game instantly.

---

## 📄 Export Formats

### 1. JSON (Structured)
The standard professional format. It preserves complex structure and includes a `translation_id` for perfect matching.
*   **Best for:** Paid AI APIs (GPT-4o, Claude 3.5 via API) and Advanced users.
*   **Split Logic:** Large games split into multiple `.json` files.

### 2. Simple TXT (Copy-Paste)
A minimalist format designed specifically for AI Chat interfaces (like the free version of Claude or ChatGPT).
*   **Format:** `ID|||Text`
*   **Safe-Guard:** Uses `<BR>` for newlines and `<PIPE3>` for vertical bars to prevent AI from breaking the structure.
*   **Best for:** Quick copy-pasting into character-limited web chats.

---

## 📤 Exporting Strings

Navigate to the **Tools (Araçlar)** section.

### Configuration Options:
*   **Export only untranslated:** (Recommended) Saves processing time by skipping already localized lines.
*   **Include context:** Includes character names and file references. **Highly recommended** for accurate tone.
*   **Smart Chunking (1500):** Now optimized to split at 1500 strings to ensure even small-context models don't truncate the output.

### Instructions & Prompts:
The tool automatically generates:
*   `PROMPT_FOR_AI.txt` (for JSON)
*   `INSTRUCTIONS_SIMPLE.txt` (for Simple TXT)
**Always give these instructions to the AI first!** They contain ASCII diagrams and rules that guarantee the AI won't break placeholders.

---

## 📥 Importing Translations

### ID Stability (v3 Engine)
RenLocalizer v3 uses a deterministic hashing system based on Ren'Py block IDs.
1. **Auto-File Creation:** If your `tl/` folder is empty, RenLocalizer will automatically create the required `.rpy` files.
2. **Dialogue Awareness:** It differentiates between dialogues (which need `translate` blocks) and UI strings (which need `old/new` syntax).
3. **In-place Update:** It updates the correct files directly, preserving your project's organization.

### Cache Matching
For **Simple TXT** imports, the tool looks for a hidden `.{filename}_cache.json` file. This file "remembers" which ID belongs to which character and file, so your Simple TXT remains clean while the import remains perfectly accurate.

---

## 💡 Best Practices

*   **Avoid conversational AI chatter:** Tell the AI "Return ONLY the translated content with the original IDs" (This is already included in our generated prompts).
*   **Check placeholders:** If you see `[ isim ]` instead of `[name]`, the AI has failed. RenLocalizer will try to block these, but always double-check.
*   **Recursive Export:** For active development, use "Export only untranslated" to capture only the new lines you've added since the last version.

---
> 🔗 **Related Pages:**
> * [[Technical-Filtering]] — How variables are protected.
> * [[Output-Formats]] — Difference between RPY formats.
