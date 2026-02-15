# -*- coding: utf-8 -*-
"""
Integrated Translation Pipeline
================================

Tek tıkla çeviri: EXE → UnRen → Translate → Çeviri → Kaydet

Bu modül tüm çeviri sürecini entegre bir pipeline olarak yönetir.
"""

import os
import sys
import logging
import asyncio
import re
import time
from typing import Optional, List, Dict, Callable, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil  # En tepeye ekleyin
from src.utils.encoding import normalize_to_utf8_sig, read_text_safely, save_text_safely
from src.core.runtime_hook_template import RUNTIME_HOOK_TEMPLATE

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from src.utils.config import ConfigManager
# sdk_finder removed
from src.core.tl_parser import TLParser, TranslationFile, TranslationEntry, get_translation_stats
from src.core.parser import RenPyParser
from src.core.translator import (
    TranslationManager,
    TranslationRequest,
    TranslationEngine,
    GoogleTranslator,
    DeepLTranslator,
)
from src.core.ai_translator import OpenAITranslator, GeminiTranslator, LocalLLMTranslator
from src.core.output_formatter import RenPyOutputFormatter
from src.core.diagnostics import DiagnosticReport


# Ren'Py dil kodları -> API dil kodları dönüşümü
# Merkezi config'den dinamik olarak oluşturulur
def _get_renpy_to_api_lang():
    """Get Ren'Py to API language mapping from centralized config."""
    try:
        from src.utils.config import ConfigManager
        config = ConfigManager()
        return config.get_renpy_to_api_map()
    except Exception:
        # Fallback for edge cases where config is not available
        return {
            "turkish": "tr", "english": "en", "german": "de", "french": "fr",
            "spanish": "es", "italian": "it", "portuguese": "pt", "russian": "ru",
            "polish": "pl", "dutch": "nl", "japanese": "ja", "korean": "ko",
            "chinese": "zh", "chinese_s": "zh-CN", "chinese_t": "zh-TW",
            "thai": "th", "vietnamese": "vi", "indonesian": "id", "malay": "ms",
            "hindi": "hi", "persian": "fa", "arabic": "ar", "czech": "cs",
            "danish": "da", "finnish": "fi", "greek": "el", "hebrew": "he",
            "hungarian": "hu", "norwegian": "no", "romanian": "ro", "swedish": "sv",
            "ukrainian": "uk", "bulgarian": "bg", "catalan": "ca", "croatian": "hr",
            "slovak": "sk", "slovenian": "sl", "serbian": "sr",
        }

# Initialize at module load - used throughout the pipeline
RENPY_TO_API_LANG = _get_renpy_to_api_lang()


