"""
Configuration Manager
====================

Manages application settings and configuration.
"""

import json
import logging
import locale
import os
import sys
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, fields
from enum import Enum
from src.utils.constants import (
    AI_DEFAULT_TEMPERATURE, AI_DEFAULT_TIMEOUT, AI_DEFAULT_MAX_TOKENS,
    AI_MAX_RETRIES, MAX_CHARS_PER_REQUEST, WINDOW_DEFAULT_WIDTH
)

class Language(Enum):
    """Supported UI languages."""
    TURKISH = "tr"
    ENGLISH = "en"
    GERMAN = "de"
    FRENCH = "fr"
    SPANISH = "es"
    RUSSIAN = "ru"
    PERSIAN = "fa"
    CHINESE_S = "zh-CN"
    JAPANESE = "ja"

TURKIC_PRIMARY_LANG_IDS = {
    0x1F,  # Turkish
    0x2C,  # Azerbaijani
    0x29,  # Persian (Azeri regions often use this)
    0x3F,  # Kazakh
    0x40,  # Kyrgyz
    0x42,  # Turkmen
    0x43,  # Uzbek
    0x44,  # Tatar
}

TURKIC_LANGUAGE_CODES = {
    "tr", "az", "azb", "tk", "uz", "kk", "ky", "tt", "ba", "ug", "sah", "kaa"
}


def _is_turkic_locale(code: str) -> bool:
    normalized = (code or "").lower().replace("_", "-")
    primary = normalized.split('-')[0]
    return primary in TURKIC_LANGUAGE_CODES


