# 📓 Glossary & Terminology Management

Maintaining consistency in character names, specific items, and world-building terms is the difference between a "good" translation and a "professional" one.

---

## 🛠️ The Glossary Editor
Access the editor via **Tools > Glossary Editor** in the main window.

*   **Source Word:** The original text (e.g., "Shadow Lord").
*   **Target Word:** Your preferred translation (e.g., "Gölge Efendisi").
*   **Match Mode:** Toggle Case Sensitivity to control how strictly the word is matched.

---

## 🚀 How it Works
The glossary is applied as a **Smart Layer** after the engine returns a translation:

1.  **Request:** RenLocalizer sends text to the engine (e.g., Google).
2.  **Translate:** The engine returns its best attempt.
3.  **Refine:** RenLocalizer scans the result and replaces any mistranslated terms with your defined glossary entries.

---

## 🛡️ Critical Terms (Protection)
If you want a word to **never** be translated (like a unique brand name or an untranslatable character name):
*   Add the word to the glossary with the **same Source and Target**.
*   This forces RenLocalizer to override any attempt by the AI to "fix" or translate that word.

---

## 📂 Storage & Sharing
*   **`glossary.json`**: All terms are stored in this file in your project root.
*   **Sharing:** You can share this file with other team members to ensure everyone uses the same terminology.

---

## 💡 Best Practices
*   **Character Names:** Always add names (e.g., "Summer" -> "Summer") to prevent AI from translating them as common nouns.
*   **UI Consistency:** Ensure buttons like "Save", "Load", and "Quit" are consistent across all translated files.
*   **Jargon:** Use it for Sci-Fi or Fantasy specific terms (e.g., "Flux Capacitor").

---
> 💡 **Tip:** Use the **Extract from Project** button in the Glossary Editor to automatically find frequently used words!