class PipelineStage(Enum):
    """Pipeline aşamaları"""
    IDLE = "idle"
    VALIDATING = "validating"
    UNRPA = "unrpa"
    GENERATING = "generating"
    PARSING = "parsing"
    TRANSLATING = "translating"
    SAVING = "saving"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PipelineResult:
    """Pipeline sonucu"""
    success: bool
    message: str
    stage: PipelineStage
    stats: Optional[Dict] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class TranslationPipeline(QObject):
    """
    Entegre çeviri pipeline'ı.
    
    Akış:
    1. Proje doğrulama
    2. UnRen (gerekirse)
    3. Translate komutu ile tl/<dil>/ oluşturma
    4. tl/<dil>/*.rpy dosyalarını parse etme
    5. old "..." metinlerini çevirme
    6. new "..." alanlarına yazma ve kaydetme
    """

    def _find_rpymc_files(self, directory: str) -> list:
        """Klasörde ve alt klasörlerinde .rpymc dosyalarını bulur."""
        rpymc_files = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpymc'):
                    rpymc_files.append(os.path.join(root, f))
        return rpymc_files

    def _extract_strings_from_rpymc_ast(self, ast_root) -> list:
        """
        AST'den stringleri çıkarır (İteratif & Güvenli).
        Recursion yerine Stack kullanarak derin nested yapılarda çökme riskini (StackOverflow) önler.
        """
        strings = set()
        # Set kullanarak O(1) lookup performansı (Red Flag 4 Fix)
        PRIORITY_KEYS = {'text', 'content', 'value', 'caption', 'label', 'description', 'message', 'body'}
        
        # Iterative Stack Approach
        stack = [ast_root]
        
        # Safety: Aşırı derin döngüler veya milyarlarca node ihtimaline karşı bir sayaç eklenebilir
        # ancak iteratif yığın Pythonda bellek bitene kadar çökmez (Recursion limitine takılmaz).
        
        while stack:
            node = stack.pop()
            
            if isinstance(node, str):
                s = node.strip()
                # 2 karakterden uzun ve sadece boşluk olmayan metinleri al
                if len(s) > 2 and not s.isspace():
                    strings.add(s)
            
            elif isinstance(node, (list, tuple)):
                # Listeyi stack'e ekle (Ters sıra ile eklersek orijinal sırayla işleriz ama Set için sıra önemsiz)
                stack.extend(node)
                
            elif isinstance(node, dict):
                # Dict değerlerini stack'e at
                for key, value in node.items():
                    # Key 'text' gibi öncelikli bir alansa, yine de stack'e atıp işliyoruz.
                    stack.append(value)
                    
            elif hasattr(node, '__dict__'):
                # Nesne özelliklerini gez
                for value in vars(node).values():
                    stack.append(value)

        result = list(strings)
        if result:
            self.log_message.emit('debug', f".rpymc extracted {len(result)} unique strings.")
        return result
    
    # Signals
    stage_changed = pyqtSignal(str, str)  # stage, message
    progress_updated = pyqtSignal(int, int, str)  # current, total, text
    log_message = pyqtSignal(str, str)  # level, message
    finished = pyqtSignal(object)  # PipelineResult
    show_warning = pyqtSignal(str, str)  # title, message - for popup warnings
    
    def __init__(
        self,
        config: ConfigManager,
        translation_manager: TranslationManager,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        self.config = config
        self.translation_manager = translation_manager
        self.tl_parser = TLParser()
        self.diagnostic_report = DiagnosticReport()
        # Use a less alarming name for error log, e.g. pipeline_debug.log
        self.error_log_path = Path("pipeline_debug.log")
        self.normalize_count = 0
        
        # State
        self.current_stage = PipelineStage.IDLE
        self.should_stop = False
        self.is_running = False
        
        # Log Buffering (v2.5.3 Optimization)
        self._log_queue = []
        self._last_log_time = 0
        self._log_throttle_interval = 0.08  # ~12 FPS limit for logs
        
        # Settings (default values; overridden via configure)
        self.game_exe_path: Optional[str] = None
        self.project_path: Optional[str] = None
        self.target_language: str = "turkish"
        self.source_language: str = "en"
        self.engine: TranslationEngine = TranslationEngine.GOOGLE
        self.auto_unren: bool = True # Legacy name, means auto extraction
        self.use_proxy: bool = False

    def emit_log(self, level: str, message: str):
        """
        Send log message to UI with throttling for better performance.
        High-priority logs (error, warning) are sent immediately.
        """
        if level in ('error', 'warning'):
            self.log_message.emit(level, message)
            return

        current_time = time.time()
        if current_time - self._last_log_time > self._log_throttle_interval:
            self.log_message.emit(level, message)
            self._last_log_time = current_time

    def _log_error(self, message: str):
        """Persist errors for later inspection (not shown to user as 'fatal')."""
        # Only log if debug mode is enabled or config allows debug logs
        if getattr(self.config, 'debug_mode', False) or getattr(self, 'always_log_errors', False):
            try:
                with self.error_log_path.open("a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception:
                self.logger.debug(f"Error log yazılamadı: {message}")
        # Also record diagnostic-level errors
        try:
            self.diagnostic_report.mark_skipped('pipeline', f'error:{message}')
        except Exception:
            pass
    
    def configure(
        self,
        game_exe_path: str,
        target_language: str,
        source_language: str = "en",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        auto_unren: bool = True,
        use_proxy: bool = False,
        include_deep_scan: bool = False,
        include_rpyc: bool = False
    ):
        """Pipeline ayarlarını yapılandır.
        
        Args:
            game_exe_path: Can be either:
                - Path to game .exe file (GUI mode)
                - Path to game directory (CLI mode)
        """
        self.include_deep_scan = include_deep_scan
        self.include_rpyc = include_rpyc
        self.game_exe_path = game_exe_path
        
        # Determine project_path based on whether input is file or directory
        if os.path.isdir(game_exe_path):
            # Directory path provided (CLI mode) - use as project root
            candidate = game_exe_path
            # If the directory is named 'game', go up one level
            if os.path.basename(candidate).lower() == 'game':
                candidate = os.path.dirname(candidate)
            # If no 'game' subfolder, check if parent has one
            elif not os.path.isdir(os.path.join(candidate, 'game')):
                parent = os.path.dirname(candidate)
                if os.path.isdir(os.path.join(parent, 'game')):
                    candidate = parent
        else:
            # File path provided (GUI mode) - use parent directory
            candidate = os.path.dirname(game_exe_path)
            try:
                if os.path.basename(candidate).lower() == 'game':
                    # EXE located inside <project>/game/Game.exe; use project root
                    candidate = os.path.dirname(candidate)
                    self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_game'))
                elif not os.path.isdir(os.path.join(candidate, 'game')):
                    # If candidate lacks a game folder but parent has it, use parent
                    parent = os.path.dirname(candidate)
                    if os.path.isdir(os.path.join(parent, 'game')):
                        candidate = parent
                        self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_parent'))
            except Exception:
                # Defensive: if any error occurs, fall back to dirname
                candidate = os.path.dirname(game_exe_path)
        
        self.project_path = candidate
        self.target_language = target_language
        self.source_language = source_language
        self.engine = engine
        self.auto_unren = auto_unren
        self.use_proxy = use_proxy
    
    def stop(self):
        """Pipeline'ı durdur"""
        self.should_stop = True
        self.log_message.emit("warning", self.config.get_ui_text("stop_requested"))
    
    def _set_stage(self, stage: PipelineStage, message: str = ""):
        """Aşamayı değiştir ve sinyal gönder"""
        self.current_stage = stage
        self.stage_changed.emit(stage.value, message)
        
        # Localized stage label
        stage_label = self.config.get_log_text(f"stage_{stage.value}", stage.value.upper())
        self.log_message.emit("info", f"[{stage_label}] {message}")
    
    def run(self):
        """Pipeline'ı çalıştır"""
        self.is_running = True
        self.should_stop = False
        
        try:
            result = self._run_pipeline()
            self.finished.emit(result)
        except Exception as e:
            self.logger.exception("Pipeline hatası")
            result = PipelineResult(
                success=False,
                message=f"Beklenmeyen hata: {str(e)}",
                stage=PipelineStage.ERROR,
                error=str(e)
            )
            self.finished.emit(result)
        finally:
            self.is_running = False
    
    def _run_pipeline(self) -> PipelineResult:
        """Ana pipeline akışı"""
        
        # 1. Doğrulama
        self._set_stage(PipelineStage.VALIDATING, self.config.get_ui_text("stage_validating"))
        
        # game_exe_path can be either:
        # 1. An .exe file path (traditional GUI usage)
        # 2. A directory path (CLI usage with --mode full)
        if not self.game_exe_path:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_invalid_exe"),
                stage=PipelineStage.ERROR
            )
        
        # Accept both file and directory paths
        is_file = os.path.isfile(self.game_exe_path)
        is_dir = os.path.isdir(self.game_exe_path)
        
        if not is_file and not is_dir:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_invalid_exe") + f" (path does not exist: {self.game_exe_path})",
                stage=PipelineStage.ERROR
            )
        
        # Ensure project_path is normalized in case the user selected an EXE
        # inside a 'game' subfolder or in a nested path.
        project_path = self.project_path
        try:
            # If project_path currently points to a 'game' folder, normalize up one level
            if os.path.basename(project_path).lower() == 'game':
                self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_game'))
                project_path = os.path.dirname(project_path)
            # If project_path doesn't have a 'game' folder but parent does, normalize up
            elif not os.path.isdir(os.path.join(project_path, 'game')):
                parent = os.path.dirname(project_path)
                if os.path.isdir(os.path.join(parent, 'game')):
                    self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_parent'))
                    project_path = parent
        except Exception:
            # on failure, leave project_path as-is
            pass
        game_dir = os.path.join(project_path, 'game')
        
        if not os.path.isdir(game_dir):
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_game_folder_missing"),
                stage=PipelineStage.ERROR
            )
        
        # .rpy dosyası kontrolü
        has_rpy = self._has_rpy_files(game_dir)
        has_rpyc = self._has_rpyc_files(game_dir)
        has_rpa = self._has_rpa_files(game_dir)  # Arşiv dosyası kontrolü

        # .rpymc dosyalarını bul ve gerçek AST tabanlı okuyucuyu kullan
        self.rpymc_entries = []
        should_scan_rpym = getattr(self.config.translation_settings, 'scan_rpym_files', False)
        
        if should_scan_rpym:
            rpymc_files = self._find_rpymc_files(game_dir)
            if rpymc_files:
                from src.core.rpyc_reader import extract_texts_from_rpyc
                for rpymc_path in rpymc_files:
                    try:
                        texts = extract_texts_from_rpyc(rpymc_path, config_manager=self.config)
                        for t in texts:
                            text_val = t.get('text') or ""
                            if not text_val:
                                continue
                            ctx_path = t.get('context_path') or []
                            if isinstance(ctx_path, str):
                                ctx_path = [ctx_path]
                            entry = TranslationEntry(
                                original_text=text_val,
                                translated_text="",
                                file_path=str(rpymc_path),
                                line_number=t.get('line_number', 0) or 0,
                                entry_type="rpymc",
                                character=t.get('character'),
                                source_comment=None,
                                block_id=None,
                                context_path=ctx_path,
                                translation_id=TLParser.make_translation_id(
                                        str(rpymc_path), t.get('line_number', 0) or 0, text_val, ctx_path, t.get('raw_text')
                                    )
                            )
                            self.rpymc_entries.append(entry)
                    except Exception as e:
                        msg = f".rpymc extraction failed: {rpymc_path} ({e})"
                        self.log_message.emit('warning', msg)
                        self._log_error(msg)

                # Log .rpymc entry count
                self.log_message.emit('debug', self.config.get_log_text('rpymc_entry_count', count=len(self.rpymc_entries)))
        else:
            self.log_message.emit('debug', "Skipping .rpymc scan (scan_rpym_files disabled)")
        
        if self.should_stop:
            return self._stopped_result()
        
        # 2. UnRen/UnRPA (gerekirse) - .rpyc VEYA .rpa dosyası varsa çalıştır
        # Platform-aware: Windows uses UnRen batch, Linux/macOS uses unrpa
        # DÜZELTME: .rpy olsa bile .rpa varsa (ve auto_unren açıksa) extraction yapılmalı.
        # Çünkü dışarıdaki .rpy dosyaları eksik/yardımcı olabilir, asıl veri .rpa içindedir.
        needs_extraction = has_rpa and self.auto_unren
        needs_decompile = not has_rpy and has_rpyc and self.auto_unren
        
        if needs_extraction or needs_decompile:
            self.log_message.emit("info", self.config.get_log_text('rpa_extraction_needed'))
            self._set_stage(PipelineStage.UNRPA, self.config.get_ui_text("stage_unren"))
            
            # Decompile/Extract
            success = self._run_extraction(project_path)
            
            if not success:
                # On non-Windows, if unrpa failed but we have rpyc files, we can still continue
                import os as _os
                if _os.name != "nt" and has_rpyc:
                    self.log_message.emit("warning", self.config.get_log_text('log_rpa_failed_rpyc_continue'))
                else:
                    return PipelineResult(
                        success=False,
                        message=self.config.get_ui_text("unren_launch_failed").format(error=""),
                        stage=PipelineStage.ERROR
                    )
            
            # CRITICAL: Clean up engine-level translations if they were accidentally created
            # This prevents technical common scripts from breaking the game
            tl_path = os.path.join(game_dir, 'tl')
            if os.path.exists(tl_path):
                for root, dirs, files in os.walk(tl_path):
                     if 'common' in root.replace('\\', '/').split('/'):
                          for f in files:
                               try: os.remove(os.path.join(root, f))
                               except Exception: pass
            
            # Tekrar kontrol
            has_rpy = self._has_rpy_files(game_dir)
        
        # RPYC-only mode: If no .rpy but has .rpyc and RPYC Reader is enabled
        rpyc_only_mode = False
        if not has_rpy and has_rpyc:
            # Check if RPYC reader is enabled
            rpyc_enabled = getattr(self.config.translation_settings, 'enable_rpyc_reader', False) or getattr(self, 'include_rpyc', False)
            if rpyc_enabled:
                self.log_message.emit("info", self.config.get_ui_text("pipeline_rpyc_only_mode", "RPYC-only mode: No .rpy files found, reading .rpyc files directly."))
                rpyc_only_mode = True
            else:
                return PipelineResult(
                    success=False,
                    message=self.config.get_ui_text("pipeline_no_rpy_files") + " " + self.config.get_ui_text("pipeline_enable_rpyc_hint", "(Try enabling RPYC Reader)"),
                    stage=PipelineStage.ERROR
                )
        
        if self.should_stop:
            return self._stopped_result()
        
        # 2.5. Kaynak dosyaları çevrilebilir hale getir
        self._set_stage(PipelineStage.GENERATING, self.config.get_ui_text("stage_generating"))
        self._make_source_translatable(game_dir)
        
        if self.should_stop:
            return self._stopped_result()
        
        # 3. Translate komutu
        self._set_stage(PipelineStage.GENERATING, f"{self.config.get_ui_text('stage_generating')} ({self.target_language})")
        
        tl_dir = os.path.join(game_dir, 'tl', self.target_language)
        
        # Zaten varsa atla
        if not os.path.isdir(tl_dir) or not self._has_rpy_files(tl_dir):
            success = self._run_translate_command(project_path)
            
            if not success:
                return PipelineResult(
                    success=False,
                    message=self.config.get_ui_text("pipeline_translate_failed"),
                    stage=PipelineStage.ERROR
                )
        else:
            self.log_message.emit("info", self.config.get_ui_text("pipeline_tl_exists_skip").replace("{lang}", str(self.target_language)))
        
        if self.should_stop:
            return self._stopped_result()
        
        # 4. Parse
        self._set_stage(PipelineStage.PARSING, self.config.get_ui_text("stage_parsing"))
        
        # Ren'Py klasör adı ile API/ISO kodunu eşle
        reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
        renpy_lang = reverse_lang_map.get(self.target_language.lower(), self.target_language)

        tl_path = os.path.join(game_dir, 'tl')
        tl_files = self.tl_parser.parse_directory(tl_path, renpy_lang)


        # Yaln?zca hedef dil alt?ndaki dosyalar? kabul et; di?er dil klas?rlerini hari? tut
        target_tl_dir = os.path.normcase(os.path.join(tl_path, renpy_lang))
        filtered_files: List[TranslationFile] = []
        for tl_file in tl_files:
            fp_norm = os.path.normcase(tl_file.file_path)
            if fp_norm.startswith(target_tl_dir):
                tl_file.entries = [
                    e for e in tl_file.entries
                    if os.path.normcase(e.file_path or tl_file.file_path).startswith(target_tl_dir)
                ]
                filtered_files.append(tl_file)
            else:
                self.log_message.emit("info", self.config.get_log_text('other_lang_folder_skipped', path=tl_file.file_path))
        tl_files = filtered_files


        # Phase 5: Deep Scan Integration
        if getattr(self, 'include_deep_scan', False):
            self.log_message.emit("info", self.config.get_log_text('deep_scan_running'))
            try:
                parser = RenPyParser()
                # Scan source files
                scan_res = parser.extract_combined(
                    str(game_dir), include_rpy=True, include_rpyc=True, 
                    include_deep_scan=True, recursive=True,
                    exclude_dirs=['renpy', 'common', 'tl', 'lib', 'python-packages'] # Security: skip engine
                )
                
                existing = {e.original_text for t in tl_files for e in t.entries}
                missing = []
                for entries in scan_res.values():
                    for e in entries:
                        txt = e.get('text')
                        if txt and txt not in existing and len(txt) > 1:
                            missing.append(e)
                            existing.add(txt)
                
                if missing:
                     self.log_message.emit("info", self.config.get_log_text('deep_scan_found', count=len(missing)))
                     deepscan_dir = os.path.join(tl_path, renpy_lang)
                     os.makedirs(deepscan_dir, exist_ok=True)
                     d_file = os.path.join(deepscan_dir, "strings_deepscan.rpy")
                     
                     lines = ["# Deep Scan generated translations", f"translate {renpy_lang} strings:\n"]
                     for m in missing:
                         o = m['text'].replace('"', '\\"').replace('\n', '\\n')
                         if m.get('context'): lines.append(f"    # context: {m['context']}")
                         lines.append(f'    old "{o}"\n    new ""\n')
                         
                     with open(d_file, 'w', encoding="utf-8") as f:
                         f.write('\n'.join(lines))
                         
                     # Add new file to pipeline processing
                     for ntf in self.tl_parser.parse_directory(deepscan_dir, renpy_lang):
                         if os.path.normcase(ntf.file_path) == os.path.normcase(d_file):
                             tl_files.append(ntf)
                             break
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('deep_scan_error', error=str(e)))

        # Hata raporunda görülen UnicodeDecodeError'ları engellemek için tl çıktısını
        # tümüyle UTF-8-SIG formatında normalize et (renpy loader katı UTF-8 kullanıyor).
        try:
            normalized = self._normalize_tl_encodings(os.path.join(tl_path, renpy_lang))
            if normalized:
                self.log_message.emit("info", self.config.get_log_text('log_tl_normalized', count=normalized))
                self.normalize_count = normalized
        except Exception as e:
            msg = self.config.get_log_text('encoding_normalize_failed', path="tl", error=str(e))
            self.log_message.emit("warning", msg)
            self._log_error(msg)
        
        if not tl_files:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_files_not_found_parse"),
                stage=PipelineStage.ERROR
            )
        
        # Çevrilmemiş girişleri topla
        all_entries = []
        for tl_file in tl_files:
            all_entries.extend(tl_file.get_untranslated())

        # Initialize diagnostic report
        try:
            self.diagnostic_report.project = os.path.basename(os.path.abspath(game_dir))
            self.diagnostic_report.target_language = self.target_language
            for tl_file in tl_files:
                # record extracted counts based on entries
                for e in tl_file.entries:
                    fp = e.file_path or tl_file.file_path
                    self.diagnostic_report.add_extracted(fp, {
                        'text': e.original_text,
                        'line_number': e.line_number,
                        'context_path': getattr(e, 'context_path', [])
                    })
        except Exception:
            pass
        
        if not all_entries:
            stats = get_translation_stats(tl_files)
            if game_dir and os.path.isdir(game_dir):
                self._create_language_init_file(str(game_dir))
                
                # strings.json oluştur (Agresif kanca için)
                lang_dir = os.path.join(tl_path, renpy_lang)
                self._generate_strings_json(tl_files, lang_dir)
                
                self._manage_runtime_hook()
            return PipelineResult(
                success=True,
                message=self.config.get_ui_text("pipeline_all_already_translated"),
                stage=PipelineStage.COMPLETED,
                stats=stats,
                output_path=tl_dir
            )
        
        self.log_message.emit("info", self.config.get_ui_text("pipeline_entries_to_translate").replace("{count}", str(len(all_entries))))
        
        if self.should_stop:
            return self._stopped_result()
        
        # --- .rpymc entry'lerini all_entries'ye ekle ---
        if getattr(self, 'rpymc_entries', None):
            self.log_message.emit('info', self.config.get_log_text('rpymc_adding_entries', count=len(self.rpymc_entries)))
            all_entries.extend(self.rpymc_entries)
        
        # 5. Çeviri
        self._set_stage(PipelineStage.TRANSLATING, self.config.get_ui_text("stage_translating"))
        
        translations = self._translate_entries(all_entries)
        
        if self.should_stop:
            return self._stopped_result()
        
        if not translations:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_translate_failed"),
                stage=PipelineStage.ERROR
            )
        
        # 6. Kaydetme
        self._set_stage(PipelineStage.SAVING, self.config.get_ui_text("stage_saving"))
        
        saved_count = 0
        for tl_file in tl_files:
            # Bu dosyaya ait çevirileri filtrele
            file_translations = {}
            for entry in tl_file.entries:
                # original_text kullan (old_text property olarak da çalışır)
                tid = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                    entry.file_path, entry.line_number, entry.original_text
                )
                if tid in translations:
                    file_translations[tid] = translations[tid]
                elif entry.original_text in translations:
                    file_translations[entry.original_text] = translations[entry.original_text]
            
            if file_translations:
                success = self.tl_parser.save_translations(tl_file, file_translations)
                if success:
                    saved_count += 1
                    # Diagnostics: mark written entries
                    try:
                        for tid in file_translations.keys():
                            # find file path
                            fp = tl_file.file_path
                            self.diagnostic_report.mark_written(fp, tid)
                    except Exception:
                        pass
        
        # 6.5. Atomik segment çevirileri strings.json'a zaten ekleniyor (extra_translations)
        # ve runtime hook Layer 1/2 tarafından eşleştiriliyor.
        # _rl_segments.rpy artık oluşturulmuyor (v2.7.1 hotfix):
        #   - translate XX strings: bloğu renpy.say() düzeyinde çalışmaz
        #   - play_dialogue() quote wrapping ("text") nedeniyle match yapamaz
        #   - Duplicate entry crash'lerine neden oluyordu
        # Eski _rl_segments.rpy dosyası varsa temizle
        _old_seg_path = os.path.join(tl_dir, '_rl_segments.rpy')
        if os.path.exists(_old_seg_path):
            try:
                os.remove(_old_seg_path)
                self.emit_log("info", "[AtomicSegments] Removed obsolete _rl_segments.rpy (translations handled by runtime hook)")
                # .rpyc de varsa sil
                _old_seg_rpyc = _old_seg_path + 'c'
                if os.path.exists(_old_seg_rpyc):
                    os.remove(_old_seg_rpyc)
            except Exception:
                pass
        
        # 7. Dil başlatma kodu oluştur (game/ klasörüne)
        self._create_language_init_file(game_dir)
        
        # Final istatistikler
        # Dosyaları yeniden parse et
        tl_files_updated = self.tl_parser.parse_directory(tl_path, self.target_language)
        stats = get_translation_stats(tl_files_updated)

        # Write diagnostics JSON next to tl folder
        try:
            diag_path = os.path.join(tl_dir, 'diagnostics', f'diagnostic_{self.target_language}.json')
            self.diagnostic_report.write(diag_path)
            self.log_message.emit('info', self.config.get_log_text('log_diagnostic_written', path=diag_path))
        except Exception:
            pass
        
        # Hedef dil icin dil baslatici dosyasi olustur
        if game_dir and os.path.isdir(game_dir):
            self._create_language_init_file(str(game_dir))
            
            # strings.json oluştur (Agresif kanca için)
            lang_dir = os.path.join(tl_path, renpy_lang)
            self._generate_strings_json(tl_files_updated, lang_dir, extra_translations=translations)
            
            self._manage_runtime_hook()

        self._set_stage(PipelineStage.COMPLETED, self.config.get_ui_text("stage_completed"))
        summary = self.config.get_ui_text("pipeline_completed_summary").replace("{translated}", str(len(translations))).replace("{saved}", str(saved_count))
        if self.normalize_count:
            summary += f" | {self.config.get_log_text('log_tl_normalized', count=self.normalize_count)}"
        
        return PipelineResult(
            success=True,
            message=summary,
            stage=PipelineStage.COMPLETED,
            stats=stats,
            output_path=tl_dir
        )
    
    def _stopped_result(self) -> PipelineResult:
        """Durduruldu sonucu"""
        return PipelineResult(
            success=False,
            message=self.config.get_ui_text("pipeline_user_stopped"),
            stage=PipelineStage.IDLE
        )
    
    def _has_rpy_files(self, directory: str) -> bool:
        """Klasörde .rpy dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpy'):
                    return True
        return False
    
    def _has_rpyc_files(self, directory: str) -> bool:
        """Klasörde .rpyc dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpyc'):
                    return True
        return False
    
    def _has_rpa_files(self, directory: str) -> bool:
        """Klasörde .rpa arşiv dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpa'):
                    return True
        return False

    def _normalize_tl_encodings(self, tl_dir: str) -> int:
        """
        tl/<lang> içindeki .rpy dosyalarını UTF-8-SIG'e yeniden yazar.
        Ren'Py loader'ı 'python_strict' ile okuduğu için geçersiz byte'lar
        (örn. 0xBE) oyunu düşürüyor; burada tamamını normalize ediyoruz.
        """
        tl_path = Path(tl_dir)
        if not tl_path.exists():
            return 0

        normalized = 0
        for file_path in tl_path.rglob("*.rpy"):
            try:
                if normalize_to_utf8_sig(file_path):
                    normalized += 1
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('encoding_normalize_failed', path=file_path, error=str(e)))
        return normalized
    
    def _generate_strings_json(self, tl_files: List[TranslationFile], lang_dir: str, extra_translations: dict = None):
        """
        Tüm çevirileri strings.json dosyasına aktarır.
        Agresif substring çeviri motoru için gereklidir.
        
        Args:
            tl_files: Çeviri dosyaları listesi
            lang_dir: Hedef dil dizini
            extra_translations: Ek çeviri çiftleri (atomik segment girişleri vb.)
        """
        try:
            import json
            mapping = {}
            skipped_corrupt = 0
            skipped_reason_counts = {
                'separator_remnant': 0,
                'placeholder_remnant': 0,
                'html_leakage': 0,
                'length_inflation': 0,
                'placeholder_set_mismatch': 0,
                'renpy_tag_set_mismatch': 0,
                'duplicate_key_conflict': 0,
            }
            skipped_samples = []

            def _mark_skipped(reason: str, original: str, translated: str):
                nonlocal skipped_corrupt
                skipped_corrupt += 1
                if reason in skipped_reason_counts:
                    skipped_reason_counts[reason] += 1
                if len(skipped_samples) < 100:
                    skipped_samples.append({
                        'reason': reason,
                        'original_preview': original[:120],
                        'translated_preview': translated[:120],
                    })

            for tfile in tl_files:
                for entry in tfile.entries:
                    if entry.original_text and entry.translated_text:
                        # Skip technical/empty/same
                        orig = entry.original_text.strip()
                        trans = entry.translated_text.strip()
                        if not orig or not trans or orig == trans:
                            continue
                        # Sanitization: skip corrupted translations
                        # 1. Separator remnant check (batch separator bleeding)
                        if '|||' in trans or 'RNLSEP' in trans or 'SEP777' in trans or 'TXTSEP' in trans:
                            _mark_skipped('separator_remnant', orig, trans)
                            self.logger.debug(f"strings.json: Skipping separator remnant in translation of: {orig[:40]}")
                            continue
                        # 2. Placeholder remnant check (restore failure leakage)
                        if '\u27e6RLPH' in trans or 'XRPYX_' in trans or 'RNPY_' in trans or '\u27e6' in trans:
                            _mark_skipped('placeholder_remnant', orig, trans)
                            self.logger.debug(f"strings.json: Skipping placeholder remnant in translation of: {orig[:40]}")
                            continue
                        # 3. HTML tag leakage check (from Google Translate HTML protection mode)
                        if '<span' in trans.lower() or '</span>' in trans.lower() or '<div' in trans.lower():
                            _mark_skipped('html_leakage', orig, trans)
                            self.logger.debug(f"strings.json: Skipping HTML tag leakage in translation of: {orig[:40]}")
                            continue
                        # 4. Length inflation check (translated text abnormally longer than original)
                        orig_len = len(orig)
                        trans_len = len(trans)
                        if orig_len > 0 and trans_len > max(orig_len * 4, orig_len + 80):
                            _mark_skipped('length_inflation', orig, trans)
                            self.logger.debug(f"strings.json: Skipping inflated translation ({trans_len} vs {orig_len}): {orig[:40]}")
                            continue

                        # 5. Placeholder set integrity check
                        # Prevents broken mappings such as missing/extra [name] placeholders.
                        orig_placeholders = sorted(re.findall(r'\[[^\]]+\]', orig))
                        trans_placeholders = sorted(re.findall(r'\[[^\]]+\]', trans))
                        if orig_placeholders != trans_placeholders:
                            _mark_skipped('placeholder_set_mismatch', orig, trans)
                            self.logger.debug(f"strings.json: Skipping placeholder-set mismatch in translation of: {orig[:40]}")
                            continue

                        # 6. Ren'Py text tag integrity check
                        # Prevents context bleed like plain key -> styled/tagged value
                        # e.g. "RedLightHouse" -> "{font=...}RedLightHouse{/font}"
                        orig_tags = sorted(re.findall(r'\{/?[^}]+\}', orig))
                        trans_tags = sorted(re.findall(r'\{/?[^}]+\}', trans))
                        if orig_tags != trans_tags:
                            _mark_skipped('renpy_tag_set_mismatch', orig, trans)
                            self.logger.debug(f"strings.json: Skipping Ren'Py tag-set mismatch in translation of: {orig[:40]}")
                            continue

                        # 7. Duplicate key conflict detection
                        # When the same original text appears in multiple files with
                        # different translations, silently overwriting loses data.
                        # Strategy: keep the first (typically from the main dialogue file).
                        if orig in mapping:
                            if mapping[orig] != trans:
                                _mark_skipped('duplicate_key_conflict', orig, trans)
                                self.logger.debug(
                                    f"strings.json: Duplicate key conflict, keeping existing: "
                                    f"{orig[:40]} -> existing={mapping[orig][:30]} vs new={trans[:30]}"
                                )
                            continue  # same key+value is harmless, skip either way

                        mapping[orig] = trans
            
            # ── Atomik segment çevirileri ekle (v2.7.1) ──
            # Delimiter gruplarından gelen bağımsız segment çevirileri,
            # Ren'Py runtime vary() eşleşmesi için strings.json'a eklenir.
            if extra_translations:
                for orig, trans in extra_translations.items():
                    orig_s = orig.strip()
                    trans_s = trans.strip()
                    if orig_s and trans_s and orig_s != trans_s and orig_s not in mapping:
                        mapping[orig_s] = trans_s
            
            # ── Delimiter grup segmentlerini ayır (v2.7.1 hotfix) ──
            # Ren'Py vary() fonksiyonu <A|B|C> bloklarını parçalayıp tek segment seçer.
            # strings.json'da birleşik blok ("old <A|B|C>": "<X|Y|Z>") var ama
            # bireysel segmentler ("A": "X") yok → vary() çıktısı eşleşmiyor.
            # Bu adım tüm mapping'i tarayıp:
            #   1) Angle-pipe gruplarını (<A|B|C>) bireysel segment çiftlerine ayırır
            #   2) Bare pipe patternlerini (A|B|C, <> olmadan) bireysel segment çiftlerine ayırır
            try:
                from src.core.syntax_guard import split_angle_pipe_groups, split_delimited_text
                _seg_additions = {}
                _seg_count = 0
                for m_orig, m_trans in list(mapping.items()):
                    # ── Yol 1: Angle-pipe grupları (<A|B|C>) ──
                    orig_split = split_angle_pipe_groups(m_orig)
                    if orig_split is not None:
                        trans_split = split_angle_pipe_groups(m_trans)
                        if trans_split is not None:
                            _, orig_groups = orig_split
                            _, trans_groups = trans_split
                            for g_idx in range(min(len(orig_groups), len(trans_groups))):
                                o_segs = orig_groups[g_idx]
                                t_segs = trans_groups[g_idx]
                                for s_idx in range(min(len(o_segs), len(t_segs))):
                                    o_s = o_segs[s_idx].strip()
                                    t_s = t_segs[s_idx].strip()
                                    if o_s and t_s and o_s != t_s and o_s not in mapping and o_s not in _seg_additions:
                                        _seg_additions[o_s] = t_s
                                        _seg_count += 1
                        continue  # Angle-pipe bulundu — bare pipe'a düşme
                    
                    # ── Yol 2: Bare pipe (A|B|C, <> olmadan) ──
                    if '|' not in m_orig:
                        continue
                    orig_delim = split_delimited_text(m_orig)
                    if orig_delim is None:
                        # split_delimited_text false-positive filtresi geçemediyse
                        # basit pipe split dene (vary() tam olarak bunu yapar)
                        if '|' in m_orig and '|' in m_trans:
                            o_parts = m_orig.split('|')
                            t_parts = m_trans.split('|')
                            # Safety: limit segment count (>6 likely CSV/data, not dialogue)
                            # and require at least 2 alpha chars per segment to filter noise.
                            if (len(o_parts) >= 2 and len(o_parts) == len(t_parts)
                                    and len(o_parts) <= 6):
                                _pipe_valid = True
                                for _p in o_parts:
                                    if sum(1 for ch in _p.strip() if ch.isalpha()) < 2:
                                        _pipe_valid = False
                                        break
                                if _pipe_valid:
                                    for o_s, t_s in zip(o_parts, t_parts):
                                        o_s = o_s.strip()
                                        t_s = t_s.strip()
                                        if o_s and t_s and o_s != t_s and o_s not in mapping and o_s not in _seg_additions:
                                            _seg_additions[o_s] = t_s
                                            _seg_count += 1
                        continue
                    
                    o_segs, _, _, _ = orig_delim
                    trans_delim = split_delimited_text(m_trans)
                    if trans_delim is not None:
                        t_segs, _, _, _ = trans_delim
                    elif '|' in m_trans:
                        # Çeviri split_delimited_text'e uymuyorsa basit pipe split
                        t_segs = m_trans.split('|')
                    else:
                        continue
                    
                    for s_idx in range(min(len(o_segs), len(t_segs))):
                        o_s = o_segs[s_idx].strip()
                        t_s = t_segs[s_idx].strip()
                        if o_s and t_s and o_s != t_s and o_s not in mapping and o_s not in _seg_additions:
                            _seg_additions[o_s] = t_s
                            _seg_count += 1
                
                if _seg_additions:
                    mapping.update(_seg_additions)
                    self.logger.info(f"strings.json: {_seg_count} individual segments extracted from delimiter groups")
            except Exception as e:
                self.logger.debug(f"strings.json segment splitting skipped: {e}")
            
            if skipped_corrupt > 0:
                self.logger.warning(f"strings.json: Skipped {skipped_corrupt} potentially corrupted translation(s)")
                reason_summary = ', '.join(
                    f"{name}={count}" for name, count in skipped_reason_counts.items() if count > 0
                )
                if reason_summary:
                    self.logger.info(f"strings.json: Corruption reasons -> {reason_summary}")
                try:
                    diag_dir = os.path.join(lang_dir, 'diagnostics')
                    os.makedirs(diag_dir, exist_ok=True)
                    report_path = os.path.join(diag_dir, 'strings_json_skipped_corruptions.json')
                    with open(report_path, 'w', encoding='utf-8') as rf:
                        json.dump({
                            'generated_at': int(time.time()),
                            'total_skipped': skipped_corrupt,
                            'reason_counts': skipped_reason_counts,
                            'sample_limit': 100,
                            'samples': skipped_samples,
                        }, rf, ensure_ascii=False, indent=2)
                    self.logger.info(f"strings.json: Wrote skipped-corruption report -> {report_path}")
                except Exception as report_exc:
                    self.logger.debug(f"strings.json: Failed to write skipped-corruption report: {report_exc}")
            
            if mapping:
                json_path = os.path.join(lang_dir, "strings.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=4)
                self.log_message.emit('info', self.config.get_log_text('log_strings_json_generated', count=len(mapping)))
        except Exception as e:
            self.logger.warning(f"Failed to generate strings.json: {e}")

    def _write_atomic_segments_rpy(self, tl_dir: str, renpy_lang: str):
        """
        DEPRECATED (v2.7.1 hotfix) — Bu metod artık çağrılmıyor.
        
        Neden kaldırıldı:
        1. translate XX strings: bloğu renpy.say() dinamik diyaloglarında çalışmaz
        2. play_dialogue() fonksiyonu vary() çıktısını \"...\" ile sarmalıyor,
           bu yüzden old "text" girişleri "text" (tırnaklı) ile eşleşemez
        3. strings.rpy ile duplicate entry crash'lerine neden oluyordu
        
        Atomik segment çevirileri artık:
        - strings.json'a ekleniyor (extra_translations parametresi ile)
        - Runtime hook Layer 1/2 tarafından eşleştiriliyor (quote-stripping ile)
        
        Bu metod geriye dönük uyumluluk için korunuyor ama çağrılmıyor.
        """
        self.logger.debug("_write_atomic_segments_rpy is deprecated, skipping")
        return

    def _manage_runtime_hook(self):
        """
        Manages the presence of the runtime translation hook script based on settings.
        Generated by RenLocalizer to force translation of untagged strings.
        v2.7.0: Loads ALL mappings from ALL .rpy files in tl directory.
        """
        if not self.project_path:
            return
            
        try:
            game_dir = Path(self.project_path) / "game"
            if not game_dir.exists():
                return
                
            hook_filename = "zzz_renlocalizer_runtime.rpy"
            hook_path = game_dir / hook_filename
            
            # Clean up old versions
            for old in game_dir.glob("*_renlocalizer_*.rpy"):
                if old.name != hook_filename:
                    old.unlink(missing_ok=True)

            # Settings check: auto_generate_hook OR force_runtime_translation
            auto_gen = getattr(self.config.translation_settings, 'auto_generate_hook', True)
            force_run = getattr(self.config.translation_settings, 'force_runtime_translation', False)
            should_exist = auto_gen or force_run
            
            # Hedef dili al
            target_lang = getattr(self, 'target_language', None) or getattr(self.config.translation_settings, 'target_language', 'turkish') or 'turkish'
            # ISO -> Ren'Py native
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            renpy_lang = reverse_lang_map.get(target_lang.lower(), target_lang)
            
            if should_exist:
                content = (
                    RUNTIME_HOOK_TEMPLATE.replace("{renpy_lang}", renpy_lang)
                    .replace("{{", "{")
                    .replace("}}", "}")
                )
                save_text_safely(hook_path, content, encoding="utf-8")
                self.log_message.emit('info', self.config.get_ui_text("log_hook_installed").replace("{filename}", hook_filename))
            else:
                # Remove if it exists
                if hook_path.exists():
                    os.remove(hook_path)
                    self.log_message.emit('info', self.config.get_ui_text("log_hook_removed").replace("{filename}", hook_filename))
                    
        except Exception as e:
            self.logger.warning(f"Failed to manage runtime hook: {e}")

    def _create_language_init_file(self, game_dir: str):
        """
        Dil baslangic dosyasini olusturur.
        game/ klasorune yazilir, boylece oyun baslarken varsayilan dil ayarlanir.
        
        v2.6.7: Agresif aktivasyon - Bazı oyunlar basit config.default_language'ı
        görmezden geldiği için çoklu yöntem kullanıyoruz.
        """
        try:
            # Hedef dil kodunu hesapla; ISO gelirse Ren'Py adina cevir
            language_code = (getattr(self, 'target_language', None) or '').strip().lower()
            if not language_code:
                try:
                    language_code = getattr(self.config.translation_settings, 'target_language', '') or ''
                except Exception:
                    language_code = ''
            original_input = language_code
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            if language_code:
                language_code = reverse_lang_map.get(language_code, language_code)
            else:
                # Hedef bilinmiyorsa tl alt klasorlerini kontrol et; yalnizca tek klasor varsa kullan
                tl_root = Path(game_dir) / "tl"
                subdirs = sorted([p.name for p in tl_root.iterdir() if p.is_dir()]) if tl_root.exists() else []
                if len(subdirs) == 1:
                    language_code = subdirs[0].lower()
                    self.log_message.emit("info", self.config.get_log_text('target_lang_auto', lang=language_code))
                else:
                    language_code = 'turkish'
                    self.log_message.emit("warning", self.config.get_log_text('target_lang_default'))

            # Once eski otomatik init dosyalarini temizle ki tek dosya aktif kalsin
            try:
                for existing in Path(game_dir).glob("*_language.rpy"):
                    if "renlocalizer" in existing.name or existing.name.startswith("a0_") or existing.name.startswith("zzz_"):
                        if existing.name != f"zzz_{language_code}_language.rpy":
                            existing.unlink(missing_ok=True)
                            self.log_message.emit("info", self.config.get_log_text('old_lang_init_deleted', name=existing.name))
            except Exception:
                pass

            # Dosya adi: zzz_[lang]_language.rpy (En son yuklenir, oyunun ayarlarini ezer)
            init_file = os.path.join(game_dir, f'zzz_{language_code}_language.rpy')

            self.log_message.emit(
                "info",
                self.config.get_ui_text("pipeline_lang_init_check").replace("{path}", init_file)
                + f" | dil={language_code} (input={original_input or 'none'})"
            )

            # Zaten varsa sil ve yeniden olustur (guncellemek icin)
            if os.path.exists(init_file):
                os.remove(init_file)
                self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_update"))

            # Sanitize language_code for use as Python identifier (e.g. zh-CN -> zh_cn)
            safe_code = language_code.replace("-", "_").replace(" ", "_").replace(".", "_")

            # Agresif çoklu-fazlı dil aktivasyon sistemi
            # v2.7.5: Ren'Py dokümantasyonuna uygun güvenli yaklaşım
            #
            # KRİTİK GÜVENLIK KURALLARI:
            # 1. gui.init() "init offset = -2" ile çalışır ve renpy.call_in_new_context("_style_reset")
            #    çağırır. Yeni context oluşturulurken config.context_copy_remove_screens'deki
            #    ekranlar (varsayılan: ['notify', ...]) scene_lists'ten kaldırılır.
            #    Bu kaldırma screen.update() → renpy.ui.detached() → stack[-1] gerektirir.
            #    Init fazında ui.stack BOŞ'tur (ui.reset() post_init'te çalışır).
            #    Bu yüzden gui.init() ÖNCESI herhangi bir screen gösterilmemeli!
            #
            # 2. _preferences.language Ren'Py dokümantasyonunda READ-ONLY olarak belirtilir.
            #    Dil değiştirmek için renpy.change_language() kullanılmalıdır.
            #
            # 3. config.language (config.default_language DEĞİL) kullanıcı tercihini EZER.
            #    Bu "unsanctioned translations" için Ren'Py'nin resmi önerisidir.
            #
            # GÜVENLI PRİORİTE SIRASI:
            #   init -2  : gui.init() (oyunun gui.rpy dosyası)
            #   init 0   : Bizim config.language ayarımız (gui.init SONRASI, güvenli)
            #   init 999 : Runtime hook kurulumu
            content = f"""# ============================================================
