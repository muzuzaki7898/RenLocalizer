# -*- coding: utf-8 -*-
"""
Syntax Guard Module
===================
Ren'Py sözdizimini (değişkenler, tagler, özellikli karakterler) koruma ve geri yükleme işlemlerini yönetir.
"""

import re
from typing import Dict, Tuple, List

# Try to import rapidfuzz for advanced matching, fallback to basic mode if missing
try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


# Ren'Py variable patterns
RENPY_VAR_PATTERN = re.compile(r'\[([^\[\]]+)\]')  # [variable]
RENPY_TAG_PATTERN = re.compile(r'\{([^\{\}]+)\}')  # {tag}
RENPY_ESCAPED_PATTERN = re.compile(r'\{\{|\}\}')   # {{ }}
RENPY_QMARK_PLACEHOLDER_RE = re.compile(r'\?[A-Za-z]\d{3}\?')
RENPY_ANGLE_PLACEHOLDER_RE = re.compile(r'\u27e6[^\u27e7]+\u27e7')

# Combined protection regex
PROTECT_RE = re.compile(
    r'(\{\{|\}\}|\[\[|'  # Escaped brackets added
    r'\{[^\}]+\}|\[[^\[\]]+\]|'
    r'\?[A-Za-z]\d{3}\?|'
    r'\u27e6[^\u27e7]+\u27e7)'
)

# AI hallucination cleanup patterns
CLEANUP_RE = re.compile(r'\[\s*\[\s*([vteg])\s*(\d+)\s*\]\s*\]', re.IGNORECASE)
# Fix spacing inside placeholders: "[[ t0 ]]" or "[[ t0]]" -> "[[t0]]"
PLACEHOLDER_SPACING_RE = re.compile(r'\[\[\s*([vteg]\d+)\s*\]\]', re.IGNORECASE)
# Safe Mode (Google) cleanup: Fixes "X_RPY_v 0_X" or "X RPY v0 X" -> "X_RPY_v0_X"
SAFE_MODE_CLEANUP_RE = re.compile(r'X[_\s]*RPY[_\s]*([vteg])\s*(\d+)[_\s]*X', re.IGNORECASE)

def protect_renpy_syntax(text: str, use_safe_tag: bool = False) -> Tuple[str, Dict[str, str]]:
    """
    Ren'Py değişkenlerini ve tag'lerini çeviriden korur.
    Metni placeholder'larla değiştirir ve bir geri dönüşüm sözlüğü döner.
    
    Args:
        text (str): Korunacak metin
        use_safe_tag (bool): True ise Google Translate dostu 'Kelime Bazlı' maskeleme kullanır (örn: X_RPY_v0_X).
                             False ise standart Ren'Py benzeri format kullanır (örn: [[v0]]).
    """
    placeholders: Dict[str, str] = {}
    counter = 0
    out_parts: List[str] = []
    last = 0
    
    for m in PROTECT_RE.finditer(text):
        start, end = m.start(), m.end()
        out_parts.append(text[last:start])
        
        token = m.group(0)
        if token in ('{{', '}}'):
            prefix = 'e'
        elif token.startswith('{') and token.endswith('}'):
            prefix = 't'
        else:
            prefix = 'v'
            
        if use_safe_tag:
            # Google Safe Mode: Use word-like tokens to prevent bracket corruption
            # X_RPY_{type}{id}_X  -> Treated as a proper noun by Google
            key = f" X_RPY_{prefix}{counter}_X "
        else:
            # Standard Mode (AI/DeepL): Bracket notation
            key = f" [[{prefix}{counter}]] "
            
        # Strip key for storage, but keep spaces for injection to preventing sticking
        placeholders[key.strip()] = token
        out_parts.append(key)
        counter += 1
        last = end
        
    out_parts.append(text[last:])
    protected = ''.join(out_parts)
    return protected, placeholders

def restore_renpy_syntax(text: str, placeholders: Dict[str, str], enable_fuzzy: bool = True) -> str:
    """
    Placeholder'ları orijinal değerleriyle değiştirir.
    enable_fuzzy: RapidFuzz ile yaklaşık eşleşme yapılıp yapılmayacağı.
    """
    if not text or not placeholders:
        return text

    # Pre-clean known AI corruptions (Bracket mode)
    cleaned_text = CLEANUP_RE.sub(r'[[\1\2]]', text)
    # Fix placeholder spacing: "[[ t0 ]]" -> "[[t0]]"
    cleaned_text = PLACEHOLDER_SPACING_RE.sub(r'[[\1]]', cleaned_text)
    # Fix Safe Mode corruptions (Google): "X_RPY_v 0_X" or "X_RPY_V0_X" -> "X_RPY_v0_X"
    # Use lambda to ensure lowercase (Google sometimes uppercases)
    cleaned_text = SAFE_MODE_CLEANUP_RE.sub(
        lambda m: f"X_RPY_{m.group(1).lower()}{m.group(2)}_X", cleaned_text
    )
    
    result = cleaned_text
    
    # Simple replacement strategy (More complex fuzzy matching logic can be injected here if needed)
    for key, original in placeholders.items():
        # 1. Exact match
        if key in result:
            result = result.replace(key, original)
            continue
            
        # 2. Flexible match (stripped)
        stripped_key = key.strip()
        if stripped_key in result:
            result = result.replace(stripped_key, original)
            continue
            
        # 3. Regex match (spaces inside brackets)
        # [[ v0 ]] -> [[v0]]
        flexible_pattern = re.escape(stripped_key).replace(r'\[\[', r'\[\[\s*').replace(r'\]\]', r'\s*\]\]')
        # Use a temporary placeholder to avoid regex messing up other parts
        if re.search(flexible_pattern, result):
             result = re.sub(flexible_pattern, original, result)
             continue

        # 4. Fuzzy Match (RapidFuzz) - The "Magic" Layer
        # Only strict if RapidFuzz is available and placeholder is long enough AND user enabled it
        if enable_fuzzy and RAPIDFUZZ_AVAILABLE and len(original) >= 5: # Short vars like [v1] are too risky for fuzzy
            try:
                # Find the best match in the text that looks like a placeholder
                # We search for bracketed patterns in the result to compare against 'original'
                
                # Scan specifically for corrupted looking brackets in the result
                # e.g. [plyer_name], (player_name), [player name]
                candidates = re.findall(r'[\[\{\(].{2,30}[\]\}\)]', result)
                
                if candidates:
                    match, score, _ = process.extractOne(original, candidates, scorer=fuzz.ratio)
                    
                    # High confidence threshold (85%) to avoid false positives
                    if score >= 85:
                        result = result.replace(match, original)
                        continue
                        
            except Exception:
                pass # Fail silently on fuzzy match errors, integrity check will catch it anyway

    return result

def validate_translation_integrity(text: str, placeholders: Dict[str, str]) -> List[str]:
    """
    Çevirinin bütünlüğünü doğrular (tüm orijinal tag'ler yerinde mi?).
    Eksik orijinal tag'lerin listesini döner.
    """
    missing = []
    for key, original in placeholders.items():
        # Check if ORIGINAL content exists in text (restoration success)
        if original not in text:
            # Toleranslı kontrol (boşluksuz)
            clean_original = original.replace(" ", "")
            clean_text = text.replace(" ", "")
            
            if clean_original not in clean_text:
                 missing.append(original)
                
    # Strict bracket check
    stripped = text.strip()
    if stripped.endswith('[') or stripped.endswith('{'):
        missing.append("UNBALANCED_BRACKET_END")
        
    return missing
