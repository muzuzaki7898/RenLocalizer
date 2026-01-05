"""Utility helpers for managing the UnRen-forall toolkit.

This module downloads, caches and launches Lurmel's UnRen batch scripts,
allowing RenLocalizer to automatically extract/decompile Ren'Py projects
before parsing them.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from src.utils.config import ConfigManager
from src.utils.unrpa_adapter import UnrpaAdapter


@dataclass
class UnRenDownloadResult:
    """Metadata for the downloaded UnRen package."""

    root_path: Path
    version_label: str
    source_url: str


class UnRenManager:
    """Handles downloading and launching the UnRen batch scripts."""

    DEFAULT_RELEASE_URL = (
        "https://github.com/Lurmel/UnRen-forall/releases/download/"
        "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.17/"
        "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.14.zip"
    )
    FALLBACK_RELEASE_URLS = [
        (
            "https://github.com/Lurmel/UnRen-forall/releases/download/"
            "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.17/UnRen-link.txt"
        ),
        "https://github.com/Lurmel/UnRen-forall/releases/latest/download/UnRen-forall.zip",
        (
            "https://github.com/Lurmel/UnRen-forall/releases/download/"
            "UnRen-forall_la_0.35-le_9.6.47-cu_9.7.14/"
            "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.14.zip"
        ),
    ]

    SCRIPT_NAMES = {
        "auto": "UnRen-forall.bat",
        "forall": "UnRen-forall.bat",
        "legacy": "UnRen-legacy.bat",
        "current": "UnRen-current.bat",
    }

    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Paths & availability
    # ------------------------------------------------------------------
    def get_cache_dir(self) -> Path:
        """Return the folder where UnRen should be cached."""

        if os.name == "nt":
            base = Path(os.getenv("LOCALAPPDATA", Path.home()))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "RenLocalizer" / "unren"

    def get_custom_path(self) -> Optional[Path]:
        """Return user-provided UnRen location, if any."""

        custom = (self.config.app_settings.unren_custom_path or "").strip()
        if custom:
            path = Path(custom)
            if path.exists():
                # Only accept custom path if it contains .bat scripts for UnRen (Windows only)
                if os.name == 'nt':
                     found_script = any(path.glob('**/*.bat'))
                     if found_script:
                         return path
                     self.logger.warning("Configured UnRen path doesn't contain batch scripts: %s", path)
                     return None
                else:
                    # On Linux/Mac, we accept any folder if we are just using the path setting 
                    # for something else, but strictly speaking we don't need a path for the library.
                    return path
            self.logger.warning("Configured UnRen path does not exist: %s", path)
        return None

    def get_unren_root(self) -> Optional[Path]:
        """Locate the folder containing the UnRen batch files."""

        # On non-Windows, we don't rely on the batch files if we have the adapter
        if os.name != "nt":
            return self.get_cache_dir()

        custom = self.get_custom_path()
        if custom:
            return custom

        cache_dir = self.get_cache_dir()
        if cache_dir.exists():
            return cache_dir
        return None

    def is_available(self) -> bool:
        """Check if archive extraction tool is ready for use."""
        # Use unrpa library on ALL platforms (more reliable than batch scripts)
        return UnrpaAdapter.is_available()

    def verify_installation(self) -> dict:
        """Return a dict with details about the installed UnRen package.

        Useful for UI preflight checks and debug reporting.
        """
        root = self.get_unren_root()
        details = {
            'installed': False,
            'root': str(root) if root else None,
            'scripts': [],
            'errors': []
        }
        if not root:
            details['errors'].append('UnRen root not found')
            return details
        try:
            # enumerate candidate scripts
            for s in root.glob('**/*.bat'):
                details['scripts'].append(str(s))
            details['installed'] = len(details['scripts']) > 0
        except Exception as exc:  # pragma: no cover - introspection
            details['errors'].append(str(exc))
        return details

    # ------------------------------------------------------------------
    # Download / extraction
    # ------------------------------------------------------------------
    def ensure_available(self, force_download: bool = False) -> Path:
        """Ensure archive extraction tool is available."""
        # Use unrpa library on ALL platforms now (batch scripts are unreliable)
        if UnrpaAdapter.is_available():
            return self.get_cache_dir()
        else:
            raise RuntimeError(
                "unrpa library not found. Please install it with: pip install unrpa\n"
                "This is required for extracting .rpa archive files."
            )

    def force_redownload(self) -> Path:
        """For compatibility - just check if unrpa is available."""
        # With unrpa, there's nothing to "redownload" - it's a pip package
        if UnrpaAdapter.is_available():
            if self.parent_window if hasattr(self, 'parent_window') else None:
                pass  # unrpa is already installed
            return self.get_cache_dir()
        else:
            raise RuntimeError(
                "unrpa library not found. Please install it with: pip install unrpa"
            )

    def _download_and_extract(self) -> UnRenDownloadResult:
        """Download the UnRen zip and extract it to cache dir."""

        target_dir = self.get_cache_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        urls = [self.DEFAULT_RELEASE_URL, *self.FALLBACK_RELEASE_URLS]
        last_error: Optional[Exception] = None
        zip_path = target_dir / "UnRen-forall.zip"

        for url in urls:
            try:
                self.logger.info("Downloading UnRen package from %s", url)
                self._stream_download(url, zip_path)
                version = self._infer_version_from_filename(zip_path.name)
                self._extract_zip(zip_path, target_dir)
                zip_path.unlink(missing_ok=True)
                return UnRenDownloadResult(root_path=target_dir, version_label=version, source_url=url)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.logger.warning("Failed to download from %s: %s", url, exc)

        raise RuntimeError("Could not download UnRen package") from last_error

    def _stream_download(self, url: str, destination: Path) -> None:
        """Download a URL to the given destination path."""

        if url.lower().endswith(".txt"):
            resolved = self._extract_url_from_text_link(url)
            if not resolved:
                raise RuntimeError("Could not resolve download URL from link file")
            self.logger.info("Resolved UnRen link helper to %s", resolved)
            self._stream_download(resolved, destination)
            return

        with urlopen(url, timeout=60) as response, open(destination, "wb") as out_file:
            chunk = response.read(8192)
            while chunk:
                out_file.write(chunk)
                chunk = response.read(8192)

    def _extract_url_from_text_link(self, url: str) -> Optional[str]:
        """Download a helper text file and extract the first https URL."""

        try:
            with urlopen(url, timeout=30) as response:
                data = response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError) as exc:  # pragma: no cover - network
            self.logger.warning("Failed to read redirect link %s: %s", url, exc)
            return None

        match = re.search(r"https?://\S+", data)
        if match:
            candidate = match.group(0).strip()
            # Strip trailing punctuation/newlines
            candidate = candidate.rstrip('\n\r\t\'"')
            return candidate
        self.logger.warning("Could not find download URL inside %s", url)
        return None

    def _extract_zip(self, zip_path: Path, destination: Path) -> None:
        """Extract the downloaded archive into destination."""

        temp_dir = Path(tempfile.mkdtemp(prefix="unren_extract_"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            # Some archives place everything inside a top-level folder like 'UnRen-forall'
            # We want to flatten the archive contents into our destination so looking
            # for scripts is deterministic.
            # Move extracted content up one level if needed.
            entries = list(temp_dir.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                # Single top-level folder found, use its content
                top = entries[0]
                for item in top.iterdir():
                    target = destination / item.name
                    if target.exists():
                        if target.is_file():
                            target.unlink()
                        else:
                            shutil.rmtree(target)
                    shutil.move(str(item), target)
            else:
                # Move everything directly
                for item in entries:
                    target = destination / item.name
                    if target.exists():
                        if target.is_file():
                            target.unlink()
                        else:
                            shutil.rmtree(target)
                    shutil.move(str(item), target)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _infer_version_from_filename(self, filename: str) -> str:
        """Best-effort extraction of version label from archive name."""

        stem = filename.replace(".zip", "")
        return stem or f"downloaded-{datetime.utcnow().strftime('%Y%m%d')}"

    # ------------------------------------------------------------------
    # Variant detection & invocation
    # ------------------------------------------------------------------
    def detect_variant_for_project(self, project_dir: Path) -> str:
        """Heuristic to decide which UnRen script to run for a project."""

        project_dir = project_dir.resolve()
        version_file = project_dir / "renpy-version.txt"
        if version_file.exists():
            try:
                version_text = version_file.read_text(encoding="utf-8", errors="ignore")
                major = self._parse_major_version(version_text)
                if major and major >= 8:
                    return "current"
                if major and major < 8:
                    return "legacy"
            except Exception:  # noqa: BLE001
                pass

        # Fallback: let UnRen-forall auto-detect
        return "auto"

    def _parse_major_version(self, version_text: str) -> Optional[int]:
        digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in version_text)
        parts = [p for p in digits.split() if p]
        if not parts:
            return None
        try:
            return int(parts[0].split(".")[0])
        except ValueError:
            return None

    def run_unren(
        self,
        project_dir: Path,
        variant: str = "auto",
        wait: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
        automation_script: Optional[str] = None,
        timeout: Optional[int] = 300,  # 5 minute default timeout for automation
    ) -> subprocess.Popen:
        """Extract RPA archives using unrpa library.

        This method now uses the unrpa Python library on ALL platforms
        for more reliable archive extraction. The batch scripts are no longer used.

        Returns a mock Popen-like object for compatibility.
        """
        self.logger.info("Running UnRPA extraction on %s", project_dir)
        
        adapter = UnrpaAdapter()
        if not adapter.is_available():
            raise RuntimeError(
                "unrpa library is not installed. Please run: pip install unrpa"
            )
        
        # Find the 'game' directory
        project_dir = Path(project_dir).resolve()
        game_dir = project_dir / "game"
        
        if not game_dir.exists():
            # If project_dir IS the game dir
            if project_dir.name == "game":
                game_dir = project_dir
            else:
                # Try using the project root
                game_dir = project_dir
        
        try:
            success = adapter.extract_game(game_dir)
            
            if success:
                self.logger.info("UnRPA extraction completed successfully.")
                if log_callback:
                    log_callback("RPA arşivleri başarıyla açıldı.")
            else:
                self.logger.warning("No RPA files found or extraction had issues.")
                if log_callback:
                    log_callback("RPA dosyası bulunamadı veya zaten açılmış.")
            
            # Return a mock process-like object for compatibility
            class MockProcess:
                def __init__(self, success_flag):
                    self.returncode = 0 if success_flag else 1
                    self.stdin = None
                    self.stdout = []
                def wait(self, timeout=None): return self.returncode
                def terminate(self): pass
                def kill(self): pass
            
            return MockProcess(success)

        except Exception as e:
            self.logger.error("UnRPA extraction failed: %s", e)
            raise RuntimeError(f"RPA extraction failed: {e}")

        return MockProcess(False)  # Fallback, should never reach here
