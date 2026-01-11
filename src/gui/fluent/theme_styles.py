# -*- coding: utf-8 -*-
"""
Theme Styles Module
===================

Comprehensive stylesheet definitions for application themes (Dark, Light, Red, Turquoise).
Designed to work with qfluentwidgets components with FULL internal control.
"""

# =============================================================================
# THEME PALETTES
# =============================================================================

# 1. LIGHT THEME
LIGHT_COLORS = {
    "window_bg": "#FFFFFF",
    "nav_bg": "#F3F3F3",       # Very light grey
    "card_bg": "#FFFFFF",
    "card_hover_bg": "#F9F9F9",
    "card_border": "#E5E5E5",
    "input_bg": "#FFFFFF",
    "input_border": "#E0E0E0",
    "input_hover_border": "#0078D4",
    
    "text_primary": "#000000", # Pure black text
    "text_secondary": "#505050",
    "text_disabled": "#A0A0A0",
    "text_link": "#0078D4",
    
    "accent": "#0078D4",
    "accent_hover": "#106EBE",
    "accent_pressed": "#005A9E",
    "accent_light": "#E9F2FB", # Lighter blue bg
    
    "success": "#107C10",
    "success_bg": "#DFF6DD",
    "warning": "#9D5D00",      # Darker yellow for visibility against white
    "warning_bg": "#FFF4CE",
    "error": "#C50F1F",
    "error_bg": "#FDE7E9",
    "info": "#0078D4",
    "info_bg": "#F0F6FD",
    
    "scrollbar": "#C0C0C0",
    "scrollbar_hover": "#909090",
    "divider": "#E0E0E0",
    "shadow": "rgba(0, 0, 0, 0.05)",
}

# 2. DARK THEME
DARK_COLORS = {
    "window_bg": "#121212",    # Deep Dark (Material-like)
    "nav_bg": "#181818",       # Slightly lighter
    "card_bg": "#202020",      # Card surface
    "card_hover_bg": "#282828",
    "card_border": "#303030",
    "input_bg": "#1C1C1C",
    "input_border": "#383838",
    "input_hover_border": "#60CDFF",
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#CCCCCC",
    "text_disabled": "#606060",
    "text_link": "#60CDFF",
    
    "accent": "#60CDFF",
    "accent_hover": "#73D6FF",
    "accent_pressed": "#4CC2FF",
    "accent_light": "#202020",
    
    "success": "#6CCB5F",
    "success_bg": "#1E3B1E",
    "warning": "#FCE100",
    "warning_bg": "#433519",
    "error": "#FF6B6B",
    "error_bg": "#442222",
    "info": "#60CDFF",
    "info_bg": "#202020",
    
    "scrollbar": "#404040",
    "scrollbar_hover": "#606060",
    "divider": "#303030",
    "shadow": "rgba(0, 0, 0, 0.5)",
}

# 3. RED THEME (GAMER/BOLD)
RED_COLORS = {
    "window_bg": "#1E1E1E",     # Slight warmer dark
    "nav_bg": "#252525",
    "card_bg": "#2D2D2D",
    "card_hover_bg": "#353535",
    "card_border": "#454545",
    "input_bg": "#2D2D2D",
    "input_border": "#555555",
    "input_hover_border": "#D13438", # Red hover
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#B0B0B0",
    "text_disabled": "#666666",
    "text_link": "#FF4343",
    
    "accent": "#D13438",        # Fluent Red
    "accent_hover": "#E83B3F",
    "accent_pressed": "#B92024",
    "accent_light": "#3E1819",  # Dark red background for selection
    
    "success": "#6CCB5F",
    "success_bg": "#1E3B1E",
    "warning": "#FCE100",
    "warning_bg": "#433519",
    "error": "#FF6B6B",
    "error_bg": "#442222",
    "info": "#D13438",          # Use red for info in red theme? Maybe keep blue or use Red
    "info_bg": "#3E1819",
    
    "scrollbar": "#555555",
    "scrollbar_hover": "#D13438", # Red hover scrollbar
    "divider": "#404040",
    "shadow": "rgba(0, 0, 0, 0.4)",
}

