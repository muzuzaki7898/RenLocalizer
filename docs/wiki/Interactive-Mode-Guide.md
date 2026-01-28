# 🎮 Interactive Mode Guide

The **Interactive Mode** is a user-friendly wizard built into the RenLocalizer CLI. It guides you through the translation process step-by-step, making it perfect for users who prefer not to memorize complex command-line arguments.

---

## 🚀 How to Launch

Simply run the CLI script without any arguments:

```bash
python run_cli.py
```

Or explicitly with the flag:

```bash
python run_cli.py --interactive
```

---

## 🧙‍♂️ The Wizard Steps

The interactive mode will present a series of menus. Use your keyboard to type the number of your choice and press **Enter**.

### 1. Main Menu
You will see the following options:

*   **[1] Full Translation (Game EXE/Project):** The most common option. Select this if you have a downloaded game folder or `.exe` file.
*   **[2] Translate Existing TL Folder:** Select this if you already have a `game/tl/language` folder and just want to update the translations.
*   **[3] Settings:** Configure global options like the default AI engine or proxy.
*   **[4] Help:** Shows a brief usage guide.
*   **[5] Exit:** Closes the program.

### 2. Path Selection
*   The wizard will ask for the **Path**.
*   You can drag and drop the game folder or `.exe` file into the terminal window, then press Enter.

### 3. Target Language
*   Choose from a list of common languages (Turkish, English, Spanish, etc.).
*   Select **[10] Other** to enter a custom ISO code (e.g., `pt-br`, `id`, `pl`).

### 4. Mode Selection
*   **[1] Auto (Recommended):** Automatically detects if it needs to extract archives (UnRen) or just translate files.
*   **[2] Full (UnRen + Translation):** Forces the UnRen extraction process. *Windows Only.*
*   **[3] Translate Only:** Skips extraction and looks for `.rpy` files immediately.

---

## 💡 Tips

*   **Default Values:** If a prompt shows `[default]`, you can just press **Enter** to accept that value.
*   **Back Navigation:** Enter `0` in most menus to go back to the previous screen.
*   **Quick Automation:** Once you are comfortable with the settings you choose here, you can consult [[CLI-Usage]] to look up the equivalent command-line arguments for faster future runs.
