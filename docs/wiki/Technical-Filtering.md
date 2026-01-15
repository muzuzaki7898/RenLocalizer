# 🛡️ Technical String Filtering

Ren'Py files are a mix of dialogue and technical code. To prevent breaking the game, RenLocalizer uses a multi-layered filtering system.

---

## 🔹 Placeholder Protection
Ren'Py uses `[variables]` and `{tags}` for logic and styling.
*   **Target:** `[player_name]`, `[persistent.day]`, `{b}Text{/b}`.
*   **Mechanism:** Before translation, RenLocalizer replaces these with unique tokens (e.g., `?V001?`). After translation, it restores the exact original code.

## 🔹 Technical Keyword Filter
The system automatically skips internal Ren'Py keywords that might look like strings:
*   `renpy.dissolve`
*   `gui.text_font`
*   `config.version`
*   `persistent.save_slot`

## 🔹 Heuristic "Symbol Density"
RenLocalizer analyzes the ratio of special symbols (dots, underscores, brackets) in a string.
*   **Technical High Density:** `path.to.my_file[0]` (Skipped).
*   **Human Low Density:** `Hello, how are you?` (Translated).

---

## ⚠️ Common Scenarios

### **Unwanted Translation (False Positive)**
If a piece of code *is* being translated when it shouldn't:
1.  Open the **Glossary Editor**.
2.  Add the code as both Source and Target (e.g., `sys_path` -> `sys_path`).
3.  This protects it from the translation engine.

### **Missing Translation (False Negative)**
If a button or menu item is being ignored:
1.  Check **Settings > Text Types**.
2.  Ensure "Translate Buttons" or "Translate UI" is enabled.

---
> 💡 **Tip:** Use the **Deep Scan** feature for a much more thorough (but slower) AST-based scan of technical strings.
