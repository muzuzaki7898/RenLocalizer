# 📄 Understanding Output Formats

RenLocalizer supports three main ways of interacting with translation data. Choosing the right one is important for your technical or AI-driven workflow.

---

## 🔹 1. OLD_NEW Format (Native Ren'Py)
This is the official Ren'Py translation standard. RenLocalizer uses this for writing directly to your game files.

*   **How it looks:**
    ```renpy
    # game/script.rpy:10
    old "Hello world"
    new "Hola mundo"
    ```
*   **Pros:** Official standard, used by the engine at runtime.
*   **Best for:** The final translated files in your `game/tl/` directory.

---

## 🔹 2. External JSON (Structured AI)
A bridge format for external translation tools that support file uploads.

*   **How it looks:**
    ```json
    {
      "original": "Hello world",
      "translation": "",
      "character": "Eileen",
      "file_path": "game/script.rpy",
      "translation_id": "id_1234abcd5678efgh"
    }
    ```
*   **Best for:** Professional AI APIs (OpenRouter, DeepL) or batch processing tools.

---

## 🔹 3. Simple TXT (Chat-Friendly)
New in v2.6.0. A minimalist text format designed for "Copy-Paste" workflows with AI Chat web interfaces.

*   **How it looks:**
    ```text
    123|||Hello world
    124|||How are you?
    ```
*   **Pros:** High token efficiency, easy to read, impossible for AI to "break" the JSON syntax because there is no JSON.
*   **Best for:** Free versions of ChatGPT or Claude where you can't easily upload files.

---

## 🛠️ Format Management inside RenLocalizer

In the **Tools** interface, you can select between JSON and Simple TXT for your Export/Import workflow. 

### Why did the "Output Format" setting disappear from the main menu?
In version 2.5.0 and later, **RenLocalizer permanently uses the OLD_NEW format** for internal game writing. This ensures that all translations are fully compatible with Ren'Py's internal ID system and incremental updates (Smart Skip). We removed the option to simplify the UI and prevent accidental game corruption by using legacy formats.

---

## 📂 Directory Structure
Regardless of the format, RenLocalizer places its final game-ready output in:
`game/tl/[target_language]/`

For example, if you choose Spanish (`es`):
`game/tl/es/script.rpy` (or other matched script names).

---

> 🔗 **Related Pages:**
> * [[External-AI-Translation]] — How to use these formats in your workflow.