# 4. TURQUOISE THEME (MODERN/TEAL)
TURQUOISE_COLORS = {
    "window_bg": "#202324",     # Slight cool tint
    "nav_bg": "#282B2C",
    "card_bg": "#2F3334",
    "card_hover_bg": "#3A3E40",
    "card_border": "#45494A",
    "input_bg": "#2F3334",
    "input_border": "#55595A",
    "input_hover_border": "#00B7C3",
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#B0B6B8",
    "text_disabled": "#666A6B",
    "text_link": "#00B7C3",
    
    "accent": "#00B7C3",        # Teal / Turquoise
    "accent_hover": "#00D8E6",
    "accent_pressed": "#009DA6",
    "accent_light": "#16383A",  # Dark teal background
    
    "success": "#6CCB5F",
    "success_bg": "#1E3B1E",
    "warning": "#FCE100",
    "warning_bg": "#433519",
    "error": "#FF6B6B",
    "error_bg": "#442222",
    "info": "#00B7C3",
    "info_bg": "#16383A",
    
    "scrollbar": "#55595A",
    "scrollbar_hover": "#00B7C3",
    "divider": "#45494A",
    "shadow": "rgba(0, 0, 0, 0.3)",
}

# 5. GREEN THEME (NATURE/MATRIX)
GREEN_COLORS = {
    "window_bg": "#0D1510",     # Very dark green-black
    "nav_bg": "#121C16",
    "card_bg": "#1A2A1F",
    "card_hover_bg": "#243528",
    "card_border": "#2E4033",
    "input_bg": "#1A2A1F",
    "input_border": "#3D5242",
    "input_hover_border": "#00C853",
    
    "text_primary": "#E8F5E9",  # Light green-white
    "text_secondary": "#A5D6A7",
    "text_disabled": "#4A6B4E",
    "text_link": "#00E676",
    
    "accent": "#00C853",        # Green 500
    "accent_hover": "#00E676",  # Green A400
    "accent_pressed": "#00A844",
    "accent_light": "#1B3D20",
    
    "success": "#00E676",
    "success_bg": "#1B3D20",
    "warning": "#FFD600",
    "warning_bg": "#3D3A10",
    "error": "#FF5252",
    "error_bg": "#3D1515",
    "info": "#00C853",
    "info_bg": "#1B3D20",
    
    "scrollbar": "#2E4033",
    "scrollbar_hover": "#00C853",
    "divider": "#2E4033",
    "shadow": "rgba(0, 0, 0, 0.4)",
}

# 6. NEON THEME (CYBERPUNK/MIXED)
NEON_COLORS = {
    "window_bg": "#0A0A14",     # Deep dark blue-black
    "nav_bg": "#0F0F1A",
    "card_bg": "#151525",
    "card_hover_bg": "#1E1E35",
    "card_border": "#2A2A45",
    "input_bg": "#151525",
    "input_border": "#3A3A55",
    "input_hover_border": "#FF6B9D",  # Pink
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#C8C8E8",
    "text_disabled": "#5A5A7A",
    "text_link": "#00D4FF",     # Cyan
    
    "accent": "#FF6B9D",        # Neon Pink
    "accent_hover": "#FF8FB8",
    "accent_pressed": "#E85588",
    "accent_light": "#2A1525",
    
    "success": "#00FF88",       # Neon Green
    "success_bg": "#0A2A1A",
    "warning": "#FFE400",       # Neon Yellow
    "warning_bg": "#2A2A0A",
    "error": "#FF3366",         # Neon Red
    "error_bg": "#2A0A15",
    "info": "#00D4FF",          # Neon Cyan
    "info_bg": "#0A1A2A",
    
    "scrollbar": "#3A3A55",
    "scrollbar_hover": "#9D4EDD",  # Purple on hover
    "divider": "#2A2A45",
    "shadow": "rgba(0, 0, 0, 0.5)",
}


# =============================================================================
# GENERIC GENERATORS
# =============================================================================

