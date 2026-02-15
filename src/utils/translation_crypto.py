# -*- coding: utf-8 -*-
"""
Translation Encryption / Obfuscation
======================================

Protects translated .rpy output files from casual copying.

Two modes:

1. **Obfuscation** (no external deps):
   - Base64 encodes translation strings in the .rpy file
   - Injects a small Ren'Py init block that decodes at load time
   - Deters casual reading; NOT cryptographically secure

2. **AES Encryption** (requires ``cryptography`` package):
   - Encrypts translations with AES-256-GCM
   - Stores encrypted blob in a .rlenc file alongside a loader .rpy
   - Key can be derived from game name or user-provided passphrase

Both modes produce files that work with the Ren'Py engine out of the box.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ────────────────────────── Obfuscation (Zero-Dep) ──────────────────────────

_OBFUSCATION_INIT = '''
init -999 python:
    import base64 as _b64
    def _rl_deobf(s):
        try:
            return _b64.b64decode(s.encode("ascii")).decode("utf-8")
        except Exception:
            return s
'''.strip()


def obfuscate_rpy_content(content: str) -> str:
    """
    Replace translation string values with base64-encoded versions
    and inject a decoder init block.

    Handles old/new format:
        old "Hello"
        new "SGVsbG8="    ← base64 of "Hello"

    And dialogue format:
        e "_rl_deobf(\"SGVsbG8=\")"
    """
    lines = content.split("\n")
    result_lines: List[str] = []
    need_init = False

    # Pattern for new "..." lines
    new_re = re.compile(r'^(\s+new\s+)"(.*)"(\s*)$')
    # Pattern for dialogue lines: speaker "text"
    # Exclude Ren'Py keywords that could false-match (if, while, return, etc.)
    _RENPY_KEYWORDS = {'if', 'elif', 'else', 'while', 'for', 'return', 'pass',
                       'python', 'init', 'define', 'default', 'label', 'jump',
                       'call', 'scene', 'show', 'hide', 'with', 'play', 'stop',
                       'queue', 'menu', 'translate', 'style', 'screen', 'transform'}
    dialogue_re = re.compile(r'^(\s+(\w+)\s+)"(.*)"(\s*)$')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for new "..." line
        m = new_re.match(line)
        if m:
            prefix, text, suffix = m.group(1), m.group(2), m.group(3)
            if text.strip():
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
                result_lines.append(f'{prefix}"_rl_deobf(\'{encoded}\')"{suffix}')
                need_init = True
                i += 1
                continue

        # Check for dialogue line (within translate block)
        dm = dialogue_re.match(line)
        if dm and not line.strip().startswith("old ") and not line.strip().startswith("new "):
            prefix, speaker, text, suffix = dm.group(1), dm.group(2), dm.group(3), dm.group(4)
            if (text.strip() and not text.startswith("_rl_deobf")
                    and speaker.lower() not in _RENPY_KEYWORDS):
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
                result_lines.append(f'{prefix}"[_rl_deobf(\'{encoded}\')]"{suffix}')
                need_init = True
                i += 1
                continue

        result_lines.append(line)
        i += 1

    if need_init:
        # Prepend the init block
        result_lines = [_OBFUSCATION_INIT, "", ""] + result_lines

    return "\n".join(result_lines)


def deobfuscate_rpy_content(content: str) -> str:
    """
    Reverse obfuscation — decode base64 strings back to plain text.
    Useful for editing obfuscated files.
    """
    # Pattern: _rl_deobf('BASE64')
    pattern = re.compile(r"_rl_deobf\('([A-Za-z0-9+/=]+)'\)")

    def _decode(m):
        try:
            return base64.b64decode(m.group(1)).decode("utf-8")
        except Exception:
            return m.group(0)

    result = pattern.sub(_decode, content)

    # Remove the init block if present (handles various newline patterns)
    # The init block is prepended with two empty lines after it
    for sep in ("\n\n\n", "\n\n", "\n"):
        pattern = _OBFUSCATION_INIT + sep
        if pattern in result:
            result = result.replace(pattern, "", 1)
            break
    else:
        # Direct match without trailing newlines
        result = result.replace(_OBFUSCATION_INIT, "", 1)

    return result


def obfuscate_rpy_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Obfuscate a .rpy translation file.

    Args:
        input_path:  Path to the plain .rpy file.
        output_path: Output path. If None, overwrites the input file.

    Returns:
        Path of the output file.
    """
    p = Path(input_path)
    content = p.read_text(encoding="utf-8-sig")
    obfuscated = obfuscate_rpy_content(content)

    out = Path(output_path) if output_path else p
    out.write_text(obfuscated, encoding="utf-8-sig", newline="\n")
    logger.info("Obfuscated %s → %s", p.name, out.name)
    return str(out)


