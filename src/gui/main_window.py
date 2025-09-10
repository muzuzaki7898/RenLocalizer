"""
Main Window
==========

Main application window with modern PyQt6/PySide6 interface.
"""

import sys
import logging
import asyncio
import time
from pathlib import Path
from typing import Optional, List

try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QProgressBar, QTextEdit, QFileDialog, QMenuBar, QStatusBar,
        QGroupBox, QCheckBox, QTabWidget, QSplitter, QTreeWidget, QTreeWidgetItem,
        QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QSlider
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
    from PyQt6.QtGui import QFont, QIcon, QPixmap, QAction
    GUI_FRAMEWORK = "PyQt6"
except ImportError:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QProgressBar, QTextEdit, QFileDialog, QMenuBar, QStatusBar,
        QGroupBox, QCheckBox, QTabWidget, QSplitter, QTreeWidget, QTreeWidgetItem,
        QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QSlider
    )
    from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer, QSize
    from PySide6.QtGui import QFont, QIcon, QPixmap, QAction
    GUI_FRAMEWORK = "PySide6"

from src.utils.config import ConfigManager
from src.core.parser import RenPyParser
from src.core.translator import TranslationManager, TranslationEngine, GoogleTranslator, DeepLTranslator, YandexTranslator
from src.core.output_formatter import RenPyOutputFormatter
from src.gui.translation_worker import TranslationWorker
from src.gui.settings_dialog import SettingsDialog
from src.gui.api_keys_dialog import ApiKeysDialog
from src.gui.info_dialog import InfoDialog
from src.gui.professional_themes import get_theme_qss

