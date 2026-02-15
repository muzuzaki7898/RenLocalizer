# -*- coding: utf-8 -*-
"""
Data File Extractor Plugin System
====================================

Extensible extractors for non-RPY data files commonly found in Ren'Py projects.
Supports JSON, YAML, and custom formats via a simple plugin interface.

Usage:
    registry = ExtractorRegistry()
    entries = registry.extract_file("game/data/dialogue.json")

Adding a custom extractor:
    @registry.register("toml")
    class TomlExtractor(BaseExtractor):
        ...
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable

logger = logging.getLogger(__name__)


# ────────────────────────── Data Model ──────────────────────────

@dataclass
class ExtractedEntry:
    """A single translatable string extracted from a data file."""
    file: str            # source file path
    key_path: str        # dot-separated path, e.g. "chapters.0.dialogue.2.text"
    original: str        # the original string value
    context: str = ""    # surrounding context or label
    line: int = 0        # approximate line number (0 = unknown)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.file, self.key_path, self.original))


# ────────────────────────── Base Extractor ──────────────────────────

class BaseExtractor(ABC):
    """
    Abstract base class for data file extractors.

    Subclasses must implement ``extract(path)`` → list of ExtractedEntry.
    Optionally override ``can_handle(path)`` for advanced matching.
    """

    # Minimum string length to consider translatable (skip single chars, numbers)
    min_length: int = 2

    # Keys whose values should NEVER be extracted
    skip_keys: Set[str] = frozenset({
        "id", "key", "path", "file", "image", "icon", "sound",
        "music", "audio", "sfx", "bg", "sprite", "animation",
        "script", "code", "class", "type", "tag", "version",
        "color", "font", "style", "xpos", "ypos", "xsize", "ysize",
        "xanchor", "yanchor", "xoffset", "yoffset",
    })

    # Keys whose values SHOULD be extracted (override)
    include_keys: Set[str] = frozenset({
        "text", "dialogue", "message", "name", "title", "description",
        "label", "caption", "tooltip", "hint", "prompt", "question",
        "answer", "option", "choice", "button", "menu_text",
        "notification", "summary", "bio", "note",
    })

    def can_handle(self, path: str) -> bool:
        """Return True if this extractor can process the given file."""
        return True

    @abstractmethod
    def extract(self, path: str) -> List[ExtractedEntry]:
        """Extract translatable strings from the file at *path*."""
        ...

    def write_back(self, path: str, translations: Dict[str, str]) -> bool:
        """
        Write translations back to the file.

        Args:
            path: Original file path.
            translations: key_path → translated_text mapping.

        Returns:
            True on success. Default implementation returns False (read-only).
        """
        return False

    # ── helpers ──

    def _is_translatable(self, key: str, value: Any) -> bool:
        """Heuristic: should this key's value be extracted?"""
        if not isinstance(value, str):
            return False
        if len(value) < self.min_length:
            return False
        # Skip if value looks like a path/URL/colour/number
        if re.match(r'^(https?://|/|\\|#[0-9a-fA-F]{3,8}$|\d+(\.\d+)?$)', value):
            return False
        # Key-based filtering
        base_key = key.rsplit(".", 1)[-1].lower() if "." in key else key.lower()
        if base_key in self.skip_keys:
            return False
        # If key matches include list, always accept
        if base_key in self.include_keys:
            return True
        # Default: accept strings that contain letters and are >3 chars
        if len(value) >= 3 and re.search(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF]', value):
            return True
        return False


# ────────────────────────── JSON Extractor ──────────────────────────

class JsonExtractor(BaseExtractor):
    """
    Extracts translatable strings from JSON files.

    Handles nested dicts/lists and filters based on key heuristics.
    """

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(".json")

    def extract(self, path: str) -> List[ExtractedEntry]:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning("JSON parse error in %s: %s", path, e)
            return []

        entries: List[ExtractedEntry] = []
        self._walk(data, "", path, entries)
        return entries

    def write_back(self, path: str, translations: Dict[str, str]) -> bool:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            return False

        modified = self._apply(data, "", translations)
        if not modified:
            return False

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error("JSON write-back failed for %s: %s", path, e)
            return False

    def _walk(
        self, obj: Any, prefix: str, file_path: str,
        entries: List[ExtractedEntry],
    ):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key_path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, str) and self._is_translatable(key_path, v):
                    entries.append(ExtractedEntry(
                        file=file_path, key_path=key_path, original=v,
                    ))
                elif isinstance(v, (dict, list)):
                    self._walk(v, key_path, file_path, entries)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                key_path = f"{prefix}.{i}"
                if isinstance(item, str) and self._is_translatable(prefix, item):
                    entries.append(ExtractedEntry(
                        file=file_path, key_path=key_path, original=item,
                    ))
                elif isinstance(item, (dict, list)):
                    self._walk(item, key_path, file_path, entries)

    def _apply(self, obj: Any, prefix: str, translations: Dict[str, str]) -> bool:
        changed = False
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                key_path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, str) and key_path in translations:
                    obj[k] = translations[key_path]
                    changed = True
                elif isinstance(v, (dict, list)):
                    if self._apply(v, key_path, translations):
                        changed = True

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                key_path = f"{prefix}.{i}"
                if isinstance(item, str) and key_path in translations:
                    obj[i] = translations[key_path]
                    changed = True
                elif isinstance(item, (dict, list)):
                    if self._apply(item, key_path, translations):
                        changed = True
        return changed