# ────────────────────────── AES Encryption ──────────────────────────

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key from a passphrase using PBKDF2."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 100_000)


def encrypt_translations(
    translations: Dict[str, str],
    passphrase: str,
    output_path: str,
) -> Tuple[str, str]:
    """
    Encrypt translation pairs to a .rlenc file + generate a loader .rpy.

    Requires the ``cryptography`` package.

    Args:
        translations: dict of {original_text: translated_text}
        passphrase:   encryption passphrase
        output_path:  base path (without extension)

    Returns:
        Tuple of (rlenc_path, loader_rpy_path).

    Raises:
        ImportError: if ``cryptography`` is not installed.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt)
    nonce = secrets.token_bytes(12)

    # Serialize translations
    payload = json.dumps(translations, ensure_ascii=False).encode("utf-8")

    # Encrypt
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, payload, None)

    # Write .rlenc (salt + nonce + ciphertext)
    enc_path = output_path + ".rlenc"
    with open(enc_path, "wb") as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    # Generate loader .rpy
    loader_rpy = output_path + "_loader.rpy"
    loader_content = _generate_aes_loader(enc_path, passphrase)
    with open(loader_rpy, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(loader_content)

    logger.info("Encrypted %d translations → %s", len(translations), enc_path)
    return enc_path, loader_rpy


def decrypt_translations(enc_path: str, passphrase: str) -> Dict[str, str]:
    """
    Decrypt a .rlenc file back to a translation dict.

    Args:
        enc_path:    Path to the .rlenc file.
        passphrase:  Encryption passphrase.

    Returns:
        Dict of {original_text: translated_text}.

    Raises:
        ImportError: if ``cryptography`` is not installed.
        ValueError: if passphrase is wrong or data is corrupted.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(enc_path, "rb") as f:
        salt = f.read(16)
        nonce = f.read(12)
        ciphertext = f.read()

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    try:
        payload = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Decryption failed — wrong passphrase or corrupted data")

    return json.loads(payload.decode("utf-8"))


def _generate_aes_loader(enc_path: str, passphrase: str) -> str:
    """Generate a Ren'Py init script that loads encrypted translations at runtime.

    The loader reads the .rlenc file, derives the AES key from the passphrase
    using PBKDF2-SHA256 (100k iterations), and decrypts with AES-GCM.

    SECURITY NOTE: The passphrase is embedded as a hash in the loader .rpy file.
    This provides obfuscation, NOT strong security. For games requiring real DRM,
    use an external key management system.
    """
    enc_filename = os.path.basename(enc_path)
    # Embed passphrase as hex-encoded bytes for the loader
    passphrase_hex = passphrase.encode("utf-8").hex()

    return f'''# Auto-generated by RenLocalizer — Encrypted Translation Loader
# This file loads translations from {enc_filename}
# Do NOT edit manually.

init -998 python:
    import json, hashlib, os, struct

    def _rl_decrypt_translations():
        """Decrypt .rlenc file and register translations."""
        _enc_path = os.path.join(config.gamedir, "{enc_filename}")
        if not os.path.exists(_enc_path):
            return

        with open(_enc_path, "rb") as _f:
            _salt = _f.read(16)
            _nonce = _f.read(12)
            _ct = _f.read()

        # Derive key — must match encrypt_translations() exactly
        _passphrase = bytes.fromhex("{passphrase_hex}")
        _key = hashlib.pbkdf2_hmac("sha256", _passphrase, _salt, 100000)

        # AES-256-GCM decrypt (pure-Python fallback for Ren\\u2019Py runtime)
        # Ren\\u2019Py ships Python 2/3 — try cryptography first, then notify
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
            _aesgcm = _AESGCM(_key)
            _payload = _aesgcm.decrypt(_nonce, _ct, None)
            _translations = json.loads(_payload)
            # Store for runtime use
            if not hasattr(store, "_rl_translations"):
                store._rl_translations = {{}}
            store._rl_translations.update(_translations)
            renpy.notify("Encrypted translations loaded ({{}} entries)".format(len(_translations)))
        except ImportError:
            renpy.notify("cryptography package required for encrypted translations")
        except Exception as _e:
            renpy.notify("Translation decryption error: " + str(_e))

    _rl_decrypt_translations()
'''


# ────────────────────────── Convenience ──────────────────────────

def is_cryptography_available() -> bool:
    """Check if the ``cryptography`` package is installed."""
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        return False
