# -*- coding: utf-8 -*-
"""
RenLocalizer CLI Main Module
"""

import sys
import os
import argparse
import signal
import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QCoreApplication, QTimer, QObject, pyqtSlot

# Import core modules
from src.utils.config import ConfigManager
from src.core.translation_pipeline import TranslationPipeline, PipelineResult, PipelineStage
from src.core.translator import TranslationManager, TranslationEngine
from src.version import VERSION

class CliHandler(QObject):
    """Handles CLI events and pipeline signals."""
    
    def __init__(self, pipeline: TranslationPipeline, verbose: bool = False):
        super().__init__()
        self.pipeline = pipeline
        self.verbose = verbose
        
        # Connect signals
        self.pipeline.stage_changed.connect(self.on_stage_changed)
        self.pipeline.progress_updated.connect(self.on_progress_updated)
        self.pipeline.log_message.connect(self.on_log_message)
        self.pipeline.finished.connect(self.on_finished)
        self.pipeline.show_warning.connect(self.on_warning)
        
    @pyqtSlot(str, str)
    def on_stage_changed(self, stage: str, message: str):
        print(f"\n>> STAGE: {message} ({stage})")

    @pyqtSlot(int, int, str)
    def on_progress_updated(self, current: int, total: int, text: str):
        # Print a progress bar or status line
        percent = 0
        if total > 0:
            percent = int((current / total) * 100)
        
        # Clear line and print progress
        sys.stdout.write(f"\rProgress: [{current}/{total}] {percent}% - {text[:50].ljust(50)}")
        sys.stdout.flush()

    @pyqtSlot(str, str)
    def on_log_message(self, level: str, message: str):
        if self.verbose or level in ["warning", "error", "critical"]:
            print(f"\n[{level.upper()}] {message}")

    @pyqtSlot(str, str)
    def on_warning(self, title: str, message: str):
        print(f"\n[WARNING] {title}: {message}")

    @pyqtSlot(object)
    def on_finished(self, result: PipelineResult):
        print("\n" + "="*60)
        if result.success:
            print("SUCCESS")
            print(result.message)
            if result.stats:
                print("\nStatistics:")
                print(f"  Total items: {result.stats.get('total', 0)}")
                print(f"  Translated:  {result.stats.get('translated', 0)}")
                print(f"  Untranslated:{result.stats.get('untranslated', 0)}")
        else:
            print("FAILED")
            print(result.message)
            if result.error:
                print(f"Details: {result.error}")
        print("="*60)
        
        # Quit application
        QCoreApplication.quit()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

