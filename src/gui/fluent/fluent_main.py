# -*- coding: utf-8 -*-
"""
Fluent Main Window
==================

Main application window using PyQt6-Fluent-Widgets with Windows 11 Fluent Design.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QDesktopServices
from PyQt6.QtWidgets import QApplication, QMessageBox

from qfluentwidgets import (
    FluentWindow, FluentIcon, NavigationItemPosition,
    setTheme, Theme, setThemeColor, InfoBar, InfoBarPosition
)
from qfluentwidgets import FluentIcon as FIF

from src.utils.config import ConfigManager
from src.utils.update_checker import check_for_updates
from src.version import VERSION


class UpdateCheckWorker(QThread):
    """Run update checks without blocking the UI."""
    finished = pyqtSignal(object)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        result = check_for_updates(self.current_version)
        self.finished.emit(result)


class FluentMainWindow(FluentWindow):
    """Main application window with Fluent Design."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Initialize config manager
        self.config_manager = ConfigManager()
        
        # Set window properties
        self.setWindowTitle(f"RenLocalizer v{VERSION}")
        self.setMinimumSize(1000, 700)
        self.showMaximized()
        
        # Set application icon
        self._set_window_icon()
        
        # Apply dark theme
        setTheme(Theme.DARK)
        setThemeColor("#0078D4")  # Windows 11 accent blue
        
        # Initialize interfaces (pages)
        self._init_interfaces()
        
        # Setup navigation
        self._init_navigation()
        
        self.logger.info("FluentMainWindow initialized successfully")
        
        # Check for updates on startup
        self._check_for_updates()

    def _set_window_icon(self):
        """Set the application icon."""
        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            icon_path = Path(__file__).parent.parent.parent.parent / "icon.ico"
        
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _init_interfaces(self):
        """Initialize all page interfaces."""
        # Import interfaces here to avoid circular imports
        from .home_interface import HomeInterface
        from .tools_interface import ToolsInterface
        from .settings_interface import SettingsInterface
        from .about_interface import AboutInterface
        
        # Create interface instances
        self.home_interface = HomeInterface(self.config_manager, self)
        self.tools_interface = ToolsInterface(self.config_manager, self)
        self.settings_interface = SettingsInterface(self.config_manager, self)
        self.about_interface = AboutInterface(self.config_manager, self)

    def _init_navigation(self):
        """Setup navigation sidebar."""
        # Add main navigation items
        self.addSubInterface(
            self.home_interface,
            FIF.HOME,
            self.config_manager.get_ui_text("nav_home", "Ana Sayfa")
        )
        
        self.addSubInterface(
            self.tools_interface,
            FIF.DEVELOPER_TOOLS,
            self.config_manager.get_ui_text("nav_tools", "Araçlar")
        )
        
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            self.config_manager.get_ui_text("nav_settings", "Ayarlar")
        )
        
        # Add separator before bottom items
        self.navigationInterface.addSeparator()
        
        # Add Patreon support link at bottom
        self.navigationInterface.addItem(
            routeKey='patreon',
            icon=FIF.HEART,
            text=self.config_manager.get_ui_text("nav_support", "Destek Ol"),
            onClick=self._open_patreon,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )
        
        # Add about at bottom
        self.addSubInterface(
            self.about_interface,
            FIF.INFO,
            self.config_manager.get_ui_text("nav_about", "Hakkında"),
            position=NavigationItemPosition.BOTTOM
        )

    def _open_patreon(self):
        """Open Patreon donation page."""
        url = QUrl("https://www.patreon.com/c/LordOfTurk")
        QDesktopServices.openUrl(url)
        
        # Show info bar
        InfoBar.success(
            title=self.config_manager.get_ui_text("patreon_thanks_title", "Teşekkürler!"),
            content=self.config_manager.get_ui_text("patreon_thanks_content", "Desteklediğiniz için teşekkür ederiz!"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _check_for_updates(self, manual=False):
        """Check for updates in background."""
        if not manual and not getattr(self.config_manager.app_settings, 'check_for_updates', True):
            self.logger.info("Automatic update check disabled in settings")
            return
            
        self._manual_update_check = manual # Set flag before starting
        self.update_worker = UpdateCheckWorker(VERSION, self)
        self.update_worker.finished.connect(self._on_update_check_finished)
        self.update_worker.start()

    def _on_update_check_finished(self, result):
        """Handle update check results."""
        # Detect if this was a manual check (triggered from settings)
        is_manual = getattr(self, "_manual_update_check", False)
        self._manual_update_check = False # Reset flag

        if result and result.update_available:
            self.logger.info(f"Update available: {result.latest_version}")
            
            # Show update notification with button
            bar = InfoBar.info(
                title=self.config_manager.get_ui_text("update_available_title", "Update Available"),
                content=self.config_manager.get_ui_text("update_available_content", "A new version {version} is available.").format(version=result.latest_version),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=-1,  # Keep visible until user acts
                parent=self
            )
            
            # Add action button to open releases
            bar.setCustomBackgroundColor("#0078D4", "#005A9E")
            
            # Since qfluentwidgets InfoBar doesn't easily support adding custom buttons via API 
            # in its simple form, we'll use a traditional message box for the actual prompt
            # for maximum reliability, or just keep it simple with a persistent notification.
            # However, for a better UX, let's use a standard dialog invitation if they click it.
            
            reply = QMessageBox.information(
                self,
                self.config_manager.get_ui_text("update_available_title", "Update Available"),
                self.config_manager.get_ui_text("update_available_message", "A new version {version} is available. Download now?").format(version=result.latest_version),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(result.release_url))
        elif result and not result.update_available and not result.error:
            # If it was a manual check, show "Up to date"
            self.logger.info(f"Already at latest version: {VERSION}")
            if is_manual:
                self.show_info_bar(
                    "success",
                    self.config_manager.get_ui_text("success", "Başarılı"),
                    self.config_manager.get_ui_text("update_up_to_date", "Güncelsiniz (v{current})").format(current=VERSION)
                )
        elif result and result.error:
            self.logger.warning(f"Update check failed: {result.error}")
            if is_manual:
                self.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    self.config_manager.get_ui_text("update_check_failed", "Güncelleme kontrolü başarısız: {error}").format(error=result.error)
                )

    def show_info_bar(self, level: str, title: str, content: str, duration: int = 3000):
        """Show an InfoBar notification."""
        if level == "success":
            InfoBar.success(title, content, orient=Qt.Orientation.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP,
                          duration=duration, parent=self)
        elif level == "warning":
            InfoBar.warning(title, content, orient=Qt.Orientation.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP,
                          duration=duration, parent=self)
        elif level == "error":
            InfoBar.error(title, content, orient=Qt.Orientation.Horizontal,
                         isClosable=True, position=InfoBarPosition.TOP,
                         duration=duration, parent=self)
        else:
            InfoBar.info(title, content, orient=Qt.Orientation.Horizontal,
                        isClosable=True, position=InfoBarPosition.TOP,
                        duration=duration, parent=self)

    def closeEvent(self, event):
        """Handle window close event."""
        # Save any pending settings
        try:
            self.config_manager.save_config()
        except Exception as e:
            self.logger.error(f"Error saving config on close: {e}")
        
        super().closeEvent(event)
