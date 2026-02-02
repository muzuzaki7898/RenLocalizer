# -*- coding: utf-8 -*-
"""
RenLocalizer V2 Launcher
Cross-platform launcher for Windows and Unix systems
Now powered by Qt Quick (QML)
"""

import os
import sys
import warnings
from pathlib import Path
from src.utils.logger import setup_logger

from src.version import VERSION

# ============================================================
# CRITICAL: Disable Qt system theme detection BEFORE any Qt imports
# This ensures the app uses its own theme regardless of Windows settings
# ============================================================
os.environ["QT_QPA_PLATFORM_THEME"] = ""  # Disable system theme
os.environ["QT_STYLE_OVERRIDE"] = ""  # Disable style override

# ============================================================
# QML & MATERIAL STYLE SETTINGS
# Load theme from config if available, otherwise default to Dark
# ============================================================
def _get_configured_theme():
    try:
        import json
        config_path = os.path.join(os.getcwd(), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # app_settings -> theme
                return data.get("app_settings", {}).get("theme", "Dark")
    except:
        pass
    return "Dark"

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"
os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"] = _get_configured_theme()
os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] = "Purple"

# ============================================================
# CRITICAL: Set AppUserModelId for Windows taskbar icon
# This MUST be done early, before any Qt/GUI initialization
# ============================================================
if sys.platform == "win32":
    try:
        import ctypes
        # Set explicitly for taskbar icon to appear immediately
        # Changed ID slightly to force Windows Icon Cache refresh
        myappid = "LordOfTurk.RenLocalizer.V2.QML.Rev1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass  # Silent fail is acceptable on non-Windows or old Windows versions

warnings.filterwarnings("ignore", category=SyntaxWarning, message=r".*invalid escape sequence.*")

# Ensure stdout/stderr use UTF-8 where possible
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ============================================================
# GLOBAL EXCEPTION HANDLER
# ============================================================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Catch all unhandled exceptions and show a user-friendly dialog."""
    import traceback
    import datetime
    
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Log to file
    try:
        with open("crash_report.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n[{timestamp}]\n{error_msg}\n")
    except Exception:
        pass
    
    # Show GUI dialog if possible (Use ctypes for independence from Qt crash)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Bir hata oluştu:\n\n{exc_value}\n\nDetaylar crash_report.log dosyasına kaydedildi.", "RenLocalizer Hatası", 0x10)
        except:
            print(error_msg)
    else:
        print(error_msg)
    
    # Call original handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = global_exception_handler


def show_error_and_wait(title: str, message: str) -> None:
    """Show error message and wait for user input (works without Qt)."""
    print(f"\n{'=' * 60}")
    print(f"ERROR: {title}")
    print("=" * 60)
    print(message)
    print("=" * 60)

    # Try Windows MessageBox
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        except Exception:
            pass

    # Keep console open
    print("\nPress Enter to close...")
    try:
        input()
    except Exception:
        import time
        time.sleep(10)


def check_windows_version() -> bool:
    """Check if Windows version is compatible."""
    if sys.platform != "win32":
        return True

    try:
        import platform
        machine = platform.machine()
        # Check for 64-bit
        if machine not in ["AMD64", "x86_64"]:
            show_error_and_wait(
                "Unsupported Architecture",
                f"RenLocalizer requires 64-bit Windows.\nYour system: {machine}"
            )
            return False
        return True
    except Exception as e:
        print(f"Warning: Could not check Windows version: {e}")
        return True


def check_vcruntime() -> bool:
    """Check if Visual C++ Runtime is installed (Windows only)."""
    if sys.platform != "win32":
        return True

    import ctypes
    required_dlls = ["vcruntime140.dll", "msvcp140.dll"]
    missing_dlls = []

    for dll_name in required_dlls:
        try:
            ctypes.WinDLL(dll_name)
        except OSError:
            missing_dlls.append(dll_name)

    if missing_dlls:
        show_error_and_wait(
            "RenLocalizer - Missing Runtime",
            f"RenLocalizer requires Microsoft Visual C++ Redistributable.\n\n"
            f"Missing: {', '.join(missing_dlls)}\n\n"
            "Please install Visual C++ Redistributable 2015-2022 (x64)."
        )
        return False
    return True


def get_base_dir() -> Path:
    """Get the base directory where the executable/script resides (for config/logs)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

def resolve_asset_path(path: str | Path) -> Path:
    """Resolve an asset path, checking _MEIPASS for PyInstaller bundles."""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            # OneFile mode: Use temp folder
            base = Path(sys._MEIPASS)
        else:
            # OneDir mode: Use executable directory
            base = Path(sys.executable).parent
    else:
        # Development mode
        base = Path(__file__).parent
        
    return base / path

# Set working directory to where the executable is (for relative config/output paths)
WORK_DIR = get_base_dir()
os.chdir(WORK_DIR)

# Add project root to Python path (for imports)
sys.path.insert(0, str(WORK_DIR))


def setup_qt_environment() -> None:
    """Setup Qt environment variables for frozen exe."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if not meipass:
            return

        meipass_path = Path(meipass)
        
        # Add DLL directories (Python 3.8+)
        if hasattr(os, "add_dll_directory"):
            dll_paths = [
                meipass_path,
                meipass_path / "PyQt6" / "Qt6" / "bin",
            ]
            for dll_path in dll_paths:
                if dll_path.exists():
                    try:
                        os.add_dll_directory(str(dll_path))
                    except:
                        pass

        # Set QT_PLUGIN_PATH
        plugin_paths = [
            meipass_path / "PyQt6" / "Qt6" / "plugins",
            meipass_path / "PyQt6" / "plugins",
        ]
        existing_plugin_paths = [str(p) for p in plugin_paths if p.exists()]
        if existing_plugin_paths:
            os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(existing_plugin_paths)

        # Disable noisy Qt font warnings
        os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false;qt.text.font.db=false;*.debug=false"


