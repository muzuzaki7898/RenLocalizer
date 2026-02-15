# -*- coding: utf-8 -*-
"""
Project Import / Export
========================

Bundles RenLocalizer project state into a portable `.rlproj` archive
(ZIP containing JSON manifests + cache + glossary).

Archive layout
--------------
    manifest.json          — version, project name, timestamp
    settings.json          — TranslationSettings + AppSettings snapshot
    glossary.json          — term glossary
    critical_terms.json    — critical term list
    never_translate.json   — never-translate rules
    cache/
      translation_cache.json — engine → lang → lang → text map
"""

from __future__ import annotations

import json
import logging
import os
import time
import zipfile
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.version import VERSION

logger = logging.getLogger(__name__)

RLPROJ_EXTENSION = ".rlproj"
MANIFEST_NAME = "manifest.json"
CURRENT_RLPROJ_VERSION = 1  # bump when archive layout changes


# ────────────────────────── Export ──────────────────────────

def export_project(
    output_path: str,
    *,
    config_manager,
    project_name: str = "",
    cache_data: Optional[Dict] = None,
    include_api_keys: bool = False,
) -> str:
    """
    Export current project state to a `.rlproj` archive.

    Args:
        output_path:      Destination file path (should end with .rlproj).
        config_manager:   The active ConfigManager instance.
        project_name:     Human-readable project name (auto-derived if empty).
        cache_data:       Translation cache dict (engine→src→tgt→text).
                          Pass ``None`` to skip cache export.
        include_api_keys: Whether to include API keys in the archive.

    Returns:
        Absolute path of the created archive.
    """
    out = Path(output_path)
    if not out.suffix:
        out = out.with_suffix(RLPROJ_EXTENSION)

    if not project_name:
        last_dir = getattr(config_manager.app_settings, "last_input_directory", "")
        project_name = os.path.basename(last_dir) if last_dir else "Untitled"

    # ── manifest ──
    manifest = {
        "rlproj_version": CURRENT_RLPROJ_VERSION,
        "app_version": VERSION,
        "project_name": project_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_language": config_manager.translation_settings.source_language,
        "target_language": config_manager.translation_settings.target_language,
    }

    # ── settings snapshot ──
    settings_snapshot: Dict[str, Any] = {
        "translation_settings": asdict(config_manager.translation_settings),
        "app_settings": asdict(config_manager.app_settings),
    }
    if include_api_keys:
        settings_snapshot["api_keys"] = asdict(config_manager.api_keys)

    # Strip proxy for safety
    settings_snapshot["proxy_settings"] = asdict(config_manager.proxy_settings)
    settings_snapshot["proxy_settings"].pop("proxy_url", None)

    # ── glossary + terms ──
    glossary = getattr(config_manager, "glossary", {}) or {}
    critical_terms = getattr(config_manager, "critical_terms", []) or []
    never_translate = getattr(config_manager, "never_translate_rules", {}) or {}

    # ── write archive ──
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(MANIFEST_NAME, _to_json(manifest))
        zf.writestr("settings.json", _to_json(settings_snapshot))
        zf.writestr("glossary.json", _to_json(glossary))
        zf.writestr("critical_terms.json", _to_json(critical_terms))
        zf.writestr("never_translate.json", _to_json(never_translate))

        if cache_data:
            zf.writestr("cache/translation_cache.json", _to_json(cache_data))

    logger.info("Project exported → %s (%d bytes)", out, out.stat().st_size)
    return str(out.resolve())


# ────────────────────────── Import ──────────────────────────

class ProjectImportResult:
    """Result of an import operation."""

    def __init__(self):
        self.manifest: Dict[str, Any] = {}
        self.settings: Dict[str, Any] = {}
        self.glossary: Dict[str, str] = {}
        self.critical_terms: list = []
        self.never_translate: Dict = {}
        self.cache_data: Optional[Dict] = None
        self.warnings: list[str] = []
        self.ok: bool = True

    @property
    def project_name(self) -> str:
        return self.manifest.get("project_name", "Unknown")

    @property
    def source_language(self) -> str:
        return self.manifest.get("source_language", "auto")

    @property
    def target_language(self) -> str:
        return self.manifest.get("target_language", "")

    def summary(self) -> str:
        parts = [f"Project: {self.project_name}"]
        parts.append(f"Languages: {self.source_language} → {self.target_language}")
        parts.append(f"Glossary entries: {len(self.glossary)}")
        parts.append(f"Critical terms: {len(self.critical_terms)}")
        if self.cache_data:
            try:
                total = sum(
                    len(texts)
                    for engines in self.cache_data.values()
                    for src_langs in engines.values()
                    for texts in src_langs.values()
                )
                parts.append(f"Cached translations: ~{total}")
            except (AttributeError, TypeError):
                parts.append("Cached translations: (unknown structure)")
        if self.warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
        return "\n".join(parts)


