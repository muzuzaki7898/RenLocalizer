# 📥 Installation Guide

RenLocalizer is designed to be flexible. You can run it as a standalone executable on Windows or from the source code on any platform (macOS, Linux, Windows).

---

## 🪟 Windows (Standalone)
The easiest way to use RenLocalizer on Windows:

1.  Navigate to the [Releases](https://github.com/Lord0fTurk/RenLocalizer/releases) page.
2.  Download the latest `RenLocalizer_vX.X.X_Windows.zip`.
3.  **Extract** the ZIP file to a folder of your choice.
4.  Run `RenLocalizer.exe` to start the GUI.

---

## 🍎 macOS & 🐧 Linux (from Source)
Since RenLocalizer is built with Python 3, it works natively on Unix-based systems.

### 📋 Prerequisites
*   **Python 3.10** or higher.
*   **pip** (Python package manager).

### 🛠️ Step-by-Step Setup
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Lord0fTurk/RenLocalizer.git
    cd RenLocalizer
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # macOS/Linux
    # venv\Scripts\activate   # Windows
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Launch the Application:**
    *   **GUI:** `python run.py`
    *   **CLI:** `python run_cli.py`

---

## 🚀 Convenience Scripts
We provide pre-made scripts to handle the environment setup automatically:

*   **`RenLocalizer.sh`**: Sets up the VENV and launches the GUI.
*   **`RenLocalizerCLI.sh`**: Sets up the VENV and launches the CLI.

> 💡 **Note:** Make sure to grant execution permissions on Linux/macOS:
> `chmod +x RenLocalizer.sh`

---

## 📦 Core Dependencies
The tool relies on these main libraries:
*   **UI:** `PyQt6` & `PyQt6-Fluent-Widgets`
*   **AI:** `openai`, `google-genai`
*   **Extraction:** `unrpa`
*   **Engines:** `requests`, `httpx`, `beautifulsoup4`
