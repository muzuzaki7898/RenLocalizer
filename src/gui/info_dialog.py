"""
Info Dialog
==========

Multi-page information dialog with detailed help content.
"""

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
        QTextEdit, QDialogButtonBox, QLabel, QScrollArea
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QIcon
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
        QTextEdit, QDialogButtonBox, QLabel, QScrollArea
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

from src.utils.config import ConfigManager

class InfoDialog(QDialog):
    """Multi-page information dialog."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Get dialog data from JSON
        dialog_data = self.config_manager.get_ui_text("info_dialog")
        
        if isinstance(dialog_data, str):
            # Fallback if info_dialog data is not available
            self.setWindowTitle("Info")
            self.create_simple_dialog()
            return
        
        self.setWindowTitle(dialog_data.get("title", "Info"))
        self.setModal(True)
        self.resize(800, 650)  # Increased width and height
        
        # Set dialog icon
        from pathlib import Path
        import sys
        # PyInstaller için exe çalışma zamanında doğru yolu bulma
        if getattr(sys, 'frozen', False):
            # PyInstaller ile paketlenmiş exe durumu - temporary dizinde icon var
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            # Normal Python çalışma zamanı
            icon_path = Path(__file__).parent.parent.parent / "icon.ico"
        
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_formats_tab(dialog_data)
        self.create_performance_tab(dialog_data)
        self.create_features_tab(dialog_data)
        self.create_troubleshooting_tab(dialog_data)
        
        # Add close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def create_simple_dialog(self):
        """Create simple dialog if JSON data is not available."""
        layout = QVBoxLayout(self)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("<h3>Info</h3><p>Information dialog is loading...</p>")
        layout.addWidget(text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def create_formats_tab(self, dialog_data):
        """Create output formats information tab."""
        formats_data = dialog_data.get("formats", {})
        tab_title = dialog_data.get("tabs", {}).get("formats", "Formats")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create text widget (QTextEdit has its own scrolling and word wrap)
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with dark theme compatible colors
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4; color: #ffffff;">
        <h2 style="color: #60a5fa; margin-bottom: 15px;">{formats_data.get('title', 'Translation File Formats')}</h2>
        <p style="margin-bottom: 20px; color: #d1d5db;">{formats_data.get('description', '')}</p>
        
        <div style="border: 2px solid #3b82f6; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #1e3a8a; color: #ffffff;">
        <h3 style="color: #93c5fd; margin-top: 0;">{formats_data.get('simple', {}).get('title', 'SIMPLE Format')}</h3>
        <p style="color: #e5e7eb;"><b>Özellikler:</b></p>
        <ul style="margin-left: 20px; color: #f3f4f6;">
        """
        
        for feature in formats_data.get('simple', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px; color: #f3f4f6;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p style="color: #e5e7eb;"><b>Örnek:</b></p>
        <pre style="background-color: #374151; color: #f9fafb; padding: 10px; border-radius: 5px; border: 1px solid #6b7280; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('simple', {}).get('example', '')}
        </pre>
        <p style="color: #e5e7eb;"><b>Önerilen:</b> <i style="color: #d1d5db;">{formats_data.get('simple', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <div style="border: 2px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #065f46; color: #ffffff;">
        <h3 style="color: #6ee7b7; margin-top: 0;">{formats_data.get('old_new', {}).get('title', 'OLD_NEW Format')}</h3>
        <p style="color: #e5e7eb;"><b>Özellikler:</b></p>
        <ul style="margin-left: 20px; color: #f3f4f6;">
        """
        
        for feature in formats_data.get('old_new', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px; color: #f3f4f6;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p style="color: #e5e7eb;"><b>Örnek:</b></p>
        <pre style="background-color: #374151; color: #f9fafb; padding: 10px; border-radius: 5px; border: 1px solid #6b7280; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('old_new', {}).get('example', '')}
        </pre>
        <p style="color: #e5e7eb;"><b>Önerilen:</b> <i style="color: #d1d5db;">{formats_data.get('old_new', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <hr style="margin: 20px 0; border: 1px solid #4b5563;">
        <div style="background-color: #451a03; color: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b;">
        <p style="color: #fef3c7;"><b>💡 Not:</b> {formats_data.get('note', '')}</p>
        <p style="color: #fde68a;"><b>⚙️ Ayar:</b> <i>{formats_data.get('change_setting', '')}</i></p>
        </div>
        </div>
        """
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_performance_tab(self, dialog_data):
        """Create performance settings information tab."""
        perf_data = dialog_data.get("performance", {})
        tab_title = dialog_data.get("tabs", {}).get("performance", "Performance")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{perf_data.get('title', 'Performance Settings')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{perf_data.get('description', '')}</p>
        """
        
        # Parser Workers
        parser_data = perf_data.get('parser_workers', {})
        html_content += f"""
        <div style="border: 2px solid #9c27b0; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #2a1b3d;">
        <h3 style="color: #ce93d8; margin-top: 0;">🚀 {parser_data.get('title', 'Parser Workers')}</h3>
        <p style="color: #e0e0e0;">{parser_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in parser_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #3a2859; padding: 8px; border-radius: 4px; color: #d1c4e9;'><i>💡 {parser_data.get('note', '')}</i></p></div>"
        
        # Concurrent Threads
        threads_data = perf_data.get('concurrent_threads', {})
        html_content += f"""
        <div style="border: 2px solid #f44336; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d1a1a;">
        <h3 style="color: #ef9a9a; margin-top: 0;">⚡ {threads_data.get('title', 'Concurrent Threads')}</h3>
        <p style="color: #e0e0e0;">{threads_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in threads_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #4d2626; padding: 8px; border-radius: 4px; color: #ffcdd2;'><i>⚠️ {threads_data.get('note', '')}</i></p></div>"
        
        # Batch Size
        batch_data = perf_data.get('batch_size', {})
        html_content += f"""
        <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1b3d1b;">
        <h3 style="color: #a5d6a7; margin-top: 0;">📦 {batch_data.get('title', 'Batch Size')}</h3>
        <p style="color: #e0e0e0;">{batch_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in batch_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #2d5016; padding: 8px; border-radius: 4px; color: #c8e6c9;'><i>📊 {batch_data.get('note', '')}</i></p></div>"
        
        # Request Delay
        delay_data = perf_data.get('request_delay', {})
        html_content += f"""
        <div style="border: 2px solid #ff9800; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d2a1a;">
        <h3 style="color: #ffcc80; margin-top: 0;">⏱️ {delay_data.get('title', 'Request Delay')}</h3>
        <p style="color: #e0e0e0;">{delay_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in delay_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #4d3319; padding: 8px; border-radius: 4px; color: #ffe0b2;'><i>🎯 {delay_data.get('note', '')}</i></p></div>"
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_features_tab(self, dialog_data):
        """Create features information tab."""
        features_data = dialog_data.get("features", {})
        tab_title = dialog_data.get("tabs", {}).get("features", "Features")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{features_data.get('title', 'Program Features')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{features_data.get('description', '')}</p>
        
        <h3 style="color: #a5d6a7; margin-bottom: 15px;">✅ Mevcut Özellikler</h3>
        """
        
        for feature in features_data.get('current', []):
            html_content += f"""
            <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1b3d1b;">
            <h4 style="color: #a5d6a7; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0; color: #e0e0e0;">{feature.get('description', '')}</p>
            </div>
            """
        
        html_content += """<h3 style="color: #ffcc80; margin-bottom: 15px; margin-top: 25px;">🚀 Gelecek Özellikler</h3>"""
        
        for feature in features_data.get('upcoming', []):
            html_content += f"""
            <div style="border: 2px solid #ff9800; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d2a1a;">
            <h4 style="color: #ffcc80; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0; color: #e0e0e0;">{feature.get('description', '')}</p>
            </div>
            """
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_troubleshooting_tab(self, dialog_data):
        """Create troubleshooting information tab."""
        trouble_data = dialog_data.get("troubleshooting", {})
        tab_title = dialog_data.get("tabs", {}).get("troubleshooting", "Troubleshooting")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{trouble_data.get('title', 'Troubleshooting')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{trouble_data.get('description', '')}</p>
        """
        
        colors = ['#f44336', '#ff9800', '#4caf50', '#2196f3']  # Different colors for each problem
        bg_colors = ['#3d1a1a', '#3d2a1a', '#1b3d1b', '#1a2a3d']
        text_colors = ['#ef9a9a', '#ffcc80', '#a5d6a7', '#90caf9']
        
        for i, issue in enumerate(trouble_data.get('common_issues', [])):
            color = colors[i % len(colors)]
            bg_color = bg_colors[i % len(bg_colors)]
            text_color = text_colors[i % len(text_colors)]
            
            html_content += f"""
            <div style="border: 2px solid {color}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: {bg_color};">
            <h3 style="color: {text_color}; margin-top: 0; margin-bottom: 10px;">❓ {issue.get('problem', '')}</h3>
            <p style="color: #e0e0e0;"><b>🔧 Çözümler:</b></p>
            <ul style="margin-left: 20px; color: #e0e0e0;">
            """
            for solution in issue.get('solutions', []):
                html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{solution}</li>"
            html_content += "</ul></div>"
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