class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.config_manager = ConfigManager()
        self.parser = RenPyParser()
        
        # Current theme (default: solarized)
        self.current_theme = self.config_manager.app_settings.theme
        
        # Lazy import to avoid circular imports
        from src.core.proxy_manager import ProxyManager
        self.proxy_manager = ProxyManager()
        
        self.translation_manager = TranslationManager(self.proxy_manager)
        self.output_formatter = RenPyOutputFormatter()
        
        # Translation worker
        self.translation_worker: Optional[TranslationWorker] = None
        self.worker_thread: Optional[QThread] = None
        
        # State
        self.current_directory: Optional[Path] = None
        self.extracted_texts: List = []
        self.translation_results: List = []
        
        # Initialize UI
        self.init_ui()
        self.setup_translation_engines()
        
        # Load settings
        self.load_settings()
        
        # Initialize proxy manager in background
        self.initialize_proxy_manager()
        
        # Refresh UI language after everything is set up
        self.refresh_ui_language()
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(self.config_manager.get_ui_text("app_title"))
        self.setMinimumSize(1000, 700)
        
        # Set application icon
        icon_path = Path(__file__).parent.parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create main content
        self.create_main_content(layout)
        
        # Create status bar
        self.create_status_bar()
        
        # Apply theme
        self.apply_theme()
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu(self.config_manager.get_ui_text("file_menu"))
        
        open_action = QAction(self.config_manager.get_ui_text("open_directory"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction(self.config_manager.get_ui_text("save_translations"), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_translations)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(self.config_manager.get_ui_text("exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu(self.config_manager.get_ui_text("edit_menu"))
        
        settings_action = QAction(self.config_manager.get_ui_text("settings"), self)
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)
        
        api_keys_action = QAction(self.config_manager.get_ui_text("api_keys"), self)
        api_keys_action.triggered.connect(self.show_api_keys)
        edit_menu.addAction(api_keys_action)
        
        # View menu with theme options
        view_menu = menubar.addMenu(self.config_manager.get_ui_text("view_menu"))
        
        # Theme submenu
        theme_menu = view_menu.addMenu(self.config_manager.get_ui_text("theme_menu"))
        
        dark_theme_action = QAction(self.config_manager.get_ui_text("dark_theme"), self)
        dark_theme_action.triggered.connect(lambda: self.change_theme('dark'))
        theme_menu.addAction(dark_theme_action)
        
        solarized_theme_action = QAction(self.config_manager.get_ui_text("solarized_theme"), self)
        solarized_theme_action.triggered.connect(lambda: self.change_theme('solarized'))
        theme_menu.addAction(solarized_theme_action)
        
        # Help menu
        help_menu = menubar.addMenu(self.config_manager.get_ui_text("help_menu"))
        
        about_action = QAction(self.config_manager.get_ui_text("about"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        info_action = QAction(self.config_manager.get_ui_text("info"), self)
        info_action.triggered.connect(self.show_info)
        help_menu.addAction(info_action)
    
    def create_main_content(self, parent_layout):
        """Create the main content area."""
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        parent_layout.addWidget(splitter)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Results and logs
        right_panel = self.create_results_panel()
        splitter.addWidget(right_panel)
        
        # Set initial sizes
        splitter.setSizes([400, 600])
    
    def create_control_panel(self) -> QWidget:
        """Create the control panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Input section
        self.input_group = QGroupBox(self.config_manager.get_ui_text("input_section"))
        self.input_group._ui_key = "input_section"  # Store key for language updates
        input_layout = QFormLayout(self.input_group)
        
        self.directory_input = QLineEdit()
        self.directory_input.setPlaceholderText(self.config_manager.get_ui_text("directory_placeholder"))
        self.browse_button = QPushButton(self.config_manager.get_ui_text("browse"))
        self.browse_button.setProperty("class", "secondary")
        self.browse_button.clicked.connect(self.open_directory)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.directory_input)
        dir_layout.addWidget(self.browse_button)
        
        input_layout.addRow(self.config_manager.get_ui_text("directory_label"), dir_layout)
        layout.addWidget(self.input_group)
        
        # Translation settings
        self.trans_group = QGroupBox(self.config_manager.get_ui_text("translation_settings"))
        self.trans_group._ui_key = "translation_settings"  # Store key for language updates
        trans_layout = QFormLayout(self.trans_group)
        
        # Source language
        self.source_lang_combo = QComboBox()
        self.populate_language_combo(self.source_lang_combo, include_auto=True)
        trans_layout.addRow(self.config_manager.get_ui_text("source_lang_label"), self.source_lang_combo)
        
        # Target language
        self.target_lang_combo = QComboBox()
        self.populate_language_combo(self.target_lang_combo)
        trans_layout.addRow(self.config_manager.get_ui_text("target_lang_label"), self.target_lang_combo)
        
        # Translation engine
        self.engine_combo = QComboBox()
        self.populate_engine_combo()
        trans_layout.addRow(self.config_manager.get_ui_text("translation_engine_label"), self.engine_combo)
        
        # Output format
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem("Simple Format (Basit)", "simple")
        self.output_format_combo.addItem("Old/New Format (Ren'Py Standart)", "old_new")
        self.output_format_combo.setCurrentText("Old/New Format (Ren'Py Standart)")
        trans_layout.addRow(self.config_manager.get_ui_text("output_format_label"), self.output_format_combo)
        
        layout.addWidget(self.trans_group)
        
        # Advanced settings
        self.advanced_group = QGroupBox(self.config_manager.get_ui_text("advanced_settings"))
        self.advanced_group._ui_key = "advanced_settings"  # Store key for language updates
        advanced_layout = QFormLayout(self.advanced_group)
        
        # Concurrent threads
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setValue(self.config_manager.translation_settings.max_concurrent_threads)
        advanced_layout.addRow(self.config_manager.get_ui_text("concurrent_threads_label"), self.threads_spin)
        
        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 2000)
        self.batch_size_spin.setValue(self.config_manager.translation_settings.max_batch_size)
        advanced_layout.addRow(self.config_manager.get_ui_text("batch_size_label"), self.batch_size_spin)
        
        # Request delay
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 5.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setValue(0.1)
        self.delay_spin.setSuffix(" s")
        advanced_layout.addRow(self.config_manager.get_ui_text("request_delay_label"), self.delay_spin)
        
        # Parser workers (for parallel file processing)
        self.parser_workers_spin = QSpinBox()
        self.parser_workers_spin.setRange(1, 16)
        self.parser_workers_spin.setValue(4)
        self.parser_workers_spin.setToolTip("Paralel dosya işleme için worker sayısı (çok dosyalı projeler için)")
        advanced_layout.addRow(self.config_manager.get_ui_text("parser_workers_label"), self.parser_workers_spin)
        
        # Proxy enabled with refresh button
        proxy_layout = QHBoxLayout()
        self.proxy_check = QCheckBox()
        self.proxy_check.setChecked(True)
        self.proxy_check.stateChanged.connect(self.on_proxy_setting_changed)
        proxy_layout.addWidget(self.proxy_check)
        
        self.refresh_proxy_btn = QPushButton(self.config_manager.get_ui_text("refresh_proxies_btn"))
        self.refresh_proxy_btn.setMaximumWidth(120)
        self.refresh_proxy_btn.clicked.connect(self.refresh_proxies)
        proxy_layout.addWidget(self.refresh_proxy_btn)
        proxy_layout.addStretch()
        
        proxy_widget = QWidget()
        proxy_widget.setLayout(proxy_layout)
        advanced_layout.addRow(self.config_manager.get_ui_text("proxy_enabled_label"), proxy_widget)
        
        layout.addWidget(self.advanced_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton(self.config_manager.get_ui_text("start_translation"))
        self.start_button.setProperty("class", "success")
        self.start_button.clicked.connect(self.start_translation)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton(self.config_manager.get_ui_text("stop_translation"))
        self.stop_button.setProperty("class", "error")
        self.stop_button.clicked.connect(self.stop_translation)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        # Progress
        progress_group = QGroupBox(self.config_manager.get_ui_text("progress"))
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel(self.config_manager.get_ui_text("ready"))
        self.progress_label.setProperty("class", "caption")
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        return widget
    
    def create_results_panel(self) -> QWidget:
        """Create the results panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tab widget for different views
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Extracted texts tab
        self.extracted_tree = QTreeWidget()
        self.extracted_tree.setHeaderLabels([
            self.config_manager.get_ui_text("text_header"), 
            self.config_manager.get_ui_text("type_header"), 
            self.config_manager.get_ui_text("file_header"), 
            self.config_manager.get_ui_text("line_header")
        ])
        self.tab_widget.addTab(self.extracted_tree, self.config_manager.get_ui_text("extracted_texts_tab"))
        
        # Translation results tab
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels([
            self.config_manager.get_ui_text("original_header"), 
            self.config_manager.get_ui_text("translated_header"), 
            self.config_manager.get_ui_text("engine_header"), 
            self.config_manager.get_ui_text("status_header")
        ])
        self.tab_widget.addTab(self.results_tree, self.config_manager.get_ui_text("translation_results_tab"))
        
        # Log tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.tab_widget.addTab(self.log_text, self.config_manager.get_ui_text("log_tab"))
        
        return widget
    
    def populate_language_combo(self, combo: QComboBox, include_auto: bool = False):
        """Populate language combo box."""
        languages = self.config_manager.get_supported_languages()
        
        if not include_auto and 'auto' in languages:
            del languages['auto']
        
        for code, name in languages.items():
            combo.addItem(f"{name} ({code})", code)
    
    def populate_engine_combo(self):
        """Populate translation engine combo box with type indicators."""
        engines = [
            (TranslationEngine.GOOGLE, "Google Translate (WEB - Ücretsiz)"),
            (TranslationEngine.DEEPL, "DeepL (API - Anahtar Gerekli)"),
            (TranslationEngine.BING, "Microsoft Translator (API - Anahtar Gerekli)"),
            (TranslationEngine.YANDEX, "Yandex Translate (WEB - Ücretsiz)"),
            (TranslationEngine.LIBRETRANSLATOR, "LibreTranslator (API - Yerel/Özgür)")
        ]
        
        for engine, name in engines:
            self.engine_combo.addItem(name, engine)
    
    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = self.statusBar()
        
        # Status label
        self.status_label = QLabel(self.config_manager.get_ui_text("ready"))
        self.status_label.setProperty("class", "subtitle")
        self.status_bar.addWidget(self.status_label)
        
        # Stats labels
        self.files_label = QLabel(self.config_manager.get_ui_text("files_status").format(count=0))
        self.files_label.setProperty("class", "caption")
        self.status_bar.addPermanentWidget(self.files_label)
        
        self.texts_label = QLabel(self.config_manager.get_ui_text("texts_status").format(count=0))
        self.texts_label.setProperty("class", "caption")
        self.status_bar.addPermanentWidget(self.texts_label)
        
        self.translations_label = QLabel(self.config_manager.get_ui_text("translations_status").format(count=0))
        self.translations_label.setProperty("class", "caption")
        self.status_bar.addPermanentWidget(self.translations_label)
    
    def apply_theme(self):
        """Apply the current theme to the application."""
        try:
            # Get QSS for current theme
            qss = get_theme_qss(self.current_theme)
            self.setStyleSheet(qss)
            
            # Set window properties for modern look
            self.setWindowTitle("RenLocalizer V2 - Professional Ren'Py Translation Tool")
            
            self.logger.info(f"Applied {self.current_theme} theme successfully")
            
        except Exception as e:
            self.logger.error(f"Error applying theme {self.current_theme}: {e}")
            # Fallback to light theme
            if self.current_theme != 'light':
                self.current_theme = 'light'
                self.apply_theme()
    
    def change_theme(self, theme_name: str):
        """Change the application theme."""
        available_themes = ['dark', 'solarized']  # Şu an için sadece bu temalar aktif
        if theme_name in available_themes:
            self.current_theme = theme_name
            self.config_manager.app_settings.theme = theme_name  # set_setting yerine doğrudan atama
            self.config_manager.save_config()
            self.apply_theme()
            self.logger.info(f"Theme changed to: {theme_name}")
        else:
            self.logger.warning(f"Unknown or unavailable theme: {theme_name}")
    
    def setup_translation_engines(self):
        """Setup translation engines."""
        # Add Google Translator (free)
        google_translator = GoogleTranslator(proxy_manager=self.proxy_manager)
        self.translation_manager.add_translator(TranslationEngine.GOOGLE, google_translator)
        
        # Add DeepL if API key is available
        deepl_key = self.config_manager.get_api_key("deepl")
        if deepl_key:
            deepl_translator = DeepLTranslator(api_key=deepl_key, proxy_manager=self.proxy_manager)
            self.translation_manager.add_translator(TranslationEngine.DEEPL, deepl_translator)
        
        # Add Yandex if API key is available
        yandex_key = self.config_manager.get_api_key("yandex")
        if yandex_key:
            yandex_translator = YandexTranslator(api_key=yandex_key, proxy_manager=self.proxy_manager)
            self.translation_manager.add_translator(TranslationEngine.YANDEX, yandex_translator)
    
    def initialize_proxy_manager(self):
        """Initialize proxy manager in background only if enabled."""
        # Check if proxy is enabled in config
        proxy_enabled = self.config_manager.proxy_settings.enabled
        if not proxy_enabled:
            self.logger.info("Proxy disabled in config - skipping proxy initialization")
            # Update status to show proxy is disabled
            QTimer.singleShot(100, lambda: self.status_label.setText(f"{self.config_manager.get_ui_text('ready')} - No Proxy"))
            return
        
        import asyncio
        import threading
        
        def run_async_init():
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run proxy initialization
                loop.run_until_complete(self.proxy_manager.initialize())
                
                # Log proxy stats
                stats = self.proxy_manager.get_proxy_stats()
                self.logger.info(f"Proxy manager initialized: {stats['working_proxies']}/{stats['total_proxies']} working proxies")
                
            except Exception as e:
                self.logger.error(f"Error initializing proxy manager: {e}")
            finally:
                loop.close()
        
        # Start proxy initialization in background thread
        proxy_thread = threading.Thread(target=run_async_init, daemon=True)
        proxy_thread.start()
        self.logger.info("Proxy manager initialization started in background")
    
    def load_settings(self):
        """Load settings from configuration."""
        # Window size
        self.resize(
            self.config_manager.app_settings.window_width,
            self.config_manager.app_settings.window_height
        )
        
        # Set language selections
        source_lang = self.config_manager.translation_settings.source_language
        target_lang = self.config_manager.translation_settings.target_language
        
        # Find and set current language selections
        for i in range(self.source_lang_combo.count()):
            if self.source_lang_combo.itemData(i) == source_lang:
                self.source_lang_combo.setCurrentIndex(i)
                break
        
        for i in range(self.target_lang_combo.count()):
            if self.target_lang_combo.itemData(i) == target_lang:
                self.target_lang_combo.setCurrentIndex(i)
                break
        
        # Set other settings
        self.threads_spin.setValue(self.config_manager.translation_settings.max_concurrent_threads)
        self.batch_size_spin.setValue(self.config_manager.translation_settings.max_batch_size)
        self.delay_spin.setValue(self.config_manager.translation_settings.request_delay)
        self.proxy_check.setChecked(self.config_manager.proxy_settings.enabled)
        self.parser_workers_spin.setValue(getattr(self.config_manager.app_settings, 'parser_workers', 4))
        
        # Set output format
        output_format = getattr(self.config_manager.app_settings, 'output_format', 'old_new')
        for i in range(self.output_format_combo.count()):
            if self.output_format_combo.itemData(i) == output_format:
                self.output_format_combo.setCurrentIndex(i)
                break
        
        # Set last directory
        if self.config_manager.app_settings.last_input_directory:
            self.directory_input.setText(self.config_manager.app_settings.last_input_directory)
    
    def save_settings(self):
        """Save current settings."""
        # Window size
        self.config_manager.app_settings.window_width = self.width()
        self.config_manager.app_settings.window_height = self.height()
        
        # Language settings
        self.config_manager.translation_settings.source_language = self.source_lang_combo.currentData()
        self.config_manager.translation_settings.target_language = self.target_lang_combo.currentData()
        
        # Other settings
        self.config_manager.translation_settings.max_concurrent_threads = self.threads_spin.value()
        self.config_manager.translation_settings.max_batch_size = self.batch_size_spin.value()
        self.config_manager.translation_settings.request_delay = self.delay_spin.value()
        self.config_manager.proxy_settings.enabled = self.proxy_check.isChecked()
        
        # Save output format
        self.config_manager.app_settings.output_format = self.output_format_combo.currentData()
        
        # Save parser workers
        self.config_manager.app_settings.parser_workers = self.parser_workers_spin.value()
        # Anlık concurrency güncellemesi
        if hasattr(self, 'translation_manager'):
            try:
                self.translation_manager.set_max_concurrency(self.threads_spin.value())
            except Exception:
                pass
        
        # Directory
        self.config_manager.app_settings.last_input_directory = self.directory_input.text()
        
        # Save to file
        self.config_manager.save_config()
    
    def open_directory(self):
        """Open directory dialog."""
        directory = QFileDialog.getExistingDirectory(
            self,
            self.config_manager.get_ui_text("select_directory_title"),
            self.config_manager.app_settings.last_input_directory
        )
        
        if directory:
            self.directory_input.setText(directory)
            self.current_directory = Path(directory)
            self.scan_directory()
    
    def scan_directory(self):
        """Scan directory for .rpy files."""
        if not self.current_directory or not self.current_directory.exists():
            return
        
        try:
            self.status_label.setText(self.config_manager.get_ui_text("scanning_directory"))
            
            # Check if we should use parallel processing
            rpy_files = list(self.current_directory.rglob('*.rpy'))
            use_parallel = len(rpy_files) > 10  # Use parallel for 10+ files
            
            if use_parallel:
                self.status_label.setText(f"Scanning {len(rpy_files)} files (parallel mode)...")
                max_workers = self.parser_workers_spin.value()
                
                # Use parallel processing for large projects
                extracted_data = self.parser.extract_from_directory_parallel(
                    self.current_directory, 
                    recursive=True, 
                    max_workers=max_workers
                )
                
                # Convert to MainWindow format
                self.extracted_texts = []
                for file_path, texts in extracted_data.items():
                    for text in texts:
                        text_data = {
                            'text': text,
                            'type': 'dialogue',
                            'file_path': str(file_path),
                            'line_number': 1,
                            'character': '',
                            'context': ''
                        }
                        self.extracted_texts.append(text_data)
            else:
                # Use standard processing for small projects
                self.extracted_texts = self.parser.parse_directory(self.current_directory)
            
            # Update extracted texts tree
            self.update_extracted_texts_tree()
            
            # Update status
            processing_mode = "parallel" if use_parallel else "sequential"
            self.files_label.setText(self.config_manager.get_ui_text("files_status").format(count=len(rpy_files)))
            self.texts_label.setText(self.config_manager.get_ui_text("texts_status").format(count=len(self.extracted_texts)))
            self.status_label.setText(f"{self.config_manager.get_ui_text('directory_scanned')} ({processing_mode})")
            
            self.logger.info(f"Scanned directory: {len(self.extracted_texts)} texts found using {processing_mode} processing")
            
        except Exception as e:
            self.logger.error(f"Error scanning directory: {e}")
            self.status_label.setText(self.config_manager.get_ui_text("error_scanning_directory"))
    
    def update_extracted_texts_tree(self):
        """Update the extracted texts tree."""
        self.extracted_tree.clear()
        
        for text_data in self.extracted_texts:
            item = QTreeWidgetItem([
                text_data['text'][:100] + "..." if len(text_data['text']) > 100 else text_data['text'],
                text_data['type'],
                Path(text_data['file_path']).name,
                str(text_data['line_number'])
            ])
            self.extracted_tree.addTopLevelItem(item)
    
    def start_translation(self):
        """Start the translation process."""
        if not self.extracted_texts:
            QMessageBox.warning(self, self.config_manager.get_ui_text("warning"), self.config_manager.get_ui_text("no_texts_warning"))
            return
        
        # Get current settings
        source_lang = self.source_lang_combo.currentData()
        target_lang = self.target_lang_combo.currentData()
        engine = self.engine_combo.currentData()
        use_proxy = self.proxy_check.isChecked()
        
        # Configure translation manager based on proxy setting
        if use_proxy:
            self.logger.info("Translation will use proxy rotation")
        else:
            self.logger.info("Translation will use direct connection (no proxy)")
        # Concurrency runtime güncelle
        try:
            self.translation_manager.set_max_concurrency(self.threads_spin.value())
        except Exception:
            pass
        
        # Create and start worker
        self.translation_worker = TranslationWorker(
            texts=self.extracted_texts,
            source_lang=source_lang,
            target_lang=target_lang,
            engine=engine,
            translation_manager=self.translation_manager,
            config=self.config_manager,
            use_proxy=use_proxy
        )
        
        # Connect signals
        self.translation_worker.progress_updated.connect(self.update_progress)
        self.translation_worker.translation_completed.connect(self.on_translation_completed)
        self.translation_worker.error_occurred.connect(self.on_translation_error)
        self.translation_worker.finished.connect(self.on_translation_finished)
        
        # Start in thread
        self.worker_thread = QThread()
        self.translation_worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.translation_worker.run)
        self.worker_thread.start()
        
        # Update UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(self.config_manager.get_ui_text("starting_translation"))
    
    def stop_translation(self):
        """Stop the translation process."""
        if self.translation_worker:
            self.translation_worker.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(self.config_manager.get_ui_text("stopping"))
    
    def update_progress(self, completed: int, total: int, current_text: str):
        """Update translation progress."""
        if total > 0:
            progress = int((completed / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f"{completed}/{total} - {current_text[:50]}...")
            self.translations_label.setText(self.config_manager.get_ui_text("translations_status").format(count=completed))
    
    def on_translation_completed(self, results):
        """Handle translation completion."""
        self.translation_results = results
        self.update_results_tree()
        self.status_label.setText(self.config_manager.get_ui_text("translation_completed"))
        
        # Auto-save translations if auto-save is enabled
        if hasattr(self.config_manager.app_settings, 'auto_save_translations') and self.config_manager.app_settings.auto_save_translations:
            self.auto_save_translations()
        else:
            # Show save dialog
            reply = QMessageBox.question(
                self,
                self.config_manager.get_ui_text("save_translations"),
                self.config_manager.get_ui_text("auto_save_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_translations()
    
    def auto_save_translations(self):
        """Automatically save translations to default location."""
        if not self.translation_results:
            return
        
        try:
            # Determine output directory based on project structure
            output_dir = self._determine_output_directory()
            
            target_lang = self.target_lang_combo.currentData()
            selected_format = self.output_format_combo.currentData()
            
            # Save with Ren'Py structure support
            output_files = self.output_formatter.organize_output_files(
                self.translation_results,
                Path(output_dir),
                target_lang,
                output_format=selected_format,
                create_renpy_structure=True  # Enable Ren'Py structure
            )
            
            self.config_manager.app_settings.last_output_directory = output_dir
            self.save_settings()
            
            # Show success message
            self.log_text.append(f"✅ {self.config_manager.get_ui_text('auto_save_success').format(count=len(output_files), directory=output_dir)}")
            self.status_label.setText(f"{self.config_manager.get_ui_text('translation_completed')} - {self.config_manager.get_ui_text('auto_saved')}")
            
        except Exception as e:
            self.logger.error(f"Error auto-saving translations: {e}")
            self.log_text.append(f"❌ Auto-save error: {str(e)}")
            
            # Show error dialog
            QMessageBox.critical(
                self,
                self.config_manager.get_ui_text("auto_save_error"),
                self.config_manager.get_ui_text("auto_save_error_message").format(error=str(e))
            )
    
    def _determine_output_directory(self) -> str:
        """Determine the best output directory for translations."""
        # Check if we have a current directory (input directory)
        if self.current_directory:
            project_root = Path(self.current_directory)
            
            # Check if it's a Ren'Py project (has game folder)
            game_dir = None
            
            # Check current directory and parents for game folder
            current = project_root
            while current != current.parent:
                if (current / "game").exists():
                    game_dir = current
                    break
                current = current.parent
            
            if game_dir:
                # Ren'Py project detected - return project root
                self.log_text.append(f"🎮 Ren'Py project detected: {game_dir}")
                return str(game_dir)
            else:
                # Not a Ren'Py project - use input directory
                return str(project_root)
        
        # Use last output directory or create default
        output_dir = self.config_manager.app_settings.last_output_directory
        if not output_dir or not Path(output_dir).exists():
            # Create default output directory
            current_time = time.strftime("%Y%m%d_%H%M%S")
            output_dir = Path.cwd() / "translations" / f"translation_{current_time}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_dir = str(output_dir)
        
        return output_dir
    
    def on_translation_error(self, error_message):
        """Handle translation error."""
        self.logger.error(f"Translation error: {error_message}")
        self.log_text.append(f"ERROR: {error_message}")
        QMessageBox.critical(self, self.config_manager.get_ui_text("translation_error"), error_message)
    
    def on_translation_finished(self):
        """Handle translation process finished."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        
        self.translation_worker = None
    
    def update_results_tree(self):
        """Update the translation results tree."""
        self.results_tree.clear()
        
        for result in self.translation_results:
            status = self.config_manager.get_ui_text("success") if result.success else self.config_manager.get_ui_text("failed")
            
            item = QTreeWidgetItem([
                result.original_text[:50] + "..." if len(result.original_text) > 50 else result.original_text,
                result.translated_text[:50] + "..." if len(result.translated_text) > 50 else result.translated_text,
                result.engine.value,
                status
            ])
            
            # Color code based on success
            if not result.success:
                item.setBackground(0, self.palette().color(self.palette().ColorRole.Light))
            
            self.results_tree.addTopLevelItem(item)
    
    def save_translations(self):
        """Save translations to files."""
        if not self.translation_results:
            QMessageBox.warning(self, self.config_manager.get_ui_text("warning"), self.config_manager.get_ui_text("no_translations_warning"))
            return
        
        output_dir = QFileDialog.getExistingDirectory(
            self,
            self.config_manager.get_ui_text("select_output_directory"),
            self.config_manager.app_settings.last_output_directory
        )
        
        if output_dir:
            try:
                target_lang = self.target_lang_combo.currentData()
                selected_format = self.output_format_combo.currentData()
                
                # Save with Ren'Py structure support
                output_files = self.output_formatter.organize_output_files(
                    self.translation_results,
                    Path(output_dir),
                    target_lang,
                    output_format=selected_format,
                    create_renpy_structure=True  # Enable Ren'Py structure
                )
                
                self.config_manager.app_settings.last_output_directory = output_dir
                self.save_settings()
                
                QMessageBox.information(
                    self,
                    self.config_manager.get_ui_text("success"),
                    self.config_manager.get_ui_text("translations_saved").format(count=len(output_files), directory=output_dir)
                )
                
            except Exception as e:
                self.logger.error(f"Error saving translations: {e}")
                QMessageBox.critical(self, self.config_manager.get_ui_text("error"), self.config_manager.get_ui_text("error_saving").format(error=str(e)))
    
    def update_status(self):
        """Update status periodically."""
        # Update proxy status in status bar
        if hasattr(self, 'proxy_manager') and self.proxy_manager.proxies:
            stats = self.proxy_manager.get_proxy_stats()
            working_proxies = stats['working_proxies']
            total_proxies = stats['total_proxies']
            
            # Update status bar with proxy info
            if working_proxies > 0:
                extra = ""
                # Cache stats ekle
                if hasattr(self, 'translation_manager'):
                    try:
                        cstats = self.translation_manager.get_cache_stats()
                        extra = f" - Cache: {cstats['hits']}/{cstats['misses']} ({cstats['hit_rate']}%)"
                    except Exception:
                        pass
                conc_part = ""
                if hasattr(self, 'translation_manager'):
                    try:
                        conc_part = f" - Concurrency: {self.translation_manager.max_concurrent_requests}"
                    except Exception:
                        pass
                self.status_label.setText(f"{self.config_manager.get_ui_text('ready')} - Proxy: {working_proxies}/{total_proxies}{conc_part}{extra}")
            else:
                self.status_label.setText(f"{self.config_manager.get_ui_text('ready')} - No Proxy")
        else:
            # Show loading proxy status
            extra = ""
            if hasattr(self, 'translation_manager'):
                try:
                    cstats = self.translation_manager.get_cache_stats()
                    extra = f" - Cache: {cstats['hits']}/{cstats['misses']} ({cstats['hit_rate']}%)"
                except Exception:
                    pass
            conc_part = ""
            if hasattr(self, 'translation_manager'):
                try:
                    conc_part = f" - Concurrency: {self.translation_manager.max_concurrent_requests}"
                except Exception:
                    pass
            self.status_label.setText(f"{self.config_manager.get_ui_text('ready')} - Loading Proxies...{conc_part}{extra}")
    
    def show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self.config_manager, self)
        dialog.language_changed.connect(self.refresh_ui_language)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_settings()
            # Check if language or theme changed
            if hasattr(dialog, 'language_changed_flag') and dialog.language_changed_flag:
                self.refresh_ui_language()
            if hasattr(dialog, 'theme_changed_flag') and dialog.theme_changed_flag:
                self.current_theme = self.config_manager.app_settings.theme
                self.apply_theme()
    
    def show_api_keys(self):
        """Show API keys dialog."""
        dialog = ApiKeysDialog(self.config_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setup_translation_engines()  # Refresh engines with new keys
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            self.config_manager.get_ui_text("about_title"),
            self.config_manager.get_ui_text("about_content").format(framework=GUI_FRAMEWORK)
        )
    
    def show_info(self):
        """Show multi-page info dialog with detailed information."""
        dialog = InfoDialog(self)
        dialog.exec()
    
    def closeEvent(self, event):
        """Handle application close."""
        # Stop any running translation
        if self.translation_worker:
            self.stop_translation()
        
        # Save settings
        self.save_settings()

        # Asenkron translator oturumlarını kapat
        try:
            import asyncio
            asyncio.run(self.translation_manager.close_all())
        except Exception:
            pass
        
        event.accept()
    
    def refresh_ui_language(self):
        """Refresh UI elements when language changes."""
        # Update window title
        self.setWindowTitle(self.config_manager.get_ui_text("app_title"))
        
        # Update menu items (recreate menu bar)
        self.menuBar().clear()
        self.create_menu_bar()
        
        # Update group box titles and labels
        self.update_control_panel_texts()
        self.update_results_panel_texts()
        self.update_status_bar_texts()
        
        # Update button texts
        self.start_button.setText(self.config_manager.get_ui_text("start_translation"))
        self.stop_button.setText(self.config_manager.get_ui_text("stop_translation"))
        
        # Update progress label
        self.progress_label.setText(self.config_manager.get_ui_text("ready"))
        
        # Update status label
        self.status_label.setText(self.config_manager.get_ui_text("ready"))
    
    def update_control_panel_texts(self):
        """Update control panel text elements."""
        # Update group box titles
        if hasattr(self, 'input_group'):
            self.input_group.setTitle(self.config_manager.get_ui_text("input_section"))
        if hasattr(self, 'trans_group'):
            self.trans_group.setTitle(self.config_manager.get_ui_text("translation_settings"))
        if hasattr(self, 'advanced_group'):
            self.advanced_group.setTitle(self.config_manager.get_ui_text("advanced_settings"))
        
        # Update button texts
        if hasattr(self, 'browse_button'):
            self.browse_button.setText(self.config_manager.get_ui_text("browse"))
        if hasattr(self, 'directory_input'):
            self.directory_input.setPlaceholderText(self.config_manager.get_ui_text("directory_placeholder"))
    
    def update_results_panel_texts(self):
        """Update results panel text elements."""
        # Update tab texts
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setTabText(0, self.config_manager.get_ui_text("extracted_texts_tab"))
            self.tab_widget.setTabText(1, self.config_manager.get_ui_text("translation_results_tab"))
            self.tab_widget.setTabText(2, self.config_manager.get_ui_text("log_tab"))
        
        # Update tree headers
        if hasattr(self, 'extracted_tree'):
            self.extracted_tree.setHeaderLabels([
                self.config_manager.get_ui_text("text_header"),
                self.config_manager.get_ui_text("type_header"),
                self.config_manager.get_ui_text("file_header"),
                self.config_manager.get_ui_text("line_header")
            ])
        
        if hasattr(self, 'results_tree'):
            self.results_tree.setHeaderLabels([
                self.config_manager.get_ui_text("original_header"),
                self.config_manager.get_ui_text("translated_header"),
                self.config_manager.get_ui_text("engine_header"),
                self.config_manager.get_ui_text("status_header")
            ])
    
    def update_status_bar_texts(self):
        """Update status bar text elements."""
        if hasattr(self, 'files_label'):
            current_count = self.files_label.text().split(': ')[-1] if ': ' in self.files_label.text() else '0'
            self.files_label.setText(self.config_manager.get_ui_text("files_status").format(count=current_count))
        
        if hasattr(self, 'texts_label'):
            current_count = self.texts_label.text().split(': ')[-1] if ': ' in self.texts_label.text() else '0'
            self.texts_label.setText(self.config_manager.get_ui_text("texts_status").format(count=current_count))
        
        if hasattr(self, 'translations_label'):
            current_count = self.translations_label.text().split(': ')[-1] if ': ' in self.translations_label.text() else '0'
            self.translations_label.setText(self.config_manager.get_ui_text("translations_status").format(count=current_count))
    
    def on_proxy_setting_changed(self, state):
        """Handle proxy setting changes."""
        enabled = self.proxy_check.isChecked()
        self.logger.info(f"Proxy setting changed: {'enabled' if enabled else 'disabled'}")
        
        # Update translation manager
        if hasattr(self, 'translation_manager'):
            self.translation_manager.set_proxy_enabled(enabled)
        
        # Update config
        self.config_manager.proxy_settings.enabled = enabled
        
        # Save config if auto-save is enabled
        if self.config_manager.app_settings.auto_save_settings:
            self.config_manager.save_config()
    
    def refresh_proxies(self):
        """Manually refresh proxy list."""
        # Check if proxy is enabled
        if not self.config_manager.proxy_settings.enabled:
            self.logger.info("Proxy disabled - skipping proxy refresh")
            self.status_label.setText(f"{self.config_manager.get_ui_text('ready')} - No Proxy")
            return
            
        if hasattr(self, 'proxy_manager'):
            self.logger.info("Manually refreshing proxy list...")
            
            # Run proxy refresh in background thread
            import threading
            
            def refresh_task():
                try:
                    # Run async proxy initialization in new event loop
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.proxy_manager.initialize())
                    loop.close()
                    
                    # Log result
                    proxy_count = len(self.proxy_manager.working_proxies)
                    self.logger.info(f"Proxy refresh completed. Found {proxy_count} working proxies")
                    
                except Exception as e:
                    self.logger.error(f"Error refreshing proxies: {e}")
            
            refresh_thread = threading.Thread(target=refresh_task, daemon=True)
            refresh_thread.start()