def get_theme_stylesheet(c: dict) -> str:
    """
    Generate comprehensive stylesheet based on provided color palette.
    """
    return f"""
    /* ===== GLOBAL STYLES ===== */
    /* REMOVED global QWidget/QLabel styling to prevent font issues and visual flattening */
    
    QDialog, QMessageBox, MessageBox, QMenu {{
        background-color: {c['window_bg']};
        color: {c['text_primary']};
    }}


    
    /* ===== MAIN WINDOW ===== */
    FluentWindow, QMainWindow {{
        background-color: {c['window_bg']};
    }}
    
    QStackedWidget {{
        background-color: {c['window_bg']};
    }}
    
    /* ===== SCROLL AREAS ===== */
    QScrollArea {{
        background-color: {c['window_bg']};
        border: none;
    }}
    
    QScrollArea > QWidget > QWidget {{
        background-color: {c['window_bg']};
    }}
    
    ScrollArea {{
        background-color: {c['window_bg']};
        border: none;
    }}
    
    SmoothScrollArea {{
        background-color: {c['window_bg']};
        border: none;
    }}
    
    /* ===== SCROLLBARS ===== */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar']};
        border-radius: 6px;
        min-height: 30px;
        margin: 2px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar']};
        border-radius: 6px;
        min-width: 30px;
        margin: 2px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* ===== CARDS ===== */
    CardWidget {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
    }}
    
    CardWidget:hover {{
        background-color: {c['card_hover_bg']};
        border-color: {c['accent']};
    }}
    
    /* ===== SETTING CARDS ===== */
    SettingCard {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    SettingCard:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    SettingCardGroup {{
        background-color: transparent;
    }}
    
    ExpandSettingCard {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    /* ===== LABELS ===== */
    /* Force transparent background on ALL label types to prevent dark blocks */
    QLabel, QLabel * {{
        background-color: transparent !important;
        background: transparent !important;
    }}

    TitleLabel, StrongBodyLabel, SubtitleLabel, BodyLabel, CaptionLabel {{
        background-color: transparent !important;
        background: transparent !important;
    }}
    
    /* Setting card internal labels */
    SettingCard QLabel, CardWidget QLabel {{
        background-color: transparent !important;
        background: transparent !important;
    }}


    
    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
        padding: 6px 16px;
    }}
    
    QPushButton:hover {{
        background-color: {c['card_hover_bg']};
        border-color: {c['accent']};
    }}
    
    QPushButton:pressed {{
        background-color: {c['accent_light']};
    }}
    
    PushButton {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    PushButton:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    PrimaryPushButton {{
        background-color: {c['accent']};
        color: #FFFFFF; /* Always white on primary */
        border: none;
        border-radius: 6px;
    }}
    
    PrimaryPushButton:hover {{
        background-color: {c['accent_hover']};
    }}
    
    PrimaryPushButton:pressed {{
        background-color: {c['accent_pressed']};
    }}
    
    TransparentToolButton {{
        background-color: transparent;
        border: none;
    }}
    
    TransparentToolButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    /* ===== INPUT FIELDS ===== */
    QLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    
    QLineEdit:focus {{
        border-color: {c['accent']};
        border-width: 2px;
    }}
    
    QLineEdit:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    LineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    LineEdit:focus {{
        border-color: {c['accent']};
    }}
    
    PasswordLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== TEXT EDIT / TEXT BROWSER ===== */
    QTextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    TextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    QPlainTextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== COMBOBOX ===== */
    QComboBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    
    QComboBox:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    QComboBox::drop-down {{
        border: none;
        padding-right: 10px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        selection-background-color: {c['accent_light']};
        selection-color: {c['text_primary']};
    }}
    
    ComboBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== SLIDERS ===== */
    QSlider::groove:horizontal {{
        background-color: {c['input_border']};
        height: 6px;
        border-radius: 3px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {c['accent']};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: {c['accent_hover']};
    }}
    
    QSlider::sub-page:horizontal {{
        background-color: {c['accent']};
        border-radius: 3px;
    }}
    
    Slider {{
        background-color: transparent;
    }}
    
    /* ===== CHECKBOXES ===== */
    QCheckBox {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['input_border']};
        border-radius: 4px;
        background-color: {c['input_bg']};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
    }}
    
    QCheckBox::indicator:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    /* ===== SWITCH BUTTON ===== */
    SwitchButton {{
        background-color: transparent;
    }}
    
    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {c['input_border']};
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 3px;
    }}
    
    ProgressBar {{
        background-color: {c['input_border']};
        border-radius: 3px;
    }}
    
    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QTabBar::tab {{
        background-color: {c['nav_bg']};
        color: {c['text_secondary']};
        padding: 8px 16px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
    }}
    
    QTabBar::tab:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== TOOLTIPS ===== */
    QToolTip {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    
    /* ===== MENU ===== */
    QMenu {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    
    QMenu::item:selected {{
        background-color: {c['accent_light']};
    }}
    
    QMenu::separator {{
        height: 1px;
        background-color: {c['divider']};
        margin: 4px 8px;
    }}
    
    /* ===== MESSAGE BOX / DIALOG ===== */
    QDialog {{
        background-color: {c['window_bg']};
    }}
    
    QMessageBox {{
        background-color: {c['window_bg']};
    }}
    
    MessageBox {{
        background-color: {c['window_bg']};
    }}
    
    /* ===== INFO BAR ===== */
    InfoBar {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
    }}
    
    /* ===== GROUP BOX ===== */
    QGroupBox {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
    }}
    
    QGroupBox::title {{
        color: {c['text_primary']};
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
    }}
    
    /* ===== TABLE / LIST VIEWS ===== */
    QTableView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
        gridline-color: {c['divider']};
    }}
    
    QTableView::item {{
        padding: 6px;
    }}
    
    QTableView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QHeaderView::section {{
        background-color: {c['nav_bg']};
        color: {c['text_primary']};
        border: none;
        border-bottom: 1px solid {c['divider']};
        padding: 8px;
    }}
    
    QListView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QListView::item {{
        padding: 6px;
        border-radius: 4px;
    }}
    
    QListView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QListView::item:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== TREE VIEW ===== */
    QTreeView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QTreeView::item {{
        padding: 4px;
    }}
    
    QTreeView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QTreeView::item:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== SPIN BOX ===== */
    QSpinBox, QDoubleSpinBox, SpinBox, DoubleSpinBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']} !important;
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 4px 8px;
        min-width: 80px;
        selection-background-color: {c['accent']};
        selection-color: #FFFFFF;
        font-weight: bold;
    }}
    
    QSpinBox:hover, QDoubleSpinBox:hover, SpinBox:hover, DoubleSpinBox:hover {{
        border-color: {c['input_hover_border']};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button, SpinBox::up-button, DoubleSpinBox::up-button {{
        border: none;
        background: transparent;
    }}

    QSpinBox::down-button, QDoubleSpinBox::down-button, SpinBox::down-button, DoubleSpinBox::down-button {{
        border: none;
        background: transparent;
    }}
    
    /* ===== FRAME ===== */
    QFrame {{
        background-color: {c['window_bg']};
    }}
    
    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {c['divider']};
    }}
    
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    
    QSplitter::handle:vertical {{
        height: 1px;
    }}
    """


