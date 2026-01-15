# 📄 Understanding Output Formats

RenLocalizer supports two different ways of generating translation files. Choosing the right one is important for game compatibility.

---

## 🔹 1. OLD_NEW Format (Recommended)
This is the modern, official Ren'Py translation standard.

*   **How it looks:**
    ```renpy
    # game/script.rpy:10
    old "Hello world"
    new "Hola mundo"
    ```
*   **Pros:**
    *   ✅ Follows official Ren'Py documentation.
    *   ✅ Supports high-performance "Translation ID" matching.
    *   ✅ compatible with Ren'Py 7.x and 8.x.
    *   ✅ Safe; won't break original script logic.
*   **Best for:** Most modern games and official localizations.

---

## 🔹 2. SIMPLE Format (Legacy/Removed)
> [!NOTE]
> This format has been removed in v2.5.0 to ensure maximum compatibility and stability.

---

## 🛠️ Format Selection
In version 2.5.0 and later, **RenLocalizer permanently uses the OLD_NEW format**. This ensures that all translations are fully compatible with Ren'Py's internal ID system and incremental updates (Smart Skip).

The "Output Format" setting has been removed from the application to simplify the user experience and prevent accidental game corruption.

---

> ⚠️ **Important:** If you change the format, we recommend deleting the existing files in your `game/tl/` folder and re-translating to avoid duplicate definition errors.

---

## 📂 Directory Structure
Regardless of the format, RenLocalizer places its output in:
`game/tl/[target_language]/`

For example, if you choose Spanish (`es`):
`game/tl/es/all_translations.rpy`