def import_project(archive_path: str) -> ProjectImportResult:
    """
    Read a `.rlproj` archive and return its contents.

    Does NOT apply settings automatically — the caller decides what to merge.

    Args:
        archive_path: Path to the .rlproj file.

    Returns:
        ProjectImportResult with all extracted data.
    """
    result = ProjectImportResult()
    p = Path(archive_path)

    if not p.exists():
        result.ok = False
        result.warnings.append(f"File not found: {archive_path}")
        return result

    try:
        with zipfile.ZipFile(str(p), "r") as zf:
            names = zf.namelist()

            # ZIP bomb guard — reject archives with excessive uncompressed size
            _MAX_ENTRY_SIZE = 100 * 1024 * 1024  # 100 MB per entry
            _MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500 MB total
            total_uncompressed = 0
            for info in zf.infolist():
                if info.file_size > _MAX_ENTRY_SIZE:
                    result.ok = False
                    result.warnings.append(
                        f"Entry '{info.filename}' exceeds size limit "
                        f"({info.file_size / 1024 / 1024:.0f} MB > {_MAX_ENTRY_SIZE / 1024 / 1024:.0f} MB)"
                    )
                    return result
                total_uncompressed += info.file_size
            if total_uncompressed > _MAX_TOTAL_SIZE:
                result.ok = False
                result.warnings.append(
                    f"Archive total uncompressed size exceeds limit "
                    f"({total_uncompressed / 1024 / 1024:.0f} MB > {_MAX_TOTAL_SIZE / 1024 / 1024:.0f} MB)"
                )
                return result

            # manifest (required)
            if MANIFEST_NAME not in names:
                result.ok = False
                result.warnings.append("Invalid archive: missing manifest.json")
                return result

            result.manifest = _from_json(zf.read(MANIFEST_NAME))

            # Version check
            ver = result.manifest.get("rlproj_version", 0)
            if ver > CURRENT_RLPROJ_VERSION:
                result.warnings.append(
                    f"Archive version ({ver}) is newer than supported ({CURRENT_RLPROJ_VERSION}). "
                    "Some data may not be loaded correctly."
                )

            # settings
            if "settings.json" in names:
                result.settings = _from_json(zf.read("settings.json"))

            # glossary
            if "glossary.json" in names:
                result.glossary = _from_json(zf.read("glossary.json"))
                if not isinstance(result.glossary, dict):
                    result.warnings.append("glossary.json is not a dict — skipped")
                    result.glossary = {}

            # critical terms
            if "critical_terms.json" in names:
                result.critical_terms = _from_json(zf.read("critical_terms.json"))
                if not isinstance(result.critical_terms, list):
                    result.warnings.append("critical_terms.json is not a list — skipped")
                    result.critical_terms = []

            # never translate
            if "never_translate.json" in names:
                result.never_translate = _from_json(zf.read("never_translate.json"))

            # cache
            cache_path = "cache/translation_cache.json"
            if cache_path in names:
                result.cache_data = _from_json(zf.read(cache_path))

    except zipfile.BadZipFile:
        result.ok = False
        result.warnings.append("File is not a valid ZIP archive")
    except Exception as e:
        result.ok = False
        result.warnings.append(f"Import error: {e}")

    logger.info("Project imported from %s — %s", p, "OK" if result.ok else "FAILED")
    return result


def apply_import(
    result: ProjectImportResult,
    config_manager,
    *,
    merge_glossary: bool = True,
    merge_cache: bool = True,
    apply_settings: bool = True,
) -> list[str]:
    """
    Apply imported project data to the current ConfigManager.

    Args:
        result:          The ProjectImportResult from import_project().
        config_manager:  Active ConfigManager instance.
        merge_glossary:  Merge glossary (True) or replace (False).
        merge_cache:     Merge cache into current cache.
        apply_settings:  Overwrite translation settings.

    Returns:
        List of warning/info messages.
    """
    from dataclasses import fields as dc_fields
    from src.utils.config import TranslationSettings, AppSettings

    messages: list[str] = []

    # ── Settings ──
    if apply_settings and result.settings:
        ts_data = result.settings.get("translation_settings", {})
        if ts_data:
            valid_fields = {f.name for f in dc_fields(TranslationSettings)}
            filtered = {k: v for k, v in ts_data.items() if k in valid_fields}
            try:
                config_manager.translation_settings = TranslationSettings(**filtered)
                messages.append(f"Translation settings applied ({len(filtered)} fields)")
            except Exception as e:
                messages.append(f"Could not apply translation settings: {e}")

        app_data = result.settings.get("app_settings", {})
        if app_data:
            valid_fields = {f.name for f in dc_fields(AppSettings)}
            filtered = {k: v for k, v in app_data.items() if k in valid_fields}
            try:
                config_manager.app_settings = AppSettings(**filtered)
                messages.append(f"App settings applied ({len(filtered)} fields)")
            except Exception as e:
                messages.append(f"Could not apply app settings: {e}")

    # ── Glossary ──
    if result.glossary:
        current_glossary = getattr(config_manager, 'glossary', None) or {}
        if merge_glossary:
            before = len(current_glossary)
            current_glossary.update(result.glossary)
            config_manager.glossary = current_glossary
            added = len(config_manager.glossary) - before
            messages.append(f"Glossary merged: {added} new entries (total {len(config_manager.glossary)})")
        else:
            config_manager.glossary = dict(result.glossary)
            messages.append(f"Glossary replaced: {len(config_manager.glossary)} entries")

    # ── Critical terms ──
    if result.critical_terms:
        existing = set(config_manager.critical_terms) if isinstance(config_manager.critical_terms, list) else set()
        for term in result.critical_terms:
            existing.add(term)
        config_manager.critical_terms = sorted(existing)
        messages.append(f"Critical terms: {len(config_manager.critical_terms)} total")

    # ── Never-translate ──
    if result.never_translate:
        if isinstance(config_manager.never_translate_rules, dict):
            config_manager.never_translate_rules.update(result.never_translate)
        messages.append("Never-translate rules merged")

    # ── Save ──
    try:
        config_manager.save_config()
        messages.append("Configuration saved")
    except Exception as e:
        messages.append(f"Could not save config: {e}")

    return messages


# ────────────────────────── Helpers ──────────────────────────

def _to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _from_json(data: bytes) -> Any:
    return json.loads(data.decode("utf-8-sig"))
