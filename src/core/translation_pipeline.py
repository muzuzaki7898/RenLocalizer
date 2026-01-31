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
from typing import Optional, List, Dict, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil  # En tepeye ekleyin
from src.utils.encoding import normalize_to_utf8_sig, read_text_safely

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
from src.core.ai_translator import OpenAITranslator, GeminiTranslator
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
        AST'den stringleri çıkarır. Tüm metin tiplerini (tek satır, çok satır, uzun paragraflar dahil) eksiksiz yakalar.
        Özellikle 'text', 'content', 'value', 'caption', 'label', 'description' gibi alanları öncelikli kontrol eder.
        """
        strings = set()
        PRIORITY_KEYS = ['text', 'content', 'value', 'caption', 'label', 'description', 'message', 'body']
        def walk(node):
            if isinstance(node, str):
                s = node.strip()
                if len(s) > 2 and not all(c in '\n\r\t ' for c in s):
                    strings.add(s)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                # Önce öncelikli anahtarları gez
                for key in PRIORITY_KEYS:
                    if key in node:
                        walk(node[key])
                # Sonra kalanları gez
                for k, v in node.items():
                    if k not in PRIORITY_KEYS:
                        walk(v)
            elif hasattr(node, '__dict__'):
                d = vars(node)
                for key in PRIORITY_KEYS:
                    if key in d:
                        walk(d[key])
                for k, v in d.items():
                    if k not in PRIORITY_KEYS:
                        walk(v)
        walk(ast_root)
        result = list(strings)
        for i, s in enumerate(result[:3]):
            self.log_message.emit('debug', f".rpymc sample string {i+1}: {repr(s)[:120]}")
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
        needs_extraction = not has_rpy and has_rpa and self.auto_unren
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
                               except: pass
            
            # Tekrar kontrol
            has_rpy = self._has_rpy_files(game_dir)
        
        # RPYC-only mode: If no .rpy but has .rpyc and RPYC Reader is enabled
        rpyc_only_mode = False
        if not has_rpy and has_rpyc:
            # Check if RPYC reader is enabled
            rpyc_enabled = getattr(self.config.translation_settings, 'enable_rpyc_reader', False) or getattr(self, 'include_rpyc', False)
            if rpyc_enabled:
                self.log_message.emit("info", self.config.get_ui_text("pipeline_rpyc_only_mode", "RPYC-only modu: .rpy dosyası bulunamadı, doğrudan .rpyc dosyaları okunacak."))
                rpyc_only_mode = True
            else:
                return PipelineResult(
                    success=False,
                    message=self.config.get_ui_text("pipeline_no_rpy_files") + " " + self.config.get_ui_text("pipeline_enable_rpyc_hint", "(RPYC Reader'ı etkinleştirmeyi deneyin)"),
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
    
    def _manage_runtime_hook(self):
        """
        Manages the presence of the runtime translation hook script based on settings.
        Generated by RenLocalizer to force translation of untagged strings.
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

            should_exist = getattr(self.config.translation_settings, 'force_runtime_translation', False)
            
            # Hedef dili al
            target_lang = getattr(self, 'target_language', None) or getattr(self.config.translation_settings, 'target_language', 'turkish') or 'turkish'
            # ISO -> Ren'Py native
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            renpy_lang = reverse_lang_map.get(target_lang.lower(), target_lang)
            
            if should_exist:
                content = f'''# RenLocalizer Runtime Translation Hook
# This script forces translation lookup for all text displayed by Ren'Py,
# solving issues where developers missed the !t flag on interpolated strings.
# Press Shift+L to manually switch to the translated language.
# Generated by RenLocalizer.

init 1501 python:
    # =========================================================================
    # LANGUAGE HOTKEY: Shift+L
    # =========================================================================
    def _renlocalizer_switch_lang():
        target = "{renpy_lang}"
        renpy.change_language(target)
        persistent.renlocalizer_target_lang = target
        renpy.notify("RenLocalizer: Language → {renpy_lang.title()}")
        renpy.restart_interaction()

    # Register Shift+L as language toggle
    config.underlay.append(renpy.Keymap(shift_K_l=_renlocalizer_switch_lang))

    # =========================================================================
    # RUNTIME TEXT TRANSLATION HOOK
    # =========================================================================
    # Save original replacer if it exists and hasn't been wrapped yet
    if not hasattr(store, '_renlocalizer_old_replace_text'):
        if hasattr(config, 'replace_text') and config.replace_text:
            store._renlocalizer_old_replace_text = config.replace_text
        else:
            store._renlocalizer_old_replace_text = lambda s: s

    def _renlocalizer_force_translate(s):
        # 1. Run original game filters
        s = store._renlocalizer_old_replace_text(s)
        # 2. Force Ren'Py translation lookup
        if s:
            return renpy.translate_string(s)
        return s

    # Install the hooks
    config.say_menu_text_filter = _renlocalizer_force_translate
    config.replace_text = _renlocalizer_force_translate
'''
                with open(hook_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log_message.emit('info', f"Runtime translation hook installed: {hook_filename}")
            else:
                # Remove if it exists
                if hook_path.exists():
                    os.remove(hook_path)
                    self.log_message.emit('info', f"Runtime translation hook removed: {hook_filename}")
                    
        except Exception as e:
            self.logger.warning(f"Failed to manage runtime hook: {e}")

    def _create_language_init_file(self, game_dir: str):
        """
        Dil baslangic dosyasini olusturur.
        game/ klasorune yazilir, boylece oyun baslarken varsayilan dil ayarlanir.
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

            # Sade ve dinamik baslaticinin icerigi
            content = (
                f"# Auto-generated language initializer by RenLocalizer\n"
                f"init 1500 python:\n"
                f"    # Ensure the game switches to this language upon first install or change\n"
                f"    # Using late init (1500) to overwrite other scripts safely\n"
                f"    if getattr(persistent, 'renlocalizer_target_lang', None) != \"{language_code}\":\n"
                f"        persistent.renlocalizer_target_lang = \"{language_code}\"\n"
                f"        _preferences.language = \"{language_code}\"\n"
                f"\n"
                f"define config.default_language = \"{language_code}\"\n"
            )

            with open(init_file, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(content)

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
                            with open(filepath, 'w', encoding='utf-8-sig', newline='\n') as f:
                                f.write(content)
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
                self.log_message.emit("warning", "⏳ .rpyc (Binary) veri tabanı taranıyor... Bu işlem dosya boyutuna göre zaman alabilir. Lütfen bekleyin, program donmadı!")
                self.log_message.emit("info", self.config.get_log_text('rpyc_scan_running'))
                # Import here to avoid circular imports if any
                try:
                    from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                    rpyc_results = extract_texts_from_rpyc_directory(game_dir)
                    self.log_message.emit("success", f"✅ .rpyc taraması tamamlandı. {len(rpyc_results)} dosya işlendi.")
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
                        self.log_message.emit("info", f"Mevcut çeviri dosyalarında {len(existing_global_strings)} çakışan string bulundu, bunlar strings.rpy'ye eklenmeyecek.")
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
                        strings_path = os.path.join(tl_dir, 'strings.rpy')
                        with open(strings_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                            f.write(strings_content)
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
            if self.translation_manager:
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
        """Sözlük terimlerini placeholder ile korur ve karşılıklarını saklar."""
        if not self.config or not hasattr(self.config, 'glossary') or not self.config.glossary:
            return text, {}
            
        placeholders = {}
        counter = 0
        # En uzun terimler önce (çakışmayı önlemek için)
        sorted_terms = sorted(self.config.glossary.items(), key=lambda x: -len(x[0]))
        
        result = text
        for src, dst in sorted_terms:
            if not src or not dst: continue
            
            # Sadece tam kelime eşleşmesi (\b)
            pattern = re.compile(r'(?i)\b' + re.escape(src) + r'\b')
            
            def replace_func(match):
                nonlocal counter
                key = f"[[g{counter}]]"
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
    
    def _translate_entries(self, entries: List[TranslationEntry]) -> Dict[str, str]:
        """Girişleri çevir (placeholder koruması zorunlu)."""
        from src.core.translator import protect_renpy_syntax, restore_renpy_syntax
        translations = {}
        formatter = RenPyOutputFormatter()

        # Teknik/yer tutucu metinleri çeviri kuyruğundan ayıkla
        filtered_entries: List[TranslationEntry] = []
        for entry in entries:
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

        try:
            unchanged_count = 0
            failed_entries: List[str] = []
            sample_logs: List[str] = []
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
                batch_placeholders = []
                for entry in batch:
                    translation_id = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                        entry.file_path,
                        entry.line_number,
                        entry.original_text,
                        getattr(entry, 'context_path', []),
                        getattr(entry, 'raw_text', None)
                    )
                    # Her metni çeviri öncesi koru (Ren'Py tagleri + Sözlük terimleri)
                    protected_text, placeholders = protect_renpy_syntax(entry.original_text)
                    
                    # Sözlük koruması uygula
                    protected_text, glossary_placeholders = self._protect_glossary_terms(protected_text)
                    placeholders.update(glossary_placeholders)
                    
                    batch_placeholders.append(placeholders)
                    req = TranslationRequest(
                        text=protected_text,  # KORUNMUŞ metin
                        source_lang=api_source_lang,
                        target_lang=api_target_lang,
                        engine=self.engine,
                        metadata={
                            'entry': entry,
                            'translation_id': translation_id,
                            'file_path': entry.file_path,
                            'line_number': entry.line_number,
                            'context_path': getattr(entry, 'context_path', []),
                            'placeholders': placeholders,
                        }
                    )
                    requests.append(req)

                # Batch çeviri
                self.translation_manager.set_proxy_enabled(self.use_proxy)
                self.translation_manager.ai_request_delay = getattr(self.config.translation_settings, 'ai_request_delay', 1.5)
                results = loop.run_until_complete(
                    self.translation_manager.translate_batch(requests)
                )

                # Sonuçları kaydet (her zaman restore ile!)
                stop_quota = False
                for idx, result in enumerate(results):
                    tid = result.metadata.get('translation_id') or result.original_text
                    placeholders = result.metadata.get('placeholders') or {}
                    
                    # Kota doldu hatasını kontrol et
                    if result.quota_exceeded:
                        stop_quota = True

                    if result.success:
                        translated_raw = result.translated_text
                        if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                            translated_raw = formatter.apply_glossary(
                                text=translated_raw, 
                                glossary=self.config.glossary,
                                original_text=batch[idx].original_text
                            )

                        # Çeviri sonrası placeholder restore
                        restored = restore_renpy_syntax(translated_raw, placeholders) if translated_raw else ""
                        
                        # Otomatik doğrulama: placeholder bozulduysa orijinali kullan
                        if not self.validate_placeholders(original=batch[idx].original_text, translated=restored):
                            self.log_message.emit("warning", self.config.get_log_text('placeholder_corrupted', original=batch[idx].original_text, translated=restored))
                            restored = batch[idx].original_text
                        
                        if restored:
                            translations[tid] = restored
                            translations.setdefault(batch[idx].original_text, restored)
                            
                            # Diagnostics: record translated and unchanged
                            try:
                                file_path = result.metadata.get('file_path') or batch[idx].file_path
                                if restored == batch[idx].original_text:
                                    self.diagnostic_report.mark_unchanged(file_path, tid, original_text=batch[idx].original_text)
                                else:
                                    self.diagnostic_report.mark_translated(file_path, tid, restored, original_text=batch[idx].original_text)
                            except Exception:
                                pass
                            
                            if restored == batch[idx].original_text:
                                unchanged_count += 1
                                if len(sample_logs) < 5:
                                    sample_logs.append(f"UNCHANGED {result.metadata.get('file_path','')}:{result.metadata.get('line_number','')} -> {batch[idx].original_text[:80]}")
                    else:
                        err = result.error or "empty"
                        file_info = f"{result.metadata.get('file_path','')}:{result.metadata.get('line_number','')}"
                        if file_info == ":":
                            entry = f"({err})"
                        else:
                            entry = f"{file_info} ({err})"
                        failed_entries.append(entry)
                        # Diagnostics: mark skipped/failed
                        try:
                            file_path = result.metadata.get('file_path') or batch[idx].file_path
                            self.diagnostic_report.mark_skipped(file_path, f"translate_failed:{err}", {'text': batch[idx].original_text, 'line_number': batch[idx].line_number})
                        except Exception:
                            pass
                
                # Her batch çevirisinden sonra cache kaydet (Daha güvenli checkpoint)
                self.translation_manager.save_cache(cache_file)
                
                # Sadece her 50 metinde bir "Checkpoint saved" logu bas (log kirliliğini önlemek için)
                if current % 50 == 0:
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
        """
        # Orijinaldeki [köşeli parantez] bloklarını bul
        orig_vars = re.findall(r'\[[^\]]+\]', original)

        for var in orig_vars:
            if var not in translated:
                # HATA: Çeviri motoru değişkeni bozmuş!
                # Çeviriyi iptal et ve orijinal metni kullan veya değişkeni zorla ekle
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
