# -*- coding: utf-8 -*-
"""
RPA Archive Packer
===================

Pack files into Ren'Py RPA-3.0 archives.
Reverse of rpa_parser.py — creates .rpa files from a directory of .rpy files.

Typical use:
    Pack translated .rpy files back into an .rpa archive that can be dropped
    into the game's ``game/`` folder.

Usage:
    from src.utils.rpa_packer import RPAPacker

    packer = RPAPacker()
    packer.pack_directory("game/tl/turkish", "translations.rpa")
"""

from __future__ import annotations

import logging
import os
import pickle
import secrets
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class RPAPacker:
    """
    Creates RPA-3.0 archives compatible with Ren'Py's archive loader.
    """

    RPA3_VERSION = "RPA-3.0"
    # Default prefix length for obfuscation (Ren'Py standard)
    PREFIX_LEN = 0

    def __init__(self, *, key: Optional[int] = None):
        """
        Args:
            key: XOR obfuscation key. If None, a random key is generated.
        """
        self.key = key if key is not None else secrets.randbits(32)

    def pack_files(
        self,
        files: Dict[str, str],
        output_path: str,
    ) -> str:
        """
        Pack files into an RPA-3.0 archive.

        Args:
            files: Mapping of {archive_path: local_path}.
                   archive_path: path INSIDE the archive (e.g. "tl/turkish/script.rpy")
                   local_path:   actual file on disk
            output_path: Destination .rpa file path.

        Returns:
            Absolute path of the created archive.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Phase 1: Write placeholder header + all file data sequentially
        # Phase 2: Append compressed index
        # Phase 3: Rewrite header with correct offset

        key = self.key
        index: Dict[str, List[Tuple[int, int, bytes]]] = {}

        # Calculate header size dynamically
        # Format: "RPA-3.0 {016x} {08x}\n" = 7 + 1 + 16 + 1 + 8 + 1 = 34 bytes
        header_len = len(f"{self.RPA3_VERSION} {'0' * 16} {'0' * 8}\n".encode("utf-8"))

        with open(str(out), "wb") as f:
            # Write placeholder header
            f.write(b" " * header_len)

            for archive_name, local_path in files.items():
                try:
                    data = Path(local_path).read_bytes()
                except Exception as e:
                    logger.warning("Skipping %s: %s", local_path, e)
                    continue

                offset = f.tell()
                length = len(data)
                prefix = b""

                # Write file data
                f.write(data)

                # Store index entry (XOR-encoded)
                index[archive_name] = [(offset ^ key, length ^ key, prefix)]

            # Write compressed index
            # NOTE: pickle is required for RPA-3.0 format compatibility with Ren'Py.
            # Ren'Py uses pickle.loads() to read the index. This is a known security
            # characteristic of the RPA format — do NOT load untrusted .rpa files.
            index_offset = f.tell()
            index_bytes = pickle.dumps(index, protocol=2)  # protocol 2 for py2 compat
            f.write(zlib.compress(index_bytes))

            # Rewrite header with real offset
            header_line = f"{self.RPA3_VERSION} {index_offset:016x} {key:08x}\n"
            f.seek(0)
            f.write(header_line.encode("utf-8"))

        size = out.stat().st_size
        logger.info(
            "RPA archive created: %s (%d files, %d bytes)",
            out.name, len(index), size
        )
        return str(out.resolve())

    def pack_directory(
        self,
        directory: str,
        output_path: str,
        *,
        base_prefix: str = "",
        extensions: Optional[Set[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
    ) -> str:
        """
        Pack all matching files in a directory into an RPA archive.

        Args:
            directory:    Root directory to pack.
            output_path:  Destination .rpa file.
            base_prefix:  Prefix added to all archive paths (e.g. "tl/turkish/").
            extensions:   Only include files with these extensions.
                          Default: {".rpy", ".rpyc"}
            exclude_dirs: Directory names to skip.

        Returns:
            Absolute path of the created archive.
        """
        if extensions is None:
            extensions = {".rpy", ".rpyc", ".rpym", ".rpymc"}
        if exclude_dirs is None:
            exclude_dirs = {"__pycache__", ".git", "cache", "saves"}

        root = Path(directory)
        files: Dict[str, str] = {}

        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

            for fname in filenames:
                if Path(fname).suffix.lower() not in extensions:
                    continue

                local = os.path.join(dirpath, fname)
                # Archive path is relative to root, with forward slashes
                rel = os.path.relpath(local, str(root)).replace("\\", "/")
                archive_path = f"{base_prefix}{rel}" if base_prefix else rel
                files[archive_path] = local

        if not files:
            logger.warning("No matching files found in %s", directory)
            return ""

        return self.pack_files(files, output_path)


def pack_translations(
    translation_dir: str,
    output_path: str,
    *,
    language: str = "",
) -> str:
    """
    Convenience function: pack translated .rpy files into a distributable .rpa.

    Args:
        translation_dir: Directory containing translated .rpy files.
        output_path:     Output .rpa path. If empty, auto-derived.
        language:        Language code (used for naming if output_path is empty).

    Returns:
        Path to the created .rpa file, or empty string on failure.
    """
    if not output_path:
        lang_suffix = f"_{language}" if language else ""
        output_path = str(Path(translation_dir).parent / f"translations{lang_suffix}.rpa")

    packer = RPAPacker()
    return packer.pack_directory(translation_dir, output_path)
