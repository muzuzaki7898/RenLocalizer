# Installation Guide

RenLocalizer is designed to be flexible. You can run it as a standalone executable (Windows) or from the source code (All platforms).

## 🪟 Windows (Standalone)
The easiest way to use RenLocalizer on Windows is to download the latest release:

1.  Go to the [Releases](https://github.com/Lord0fTurk/RenLocalizer/releases) page.
2.  Download the `RenLocalizer_vX.X.X_Windows.zip` file.
3.  Extract the ZIP and run `RenLocalizer.exe`.

## 🍎 macOS & 🐧 Linux (from Source)
Since Ren'Py games run on Python, RenLocalizer works natively on Linux and macOS using Python 3.10+.

### Prerequisites
- Python 3.10 or higher.
- `pip` (Python package manager).

### Steps
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Lord0fTurk/RenLocalizer.git
    cd RenLocalizer
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # venv\Scripts\activate   # On Windows (if running source)
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the App:**
    ```bash
    python run.py       # Starts the GUI
    python run_cli.py   # Starts the CLI
    ```

## 🛠️ Build Scripts
We provide convenience scripts for Unix-based systems:
- `RenLocalizer.sh`: Automatically sets up the environment and launches the GUI.
- `RenLocalizerCLI.sh`: Automatically sets up the environment and launches the CLI.

Run them with:
```bash
chmod +x RenLocalizer.sh
./RenLocalizer.sh
```

## 📦 Requirements Trace
The tool depends on:
- `PySide6` / `PyQt6-Fluent-Widgets` for the UI.
- `openai`, `google-genai` for AI engines.
- `unrpa` for archive extraction.
- `requests`, `beautifulsoup4` for traditional translation engines.
