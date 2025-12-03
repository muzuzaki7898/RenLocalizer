# -*- coding: utf-8 -*-
"""
Integrated Translation Dialog
==============================

Tek tıkla çeviri: EXE seç → Çevir → Bitti

Bu dialog, tüm çeviri sürecini tek bir arayüzde birleştirir:
1. Oyun EXE'sini seç
2. Hedef dili seç
3. Çevir butonuna tıkla
4. Pipeline otomatik olarak:
   - Projeyi doğrular
   - Gerekirse UnRen ile decompile eder
   - Ren'Py translate komutu ile tl/<dil>/ oluşturur
   - Metinleri çevirir
   - Dosyalara kaydeder
"""

import os
import logging
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
        QGroupBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox,
        QFrame, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QSize
    from PyQt6.QtGui import QFont, QIcon
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
        QGroupBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox,
        QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QFont, QIcon

from src.utils.config import ConfigManager
from src.core.translator import TranslationManager, TranslationEngine
from src.core.translation_pipeline import (
    TranslationPipeline, PipelineWorker, PipelineStage, PipelineResult
)


class IntegratedTranslationDialog(QDialog):
    """
    Entegre Çeviri Dialogu
    
    Tek tıkla:
    EXE Seç → UnRen → Translate → Çeviri → Kaydet
    """
    
    # Desteklenen diller (36 dil)
    SUPPORTED_LANGUAGES = [
        ("turkish", "Türkçe"),
        ("english", "English"),
        ("german", "Deutsch"),
        ("french", "Français"),
        ("spanish", "Español"),
        ("italian", "Italiano"),
        ("portuguese", "Português"),
        ("russian", "Русский"),
        ("polish", "Polski"),
        ("dutch", "Nederlands"),
        ("japanese", "日本語"),
        ("korean", "한국어"),
        ("chinese_s", "简体中文"),
        ("chinese_t", "繁體中文"),
        ("arabic", "العربية"),
        ("thai", "ไทย"),
        ("vietnamese", "Tiếng Việt"),
        ("indonesian", "Bahasa Indonesia"),
        ("czech", "Čeština"),
        ("danish", "Dansk"),
        ("finnish", "Suomi"),
        ("greek", "Ελληνικά"),
        ("hebrew", "עברית"),
        ("hindi", "हिन्दी"),
        ("hungarian", "Magyar"),
        ("norwegian", "Norsk"),
        ("romanian", "Română"),
        ("swedish", "Svenska"),
        ("ukrainian", "Українська"),
        ("bulgarian", "Български"),
        ("catalan", "Català"),
        ("croatian", "Hrvatski"),
        ("slovak", "Slovenčina"),
        ("slovenian", "Slovenščina"),
        ("serbian", "Српски"),
        ("malay", "Bahasa Melayu"),
    ]
    
    def __init__(self, config: ConfigManager, translation_manager: TranslationManager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        self.config = config
        self.translation_manager = translation_manager
        
        # Pipeline
        self.pipeline = TranslationPipeline(config, translation_manager)
        self.pipeline_worker: Optional[PipelineWorker] = None
        
        # State
        self.is_running = False
        
        # UI
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("🚀 Entegre Çeviri")
        self.setMinimumSize(600, 500)
        self.setMaximumWidth(700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Açıklama
        desc_label = QLabel(
            "Oyun EXE'sini seçin, dili belirleyin ve tek tıkla çevirin.\n"
            "Sistem otomatik olarak decompile, translate ve çeviri işlemlerini yapar."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 8px;")
        layout.addWidget(desc_label)
        
        # === PROJE SEÇİMİ ===
        project_group = QGroupBox("📁 Proje Seçimi")
        project_layout = QFormLayout(project_group)
        
        # EXE seçimi
        exe_layout = QHBoxLayout()
        self.exe_input = QLineEdit()
        self.exe_input.setPlaceholderText("Oyun EXE dosyasını seçin (örn: Game.exe)")
        self.exe_input.setMinimumWidth(300)
        self.browse_button = QPushButton("Gözat...")
        self.browse_button.clicked.connect(self.browse_exe)
        exe_layout.addWidget(self.exe_input)
        exe_layout.addWidget(self.browse_button)
        project_layout.addRow("Oyun EXE:", exe_layout)
        
        layout.addWidget(project_group)
        
        # === ÇEVİRİ AYARLARI ===
        settings_group = QGroupBox("⚙️ Çeviri Ayarları")
        settings_layout = QFormLayout(settings_group)
        
        # Kaynak dil
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItem("Otomatik Algıla (Auto)", "auto")
        self.source_lang_combo.addItem("English", "en")
        self.source_lang_combo.addItem("Japanese", "ja")
        settings_layout.addRow("Kaynak Dil:", self.source_lang_combo)
        
        # Hedef dil
        self.target_lang_combo = QComboBox()
        for code, name in self.SUPPORTED_LANGUAGES:
            self.target_lang_combo.addItem(f"{name} ({code})", code)
        settings_layout.addRow("Hedef Dil:", self.target_lang_combo)
        
        # Çeviri motoru
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Google Translate (Ücretsiz)", TranslationEngine.GOOGLE)
        self.engine_combo.addItem("DeepL (API Key)", TranslationEngine.DEEPL)
        self.engine_combo.addItem("Bing Translate", TranslationEngine.BING)
        self.engine_combo.addItem("Yandex Translate", TranslationEngine.YANDEX)
        settings_layout.addRow("Çeviri Motoru:", self.engine_combo)
        
        layout.addWidget(settings_group)
        
        # === İLERLEME ===
        progress_group = QGroupBox("📊 İlerleme")
        progress_layout = QVBoxLayout(progress_group)
        
        # Aşama etiketi
        self.stage_label = QLabel("Hazır")
        self.stage_label.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.stage_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Log alanı
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText("Log mesajları burada görünecek...")
        progress_layout.addWidget(self.log_text)
        
        layout.addWidget(progress_group)
        
        # === BUTONLAR ===
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("🚀 Çeviriyi Başlat")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.start_button.clicked.connect(self.start_pipeline)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹ Durdur")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.stop_button.clicked.connect(self.stop_pipeline)
        button_layout.addWidget(self.stop_button)
        
        self.close_button = QPushButton("Kapat")
        self.close_button.setMinimumHeight(40)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def connect_signals(self):
        """Sinyalleri bağla"""
        self.pipeline.stage_changed.connect(self.on_stage_changed)
        self.pipeline.progress_updated.connect(self.on_progress_updated)
        self.pipeline.log_message.connect(self.on_log_message)
        self.pipeline.finished.connect(self.on_finished)
    
    def browse_exe(self):
        """EXE dosyası seç"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Oyun EXE'sini Seçin",
            "",
            "Executable (*.exe);;All Files (*.*)"
        )
        
        if file_path:
            self.exe_input.setText(file_path)
            self.log_text.clear()
            self.add_log("info", f"EXE seçildi: {file_path}")
            
            # Proje dizinini kontrol et
            project_dir = os.path.dirname(file_path)
            game_dir = os.path.join(project_dir, 'game')
            
            if os.path.isdir(game_dir):
                self.add_log("info", f"✓ Geçerli Ren'Py projesi bulundu")
                
                # .rpy ve .rpyc durumunu kontrol et
                has_rpy = self._has_files(game_dir, '.rpy')
                has_rpyc = self._has_files(game_dir, '.rpyc')
                
                if has_rpy:
                    self.add_log("info", "✓ .rpy dosyaları mevcut")
                elif has_rpyc:
                    self.add_log("warning", "⚠ Sadece .rpyc dosyaları var - decompile gerekli")
            else:
                self.add_log("error", "✗ 'game' klasörü bulunamadı")
    
    def _has_files(self, directory: str, extension: str) -> bool:
        """Klasörde belirli uzantılı dosya var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith(extension):
                    return True
        return False
    
    def add_log(self, level: str, message: str):
        """Log mesajı ekle"""
        color_map = {
            "info": "#17a2b8",
            "warning": "#ffc107",
            "error": "#dc3545",
            "success": "#28a745"
        }
        color = color_map.get(level, "#6c757d")
        
        self.log_text.append(f'<span style="color:{color}">{message}</span>')
    
    def start_pipeline(self):
        """Pipeline'ı başlat"""
        exe_path = self.exe_input.text().strip()
        
        if not exe_path:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir oyun EXE'si seçin.")
            return
        
        if not os.path.isfile(exe_path):
            QMessageBox.warning(self, "Uyarı", "Seçilen EXE dosyası bulunamadı.")
            return
        
        # Ayarları al - config'den oku
        target_lang = self.target_lang_combo.currentData()
        source_lang = self.source_lang_combo.currentData()
        engine = self.engine_combo.currentData()
        auto_unren = self.config.app_settings.unren_auto_download
        use_proxy = getattr(self.config.proxy_settings, "enabled", False)
        
        # Pipeline'ı yapılandır
        self.pipeline.configure(
            game_exe_path=exe_path,
            target_language=target_lang,
            source_language=source_lang,
            engine=engine,
            auto_unren=auto_unren,
            use_proxy=use_proxy
        )
        
        # UI güncelle
        self.is_running = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.browse_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self.add_log("info", "🚀 Pipeline başlatılıyor...")
        
        # Worker'ı başlat
        self.pipeline_worker = PipelineWorker(self.pipeline)
        self.pipeline_worker.start()
    
    def stop_pipeline(self):
        """Pipeline'ı durdur"""
        if self.pipeline_worker:
            self.add_log("warning", "⏹ Durdurma isteği gönderildi...")
            self.pipeline.stop()
    
    def on_stage_changed(self, stage: str, message: str):
        """Aşama değiştiğinde"""
        stage_names = {
            "idle": "Hazır",
            "validating": "🔍 Doğrulanıyor...",
            "unren": "📦 Decompile Ediliyor (UnRen)...",
            "generating": "📝 Çeviri Dosyaları Oluşturuluyor...",
            "parsing": "📖 Dosyalar Okunuyor...",
            "translating": "🌐 Çevriliyor...",
            "saving": "💾 Kaydediliyor...",
            "completed": "✅ Tamamlandı!",
            "error": "❌ Hata!"
        }
        
        display_name = stage_names.get(stage, stage)
        self.stage_label.setText(display_name)
        
        # Progress bar için tahmini değerler
        stage_progress = {
            "idle": 0,
            "validating": 5,
            "unren": 15,
            "generating": 30,
            "parsing": 40,
            "translating": 50,  # 50-95 arası çeviri sırasında güncellenir
            "saving": 95,
            "completed": 100,
            "error": 0
        }
        
        if stage in stage_progress and stage != "translating":
            self.progress_bar.setValue(stage_progress[stage])
    
    def on_progress_updated(self, current: int, total: int, text: str):
        """İlerleme güncellendiğinde"""
        if total > 0:
            # Çeviri aşaması 50-95 arası
            percentage = 50 + int((current / total) * 45)
            self.progress_bar.setValue(percentage)
        
        # Her 10 metinde bir log
        if current % 10 == 0 or current == total:
            self.add_log("info", f"Çevriliyor: {current}/{total}")
    
    def on_log_message(self, level: str, message: str):
        """Log mesajı geldiğinde"""
        self.add_log(level, message)
    
    def on_finished(self, result: PipelineResult):
        """Pipeline tamamlandığında"""
        self.is_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.browse_button.setEnabled(True)
        
        if result.success:
            self.progress_bar.setValue(100)
            self.add_log("success", f"✅ {result.message}")
            
            if result.stats:
                stats = result.stats
                self.add_log("info", f"📊 Toplam: {stats['total']} giriş")
                self.add_log("info", f"✓ Çevrilmiş: {stats['translated']}")
                self.add_log("info", f"○ Çevrilmemiş: {stats['untranslated']}")
            
            if result.output_path:
                self.add_log("info", f"📁 Çıktı: {result.output_path}")
            
            QMessageBox.information(
                self,
                "Başarılı",
                f"{result.message}\n\n"
                f"Çıktı klasörü:\n{result.output_path}"
            )
        else:
            self.add_log("error", f"❌ {result.message}")
            
            if result.error:
                self.add_log("error", f"Detay: {result.error}")
            
            QMessageBox.warning(
                self,
                "Hata",
                f"Pipeline başarısız:\n\n{result.message}"
            )
    
    def closeEvent(self, event):
        """Dialog kapatılırken"""
        if self.is_running:
            reply = QMessageBox.question(
                self,
                "Çeviri Devam Ediyor",
                "Çeviri işlemi devam ediyor. Durdurup kapatmak istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_pipeline()
                if self.pipeline_worker:
                    self.pipeline_worker.wait(5000)  # 5 saniye bekle
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
