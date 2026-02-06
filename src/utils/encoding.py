"""
Encoding helpers to read/write text defensively without crashing on bad bytes.
"""

import os
import time
import tempfile
import chardet
from pathlib import Path
from typing import Optional, Tuple


def read_text_safely(path: Path, preferred: Tuple[str, ...] = ("utf-8-sig", "utf-8")) -> Optional[str]:
    """
    Read file as text with tolerant fallbacks:
    - try preferred encodings first
    - then chardet detection with errors='replace'
    Returns None on I/O failure.
    """
    try:
        raw = path.read_bytes()
    except Exception:
        return None

    for enc in preferred:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    detected = chardet.detect(raw)
    enc = detected.get("encoding") or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except Exception:
        return None


def save_text_safely(path: Path, content: str, encoding: str = "utf-8-sig", newline: str = "\n") -> bool:
    """
    Atomic write with Windows-aware retry logic for 'Access Denied' issues.
    
    1. Writes content to a temporary file in the same directory.
    2. Retries up to 5 times if a PermissionError (File Lock) occurs.
    3. Replaces the destination file atomically (os.replace).
    """
    path_obj = Path(path)
    parent = path_obj.parent
    parent.mkdir(parents=True, exist_ok=True)
    
    # Create temp file in the same directory to ensure it's on the same filesystem
    temp_fd, temp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp", text=True)
    
    try:
        # Step 1: Write to temp
        with os.fdopen(temp_fd, 'w', encoding=encoding, newline=newline) as f:
            f.write(content)
        
        # Step 2: Atomic Swap with Retry (Bypass Windows File Locks)
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if os.path.exists(path_obj):
                    os.replace(temp_path, str(path_obj))
                else:
                    os.rename(temp_path, str(path_obj))
                return True
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.3 * (attempt + 1)) # Incremental backoff
                    continue
                return False
            except Exception:
                return False
    finally:
        # Cleanup temp file if something went wrong and it's still there
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
    return False


def normalize_to_utf8_sig(path: Path) -> bool:
    """
    Rewrite file to UTF-8-SIG with LF newlines safely.
    Returns True if rewrite succeeded.
    """
    text = read_text_safely(path)
    if text is None:
        return False
    return save_text_safely(path, text, encoding="utf-8-sig", newline="\n")