# ────────────────────────── YAML Extractor ──────────────────────────

class YamlExtractor(BaseExtractor):
    """
    Extracts translatable strings from YAML files.

    Uses PyYAML if available; degrades gracefully without it.
    """

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith((".yaml", ".yml"))

    def extract(self, path: str) -> List[ExtractedEntry]:
        yaml = _get_yaml()
        if yaml is None:
            logger.info("PyYAML not installed — skipping %s", path)
            return []

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.warning("YAML parse error in %s: %s", path, e)
            return []

        if data is None:
            return []

        entries: List[ExtractedEntry] = []
        self._walk(data, "", path, entries)
        return entries

    def write_back(self, path: str, translations: Dict[str, str]) -> bool:
        """Write translated strings back. WARNING: YAML comments and formatting may be lost."""
        yaml = _get_yaml()
        if yaml is None:
            return False
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = yaml.safe_load(f)
        except Exception:
            return False

        modified = self._apply(data, "", translations)
        if not modified:
            return False

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception as e:
            logger.error("YAML write-back failed for %s: %s", path, e)
            return False

    def _walk(self, obj, prefix, file_path, entries):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kp = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, str) and self._is_translatable(kp, v):
                    entries.append(ExtractedEntry(file=file_path, key_path=kp, original=v))
                elif isinstance(v, (dict, list)):
                    self._walk(v, kp, file_path, entries)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                kp = f"{prefix}.{i}"
                if isinstance(item, str) and self._is_translatable(prefix, item):
                    entries.append(ExtractedEntry(file=file_path, key_path=kp, original=item))
                elif isinstance(item, (dict, list)):
                    self._walk(item, kp, file_path, entries)

    def _apply(self, obj, prefix, translations):
        changed = False
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                kp = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, str) and kp in translations:
                    obj[k] = translations[kp]
                    changed = True
                elif isinstance(v, (dict, list)):
                    if self._apply(v, kp, translations):
                        changed = True
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                kp = f"{prefix}.{i}"
                if isinstance(item, str) and kp in translations:
                    obj[i] = translations[kp]
                    changed = True
                elif isinstance(item, (dict, list)):
                    if self._apply(item, kp, translations):
                        changed = True
        return changed


# ────────────────────────── Registry ──────────────────────────

class ExtractorRegistry:
    """
    Central registry for data file extractors.

    Built-in extractors (JSON, YAML) are registered automatically.
    Users can add custom extractors via ``register()``.
    """

    def __init__(self):
        self._extractors: Dict[str, BaseExtractor] = {}
        # Register built-ins
        self._extractors["json"] = JsonExtractor()
        self._extractors["yaml"] = YamlExtractor()

    def register(self, name: str, extractor: Optional[BaseExtractor] = None):
        """
        Register an extractor, either directly or as a decorator.

        Usage (direct):
            registry.register("csv", CsvExtractor())

        Usage (decorator):
            @registry.register("csv")
            class CsvExtractor(BaseExtractor): ...
        """
        if extractor is not None:
            self._extractors[name] = extractor
            return extractor

        # Decorator form
        def decorator(cls):
            self._extractors[name] = cls()
            return cls
        return decorator

    def get(self, name: str) -> Optional[BaseExtractor]:
        return self._extractors.get(name)

    @property
    def available(self) -> List[str]:
        return list(self._extractors.keys())

    def extract_file(self, path: str) -> List[ExtractedEntry]:
        """
        Auto-detect extractor and extract translatable strings.

        Tries each registered extractor's ``can_handle()`` in order.
        """
        for name, extractor in self._extractors.items():
            if extractor.can_handle(path):
                logger.debug("Using %s extractor for %s", name, path)
                return extractor.extract(path)
        logger.debug("No extractor matched %s", path)
        return []

    def extract_directory(
        self,
        directory: str,
        *,
        recursive: bool = True,
        extensions: Optional[Set[str]] = None,
    ) -> List[ExtractedEntry]:
        """
        Scan a directory for data files and extract translatable content.

        Args:
            directory: Root directory to scan.
            recursive: Walk subdirectories.
            extensions: Limit to these extensions (e.g. {".json", ".yaml"}).
                        Default: all extensions that registered extractors can handle.
        """
        all_entries: List[ExtractedEntry] = []
        root = Path(directory)

        skip_dirs = {"renpy", "__pycache__", "cache", "saves", ".git", "node_modules"}

        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            if not recursive and Path(dirpath) != root:
                dirnames.clear()  # prevent os.walk from entering subdirs
                continue

            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                ext = Path(fname).suffix.lower()
                if extensions and ext not in extensions:
                    continue

                entries = self.extract_file(fpath)
                all_entries.extend(entries)

        logger.info("Extracted %d translatable strings from %s", len(all_entries), directory)
        return all_entries


# ────────────────────────── Optional Dependencies ──────────────────────────

def _get_yaml():
    """Lazy import PyYAML."""
    try:
        import yaml
        return yaml
    except ImportError:
        return None
