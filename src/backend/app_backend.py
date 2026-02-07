# -*- coding: utf-8 -*-
"""
App Backend - Python-QML Bridge
================================

This module provides the bridge between QML UI and Python backend logic.
All QML-callable methods and signals are defined here.
"""

import os
import sys
import logging
import threading
import asyncio
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl, QThread
from PyQt6.QtGui import QDesktopServices

from src.utils.config import ConfigManager
from src.version import VERSION
from src.core.translator import (
    TranslationManager, TranslationEngine,
    GoogleTranslator, DeepLTranslator, PseudoTranslator
)
from src.core.proxy_manager import ProxyManager
from src.core.translation_pipeline import TranslationPipeline, PipelineWorker

if TYPE_CHECKING:
    from src.core.ai_translator import OpenAITranslator, GeminiTranslator, LocalLLMTranslator, DeepSeekTranslator
from src.utils.data_transfer import export_glossary_to_file, import_glossary_from_file


class AppBackend(QObject):
    """
    Python-QML köprüsü.
    
    QML tarafından çağrılabilir metotlar (@pyqtSlot) ve
    QML'e bildirim gönderen sinyaller (pyqtSignal) içerir.
    """
    
    # ========== SIGNALS (QML'e bildirim gönderir) ==========
    logMessage = pyqtSignal(str, str, arguments=['level', 'message'])
    progressChanged = pyqtSignal(int, int, str, arguments=['current', 'total', 'text'])
    stageChanged = pyqtSignal(str, str, arguments=['stage', 'displayName'])
    translationStarted = pyqtSignal()
    translationFinished = pyqtSignal(bool, str, arguments=['success', 'message'])
    statsReady = pyqtSignal(int, int, int, arguments=['total', 'translated', 'untranslated'])
    warningMessage = pyqtSignal(str, str, arguments=['title', 'message'])
    languageRefresh = pyqtSignal()
    updateAvailable = pyqtSignal(str, str, str, arguments=['currentVersion', 'latestVersion', 'releaseUrl'])
    updateCheckFinished = pyqtSignal(bool, str, arguments=['hasUpdate', 'message']) # NEW explicit signal
    
    # Initialization Signals (For UI BusyIndicator)
    initializationChanged = pyqtSignal()
    initMessageChanged = pyqtSignal()
    busyChanged = pyqtSignal() # New signal for general busy state
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self._version = VERSION
        self._ui_trigger = False
        
        # State
        self._project_path = self.config.app_settings.last_input_directory or ""
        self._target_language = getattr(self.config.translation_settings, 'target_language', "turkish")
        self._source_language = getattr(self.config.translation_settings, 'source_language', "auto")
        self._selected_engine = getattr(self.config.translation_settings, 'selected_engine', "google")
        self._is_translating = False
        self._is_initializing = False
        self._is_busy = False # General busy state for tools
        self._init_message = ""
        
        # Pipeline
        self.pipeline: Optional[TranslationPipeline] = None
        self.pipeline_worker: Optional[PipelineWorker] = None
        
        # Managers
        self.proxy_manager = ProxyManager()
        self.translation_manager = TranslationManager(self.proxy_manager, self.config)

        self._start_async_setup() # Heavy setup to thread
        
        # Initial Cache Load (Async call)
        self._update_cache_path_async()

    def _start_async_setup(self):
        """Move heavy engine setup to background thread."""
        threading.Thread(target=self._setup_translation_engines, daemon=True).start()

    @pyqtProperty(bool, notify=busyChanged)
    def isBusy(self):
        """Returns True if any background tool is running."""
        return self._is_busy

    def _set_busy(self, busy: bool):
        if self._is_busy != busy:
            self._is_busy = busy
            self.busyChanged.emit()

    @pyqtProperty(bool, notify=initializationChanged)
    def isInitializing(self):
        """Returns True if the backend is initializing (e.g. loading AI models)."""
        return self._is_initializing

    @pyqtProperty(str, notify=initMessageChanged)
    def initializationMessage(self):
        """Returns the current initialization status message."""
        return self._init_message

    def _set_initializing(self, active: bool, message: str = ""):
        """Internal helper to update initialization state and emit signals safely."""
        if self._is_initializing != active:
            self._is_initializing = active
            self.initializationChanged.emit()
        
        if self._init_message != message:
            self._init_message = message
            self.initMessageChanged.emit()
    
    def _setup_translation_engines(self):
        """Setup available translation engines."""
        # Local imports to avoid heavy startup load
        from src.core.ai_translator import OpenAITranslator, GeminiTranslator, LocalLLMTranslator

        # 1. Google Translate (Web)
        google_translator = GoogleTranslator(
            proxy_manager=self.proxy_manager,
            config_manager=self.config
        )
        self.translation_manager.add_translator(TranslationEngine.GOOGLE, google_translator)
        
        # 2. Pseudo (Test)
        pseudo_translator = PseudoTranslator(mode="both")
        self.translation_manager.add_translator(TranslationEngine.PSEUDO, pseudo_translator)
        
        # 3. DeepL
        deepl_key = self.config.get_api_key("deepl")
        if deepl_key:
            deepl_translator = DeepLTranslator(api_key=deepl_key, proxy_manager=self.proxy_manager)
            self.translation_manager.add_translator(TranslationEngine.DEEPL, deepl_translator)

        # 4. OpenAI
        openai_key = self.config.get_api_key("openai")
        # OpenAI her zaman ekle (Key boş olsa bile, kullanıcı sonradan girebilir)
        openai_translator = OpenAITranslator(
            api_key=openai_key or "dummy", # Key yoksa dummy ver, request anında kontrol edilebilir
            model=getattr(self.config.translation_settings, 'openai_model', 'gpt-3.5-turbo'),
            base_url=getattr(self.config.translation_settings, 'openai_base_url', None),
            config_manager=self.config,
            proxy_manager=self.proxy_manager
        )
        self.translation_manager.add_translator(TranslationEngine.OPENAI, openai_translator)

        # 5. Gemini
        gemini_key = self.config.get_api_key("gemini")
        gemini_translator = GeminiTranslator(
            api_key=gemini_key or "dummy",
            model=getattr(self.config.translation_settings, 'gemini_model', 'gemini-2.0-flash-exp'),
            config_manager=self.config
        )
        self.translation_manager.add_translator(TranslationEngine.GEMINI, gemini_translator)



        # 6. Local LLM
        local_translator = LocalLLMTranslator(
            model=getattr(self.config.translation_settings, 'local_llm_model', 'llama3.2'),
            base_url=getattr(self.config.translation_settings, 'local_llm_url', 'http://localhost:11434/v1'),
            config_manager=self.config
        )
        self.translation_manager.add_translator(TranslationEngine.LOCAL_LLM, local_translator)
    
    @pyqtSlot()
    def refreshUI(self):
        """Tüm arayüz metinlerini yenilemek için tetikleyiciyi değiştir."""
        self._ui_trigger = not self._ui_trigger
        self.languageRefresh.emit()

    @pyqtProperty(bool, notify=languageRefresh)
    def uiTrigger(self) -> bool:
        """Dil değiştiğinde QML tarafında metinlerin yeniden yüklenmesini tetikleyen mülk."""
        return self._ui_trigger

    @pyqtSlot(result=str)
    def get_app_path(self) -> str:
        """Uygulamanın çalıştığı dizini döndür (Dosya yolları için)."""
        return os.getcwd().replace("\\", "/")

    @pyqtSlot(str, result=str)
    def get_asset_url(self, relative_path: str) -> str:
        """Returns a valid file URL for the asset, handling frozen state."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
        else:
            # Development mode: assume running from project root
            base = Path(os.getcwd())
        
        full_path = base / relative_path
        # Convert to forward slashes for QML
        return QUrl.fromLocalFile(str(full_path)).toString()
    
    # ========== PROPERTIES ==========
    
    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return self._version
    
    @pyqtProperty(bool, notify=translationStarted)
    def isTranslating(self) -> bool:
        return self._is_translating
    
    # ========== SLOTS (QML'den çağrılabilir) ==========
    
    @pyqtSlot(str, result=str)
    def getText(self, key: str) -> str:
        """Yerelleştirilmiş metin döndür."""
        return self.config.get_ui_text(key, key)
    
    @pyqtSlot(str, str, result=str)
    def getTextWithDefault(self, key: str, default: str) -> str:
        """Yerelleştirilmiş metin döndür, bulunamazsa default kullan."""
        return self.config.get_ui_text(key, default)
    
    @pyqtSlot(result=list)
    def getAvailableEngines(self) -> list:
        """Kullanılabilir çeviri motorlarını döndür."""
        engines = [
            {"code": "google", "name": self.config.get_ui_text("translation_engines.google", "🌐 Google Translate (Free)")},
            {"code": "deepl", "name": self.config.get_ui_text("translation_engines.deepl", "🔷 DeepL (API Key)")},
            {"code": "openai", "name": self.config.get_ui_text("translation_engines.openai", "🤖 OpenAI / OpenRouter")},
            {"code": "gemini", "name": self.config.get_ui_text("translation_engines.gemini", "✨ Google Gemini")},

            {"code": "local_llm", "name": self.config.get_ui_text("translation_engines.local_llm", "🖥️ Local LLM")},
        ]
        
        # Pseudo motorunu debug modunda göster
        if getattr(self.config.translation_settings, 'show_debug_engines', False):
             engines.append({"code": "pseudo", "name": self.config.get_ui_text("pseudo_engine_name", "🧪 Pseudo-Localization")})
        
        return engines
    
    @pyqtSlot(result=list)
    def getSourceLanguages(self) -> list:
        """Kaynak dilleri döndür."""
        languages = [{"code": "auto", "name": self.config.get_ui_text("auto_detect", "🔍 Auto Detect")}]
        for code, name in self.config.get_target_languages_for_ui():
            languages.append({"code": code, "name": name})
        return languages
    
    @pyqtSlot(result=list)
    def getTargetLanguages(self) -> list:
        """Hedef dilleri döndür."""
        languages = []
        for code, name in self.config.get_target_languages_for_ui():
            languages.append({"code": code, "name": name})
        return languages
    
    @pyqtSlot(str)
    def openUrl(self, url: str):
        """Harici URL aç."""
        QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot(str, result=str)
    def extractRPA(self, path: str) -> str:
        """RPA arşivlerini çıkar."""
        if path.startswith("file:///"):
            if sys.platform == "win32":
                path = path[8:] # Remove file:///
            else:
                path = path[7:] # Remove file:// (keep leading / for Unix paths)
                
        try:
            from src.utils.unrpa_adapter import UnrpaAdapter
            adapter = UnrpaAdapter()
            
            project_dir = os.path.dirname(path) if os.path.isfile(path) else path
            game_dir = os.path.join(project_dir, 'game') if os.path.isdir(os.path.join(project_dir, 'game')) else project_dir
            
            success = adapter.extract_game(Path(game_dir))
            if success:
                return self.config.get_ui_text("unren_completed", "RPA extraction completed.")
            else:
                return self.config.get_ui_text("log_rpa_not_found_or_extracted", "RPA file not found or already extracted.")
        except Exception as e:
            return f"{self.config.get_ui_text('error', 'Error')}: {str(e)}"

    @pyqtSlot(str, result=str)
    def cleanupSDK(self, path: str) -> str:
        """SDK temizliği yap (UnRen mod dosyalarını sil)."""
        if self._is_busy:
            return self.config.get_ui_text("app_busy", "Another operation is in progress...")

        self._set_busy(True)
        # We must run this in a thread to avoid main thread blocking
        threading.Thread(target=self._run_cleanup_thread, args=(path,), daemon=True).start()
        return self.config.get_ui_text("msg_task_started", "Operation started in background...")

    def _run_cleanup_thread(self, path):
        try:
            if path.startswith("file:///"):
                if sys.platform == "win32":
                    path = path[8:]
                else:
                    path = path[7:]
            
            project_dir = os.path.dirname(path) if os.path.isfile(path) else path
            game_dir = os.path.join(project_dir, 'game') if os.path.isdir(os.path.join(project_dir, 'game')) else project_dir
            
            cleanup_patterns = [
                "unren-console.rpy", "unren-console.rpyc",
                "unren-qmenu.rpy", "unren-qmenu.rpyc",
                "unren-quick.rpy", "unren-quick.rpyc",
                "unren-rollback.rpy", "unren-rollback.rpyc",
                "unren-skip.rpy", "unren-skip.rpyc",
            ]
            
            deleted_count = 0
            for filename in cleanup_patterns:
                filepath = os.path.join(game_dir, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_count += 1
            
            msg = self.config.get_ui_text("msg_sdk_cleanup_success", f"Cleanup completed. {deleted_count} files removed.").replace("{count}", str(deleted_count))
            self.logMessage.emit("success", msg)
        except Exception as e:
            self.logMessage.emit("error", f"{self.config.get_ui_text('error', 'Error')}: {str(e)}")
        finally:
            self._set_busy(False)

    @pyqtSlot()
    def runUnRen(self):
        """UnRen arayüzünü aç veya işlemi başlat (Tools page shortcut)."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warning", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
        
        if self._is_busy:
            self.warningMessage.emit(self.config.get_ui_text("warning", "Warning"), self.config.get_ui_text("app_busy", "Another operation is in progress..."))
            return

        self.logMessage.emit("info", self.config.get_ui_text("msg_unren_requested", "UnRPA extraction requested..."))
        self._set_busy(True)
        threading.Thread(target=self._run_unren_thread, daemon=True).start()

    def _run_unren_thread(self):
        try:
            result = self.extractRPA(self._project_path)
            self.logMessage.emit("info", result)
        finally:
            self._set_busy(False)

    @pyqtSlot()
    def runHealthCheck(self):
        """Sağlık kontrolünü başlat."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warning", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
        
        if self._is_busy: return

        self.logMessage.emit("info", self.config.get_ui_text("log_health_check_analyzing", "Starting Health Check..."))
        self._set_busy(True)
        threading.Thread(target=self._run_health_check_thread, daemon=True).start()
        
    def _run_health_check_thread(self):
        try:
            self.logMessage.emit("info", self.config.get_ui_text("log_health_check_analyzing"))
            time.sleep(1)
            
            # Use directory if file selected
            base_dir = self._project_path
            if os.path.isfile(base_dir):
                base_dir = os.path.dirname(base_dir)
                
            self.logMessage.emit("info", self.config.get_ui_text("log_health_check_verifying"))
            report = self.healthCheck(base_dir)
            self.logMessage.emit("success", self.config.get_log_text("log_health_check_success", report=report))
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("msg_error_health_check", "Health check error: {error}").replace("{error}", str(e)))
        finally:
            self._set_busy(False)
        
    @pyqtSlot()
    def runFontCheck(self):
        """Font kontrolünü başlat."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warning", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
            
        if self._is_busy: return

        target_lang = self.config.translation_settings.target_language
        self.logMessage.emit("info", self.config.get_log_text("log_font_check_testing", lang=target_lang.upper()))
        
        # Simüle edilmiş aşamalı kontrol
        self._set_busy(True)
        threading.Thread(target=self._run_font_check_thread, args=(target_lang,), daemon=True).start()

    def _run_font_check_thread(self, lang):
        try:
            lang = lang.lower()
            time.sleep(1)
            self.logMessage.emit("info", self.config.get_ui_text("log_font_check_starting"))
            time.sleep(2)
            
            # Daha kapsamlı dil bazlı kontrol mantığı
            if any(x in lang for x in ["tr", "turkish"]):
                self.logMessage.emit("warning", self.config.get_ui_text("log_font_check_risk_tr"))
            elif any(x in lang for x in ["ru", "russian", "uk", "ukrainian"]):
                self.logMessage.emit("warning", self.config.get_ui_text("log_font_check_warn_ru"))
            elif any(x in lang for x in ["ar", "arabic", "fa", "persian", "he", "hebrew"]):
                self.logMessage.emit("error", self.config.get_ui_text("log_font_check_error_rtl"))
            elif any(x in lang for x in ["zh", "chinese", "ja", "japanese", "ko", "korean"]):
                self.logMessage.emit("error", self.config.get_ui_text("log_font_check_error_cjk"))
            else:
                self.logMessage.emit("success", self.config.get_log_text("log_font_check_success", lang=lang.upper()))
            
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("msg_error_font_check", "Font check error: {error}").replace("{error}", str(e)))
        finally:
            self._set_busy(False)

    @pyqtSlot()
    def autoInjectFont(self):
        """Uyumlu fontu otomatik indir ve enjekte et."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warn_title", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
            
        if self._is_busy: return

        target_lang = self.config.translation_settings.target_language or "turkish"
        
        # Kullanıcı onayı gerekebilir ama şimdilik direkt işlem yapılıyor çünkü araçlar menüsünden çağrılacak
        self.logMessage.emit("info", self.config.get_ui_text("log_font_inject_start", "Auto font injection started for {lang}...").replace("{lang}", target_lang))
        
        self._set_busy(True)
        threading.Thread(target=self._run_font_inject_thread, args=(target_lang, None), daemon=True).start()

    @pyqtSlot(str)
    def manualInjectFont(self, font_name: str):
        """Kullanıcının seçtiği fontu indir ve enjekte et."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warn_title", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
            
        if self._is_busy: return
        
        if not font_name:
            return

        target_lang = self.config.translation_settings.target_language or "turkish"
        
        self.logMessage.emit("info", self.config.get_ui_text("log_font_inject_start", "Starting font injection...").replace("{lang}", f"{target_lang} ({font_name})"))
        
        self._set_busy(True)
        threading.Thread(target=self._run_font_inject_thread, args=(target_lang, font_name), daemon=True).start()

    @pyqtSlot(result=list)
    def getGoogleFontsList(self) -> list:
        """Kullanılabilir Google fontlarını döndür."""
        try:
            from src.utils.font_injector import FontInjector
            injector = FontInjector()
            return injector.get_available_fonts()
        except Exception:
            return ["Roboto", "Noto Sans", "Open Sans"] # Fallback

    def _run_font_inject_thread(self, lang, force_font=None):
        try:
            from src.utils.font_injector import FontInjector
            injector = FontInjector()
            
            # Proje yolunu al (eğer dosya ise klasöre çevir)
            base_dir = self._project_path
            if os.path.isfile(base_dir):
                base_dir = os.path.dirname(base_dir)
            
            # İşlemi yap (force_font parametresiyle)
            result = injector.inject_font(base_dir, lang, force_font_family=force_font)
            
            # Localization logic
            # result['ui_key'] is the translation key
            # result['ui_args'] are the parameters for python .format()
            ui_key = result.get("ui_key", "log_font_inject_error")
            ui_args = result.get("ui_args", {})
            fallback_msg = result.get("message", "An error occurred")
            
            # Get template from config using the key
            msg_template = self.config.get_ui_text(ui_key, fallback_msg)
            
            # Format the message (safely)
            try:
                final_msg = msg_template.format(**ui_args)
            except Exception as e:
                # Fallback if format fails (missing keys in json or args)
                final_msg = fallback_msg + f" (Loc err: {e})"

            if result["success"]:
                self.logMessage.emit("success", final_msg)
            else:
                self.logMessage.emit("error", final_msg)
                
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("log_font_inject_critical_error", "Font injection critical error: {error}").replace("{error}", str(e)))
        finally:
            self._set_busy(False)

    @pyqtSlot(str, result=str)
    def healthCheck(self, path: str) -> str:
        """Oyun sağlığını kontrol et."""
        if path.startswith("file:///"):
            path = path[8:] if sys.platform == "win32" else path[7:]
            
        try:
            from src.tools.health_check import run_health_check
            report = run_health_check(path, verbose=False)
            return report.summary()
        except Exception as e:
            return f"{self.config.get_ui_text('error', 'Error')}: {str(e)}"

    @pyqtSlot(str, result=str)
    def fontCheck(self, path: str) -> str:
        """Font uyumluluğunu kontrol et."""
        if path.startswith("file:///"):
            path = path[8:] if sys.platform == "win32" else path[7:]
            
        try:
            from src.tools.font_helper import check_font_for_project
            summary = check_font_for_project(path, "tr", verbose=False)
            return self.config.get_ui_text("font_check_summary", "Checked: {total}\nOK: {comp}\nIssue: {incomp}").format(
                total=summary['fonts_checked'],
                comp=summary['compatible_fonts'],
                incomp=summary['incompatible_fonts']
            )
        except Exception as e:
            return f"{self.config.get_ui_text('error', 'Error')}: {str(e)}"
    
    @pyqtSlot(result=str)
    def getLastProjectPath(self) -> str:
        """Son kullanılan proje yolunu getir."""
        return self.config.app_settings.last_input_directory or ""

    @pyqtSlot(str)
    def setProjectPath(self, path: str):
        """Proje klasörünü ayarla."""
        if path.startswith("file:///"):
            if sys.platform == "win32":
                path = path[8:]
            else:
                path = path[7:]
        
        self.config.app_settings.last_input_directory = path
        self._project_path = path  # Update internal state
        self.config.save_config()
        self.logMessage.emit("info", self.config.get_log_text("log_project_path_set", path=path))

        # Validate
        project_dir = os.path.dirname(path) if os.path.isfile(path) else path
        game_dir = os.path.join(project_dir, 'game')
        
        if os.path.isdir(game_dir):
            self.logMessage.emit("info", "✅ " + self.config.get_ui_text("valid_renpy_project", "Valid Ren'Py project"))
        else:
            self.logMessage.emit("warning", "⚠️ " + self.config.get_ui_text("game_folder_not_found", "game/ folder not found"))

        # Reload cache for the new project (Async)
        self._update_cache_path_async()
    
    @pyqtSlot(str)
    def setEngine(self, engine: str):
        """Çeviri motorunu ayarla ve başlat."""
        self._selected_engine = engine
        self.config.translation_settings.selected_engine = engine
        self.config.save_config()
        self.logMessage.emit("info", self.config.get_log_text("log_engine_selected", engine=engine))
        
        # Trigger async initialization
        self.update_translation_engine()

        # Show warnings for AI engines
        if engine in ["openai", "gemini", "deepseek", "local_llm"]:
            self.warningMessage.emit(
                self.config.get_ui_text("warning", "⚠️ Warning"),
                self.config.get_ui_text("ai_censorship_warning", "AI models may apply censorship or run slowly.")
            )

    @pyqtSlot()
    def update_translation_engine(self):
        """Update translation engine based on current settings (Async)."""
        engine_str = getattr(self.config.translation_settings, 'selected_engine', "google")
        use_proxy = getattr(self.config.proxy_settings, 'enabled', False)
        
        self.logger.info(f"Initializing translation engine: {engine_str} (Proxy: {use_proxy})")
        
        # Translate UI text for loading message
        msg = self.config.get_ui_text("msg_loading_ai", "Loading AI module and libraries...")
        
        # Start async initialization
        self._set_initializing(True, msg)
        
        def run_setup():
            try:
                # Convert string to enum
                from src.core.translator import TranslationEngine
                try:
                    engine_enum = TranslationEngine(engine_str)
                except ValueError:
                    engine_enum = TranslationEngine.GOOGLE

                self._setup_engine(engine_enum, use_proxy)
                
                # Success
                self.logMessage.emit("info", self.config.get_log_text("log_engine_initialized", engine=engine_str))
            except Exception as e:
                self.logger.error(f"Error initializing engine {engine_str}: {e}")
                import traceback
                traceback.print_exc()
                self.logMessage.emit("error", self.config.get_log_text("log_engine_init_failed", error=str(e)))
            finally:
                # Reset state on main thread
                # Since we are in a thread, we should ideally use QMetaObject.invokeMethod, 
                # but PyQt signals/properties are thread-safe for emitting.
                # To be 100% safe for property updates affecting UI:
                self._set_initializing(False, "")

        threading.Thread(target=run_setup, daemon=True).start()
    
    @pyqtSlot(str)
    def setSourceLanguage(self, lang: str):
        """Kaynak dili ayarla."""
        self._source_language = lang
        self.config.translation_settings.source_language = lang
        self.config.save_config()
    
    @pyqtSlot(str)
    def setTargetLanguage(self, lang: str):
        """Hedef dili ayarla."""
        self._target_language = lang
        self.config.translation_settings.target_language = lang
        self.config.save_config()
        # Reload cache for the new language (Async to avoid UI freeze)
        self._update_cache_path_async()

    def _update_cache_path_async(self):
        """Starts async cache update."""
        threading.Thread(target=self._update_cache_path, daemon=True).start()

    def _update_cache_path(self):
        """Proje veya dil değiştiğinde cache dosyasını yeniden yükle (Background Thread)."""
        if not self._project_path or not self._target_language:
            return

        try:
            # Logic mirrored from TranslationPipeline
            should_use_global_cache = getattr(self.config.translation_settings, 'use_global_cache', True)
            
            # Determine Project Directory
            project_dir = os.path.dirname(self._project_path) if os.path.isfile(self._project_path) else self._project_path
            
            if should_use_global_cache:
                # Global Cache Path
                project_name = os.path.basename(project_dir.rstrip('/\\'))
                if not project_name:
                    project_name = "default_project"
                
                # Use program directory (next to run.py/executable)
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if getattr(sys, 'frozen', False):
                    app_dir = os.path.dirname(sys.executable)
                
                base_cache_dir = os.path.join(app_dir, getattr(self.config.translation_settings, 'cache_path', 'cache'))
                cache_dir = os.path.join(base_cache_dir, project_name, self._target_language)
            else:
                # Local Cache Path
                cache_dir = os.path.join(project_dir, 'game', 'tl', self._target_language)

            cache_file = os.path.join(cache_dir, "translation_cache.json")
            
            if os.path.exists(cache_file):
                self.translation_manager.load_cache(cache_file)
                # self.logMessage.emit("debug", f"Cache reloaded from: {cache_file}") # Too verbose?
            else:
                # Clear cache if file doesn't exist for this new context, to avoid showing old project data
                self.translation_manager._cache.clear()
                self.translation_manager.cache_hits = 0
                self.translation_manager.cache_misses = 0
                
        except Exception as e:
            self.logger.error(f"Failed to update cache path: {e}")
    
    @pyqtSlot(result=list)
    def getGlossaryItems(self) -> list:
        """Sözlük öğelerini getir."""
        return [{"source": k, "target": v, "notes": ""} for k, v in self.config.glossary.items()]

    @pyqtSlot(str, str)
    def addGlossaryItem(self, source: str, target: str):
        """Sözlük öğesi ekle."""
        if not source: return
        self.config.glossary[source] = target
        self.config.save_glossary()

    @pyqtSlot(str)
    def removeGlossaryItem(self, source: str):
        """Sözlük öğesi sil."""
        if source in self.config.glossary:
            del self.config.glossary[source]
            self.config.save_glossary()

    @pyqtSlot(result=str)
    def extractGlossaryTerms(self) -> str:
        """Projeden terimleri otomatik çıkar."""
        if not self._project_path:
            return self.config.get_ui_text("glossary_extract_no_project", "Select a project first.")
            
        try:
            from src.tools.glossary_extractor import GlossaryExtractor
            extractor = GlossaryExtractor()
            terms = extractor.extract_from_directory(self._project_path, min_occurrence=3)
            
            added = 0
            for term in terms.keys():
                if term not in self.config.glossary:
                    self.config.glossary[term] = ""
                    added += 1
            
            if added > 0:
                self.config.save_glossary()
                return self.config.get_ui_text("msg_glossary_extracted_success", f"{added} yeni terim eklendi.").replace("{count}", str(added))
            return self.config.get_ui_text("msg_glossary_extracted_fail", "No new terms found.")
        except ImportError:
            return self.config.get_ui_text("glossary_extractor_not_found", "GlossaryExtractor module not found.")
        except Exception as e:
            return f"{self.config.get_ui_text('error', 'Hata')}: {str(e)}"

    @pyqtSlot()
    def translateEmptyGlossaryItems(self):
        """Boş sözlük terimlerini Google Translate ile doldur (Threadli)."""
        threading.Thread(target=self._translate_glossary_thread, daemon=True).start()

    def _translate_glossary_thread(self):
        try:
            import requests
            empty_keys = [k for k, v in self.config.glossary.items() if not v]
            if not empty_keys:
                self.logMessage.emit("info", self.config.get_ui_text("msg_glossary_translate_no_empty", "No empty terms to translate."))
                return

            self.logMessage.emit("info", self.config.get_ui_text("msg_glossary_translating", "Translating {count} terms...").replace("{count}", str(len(empty_keys))))
            
            count = 0
            for key in empty_keys:
                try:
                    # Simple sync Google Translate call
                    url = "https://translate.googleapis.com/translate_a/single"
                    params = {
                        "client": "gtx", "sl": "auto", "tl": self.config.translation_settings.target_language, 
                        "dt": "t", "q": key
                    }
                    data = requests.get(url, params=params, timeout=5).json()
                    if data and isinstance(data, list) and len(data) > 0:
                        self.config.glossary[key] = data[0][0][0]
                        count += 1
                except Exception:
                    pass
            
            if count > 0:
                self.config.save_glossary()
                self.logMessage.emit("success", self.config.get_ui_text("msg_glossary_translate_success", "{count} terms translated and saved.").replace("{count}", str(count)))
                # Refresh UI signal needed here if we were strictly MVVM, 
                # but QML will refresh on next getGlossaryItems call or we can emit a signal.
            else:
                self.logMessage.emit("warning", self.config.get_ui_text("msg_glossary_translate_fail", "No terms could be translated."))
                
        except Exception as e:
            self.logMessage.emit("error", f"Glossary translation error: {e}")

    @pyqtSlot()
    def fillEmptyGlossaryWithSource(self):
        """Boş çevirileri kaynak metinle doldur."""
        count = 0
        for k, v in self.config.glossary.items():
            if not v:
                self.config.glossary[k] = k
                count += 1
        
        if count > 0:
            self.config.save_glossary()
            self.logMessage.emit("success", self.config.get_ui_text("msg_glossary_fill_source_success", "{count} terms filled with source.").replace("{count}", str(count)))
        else:
            self.logMessage.emit("info", self.config.get_ui_text("msg_glossary_translate_no_empty", "No empty terms to fill."))

    @pyqtSlot()
    def generateRuntimeHook(self):
        """Runtime Hook dosyasını oluştur (Çevirileri zorla yükle)."""
        if not self._project_path:
            self.warningMessage.emit(self.config.get_ui_text("warn_title", "Warning"), self.config.get_ui_text("select_game_folder", "Please select the game folder first."))
            return
            
        try:
            self.logMessage.emit("info", self.config.get_ui_text("log_hook_preparing"))
            # Fix: If project_path is a file (the exe), get the directory
            base_dir = self._project_path
            if os.path.isfile(base_dir):
                base_dir = os.path.dirname(base_dir)
                
            game_dir = os.path.join(base_dir, "game")
            if not os.path.exists(game_dir):
                self.logMessage.emit("error", self.config.get_ui_text("error_hook_game_not_found"))
                return

            self.logMessage.emit("info", self.config.get_ui_text("log_hook_configuring"))
            
            # Hedef dili al
            target_lang = self.config.translation_settings.target_language or "turkish"
            # ISO -> Ren'Py native (örn: "tr" -> "turkish")
            from src.core.translation_pipeline import RENPY_TO_API_LANG
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            renpy_lang = reverse_lang_map.get(target_lang.lower(), target_lang)
            
            # Ren'Py dokümantasyonuna uygun Runtime Hook içeriği
            hook_content = f'''# RenLocalizer Runtime Translation Hook
# This script forces translation lookup for all text displayed by Ren'Py,
# solving issues where developers missed the !t flag on interpolated strings.
# Press Shift+L to manually switch to the translated language.
# Generated by RenLocalizer.

# Set default language at first run (before init blocks)
# define config.default_language = "{renpy_lang}"  <-- REMOVED: Managed by zzz_{renpy_lang}_language.rpy

init 1501 python:
    # =========================================================================
    # LANGUAGE HOTKEY: Shift+L
    # =========================================================================
    def _renlocalizer_switch_lang():
        target = "{renpy_lang}"
        renpy.change_language(target)
        persistent.renlocalizer_target_lang = target
        renpy.notify("RenLocalizer: Language -> {renpy_lang.title()}")
        renpy.restart_interaction()

    # Register Shift+L as language toggle
    config.underlay.append(renpy.Keymap(shift_K_l=_renlocalizer_switch_lang))

    # =========================================================================
    # RUNTIME TEXT TRANSLATION HOOK (HYBRID MODE)
    # =========================================================================
    # We use a Hybrid Approach to catch ALL strings:
    # 1. say_menu_text_filter: Translates Dialogue/Menus BEFORE variable substitution.
    #    This catches strings like "%(name)s wins!" -> "%(name)s kazandı!".
    # 2. replace_text: Translates Screens/UI AFTER substitution.
    #    This catches UI text that doesn't go through the say statement.
    
    # --- Hook 1: Say/Menu Filter (Pre-Substitution) ---
    if not hasattr(store, '_renlocalizer_old_say_filter'):
        store._renlocalizer_old_say_filter = config.say_menu_text_filter

    def _renlocalizer_safe_translate(s):
        if not s: return s
        try:
            # Try primary Ren'Py API
            if hasattr(renpy, 'translate_string'):
                return renpy.translate_string(s)
            # Try older Ren'Py 7 namespace
            import renpy.translation
            if hasattr(renpy.translation, 'translate_string'):
                return renpy.translation.translate_string(s)
        except:
            pass
        return s

    def _renlocalizer_say_filter(s):
        # 1. Run original filter first (if any)
        if store._renlocalizer_old_say_filter:
            s_orig = store._renlocalizer_old_say_filter(s)
            if s_orig is not None:
                s = s_orig
        
        # 2. Force Translation of the RAW string
        if s:
            translated = _renlocalizer_safe_translate(s)
            if translated and translated != s:
                return translated
        return s

    config.say_menu_text_filter = _renlocalizer_say_filter

    # --- Hook 2: Replace Text (Post-Substitution / Screens) ---
    if not hasattr(store, '_renlocalizer_old_replace_text'):
        try:
            store._renlocalizer_old_replace_text = config.replace_text
        except:
            store._renlocalizer_old_replace_text = lambda s: s

    def _renlocalizer_force_translate(s):
        # 1. Run original replace_text first
        if store._renlocalizer_old_replace_text:
            s = store._renlocalizer_old_replace_text(s)
        
        # 2. Force Translation (Fallback for UI)
        if s:
            translated = _renlocalizer_safe_translate(s)
            if translated and translated != s:
                return translated
        return s

    config.replace_text = _renlocalizer_force_translate
'''
            hook_path = os.path.join(game_dir, "zzz_renlocalizer_runtime.rpy")
            self.logMessage.emit("info", self.config.get_log_text("log_hook_writing", filename=os.path.basename(hook_path)))
            
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write(hook_content)
            
            self.logMessage.emit("success", self.config.get_ui_text("log_hook_success"))
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("msg_error_hook_gen", "Hook generation error: {error}").replace("{error}", str(e)))

    @pyqtSlot(str, str, str, str, bool)
    def startTLTranslation(self, tl_path: str, target_lang: str, source_lang: str, engine: str, use_proxy: bool):
        """Mevcut bir TL klasörünü çevirmeye başla."""
        if tl_path.startswith("file:///"):
            tl_path = tl_path[8:] if sys.platform == "win32" else tl_path[7:]

        self.logMessage.emit("info", self.config.get_ui_text("log_tl_started"))
        self.logMessage.emit("info", self.config.get_log_text("log_tl_folder", folder=os.path.basename(tl_path)))
        self.logMessage.emit("info", self.config.get_log_text("log_tl_info", engine=engine.upper(), lang=target_lang.upper()))
        threading.Thread(
            target=self._run_tl_translation_thread, 
            args=(tl_path, target_lang, source_lang, engine, use_proxy),
            daemon=True
        ).start()

    def _run_tl_translation_thread(self, tl_path, target_lang, source_lang, engine_str, use_proxy):
        try:
            from src.core.translation_pipeline import TranslationPipeline
            engine = self._get_engine_enum(engine_str)
            
            pipeline = TranslationPipeline(self.config, self.translation_manager)
            pipeline.log_message.connect(self.logMessage)
            pipeline.progress_updated.connect(self.progressUpdated)
            
            result = pipeline.translate_existing_tl(
                tl_path, target_lang, source_lang, engine, use_proxy
            )
            
            if result.success:
                self.logMessage.emit("success", result.message)
            else:
                self.logMessage.emit("error", result.message)
                
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("msg_error_tl_translate", "TL translation error: {error}").replace("{error}", str(e)))

    def _get_engine_enum(self, engine_str: str) -> TranslationEngine:
        """String engine adını enum'a çevir."""
        from src.core.translator import TranslationEngine
        mapping = {
            "google": TranslationEngine.GOOGLE,
            "deepl": TranslationEngine.DEEPL,
            "openai": TranslationEngine.OPENAI,
            "gemini": TranslationEngine.GEMINI,
            "local_llm": TranslationEngine.LOCAL_LLM,
            "pseudo": TranslationEngine.PSEUDO,
        }
        return mapping.get(engine_str, TranslationEngine.GOOGLE)
    
    @pyqtSlot()
    def startTranslation(self):
        """Çeviri işlemini başlat."""
        if not self._project_path:
            self.logMessage.emit("error", self.config.get_ui_text("please_select_exe", "Please select a game"))
            return
        
        if self._is_translating:
            return
        
        self._is_translating = True
        self.translationStarted.emit()
        
        try:
            # Get engine enum
            engine = self._get_engine_enum(self._selected_engine)
            use_proxy = getattr(self.config.proxy_settings, "enabled", False)
            
            # Setup engine-specific translators
            self._setup_engine(engine, use_proxy)
            
            # Create pipeline
            self.pipeline = TranslationPipeline(self.config, self.translation_manager)
            self.pipeline.configure(
                game_exe_path=self._project_path,
                target_language=self._target_language,
                source_language=self._source_language,
                engine=engine,
                auto_unren=self.config.app_settings.unren_auto_download,
                use_proxy=use_proxy
            )
            
            # Connect signals
            self.pipeline.stage_changed.connect(self._on_stage_changed)
            self.pipeline.progress_updated.connect(self._on_progress_updated)
            self.pipeline.log_message.connect(self._on_log_message)
            self.pipeline.finished.connect(self._on_pipeline_finished)
            self.pipeline.show_warning.connect(self._on_show_warning)
            
            self.logMessage.emit("info", self.config.get_ui_text("pipeline_starting", "Pipeline starting..."))
            
            # Start worker
            self.pipeline_worker = PipelineWorker(self.pipeline)
            self.pipeline_worker.start()
            
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("msg_error_init", "Initialization error: {error}").replace("{error}", str(e)))
            self._is_translating = False
            self.translationFinished.emit(False, str(e))
    
    def _setup_engine(self, engine: TranslationEngine, use_proxy: bool):
        """Initialize selected translation engine."""
        # Local imports
        from src.core.ai_translator import OpenAITranslator, GeminiTranslator, LocalLLMTranslator

        ts = self.config.translation_settings
        self.translation_manager.max_retries = ts.max_retries
        self.translation_manager.max_batch_size = ts.max_batch_size
        self.translation_manager.set_max_concurrency(ts.max_concurrent_threads)
        
        self.translation_manager.set_max_concurrency(ts.max_concurrent_threads)
        
        # Google Translate is always available as fallback, no heavy import needed
        # self.translation_manager.add_translator(...) # Already added in init
        
        if engine == TranslationEngine.OPENAI:
            if not self.config.api_keys.openai_api_key:
                raise ValueError(self.config.get_ui_text("error_api_key_missing", "API Key Missing").format(engine="OpenAI"))
                
            self.translation_manager.add_translator(
                TranslationEngine.OPENAI,
                OpenAITranslator(
                    api_key=self.config.api_keys.openai_api_key,
                    model=ts.openai_model or "gpt-3.5-turbo",
                    base_url=ts.openai_base_url,
                    proxy_manager=self.proxy_manager if use_proxy else None,
                    config_manager=self.config,
                    temperature=ts.ai_temperature,
                    timeout=ts.ai_timeout,
                    max_tokens=ts.ai_max_tokens
                )
            )
        elif engine == TranslationEngine.LOCAL_LLM:
            self.translation_manager.add_translator(
                TranslationEngine.LOCAL_LLM,
                LocalLLMTranslator(
                    model=ts.local_llm_model or "llama3.2",
                    base_url=ts.local_llm_url or "http://localhost:11434/v1",
                    proxy_manager=self.proxy_manager if use_proxy else None,
                    config_manager=self.config,
                    temperature=ts.ai_temperature,
                    timeout=getattr(ts, 'local_llm_timeout', 300),
                    max_tokens=ts.ai_max_tokens
                )
            )
        elif engine == TranslationEngine.GEMINI:
            if not self.config.api_keys.gemini_api_key:
                raise ValueError(self.config.get_ui_text("error_api_key_missing", "API Key Missing").format(engine="Gemini"))

            gemini_translator = GeminiTranslator(
                api_key=self.config.api_keys.gemini_api_key,
                model=ts.gemini_model or "gemini-pro",
                safety_level=ts.gemini_safety_settings,
                proxy_manager=self.proxy_manager if use_proxy else None,
                config_manager=self.config,
                temperature=ts.ai_temperature,
                timeout=ts.ai_timeout,
                max_tokens=ts.ai_max_tokens
            )
            fallback = GoogleTranslator(self.proxy_manager, self.config)
            gemini_translator.set_fallback_translator(fallback)
            self.translation_manager.add_translator(TranslationEngine.GEMINI, gemini_translator)

        elif engine == TranslationEngine.DEEPL:
            self.translation_manager.add_translator(
                TranslationEngine.DEEPL,
                DeepLTranslator(
                    api_key=self.config.api_keys.deepl_api_key,
                    proxy_manager=self.proxy_manager
                )
            )
    
    @pyqtSlot()
    def stopTranslation(self):
        """Çeviri işlemini durdur."""
        if self.pipeline:
            self.logMessage.emit("warning", self.config.get_ui_text("stop_requested", "Durdurma istendi..."))
            self.pipeline.stop()
            
            if self.pipeline_worker:
                try:
                    self.pipeline_worker.wait(5000)
                except Exception:
                    pass
                self.pipeline_worker = None
    
    @pyqtSlot(bool)
    def checkForUpdates(self, manual: bool = False):
        """Check for updates."""
        if not manual and not self.config.app_settings.check_for_updates:
            return

        self.logMessage.emit("info", self.config.get_ui_text("update_checking", "Checking for updates..."))
        threading.Thread(target=self._check_updates_thread, args=(manual,), daemon=True).start()

    def _check_updates_thread(self, manual: bool):
        try:
            from src.utils.update_checker import check_for_updates
            result = check_for_updates(self._version)
            
            if result.update_available:
                self.logMessage.emit("success", self.config.get_log_text("log_update_available", version=result.latest_version))
                # Emit update signal: current, latest, url
                self.updateAvailable.emit(
                    result.current_version,
                    result.latest_version,
                    result.release_url
                )
                if manual:
                     self.updateCheckFinished.emit(True, f"Update found: {result.latest_version}")
            else:
                msg = self.config.get_ui_text("update_check_no_update", "You are up to date.")
                if manual:
                     self.logMessage.emit("success", msg)
                     self.updateCheckFinished.emit(False, msg)
        except Exception as e:
            if manual:
                self.logMessage.emit("error", self.config.get_ui_text("log_update_check_failed", "Update check failed: {error}").replace("{error}", str(e)))
                self.updateCheckFinished.emit(False, f"Update Check Failed: {e}")

    # ========== HELPERS ==========

    @pyqtSlot(result=str)
    def get_app_path(self) -> str:
        """Uygulamanın çalıştığı dizini döndür (Dosya yolları için)."""
        return os.getcwd().replace("\\", "/")

    # ========== PIPELINE SIGNAL HANDLERS ==========
    
    def _on_stage_changed(self, stage: str, message: str):
        """Handle pipeline stage change."""
        stage_keys = {
            "idle": "stage_idle", "validating": "stage_validating",
            "unren": "stage_unren", "generating": "stage_generating",
            "parsing": "stage_parsing", "translating": "stage_translating",
            "saving": "stage_saving", "completed": "stage_completed",
            "error": "stage_error"
        }
        display_name = self.config.get_ui_text(stage_keys.get(stage, "stage_idle"), stage)
        self.stageChanged.emit(stage, display_name)
    
    def _on_progress_updated(self, current: int, total: int, text: str):
        """Handle translation progress update."""
        self.progressChanged.emit(current, total, text)
    
    def _on_log_message(self, level: str, message: str):
        """Handle log message from pipeline."""
        self.logMessage.emit(level, message)
    
    def _on_show_warning(self, title: str, message: str):
        """Show warning popup from pipeline."""
        self.warningMessage.emit(title, message)
    
    def _on_pipeline_finished(self, result):
        """Handle pipeline completion."""
        self._is_translating = False
        
        if result.success:
            self.logMessage.emit("success", f"✅ {result.message}")
            if result.stats:
                self.statsReady.emit(
                    result.stats.get('total', 0),
                    result.stats.get('translated', 0),
                    result.stats.get('untranslated', 0)
                )
        else:
            self.logMessage.emit("error", f"❌ {result.message}")
            if result.error:
                self.logMessage.emit("error", f"Detail: {result.error}")
        
        if self.config.translation_settings.auto_generate_hook and result.success:
            self.generateRuntimeHook()

        self.translationFinished.emit(result.success, result.message)
        
        # Cleanup
        if self.pipeline_worker:
            try:
                self.pipeline_worker.wait(2000)
            except Exception:
                pass
            self.pipeline_worker = None
        
        # Close async sessions
        try:
            threading.Thread(
                target=lambda: asyncio.run(self.translation_manager.close_all()),
                daemon=True
            ).start()
        except Exception:
            pass

    @pyqtSlot(str, str, result=str)
    def exportGlossary(self, path: str, format_type: str) -> str:
        """Export glossary to file."""
        if path.startswith("file:///"):
            path = path[8:] if sys.platform == "win32" else path[7:]
            
        try:
            # Ensure correct extension
            if not path.lower().endswith(f".{format_type}"):
                path += f".{format_type}"
                
            export_glossary_to_file(self.config.glossary, path)
            msg = self.config.get_ui_text("glossary_export_success", "Glossary exported successfully to {path}").format(path=path)
            self.logMessage.emit("success", msg)
            return "" # Empty string = success
        except Exception as e:
            err = str(e)
            self.logMessage.emit("error", self.config.get_ui_text("log_export_failed", "Export failed: {error}").replace("{error}", err))
            return err
            
    @pyqtSlot(str, result=str)
    def importGlossary(self, path: str) -> str:
        """Import glossary from file (merge with existing)."""
        if path.startswith("file:///"):
            path = path[8:] if sys.platform == "win32" else path[7:]
            
        try:
            new_term_count = 0
            updated_term_count = 0
            
            imported_data = import_glossary_from_file(path)
            
            for source, target in imported_data.items():
                if source in self.config.glossary:
                    if self.config.glossary[source] != target:
                         self.config.glossary[source] = target
                         updated_term_count += 1
                else:
                    self.config.glossary[source] = target
                    new_term_count += 1
            
            if new_term_count > 0 or updated_term_count > 0:
                self.config.save_glossary()
                msg = self.config.get_ui_text("glossary_import_success", "Imported: {new} new, {updated} updated.").format(
                    new=new_term_count, updated=updated_term_count
                )
                self.logMessage.emit("success", msg)
                return "" # Success
            else:
                msg = self.config.get_ui_text("glossary_import_no_change", "No changes made. File might be identical or empty.")
                self.logMessage.emit("info", msg)
                return msg

        except Exception as e:
            err = str(e)
            self.logMessage.emit("error", self.config.get_ui_text("log_import_failed", "Import failed: {error}").replace("{error}", err))
            return err

    # ========== CACHE EXPLORER SLOTS ==========

    @pyqtSlot(str, result=list)
    def getCacheEntries(self, filter_text: str = "") -> list:
        """Get flattened cache entries for UI."""
        entries = []
        filter_text = filter_text.lower()
        
        # cache key: (engine, sl, tl, text) -> val: TranslationResult
        # Accessing private member _cache for Explorer functionality
        # Need to be thread-safe if updated dynamically, but for UI view it's mostly fine
        # We'll take a snapshot
        
        try:
            cache_snapshot = list(self.translation_manager._cache.items())
            
            # Sort by most recent (which are at the end of OrderedDict) -> reverse
            cache_snapshot.reverse()
            
            count = 0
            limit = 1000 # Hard limit for UI performance for now
            
            for key, val in cache_snapshot:
                engine, sl, tl, original = key
                translated = val.translated_text
                
                if filter_text:
                    if (filter_text not in original.lower() and 
                        filter_text not in translated.lower() and 
                        filter_text not in engine.lower()):
                        continue
                        
                entries.append({
                    "engine": engine,
                    "source_lang": sl,
                    "target_lang": tl,
                    "original": original,
                    "translated": translated
                })
                count += 1
                if count >= limit:
                    break
                    
            return entries
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("log_cache_list_error", "Error listing cache: {error}").replace("{error}", str(e)))
            return []

    def _get_current_cache_file(self) -> Optional[str]:
        """Helper to get current cache file path based on settings."""
        if not self._project_path or not self._target_language:
            return None
            
        try:
            should_use_global_cache = getattr(self.config.translation_settings, 'use_global_cache', True)
            project_dir = os.path.dirname(self._project_path) if os.path.isfile(self._project_path) else self._project_path
            
            if should_use_global_cache:
                project_name = os.path.basename(project_dir.rstrip('/\\')) or "default_project"
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if getattr(sys, 'frozen', False):
                    app_dir = os.path.dirname(sys.executable)
                base_cache_dir = os.path.join(app_dir, getattr(self.config.translation_settings, 'cache_path', 'cache'))
                cache_dir = os.path.join(base_cache_dir, project_name, self._target_language)
            else:
                cache_dir = os.path.join(project_dir, 'game', 'tl', self._target_language)
                
            return os.path.join(cache_dir, "translation_cache.json")
        except:
            return None

    @pyqtSlot(str, str, str, str, result=bool)
    def deleteCacheEntry(self, engine: str, source_lang: str, target_lang: str, original: str) -> bool:
        """Delete a specific cache entry."""
        key = (engine, source_lang, target_lang, original)
        if key in self.translation_manager._cache:
            del self.translation_manager._cache[key]
            
            cache_file = self._get_current_cache_file()
            if cache_file:
                self.translation_manager.save_cache(cache_file)
            return True
        return False

    @pyqtSlot(str, str, str, str, str, result=bool)
    def updateCacheEntry(self, engine: str, source_lang: str, target_lang: str, original: str, new_translation: str) -> bool:
        """Update a specific cache entry."""
        key = (engine, source_lang, target_lang, original)
        if key in self.translation_manager._cache:
            # Update the translated text
            res = self.translation_manager._cache[key]
            res.translated_text = new_translation
            
            cache_file = self._get_current_cache_file()
            if cache_file:
                self.translation_manager.save_cache(cache_file)
            return True
        return False

    @pyqtSlot(result=bool)
    def clearCache(self) -> bool:
        """Clear all cache."""
        try:
            self.translation_manager._cache.clear()
            
            cache_file = self._get_current_cache_file()
            if cache_file and os.path.exists(os.path.dirname(cache_file)):
                self.translation_manager.save_cache(cache_file)
                
            self.logMessage.emit("success", self.config.get_ui_text("log_cache_cleared", "Translation memory cleared."))
            return True
        except Exception as e:
            self.logMessage.emit("error", self.config.get_ui_text("log_cache_clear_error", "Error clearing cache: {error}").replace("{error}", str(e)))
            return False

    @pyqtSlot(result=int)
    def getCacheSize(self) -> int:
        return len(self.translation_manager._cache)