def check_unix_system() -> bool:
    if sys.platform == "win32": return True
    return True


def main() -> int:
    print("=" * 60)
    print("RenLocalizer V2 (Qt Quick Edition) Starting...")
    print("=" * 60)

    # Initialize Secure Logger
    logger = setup_logger()
    logger.info(f"RenLocalizer V2 Starting... Version: {VERSION}")

    setup_qt_environment()
    
    # Check system requirements
    if sys.platform == "win32":
        if not check_windows_version(): return 1
        if not check_vcruntime(): return 1
    else:
        check_unix_system()

    print("\nLoading Qt framework...")

    try:
        # Import Qt
        from PyQt6.QtCore import QUrl, Qt
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtQml import QQmlApplicationEngine

        # Use QApplication for better desktop integration (Icons, Taskbar, etc.)
        app = QApplication(sys.argv)
        app.setApplicationName("RenLocalizer")
        app.setOrganizationName("LordOfTurk")
        
        # Import Backends (Logic)
        from src.version import VERSION
        from src.utils.config import ConfigManager
        from src.backend.app_backend import AppBackend
        from src.backend.settings_backend import SettingsBackend
        
        app.setApplicationVersion(VERSION)

        # Set application icon
        icon_path = resolve_asset_path("icon.ico")
        app_icon = QIcon()
        
        if icon_path.exists():
            print(f"[INFO] Loading icon from: {icon_path}")
            app_icon = QIcon(str(icon_path))
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)
                print("[INFO] Icon loaded successfully.")
            else:
                 print("[WARNING] Icon file exists but QIcon failed to load it.")
        else:
             print(f"[WARNING] Icon file not found at: {icon_path}")

        # Initialize Logic
        config_manager = ConfigManager()
        backend = AppBackend(config_manager)
        settings_backend = SettingsBackend(config_manager)
        
        # Link backends for signal propagation (Localization refresh)
        settings_backend.languageChanged.connect(backend.refreshUI)
        settings_backend.themeChanged.connect(backend.refreshUI)

        # Create QML Engine
        engine = QQmlApplicationEngine()

        # Expose Backends to QML
        engine.rootContext().setContextProperty("backend", backend)
        engine.rootContext().setContextProperty("settingsBackend", settings_backend)

        # Error Handling for QML
        def on_object_created(obj, url):
            if obj is None:
                print(f"[FATAL ERROR] Failed to load QML: {url}")
                app.exit(-1)

        engine.objectCreated.connect(on_object_created)

        # Load MAIN QML
        # Use resolve_asset_path so it works inside PyInstaller bundle
        qml_path = resolve_asset_path("src/gui/qml/main.qml")
        print(f"Loading UI: {qml_path}")
        
        if not qml_path.exists():
            print(f"[ERROR] QML file not found: {qml_path}")
            # Do not exit here, let engine.load fail gracefully or handled below
        
        # Important: Add QML root to import paths so imports work in frozen exe
        qml_root = resolve_asset_path("src/gui/qml")
        engine.addImportPath(str(qml_root))

        engine.load(QUrl.fromLocalFile(str(qml_path)))

        if not engine.rootObjects():
            print("[ERROR] No root objects created.")
            return 1

        # Force icon on the root window (Fix for Windows taskbar)
        if engine.rootObjects():
            root_window = engine.rootObjects()[0]
            if icon_path.exists() and not app_icon.isNull():
                root_window.setIcon(app_icon)
                app.setWindowIcon(app_icon) # Set app icon again
            
            # Explicitly show window after setting properties
            root_window.show()
            
            # Additional force for Windows Taskbar refresh using Win32 API
            if sys.platform == "win32" and icon_path.exists():
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # Get Window Handle (HWND)
                    hwnd = root_window.winId()
                    
                    # Load Icon via Windows API (Large and Small) - bypassing Qt
                    h_icon = QIcon(str(icon_path)).pixmap(32, 32).toImage() # 32x32 for Taskbar
                    # Note: Getting HICON from Qt is tricky without heavy boilerplate. 
                    # Simpler approach: Rely on Qt's setWindowIcon but force refresh via AppID or just wait.
                    # Alternatively, use LoadImageW if we want to be pure native.
                    
                    user32 = ctypes.windll.user32
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    WM_SETICON = 0x80
                    
                    # Load from file directly using LoadImageW
                    # LR_LOADFROMFILE = 0x10, IMAGE_ICON = 1
                    h_icon_big = user32.LoadImageW(None, str(icon_path), 1, 0, 0, 0x10)
                    h_icon_small = user32.LoadImageW(None, str(icon_path), 1, 0, 0, 0x10)
                    
                    if h_icon_big:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon_big)
                    if h_icon_small:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon_small)
                        
                except Exception as e:
                    print(f"Warning: Failed to set native Windows icon: {e}")

        print("[OK] UI loaded successfully. Entering event loop.")
        return app.exec()

    except Exception as e:
        error_msg = f"Error starting RenLocalizer V2: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()

        show_error_and_wait(
            "RenLocalizer - Startup Error",
            f"{error_msg}\n\nCheck logs for details."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