def get_navigation_stylesheet(c: dict) -> str:
    """
    Specific stylesheet for NavigationInterface based on palette.
    """
    return f"""
    NavigationInterface {{
        background-color: {c['nav_bg']};
        border-right: 1px solid {c['divider']};
    }}
    
    NavigationPanel {{
        background-color: {c['nav_bg']};
    }}
    
    NavigationWidget {{
        background-color: transparent;
    }}
    
    NavigationPushButton {{
        background-color: transparent;
        color: {c['text_primary']};
        border: none;
        border-radius: 6px;
        padding: 8px 12px;
    }}
    
    NavigationPushButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    NavigationPushButton:pressed {{
        background-color: {c['card_border']};
    }}
    
    NavigationPushButton[isSelected="true"] {{
        background-color: {c['accent_light']};
        color: {c['accent']};
        font-weight: bold;
    }}
    
    NavigationTreeWidget {{
        background-color: transparent;
    }}
    
    NavigationSeparator {{
        background-color: {c['divider']};
    }}
    
    /* Ensure Nav labels are readable on custom backgrounds */
    NavigationItem > QLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    """




def get_titlebar_stylesheet(c: dict) -> str:
    """
    Specific stylesheet for TitleBar based on palette.
    """
    return f"""
    TitleBar {{
        background-color: {c['nav_bg']};
    }}
    
    TitleBarButton {{

        background-color: transparent;
        border: none;
    }}
    
    TitleBarButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    MinimizeButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    MaximizeButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    CloseButton:hover {{
        background-color: {c['error']};
    }}
    """


def apply_theme_palette(widget, c: dict) -> None:
    """
    Apply generic palette colors directly to a widget and its children.
    
    Args:
        widget: QWidget to style
        c: color dictionary (palette)
    """
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtWidgets import QWidget
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c['window_bg']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Base, QColor(c['input_bg']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c['card_hover_bg']))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c['card_bg']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Text, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Button, QColor(c['card_bg']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(c['accent']))
    palette.setColor(QPalette.ColorRole.Link, QColor(c['text_link']))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c['accent']))
    
    # White text on highlighted items for everything except possibly light theme
    # But for safety, let's stick to standard internal design
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#FFFFFF'))
    
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c['text_disabled']))
    
    widget.setPalette(palette)
