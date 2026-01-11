# Build Instructions

This guide details how to build RenLocalizer into standalone executables for Windows, Linux, and macOS.

## 📋 Prerequisites

- **Python 3.10+** (Recommended: 3.11)
- **Pip** & **Virtualenv**
- **Git**

## 🏗️ Building for Distribution

RenLocalizer uses `PyInstaller` to create standalone executables. The build process is configured in `RenLocalizer.spec` to produce two separate binaries:
1. **RenLocalizer** (GUI Version)
2. **RenLocalizerCLI** (Command Line Version)

### 1. Setup Environment
```bash
# Clone and enter repo
git clone https://github.com/Lord0fTurk/RenLocalizer.git
cd RenLocalizer

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Run the Build
Use the provided spec file which handles hidden imports (OpenAI, Gemini, UnRPA) and asset bundling automatically.

```bash
pyinstaller RenLocalizer.spec --clean --noconfirm
```

### 3. Check Artifacts
The build output will be in the `dist/` directory.
- `dist/RenLocalizer/`: Contains the main executable and all dependencies (Folder/Onedir mode).
  - `RenLocalizer.exe` (GUI)
  - `RenLocalizerCLI.exe` (CLI)

> **Note:** We use "Onedir" mode (folder based) instead of "Onefile" to ensure faster startup times and better compatibility with external assets like `locales/` and `tools/`.

---

## 🤖 GitHub Actions (CI/CD)

This project includes automated workflows for building and releasing on all platforms.

- **File:** `.github/workflows/release.yml`
- **Triggers:** Pushing any tag (e.g., `v2.4.10`)
- **Outputs:**
  - `RenLocalizer-Windows-x64.zip`
  - `RenLocalizer-Linux-x64.tar.gz`
  - `RenLocalizer-macOS-x64.zip`

---

## 🔧 Troubleshooting Builds

### "No module named 'openai'" or similar
If the executable fails with missing module errors:
1. Ensure the module is listed in `hidden_imports` in `RenLocalizer.spec`.
2. Re-run PyInstaller with `--clean`.

### Anti-Virus False Positives
PyInstaller executables (especially unsigned ones) are often flagged by Windows Defender.
- **Solution:** Sign the executable or add an exclusion folder.

### Assets not loading
Ensure that `locales/` and `icon.ico` are correctly copied to the `dist/RenLocalizer/` folder. The `.spec` file handles this, but verify manually if issues persist.