def detect_system_language() -> str:
    """Detect the system language and return appropriate UI language code."""
    try:
        # Method 1: Windows locale detection
        if os.name == 'nt':  # Windows
            try:
                import ctypes
                # Get user default UI language
                lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                # Primary language mask
                primary_lang = lang_id & 0x3FF

                if primary_lang in TURKIC_PRIMARY_LANG_IDS:
                    return 'tr'
                if primary_lang == 0x09:  # English
                    return 'en'
            except Exception:
                pass

        # Method 2: Standard locale detection
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                if _is_turkic_locale(system_locale):
                    return 'tr'
                lang_part = system_locale.split('_')[0].lower()
                if lang_part == 'en':
                    return 'en'
        except Exception:
            pass

        # Method 3: Environment variables
        try:
            for env_var in ['LANG', 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES']:
                env_value = os.environ.get(env_var, '').lower()
                if not env_value:
                    continue
                if _is_turkic_locale(env_value):
                    return 'tr'
                if 'en' in env_value:
                    return 'en'
        except Exception:
            pass

        # Default to English if detection fails
        return 'en'

    except Exception:
        return 'en'

@dataclass
class TranslationSettings:
    """Translation-related settings."""
    source_language: str = "auto"
    target_language: str = "tr"
    max_concurrent_threads: int = 32
    request_delay: float = 0.1
    max_batch_size: int = 100  # Default batch size (user adjustable, lower = more stable)
    enable_proxy: bool = False  # Disabled by default
    max_retries: int = 3
    timeout: int = 30
    # Multi-endpoint Google Translator settings (v2.1.0)
    use_multi_endpoint: bool = True  # Birden fazla Google mirror kullan
    enable_lingva_fallback: bool = True  # Lingva fallback (ücretsiz, API key gerektirmez)
    max_chars_per_request: int = MAX_CHARS_PER_REQUEST  # Bir istekteki maksimum karakter
    # Glossary & critical terms
    # Glossary & critical terms
    glossary_file: str = "glossary.json"  # Terim sözlüğü yolu (proje köküne göre)
    critical_terms_file: str = "critical_terms.json"  # Kritik kelimeler listesi
    # Type-based translation filters
    translate_dialogue: bool = True
    translate_menu: bool = True
    translate_ui: bool = False
    translate_config_strings: bool = False
    translate_gui_strings: bool = False
    translate_style_strings: bool = False
    translate_renpy_functions: bool = False
    # NEW: Extended text type filters (v2.2.0)
    translate_buttons: bool = True  # textbutton metinleri
    translate_alt_text: bool = True  # imagebutton/hotspot/hotbar alt metinleri (erişilebilirlik)
    translate_input_text: bool = True  # input default/prefix/suffix metinleri
    translate_notifications: bool = True  # Notify() ve renpy.notify() metinleri
    translate_confirmations: bool = True  # Confirm() ve renpy.confirm() metinleri
    translate_define_strings: bool = False  # define statements ile tanımlanan stringler
    
    # Advanced Syntax Guard Settings
    # DEPRECATED: Fuzzy match özelliği v2.5.1+ sürümlerinde kaldırıldı
    # XRPYX placeholder formatı fuzzy matching'e ihtiyaç duymuyor
    # Bu ayar sadece geriye dönük uyumluluk için tutuluyor, UI'da gösterilmiyor
    enable_fuzzy_match: bool = False
    # Deep Scan: Normal pattern'lerin kaçırdığı gizli stringleri bul
    # init python bloklarındaki dictionary'ler, değişken atamaları vb.
    enable_deep_scan: bool = True  # Varsayılan artık açık (gizli string taraması)
    # RPYC Reader: Derlenmiş .rpyc dosyalarını AST ile doğrudan oku
    enable_rpyc_reader: bool = True  # Varsayılan artık açık (derlenmiş .rpyc okuma)
    # Include renpy/common from installed Ren'Py SDKs (optional)
    include_engine_common: bool = True
    context_limit: int = 10  # Number of surrounding lines for context
    # AI Settings (v2.5.0)
    openai_model: str = "gpt-3.5-turbo"
    openai_base_url: str = ""  # For OpenRouter or Local
    deepseek_model: str = "deepseek-chat"
    gemini_model: str = "gemini-2.5-flash"
    gemini_safety_settings: str = "BLOCK_NONE"  # BLOCK_NONE, BLOCK_ONLY_HIGH, STANDARD
    local_llm_model: str = "llama3.2"
    local_llm_url: str = "http://localhost:11434/v1"
    local_llm_timeout: int = 300  # Local LLM için ayrı timeout (saniye) - yerel modeller daha yavaş olabilir
    # Advanced AI Settings
    ai_temperature: float = AI_DEFAULT_TEMPERATURE  # 0.0-1.0, lower = more consistent, higher = more creative
    ai_timeout: int = AI_DEFAULT_TIMEOUT  # seconds, timeout for AI requests
    ai_max_tokens: int = AI_DEFAULT_MAX_TOKENS  # max output tokens
    ai_batch_size: int = 50  # Number of lines per AI request batch (1-200) tokens
    ai_retry_count: int = AI_MAX_RETRIES  # number of retries on failure
    ai_concurrency: int = 2  # NEW: Maximum concurrent requests for AI engines
    ai_request_delay: float = 1.5  # NEW: Delay between AI requests (seconds)
    ai_custom_system_prompt: str = ""  # User-defined system prompt (empty = use built-in)
    # Aggressive Translation Retry: Retry unchanged translations with Lingva/alt endpoints (slower but more thorough)
    aggressive_retry_translation: bool = False  # Default off for speed
    # NEW: Directory & File filtering (v2.5.2)
    exclude_system_folders: bool = True  # Automatically skip renpy/, cache/, saves/, etc.
    scan_rpym_files: bool = False       # Skip .rpym and .rpymc files by default (usually technical)
    auto_generate_hook: bool = True     # Automatically generate Runtime Hook after translation
    # NEW: Cache Management (v2.5.3)
    use_global_cache: bool = True       # Global cache (keeps translations in program folder for portability)
    cache_path: str = "cache"           # Global cache directory name
    # DeepL Settings
    deepl_formality: str = "default"  # default, formal, informal - Hitap şekli (Sen/Siz)
    # Runtime Translation Hook (Zorla Çeviri)
    force_runtime_translation: bool = False  # Oyun içi metinleri zorla çevir (eksik !t flagleri için)
    # Debug/Development settings
    show_debug_engines: bool = False  # Pseudo-Localization gibi debug motorlarını ana listede göster
    # NEW: HTML Wrap Protection (v2.6.3) - translate="no" attribute protection
    # Default: False - Ücretsiz Google endpoint'leri HTML modunu tam desteklemiyor
    # Kullanıcı ayarlardan açabilir (experimental)
    use_html_protection: bool = False

@dataclass
class ApiKeys:
    """API keys for various translation services."""
    deepl_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""

@dataclass
class AppSettings:
    """General application settings."""
    ui_language: str = ""  # Will be auto-detected if empty
    app_theme: str = "dark"  # Application theme: 'dark', 'light', or 'auto'
    last_input_directory: str = ""
    check_for_updates: bool = True
    # Output format: 'old_new' (Ren'Py official old/new blocks, recommended) or 'simple' (legacy)
    output_format: str = "old_new"
    # UnRen integration (Auto RPA Extraction)
    unren_auto_download: bool = True

@dataclass
class ProxySettings:
    """Proxy-related settings."""
    enabled: bool = False  # Disabled by default
    auto_rotate: bool = True
    test_on_startup: bool = True
    update_interval: int = 3600  # seconds
    max_failures: int = 10
    manual_proxies: list = None
    
    def __post_init__(self):
        if self.manual_proxies is None:
            self.manual_proxies = []

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_file: str = "config.json"):
        self.logger = logging.getLogger(__name__)
        self.config_file = Path(config_file)
        self._lock = threading.Lock() # Thread-safety for configuration
        
        # Get the correct locales directory for both dev and executable
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller executable
            self.locales_dir = Path(sys._MEIPASS) / "locales"
        else:
            # Running in development
            self.locales_dir = Path("locales")
        
        # Default configuration
        self.translation_settings = TranslationSettings()
        self.api_keys = ApiKeys()
        self.app_settings = AppSettings()
        self.proxy_settings = ProxySettings()
        
        # Load language files
        self._language_data = {}
        self._load_language_files()

        # Load glossary and critical terms
        self.glossary = self._load_json_file(self.translation_settings.glossary_file, default={})
        self.critical_terms = self._load_json_file(self.translation_settings.critical_terms_file, default=[])

        # Load never-translate rules (optional)
        self.never_translate_rules = self._load_json_file("never_translate.json", default={})
        
        # Load existing configuration
        self.load_config()

    def save_config(self, app_settings: Optional[AppSettings] = None) -> bool:
        """Save configuration to file safely (Atomic & Thread-Safe)."""
        with self._lock: # Ensure thread safety
            try:
                # If specific settings provided, update our instance
                if app_settings is not None:
                    self.app_settings = app_settings
                
                config_data = {
                    'translation_settings': asdict(self.translation_settings),
                    'api_keys': asdict(self.api_keys),
                    'app_settings': asdict(self.app_settings),
                    'proxy_settings': asdict(self.proxy_settings)
                }
                
                # Atomic Write Strategy: Write to temp -> Rename
                # This prevents file corruption if write fails or power is lost
                import tempfile
                import shutil
                
                dir_name = self.config_file.parent.absolute()
                # Create temp file in same directory to ensure atomic move works
                with tempfile.NamedTemporaryFile('w', dir=str(dir_name), delete=False, encoding='utf-8') as tf:
                    json.dump(config_data, tf, indent=4, ensure_ascii=False)
                    temp_name = tf.name
                
                # Atomic replace
                try:
                    shutil.move(temp_name, str(self.config_file))
                    self.logger.info("Configuration saved successfully (Atomic)")
                    return True
                except Exception as move_err:
                    self.logger.error(f"Atomic move failed, trying direct write: {move_err}")
                    # Fallback to unsecured write if rename fails (e.g. permissions)
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=4, ensure_ascii=False)
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error saving configuration: {e}")
                return False
    
    def _filter_config_data(self, dataclass_type, data):
        """Filter dictionary keys to match dataclass fields to avoid __init__ errors."""
        if not isinstance(data, dict):
            return {}
        valid_fields = {f.name for f in fields(dataclass_type)}
        return {k: v for k, v in data.items() if k in valid_fields}

    def _load_language_files(self):
        """Load language JSON files from locales directory dynamically."""
        # Mapping from filename stem to language code (for old-style names)
        FILENAME_TO_LANG_CODE = {
            "turkish": "tr",
            "english": "en",
            "spanish": "es",
            "german": "de",
            "french": "fr",
            "russian": "ru",
            "simplified_chinese": "zh-CN",
            "chinese": "zh-CN",
            # Direct API codes (new naming convention)
            "tr": "tr",
            "en": "en",
            "es": "es",
            "de": "de",
            "fr": "fr",
            "ru": "ru",
            "zh-cn": "zh-CN",  # lowercase version for case-insensitive matching
        }
        
        try:
            self.logger.debug(f"Loading language files from: {self.locales_dir}")
            
            if not self.locales_dir.exists():
                self.logger.warning(f"Locales directory not found: {self.locales_dir}")
                self._language_data = self._get_fallback_translations()
                return
            
            # Dynamically load all JSON files
            for json_file in self.locales_dir.glob("*.json"):
                try:
                    stem = json_file.stem.lower()  # e.g., "tr", "en", "zh-cn"
                    
                    # Map to proper language code
                    if stem in FILENAME_TO_LANG_CODE:
                        lang_code = FILENAME_TO_LANG_CODE[stem]
                    else:
                        # Fallback: use stem as-is for 2-letter codes, otherwise first 2 chars
                        lang_code = stem if len(stem) <= 5 else stem[:2]
                    
                    with open(json_file, 'r', encoding='utf-8') as f:
                        self._language_data[lang_code] = json.load(f)
                    self.logger.debug(f"Loaded {json_file.name} as '{lang_code}'")
                except Exception as file_err:
                    self.logger.warning(f"Could not load {json_file.name}: {file_err}")
            
            self.logger.info(f"Loaded {len(self._language_data)} language files: {list(self._language_data.keys())}")
                
        except Exception as e:
            self.logger.warning(f"Could not load language files: {e}")
            # Fallback to embedded translations if JSON files fail
            self._language_data = self._get_fallback_translations()

    def _load_json_file(self, filename: str, default):
        """Load a JSON file from project root; return default on error."""
        try:
            path = Path(filename)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load JSON file {filename}: {e}")
        return default
    
    def _get_fallback_translations(self) -> Dict[str, Dict[str, Any]]:
        """Fallback translations if JSON files are not available."""
        return {
            'tr': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'Dosya',
                'help_menu': 'Yardım',
                'about': 'Hakkında',
                'info': 'Bilgi',
                'update_checking': 'Güncellemeler kontrol ediliyor...',
                'check_updates_now_label': 'Şimdi Kontrol:',
                'check_updates_now_button': 'Kontrol Et',
                'check_updates_now_tooltip': 'Güncellemeleri şimdi kontrol et',
                'update_available_title': 'Güncelleme Var',
                'update_available_message': 'Yeni sürüm mevcut: {latest} (şu an: {current}).\nSürüm sayfası açılsın mı?',
                'update_up_to_date': 'Güncelsiniz (v{current}).',
                'update_check_failed': 'Güncelleme kontrolü başarısız: {error}',
                'update_check_unavailable': 'Güncelleme kontrolü şu anda kullanılamıyor.',
                'update_open_release': 'Sürümler Sayfasını Aç',
                'update_later': 'Daha Sonra',
                'info_dialog': {
                    'title': 'Program Bilgi Merkezi',
                    'tabs': {
                        'formats': 'Çıktı Formatları'
                    }
                }
            },
            'en': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'File',
                'help_menu': 'Help',
                'about': 'About',
                'info': 'Info',
                'update_checking': 'Checking for updates...',
                'check_updates_now_label': 'Check Now:',
                'check_updates_now_button': 'Check',
                'check_updates_now_tooltip': 'Check for updates right now',
                'update_available_title': 'Update Available',
                'update_available_message': 'A new version is available: {latest} (current: {current}).\nOpen the releases page?',
                'update_up_to_date': 'You are up to date (v{current}).',
                'update_check_failed': 'Update check failed: {error}',
                'update_check_unavailable': 'Update check is not available.',
                'update_open_release': 'Open Releases Page',
                'update_later': 'Later',
                'info_dialog': {
                    'title': 'Program Information Center',
                    'tabs': {
                        'formats': 'Output Formats'
                    }
                }
            }
        }
    
    def load_config(self) -> bool:
        """Load configuration from file."""
        try:
            config_loaded = False
            
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Load translation settings
                if 'translation_settings' in config_data:
                    trans_data = self._filter_config_data(TranslationSettings, config_data['translation_settings'])
                    self.translation_settings = TranslationSettings(**trans_data)
                
                # Load API keys
                if 'api_keys' in config_data:
                    api_data = self._filter_config_data(ApiKeys, config_data['api_keys'])
                    self.api_keys = ApiKeys(**api_data)
                
                # Load app settings
                if 'app_settings' in config_data:
                    app_data = self._filter_config_data(AppSettings, config_data['app_settings'])
                    self.app_settings = AppSettings(**app_data)
                
                # Load proxy settings
                if 'proxy_settings' in config_data:
                    proxy_data = config_data['proxy_settings']
                    # Migration: custom_proxies -> manual_proxies
                    if 'custom_proxies' in proxy_data and 'manual_proxies' not in proxy_data:
                        proxy_data['manual_proxies'] = proxy_data.pop('custom_proxies')
                    elif 'custom_proxies' in proxy_data:
                        proxy_data.pop('custom_proxies')
                    
                    proxy_data = self._filter_config_data(ProxySettings, proxy_data)
                    self.proxy_settings = ProxySettings(**proxy_data)
                
                config_loaded = True
                self.logger.info("Configuration loaded successfully")
            else:
                self.logger.info("Config file not found. Creating default configuration.")
                self.save_config()  # Create the file with default values immediately
            
            # Auto-detect system language if not set or if using defaults
            if not self.app_settings.ui_language or not config_loaded:
                detected_lang = detect_system_language()
                self.app_settings.ui_language = detected_lang
                self.logger.info(f"Auto-detected system language: {detected_lang}")
                
                # Save the detected language to config for future use
                if config_loaded:  # Only save if config was successfully loaded
                    self.save_config()
            
            return config_loaded
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            # Even if config loading fails, set system language
            detected_lang = detect_system_language()
            self.app_settings.ui_language = detected_lang
            self.logger.info(f"Config failed, using auto-detected language: {detected_lang}")
            return False
    

    
    def save_glossary(self) -> bool:
        """Save glossary to file."""
        try:
            filename = self.translation_settings.glossary_file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.glossary, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Glossary saved to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving glossary: {e}")
            return False

    def get_api_key(self, service: str) -> str:
        """Get API key for a service."""
        return getattr(self.api_keys, f"{service}_api_key", "")
    
    def set_api_key(self, service: str, api_key: str) -> None:
        """Set API key for a service."""
        setattr(self.api_keys, f"{service}_api_key", api_key)
        if self.app_settings.auto_save_settings:
            self.save_config()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'ui.theme')."""
        try:
            parts = key.split('.')
            if len(parts) == 2:
                section, setting = parts
                if section == 'ui' or section == 'app':
                    return getattr(self.app_settings, setting, default)
                elif section == 'translation':
                    return getattr(self.translation_settings, setting, default)
                elif section == 'proxy':
                    return getattr(self.proxy_settings, setting, default)
            return default
        except Exception:
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value using dot notation (e.g., 'ui.theme')."""
        try:
            parts = key.split('.')
            if len(parts) == 2:
                section, setting = parts
                if section == 'ui' or section == 'app':
                    setattr(self.app_settings, setting, value)
                elif section == 'translation':
                    setattr(self.translation_settings, setting, value)
                elif section == 'proxy':
                    setattr(self.proxy_settings, setting, value)
                
                if self.app_settings.auto_save_settings:
                    self.save_config()
        except Exception as e:
            self.logger.error(f"Error setting {key} to {value}: {e}")

    def load_locale(self, lang: Language) -> None:
        """Compatibility method for language switching."""
        self.app_settings.ui_language = lang.value
        self.logger.info(f"UI Language shifted to: {lang.value}")
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported language codes and names (API code -> English name)."""
        return {item['api']: item['english'] for item in self.get_all_languages()}
    
    def get_all_languages(self) -> list:
        """
        Central language list - single source of truth.
        Returns list of dicts with 'renpy', 'api', 'english', and 'native' keys.
        """
        return [
            {"renpy": "turkish", "api": "tr", "english": "Turkish", "native": "Türkçe"},
            {"renpy": "english", "api": "en", "english": "English", "native": "English"},
            {"renpy": "german", "api": "de", "english": "German", "native": "Deutsch"},
            {"renpy": "french", "api": "fr", "english": "French", "native": "Français"},
            {"renpy": "spanish", "api": "es", "english": "Spanish", "native": "Español"},
            {"renpy": "italian", "api": "it", "english": "Italian", "native": "Italiano"},
            {"renpy": "portuguese", "api": "pt", "english": "Portuguese", "native": "Português"},
            {"renpy": "russian", "api": "ru", "english": "Russian", "native": "Русский"},
            {"renpy": "polish", "api": "pl", "english": "Polish", "native": "Polski"},
            {"renpy": "dutch", "api": "nl", "english": "Dutch", "native": "Nederlands"},
            {"renpy": "japanese", "api": "ja", "english": "Japanese", "native": "日本語"},
            {"renpy": "korean", "api": "ko", "english": "Korean", "native": "한국어"},
            {"renpy": "chinese_s", "api": "zh-CN", "english": "Chinese (Simplified)", "native": "简体中文"},
            {"renpy": "chinese_t", "api": "zh-TW", "english": "Chinese (Traditional)", "native": "繁體中文"},
            {"renpy": "arabic", "api": "ar", "english": "Arabic", "native": "العربية"},
            {"renpy": "thai", "api": "th", "english": "Thai", "native": "ไทย"},
            {"renpy": "vietnamese", "api": "vi", "english": "Vietnamese", "native": "Tiếng Việt"},
            {"renpy": "indonesian", "api": "id", "english": "Indonesian", "native": "Bahasa Indonesia"},
            {"renpy": "malay", "api": "ms", "english": "Malay", "native": "Bahasa Melayu"},
            {"renpy": "hindi", "api": "hi", "english": "Hindi", "native": "हिन्दी"},
            {"renpy": "persian", "api": "fa", "english": "Persian (Farsi)", "native": "فارsi"},
            {"renpy": "czech", "api": "cs", "english": "Czech", "native": "Čeština"},
            {"renpy": "danish", "api": "da", "english": "Danish", "native": "Dansk"},
            {"renpy": "finnish", "api": "fi", "english": "Finnish", "native": "Suomi"},
            {"renpy": "greek", "api": "el", "english": "Greek", "native": "Ελληνικά"},
            {"renpy": "hebrew", "api": "he", "english": "Hebrew", "native": "עברית"},
            {"renpy": "hungarian", "api": "hu", "english": "Hungarian", "native": "Magyar"},
            {"renpy": "norwegian", "api": "no", "english": "Norwegian", "native": "Norsk"},
            {"renpy": "romanian", "api": "ro", "english": "Romanian", "native": "Română"},
            {"renpy": "swedish", "api": "sv", "english": "Swedish", "native": "Svenska"},
            {"renpy": "ukrainian", "api": "uk", "english": "Ukrainian", "native": "Українська"},
            {"renpy": "bulgarian", "api": "bg", "english": "Bulgarian", "native": "Български"},
            {"renpy": "catalan", "api": "ca", "english": "Catalan", "native": "Català"},
            {"renpy": "croatian", "api": "hr", "english": "Croatian", "native": "Hrvatski"},
            {"renpy": "slovak", "api": "sk", "english": "Slovak", "native": "Slovenčina"},
            {"renpy": "slovenian", "api": "sl", "english": "Slovenian", "native": "Slovenščina"},
            {"renpy": "serbian", "api": "sr", "english": "Serbian", "native": "Српски"},
            {"renpy": "afrikaans", "api": "af", "english": "Afrikaans", "native": "Afrikaans"},
            {"renpy": "albanian", "api": "sq", "english": "Albanian", "native": "Shqip"},
            {"renpy": "amharic", "api": "am", "english": "Amharic", "native": "አማርኛ"},
            {"renpy": "armenian", "api": "hy", "english": "Armenian", "native": "Հայերեն"},
            {"renpy": "azerbaijani", "api": "az", "english": "Azerbaijani", "native": "Azərbaycanca"},
            {"renpy": "basque", "api": "eu", "english": "Basque", "native": "Euskara"},
            {"renpy": "belarusian", "api": "be", "english": "Belarusian", "native": "Беларуская"},
            {"renpy": "bengali", "api": "bn", "english": "Bengali", "native": "বাংলা"},
            {"renpy": "bosnian", "api": "bs", "english": "Bosnian", "native": "Bosanski"},
            {"renpy": "esperanto", "api": "eo", "english": "Esperanto", "native": "Esperanto"},
            {"renpy": "estonian", "api": "et", "english": "Estonian", "native": "Eesti"},
            {"renpy": "filipino", "api": "tl", "english": "Filipino", "native": "Filipino"},
            {"renpy": "galician", "api": "gl", "english": "Galician", "native": "Galego"},
            {"renpy": "georgian", "api": "ka", "english": "Georgian", "native": "ქართული"},
            {"renpy": "gujarati", "api": "gu", "english": "Gujarati", "native": "ગુજરાતી"},
            {"renpy": "haitian_creole", "api": "ht", "english": "Haitian Creole", "native": "Kreyòl Ayisyen"},
            {"renpy": "hausa", "api": "ha", "english": "Hausa", "native": "Hausa"},
            {"renpy": "icelandic", "api": "is", "english": "Icelandic", "native": "Íslenska"},
            {"renpy": "igbo", "api": "ig", "english": "Igbo", "native": "Asụsụ Igbo"},
            {"renpy": "irish", "api": "ga", "english": "Irish", "native": "Gaeilge"},
            {"renpy": "javanese", "api": "jv", "english": "Javanese", "native": "Basa Jawa"},
            {"renpy": "kannada", "api": "kn", "english": "Kannada", "native": "ಕನ್ನಡ"},
            {"renpy": "kazakh", "api": "kk", "english": "Kazakh", "native": "Қазақ тілі"},
            {"renpy": "khmer", "api": "km", "english": "Khmer", "native": "ភាសាខ្មែរ"},
            {"renpy": "kurdish", "api": "ku", "english": "Kurdish", "native": "Kurdî"},
            {"renpy": "kyrgyz", "api": "ky", "english": "Kyrgyz", "native": "Кыргызча"},
            {"renpy": "lao", "api": "lo", "english": "Lao", "native": "ພາສາລາວ"},
            {"renpy": "latvian", "api": "lv", "english": "Latvian", "native": "Latviešu"},
            {"renpy": "lithuanian", "api": "lt", "english": "Lithuanian", "native": "Lietuvių"},
            {"renpy": "luxembourgish", "api": "lb", "english": "Luxembourgish", "native": "Lëtzebuergesch"},
            {"renpy": "macedonian", "api": "mk", "english": "Macedonian", "native": "Македонски"},
            {"renpy": "malagasy", "api": "mg", "english": "Malagasy", "native": "Malagasy"},
            {"renpy": "malayalam", "api": "ml", "english": "Malayalam", "native": "മലയാളം"},
            {"renpy": "maltese", "api": "mt", "english": "Maltese", "native": "Malti"},
            {"renpy": "maori", "api": "mi", "english": "Maori", "native": "Māori"},
            {"renpy": "marathi", "api": "mr", "english": "Marathi", "native": "मराठी"},
            {"renpy": "mongolian", "api": "mn", "english": "Mongolian", "native": "Монгол"},
            {"renpy": "myanmar", "api": "my", "english": "Myanmar (Burmese)", "native": "ဗမာ"},
            {"renpy": "nepali", "api": "ne", "english": "Nepali", "native": "नेपाली"},
            {"renpy": "pashto", "api": "ps", "english": "Pashto", "native": "پښتو"},
            {"renpy": "punjabi", "api": "pa", "english": "Punjabi", "native": "ਪੰਜਾਬੀ"},
            {"renpy": "samoan", "api": "sm", "english": "Samoan", "native": "Gagana Sāmoa"},
            {"renpy": "scots_gaelic", "api": "gd", "english": "Scots Gaelic", "native": "Gàidhlig"},
            {"renpy": "shona", "api": "sn", "english": "Shona", "native": "chiShona"},
            {"renpy": "sindhi", "api": "sd", "english": "Sindhi", "native": "سنڌي"},
            {"renpy": "sinhala", "api": "si", "english": "Sinhala", "native": "සිංහල"},
            {"renpy": "somali", "api": "so", "english": "Somali", "native": "Soomaali"},
            {"renpy": "swahili", "api": "sw", "english": "Swahili", "native": "Kiswahili"},
            {"renpy": "tajik", "api": "tg", "english": "Tajik", "native": "Тоҷикӣ"},
            {"renpy": "tamil", "api": "ta", "english": "Tamil", "native": "தமிழ்"},
            {"renpy": "telugu", "api": "te", "english": "Telugu", "native": "తెలుగు"},
            {"renpy": "urdu", "api": "ur", "english": "Urdu", "native": "اردو"},
            {"renpy": "uzbek", "api": "uz", "english": "Uzbek", "native": "Oʻzbekcha"},
            {"renpy": "welsh", "api": "cy", "english": "Welsh", "native": "Cymraeg"},
            {"renpy": "xhosa", "api": "xh", "english": "Xhosa", "native": "isiXhosa"},
            {"renpy": "yiddish", "api": "yi", "english": "Yiddish", "native": "ייִדיש"},
            {"renpy": "yoruba", "api": "yo", "english": "Yoruba", "native": "Yorùbá"},
            {"renpy": "zulu", "api": "zu", "english": "Zulu", "native": "isiZulu"},
        ]
    
    def get_renpy_to_api_map(self) -> Dict[str, str]:
        """Get Ren'Py language code to API code mapping."""
        return {item['renpy']: item['api'] for item in self.get_all_languages()}
    
    def get_target_languages_for_ui(self) -> list:
        """Get languages for UI dropdowns as list of (renpy_code, display_name) tuples."""
        result = []
        for item in self.get_all_languages():
            name = item['native']
            # Add English name in parens if it differs from native
            if item['english'].lower() != item['native'].lower():
                name = f"{item['native']} ({item['english']})"
            result.append((item['renpy'], name))
        return result
    
    def get_ui_translations(self) -> Dict[str, Dict[str, Any]]:
        """Get UI translations for supported languages from JSON files."""
        return self._language_data
    
    def get_ui_text(self, key: str, default: str = None, **kwargs) -> Any:
        """Get UI text in current language with support for nested keys and formatting."""
        translations = self.get_ui_translations()
        current_lang = self.app_settings.ui_language
        
        # Support for nested keys like 'info_dialog.title'
        def get_nested_value(data: Dict, key_path: str):
            keys = key_path.split('.')
            value = data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return None
            return value
        
        result = None
        # Try current language first
        if current_lang in translations:
            result = get_nested_value(translations[current_lang], key)
        
        # Fallback to English
        if result is None and 'en' in translations:
            result = get_nested_value(translations['en'], key)
        
        # Fallback to provided default or key itself
        if result is None:
            result = default if default is not None else key

        # Apply formatting if kwargs provided and result is a string
        if kwargs and isinstance(result, str):
            try:
                return result.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                # If formatting fails, return result as-is
                return result
                
        return result
    
    def get_log_text(self, key: str, default: str = None, **kwargs) -> str:
        """
        Get localized log message from pipeline_logs section.
        Supports placeholder formatting with kwargs.
        
        Example:
            get_log_text("unren_completed_code", code=0)
            -> "UnRen tamamlandı (kod: 0)"
        """
        full_key = f"pipeline_logs.{key}"
        # Use key as default if neither template nor explicit default provided
        template = self.get_ui_text(full_key, default if default is not None else key)
        
        # Apply placeholders if any
        if kwargs and isinstance(template, str):
            try:
                return template.format(**kwargs)
            except KeyError:
                # If some placeholders are missing, return template as-is
                return template
        return template
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.translation_settings = TranslationSettings()
        self.api_keys = ApiKeys()
        self.app_settings = AppSettings()
        self.proxy_settings = ProxySettings()
        self.logger.info("Configuration reset to defaults")

