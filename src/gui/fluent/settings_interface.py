# -*- coding: utf-8 -*-
"""
Settings Interface
==================

Settings page with Fluent SettingCards for all application configurations.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup, PushSettingCard,
    SwitchSettingCard, PrimaryPushSettingCard, HyperlinkCard,
    SettingCard, ComboBox, Slider, LineEdit, PasswordLineEdit, SpinBox, DoubleSpinBox,
    FluentIcon as FIF, TitleLabel, BodyLabel, InfoBar, InfoBarPosition,
    qconfig, MessageBox
)

from src.utils.config import ConfigManager, Language


class SettingsInterface(ScrollArea):
    """Settings interface with Fluent SettingCards."""
    
    # Signal emitted when language changes
    language_changed = pyqtSignal()
    # Signal emitted when debug engines toggle changes
    debug_engines_changed = pyqtSignal(bool)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent
        
        self.setObjectName("settingsInterface")
        self.setWidgetResizable(True)
        
        # Create main widget and layout
        self.scroll_widget = QWidget()
        self.expand_layout = ExpandLayout(self.scroll_widget)
        self.expand_layout.setContentsMargins(36, 20, 36, 20)
        self.expand_layout.setSpacing(28)
        
        self._init_ui()
        self.setWidget(self.scroll_widget)

    def _init_ui(self):
        """Initialize the user interface."""
        # Title
        title_label = TitleLabel(self.config_manager.get_ui_text("nav_settings", "Ayarlar"))
        self.expand_layout.addWidget(title_label)
        
        # General Settings Group
        self._create_general_group()
        
        # Translation Settings Group
        self._create_translation_group()
        
        # AI Settings Group
        self._create_ai_group()

        # API Keys Group
        self._create_api_keys_group()
        
        # Proxy Settings Group
        self._create_proxy_group()
        
        # Advanced Settings Group
        self._create_advanced_group()

    def _create_general_group(self):
        """Create general settings group."""
        self.general_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_general", "Genel Ayarlar"),
            self.scroll_widget
        )
        
        # Application Language
        self.language_card = SettingCard(
            icon=FIF.LANGUAGE,
            title=self.config_manager.get_ui_text("ui_language", "Uygulama Dili"),
            content=self.config_manager.get_ui_text("ui_language_desc", "Arayüz dilini değiştir"),
            parent=self.general_group
        )
        
        self.language_combo = ComboBox(self.language_card)
        
        # Get all available languages dynamically
        available_langs = self.config_manager.get_ui_translations().keys()
        
        # Get language metadata from ConfigManager
        all_lang_meta = self.config_manager.get_all_languages()
        # Create map: api_code -> native_name
        display_names_map = {item['api']: item['native'] for item in all_lang_meta}
        
        # Store codes for indexing
        self.LANG_CODES = sorted(available_langs)
        for code in self.LANG_CODES:
            # Fallback to English name if native not found, then to code itself
            display_name = display_names_map.get(code, code)
            self.language_combo.addItem(display_name)
            
        self.language_combo.setFixedWidth(120)
        self.language_card.hBoxLayout.addWidget(self.language_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.language_card.hBoxLayout.addSpacing(16)
        
        # Set current language
        current_lang = self.config_manager.app_settings.ui_language
        try:
            start_idx = self.LANG_CODES.index(current_lang)
            self.language_combo.setCurrentIndex(start_idx)
        except (ValueError, IndexError):
            self.language_combo.setCurrentIndex(0)
            
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.general_group.addSettingCard(self.language_card)
        
        # Application Theme (requires restart for consistent rendering)
        self.theme_card = SettingCard(
            icon=FIF.CONSTRACT,
            title=self.config_manager.get_ui_text("app_theme", "Uygulama Teması"),
            content=self.config_manager.get_ui_text("app_theme_desc", "Arayüz renklerini değiştir (Windows ayarlarından bağımsız)"),
            parent=self.general_group
        )
        
        # Theme mapping (index -> theme_key)
        self.THEME_MAP = [
            ("dark", self.config_manager.get_ui_text("theme_dark", "🌙 Koyu")),
            ("light", self.config_manager.get_ui_text("theme_light", "☀️ Açık")),
            ("red", self.config_manager.get_ui_text("theme_red", "🔴 Kırmızı")),
            ("turquoise", self.config_manager.get_ui_text("theme_turquoise", "🔵 Turkuaz")),
            ("green", self.config_manager.get_ui_text("theme_green", "🌿 Yeşil")),
            ("neon", self.config_manager.get_ui_text("theme_neon", "🌈 Neon")),
        ]
        
        self.theme_combo = ComboBox(self.theme_card)
        for theme_key, theme_label in self.THEME_MAP:
            self.theme_combo.addItem(theme_label)
        self.theme_combo.setFixedWidth(150)
        self.theme_card.hBoxLayout.addWidget(self.theme_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.theme_card.hBoxLayout.addSpacing(16)
        
        # Set current theme from config
        start_theme = getattr(self.config_manager.app_settings, 'app_theme', 'dark')
        # Find index for the current theme
        start_index = 0
        for i, (theme_key, _) in enumerate(self.THEME_MAP):
            if theme_key == start_theme:
                start_index = i
                break
        self.theme_combo.setCurrentIndex(start_index)
            
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.general_group.addSettingCard(self.theme_card)
        
        # Check for Updates
        self.check_updates_card = SwitchSettingCard(
            icon=FIF.UPDATE,
            title=self.config_manager.get_ui_text("check_updates", "Güncellemeleri Kontrol Et"),
            content=self.config_manager.get_ui_text("check_updates_desc", "Uygulama açılışında yeni sürüm kontrolü yap"),
            parent=self.general_group
        )
        self.check_updates_card.switchButton.setChecked(self.config_manager.app_settings.check_for_updates)
        self.check_updates_card.switchButton.checkedChanged.connect(self._on_check_updates_changed)
        self.general_group.addSettingCard(self.check_updates_card)
        
        # Manual Check for updates button
        self.check_now_card = PushSettingCard(
            text=self.config_manager.get_ui_text("check_updates_now_button", "Kontrol Et"),
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("check_updates_now_label", "Şimdi Kontrol Et"),
            content=self.config_manager.get_ui_text("check_updates_now_tooltip", "Güncellemeleri şimdi manuel olarak tara"),
            parent=self.general_group
        )
        self.check_now_card.clicked.connect(self._check_updates_now)
        self.general_group.addSettingCard(self.check_now_card)
        
        # Output Format setting removed - defaulting to 'old_new' always
        
        self.expand_layout.addWidget(self.general_group)

    def _on_ai_retry_changed(self, value: int):
        self.config_manager.translation_settings.ai_retry_count = value
        self.config_manager.save_config()

    def _on_ai_delay_changed(self, value: float):
        self.config_manager.translation_settings.ai_request_delay = value
        self.config_manager.save_config()

    def _on_ai_concurrency_changed(self, value: int):
        self.config_manager.translation_settings.ai_concurrency = value
        self.config_manager.save_config()

    def _on_openai_model_changed(self, text: str):
        self.config_manager.translation_settings.openai_model = text
        self.config_manager.save_config()

    def _on_openai_url_changed(self, text: str):
        self.config_manager.translation_settings.openai_base_url = text
        self.config_manager.save_config()

    def _on_gemini_model_changed(self, text: str):
        self.config_manager.translation_settings.gemini_model = text
        self.config_manager.save_config()
    
    def _on_gemini_safety_changed(self, text: str):
        self.config_manager.translation_settings.gemini_safety_settings = text
        self.config_manager.save_config()

    def _create_translation_group(self):
        """Create translation settings group."""
        self.translation_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_translation", "Çeviri Ayarları"),
            self.scroll_widget
        )
        
        # Batch size
        self.batch_size_card = SettingCard(
            icon=FIF.TILES,
            title=self.config_manager.get_ui_text("batch_size", "Batch Boyutu"),
            content=self.config_manager.get_ui_text("batch_size_desc", "Aynı anda çevrilecek metin sayısı"),
            parent=self.translation_group
        )
        self.batch_size_spin = SpinBox(self.batch_size_card)
        self.batch_size_spin.setRange(1, 1000)
        self.batch_size_spin.setFixedWidth(100)
        
        self.batch_size_card.hBoxLayout.addWidget(self.batch_size_spin, 0, Qt.AlignmentFlag.AlignRight)
        self.batch_size_card.hBoxLayout.addSpacing(16)
        
        self.batch_size_spin.setValue(self.config_manager.translation_settings.max_batch_size)
        self.batch_size_spin.valueChanged.connect(self._on_batch_size_changed)
        self.translation_group.addSettingCard(self.batch_size_card)
        
        # Max concurrent requests
        self.concurrent_card = SettingCard(
            icon=FIF.SPEED_HIGH,
            title=self.config_manager.get_ui_text("max_concurrent", "Eşzamanlı İstek"),
            content=self.config_manager.get_ui_text("max_concurrent_desc", "Aynı anda yapılacak maksimum istek sayısı"),
            parent=self.translation_group
        )
        self.concurrent_spin = SpinBox(self.concurrent_card)
        self.concurrent_spin.setRange(1, 256)
        self.concurrent_spin.setFixedWidth(100)
        
        self.concurrent_card.hBoxLayout.addWidget(self.concurrent_spin, 0, Qt.AlignmentFlag.AlignRight)
        self.concurrent_card.hBoxLayout.addSpacing(16)
        
        self.concurrent_spin.setValue(self.config_manager.translation_settings.max_concurrent_threads)
        self.concurrent_spin.valueChanged.connect(self._on_concurrent_changed)
        self.translation_group.addSettingCard(self.concurrent_card)
        
        # Retry count
        self.retry_card = SettingCard(
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("retry_count", "Yeniden Deneme"),
            content=self.config_manager.get_ui_text("retry_count_desc", "Hata durumunda yeniden deneme sayısı"),
            parent=self.translation_group
        )
        self.retry_spin = SpinBox(self.retry_card)
        self.retry_spin.setRange(1, 20)
        self.retry_spin.setFixedWidth(100)
        
        self.retry_card.hBoxLayout.addWidget(self.retry_spin, 0, Qt.AlignmentFlag.AlignRight)
        self.retry_card.hBoxLayout.addSpacing(16)
        
        self.retry_spin.setValue(self.config_manager.translation_settings.max_retries)
        self.retry_spin.valueChanged.connect(self._on_retry_changed)
        self.translation_group.addSettingCard(self.retry_card)
        
        # Aggressive Translation Retry
        self.aggressive_retry_card = SwitchSettingCard(
            icon=FIF.CALORIES,
            title=self.config_manager.get_ui_text("aggressive_retry", "Agresif Çeviri"),
            content=self.config_manager.get_ui_text("aggressive_retry_desc", "Çevrilmemiş metinleri alternatif yöntemlerle tekrar dene (yavaş ama daha kapsamlı)"),
            configItem=None,
            parent=self.translation_group
        )
        self.aggressive_retry_card.setChecked(self.config_manager.translation_settings.aggressive_retry_translation)
        self.aggressive_retry_card.checkedChanged.connect(self._on_aggressive_retry_changed)
        self.translation_group.addSettingCard(self.aggressive_retry_card)
        
        # Force Runtime Translation
        self.force_runtime_card = SwitchSettingCard(
            icon=FIF.TAG,
            title=self.config_manager.get_ui_text("force_runtime", "Zorla Çeviri (Force Translate)"),
            content=self.config_manager.get_ui_text("force_runtime_desc", "Oyun içi metinleri çalışma anında zorla çevir (eksik !t bayrakları için)"),
            configItem=None,
            parent=self.translation_group
        )
        self.force_runtime_card.setChecked(getattr(self.config_manager.translation_settings, 'force_runtime_translation', False))
        self.force_runtime_card.checkedChanged.connect(self._on_force_runtime_translation_changed)
        self.translation_group.addSettingCard(self.force_runtime_card)
        
        # Glossary editor
        self.glossary_card = PushSettingCard(
            text=self.config_manager.get_ui_text("edit", "Düzenle"),
            icon=FIF.BOOK_SHELF,
            title=self.config_manager.get_ui_text("glossary", "Sözlük"),
            content=self.config_manager.get_ui_text("glossary_desc", "Özel çeviri terimleri tanımla"),
            parent=self.translation_group
        )
        self.glossary_card.clicked.connect(self._open_glossary_editor)
        self.translation_group.addSettingCard(self.glossary_card)
        
        self.expand_layout.addWidget(self.translation_group)

    def _create_api_keys_group(self):
        """Create API keys settings group."""
        self.api_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_api", "API Anahtarları"),
            self.scroll_widget
        )
        
        # Google API Key (though usually not needed for web version, some apps use it)
        self.google_api_card = SettingCard(
            icon=FIF.GLOBE,
            title=self.config_manager.get_ui_text("google_api_title", "Google Translate API Key"),
            content=self.config_manager.get_ui_text("google_api_desc", "Free web version doesn't require API key"),
            parent=self.api_group
        )
        self.google_key_input = PasswordLineEdit(self.google_api_card)
        self.google_key_input.setFixedWidth(300)
        self.google_key_input.setText(self.config_manager.api_keys.google_api_key)
        self.google_key_input.textChanged.connect(lambda v: self._on_api_key_changed("google", v))
        self.google_api_card.hBoxLayout.addWidget(self.google_key_input, 0, Qt.AlignmentFlag.AlignRight)
        self.google_api_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.google_api_card)
        
        # DeepL API Key
        self.deepl_api_card = SettingCard(
            icon=FIF.DICTIONARY,
            title=self.config_manager.get_ui_text("deepl_api_title", "DeepL API Key"),
            content=self.config_manager.get_ui_text("deepl_api_desc", "API key required for high quality translations"),
            parent=self.api_group
        )
        self.deepl_key_input = PasswordLineEdit(self.deepl_api_card)
        self.deepl_key_input.setFixedWidth(300)
        self.deepl_key_input.setText(self.config_manager.api_keys.deepl_api_key)
        self.deepl_key_input.textChanged.connect(lambda v: self._on_api_key_changed("deepl", v))
        self.deepl_api_card.hBoxLayout.addWidget(self.deepl_key_input, 0, Qt.AlignmentFlag.AlignRight)
        self.deepl_api_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.deepl_api_card)
        
        # DeepL Formality (Sen/Siz seçimi)
        self.deepl_formality_card = SettingCard(
            icon=FIF.PEOPLE,
            title=self.config_manager.get_ui_text("deepl_formality_title", "DeepL Hitap Şekli"),
            content=self.config_manager.get_ui_text("deepl_formality_desc", "Resmi (Siz) veya samimi (Sen) hitap şekli"),
            parent=self.api_group
        )
        self.deepl_formality_combo = ComboBox(self.deepl_formality_card)
        # Formality options: default, formal, informal
        formality_options = [
            ("default", self.config_manager.get_ui_text("formality_default", "Varsayılan (Otomatik)")),
            ("formal", self.config_manager.get_ui_text("formality_formal", "Resmi (Siz/Sie/Vous...)")),
            ("informal", self.config_manager.get_ui_text("formality_informal", "Samimi (Sen/Du/Tu...)"))
        ]
        self.FORMALITY_OPTIONS = [opt[0] for opt in formality_options]
        for key, label in formality_options:
            self.deepl_formality_combo.addItem(label)
        
        # Set current formality
        current_formality = getattr(self.config_manager.translation_settings, 'deepl_formality', 'default')
        try:
            idx = self.FORMALITY_OPTIONS.index(current_formality)
            self.deepl_formality_combo.setCurrentIndex(idx)
        except ValueError:
            self.deepl_formality_combo.setCurrentIndex(0)
        
        self.deepl_formality_combo.setFixedWidth(200)
        self.deepl_formality_combo.currentIndexChanged.connect(self._on_deepl_formality_changed)
        self.deepl_formality_card.hBoxLayout.addWidget(self.deepl_formality_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.deepl_formality_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.deepl_formality_card)
        
        self.expand_layout.addWidget(self.api_group)

    def _create_ai_group(self):
        """Create AI settings group."""
        self.ai_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_ai_title", "Yapay Zeka (AI) Ayarları"),
            self.scroll_widget
        )
        
        # AI Warning Area
        from qfluentwidgets import CaptionLabel
        from PyQt6.QtGui import QColor
        
        msg1 = self.config_manager.get_ui_text("ai_hallucination_warning", "⚠️ DİKKAT: Küçük modeller halüsinasyon görebilir.")
        msg2 = self.config_manager.get_ui_text("ai_vram_warning", "⚠️ DİKKAT: 4GB VRAM sınırına dikkat edin.")
        msg3 = self.config_manager.get_ui_text("ai_source_lang_warning", "💡 İPUCU: Kaynak dili belirtmek kaliteyi artırır.")
        
        self.ai_warn1 = CaptionLabel(msg1)
        self.ai_warn2 = CaptionLabel(msg2)
        self.ai_warn3 = CaptionLabel(msg3)
        
        # Reddish color for warnings
        self.ai_warn1.setTextColor(QColor(231, 76, 60), QColor(231, 76, 60))
        self.ai_warn2.setTextColor(QColor(231, 76, 60), QColor(231, 76, 60))
        self.ai_warn3.setTextColor(QColor(52, 152, 219), QColor(52, 152, 219)) # Blue for tip
        
        self.ai_group.vBoxLayout.addWidget(self.ai_warn1)
        self.ai_group.vBoxLayout.addWidget(self.ai_warn2)
        self.ai_group.vBoxLayout.addWidget(self.ai_warn3)
        self.ai_group.vBoxLayout.addSpacing(10)

        # OpenAI / OpenRouter Settings
        self.openai_subset = SettingCard(
            icon=FIF.ROBOT,
            title=self.config_manager.get_ui_text("settings_openai_title", "OpenAI / OpenRouter"),
            content=self.config_manager.get_ui_text("settings_openai_desc", "ChatGPT, OpenRouter settings"),
            parent=self.ai_group
        )
        
        # Model Name
        self.openai_model = LineEdit(self.openai_subset)
        self.openai_model.setPlaceholderText(self.config_manager.get_ui_text("placeholder_openai_model", "Model (örn: gpt-3.5-turbo)"))
        self.openai_model.setText(self.config_manager.translation_settings.openai_model)
        self.openai_model.setFixedWidth(200)
        self.openai_model.textChanged.connect(self._on_openai_model_changed)
        
        # Base URL
        self.openai_url = LineEdit(self.openai_subset)
        self.openai_url.setPlaceholderText(self.config_manager.get_ui_text("placeholder_openai_base_url", "Base URL (Opsiyonel)"))
        self.openai_url.setText(self.config_manager.translation_settings.openai_base_url)
        self.openai_url.setToolTip(self.config_manager.get_ui_text("tooltip_openai_base_url", "OpenRouter için: https://openrouter.ai/api/v1\nLocal için: http://localhost:11434/v1"))
        self.openai_url.setFixedWidth(250)
        self.openai_url.textChanged.connect(self._on_openai_url_changed)

        # API Key
        self.openai_key = PasswordLineEdit(self.openai_subset)
        self.openai_key.setPlaceholderText(self.config_manager.get_ui_text("placeholder_openai_key", "API Key (sk-...)"))
        self.openai_key.setText(self.config_manager.api_keys.openai_api_key)
        self.openai_key.setFixedWidth(200)
        self.openai_key.textChanged.connect(lambda v: self._on_api_key_changed("openai", v))

        # Layout for OpenAI
        layout = self.openai_subset.hBoxLayout
        layout.addWidget(self.openai_model, 0, Qt.AlignmentFlag.AlignRight)
        layout.addSpacing(10)
        layout.addWidget(self.openai_url, 0, Qt.AlignmentFlag.AlignRight)
        layout.addSpacing(10)
        layout.addWidget(self.openai_key, 0, Qt.AlignmentFlag.AlignRight)
        layout.addSpacing(10)
        
        self.ai_group.addSettingCard(self.openai_subset)

        # Gemini Settings
        self.gemini_subset = SettingCard(
            icon=FIF.CALENDAR,  # Using Calendar icon as generic 'Gemini' look-alike pending better icon
            title=self.config_manager.get_ui_text("settings_gemini_title", "Google Gemini"),
            content=self.config_manager.get_ui_text("settings_gemini_desc", "Gemini Pro/Flash API ayarları"),
            parent=self.ai_group
        )

        # Model Name
        self.gemini_model = LineEdit(self.gemini_subset)
        self.gemini_model.setPlaceholderText(self.config_manager.get_ui_text("placeholder_gemini_model", "Model (örn: gemini-pro)"))
        self.gemini_model.setText(self.config_manager.translation_settings.gemini_model)
        self.gemini_model.setFixedWidth(150)
        self.gemini_model.textChanged.connect(self._on_gemini_model_changed)

        # Safety Settings
        self.gemini_safety = ComboBox(self.gemini_subset)
        self.gemini_safety.addItems(["BLOCK_NONE", "BLOCK_ONLY_HIGH", "STANDARD"])
        self.gemini_safety.setCurrentText(self.config_manager.translation_settings.gemini_safety_settings)
        self.gemini_safety.setFixedWidth(160)
        self.gemini_safety.setToolTip(self.config_manager.get_ui_text("tooltip_gemini_safety", "NSFW içerikler için BLOCK_NONE önerilir"))
        self.gemini_safety.currentTextChanged.connect(self._on_gemini_safety_changed)

        # API Key
        self.gemini_key = PasswordLineEdit(self.gemini_subset)
        self.gemini_key.setPlaceholderText(self.config_manager.get_ui_text("placeholder_gemini_key", "Gemini API Key"))
        self.gemini_key.setText(self.config_manager.api_keys.gemini_api_key)
        self.gemini_key.setFixedWidth(200)
        self.gemini_key.textChanged.connect(lambda v: self._on_api_key_changed("gemini", v))

        # Layout for Gemini
        glayout = self.gemini_subset.hBoxLayout
        glayout.addWidget(self.gemini_model, 0, Qt.AlignmentFlag.AlignRight)
        glayout.addSpacing(10)
        glayout.addWidget(self.gemini_safety, 0, Qt.AlignmentFlag.AlignRight)
        glayout.addSpacing(10)
        glayout.addWidget(self.gemini_key, 0, Qt.AlignmentFlag.AlignRight)
        glayout.addSpacing(10)
        
        self.ai_group.addSettingCard(self.gemini_subset)

        # Local LLM Settings
        self.local_llm_subset = SettingCard(
            icon=FIF.HOME,
            title=self.config_manager.get_ui_text("settings_local_llm_title", "Yerel LLM (Ollama/LM Studio...)"),
            content=self.config_manager.get_ui_text("settings_local_llm_desc", "Yerel yapay zeka sunucusu ayarları"),
            parent=self.ai_group
        )

        # Model Name - LineEdit for custom model input
        self.local_llm_model = LineEdit(self.local_llm_subset)
        self.local_llm_model.setPlaceholderText(self.config_manager.get_ui_text("placeholder_local_llm_model", "Model (örn: llama3.2)"))
        self.local_llm_model.setText(self.config_manager.translation_settings.local_llm_model)
        self.local_llm_model.setFixedWidth(150)
        self.local_llm_model.textChanged.connect(self._on_local_llm_model_changed)
        
        # Model presets dropdown - Uncensored models for VN translation
        self.local_llm_presets = ComboBox(self.local_llm_subset)
        
        # Category headers from locales
        cat_uncensored = self.config_manager.get_ui_text("llm_cat_uncensored", "── 🔓 Uncensored (Ollama) ──")
        cat_lmstudio = self.config_manager.get_ui_text("llm_cat_lmstudio", "── 📦 LM Studio (GGUF) ──")
        cat_standard = self.config_manager.get_ui_text("llm_cat_standard", "── 🦙 Standard (Ollama) ──")
        cat_desktop = self.config_manager.get_ui_text("llm_cat_desktop", "── 🖥️ Desktop Apps ──")
        preset_janai = self.config_manager.get_ui_text("llm_janai_preset", "Jan.ai (Local)")
        preset_lmstudio = self.config_manager.get_ui_text("llm_lmstudio_preset", "LM Studio (Local)")
        preset_gpt4all = self.config_manager.get_ui_text("llm_gpt4all_preset", "GPT4All (Local)")
        preset_koboldcpp = self.config_manager.get_ui_text("llm_koboldcpp_preset", "KoboldCPP (Local)")
        preset_ollama = self.config_manager.get_ui_text("llm_ollama_preset", "Ollama (Local)")
        
        local_presets = [
            cat_desktop,
            preset_ollama,
            preset_janai,
            preset_lmstudio,
            preset_gpt4all,
            preset_koboldcpp,
            cat_uncensored,
            "dolphin-mistral",
            "dolphin-llama3",
            "dolphin-mixtral",
            "wizard-vicuna-uncensored",
            "llama2-uncensored",
            "nous-hermes2",
            "openhermes",
            "neural-chat",
            cat_lmstudio,
            "dolphin-2.6-mistral-7b",
            "mistral-7b-instruct-v0.2",
            "llama-2-13b-chat",
            "neural-chat-7b-v3-1",
            cat_standard,
            "llama3.2",
            "llama3.1", 
            "mistral",
            "gemma2",
            "qwen2.5",
            "phi3",
        ]
        for model in local_presets:
            self.local_llm_presets.addItem(model)
        self.local_llm_presets.setFixedWidth(200)
        self.local_llm_presets.setToolTip(self.config_manager.get_ui_text("tooltip_uncensored_models", "NSFW VN çevirisi için sansürsüz modeller önerilir"))
        self.local_llm_presets.currentTextChanged.connect(self._on_local_llm_preset_selected)

        # Base URL
        self.local_llm_url = LineEdit(self.local_llm_subset)
        self.local_llm_url.setPlaceholderText(self.config_manager.get_ui_text("placeholder_local_llm_url", "URL (örn: http://localhost:11434/v1)"))
        self.local_llm_url.setText(self.config_manager.translation_settings.local_llm_url)
        self.local_llm_url.setFixedWidth(220)
        self.local_llm_url.textChanged.connect(self._on_local_llm_url_changed)

        # Layout for Local LLM
        llayout = self.local_llm_subset.hBoxLayout
        llayout.addWidget(self.local_llm_model, 0, Qt.AlignmentFlag.AlignRight)
        llayout.addWidget(self.local_llm_presets, 0, Qt.AlignmentFlag.AlignRight)
        llayout.addSpacing(5)
        llayout.addWidget(self.local_llm_url, 0, Qt.AlignmentFlag.AlignRight)
        llayout.addSpacing(10)
        
        self.ai_group.addSettingCard(self.local_llm_subset)
        
        # Local LLM Advanced Settings Card
        self.local_llm_advanced_card = SettingCard(
            icon=FIF.CONNECT,
            title=self.config_manager.get_ui_text("settings_local_llm_advanced", "Yerel LLM Gelişmiş Ayarları"),
            content=self.config_manager.get_ui_text("settings_local_llm_advanced_desc", "Bağlantı testi ve zaman aşımı ayarları"),
            parent=self.ai_group
        )
        
        # Timeout SpinBox
        timeout_label = BodyLabel(self.config_manager.get_ui_text("local_llm_timeout_label", "Zaman Aşımı (sn):"), self.local_llm_advanced_card)
        self.local_llm_timeout_spin = SpinBox(self.local_llm_advanced_card)
        self.local_llm_timeout_spin.setRange(30, 600)
        self.local_llm_timeout_spin.setValue(getattr(self.config_manager.translation_settings, 'local_llm_timeout', 300))
        self.local_llm_timeout_spin.setMinimumWidth(80)
        self.local_llm_timeout_spin.setToolTip(self.config_manager.get_ui_text("local_llm_timeout_tooltip", "Yerel LLM için bekleme süresi (30-600 saniye)"))
        self.local_llm_timeout_spin.valueChanged.connect(self._on_local_llm_timeout_changed)
        
        # Connection Status Label
        self.local_llm_status_label = BodyLabel("", self.local_llm_advanced_card)
        self.local_llm_status_label.setMinimumWidth(150)
        
        # Health Check Button
        from qfluentwidgets import PrimaryPushButton
        self.local_llm_test_btn = PrimaryPushButton(
            self.config_manager.get_ui_text("test_local_llm_connection", "🩺 Bağlantıyı Test Et"),
            self.local_llm_advanced_card
        )
        self.local_llm_test_btn.clicked.connect(self._test_local_llm_connection)
        
        # Layout
        adv_layout = self.local_llm_advanced_card.hBoxLayout
        adv_layout.addWidget(timeout_label, 0, Qt.AlignmentFlag.AlignRight)
        adv_layout.addWidget(self.local_llm_timeout_spin, 0, Qt.AlignmentFlag.AlignRight)
        adv_layout.addSpacing(15)
        adv_layout.addWidget(self.local_llm_status_label, 0, Qt.AlignmentFlag.AlignRight)
        adv_layout.addWidget(self.local_llm_test_btn, 0, Qt.AlignmentFlag.AlignRight)
        adv_layout.addSpacing(10)
        
        self.ai_group.addSettingCard(self.local_llm_advanced_card)

        # 1. AI Model Parameters Card
        self.ai_model_params_card = SettingCard(
            icon=FIF.DEVELOPER_TOOLS,
            title=self.config_manager.get_ui_text("settings_ai_model_params", "AI Model Parametreleri"),
            content=self.config_manager.get_ui_text("settings_ai_model_params_desc", "Sıcaklık (Temperature) ve Maksimum Token ayarları"),
            parent=self.ai_group
        )
        
        # Temperature
        self.ai_temperature = SpinBox(self.ai_model_params_card)
        self.ai_temperature.setRange(0, 10)
        self.ai_temperature.setValue(int(self.config_manager.translation_settings.ai_temperature * 10))
        self.ai_temperature.setMinimumWidth(80)
        self.ai_temperature.valueChanged.connect(self._on_ai_temperature_changed)

        # Max Tokens
        self.ai_max_tokens = SpinBox(self.ai_model_params_card)
        self.ai_max_tokens.setRange(256, 8192)
        self.ai_max_tokens.setValue(self.config_manager.translation_settings.ai_max_tokens)
        self.ai_max_tokens.setMinimumWidth(100)
        self.ai_max_tokens.valueChanged.connect(self._on_ai_max_tokens_changed)

        # Batch Size
        self.ai_batch_size = SpinBox(self.ai_model_params_card)
        self.ai_batch_size.setRange(1, 200)
        self.ai_batch_size.setValue(getattr(self.config_manager.translation_settings, 'ai_batch_size', 50))
        self.ai_batch_size.setMinimumWidth(80)
        self.ai_batch_size.setToolTip(self.config_manager.get_ui_text("tooltip_ai_batch_size", "Tek seferde yapay zekaya gönderilecek satır sayısı (Varsayılan: 50)"))
        self.ai_batch_size.valueChanged.connect(self._on_ai_batch_size_changed)

        temp_label = BodyLabel(self.config_manager.get_ui_text("ai_temp_short", "Sıcaklık:"), self.ai_model_params_card)
        tokens_label = BodyLabel(self.config_manager.get_ui_text("ai_tokens_short", "Token:"), self.ai_model_params_card)
        batch_label = BodyLabel(self.config_manager.get_ui_text("ai_batch_short", "Paket:"), self.ai_model_params_card)

        mp_layout = self.ai_model_params_card.hBoxLayout
        mp_layout.addWidget(temp_label, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addWidget(self.ai_temperature, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addSpacing(15)
        mp_layout.addWidget(tokens_label, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addWidget(self.ai_max_tokens, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addSpacing(15)
        mp_layout.addWidget(batch_label, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addWidget(self.ai_batch_size, 0, Qt.AlignmentFlag.AlignRight)
        mp_layout.addSpacing(10)
        self.ai_group.addSettingCard(self.ai_model_params_card)

        # 2. AI Connection Settings Card
        self.ai_connection_card = SettingCard(
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("settings_ai_connection", "AI Bağlantı Ayarları"),
            content=self.config_manager.get_ui_text("settings_ai_connection_desc", "Zaman aşımı ve yeniden deneme sayısı"),
            parent=self.ai_group
        )

        # Timeout
        self.ai_timeout = SpinBox(self.ai_connection_card)
        self.ai_timeout.setRange(10, 300)
        self.ai_timeout.setValue(self.config_manager.translation_settings.ai_timeout)
        self.ai_timeout.setMinimumWidth(80)
        self.ai_timeout.valueChanged.connect(self._on_ai_timeout_changed)

        # Retry Count
        self.ai_retry = SpinBox(self.ai_connection_card)
        self.ai_retry.setRange(1, 10)
        self.ai_retry.setValue(self.config_manager.translation_settings.ai_retry_count)
        self.ai_retry.setMinimumWidth(80)
        self.ai_retry.valueChanged.connect(self._on_ai_retry_changed)

        timeout_label = BodyLabel(self.config_manager.get_ui_text("ai_timeout_short", "Süre (sn):"), self.ai_connection_card)
        retry_label = BodyLabel(self.config_manager.get_ui_text("ai_retry_short", "Tekrar:"), self.ai_connection_card)

        conn_layout = self.ai_connection_card.hBoxLayout
        conn_layout.addWidget(timeout_label, 0, Qt.AlignmentFlag.AlignRight)
        conn_layout.addWidget(self.ai_timeout, 0, Qt.AlignmentFlag.AlignRight)
        conn_layout.addSpacing(20)
        conn_layout.addWidget(retry_label, 0, Qt.AlignmentFlag.AlignRight)
        conn_layout.addWidget(self.ai_retry, 0, Qt.AlignmentFlag.AlignRight)
        conn_layout.addSpacing(10)
        self.ai_group.addSettingCard(self.ai_connection_card)

        # 3. AI Rate Limits & Performance Card
        self.ai_speed_card = SettingCard(
            icon=FIF.SPEED_HIGH,
            title=self.config_manager.get_ui_text("settings_ai_speed", "AI Hız Sınırları ve Performans"),
            content=self.config_manager.get_ui_text("settings_ai_speed_desc", "Eşzamanlılık ve istekler arası gecikme"),
            parent=self.ai_group
        )

        # Concurrency
        self.ai_concurrency = SpinBox(self.ai_speed_card)
        self.ai_concurrency.setRange(1, 32)
        self.ai_concurrency.setValue(self.config_manager.translation_settings.ai_concurrency)
        self.ai_concurrency.setMinimumWidth(80)
        self.ai_concurrency.valueChanged.connect(self._on_ai_concurrency_changed)

        # Delay
        self.ai_delay = DoubleSpinBox(self.ai_speed_card)
        self.ai_delay.setRange(0.0, 30.0)
        self.ai_delay.setSingleStep(0.5)
        self.ai_delay.setValue(self.config_manager.translation_settings.ai_request_delay)
        self.ai_delay.setMinimumWidth(90)
        self.ai_delay.valueChanged.connect(self._on_ai_delay_changed)

        concurrency_label = BodyLabel(self.config_manager.get_ui_text("ai_concurrency_short", "Parallel:"), self.ai_speed_card)
        delay_label = BodyLabel(self.config_manager.get_ui_text("ai_delay_short", "Gecikme (sn):"), self.ai_speed_card)

        speed_layout = self.ai_speed_card.hBoxLayout
        speed_layout.addWidget(concurrency_label, 0, Qt.AlignmentFlag.AlignRight)
        speed_layout.addWidget(self.ai_concurrency, 0, Qt.AlignmentFlag.AlignRight)
        speed_layout.addSpacing(20)
        speed_layout.addWidget(delay_label, 0, Qt.AlignmentFlag.AlignRight)
        speed_layout.addWidget(self.ai_delay, 0, Qt.AlignmentFlag.AlignRight)
        speed_layout.addSpacing(10)
        self.ai_group.addSettingCard(self.ai_speed_card)

        # Custom System Prompt Card
        self.ai_prompt_subset = SettingCard(
            icon=FIF.EDIT,
            title=self.config_manager.get_ui_text("settings_ai_prompt_title", "Özel Sistem Prompt"),
            content=self.config_manager.get_ui_text("settings_ai_prompt_desc", "Boş = varsayılan prompt. {source_lang} ve {target_lang} değişkenleri kullanılabilir."),
            parent=self.ai_group
        )
        self.ai_system_prompt = LineEdit(self.ai_prompt_subset)
        self.ai_system_prompt.setPlaceholderText(self.config_manager.get_ui_text("placeholder_ai_prompt", "You are a translator. Translate from {source_lang} to {target_lang}..."))
        self.ai_system_prompt.setText(self.config_manager.translation_settings.ai_custom_system_prompt or "")
        self.ai_system_prompt.setMinimumWidth(500)
        self.ai_system_prompt.setToolTip(self.config_manager.get_ui_text("tooltip_ai_prompt", "AI'a verilen yönerge. Boş bırakırsanız dahili VN çeviri promptu kullanılır."))
        self.ai_system_prompt.textChanged.connect(self._on_ai_system_prompt_changed)

        prompt_layout = self.ai_prompt_subset.hBoxLayout
        prompt_layout.addWidget(self.ai_system_prompt, 1, Qt.AlignmentFlag.AlignRight)
        prompt_layout.addSpacing(10)

        self.ai_group.addSettingCard(self.ai_prompt_subset)
        
        self.expand_layout.addWidget(self.ai_group)

    def _create_proxy_group(self):
        """Create proxy settings group."""
        self.proxy_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_proxy", "Proxy Ayarları"),
            self.scroll_widget
        )
        
        # Enable proxy
        self.proxy_enabled_card = SwitchSettingCard(
            icon=FIF.VPN,
            title=self.config_manager.get_ui_text("proxy_enabled", "Proxy Kullan"),
            content=self.config_manager.get_ui_text("proxy_enabled_desc", "Çeviri isteklerinde proxy kullan"),
            configItem=None,
            parent=self.proxy_group
        )
        self.proxy_enabled_card.switchButton.setChecked(self.config_manager.proxy_settings.enabled)
        self.proxy_enabled_card.switchButton.checkedChanged.connect(self._on_proxy_enabled_changed)
        self.proxy_group.addSettingCard(self.proxy_enabled_card)
        
        # Refresh proxies button
        self.refresh_proxy_card = PushSettingCard(
            text=self.config_manager.get_ui_text("refresh", "Yenile"),
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("refresh_proxies", "Proxy Listesini Yenile"),
            content=self.config_manager.get_ui_text("refresh_proxies_desc", "Ücretsiz proxy listesini güncelle"),
            parent=self.proxy_group
        )
        self.refresh_proxy_card.clicked.connect(self._refresh_proxies)
        self.proxy_group.addSettingCard(self.refresh_proxy_card)
        
        # Manual proxies
        self.manual_proxy_card = PushSettingCard(
            text=self.config_manager.get_ui_text("edit", "Düzenle"),
            icon=FIF.EDIT,
            title=self.config_manager.get_ui_text("manual_proxies", "Manuel Proxyler"),
            content=self.config_manager.get_ui_text("manual_proxies_desc", "Kendi proxylerinizi buraya ekle"),
            parent=self.proxy_group
        )
        self.manual_proxy_card.clicked.connect(self._open_custom_proxy_dialog)
        self.proxy_group.addSettingCard(self.manual_proxy_card)
        
        self.expand_layout.addWidget(self.proxy_group)

    def _create_advanced_group(self):
        """Create advanced settings group."""
        self.advanced_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_advanced", "Gelişmiş"),
            self.scroll_widget
        )
        
        # Auto Archive Extraction (Legacy name unren, now unrpa/rpa_parser)
        self.auto_unren_card = SwitchSettingCard(
            icon=FIF.ZIP_FOLDER, # More appropriate for archives
            title=self.config_manager.get_ui_text("auto_unren", "Otomatik Arşiv Açma"),
            content=self.config_manager.get_ui_text("auto_unren_desc", "RPA dosyalarını otomatik olarak ayıkla"),
            configItem=None,
            parent=self.advanced_group
        )
        self.auto_unren_card.switchButton.setChecked(self.config_manager.app_settings.unren_auto_download)
        self.auto_unren_card.switchButton.checkedChanged.connect(self._on_auto_unren_changed)
        self.advanced_group.addSettingCard(self.auto_unren_card)
        
        # Deep scan
        self.deep_scan_card = SwitchSettingCard(
            icon=FIF.SEARCH,
            title=self.config_manager.get_ui_text("deep_scan", "Derin Tarama"),
            content=self.config_manager.get_ui_text("deep_scan_desc", "RPYC dosyalarını AST ile analiz et (yavaş)"),
            configItem=None,
            parent=self.advanced_group
        )
        self.deep_scan_card.switchButton.setChecked(
            self.config_manager.translation_settings.enable_deep_scan
        )
        self.deep_scan_card.switchButton.checkedChanged.connect(self._on_deep_scan_changed)
        self.advanced_group.addSettingCard(self.deep_scan_card)
        
        # Show Debug Engines
        self.debug_engines_card = SwitchSettingCard(
            icon=FIF.DEVELOPER_TOOLS,
            title=self.config_manager.get_ui_text("show_debug_engines", "Hata Ayıklama Motorlarını Göster"),
            content=self.config_manager.get_ui_text("show_debug_engines_desc", "Pseudo-Localization gibi geliştirici araçlarını ana listede göster"),
            configItem=None,
            parent=self.advanced_group
        )
        self.debug_engines_card.switchButton.setChecked(
            getattr(self.config_manager.translation_settings, 'show_debug_engines', False)
        )
        self.debug_engines_card.switchButton.checkedChanged.connect(self._on_debug_engines_changed)
        self.advanced_group.addSettingCard(self.debug_engines_card)
        
        # Restore defaults
        self.restore_defaults_card = PrimaryPushSettingCard(
            text=self.config_manager.get_ui_text("restore_defaults", "Varsayılanlara Dön"),
            icon=FIF.HISTORY,
            title=self.config_manager.get_ui_text("restore_defaults_title", "Ayarları Sıfırla"),
            content=self.config_manager.get_ui_text("restore_defaults_desc", "Tüm ayarları varsayılan değerlere döndür"),
            parent=self.advanced_group
        )
        self.restore_defaults_card.clicked.connect(self._restore_defaults)
        self.advanced_group.addSettingCard(self.restore_defaults_card)
        
        self.expand_layout.addWidget(self.advanced_group)

    # ==================== Event Handlers ====================

    def _on_language_changed(self, index: int):
        """Handle language change."""
        if not hasattr(self, 'LANG_CODES') or index >= len(self.LANG_CODES):
            return
            
        new_lang = self.LANG_CODES[index]
        old_lang = self.config_manager.app_settings.ui_language
        
        # Skip if no actual change
        if new_lang == old_lang:
            return
            
        self.config_manager.app_settings.ui_language = new_lang
        self.config_manager.save_config()
        
        # Emit signal
        self.language_changed.emit()
        
        # Show restart dialog with option to restart now
        if self.parent_window:
            from qfluentwidgets import MessageBox
            dialog = MessageBox(
                self.config_manager.get_ui_text("language_changed", "Dil Değiştirildi"),
                self.config_manager.get_ui_text("language_restart_message", 
                    "Yeni dil seçimi uygulandı. Değişikliklerin etkinleşmesi için uygulamayı yeniden başlatmanız gerekiyor.\n\nŞimdi yeniden başlatmak ister misiniz?"),
                self.parent_window
            )
            dialog.yesButton.setText(self.config_manager.get_ui_text("btn_restart", "Yeniden Başlat"))
            dialog.cancelButton.setText(self.config_manager.get_ui_text("update_later", "Daha Sonra"))
            
            if dialog.exec():
                # Restart the application
                import sys
                import os
                os.execl(sys.executable, sys.executable, *sys.argv)


    def _on_theme_changed(self, index: int):
        """Handle theme change - applies immediately using index-based mapping."""
        # Get theme key from index using THEME_MAP
        if index < 0 or index >= len(self.THEME_MAP):
            new_theme = "dark"
        else:
            new_theme = self.THEME_MAP[index][0]
        
        print(f"[Theme] User selected index {index} -> theme: {new_theme}")  # Debug
        
        # Save to config
        self.config_manager.app_settings.app_theme = new_theme
        self.config_manager.save_config()
        
        # Apply theme immediately
        applied = False
        if self.parent_window and hasattr(self.parent_window, 'apply_theme'):
            print(f"[Theme] Applying via parent_window.apply_theme()")
            self.parent_window.apply_theme(new_theme)
            applied = True
        
        # Show info bar
        if self.parent_window and applied:
            self.parent_window.show_info_bar(
                "success",
                self.config_manager.get_ui_text("theme_changed", "Tema Güncellendi"),
                self.config_manager.get_ui_text("theme_applied", "Tema başarıyla uygulandı.")
            )

    def _on_update_check_changed(self, checked: bool):
        """Handle update check toggle."""
        self.config_manager.app_settings.check_for_updates = checked
        self.config_manager.save_config()


    def _on_api_key_changed(self, service: str, value: str):
        """Handle API key change."""
        self.config_manager.set_api_key(service, value)

    def _on_openai_model_changed(self, text: str):
        """Handle OpenAI model name changes."""
        self.config_manager.translation_settings.openai_model = text
        self.config_manager.save_config()

    def _on_openai_url_changed(self, text: str):
        """Handle OpenAI base URL changes."""
        self.config_manager.translation_settings.openai_base_url = text
        self.config_manager.save_config()

    def _on_gemini_model_changed(self, text: str):
        """Handle Gemini model name changes."""
        self.config_manager.translation_settings.gemini_model = text
        self.config_manager.save_config()

    def _on_gemini_safety_changed(self, text: str):
        """Handle Gemini safety level changes."""
        self.config_manager.translation_settings.gemini_safety_settings = text
        self.config_manager.save_config()

    def _on_local_llm_model_changed(self, text: str):
        """Handle Local LLM model name changes."""
        self.config_manager.translation_settings.local_llm_model = text
        self.config_manager.save_config()

    def _on_local_llm_preset_selected(self, text: str):
        """Handle Local LLM preset model selection."""
        if not text or text.startswith("──") or text.startswith("--"):
            return
            
        # Preset check
        ollama_text = self.config_manager.get_ui_text("llm_ollama_preset", "Ollama (Local)")
        janai_text = self.config_manager.get_ui_text("llm_janai_preset", "Jan.ai (Local)")
        lmstudio_text = self.config_manager.get_ui_text("llm_lmstudio_preset", "LM Studio (Local)")
        gpt4all_text = self.config_manager.get_ui_text("llm_gpt4all_preset", "GPT4All (Local)")
        koboldcpp_text = self.config_manager.get_ui_text("llm_koboldcpp_preset", "KoboldCPP (Local)")

        if text == ollama_text:
            self.local_llm_model.setText("llama3")  # Popüler varsayılan
            self.local_llm_url.setText("http://localhost:11434/v1")
        elif text == janai_text:
            self.local_llm_model.setText("local-model")
            self.local_llm_url.setText("http://localhost:1337/v1")
        elif text == lmstudio_text:
            self.local_llm_model.setText("local-model")
            self.local_llm_url.setText("http://localhost:1234/v1")
        elif text == gpt4all_text:
            self.local_llm_model.setText("local-model")
            self.local_llm_url.setText("http://localhost:4891/v1")
        elif text == koboldcpp_text:
            self.local_llm_model.setText("local-model")
            self.local_llm_url.setText("http://localhost:5001/v1")
        else:
            self.local_llm_model.setText(text)

    def _on_local_llm_url_changed(self, text: str):
        """Handle Local LLM base URL changes."""
        self.config_manager.translation_settings.local_llm_url = text
        self.config_manager.save_config()

    def _on_local_llm_timeout_changed(self, value: int):
        """Handle Local LLM timeout changes."""
        self.config_manager.translation_settings.local_llm_timeout = value
        self.config_manager.save_config()

    def _test_local_llm_connection(self):
        """Test connection to local LLM server."""
        import asyncio
        import threading
        
        self.local_llm_test_btn.setEnabled(False)
        self.local_llm_status_label.setText(self.config_manager.get_ui_text("testing_connection", "⏳ Test ediliyor..."))
        
        def run_health_check():
            try:
                from src.core.ai_translator import LocalLLMTranslator
                
                # Create temporary translator for health check
                translator = LocalLLMTranslator(
                    model=self.config_manager.translation_settings.local_llm_model or "llama3.2",
                    base_url=self.config_manager.translation_settings.local_llm_url or "http://localhost:11434/v1",
                    timeout=getattr(self.config_manager.translation_settings, 'local_llm_timeout', 300),
                    config_manager=self.config_manager
                )
                
                # Run health check
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success, message = loop.run_until_complete(translator.health_check())
                finally:
                    loop.run_until_complete(translator.close())
                    loop.close()
                
                # Update UI on main thread
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(
                    self, "_update_connection_status",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, success),
                    Q_ARG(str, message)
                )
            except Exception as e:
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(
                    self, "_update_connection_status",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, False),
                    Q_ARG(str, str(e))
                )
        
        # Run in background thread
        thread = threading.Thread(target=run_health_check, daemon=True)
        thread.start()

    @pyqtSlot(bool, str)
    def _update_connection_status(self, success: bool, message: str):
        """Update connection status label (called from main thread)."""
        self.local_llm_test_btn.setEnabled(True)
        
        if success:
            self.local_llm_status_label.setText(self.config_manager.get_ui_text("local_llm_connected", "✅ Bağlandı"))
            self.local_llm_status_label.setStyleSheet("color: #4CAF50;")  # Green
            
            # Show success info bar
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "success",
                    self.config_manager.get_ui_text("connection_success", "Bağlantı Başarılı"),
                    message
                )
        else:
            self.local_llm_status_label.setText(self.config_manager.get_ui_text("local_llm_disconnected", "❌ Bağlanamadı"))
            self.local_llm_status_label.setStyleSheet("color: #F44336;")  # Red
            
            # Show error info bar
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("connection_failed", "Bağlantı Başarısız"),
                    message
                )

    def _on_ai_temperature_changed(self, value: int):
        """Handle AI temperature changes."""
        self.config_manager.translation_settings.ai_temperature = value / 10.0
        self.config_manager.save_config()

    def _on_ai_timeout_changed(self, value: int):
        """Handle AI timeout changes."""
        self.config_manager.translation_settings.ai_timeout = value
        self.config_manager.save_config()

    def _on_ai_max_tokens_changed(self, value: int):
        """Handle AI max tokens changes."""
        self.config_manager.translation_settings.ai_max_tokens = value
        self.config_manager.save_config()

    def _on_ai_batch_size_changed(self, value: int):
        """Handle AI batch size changes."""
        self.config_manager.translation_settings.ai_batch_size = value
        self.config_manager.save_config()

    def _on_ai_retry_changed(self, value: int):
        """Handle AI retry count changes."""
        self.config_manager.translation_settings.ai_retry_count = value
        self.config_manager.save_config()

    def _on_ai_system_prompt_changed(self, text: str):
        """Handle AI custom system prompt changes."""
        self.config_manager.translation_settings.ai_custom_system_prompt = text
        self.config_manager.save_config()

    def _on_ai_concurrency_changed(self, value: int):
        """Handle AI concurrency changes."""
        self.config_manager.translation_settings.ai_concurrency = value
        self.config_manager.save_config()

    def _on_ai_delay_changed(self, value: float):
        """Handle AI delay changes."""
        self.config_manager.translation_settings.ai_request_delay = value
        self.config_manager.save_config()

    def _on_batch_size_changed(self, value: int):
        """Handle batch size changed."""
        self.config_manager.translation_settings.max_batch_size = value
        self.config_manager.save_config()

    def _on_concurrent_changed(self, value: int):
        """Handle concurrent requests changed."""
        self.config_manager.translation_settings.max_concurrent_threads = value
        self.config_manager.save_config()

    def _on_retry_changed(self, value: int):
        """Handle retry count changed."""
        self.config_manager.translation_settings.max_retries = value
        self.config_manager.save_config()

    def _on_force_runtime_translation_changed(self, checked: bool):
        """Handle force runtime translation toggle."""
        self.config_manager.translation_settings.force_runtime_translation = checked
        self.config_manager.save_config()

    def _on_batch_size_slider_released(self):
        # Deprecated
        pass

    def _on_concurrent_slider_released(self):
        # Deprecated
        pass

    def _on_retry_slider_released(self):
        # Deprecated
        pass

    def _open_glossary_editor(self):
        """Open glossary editor dialog."""
        try:
            from src.gui.glossary_dialog import GlossaryEditorDialog
            dialog = GlossaryEditorDialog(self.config_manager, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening glossary editor: {e}")
    
    def _on_aggressive_retry_changed(self, checked: bool):
        """Handle aggressive retry toggle."""
        self.config_manager.translation_settings.aggressive_retry_translation = checked
        self.config_manager.save_config()

    def _on_deepl_formality_changed(self, index: int):
        """Handle DeepL formality change."""
        if hasattr(self, 'FORMALITY_OPTIONS') and 0 <= index < len(self.FORMALITY_OPTIONS):
            formality = self.FORMALITY_OPTIONS[index]
            self.config_manager.translation_settings.deepl_formality = formality
            self.config_manager.save_config()
            self.logger.info(f"DeepL formality set to: {formality}")


    def _on_proxy_enabled_changed(self, checked: bool):
        """Handle proxy enable toggle."""
        self.config_manager.proxy_settings.enabled = checked
        self.config_manager.save_config()

    def _refresh_proxies(self):
        """Refresh proxy list."""
        import asyncio
        import threading
        from src.core.proxy_manager import ProxyManager
        
        def run_refresh():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                pm = ProxyManager()
                loop.run_until_complete(pm.initialize())
                
                stats = pm.get_proxy_stats()
                self.logger.info(f"Proxy refresh: {stats['working_proxies']}/{stats['total_proxies']}")
                
                # Show success notification
                if self.parent_window:
                    # Thread safety: use QTimer or just hope InfoBar handles it (usually does via signals)
                    # For safety in complex UI, it's better to use signals, but direct call often works in simple cases
                    from PyQt6.QtCore import QMetaObject, Q_ARG
                    QMetaObject.invokeMethod(self.parent_window, "show_info_bar",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "success"),
                        Q_ARG(str, self.config_manager.get_ui_text("success", "Başarılı")),
                        Q_ARG(str, self.config_manager.get_ui_text("proxy_refresh_success", "Proxy listesi güncellendi: {working}/{total} aktif.")
                              .format(working=stats['working_proxies'], total=stats['total_proxies']))
                    )
            except Exception as e:
                self.logger.error(f"Proxy refresh error: {e}")
                if self.parent_window:
                    QMetaObject.invokeMethod(self.parent_window, "show_info_bar",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "error"),
                        Q_ARG(str, self.config_manager.get_ui_text("error", "Hata")),
                        Q_ARG(str, str(e))
                    )
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()
        
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("proxy_refreshing", "Proxy Yenileniyor"),
                self.config_manager.get_ui_text("proxy_refresh_started", "Proxy listesi arka planda güncelleniyor...")
            )

    def _open_custom_proxy_dialog(self):
        """Open custom proxy dialog."""
        try:
            from src.gui.proxy_dialog import CustomProxyDialog
            dialog = CustomProxyDialog(self.config_manager, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening proxy dialog: {e}")

    def _on_check_updates_changed(self, checked: bool):
        """Handle check updates toggle."""
        self.config_manager.app_settings.check_for_updates = checked
        self.config_manager.save_config()

    def _check_updates_now(self):
        """Trigger manual update check."""
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("update_check_title", "Güncelleme Kontrolü"),
                self.config_manager.get_ui_text("update_checking", "Yeni sürüm kontrol ediliyor...")
            )
            self.parent_window._check_for_updates(manual=True)

    def _on_auto_unren_changed(self, checked: bool):
        """Handle auto UnRen toggle."""
        self.config_manager.app_settings.unren_auto_download = checked
        self.config_manager.save_config()


    def _on_deep_scan_changed(self, checked: bool):
        """Handle deep scan toggle."""
        self.config_manager.translation_settings.enable_deep_scan = checked
        self.config_manager.save_config()

    def _on_debug_engines_changed(self, checked: bool):
        """Handle debug engines toggle."""
        self.config_manager.translation_settings.show_debug_engines = checked
        self.config_manager.save_config()
        
        # Emit signal to notify other components
        self.debug_engines_changed.emit(checked)
        
        # Notify home interface if possible via a general setting change signal or just hint
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("success", "Başarılı"),
                self.config_manager.get_ui_text("debug_engines_changed", "Ayar kaydedildi. Ana sayfadaki liste güncellendi.")
            )

        """Handle advanced filtering toggle."""
        pass

    def _restore_defaults(self):
        """Restore default settings."""
        # Show confirmation dialog
        w = MessageBox(
            self.config_manager.get_ui_text("confirm", "Onay"),
            self.config_manager.get_ui_text("restore_confirm", "Tüm ayarlar varsayılan değerlere döndürülecek. Emin misiniz?"),
            self
        )
        
        if w.exec():
            try:
                # Reset to defaults
                self.config_manager.reset_to_defaults()
                self.config_manager.save_config()
                
                if self.parent_window:
                    self.parent_window.show_info_bar(
                        "success",
                        self.config_manager.get_ui_text("success", "Başarılı"),
                        self.config_manager.get_ui_text("defaults_restored", "Ayarlar varsayılana döndürüldü. Lütfen uygulamayı yeniden başlatın.")
                    )
            except Exception as e:
                self.logger.error(f"Error restoring defaults: {e}")
