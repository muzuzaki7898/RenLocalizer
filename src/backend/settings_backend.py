# -*- coding: utf-8 -*-
"""
Settings Backend - Python-QML Bridge for Settings
==================================================

Provides settings management functionality for QML UI.
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty
from PyQt6.QtWidgets import QApplication

from src.utils.config import ConfigManager, Language


class SettingsBackend(QObject):
    """Settings page Python-QML bridge."""
    
    # Signals
    settingsSaved = pyqtSignal()
    languageChanged = pyqtSignal(str)
    themeChanged = pyqtSignal(str)
    systemThemeChanged = pyqtSignal()
    proxyRefreshFinished = pyqtSignal(bool, str) # success, message
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
    
    @pyqtSlot(str, str, result=str)
    def getTextWithDefault(self, key: str, default: str) -> str:
        """Get localized text with default fallback."""
        return self.config.get_ui_text(key, default)
    
    # ==================== GENERAL SETTINGS ====================
    
    @pyqtSlot(result=list)
    def getAvailableUILanguages(self) -> list:
        """Get available UI languages."""
        return [
            {"code": "tr", "name": "🇹🇷 Türkçe"},
            {"code": "en", "name": "🇬🇧 English"},
            {"code": "de", "name": "🇩🇪 Deutsch"},
            {"code": "fr", "name": "🇫🇷 Français"},
            {"code": "es", "name": "🇪🇸 Español"},
            {"code": "ru", "name": "🇷🇺 Русский"},
            {"code": "fa", "name": "🇮🇷 فارسی"},
            {"code": "zh-CN", "name": "🇨🇳 中文 (简体)"},
            {"code": "ja", "name": "🇯🇵 日本語"},
        ]
    
    @pyqtSlot(result=str)
    def getCurrentUILanguage(self) -> str:
        """Get current UI language code."""
        return self.config.app_settings.ui_language or "en"
    
    @pyqtSlot(str)
    def setUILanguage(self, lang_code: str):
        """Set UI language."""
        try:
            lang = Language(lang_code)
            # self.config.app_settings.ui_language = lang_code # Handled inside load_locale
            self.config.load_locale(lang)
            self.config.save_config()
            self.languageChanged.emit(lang_code)
        except Exception as e:
            print(f"Error setting UI language: {e}")
    
    @pyqtSlot(result=list)
    def getAvailableThemes(self) -> list:
        """Get available themes - internal only, no system theme."""
        return [
            {"code": "dark", "name": self.config.get_ui_text("theme_dark", "🌙 Koyu")},
            {"code": "light", "name": self.config.get_ui_text("theme_light", "☀️ Açık")},
            {"code": "red", "name": self.config.get_ui_text("theme_red", "🔴 Kırmızı")},
            {"code": "turquoise", "name": self.config.get_ui_text("theme_turquoise", "🔵 Turkuaz")},
            {"code": "green", "name": self.config.get_ui_text("theme_green", "🌿 Yeşil")},
            {"code": "neon", "name": self.config.get_ui_text("theme_neon", "🌈 Neon")},
        ]
    
    @pyqtProperty(str, notify=themeChanged)
    def currentTheme(self):
        return self.config.app_settings.app_theme or "dark"

    @currentTheme.setter
    def currentTheme(self, value):
        self.setTheme(value)

    @pyqtProperty(str, notify=languageChanged)
    def currentLanguage(self):
        return self.config.app_settings.ui_language or "tr"

    @currentLanguage.setter
    def currentLanguage(self, value):
        self.setUILanguage(value)

    @pyqtProperty(bool, notify=systemThemeChanged)
    def isSystemDark(self):
        """Sistem temasının karanlık olup olmadığını kontrol et."""
        try:
            from darkdetect import isDark
            return isDark()
        except ImportError:
            return True # Fallback to dark

    @pyqtSlot(result=str)
    def getCurrentTheme(self) -> str:
        """Get current theme."""
        return self.currentTheme
    
    @pyqtSlot(str)
    def setTheme(self, theme: str):
        """Set application theme."""
        self.config.app_settings.app_theme = theme
        self.config.save_config()
        
        # Theme remains applied via QML Material configuration
        pass
        
        self.themeChanged.emit(theme)
    
    @pyqtSlot(result=bool)
    def getCheckUpdates(self) -> bool:
        """Get check updates setting."""
        return self.config.app_settings.check_for_updates
    
    @pyqtSlot(bool)
    def setCheckUpdates(self, enabled: bool):
        """Set check updates setting."""
        self.config.app_settings.check_for_updates = enabled
        self.config.save_config()
    
    # ==================== API KEYS ====================
    
    @pyqtSlot(result=str)
    def getDeepLApiKey(self) -> str:
        return self.config.api_keys.deepl_api_key or ""
    
    @pyqtSlot(str)
    def setDeepLApiKey(self, key: str):
        self.config.api_keys.deepl_api_key = key
        self.config.save_config()

    @pyqtSlot(result=str)
    def getDeepLFormality(self) -> str:
        return getattr(self.config.translation_settings, 'deepl_formality', 'default')

    @pyqtSlot(str)
    def setDeepLFormality(self, value: str):
        self.config.translation_settings.deepl_formality = value
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getOpenAIApiKey(self) -> str:
        return self.config.api_keys.openai_api_key or ""
    
    @pyqtSlot(str)
    def setOpenAIApiKey(self, key: str):
        self.config.api_keys.openai_api_key = key
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getGeminiApiKey(self) -> str:
        return self.config.api_keys.gemini_api_key or ""
    
    @pyqtSlot(str)
    def setGeminiApiKey(self, key: str):
        self.config.api_keys.gemini_api_key = key
        self.config.save_config()

    @pyqtSlot(result=str)
    def getDeepSeekApiKey(self) -> str:
        return self.config.api_keys.deepseek_api_key or ""

    @pyqtSlot(str)
    def setDeepSeekApiKey(self, key: str):
        self.config.api_keys.deepseek_api_key = key
        self.config.save_config()

    @pyqtSlot(result=str)
    def getDeepSeekModel(self) -> str:
        return getattr(self.config.translation_settings, 'deepseek_model', 'deepseek-chat')

    @pyqtSlot(str)
    def setDeepSeekModel(self, value: str):
        self.config.translation_settings.deepseek_model = value
        self.config.save_config()
    
    # ==================== TRANSLATION SETTINGS ====================
    
    @pyqtSlot(result=int)
    def getBatchSize(self) -> int:
        return self.config.translation_settings.max_batch_size
    
    @pyqtSlot(int)
    def setBatchSize(self, value: int):
        self.config.translation_settings.max_batch_size = value
        self.config.save_config()
    
    @pyqtSlot(result=float)
    def getRequestDelay(self) -> float:
        return self.config.translation_settings.request_delay
    
    @pyqtSlot(float)
    def setRequestDelay(self, value: float):
        self.config.translation_settings.request_delay = value
        self.config.save_config()
    
    @pyqtSlot(result=int)
    def getConcurrentThreads(self) -> int:
        return self.config.translation_settings.max_concurrent_threads
    
    @pyqtSlot(int)
    def setConcurrentThreads(self, value: int):
        self.config.translation_settings.max_concurrent_threads = value
        self.config.save_config()
    
    @pyqtSlot(result=int)
    def getContextLimit(self) -> int:
        return self.config.translation_settings.context_limit
    
    @pyqtSlot(int)
    def setContextLimit(self, value: int):
        self.config.translation_settings.context_limit = value
        self.config.save_config()
    
    @pyqtSlot(result=int)
    def getMaxRetries(self) -> int:
        return self.config.translation_settings.max_retries
    
    @pyqtSlot(int)
    def setMaxRetries(self, value: int):
        self.config.translation_settings.max_retries = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getTimeout(self) -> int:
        return self.config.translation_settings.timeout
    
    @pyqtSlot(int)
    def setTimeout(self, value: int):
        self.config.translation_settings.timeout = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getMaxCharsPerRequest(self) -> int:
        return self.config.translation_settings.max_chars_per_request
    
    @pyqtSlot(int)
    def setMaxCharsPerRequest(self, value: int):
        self.config.translation_settings.max_chars_per_request = value
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getAggressiveRetry(self) -> bool:
        return self.config.translation_settings.aggressive_retry_translation

    @pyqtSlot(bool)
    def setAggressiveRetry(self, enabled: bool):
        self.config.translation_settings.aggressive_retry_translation = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getForceRuntime(self) -> bool:
        return self.config.translation_settings.force_runtime_translation

    @pyqtSlot(bool)
    def setForceRuntime(self, enabled: bool):
        self.config.translation_settings.force_runtime_translation = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getUseMultiEndpoint(self) -> bool:
        return self.config.translation_settings.use_multi_endpoint

    @pyqtSlot(bool)
    def setUseMultiEndpoint(self, enabled: bool):
        self.config.translation_settings.use_multi_endpoint = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getEnableLingvaFallback(self) -> bool:
        return self.config.translation_settings.enable_lingva_fallback

    @pyqtSlot(bool)
    def setEnableLingvaFallback(self, enabled: bool):
        self.config.translation_settings.enable_lingva_fallback = enabled
        self.config.save_config()
    
    # ==================== AI SETTINGS ====================
    
    @pyqtSlot(result=str)
    def getOpenAIModel(self) -> str:
        return self.config.translation_settings.openai_model or "gpt-3.5-turbo"
    
    @pyqtSlot(str)
    def setOpenAIModel(self, model: str):
        self.config.translation_settings.openai_model = model
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getOpenAIBaseUrl(self) -> str:
        return self.config.translation_settings.openai_base_url or ""
    
    @pyqtSlot(str)
    def setOpenAIBaseUrl(self, url: str):
        self.config.translation_settings.openai_base_url = url
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getGeminiModel(self) -> str:
        return self.config.translation_settings.gemini_model or "gemini-2.5-flash"
    
    @pyqtSlot(str)
    def setGeminiModel(self, model: str):
        self.config.translation_settings.gemini_model = model
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getGeminiSafety(self) -> str:
        return self.config.translation_settings.gemini_safety_settings or "BLOCK_MEDIUM_AND_ABOVE"
    
    @pyqtSlot(str)
    def setGeminiSafety(self, level: str):
        self.config.translation_settings.gemini_safety_settings = level
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getLocalLLMModel(self) -> str:
        return self.config.translation_settings.local_llm_model or "llama3.2"
    
    @pyqtSlot(str)
    def setLocalLLMModel(self, text: str):
        self.config.translation_settings.local_llm_model = text
        self.config.save_config()

    # ==================== OPENAI PRESETS ====================
    @pyqtSlot(result=list)
    def getOpenAIPresets(self) -> list:
        """Get available OpenAI-compatible API presets."""
        return [
            {"name": "OpenAI (Default)", "url": "", "model": "gpt-4o-mini"},
            {"name": "OpenRouter", "url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
            {"name": "DeepSeek", "url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
            {"name": "DeepSeek Reasoner", "url": "https://api.deepseek.com/v1", "model": "deepseek-reasoner"},
            {"name": "Grok (xAI)", "url": "https://api.x.ai/v1", "model": "grok-2-latest"},
            {"name": "Qwen 2.5 (OpenRouter)", "url": "https://openrouter.ai/api/v1", "model": "qwen/qwen-2.5-72b-instruct"},
            {"name": "Together AI", "url": "https://api.together.xyz/v1", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
            {"name": "Groq", "url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
            {"name": "Mistral", "url": "https://api.mistral.ai/v1", "model": "mistral-large-latest"},
            {"name": "Custom", "url": "", "model": ""}
        ]
    
    @pyqtSlot(str, result=str)
    def applyOpenAIPreset(self, name: str) -> str:
        """Apply selected OpenAI preset. Returns the new values as JSON for QML to consume."""
        import json
        presets = self.getOpenAIPresets()
        for p in presets:
            if p["name"] == name and name != "Custom":
                self.setOpenAIBaseUrl(p["url"])
                self.setOpenAIModel(p["model"])
                return json.dumps({"url": p["url"], "model": p["model"]})
        return json.dumps({"url": "", "model": ""})

    @pyqtSlot(result=list)
    def getLocalLLMPresets(self) -> list:
        """Get available Local LLM presets."""
        return [
            {"name": "Ollama (Default)", "url": "http://localhost:11434/v1", "model": "llama3.2"},
            {"name": "Jan.ai", "url": "http://localhost:1337/v1", "model": "local-model"},
            {"name": "LM Studio", "url": "http://localhost:1234/v1", "model": "local-model"},
            {"name": "GPT4All", "url": "http://localhost:4891/v1", "model": "local-model"},
            {"name": "KoboldCPP", "url": "http://localhost:5001/v1", "model": "local-model"},
            {"name": "Custom", "url": "", "model": ""}
        ]

    @pyqtSlot(str, result=str)
    def applyLocalLLMPreset(self, name: str) -> str:
        """Apply selected Local LLM preset. Returns the new values as JSON for QML to consume."""
        import json
        presets = self.getLocalLLMPresets()
        for p in presets:
            if p["name"] == name and name != "Custom":
                self.setLocalLLMUrl(p["url"])
                self.setLocalLLMModel(p["model"])
                return json.dumps({"url": p["url"], "model": p["model"]})
        return json.dumps({"url": "", "model": ""})
    
    @pyqtSlot(result=str)
    def getLocalLLMUrl(self) -> str:
        return self.config.translation_settings.local_llm_url or "http://localhost:11434/v1"
    
    @pyqtSlot(str)
    def setLocalLLMUrl(self, url: str):
        self.config.translation_settings.local_llm_url = url
        self.config.save_config()

    @pyqtSlot(result=int)
    def getLocalLLMTimeout(self) -> int:
        return self.config.translation_settings.local_llm_timeout or 300
    
    @pyqtSlot(int)
    def setLocalLLMTimeout(self, value: int):
        self.config.translation_settings.local_llm_timeout = value
        self.config.save_config()

    @pyqtSlot(result=str)
    def testLocalLLMConnection(self) -> str:
        """Test connection to local LLM server synchronously for QML."""
        import asyncio
        try:
            from src.core.ai_translator import LocalLLMTranslator
            ts = self.config.translation_settings
            translator = LocalLLMTranslator(
                model=ts.local_llm_model or "llama3.2",
                base_url=ts.local_llm_url or "http://localhost:11434/v1",
                config_manager=self.config
            )
            
            # Create a temporary event loop to run the async health check
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success, message = loop.run_until_complete(translator.health_check())
                loop.run_until_complete(translator.close())
                return message
            finally:
                loop.close()
        except Exception as e:
            return f"{self.config.get_ui_text('error', 'Hata')}: {str(e)}"
    
    @pyqtSlot(result=float)
    def getAITemperature(self) -> float:
        return self.config.translation_settings.ai_temperature
    
    @pyqtSlot(float)
    def setAITemperature(self, value: float):
        self.config.translation_settings.ai_temperature = value
        self.config.save_config()
    
    @pyqtSlot(result=int)
    def getAITimeout(self) -> int:
        return self.config.translation_settings.ai_timeout
    
    @pyqtSlot(int)
    def setAITimeout(self, value: int):
        self.config.translation_settings.ai_timeout = value
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getUseHtmlProtection(self) -> bool:
        return self.config.translation_settings.use_html_protection

    @pyqtSlot(bool)
    def setUseHtmlProtection(self, value: bool):
        self.config.translation_settings.use_html_protection = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getAIMaxTokens(self) -> int:
        return self.config.translation_settings.ai_max_tokens

    @pyqtSlot(int)
    def setAIMaxTokens(self, value: int):
        self.config.translation_settings.ai_max_tokens = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getAIBatchSize(self) -> int:
        return self.config.translation_settings.ai_batch_size

    @pyqtSlot(int)
    def setAIBatchSize(self, value: int):
        self.config.translation_settings.ai_batch_size = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getAIRetryCount(self) -> int:
        return self.config.translation_settings.ai_retry_count

    @pyqtSlot(int)
    def setAIRetryCount(self, value: int):
        self.config.translation_settings.ai_retry_count = value
        self.config.save_config()

    @pyqtSlot(result=int)
    def getAIConcurrency(self) -> int:
        return self.config.translation_settings.ai_concurrency

    @pyqtSlot(int)
    def setAIConcurrency(self, value: int):
        self.config.translation_settings.ai_concurrency = value
        self.config.save_config()

    @pyqtSlot(result=float)
    def getAIRequestDelay(self) -> float:
        return self.config.translation_settings.ai_request_delay

    @pyqtSlot(float)
    def setAIRequestDelay(self, value: float):
        self.config.translation_settings.ai_request_delay = value
        self.config.save_config()

    @pyqtSlot(result=str)
    def getAISystemPrompt(self) -> str:
        return self.config.translation_settings.ai_custom_system_prompt or ""

    @pyqtSlot(str)
    def setAISystemPrompt(self, text: str):
        self.config.translation_settings.ai_custom_system_prompt = text
        self.config.save_config()
    
    # ==================== PROXY SETTINGS ====================
    
    @pyqtSlot(result=bool)
    def getProxyEnabled(self) -> bool:
        return getattr(self.config.proxy_settings, 'enabled', False)
    
    @pyqtSlot(bool)
    def setProxyEnabled(self, enabled: bool):
        self.config.proxy_settings.enabled = enabled
        self.config.save_config()
    
    @pyqtSlot(result=str)
    def getProxyUrl(self) -> str:
        return getattr(self.config.proxy_settings, 'proxy_url', '') or ""
    
    @pyqtSlot(str)
    def setProxyUrl(self, url: str):
        self.config.proxy_settings.proxy_url = url
        self.config.save_config()

    @pyqtSlot(result=str)
    def getManualProxies(self) -> str:
        proxies = getattr(self.config.proxy_settings, 'manual_proxies', [])
        return "\n".join(proxies)

    @pyqtSlot(str)
    def setManualProxies(self, text: str):
        proxies = [p.strip() for p in text.split("\n") if p.strip()]
        self.config.proxy_settings.manual_proxies = proxies
        self.config.save_config()

    @pyqtSlot()
    def refreshProxies(self):
        """Refresh proxy list in background."""
        import threading
        threading.Thread(target=self._refresh_proxies_thread, daemon=True).start()

    def _refresh_proxies_thread(self):
        import asyncio
        try:
            from src.core.proxy_manager import ProxyManager
            
            async def run_refresh():
                pm = ProxyManager()
                # Use settings to configure partial behavior if needed
                pm.configure_from_settings(self.config.proxy_settings)
                await pm.initialize() # Fetches and tests
                return pm.get_proxy_stats()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                stats = loop.run_until_complete(run_refresh())
                msg = self.config.get_ui_text("proxy_refresh_success", "Proxy listesi güncellendi: {working}/{total} aktif.").format(
                    working=stats['working_proxies'], total=stats['total_proxies']
                )
                self.proxyRefreshFinished.emit(True, msg)
            finally:
                loop.close()
                
        except Exception as e:
            self.proxyRefreshFinished.emit(False, str(e))

    # ==================== DEEPL SETTINGS ====================

    @pyqtSlot(result=str)
    def getDeepLFormality(self) -> str:
        return getattr(self.config.translation_settings, 'deepl_formality', 'default')

    @pyqtSlot(str)
    def setDeepLFormality(self, formality: str):
        self.config.translation_settings.deepl_formality = formality
        self.config.save_config()
    
    # ==================== ADVANCED SETTINGS ====================
    
    @pyqtSlot(result=bool)
    def getShowDebugEngines(self) -> bool:
        return getattr(self.config.translation_settings, 'show_debug_engines', False)
    
    @pyqtSlot(bool)
    def setShowDebugEngines(self, enabled: bool):
        self.config.translation_settings.show_debug_engines = enabled
        self.config.save_config()
    
    @pyqtSlot(result=bool)
    def getExcludeSystemFolders(self) -> bool:
        return getattr(self.config.translation_settings, 'exclude_system_folders', True)
    
    @pyqtSlot(bool)
    def setExcludeSystemFolders(self, enabled: bool):
        self.config.translation_settings.exclude_system_folders = enabled
        self.config.save_config()
    
    @pyqtSlot(result=bool)
    def getScanRpymFiles(self) -> bool:
        return getattr(self.config.translation_settings, 'scan_rpym_files', False)
    
    @pyqtSlot(bool)
    def setScanRpymFiles(self, enabled: bool):
        self.config.translation_settings.scan_rpym_files = enabled
        self.config.save_config()
    
    @pyqtSlot(result=bool)
    def getUseGlobalCache(self) -> bool:
        return getattr(self.config.translation_settings, 'use_global_cache', True)
    
    @pyqtSlot(bool)
    def setUseGlobalCache(self, enabled: bool):
        self.config.translation_settings.use_global_cache = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getEnableDeepScan(self) -> bool:
        return self.config.translation_settings.enable_deep_scan

    @pyqtSlot(bool)
    def setEnableDeepScan(self, enabled: bool):
        self.config.translation_settings.enable_deep_scan = enabled
        self.config.save_config()

    # DEPRECATED: Fuzzy match no longer used in v2.5.1+ (XRPYX format)
    # Kept for backward compatibility with old config files
    @pyqtSlot(result=bool)
    def getEnableFuzzyMatch(self) -> bool:
        """Deprecated: Fuzzy match is no longer used."""
        return False  # Always return False

    @pyqtSlot(bool)
    def setEnableFuzzyMatch(self, enabled: bool):
        """Deprecated: Fuzzy match is no longer used."""
        pass  # No-op

    @pyqtSlot(result=bool)
    def getEnableRpycReader(self) -> bool:
        return self.config.translation_settings.enable_rpyc_reader

    @pyqtSlot(bool)
    def setEnableRpycReader(self, enabled: bool):
        self.config.translation_settings.enable_rpyc_reader = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getAutoUnren(self) -> bool:
        return self.config.app_settings.unren_auto_download

    @pyqtSlot(bool)
    def setAutoUnren(self, enabled: bool):
        self.config.app_settings.unren_auto_download = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getAutoHook(self) -> bool:
        return self.config.translation_settings.auto_generate_hook

    @pyqtSlot(bool)
    def setAutoHook(self, enabled: bool):
        self.config.translation_settings.auto_generate_hook = enabled
        self.config.save_config()

    @pyqtSlot(result=bool)
    def getUseCache(self) -> bool:
        return getattr(self.config.translation_settings, 'use_cache', True)

    @pyqtSlot(bool)
    def setUseCache(self, enabled: bool):
        self.config.translation_settings.use_cache = enabled
        self.config.save_config()

    # ==================== FILTER SETTINGS ====================

    @pyqtSlot(str, result=bool)
    def getFilter(self, key: str) -> bool:
        # Fuzzy match is deprecated, always return False
        if key == "fuzzy_match":
            return False
        return getattr(self.config.translation_settings, f"translate_{key}", True)

    @pyqtSlot(str, bool)
    def setFilter(self, key: str, value: bool):
        # Fuzzy match is deprecated, ignore
        if key == "fuzzy_match":
            return
        setattr(self.config.translation_settings, f"translate_{key}", value)
        self.config.save_config()
    
    @pyqtSlot()
    def restoreDefaults(self):
        """Restore all settings to defaults."""
        self.config.reset_to_defaults()
        self.config.save_config()
        self.settingsSaved.emit()