def load_config_override(config_path: str) -> dict:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return {}

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print the CLI header."""
    print("\n" + "="*60)
    print(f"       RenLocalizer CLI v{VERSION}")
    print("       Ren'Py Game Translation Tool")
    print("="*60)

def print_menu(title: str, options: list, show_back: bool = True) -> int:
    """Display a menu and get user selection."""
    print(f"\n  {title}")
    print("  " + "-"*40)
    for i, option in enumerate(options, 1):
        print(f"    [{i}] {option}")
    if show_back:
        print(f"    [0] Back")
    print()
    
    while True:
        try:
            choice = input("  Your choice: ").strip()
            if choice == '0' and show_back:
                return 0
            num = int(choice)
            if 1 <= num <= len(options):
                return num
            print("  Invalid choice")
        except ValueError:
            print("  Please enter a number")

def get_input(prompt: str, default: str = "") -> str:
    """Get text input from user with optional default."""
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"  {prompt}: ").strip()

def interactive_mode() -> dict:
    """Run interactive setup wizard."""
    config = {
        'input_path': '',
        'target_lang': 'tr',
        'source_lang': 'auto',
        'engine': 'google',
        'mode': 'auto',
        'proxy': False,
        'verbose': False
    }
    
    clear_screen()
    print_header()
    
    # Main Menu
    while True:
        choice = print_menu("MAIN MENU", [
            "Full Translation (Game EXE/Project)",
            "Translate Existing TL Folder",
            "Settings",
            "Help",
            "Exit"
        ], show_back=False)
        
        if choice == 1:  # Full Translation
            # Get input path
            print("\n  STEP 1: File/Folder Selection")
            print("  " + "-"*40)
            print("  Enter the game EXE or project folder path.")
            print()
            
            path = get_input("Path")
            if not path:
                print("\n  [!] Path cannot be empty")
                continue
                
            if not os.path.exists(path):
                print(f"\n  [!] File/folder not found: {path}")
                continue
            
            config['input_path'] = os.path.abspath(path)
            
            # Get target language
            print("\n  STEP 2: Target Language")
            print("  " + "-"*40)
            lang_choice = print_menu("Select target language", [
                "Turkish (tr)",
                "English (en)",
                "French (fr)",
                "German (de)",
                "Spanish (es)",
                "Russian (ru)",
                "Japanese (ja)",
                "Korean (ko)",
                "Chinese (zh)",
                "Other (enter manually)"
            ], show_back=True)
            
            if lang_choice == 0:
                continue
            
            lang_codes = ['tr', 'en', 'fr', 'de', 'es', 'ru', 'ja', 'ko', 'zh']
            if lang_choice <= 9:
                config['target_lang'] = lang_codes[lang_choice - 1]
            else:
                config['target_lang'] = get_input("Language code", "tr")
            
            # Get mode
            print("\n  STEP 3: Operation Mode")
            print("  " + "-"*40)
            mode_choice = print_menu("Select mode", [
                "Auto (Recommended)",
                "Full (UnRen + Translation - Windows Only)",
                "Translate Only"
            ], show_back=True)
            
            if mode_choice == 0:
                continue
            
            modes = ['auto', 'full', 'translate']
            config['mode'] = modes[mode_choice - 1]
            
            # Confirm and start
            clear_screen()
            print_header()
            print("\n  SUMMARY")
            print("  " + "-"*40)
            print(f"    Path:            {config['input_path']}")
            print(f"    Target Language: {config['target_lang']}")
            print(f"    Source Language: {config['source_lang']}")
            print(f"    Engine:          {config['engine']}")
            print(f"    Mode:            {config['mode']}")
            print()
            
            confirm = get_input("Start translation? (y/n)", "y")
            if confirm.lower() in ['y', 'yes']:
                return config
        
        elif choice == 2:  # Translate TL Folder
            print("\n  TRANSLATE EXISTING TL FOLDER")
            print("  " + "-"*40)
            print("  Enter the path to your game's tl folder")
            print("  Example: C:\\Games\\MyGame\\game\\tl\\turkish")
            print()
            
            path = get_input("TL Folder Path")
            if not path:
                print("\n  [!] Path cannot be empty")
                continue
                
            if not os.path.exists(path):
                print(f"\n  [!] Folder not found: {path}")
                continue
            
            config['input_path'] = os.path.abspath(path)
            config['mode'] = 'translate'  # Force translate mode for TL folders
            
            # Get target language
            print("\n  Target Language")
            print("  " + "-"*40)
            lang_choice = print_menu("Select target language", [
                "Turkish (tr)",
                "English (en)",
                "French (fr)",
                "German (de)",
                "Spanish (es)",
                "Russian (ru)",
                "Japanese (ja)",
                "Korean (ko)",
                "Chinese (zh)",
                "Other (enter manually)"
            ], show_back=True)
            
            if lang_choice == 0:
                continue
            
            lang_codes = ['tr', 'en', 'fr', 'de', 'es', 'ru', 'ja', 'ko', 'zh']
            if lang_choice <= 9:
                config['target_lang'] = lang_codes[lang_choice - 1]
            else:
                config['target_lang'] = get_input("Language code", "tr")
            
            # Confirm and start
            clear_screen()
            print_header()
            print("\n  SUMMARY")
            print("  " + "-"*40)
            print(f"    TL Folder:       {config['input_path']}")
            print(f"    Target Language: {config['target_lang']}")
            print(f"    Source Language: {config['source_lang']}")
            print(f"    Engine:          {config['engine']}")
            print(f"    Mode:            translate (TL folder)")
            print()
            
            confirm = get_input("Start translation? (y/n)", "y")
            if confirm.lower() in ['y', 'yes']:
                return config
            
        elif choice == 3:  # Settings
            while True:
                settings_choice = print_menu("SETTINGS", [
                    f"Source Language: {config['source_lang']}",
                    f"Translation Engine: {config['engine']}",
                    f"Proxy: {'On' if config['proxy'] else 'Off'}",
                    f"Verbose Logging: {'On' if config['verbose'] else 'Off'}"
                ])
                
                if settings_choice == 0:
                    break
                elif settings_choice == 1:
                    config['source_lang'] = get_input("Source language code", config['source_lang'])
                elif settings_choice == 2:
                    eng_choice = print_menu("Select engine", ["Google Translate", "DeepL"])
                    if eng_choice == 1:
                        config['engine'] = 'google'
                    elif eng_choice == 2:
                        config['engine'] = 'deepl'
                elif settings_choice == 3:
                    config['proxy'] = not config['proxy']
                elif settings_choice == 4:
                    config['verbose'] = not config['verbose']
                    
        elif choice == 4:  # Help
            clear_screen()
            print_header()
            print("""
  HELP
  ─────────────────────────────────────────
  
  RenLocalizer CLI automatically translates
  Ren'Py visual novel games.
  
  TRANSLATION MODES:
  
  1. Full Translation (Game EXE/Project)
     - For games with .exe or project folders
     - On Windows: Can run UnRen automatically
     - On Mac/Linux: Use with pre-extracted files
  
  2. Translate Existing TL Folder
     - For already generated tl/<lang> folders
     - Useful when you have .rpy translation files
     - Works on all platforms
  
  COMMAND LINE USAGE:
  python run_cli.py <path> --target-lang tr --mode auto
  
  For more info: docs/CLI_USAGE.md
  ─────────────────────────────────────────
            """)
            input("\n  Press Enter to continue...")
            
        elif choice == 5:  # Exit
            print("\n  Goodbye!\n")
            sys.exit(0)
    
    return config

def main() -> int:
    parser = argparse.ArgumentParser(description=f"RenLocalizer V{VERSION} CLI")
    
    parser.add_argument("input_path", nargs='?', default=None, 
                        help="Path to game executable, project directory, or translation file")
    
    # Configuration arguments
    parser.add_argument("--config", help="Path to JSON configuration file to override settings")
    
    # helper arguments
    parser.add_argument("--target-lang", "-t", default="tr", help="Target language code (default: tr)")
    parser.add_argument("--source-lang", "-s", default="auto", help="Source language code (default: auto)")
    parser.add_argument("--engine", "-e", default="google", choices=["google", "deepl"], help="Translation engine")
    
    # Mode arguments
    parser.add_argument("--mode", choices=["auto", "full", "translate"], default="auto", 
                        help="Operation mode: 'auto' (detect), 'full' (UnRen+Trans), 'translate' (Trans only)")
    
    # Other flags
    parser.add_argument("--proxy", action="store_true", help="Enable proxy")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive menu mode")
    
    args = parser.parse_args()
    
    # If no input_path provided or --interactive flag, run interactive mode
    if args.input_path is None or args.interactive:
        interactive_config = interactive_mode()
        args.input_path = interactive_config['input_path']
        args.target_lang = interactive_config['target_lang']
        args.source_lang = interactive_config['source_lang']
        args.engine = interactive_config['engine']
        args.mode = interactive_config['mode']
        args.proxy = interactive_config['proxy']
        args.verbose = interactive_config['verbose']

    # Create config manager
    config_manager = ConfigManager()
    
    # Apply CLI args to config
    # 1. Load external config if provided
    if args.config:
        overrides = load_config_override(args.config)
        # Apply overrides to internal config structures
        # This is a basic implementation - for deeper nesting, might need recursion
        if 'translation_settings' in overrides:
            for k, v in overrides['translation_settings'].items():
                if hasattr(config_manager.translation_settings, k):
                    setattr(config_manager.translation_settings, k, v)
        if 'app_settings' in overrides:
            for k, v in overrides['app_settings'].items():
                if hasattr(config_manager.app_settings, k):
                    setattr(config_manager.app_settings, k, v)
    
    # 2. Apply explicit CLI args (priority over config file)
    config_manager.translation_settings.target_language = args.target_lang
    config_manager.translation_settings.source_language = args.source_lang
    config_manager.translation_settings.enable_proxy = args.proxy
    
    # Setup Logging
    setup_logging(args.verbose)
    
    # Setup QCoreApplication
    app = QCoreApplication(sys.argv)
    app.setApplicationName("RenLocalizerCLI")
    app.setApplicationVersion(VERSION)

    # Initialize Managers
    translation_manager = TranslationManager(proxy_manager=None) # Proxy manager can be added if needed
    pipeline = TranslationPipeline(config_manager, translation_manager)
    
    # Create CLI Handler
    handler = CliHandler(pipeline, verbose=args.verbose)
    
    # Determine Mode
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"Error: Input path does not exist: {input_path}")
        return 1
        
    # Validating Mode vs OS
    is_windows = sys.platform == "win32"
    mode = args.mode
    is_exe_file = os.path.isfile(input_path) and input_path.lower().endswith(".exe")
    
    if mode == "auto":
        # Heuristic detection
        if is_exe_file:
            mode = "full" if is_windows else "translate"
        else:
            mode = "translate"
    
    # If user provided EXE but selected translate mode, we need to handle this
    if is_exe_file and mode == "translate":
        if is_windows:
            print("Note: EXE file provided with 'translate' mode. Switching to 'full' mode.")
            mode = "full"
        else:
            print("Error: EXE files require 'full' mode which is only available on Windows.")
            print("Please extract the game files first and provide the game folder path.")
            return 1
            
    if mode == "full" and not is_windows:
        print("Warning: 'full' mode (UnRen) is only supported on Windows. Switching to 'translate' mode.")
        mode = "translate"
        
    print(f"RenLocalizer CLI v{VERSION}")
    print(f"Input: {input_path}")
    print(f"Mode: {mode}")
    print(f"Target: {args.target_lang}")
    print("-" * 40)
    
    # Configure Pipeline
    engine_enum = TranslationEngine.GOOGLE
    if args.engine.lower() == "deepl":
        engine_enum = TranslationEngine.DEEPL

    # Setup pipeline based on mode
    if mode == "full":
        # Full pipeline expects an EXE path usually
        pipeline.configure(
            game_exe_path=input_path,
            target_language=args.target_lang,
            source_language=args.source_lang,
            engine=engine_enum,
            auto_unren=True,
            use_proxy=args.proxy
        )
        QTimer.singleShot(0, pipeline.run)
        
    elif mode == "translate":
        # Translate only mode - usage depends on what input_path is
        # If it's a directory, assume it's the game root or tl folder
        # pipeline has a method `translate_existing_tl` but it needs to be called carefully
        
        # We need to adapt the pipeline usage for pure translation without full UnRen flow
        # The pipeline class has `translate_existing_tl` method
        
        def run_translation_wrapper():
            # translate_existing_tl returns a PipelineResult directly
            try:
                result = pipeline.translate_existing_tl(
                    tl_root_path=input_path,
                    target_language=args.target_lang,
                    source_language=args.source_lang,
                    engine=engine_enum,
                    use_proxy=args.proxy
                )
                handler.on_finished(result)
            except Exception as e:
                import traceback
                print(f"Error during translation: {e}")
                traceback.print_exc()
                QCoreApplication.quit()

        QTimer.singleShot(0, run_translation_wrapper)

    # Setup signal handling for graceful exit (Ctrl+C)
    signal.signal(signal.SIGINT, lambda *args: QCoreApplication.quit())
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