# RenLocalizer - Safe Language Activation v2.7.5
# ============================================================
# Bu dosya oyunun dilini {language_code.title()}'ye ayarlar.
#
# KRİTİK: init -2'den ÖNCE (gui.init öncesi) hiçbir config/screen
# işlemi yapılmaz. Bu, IndexError crash'ini önler.
#
# Ren'Py dil seçim önceliği (dokümantasyondan):
#   1. config.language (None değilse, diğer HER ŞEYİ ezer)
#   2. Kullanıcının daha önce seçtiği dil
#   3. config.enable_language_autodetect
#   4. config.default_language
#   5. None (varsayılan dil)

# ============================================================
# PHASE 1: Safe Language Override (AFTER gui.init)
# ============================================================
# config.language kullanıcı tercihini ezer — "unsanctioned translations"
# için Ren'Py'nin resmi önerisidir. Priority 0 = gui.init (-2) SONRASI.
define config.language = "{language_code}"

# ============================================================
# PHASE 2: Runtime Enforcement (Game Start Hook)
# ============================================================
# config.start_callbacks init fazı BİTTİKTEN SONRA,
# oyun (splashscreen dahil) başlamadan HEMEN ÖNCE çalışır.
# Bu noktada ui.stack başlatılmıştır, screen göstermek güvenlidir.
init python:
    def _rl_force_{safe_code}_language():
        \"\"\"
        Oyun her başladığında dili kontrol et ve gerekirse {language_code.title()}'ye çevir.
        renpy.change_language() kullanır (_preferences.language'a doğrudan yazmaz).
        \"\"\"
        try:
            current = getattr(_preferences, 'language', None)
            if current != "{language_code}":
                renpy.change_language("{language_code}")
        except Exception:
            pass

    # Oyun başladığında bu fonksiyonu çalıştır
    if _rl_force_{safe_code}_language not in config.start_callbacks:
        config.start_callbacks.append(_rl_force_{safe_code}_language)

# ============================================================
# PHASE 3: Persistent Override (Save File Protection)
# ============================================================
# init 0'da çalışır, gui.init (-2) SONRASI — güvenli.
# Bazı oyunlar kendi persistent değişkenlerini kullanır.
init python:
    try:
        if hasattr(persistent, "language"):
            persistent.language = "{language_code}"
        if hasattr(persistent, "game_language"):
            persistent.game_language = "{language_code}"
        if hasattr(persistent, "selected_language"):
            persistent.selected_language = "{language_code}"
    except Exception:
        pass
"""


            save_text_safely(Path(init_file), content, encoding='utf-8-sig', newline='\n')

            self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_created").replace("{path}", init_file))

        except Exception as e:
            self.log_message.emit("warning", self.config.get_ui_text("pipeline_lang_init_failed").format(error=e))







    def translate_existing_tl(
        self,
        tl_root_path: str,
        target_language: str,
        source_language: str = "auto",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        use_proxy: bool = False,
    ) -> PipelineResult:
        """
        Var olan tl/<dil> klasorundeki .rpy dosyalarini (Ren'Py SDK ile uretildi)
        dogrudan cevirir. Oyunun EXE'sine gerek yoktur.
        """
        # GUI ISO kodu (fr/en/tr) gonderir; Ren'Py klasor adi icin ters cevir
        reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
        target_iso = (target_language or "").lower()
        renpy_lang = reverse_lang_map.get(target_iso, target_iso)

        # Konfigure et
        self.target_language = target_iso
        self.source_language = source_language
        self.engine = engine
        self.use_proxy = use_proxy
        self.project_path = os.path.abspath(Path(tl_root_path).parent.parent) if tl_root_path else None

        # Stage: PARSING
        self._set_stage(PipelineStage.PARSING, self.config.get_ui_text("stage_parsing"))

        # tl_path / lang_dir coz
        p = Path(tl_root_path)
        lang_dir: Optional[Path] = None
        tl_path: Optional[Path] = None

        target_dir_names: List[str] = []
        for name in [renpy_lang, target_iso]:
            if name and name not in target_dir_names:
                target_dir_names.append(name)

        def matches_name(path_obj: Path) -> bool:
            return path_obj.name.lower() in target_dir_names

        # 1) Kullanici zaten tl/<lang> secmis
        if matches_name(p) and p.parent.name.lower() == "tl":
            lang_dir = p
            tl_path = p.parent
        # 2) Kullanici tl dizinini secmis (game/tl)
        elif p.name.lower() == "tl":
            tl_path = p
            for name in target_dir_names:
                candidate = tl_path / name
                if candidate.exists():
                    lang_dir = candidate
                    break
        # 3) Kullanici oyun/project root secmis
        if lang_dir is None and (p / "tl").exists():
            tl_path = p / "tl"
            for name in target_dir_names:
                candidate = tl_path / name
                if candidate.exists():
                    lang_dir = candidate
                    break
        # 4) Son care: secilen dizin altinda dil klasoru var mi?
        if lang_dir is None:
            for name in target_dir_names:
                candidate = p / name
                if candidate.exists():
                    lang_dir = candidate
                    tl_path = p if p.name.lower() == "tl" else p.parent if p.parent.name.lower() == "tl" else p
                    break
        # 5) Ad uyusmasa bile kullanici dogrudan dil klasorunu secmis olabilir
        if lang_dir is None and p.is_dir():
            try:
                has_rpy = next(p.rglob("*.rpy"), None) is not None
            except Exception:
                has_rpy = False
            if has_rpy:
                lang_dir = p
                tl_path = p.parent if p.parent else p

        if lang_dir is None:
            return PipelineResult(
                success=False,
                message=self.config.get_log_text('tl_dir_not_found', path=f"{p} ({'/'.join(target_dir_names)})"),
                stage=PipelineStage.ERROR,
            )

        if not lang_dir.exists():
            return PipelineResult(
                success=False,
                message=self.config.get_log_text('tl_dir_not_found', path=str(lang_dir)),
                stage=PipelineStage.ERROR,
            )

        # Bilgilendirici log
        self.log_message.emit(
            "info",
            self.config.get_log_text('tl_directory_info', tl_path=str(tl_path), lang_dir=lang_dir.name, input=target_language),
        )

        # Oyun dizinini tahmin et (tl/<lang> altindaysa bir ust = game)
        game_dir = None
        try:
            if lang_dir.parent.name.lower() == "tl":
                game_dir = lang_dir.parent.parent
            elif tl_path and tl_path.name.lower() == "tl":
                game_dir = tl_path.parent
        except Exception:
            game_dir = None

        tl_files = self.tl_parser.parse_directory(str(tl_path), lang_dir.name)

        # Yalnizca hedef dil altindaki dosyalari kabul et; diger dil klasorlerini haric tut
        target_tl_dir = os.path.normcase(os.path.join(str(tl_path), lang_dir.name))
        filtered_files: List[TranslationFile] = []
        for tl_file in tl_files:
            fp_norm = os.path.normcase(tl_file.file_path)
            if fp_norm.startswith(target_tl_dir):
                tl_file.entries = [
                    e for e in tl_file.entries
                    if os.path.normcase(e.file_path or tl_file.file_path).startswith(target_tl_dir)
                ]
                filtered_files.append(tl_file)
            else:
                self.log_message.emit("info", self.config.get_log_text('log_other_lang_skipped', path=tl_file.file_path))
        tl_files = filtered_files

        # Encode normalizasyonu (hedef dil klasoru)
        try:
            normalized = self._normalize_tl_encodings(str(lang_dir))
            if normalized:
                self.log_message.emit("info", self.config.get_log_text('log_tl_normalized', count=normalized))
                self.normalize_count = normalized
        except Exception as e:
            msg = self.config.get_log_text('encoding_normalize_failed', path=str(lang_dir), error=str(e))
            self.log_message.emit("warning", msg)
            self._log_error(msg)

        if not tl_files:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_files_not_found_parse"),
                stage=PipelineStage.ERROR,
            )

        # Cevrilecek girisleri topla
        all_entries: List[TranslationEntry] = []
        for tl_file in tl_files:
            all_entries.extend(tl_file.get_untranslated())

        # Diagnostics baslangic bilgisi
        try:
            self.diagnostic_report.project = os.path.basename(os.path.abspath(tl_root_path))
            self.diagnostic_report.target_language = self.target_language
            for tl_file in tl_files:
                for e in tl_file.entries:
                    fp = e.file_path or tl_file.file_path
                    self.diagnostic_report.add_extracted(fp, {
                        'text': e.original_text,
                        'line_number': e.line_number,
                        'context_path': getattr(e, 'context_path', [])
                    })
        except Exception:
            pass

        if not all_entries:
            stats = get_translation_stats(tl_files)
            if game_dir and game_dir.exists():
                self._create_language_init_file(str(game_dir))
                self._manage_runtime_hook()
            return PipelineResult(
                success=True,
                message=self.config.get_ui_text("pipeline_all_already_translated"),
                stage=PipelineStage.COMPLETED,
                stats=stats,
                output_path=str(lang_dir)
            )

        self.log_message.emit("info", self.config.get_ui_text("pipeline_entries_to_translate").replace("{count}", str(len(all_entries))))

        # Stage: TRANSLATING
        self._set_stage(PipelineStage.TRANSLATING, self.config.get_ui_text("stage_translating"))
        translations = self._translate_entries(all_entries)

        if not translations:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_translate_failed"),
                stage=PipelineStage.ERROR
            )

        # Stage: SAVING
        self._set_stage(PipelineStage.SAVING, self.config.get_ui_text("stage_saving"))
        saved_count = 0
        for tl_file in tl_files:
            file_translations: Dict[str, str] = {}
            for entry in tl_file.entries:
                tid = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                    entry.file_path, entry.line_number, entry.original_text
                )
                if tid in translations:
                    file_translations[tid] = translations[tid]
                elif entry.original_text in translations:
                    file_translations[entry.original_text] = translations[entry.original_text]

            if file_translations:
                success = self.tl_parser.save_translations(tl_file, file_translations)
                if success:
                    saved_count += 1
                    try:
                        for tid in file_translations.keys():
                            fp = tl_file.file_path
                            self.diagnostic_report.mark_written(fp, tid)
                    except Exception:
                        pass

        # Atomik segment çevirileri strings.json'a zaten ekleniyor (extra_translations)
        # _rl_segments.rpy artık oluşturulmuyor (v2.7.1 hotfix) — runtime hook yeterli
        _old_seg_path2 = os.path.join(str(lang_dir), '_rl_segments.rpy')
        if os.path.exists(_old_seg_path2):
            try:
                os.remove(_old_seg_path2)
                self.emit_log("info", "[AtomicSegments] Removed obsolete _rl_segments.rpy")
                _old_seg_rpyc2 = _old_seg_path2 + 'c'
                if os.path.exists(_old_seg_rpyc2):
                    os.remove(_old_seg_rpyc2)
            except Exception:
                pass

        # Final istatistikler
        tl_files_updated = self.tl_parser.parse_directory(str(tl_path), lang_dir.name)
        stats = get_translation_stats(tl_files_updated)

        # Diagnostics JSON yaz
        try:
            diag_path = os.path.join(str(lang_dir), 'diagnostics', f'diagnostic_{self.target_language}.json')
            self.diagnostic_report.write(diag_path)
            self.log_message.emit('info', self.config.get_log_text('log_diagnostic_written', path=diag_path))
        except Exception:
            pass

        # Hedef dil icin dil baslatici dosyasi olustur
        if game_dir and game_dir.exists():
            self._create_language_init_file(str(game_dir))

            # strings.json oluştur (Agresif kanca için) — atomik segmentler dahil
            self._generate_strings_json(tl_files_updated, str(lang_dir), extra_translations=translations)

            self._manage_runtime_hook()

        self._set_stage(PipelineStage.COMPLETED, self.config.get_ui_text("stage_completed"))
        summary = self.config.get_ui_text("pipeline_completed_summary").replace("{translated}", str(len(translations))).replace("{saved}", str(saved_count))
        if self.normalize_count:
            summary += f" | Normalize edilen tl dosyasi: {self.normalize_count}"

        return PipelineResult(
            success=True,
            message=summary,
            stage=PipelineStage.COMPLETED,
            stats=stats,
            output_path=str(lang_dir)
        )

    def _make_source_translatable(self, game_dir: str) -> int:
        """
        Kaynak .rpy dosyalarındaki UI metinlerini çevrilebilir hale getirir.
        textbutton "Text" -> textbutton _("Text")
        textbutton 'Text' -> textbutton _('Text')
        Bu işlem Ren'Py'ın translate komutunun bu metinleri yakalamasını sağlar.
        
        Returns: Değiştirilen dosya sayısı
        """
        # Çevrilebilir yapılması gereken pattern'ler
        # Her pattern: (regex_pattern, replacement)
        # 
        # Önemli Ren'Py UI Elemanları:
        # - textbutton: Tıklanabilir metin butonu
        # - text: Ekranda gösterilen metin
        # - tooltip: Fare üzerine gelince gösterilen ipucu
        # - label: Metin etiketi (nadiren çeviri gerektirir)
        # - notify: Bildirim mesajları (renpy.notify)
        # - action Notify: Action olarak bildirim
        # - title: Pencere başlığı
        # - message: Onay/hata mesajları
        #
        # NOT: Her pattern hem tek tırnak (') hem de çift tırnak (") destekler
        # ['\"] = tek veya çift tırnak eşleşir, \\1 ile aynı tırnak kullanılır
        #
        patterns = [
            # textbutton "text" veya textbutton 'text' -> textbutton _("text")
            # Ör: textbutton "Nap": veya textbutton 'Start' action Start()
            (r"(textbutton\s+)(['\"])([^'\"]+)\2(\s*:|\s+action|\s+style|\s+xalign|\s+yalign|\s+at\s)", 
             r'\1_(\2\3\2)\4'),
            
            # text "..." veya text '...' size/color/xpos/ypos/xalign/yalign/outlines/at ile devam eden
            # Ör: text "LOCKED" color "#FF6666" size 50
            # Ör: text 'Quit':
            # NOT: text "[variable]" gibi değişken içerenleri atla (skip_patterns ile)
            (r"(\btext\s+)(['\"])([^'\"\[\]{}]+)\2(\s*:|\s+size|\s+color|\s+xpos|\s+ypos|\s+xalign|\s+yalign|\s+outlines|\s+at\s|\s+font|\s+style)", 
             r'\1_(\2\3\2)\4'),
            
            # tooltip "text" veya tooltip 'text' -> tooltip _("text")
            # Ör: tooltip "Dev Console (Toggle)"
            (r"(tooltip\s+)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # renpy.notify("text") veya renpy.notify('text') -> renpy.notify(_("text"))
            # Ör: renpy.notify("Item added to inventory")
            (r"(renpy\.notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
             r'\1_(\2\3\2)\4'),
            
            # action Notify("text") veya Notify('text') -> action Notify(_("text"))
            # Ör: action Notify("Game saved!")
            (r"(Notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
             r'\1_(\2\3\2)\4'),
            
            # title="text" veya title='text' (screen title vb.)
            # Ör: title="Settings" veya frame title 'Options':
            (r"(title\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # message="text" veya message='text' (confirm screen vb.)
            # Ör: message="Are you sure you want to quit?"
            (r"(message\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # yes="text" (confirm)
            # Ör: yes="Yes" 
            (r"(\byes\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # no="text" (confirm)  
            # Ör: no="No"
            (r"(\bno\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # alt="text" (image alt text)
            # Ör: add "image.png" alt="A beautiful sunset"
            (r"(\balt\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
        ]
        
        # Atlanacak pattern'ler (zaten çevrilebilir veya değişken)
        # Hem tek (') hem çift (") tırnak desteklenir
        skip_patterns = [
            r'_\s*\(\s*[\'"]',    # Zaten çevrilebilir: _("text") veya _('text')
            r'[\'\"]\s*\+\s*[\'"]',    # String concatenation: "text" + "more"
            r'^\s*#',             # Yorum satırı
            r'^\s*$',             # Boş satır
            r'define\s+',         # define satırları
            r'default\s+',        # default satırları
            r'=\s*[\'"][^\'"]*[\'"]\s*$',  # Sadece atama: variable = "value"
            r'[\'"][^\'"]*\[[^\]]+\][^\'"]*[\'"]',  # Değişken içeren: "[player]"
            r'[\'"][^\'"]*\{[^\}]+\}[^\'"]*[\'"]',  # Tag içeren: "{b}text{/b}"
        ]
        
        modified_count = 0
        rpy_dir = os.path.join(game_dir, 'rpy')
        
        if not os.path.isdir(rpy_dir):
            # rpy alt klasörü yoksa direkt game klasörünü tara
            rpy_dir = game_dir
        
        try:
            for root, dirs, files in os.walk(rpy_dir):
                # tl klasörünü atla
                if 'tl' in dirs:
                    dirs.remove('tl')
                
                for filename in files:
                    if not filename.endswith('.rpy'):
                        continue

                    filepath = os.path.join(root, filename)

                    # GÜVENLİK: 'renpy/' klasörü altındaki dosyaları ASLA değiştirme!
                    if os.path.sep + 'renpy' + os.path.sep in filepath or filepath.endswith(os.path.sep + 'renpy'):
                        continue
                    
                    try:
                        # Her dosya için yedek oluştur
                        # GÜVENLİK YAMASI: Yedekleme
                        backup_path = filepath + ".bak"
                        if not os.path.exists(backup_path):
                            try:
                                shutil.copy2(filepath, backup_path)
                            except Exception as e:
                                self.log_message.emit("warning", self.config.get_log_text('backup_failed_skipped', filename=filename))
                                continue  # Dosya işlenmeden atlanıyor
                        

                        content = read_text_safely(Path(filepath))
                        if content is None:
                            self.log_message.emit('warning', f"{filename} dosyası okunamadı (encoding)")
                            continue
                        
                        original_content = content
                        
                        # Her pattern için değiştir
                        for pattern, replacement in patterns:
                            # Satır satır işle
                            lines = content.split('\n')
                            new_lines = []
                            
                            for line in lines:
                                # Atlanacak satırları kontrol et
                                should_skip = False
                                for skip in skip_patterns:
                                    if re.search(skip, line):
                                        should_skip = True
                                        break
                                
                                if not should_skip:
                                    line = re.sub(pattern, replacement, line)
                                
                                new_lines.append(line)
                            
                            content = '\n'.join(new_lines)
                        
                        # Değişiklik olduysa kaydet
                        if content != original_content:
                            save_text_safely(Path(filepath), content, encoding='utf-8-sig', newline='\n')
                            modified_count += 1
                    
                    except Exception as e:
                        msg = f"Dosya işlenemedi {filename}: {e}"
                        self.log_message.emit("warning", msg)
                        self._log_error(msg)
                        continue
            
            if modified_count > 0:
                self.log_message.emit("info", self.config.get_log_text('source_files_made_translatable', count=modified_count))
            
        except Exception as e:
            self.log_message.emit("warning", self.config.get_log_text('source_files_error', error=str(e)))
        
        return modified_count
    
    def _run_extraction(self, project_path: str) -> bool:
        """RPA arşivlerini unrpa ile aç (tüm platformlarda çalışır)."""
        try:
            self.log_message.emit("info", self.config.get_log_text('unren_starting'))
            
            # unrpa kütüphanesini kullan
            from src.utils.unrpa_adapter import UnrpaAdapter
            from pathlib import Path
            
            adapter = UnrpaAdapter()
            if not adapter.is_available():
                self.log_message.emit("error", self.config.get_log_text('log_unrpa_not_installed'))
                return False
            
            # game dizinini bul
            project_path_obj = Path(project_path)
            game_dir = project_path_obj / "game"
            
            if not game_dir.exists():
                if project_path_obj.name == "game":
                    game_dir = project_path_obj
                else:
                    game_dir = project_path_obj
            
            self.log_message.emit("info", self.config.get_log_text('log_rpa_extracting', path=game_dir))
            
            try:
                success = adapter.extract_game(game_dir)
                
                if success:
                    self.log_message.emit("info", self.config.get_log_text('unren_completed'))
                    return True
                else:
                    # RPA dosyası bulunamadı veya zaten açılmış
                    self.log_message.emit("info", self.config.get_log_text('log_rpa_not_found_or_extracted'))
                    # rpyc dosyaları varsa devam et
                    if self._has_rpyc_files(str(game_dir)):
                        self.log_message.emit("info", self.config.get_log_text('log_rpyc_continue'))
                        return True
                    return False
                    
            except Exception as e:
                self.log_message.emit("error", self.config.get_log_text('log_rpa_error', error=str(e)))
                # Son şans - rpyc dosyaları varsa devam et
                if self._has_rpyc_files(str(game_dir)):
                    self.log_message.emit("info", self.config.get_log_text('log_rpyc_fallback_continue'))
                    return True
                return False
            
        except Exception as e:
            self.log_message.emit("error", self.config.get_log_text('unren_general_error', error=str(e)))
            return False
    
    def _cleanup_legacy_mod_files(self, game_dir: str) -> int:
        """
        UnRen'in eklediği mod dosyalarını temizle.
        Bu dosyalar bazı oyunlarla uyumsuz (örn: 'Screen quick_menu is not known' hatası).
        
        Silinen dosyalar:
        - unren-console.rpy / .rpyc
        - unren-qmenu.rpy / .rpyc
        - unren-quick.rpy / .rpyc
        - unren-rollback.rpy / .rpyc
        - unren-skip.rpy / .rpyc
        
        Returns: Silinen dosya sayısı
        """
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
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.log_message.emit("info", self.config.get_log_text('unren_mod_deleted', filename=filename))
                    deleted_count += 1
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('unren_mod_delete_failed', filename=filename, error=str(e)))
        
        if deleted_count > 0:
            self.log_message.emit("info", self.config.get_log_text('unren_mod_cleanup_done', count=deleted_count))
        
        return deleted_count
    
    def _run_translate_command(self, project_path: str) -> bool:
        """Kaynak dosyaları parse edip tl/ klasörüne çeviri şablonları oluştur
        
        ÖNEMLİ: Ren'Py String Translation sistemi kullanılıyor.
        Bu sistemde aynı string sadece BİR KERE tanımlanabilir (global tekil).
        Bu nedenle tüm stringler (diyalog + UI) tek bir dosyada toplanıyor.
        """
        try:
            self.log_message.emit("info", self.config.get_log_text('log_translation_files_creating', lang=self.target_language))
            
            # Dil ismini belirle (ISO kodu yerine klasör ismi)
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            renpy_lang = reverse_lang_map.get(self.target_language.lower(), self.target_language)
            
            game_dir = os.path.join(project_path, 'game')
            tl_dir = os.path.join(game_dir, 'tl', renpy_lang)
            
            # tl dizini oluştur
            os.makedirs(tl_dir, exist_ok=True)
            
            # Kaynak dosyaları parse et
            from src.core.parser import RenPyParser
            parser = RenPyParser(self.config)
            
            # 1. Parse 'game' directory
            # Parse 'game' directory and flatten results
            parse_results = parser.parse_directory(game_dir)
            source_texts = []
            for i, (file_path, entries) in enumerate(parse_results.items()):
                for entry in entries:
                    entry['file_path'] = str(file_path)
                    source_texts.append(entry)
                
                # Yield periodically to keep UI responsive
                if i % 50 == 0:
                    time.sleep(0.001)

            # Resolve feature flags once so they can be reused for engine/common scanning
            use_deep = getattr(self, 'include_deep_scan', False)
            use_rpyc = getattr(self, 'include_rpyc', False)
            
            if self.config and hasattr(self.config, 'translation_settings'):
                settings = self.config.translation_settings
                # If explicit override wasn't set (or False), fallback to config
                if not use_deep:
                    use_deep = getattr(settings, 'enable_deep_scan', getattr(settings, 'use_deep_scan', True))
                
                # USER REQUEST: Force enable RPYC scanning to ensure maximum coverage
                # We always scan RPYC files to catch strings missing from decompiled RPYs
                use_rpyc = True 

            # Remove any entries that originate from game/renpy/common — we'll re-parse them with
            # a temporary parser that forces UI scanning for engine common strings.
            renpy_common_path = os.path.normpath(os.path.abspath(os.path.join(game_dir, 'renpy', 'common')))
            if os.path.isdir(renpy_common_path):
                before_len = len(source_texts)
                def abs_path(p):
                    try:
                        return os.path.normpath(os.path.abspath(str(p)))
                    except Exception:
                        return ''
                source_texts = [e for e in source_texts if not abs_path(e.get('file_path', '')).startswith(renpy_common_path)]
                after_len = len(source_texts)
                if before_len != after_len:
                    self.log_message.emit('debug', f'Removed {before_len - after_len} entries from initial game parse that belong to renpy/common to avoid duplicates')

            # Explicitly scan 'renpy/common' if it exists in project root
            renpy_dir = os.path.join(project_path, 'renpy')
            renpy_common = os.path.join(renpy_dir, 'common')

            if os.path.isdir(renpy_common):
                self.log_message.emit("info", self.config.get_log_text('log_scanning_renpy_common', path=renpy_common))
                # Parse 'renpy/common' and flatten results
                # Use temporary parser with forced UI scanning so engine UI strings are included
                from src.core.parser import RenPyParser
                from src.utils.config import ConfigManager as LocalConfig
                import copy
                temp_conf = LocalConfig()
                temp_conf.translation_settings = copy.deepcopy(self.config.translation_settings)
                temp_conf.translation_settings.translate_ui = True
                temp_parser = RenPyParser(temp_conf)
                try:
                    common_results = temp_parser.parse_directory(renpy_common)
                except Exception:
                    common_results = parser.parse_directory(renpy_common)
                
                # Filter out obvious technical entries that might have slipped through
                for file_path, entries in common_results.items():
                    valid_entries = []
                    for entry in entries:
                        txt = entry.get('text', '')
                        # Engine strings in common are usually UI: "Quit", "Are you sure?", etc.
                        # If it has heavy punctuation, glob markers, or looks like code, skip it.
                        if re.search(r'[\\#\[\](){}|*+?^$]', txt): 
                             if len(txt) > 10 or re.search(r'\*\*?/\*\*?|\.[a-z0-9]+$', txt):
                                 continue
                        
                        # Skip common technical words that are not UI
                        if txt.lower().strip() in parser.renpy_technical_terms:
                            continue
                            
                        valid_entries.append(entry)
                    
                    for entry in valid_entries:
                        entry['file_path'] = str(file_path)
                        entry['is_engine_common'] = True
                        source_texts.append(entry)
                # If engine/common ships only .rpyc files, optionally parse them too
                if use_rpyc:
                    try:
                        from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                        rpyc_results = extract_texts_from_rpyc_directory(renpy_common)
                        for file_path, entries in rpyc_results.items():
                            for entry in entries:
                                txt = entry.get('text', '')
                                if re.search(r'[\\#\[\](){}|*+?^$]', txt):
                                    if len(txt) > 10 or re.search(r'\*\*?/\*\*?|\.[a-z0-9]+$', txt):
                                        continue
                                if txt.lower().strip() in parser.renpy_technical_terms:
                                    continue

                                patched = dict(entry)
                                patched['file_path'] = str(file_path)
                                patched['is_engine_common'] = True
                                if 'text_type' in patched and 'type' not in patched:
                                    patched['type'] = patched.get('text_type')
                                source_texts.append(patched)
                    except Exception as exc:
                        self.log_message.emit("warning", self.config.get_log_text('log_engine_common_scan_failed', error=str(exc)))
            # SDK scanning removed (v2.5.0)
            pass

            # --- FIX START: Initialize and Populate Results ---
            deep_results = {}
            rpyc_results = {}
            existing_texts = {e['text'] for e in source_texts} # For dedup
            deep_count = 0

            # 3. Deep Scan Execution
            # Check config (default to True if not set)
            if use_deep:
                self.log_message.emit("info", self.config.get_log_text('deep_scan_running_short'))
                deep_results = parser.extract_from_directory_with_deep_scan(game_dir)

            # 4. RPYC Execution
            if use_rpyc:
                self.log_message.emit("warning", "⏳ Scanning .rpyc (Binary) database... This may take time depending on file size. Please wait, program is not frozen!")
                self.log_message.emit("info", self.config.get_log_text('rpyc_scan_running'))
                # Import here to avoid circular imports if any
                try:
                    from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                    rpyc_results = extract_texts_from_rpyc_directory(game_dir)
                    self.log_message.emit("success", f"✅ .rpyc scan completed. {len(rpyc_results)} files processed.")
                except ImportError:
                    self.log_message.emit("warning", self.config.get_log_text('rpyc_module_not_found'))
            # --- FIX END ---
            
            # --- EKSİK OLAN BİRLEŞTİRME KODU BAŞLANGICI ---

            # Deep Scan Sonuçlarını Birleştir
            if deep_results:
                self.log_message.emit("info", self.config.get_log_text('deep_scan_merging'))
                for file_path, entries in deep_results.items():
                    for entry in entries:
                        if entry.get('is_deep_scan'):
                            entry['file_path'] = str(file_path)
                            source_texts.append(entry)

            # RPYC Sonuçlarını Birleştir
            if rpyc_results:
                self.log_message.emit("info", self.config.get_log_text('rpyc_data_merging'))
                # Mevcut metinleri kontrol et (tekrarı önlemek için)
                existing_texts = {e.get('text') for e in source_texts}

                for file_path, entries in rpyc_results.items():
                    for entry in entries:
                        text = entry.get('text', '')
                        if text and text not in existing_texts:
                            entry['file_path'] = str(file_path)
                            source_texts.append(entry)
                            existing_texts.add(text)

            # --- EKSİK OLAN BİRLEŞTİRME KODU BİTİŞİ ---
            
            if not source_texts:
                self.log_message.emit("warning", self.config.get_log_text('no_translatable_texts'))
                return False
            
            self.log_message.emit("info", self.config.get_log_text('texts_found_creating', count=len(source_texts)))
            
            # Check for existing translations in the tl folder to avoid duplicates
            # If a string is already in options.rpy or screens.rpy, adding it to strings.rpy causes a crash
            existing_global_strings = set()
            try:
                lang_tl_path = os.path.join(game_dir, 'tl', renpy_lang)
                if os.path.isdir(lang_tl_path):
                    # Direct scan for 'old "..."' and 'new "..."' pairs in existing .rpy files
                    # Patterns for old-new pairs in strings
                    # Improved regex to handle various indentation and optional spaces
                    string_pair_pattern = re.compile(r'^\s*old\s+"(?P<old>.*?)"\s*\n\s*new\s+"(?P<new>.*?)"\s*$', re.MULTILINE | re.DOTALL)
                    
                    # Dialogue format in tl files (comments with # and then the translation)
                    dialogue_block_pat = re.compile(r'^\s*#\s*(?:\w+\s+)?"(?P<old>.*?)"\s*\n\s*(?:\w+\s+)?"(?P<new>.*?)"\s*$', re.MULTILINE | re.DOTALL)
                    
                    for root, dirs, files in os.walk(lang_tl_path):
                        for filename in files:
                            # Skip compiled files
                            if not filename.endswith('.rpy'):
                                continue
                            
                            filepath = os.path.join(root, filename)
                            try:
                                with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
                                    content = f.read()
                                
                                # Find all 'old/new' pairs
                                for match in string_pair_pattern.finditer(content):
                                    old_text = match.group('old')
                                    new_text = match.group('new')
                                    
                                    # ONLY skip if new_text is NOT empty and NOT equal to old_text (unless intentional)
                                    if old_text and new_text and new_text.strip():
                                        # Normalize newlines and unescape for consistency
                                        old_text = old_text.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                                        existing_global_strings.add(old_text)
                                
                                # Dialogue check
                                for m2 in dialogue_block_pat.finditer(content):
                                    old_t = m2.group('old')
                                    new_t = m2.group('new')
                                    if old_t and new_t and new_t.strip():
                                        old_t = old_t.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                                        existing_global_strings.add(old_t)
                                        
                                self.logger.debug(f"Scanned {filepath}: found {len(existing_global_strings)} actively translated entries")
                            except Exception as fe:
                                self.logger.debug(f"Failed to scan {filepath}: {fe}")
                    
                    if existing_global_strings:
                        self.log_message.emit("info", f"Found {len(existing_global_strings)} conflicting strings in existing translation files, skipping them for strings.rpy.")
            except Exception as e:
                self.logger.warning(f"Existing TL scan failed: {e}")

            # TÜM metinleri GLOBAL olarak tekil tut
            # Ren'Py String Translation'da aynı string sadece 1 kere tanımlanabilir
            # Prefers entries marked as engine_common if duplicates occur
            seen_map = {}
            for entry in source_texts:
                text = entry.get('text', '')
                if not text:
                    continue
                
                # Skip if already exists in other .rpy files in tl/ folder
                if text in existing_global_strings:
                    continue
                    
                existing = seen_map.get(text)
                if not existing:
                    seen_map[text] = entry
                else:
                    # If the existing one is not engine_common but the new one is, prefer the new
                    if not existing.get('is_engine_common') and entry.get('is_engine_common'):
                        seen_map[text] = entry
                    # Prefer deep_scan or contextful entries over generic ones if needed
                    elif not existing.get('is_deep_scan') and entry.get('is_deep_scan'):
                        seen_map[text] = entry

            all_entries = list(seen_map.values())
            
            self.log_message.emit("info", self.config.get_log_text('unique_texts_found', count=len(all_entries)))
            
            # Tüm stringleri tek strings.rpy dosyasına yaz
            if all_entries:
                try:
                    # Pass renpy_lang to ensure correct header in strings.rpy
                    strings_content = self._generate_all_strings_file(all_entries, game_dir, lang_name=renpy_lang)
                    if strings_content:
                        # Atomic Write Pattern: Write to temp -> Rename
                        # This prevents file corruption if the process crashes during write
                        strings_path = os.path.join(tl_dir, 'strings.rpy')
                        temp_path = strings_path + '.tmp'
                        
                        # Phase 1: Write to temp file (Critical IO)
                        try:
                            with open(temp_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                                f.write(strings_content)
                                f.flush()
                                os.fsync(f.fileno()) # Force write to physical disk
                        except Exception as write_err:
                            self.logger.error(f"Failed to write to temp file {temp_path}: {write_err}")
                            if os.path.exists(temp_path):
                                try:
                                    os.remove(temp_path)
                                except Exception:
                                    pass
                            raise write_err

                        # Phase 2: Robust Atomic Swap (Retry Loop)
                        # Handles occasional 'Access Denied' due to AV/Scanners locking the file
                        success = False
                        rename_error = None
                        max_retries = 5
                        
                        for i in range(max_retries):
                            try:
                                if os.path.exists(strings_path):
                                    os.replace(temp_path, strings_path)
                                else:
                                    os.rename(temp_path, strings_path)
                                success = True
                                break # Success, exit loop
                            except OSError as e:
                                rename_error = e
                                # Simple backoff: 0.1, 0.2, 0.3s...
                                time.sleep(0.1 + (i * 0.1))
                        
                        if not success:
                            # CRITICAL: Do NOT delete the temp file. Save the user's data!
                            err_msg = (
                                f"CRITICAL FILE ERROR: Could not rename '{os.path.basename(temp_path)}' to 'strings.rpy' after {max_retries} attempts.\n"
                                f"Access Denied or File Locked.\n"
                                f"YOUR DATA IS SAFE HERE: {temp_path}\n"
                                f"Please manually rename this file to 'strings.rpy'."
                            )
                            self.log_message.emit("error", err_msg)
                            # We raise the error to notify the pipeline, but the file is preserved
                            if rename_error:
                                raise rename_error
                            else:
                                raise OSError("Unknown rename failure")

                        self.log_message.emit("info", self.config.get_log_text('strings_rpy_created', count=len(all_entries)))
                        return True
                except Exception as e:
                    self.log_message.emit("error", self.config.get_log_text('strings_rpy_error', error=str(e)))
                    return False
            
            return False
                
        except Exception as e:
            self.log_message.emit("error", self.config.get_log_text('translation_file_error', error=str(e)))
            return False
    
    def _generate_all_strings_file(self, entries: List[dict], game_dir: str, lang_name: str = None) -> str:
        """
        Tüm çevrilecek metinleri (diyalog + UI) tek bir strings.rpy dosyasında topla.
        
        Ren'Py String Translation formatı kullanılır:
        translate language strings:
            old "original text"
            new "translated text"
        
        Bu format ID gerektirmez ve her yerde çalışır.
        """
        formatter = RenPyOutputFormatter()
        skipped = 0
        lines = []
        lines.append("# Translation strings file")
        lines.append("# Auto-generated by RenLocalizer")
        lines.append("# Using Ren'Py String Translation format for maximum compatibility")
        lines.append("")
        
        target_lang = lang_name if lang_name else self.target_language
        lines.append(f"translate {target_lang} strings:")
        lines.append("")
        
        rel_path_cache = {}
        seen_texts = set()
        for i, entry in enumerate(entries):
            text = entry.get('text', '')
            if not text or formatter._should_skip_translation(text):
                skipped += 1
                continue
                
            # Global deduplication by text content to prevent bloating
            if text in seen_texts:
                continue
            seen_texts.add(text)
            
            file_path = entry.get('file_path', '')
            line_num = entry.get('line_number', 0)
            character = entry.get('character', '')
            # 'type' is not standard in parser.py output, it uses 'text_type'
            text_type = entry.get('text_type', 'unknown')
            is_nontranslatable_identifier = self._is_nontranslatable_identifier_entry(entry)
            
            escaped_text = self._escape_rpy_string(text)
            
            if file_path in rel_path_cache:
                rel_path = rel_path_cache[file_path]
            else:
                rel_path = 'unknown'
                if file_path:
                    try:
                        rel_path = os.path.relpath(file_path, game_dir)
                    except ValueError:
                        rel_path = os.path.abspath(file_path)
                rel_path_cache[file_path] = rel_path
            
            # Kaynak bilgisi ve karakter adını yorum olarak ekle
            comment_parts = [f"{rel_path}:{line_num}"]
            if character:
                comment_parts.append(f"({character})")
            if text_type and text_type != 'dialogue':
                comment_parts.append(f"[{text_type}]")
            if entry.get('is_engine_common'):
                comment_parts.append('[engine_common]')
            
            lines.append(f"    # {' '.join(comment_parts)}")
            # Check cache for existing translation to support seamless resume
            cached_translation = ""
            if self.translation_manager and not is_nontranslatable_identifier:
                # Cache lookup needs to match the key logic in translation_manager
                # (Engine, Source, Target, Text) -> Result
                # We do a 'best effort' check here.
                # Assuming engine is consistent or we just want *any* translation for this text/mylang.
                
                # Direct cache access via manager helper if available, or manual lookup
                # Since cache keys include engine/source/target, we iterate to find a match for current target/text
                # This is slightly expensive but worth it for resume UX.
                
                # Fast path: Try with current engine settings
                api_target = RENPY_TO_API_LANG.get(self.target_language, self.target_language)
                api_source = RENPY_TO_API_LANG.get(self.source_language, self.source_language)
                
                # Check for cached result
                cache_key = (self.engine.value, api_source, api_target, text)
                cached_res = self.translation_manager._cache.get(cache_key)
                
                # If not found with exact key, try loose match (any engine, same languages)
                if not cached_res:
                    for k, v in self.translation_manager._cache.items():
                        # buffer check: k[2] is target, k[3] is original text
                        if len(k) >= 4 and k[2] == api_target and k[3] == text:
                            cached_res = v
                            break
                            
                if cached_res and cached_res.success:
                    cached_translation = self._escape_rpy_string(cached_res.translated_text)

            if is_nontranslatable_identifier:
                cached_translation = escaped_text

            lines.append(f'    old "{escaped_text}"')
            lines.append(f'    new "{cached_translation}"')
            lines.append("")
            
            # Yield GIL periodically to keep UI alive
            if i % 100 == 0:
                time.sleep(0.001)
        
        if skipped:
            try:
                self.log_message.emit("debug", self.config.get_log_text('technical_entries_skipped', count=skipped))
            except Exception:
                pass

        return '\n'.join(lines)
    
    def _protect_glossary_terms(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Sözlük terimlerini Unicode bracket placeholder ile korur ve karşılıklarını saklar.
        
        v3.4: [[g0]] formatı yerine ⟦RLPH{ns}_gN⟧ formatına geçildi.
        Eski format Google Translate tarafından kolayca bozuluyordu çünkü
        [[ ]] çift köşeli parantezler çeviri motorları için anlamlı değildi.
        Yeni format, syntax_guard ile aynı Unicode matematiksel parantez (U+27E6/U+27E7)
        kullanır — Google bunlara "tanımsız sembol" olarak dokunmaz.
        """
        if not self.config or not hasattr(self.config, 'glossary') or not self.config.glossary:
            return text, {}
            
        import uuid
        placeholders = {}
        counter = 0
        token_namespace = uuid.uuid4().hex[:6].upper()
        # En uzun terimler önce (çakışmayı önlemek için)
        sorted_terms = sorted(self.config.glossary.items(), key=lambda x: -len(x[0]))
        
        result = text
        for src, dst in sorted_terms:
            if not src or not dst: continue
            
            # Sadece tam kelime eşleşmesi (\b)
            pattern = re.compile(r'(?i)\b' + re.escape(src) + r'\b')
            
            def replace_func(match):
                nonlocal counter
                key = f"\u27e6RLPH{token_namespace}_G{counter}\u27e7"
                placeholders[key] = dst  # Hedef çeviriyi yer tutucu sözlüğüne koy!
                counter += 1
                return key
                
            result = pattern.sub(replace_func, result)
            
        return result, placeholders

    def _escape_rpy_string(self, text: str) -> str:
        """Ren'Py string formatı için escape et"""
        if not text:
            return text
        
        # Escape sequences
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\t', '\\t')
        
        return text

    def _is_nontranslatable_identifier_entry(self, entry) -> bool:
        """style_prefix gibi kimlik/anahtar tipindeki girdiler çevrilmemeli."""
        try:
            if isinstance(entry, dict):
                character = (entry.get('character') or '').strip().lower()
            else:
                character = (getattr(entry, 'character', '') or '').strip().lower()
            return character == 'style_prefix'
        except Exception:
            return False
    
    def _translate_entries(self, entries: List[TranslationEntry]) -> Dict[str, str]:
        """Girişleri çevir (placeholder koruması zorunlu)."""
        from src.core.translator import protect_renpy_syntax
        from src.core.syntax_guard import split_delimited_text, rejoin_delimited_text, split_angle_pipe_groups, rejoin_angle_pipe_groups
        translations = {}
        self._last_atomic_segments = {}  # v2.7.1: Delimiter atomik segment çiftleri
        formatter = RenPyOutputFormatter()

        # Teknik/yer tutucu metinleri çeviri kuyruğundan ayıkla
        filtered_entries: List[TranslationEntry] = []
        for entry in entries:
            if self._is_nontranslatable_identifier_entry(entry):
                continue
            if formatter._should_skip_translation(entry.original_text):
                continue
            filtered_entries.append(entry)

        skipped = len(entries) - len(filtered_entries)
        if skipped:
            self.log_message.emit("debug", self.config.get_log_text('placeholder_excluded', count=skipped))

        entries = filtered_entries
        total = len(entries)

        # Connect all translators to the pipeline's log signal and stop callback
        self.translation_manager.should_stop_callback = lambda: self.should_stop
        for engine_type, translator in self.translation_manager.translators.items():
            if hasattr(translator, 'status_callback'):
                translator.status_callback = self.log_message.emit
            if hasattr(translator, 'should_stop_callback'):
                translator.should_stop_callback = lambda: self.should_stop
        if total == 0:
            # Final Cache Kaydı
            self.translation_manager.save_cache(cache_file)
            self.log_message.emit("info", self.config.get_log_text('log_cache_saved', path=cache_file, count=len(translations)))

            return translations

        # Batch çeviri için hazırla
        batch_size = self.config.translation_settings.max_batch_size
        
        # Optimize for AI: Use the user-defined ai_batch_size from settings
        if self.engine in (TranslationEngine.OPENAI, TranslationEngine.GEMINI, TranslationEngine.LOCAL_LLM):
            batch_size = getattr(self.config.translation_settings, 'ai_batch_size', 50)
            self.log_message.emit("debug", f"AI engine detected, using batch size: {batch_size}")

        api_target_lang = RENPY_TO_API_LANG.get(self.target_language, self.target_language)
        
        # =====================================================================
        # SMART LANGUAGE DETECTION
        # =====================================================================
        # When source_language is "auto", we detect it once at the start instead
        # of letting Google guess on each request. This prevents short texts like
        # "OK", "Yes", or character names from being incorrectly detected.
        # =====================================================================
        api_source_lang = RENPY_TO_API_LANG.get(self.source_language, self.source_language)
        
        if self.source_language.lower() == "auto" and self.engine == TranslationEngine.GOOGLE:
            self.log_message.emit("info", self.config.get_log_text(
                'smart_detect_starting', 
                "[Smart Detect] Kaynak dil tespit ediliyor..."
            ))
            
            # Get text samples from entries
            text_samples = [e.original_text for e in entries]
            
            # Detect using Google Translator
            translator = self.translation_manager.translators.get(TranslationEngine.GOOGLE)
            if not translator:
                translator = GoogleTranslator(config_manager=self.config)
                self.translation_manager.add_translator(TranslationEngine.GOOGLE, translator)
            
            try:
                # Create a specialized translator just for detection to avoid session/loop conflicts
                # This prevents the 'Event loop is closed' error on the main translator
                detection_translator = GoogleTranslator(config_manager=self.config)
                
                # Create temporary event loop for detection
                detect_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(detect_loop)
                
                detected_lang = detect_loop.run_until_complete(
                    detection_translator.detect_language(text_samples, target_lang=api_target_lang)
                )
                
                # Close the temporary loop and the detection translator's session
                detect_loop.run_until_complete(detection_translator.close_session())
                detect_loop.close()
                
                if detected_lang:
                    api_source_lang = detected_lang
                    self.log_message.emit("info", self.config.get_log_text(
                        'smart_detect_success',
                        f"[Smart Detect] ✓ Kaynak dil tespit edildi: {detected_lang.upper()}"
                    ))
                else:
                    self.log_message.emit("warning", self.config.get_log_text(
                        'smart_detect_fallback',
                        "[Smart Detect] Güven eşiği geçilemedi, 'auto' modunda devam ediliyor."
                    ))
                    api_source_lang = "auto"
            except Exception as e:
                self.logger.warning(f"Smart language detection failed: {e}")
                api_source_lang = "auto"

        # Cache path management (Global vs Local)
        should_use_global_cache = getattr(self.config.translation_settings, 'use_global_cache', True)
        
        if should_use_global_cache:
            # Create a project name based ID (last part of project_path)
            project_name = os.path.basename(self.project_path.rstrip('/\\'))
            if not project_name:
                project_name = "default_project"
            
            # Use program directory (next to run.py/executable)
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Check if frozen (PyInstaller)
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            
            base_cache_dir = os.path.join(app_dir, getattr(self.config.translation_settings, 'cache_path', 'cache'))
            cache_dir = os.path.join(base_cache_dir, project_name, self.target_language)
            self.log_message.emit("info", f"Using global portable cache profile: [{project_name}]")
        else:
            # Standard path: game/tl/<lang>/translation_cache.json
            cache_dir = os.path.join(self.project_path, 'game', 'tl', self.target_language)
            self.log_message.emit("info", "Using local project-specific cache.")

        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, "translation_cache.json")
        
        # Load existing cache for resume
        self.translation_manager.load_cache(cache_file)

        if total == 0:
            # Final Cache Kaydı
            self.translation_manager.save_cache(cache_file)
            return translations

        self.log_message.emit("info", self.config.get_log_text('translation_lang_api', lang=self.target_language, api=api_target_lang))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Ensure translator is registered; fallback to Google/DeepL defaults
        if self.engine == TranslationEngine.GOOGLE and self.engine not in self.translation_manager.translators:
            gt = GoogleTranslator(config_manager=self.config, proxy_manager=getattr(self.translation_manager, "proxy_manager", None))
            self.translation_manager.add_translator(TranslationEngine.GOOGLE, gt)
        if self.engine == TranslationEngine.DEEPL and self.engine not in self.translation_manager.translators:
            deepl_key = getattr(getattr(self.config, "api_keys", None), "deepl_api_key", "") or ""
            dt = DeepLTranslator(api_key=deepl_key, proxy_manager=getattr(self.translation_manager, "proxy_manager", None), config_manager=self.config)
            dt.status_callback = self.log_message.emit
            self.translation_manager.add_translator(TranslationEngine.DEEPL, dt)

        # AI Translators Lazy Init
        if self.engine == TranslationEngine.OPENAI and self.engine not in self.translation_manager.translators:
            # Determine correct API key based on Base URL
            # Users might enter DeepSeek key in its own field but run it via OpenAI engine (compatible mode)
            base_url = self.config.translation_settings.openai_base_url
            api_key_to_use = self.config.api_keys.openai_api_key

            if base_url and "deepseek" in base_url.lower():
                ds_key = getattr(self.config.api_keys, "deepseek_api_key", "")
                if ds_key:
                    self.log_message.emit("info", self.config.get_log_text('log_deepseek_mode'))
                    api_key_to_use = ds_key
                else:
                    self.log_message.emit("info", self.config.get_log_text('log_deepseek_fallback'))

            t = OpenAITranslator(
                api_key=api_key_to_use,
                model=self.config.translation_settings.openai_model,
                base_url=base_url,
                proxy_manager=getattr(self.translation_manager, "proxy_manager", None),
                config_manager=self.config,
                temperature=self.config.translation_settings.ai_temperature,
                timeout=self.config.translation_settings.ai_timeout,
                max_tokens=self.config.translation_settings.ai_max_tokens
            )
            t.status_callback = self.log_message.emit
            self.translation_manager.add_translator(TranslationEngine.OPENAI, t)

        if self.engine == TranslationEngine.GEMINI and self.engine not in self.translation_manager.translators:
            t = GeminiTranslator(
                api_key=self.config.api_keys.gemini_api_key,
                model=self.config.translation_settings.gemini_model,
                safety_level=self.config.translation_settings.gemini_safety_settings,
                proxy_manager=getattr(self.translation_manager, "proxy_manager", None),
                config_manager=self.config,
                temperature=self.config.translation_settings.ai_temperature,
                timeout=self.config.translation_settings.ai_timeout,
                max_tokens=self.config.translation_settings.ai_max_tokens
            )
            # Add fallback to Google
            fallback = GoogleTranslator(getattr(self.translation_manager, "proxy_manager", None), self.config)
            fallback.status_callback = self.log_message.emit
            t.set_fallback_translator(fallback)
            t.status_callback = self.log_message.emit
            self.translation_manager.add_translator(TranslationEngine.GEMINI, t)

        if self.engine == TranslationEngine.LOCAL_LLM and self.engine not in self.translation_manager.translators:
            t = LocalLLMTranslator(
                model=self.config.translation_settings.local_llm_model,
                base_url=self.config.translation_settings.local_llm_url,
                proxy_manager=getattr(self.translation_manager, "proxy_manager", None),
                config_manager=self.config,
                temperature=self.config.translation_settings.ai_temperature,
                timeout=self.config.translation_settings.ai_timeout,
                max_tokens=self.config.translation_settings.ai_max_tokens
            )
            t.status_callback = self.log_message.emit
            self.translation_manager.add_translator(TranslationEngine.LOCAL_LLM, t)

        # ================================================================
        # v2.7.1: Auto-protect character names — glossary'ye ekle
        # ================================================================
        _auto_names_added = 0
        if getattr(self.config.translation_settings, 'auto_protect_character_names', True):
            existing_glossary = self.config.glossary if hasattr(self.config, 'glossary') and self.config.glossary else {}
            existing_lower = {k.lower() for k in existing_glossary}
            char_names: set = set()
            for entry in entries:
                c = getattr(entry, 'character', '') or ''
                c = c.strip()
                # Değişken isimleri / enterpolasyon değil, gerçek isimler
                # Boşluklu isimler de kabul edilir (örn. "Mary Jane", "Old Man")
                if (c and len(c) >= 2 and not c.startswith('[') and not c.startswith('{')
                        and not c.startswith('$')
                        and c.lower() not in existing_lower
                        and c[0].isupper()):  # İsimler büyük harfle başlar
                    char_names.add(c)
            if char_names:
                # Thread-safe glossary update via config lock if available
                _lock = getattr(self.config, '_lock', None)
                if _lock:
                    _lock.acquire()
                try:
                    for name in char_names:
                        existing_glossary[name] = name  # name → name (korunur, çevrilmez)
                    self.config.glossary = existing_glossary
                finally:
                    if _lock:
                        _lock.release()
                _auto_names_added = len(char_names)
                self.log_message.emit("info", f"[AutoProtect] {_auto_names_added} character name(s) protected: {', '.join(sorted(char_names)[:10])}")

        try:
            unchanged_count = 0
            failed_entries: List[str] = []
            sample_logs: List[str] = []
            stop_quota = False
            for i in range(0, total, batch_size):
                if self.should_stop:
                    break

                batch = entries[i:i + batch_size]

                # Progress güncelle
                current = min(i + batch_size, total)
                if batch:
                    self.progress_updated.emit(current, total, batch[0].original_text[:50])

                # Çeviri istekleri oluştur (her zaman placeholder korumalı)
                requests = []
                # Delimiter-Aware Translation: Her entry için delimiter split bilgisini sakla
                # Key: request listesindeki başlangıç indexi, Value: (entry_idx, segment_count, delimiter, prefix, suffix, translation_id, original_text)
                _delimiter_groups = {}  # {batch_entry_idx: (req_start_idx, seg_count, delim, prefix, suffix, tid, orig_text)}
                # Multi-Group Angle-Pipe (v2.7.5): Çoklu <seg|seg> grupları
                _multi_group_data = {}  # {batch_entry_idx: (req_start, group_lens, tid, orig_text)}
                _delimiter_enabled = getattr(self.config.translation_settings, 'enable_delimiter_aware_translation', True)
                
                _prev_entry_text = None  # extend context tracking — reset per batch
                _prev_entry_file = None  # track file path for cross-file boundary detection
                for entry_idx, entry in enumerate(batch):
                    translation_id = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                        entry.file_path,
                        entry.line_number,
                        entry.original_text,
                        getattr(entry, 'context_path', []),
                        getattr(entry, 'raw_text', None)
                    )
                    
                    # ============================================================
                    # MULTI-GROUP ANGLE-PIPE SPLIT (v2.7.5)
                    # ============================================================
                    # Metindeki TÜM <seg1|seg2|...> gruplarını bulur.
                    # Template ayrı çevrilir, her segment bağımsız çevrilir.
                    # Bu sayede:
                    #   - Çoklu gruplar korunur (GT grup sırasını bozamaz)
                    #   - Çevreleyen metin de tam çevrilir
                    #   - Kısa/tek kelimelik segmentler desteklenir
                    multi_result = split_angle_pipe_groups(entry.original_text) if _delimiter_enabled else None
                    
                    if multi_result is not None:
                        template, groups = multi_result
                        req_start_idx = len(requests)
                        group_lens = [len(g) for g in groups]
                        _multi_group_data[entry_idx] = (req_start_idx, group_lens, translation_id, entry.original_text)
                        
                        _log_preview = entry.original_text[:80].replace('<', '\u2039').replace('>', '\u203a')
                        self.log_message.emit("debug", f"[MultiGroup] {len(groups)} groups ({sum(group_lens)} segments): {_log_preview}")
                        
                        # Request 0: Template ([DGRP_N] placeholder'lı — protect_renpy_syntax korur)
                        protected_template, ph_template = protect_renpy_syntax(template)
                        protected_template, gph_template = self._protect_glossary_terms(protected_template)
                        ph_template.update(gph_template)
                        
                        requests.append(TranslationRequest(
                            text=protected_template,
                            source_lang=api_source_lang,
                            target_lang=api_target_lang,
                            engine=self.engine,
                            metadata={
                                'preprotected': True,
                                'original_text': template,
                                'entry': entry,
                                'translation_id': translation_id,
                                'file_path': entry.file_path,
                                'line_number': entry.line_number,
                                'context_path': getattr(entry, 'context_path', []),
                                'placeholders': ph_template,
                                '_multi_group_template': True,
                            }
                        ))
                        
                        # Requests 1..N: Her grubun segmentleri
                        for group in groups:
                            for seg in group:
                                seg_text = seg.strip()
                                protected_seg, ph_seg = protect_renpy_syntax(seg_text)
                                protected_seg, gph_seg = self._protect_glossary_terms(protected_seg)
                                ph_seg.update(gph_seg)
                                
                                requests.append(TranslationRequest(
                                    text=protected_seg,
                                    source_lang=api_source_lang,
                                    target_lang=api_target_lang,
                                    engine=self.engine,
                                    metadata={
                                        'preprotected': True,
                                        'original_text': seg_text,
                                        'entry': entry,
                                        'translation_id': translation_id,
                                        'file_path': entry.file_path,
                                        'line_number': entry.line_number,
                                        'context_path': getattr(entry, 'context_path', []),
                                        'placeholders': ph_seg,
                                        '_multi_group_segment': True,
                                    }
                                ))
                        _prev_entry_text = entry.original_text  # Track for extend
                        _prev_entry_file = entry.file_path
                        continue  # Multi-group eklendi — normal akışı atla
                    
                    # ============================================================
                    # DELIMITER-AWARE SPLIT (v2.7.2) — Bare pipe fallback
                    # ============================================================
                    # Angle-pipe grubu yoksa, bare pipe pattern'i dene (seg1|seg2|seg3)
                    delim_result = split_delimited_text(entry.original_text) if _delimiter_enabled else None
                    
                    if delim_result is not None:
                        segments, delimiter, d_prefix, d_suffix = delim_result
                        req_start_idx = len(requests)
                        _delimiter_groups[entry_idx] = (req_start_idx, len(segments), delimiter, d_prefix, d_suffix, translation_id, entry.original_text)
                        
                        _log_preview = entry.original_text[:80].replace('<', '\u2039').replace('>', '\u203a')
                        self.log_message.emit("debug", f"[Delimiter] Split into {len(segments)} segments: {_log_preview}")
                        
                        # Her segmenti ayrı bir request olarak ekle
                        for seg in segments:
                            seg_text = seg.strip()
                            protected_text, placeholders = protect_renpy_syntax(seg_text)
                            protected_text, glossary_placeholders = self._protect_glossary_terms(protected_text)
                            placeholders.update(glossary_placeholders)
                            
                            req = TranslationRequest(
                                text=protected_text,
                                source_lang=api_source_lang,
                                target_lang=api_target_lang,
                                engine=self.engine,
                                metadata={
                                    'preprotected': True,
                                    'original_text': seg_text,
                                    'entry': entry,
                                    'translation_id': translation_id,
                                    'file_path': entry.file_path,
                                    'line_number': entry.line_number,
                                    'context_path': getattr(entry, 'context_path', []),
                                    'placeholders': placeholders,
                                    '_delimiter_segment': True,  # İşaretçi: bu bir segment
                                }
                            )
                            requests.append(req)
                        _prev_entry_text = entry.original_text  # Track for extend
                        _prev_entry_file = entry.file_path
                        continue  # Normal akışı atla — segmentler eklendi
                    
                    # ============================================================
                    # Normal (non-delimited) entry işleme
                    # ============================================================
                    # Her metni çeviri öncesi koru (Ren'Py tagleri + Sözlük terimleri)
                    protected_text, placeholders = protect_renpy_syntax(entry.original_text)
                    
                    # Sözlük koruması uygula
                    protected_text, glossary_placeholders = self._protect_glossary_terms(protected_text)
                    placeholders.update(glossary_placeholders)
                    
                    req = TranslationRequest(
                        text=protected_text,  # KORUNMUŞ metin
                        source_lang=api_source_lang,
                        target_lang=api_target_lang,
                        engine=self.engine,
                        metadata={
                            'preprotected': True,
                            'original_text': entry.original_text,
                            'entry': entry,
                            'translation_id': translation_id,
                            'file_path': entry.file_path,
                            'line_number': entry.line_number,
                            'context_path': getattr(entry, 'context_path', []),
                            'placeholders': placeholders,
                            'context_hint': _prev_entry_text if (
                                getattr(entry, 'text_type', '') == 'extend'
                                and _prev_entry_file == entry.file_path  # Same file only
                            ) else None,
                        }
                    )
                    requests.append(req)
                    _prev_entry_text = entry.original_text  # Track for next extend
                    _prev_entry_file = entry.file_path

                # Batch çeviri
                self.translation_manager.set_proxy_enabled(self.use_proxy)
                self.translation_manager.ai_request_delay = getattr(self.config.translation_settings, 'ai_request_delay', 1.5)
                results = loop.run_until_complete(
                    self.translation_manager.translate_batch(requests)
                )

                # Sonuçları kaydet (her zaman restore ile!)
                # ============================================================
                # FAZ 1: Delimiter gruplarını birleştir
                # ============================================================
                # Önce delimiter segmentlerini birleştirip her batch entry için
                # tek bir çevrilmiş metin elde edelim.
                # _delimiter_groups: {entry_idx: (req_start_idx, seg_count, delim, prefix, suffix, tid, orig_text)}
                # _multi_group_data: {entry_idx: (req_start, group_lens, tid, orig_text)}
                
                # Request sonuçlarını entry bazında eşle
                # Normal entry: 1 request = 1 result
                # Delimited entry: N request = N result → rejoin
                # Multi-group entry: 1 template + sum(group_lens) segments → rejoin
                
                # Build a unified result list aligned with batch entries
                _entry_results = []  # List of (tid, restored_text_or_None, entry, success, error)
                _atomic_segments = []  # List of (original_seg, translated_seg) pairs for delimiter entries
                _req_cursor = 0  # Tracks position in results list
                
                for entry_idx, entry in enumerate(batch):
                    if entry_idx in _multi_group_data:
                        # ── Multi-Group Angle-Pipe (v2.7.5) ──
                        req_start, group_lens, tid, orig_text = _multi_group_data[entry_idx]
                        total_reqs = 1 + sum(group_lens)  # 1 template + segments
                        
                        # Result 0: Çevrilmiş template
                        template_idx = req_start
                        all_success = True
                        seg_error = None
                        
                        if template_idx < len(results):
                            template_result = results[template_idx]
                            if not template_result.success or not template_result.translated_text:
                                all_success = False
                                seg_error = (template_result.error or "empty_template")
                                if template_result.quota_exceeded:
                                    stop_quota = True
                        else:
                            all_success = False
                            seg_error = "missing_template_result"
                        
                        translated_template = None
                        translated_groups = []
                        
                        if all_success:
                            translated_template = template_result.translated_text
                            if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                                translated_template = formatter.apply_glossary(
                                    text=translated_template, glossary=self.config.glossary,
                                    original_text=template_result.metadata.get('original_text', '')
                                )
                            
                            # Segment sonuçlarını gruplara ayır
                            seg_cursor = req_start + 1  # template'den sonra
                            for gl in group_lens:
                                group_segs = []
                                for s in range(gl):
                                    r_idx = seg_cursor + s
                                    if r_idx < len(results):
                                        result = results[r_idx]
                                        if result.success and result.translated_text:
                                            raw = result.translated_text
                                            if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                                                raw = formatter.apply_glossary(
                                                    text=raw, glossary=self.config.glossary,
                                                    original_text=result.metadata.get('original_text', '')
                                                )
                                            group_segs.append(raw)
                                        else:
                                            all_success = False
                                            seg_error = result.error or "empty_segment"
                                            if result.quota_exceeded:
                                                stop_quota = True
                                            break
                                        if result.quota_exceeded:
                                            stop_quota = True
                                    else:
                                        all_success = False
                                        seg_error = "missing_segment_result"
                                        break
                                translated_groups.append(group_segs)
                                seg_cursor += gl
                                if not all_success:
                                    break
                        
                        _req_cursor = req_start + total_reqs
                        
                        if all_success and translated_template and len(translated_groups) == len(group_lens):
                            restored = rejoin_angle_pipe_groups(translated_template, translated_groups)
                            
                            if restored is None:
                                self.log_message.emit("warning", f"[MultiGroup] Structural corruption detected, using original: {orig_text[:80]}")
                                _entry_results.append((tid, orig_text, entry, True, None))
                            else:
                                _entry_results.append((tid, restored, entry, True, None))
                                # ── Atomik segment kaydı (v2.7.1) ──
                                # Her segmentin orijinal→çeviri çiftini kaydet.
                                # Ren'Py runtime'da vary() ile segmentleri ayrı ayrı çağırır.
                                seg_r_cursor = req_start + 1  # template'den sonra
                                for grp_segs in translated_groups:
                                    for tr_seg in grp_segs:
                                        if seg_r_cursor < len(results):
                                            orig_seg = results[seg_r_cursor].metadata.get('original_text', '')
                                            if orig_seg and tr_seg and orig_seg != tr_seg:
                                                _atomic_segments.append((orig_seg, tr_seg))
                                            seg_r_cursor += 1
                        else:
                            _entry_results.append((tid, None, entry, False, seg_error))
                    
                    elif entry_idx in _delimiter_groups:
                        # Bu entry delimiter-split edilmişti
                        req_start, seg_count, delim, d_prefix, d_suffix, tid, orig_text = _delimiter_groups[entry_idx]
                        
                        translated_segments = []
                        all_success = True
                        seg_error = None
                        
                        for seg_i in range(seg_count):
                            r_idx = req_start + seg_i
                            if r_idx < len(results):
                                result = results[r_idx]
                                if result.success and result.translated_text:
                                    raw = result.translated_text
                                    if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                                        raw = formatter.apply_glossary(
                                            text=raw, glossary=self.config.glossary,
                                            original_text=result.metadata.get('original_text', '')
                                        )
                                    translated_segments.append(raw)
                                else:
                                    all_success = False
                                    seg_error = result.error or "empty"
                                    if result.quota_exceeded:
                                        stop_quota = True
                                    break
                                if result.quota_exceeded:
                                    stop_quota = True
                            else:
                                all_success = False
                                seg_error = "missing_result"
                                break
                        
                        _req_cursor = req_start + seg_count
                        
                        if all_success and len(translated_segments) == seg_count:
                            # Segmentleri geri birleştir (v2.7.3: yapısal doğrulama ile)
                            restored = rejoin_delimited_text(translated_segments, delim, d_prefix, d_suffix, original_text=orig_text)
                            
                            if restored is None:
                                # Yapısal bozulma tespit edildi — orijinal metni koru
                                self.log_message.emit("warning", f"[Delimiter] Structural corruption detected, using original: {orig_text[:80]}")
                                _entry_results.append((tid, orig_text, entry, True, None))
                            else:
                                _entry_results.append((tid, restored, entry, True, None))
                                # ── Atomik segment kaydı (v2.7.1) ──
                                # Bare-pipe segmentlerinin her birini ayrı çeviri girişi olarak kaydet.
                                for seg_i in range(seg_count):
                                    r_idx = req_start + seg_i
                                    if r_idx < len(results) and results[r_idx].success:
                                        orig_seg = results[r_idx].metadata.get('original_text', '')
                                        tr_seg = translated_segments[seg_i] if seg_i < len(translated_segments) else ''
                                        if orig_seg and tr_seg and orig_seg != tr_seg:
                                            _atomic_segments.append((orig_seg, tr_seg))
                        else:
                            # Herhangi bir segment başarısız ise orijinali koru
                            _entry_results.append((tid, None, entry, False, seg_error))
                    else:
                        # Normal (non-delimited) entry
                        if _req_cursor < len(results):
                            result = results[_req_cursor]
                            _req_cursor += 1
                            
                            if result.quota_exceeded:
                                stop_quota = True
                            
                            if result.success:
                                translated_raw = result.translated_text
                                if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                                    translated_raw = formatter.apply_glossary(
                                        text=translated_raw, 
                                        glossary=self.config.glossary,
                                        original_text=entry.original_text
                                    )
                                restored = translated_raw if translated_raw else ""
                                _entry_results.append((result.metadata.get('translation_id') or result.original_text, restored, entry, True, None))
                            else:
                                _entry_results.append((result.metadata.get('translation_id') or result.original_text, None, entry, False, result.error or "empty"))
                        else:
                            _entry_results.append(("", None, entry, False, "missing_result"))
                
                # ============================================================
                # FAZ 2: Sonuçları translations'a yaz
                # ============================================================
                for tid, restored, entry, success, error in _entry_results:
                    if success and restored is not None:
                        # Otomatik doğrulama: placeholder bozulduysa orijinali kullan
                        if not self.validate_placeholders(original=entry.original_text, translated=restored):
                            self.log_message.emit("warning", self.config.get_log_text('placeholder_corrupted', original=entry.original_text, translated=restored))
                            restored = entry.original_text
                        
                        if restored:
                            translations[tid] = restored
                            translations.setdefault(entry.original_text, restored)
                            
                            # Diagnostics: record translated and unchanged
                            try:
                                file_path = entry.file_path
                                if restored == entry.original_text:
                                    self.diagnostic_report.mark_unchanged(file_path, tid, original_text=entry.original_text)
                                else:
                                    self.diagnostic_report.mark_translated(file_path, tid, restored, original_text=entry.original_text)
                            except Exception:
                                pass
                            
                            if restored == entry.original_text:
                                unchanged_count += 1
                                if len(sample_logs) < 5:
                                    sample_logs.append(f"UNCHANGED {entry.file_path}:{entry.line_number} -> {entry.original_text[:80]}")
                    else:
                        err = error or "empty"
                        file_info = f"{entry.file_path}:{entry.line_number}"
                        if file_info == ":":
                            err_entry = f"({err})"
                        else:
                            err_entry = f"{file_info} ({err})"
                        failed_entries.append(err_entry)
                        # Diagnostics: mark skipped/failed
                        try:
                            self.diagnostic_report.mark_skipped(entry.file_path, f"translate_failed:{err}", {'text': entry.original_text, 'line_number': entry.line_number})
                        except Exception:
                            pass
                
                # ============================================================
                # FAZ 2.5: Atomik segment girişleri (v2.7.1)
                # ============================================================
                # Delimiter gruplarının (<A|B|C> veya A|B|C) her segmentini
                # bağımsız bir çeviri girişi olarak kaydet. Ren'Py runtime'da
                # vary() veya liste indeksleme ile segmentleri ayrı ayrı
                # çağırdığından, birleşik blok yerine atomik girişler gerekir.
                if _atomic_segments:
                    _seg_added = 0
                    for orig_seg, tr_seg in _atomic_segments:
                        if orig_seg not in translations:
                            translations[orig_seg] = tr_seg
                            self._last_atomic_segments[orig_seg] = tr_seg
                            _seg_added += 1
                    if _seg_added:
                        self.emit_log("debug", f"[AtomicSegments] {_seg_added} individual segment translations registered from delimiter groups")
                
                # Cache kaydet (Performans için her 500 metinde bir checkpoint al)
                if current % 500 == 0:
                    self.translation_manager.save_cache(cache_file)
                    self.emit_log("debug", f"Checkpoint saved: {cache_file} (Progress: {current}/{total})")

                if stop_quota:
                    self.log_message.emit("error", self.config.get_log_text('error_api_quota'))
                    self.should_stop = True
                    break
                self.emit_log("info", self.config.get_log_text('translated_count', current=current, total=total))

            if unchanged_count:
                self.log_message.emit("warning", self.config.get_log_text('unchanged_count_msg', unchanged=unchanged_count, total=len(translations)))
                for s in sample_logs:
                    self.log_message.emit("warning", s)
                self._log_error(f"UNCHANGED translations: {unchanged_count} / {len(translations)}\n" + "\n".join(sample_logs))
                
                # SMART TIP: Aggressive Retry Önerisi
                is_aggressive = getattr(self.config.translation_settings, 'aggressive_retry_translation', False)
                if not is_aggressive:
                    self.log_message.emit("info", self.config.get_log_text('log_hint_aggressive_retry'))

            if failed_entries:
                sample = "\n".join(failed_entries[:10])
                self.log_message.emit("warning", self.config.get_log_text('translation_failed_count', count=len(failed_entries), sample=sample))
                self._log_error(f"Translation failures ({len(failed_entries)}):\n{sample}")

            # Final Cache Kaydı
            self.translation_manager.save_cache(cache_file)
            self.log_message.emit("info", self.config.get_log_text('log_cache_saved', path=cache_file, count=len(translations)))

        finally:
            # Proper cleanup to avoid Proactor errors on Windows
            try:
                if loop.is_running():
                    pass # Should not happen with run_until_complete
                
                # Close all sessions and network resources
                loop.run_until_complete(self.translation_manager.close_all())
                
                # Shutdown async generators and executor
                loop.run_until_complete(loop.shutdown_asyncgens())
                # Shutdown default executor only if supported (Python 3.9+)
                if hasattr(loop, 'shutdown_default_executor'):
                    loop.run_until_complete(loop.shutdown_default_executor())
                
                loop.close()
            except Exception as e:
                self.logger.debug(f"Loop cleanup notice: {e}")

        return translations

    def validate_placeholders(self, original, translated):
        """
        Çeviri sonrası değişkenlerin doğruluğunu kontrol eder.
        v2.7.2: Fuzzy matching - boşluklu versiyonları da kabul et (Google Translate corruption tolerance)
        """
        # Orijinaldeki [köşeli parantez] bloklarını bul
        orig_vars = re.findall(r'\[[^\]]+\]', original)

        for var in orig_vars:
            if var not in translated:
                # Fuzzy check: Boşluk eklenmiş veya çıkarılmış versiyonu ara
                # [player.name] → [player. name], [player .name], [player . name]
                var_content = var[1:-1]  # Bracket'leri çıkar
                # Normalized versiyon: boşluksuz
                var_normalized = re.sub(r'\s+', '', var_content)
                
                # Translated içindeki tüm bracket'leri kontrol et
                found = False
                for trans_var in re.findall(r'\[[^\]]+\]', translated):
                    trans_content = trans_var[1:-1]
                    trans_normalized = re.sub(r'\s+', '', trans_content)
                    if var_normalized == trans_normalized:
                        found = True
                        break
                
                if not found:
                    # HATA: Çeviri motoru değişkeni tamamen kaybetmiş veya değiştirmiş!
                    return False
        return True


class PipelineWorker(QThread):
    """Pipeline için QThread wrapper"""
    
    # Forward signals
    stage_changed = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    show_warning = pyqtSignal(str, str)  # title, message - for popup warnings
    
    def __init__(self, pipeline: TranslationPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        
        # Connect signals
        self.pipeline.stage_changed.connect(self.stage_changed)
        self.pipeline.progress_updated.connect(self.progress_updated)
        self.pipeline.log_message.connect(self.log_message)
        self.pipeline.finished.connect(self._on_finished)
        self.pipeline.show_warning.connect(self.show_warning)
    
    def _on_finished(self, result):
        self.finished.emit(result)
    
    def run(self):
        self.pipeline.run()
    
    def stop(self):
        self.pipeline.stop()
