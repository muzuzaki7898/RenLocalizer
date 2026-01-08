# -*- coding: utf-8 -*-
"""
Info Interface
==============

Fluent-style information center page with collapsible sections.
Replaces the old popup-based InfoDialog with an integrated navigation page.
"""

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup, SettingCard,
    FluentIcon as FIF, TitleLabel, BodyLabel, TextEdit, CardWidget,
    PrimaryPushSettingCard, HyperlinkCard
)

from src.utils.config import ConfigManager


class InfoInterface(ScrollArea):
    """Information center interface with Fluent-style cards."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent

        self.setObjectName("infoInterface")
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
        # Get dialog data from JSON
        self.dialog_data = self.config_manager.get_ui_text("info_dialog")
        if isinstance(self.dialog_data, str):
            self.dialog_data = {}

        # Title
        title_label = TitleLabel(
            self.config_manager.get_ui_text("nav_info_center", "Bilgi Merkezi")
        )
        self.expand_layout.addWidget(title_label)

        # Create all sections
        self._create_translation_engines_section()
        self._create_formats_section()
        self._create_multi_endpoint_section()
        self._create_performance_section()
        self._create_features_section()
        self._create_troubleshooting_section()
        self._create_unren_section()

    def _create_formats_section(self):
        """Create output formats information section."""
        formats_data = self.dialog_data.get("formats", {})
        if not formats_data:
            return

        group = SettingCardGroup(
            self.config_manager.get_ui_text("info_formats_title", "Çıktı Dosya Formatları"),
            self.scroll_widget
        )

        # SIMPLE Format Card
        simple_data = formats_data.get("simple", {})
        if simple_data:
            simple_card = self._create_info_card(
                icon=FIF.DOCUMENT,
                title=simple_data.get("title", "SIMPLE Format (Varsayılan)"),
                features=simple_data.get("features", []),
                example=simple_data.get("example", ""),
                recommended=simple_data.get("recommended_for", ""),
                parent=group
            )
            group.addSettingCard(simple_card)

        # OLD_NEW Format Card
        old_new_data = formats_data.get("old_new", {})
        if old_new_data:
            old_new_card = self._create_info_card(
                icon=FIF.CODE,
                title=old_new_data.get("title", "OLD_NEW Format (Resmi)"),
                features=old_new_data.get("features", []),
                example=old_new_data.get("example", ""),
                recommended=old_new_data.get("recommended_for", ""),
                parent=group
            )
            group.addSettingCard(old_new_card)

        self.expand_layout.addWidget(group)

    def _create_multi_endpoint_section(self):
        """Create Multi-Endpoint information section."""
        me_data = self.dialog_data.get("multi_endpoint", {})
        if not me_data:
            return

        group = SettingCardGroup(
            me_data.get("title", "Multi-Endpoint Google Translator (v2.1.0)"),
            self.scroll_widget
        )

        # How it Works
        how_it_works = me_data.get("how_it_works", {})
        if how_it_works:
            steps = how_it_works.get("steps", [])
            desc = "\n".join([f"• {step}" for step in steps])
            card = SettingCard(
                icon=FIF.SYNC,
                title=how_it_works.get("title", "Nasıl Çalışır?"),
                content=desc,
                parent=group
            )
            group.addSettingCard(card)

        # Endpoints
        endpoints = me_data.get("endpoints", {})
        google_eps = endpoints.get("google", [])
        lingva_eps = endpoints.get("lingva", [])
        if google_eps or lingva_eps:
            ep_desc = f"Google: {len(google_eps)} endpoint | Lingva: {len(lingva_eps)} fallback"
            card = SettingCard(
                icon=FIF.GLOBE,
                title=endpoints.get("title", "Kullanılan Endpointler"),
                content=ep_desc,
                parent=group
            )
            group.addSettingCard(card)

        # Performance
        perf_data = me_data.get("performance", {})
        if perf_data:
            perf_desc = f"Önce: {perf_data.get('before', 'N/A')} → Sonra: {perf_data.get('after', 'N/A')}"
            card = SettingCard(
                icon=FIF.SPEED_HIGH,
                title=perf_data.get("title", "Performans Karşılaştırması"),
                content=perf_desc,
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_performance_section(self):
        """Create performance settings information section."""
        perf_data = self.dialog_data.get("performance", {})
        if not perf_data:
            return

        group = SettingCardGroup(
            perf_data.get("title", "Performans Ayarları"),
            self.scroll_widget
        )

        # Settings items
        for item in perf_data.get("items", []):
            card = SettingCard(
                icon=FIF.SPEED_MEDIUM,
                title=item.get("name", ""),
                content=item.get("description", ""),
                parent=group
            )
            group.addSettingCard(card)

        # Recommended settings
        recommended = perf_data.get("recommended", {})
        if recommended:
            rec_items = recommended.get("items", [])
            rec_desc = " | ".join(rec_items) if rec_items else ""
            card = SettingCard(
                icon=FIF.COMPLETED,
                title=recommended.get("title", "Önerilen Ayarlar"),
                content=rec_desc,
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_features_section(self):
        """Create features information section."""
        features_data = self.dialog_data.get("features", {})
        if not features_data:
            return

        group = SettingCardGroup(
            features_data.get("title", "Özellikler"),
            self.scroll_widget
        )

        # Read from 'current' array (updated structure)
        for item in features_data.get("current", []):
            card = SettingCard(
                icon=FIF.TAG,
                title=item.get("title", ""),
                content=item.get("description", ""),
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_translation_engines_section(self):
        """Create translation engines information section."""
        engines_data = self.dialog_data.get("translation_engines", {})
        if not engines_data:
            return

        group = SettingCardGroup(
            engines_data.get("title", "Çeviri Motorları"),
            self.scroll_widget
        )

        for engine in engines_data.get("engines", []):
            engine_type = engine.get("type", "")
            desc = f"[{engine_type}] {engine.get('description', '')}"
            card = SettingCard(
                icon=FIF.IOT,
                title=engine.get("name", ""),
                content=desc,
                parent=group
            )
            group.addSettingCard(card)

        # AI note
        ai_note = engines_data.get("ai_note", "")
        if ai_note:
            card = SettingCard(
                icon=FIF.INFO,
                title="AI Ayarları",
                content=ai_note,
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_new_tools_section(self):
        """Create new tools (v2.4.0) information section."""
        tools_data = self.dialog_data.get("new_tools", {})
        if not tools_data:
            return

        group = SettingCardGroup(
            tools_data.get("title", "Yeni Araçlar (v2.4.0)"),
            self.scroll_widget
        )

        for item in tools_data.get("items", []):
            card = SettingCard(
                icon=FIF.APPLICATION,
                title=item.get("name", ""),
                content=item.get("description", ""),
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_troubleshooting_section(self):
        """Create troubleshooting information section."""
        ts_data = self.dialog_data.get("troubleshooting", {})
        if not ts_data:
            return

        group = SettingCardGroup(
            ts_data.get("title", "Sorun Giderme"),
            self.scroll_widget
        )

        for item in ts_data.get("items", []):
            solutions = item.get("solutions", [])
            sol_text = " → ".join(solutions) if solutions else item.get("description", "")
            card = SettingCard(
                icon=FIF.HELP,
                title=item.get("problem", item.get("name", "")),
                content=sol_text,
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_unren_section(self):
        """Create UnRen information section."""
        unren_data = self.dialog_data.get("unren", {})
        if not unren_data:
            return

        group = SettingCardGroup(
            unren_data.get("title", "UnRen Entegrasyonu"),
            self.scroll_widget
        )

        # Description
        desc = unren_data.get("description", "")
        if desc:
            card = SettingCard(
                icon=FIF.ZIP_FOLDER,
                title=self.config_manager.get_ui_text("info_unren_what", "UnRen Nedir?"),
                content=desc,
                parent=group
            )
            group.addSettingCard(card)

        # Features
        features = unren_data.get("features", [])
        if features:
            feat_text = " | ".join(features)
            card = SettingCard(
                icon=FIF.CHECKBOX,
                title=self.config_manager.get_ui_text("info_unren_features", "Özellikler"),
                content=feat_text,
                parent=group
            )
            group.addSettingCard(card)

        # Usage
        usage = unren_data.get("usage", {})
        if usage:
            steps = usage.get("steps", [])
            steps_text = " → ".join(steps)
            card = SettingCard(
                icon=FIF.PLAY,
                title=usage.get("title", "Kullanım"),
                content=steps_text,
                parent=group
            )
            group.addSettingCard(card)

        self.expand_layout.addWidget(group)

    def _create_info_card(
        self,
        icon,
        title: str,
        features: list,
        example: str = "",
        recommended: str = "",
        parent=None
    ) -> SettingCard:
        """Create an info card with features list and optional example."""
        # Build content text
        feat_text = " • ".join(features) if features else ""
        if recommended:
            feat_text += f"\n📌 Önerilen: {recommended}"

        card = SettingCard(
            icon=icon,
            title=title,
            content=feat_text,
            parent=parent
        )

        # If there's an example, we could add it to tooltip
        if example:
            card.setToolTip(f"Örnek:\n{example}")

        return card
