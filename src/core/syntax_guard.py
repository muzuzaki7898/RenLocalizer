# -*- coding: utf-8 -*-
# MIT License - RenLocalizer
"""
Syntax Guard Module (v3.1 Hybrid)
=================================
Ren'Py ve Python sözdizimini (değişkenler, tagler, format karakterleri) koruma ve geri yükleme işlemlerini yönetir.
Bu modül, çeviri motorlarının (Google, DeepL) kod yapısını bozmasını engellemek için "Askeri Düzeyde" koruma sağlar.

Architecture & Optimizations (v2.6.4+):
---------------------------------------
1. **Hybrid Protection Strategy:**
   - **Wrapper Tags:** Dış katmandaki tagler ({i}...{/i}) tamamen kesilip alınır (Token tasarrufu + Güvenlik).
   - **Internal Tokens:** İçerideki değişkenler ([var], %s) HTML TOKEN formatlı placeholder'lara dönüştürülür.
   
2. **Regex Pooling:**
   - Tüm regex'ler modül seviyesinde derlenir (Pre-compiled).
   - Python'un `re` motoru için optimize edilmiş "Atomic Group" benzeri yapılar kullanılır.
   
3. **Bracket Healing (Cerrahi Onarım):**
   - Çeviri sonrası oluşan "Google Hallucination" hatalarını (örn: `[ [`) analiz eder ve onarır.
   - Nested (iç içe) değişken yapılarını (`[list [ 1 ]]`) tespit edip düzeltir.

4. **Python Formatting Support:**
   - `%s`, `%d`, `%f`, `%i` ve `%(var)s` gibi standart Python formatlarını otomatik tanır ve korur.
"""

import re
from typing import Dict, Tuple, List

# Ren'Py variable patterns
# Ren'Py variable patterns (Individual)
RENPY_VAR_PATTERN = re.compile(r'\[([^\[\]]+)\]')  # [variable]
RENPY_TAG_PATTERN = re.compile(r'\{([^\{\}]+)\}')  # {tag}

# =============================================================================
# SHARED REGEX PATTERNS (Single Source of Truth)
# =============================================================================
# Base building blocks for protection regexes
_PAT_PCT = r'%%'                             # Literal % (double percent)
# v2.6.6: CRITICAL FIX - Handle escaped brackets properly
# Strategy: Only match COMPLETE escaped pairs [[...]] or {{...}} to protect content atomically
# For incomplete cases like [[Phone], let normal [...]  matching handle the content
# This prevents incomplete [[  from breaking subsequent [variable] patterns
_PAT_ESC_COMPLETE = r'\[\[.*?\]\]|\{\{.*?\}\}'  # Complete pairs only: [[...]] or {{...}}
_PAT_ESC_INCOMPLETE = r'\}\}|\]\]'              # Only closing brackets as fallback (not opening)
_PAT_ESC = f"({_PAT_ESC_COMPLETE}|{_PAT_ESC_INCOMPLETE})"  # Complete pairs first, then singles
_PAT_TAG = r'\{[^\}]+\}'                     # {tag} (greedy match inside braces)
# _PAT_DISAMBIG: Disambiguation tags like {#comment}, {#game} - MUST be preserved exactly
_PAT_DISAMBIG = r'\{#[^}]+\}'
# _PAT_VAR: Matches [variable], [obj.attr], [list[index]], and [var!t] (translatable flag)
# OPTIMIZED v2.6.6: Prevents catastrophic backtracking on deeply nested brackets
# Uses non-backtracking approach: Match content inside [...] but avoid complex alternation
# Old pattern had catastrophic backtracking: r"\[(?:[^\[\]\n'\"]+|'[^']*'|\"[^\"]*\"|\[[^\[\]\n]*\])+\]"
# New: Simpler but safer - matches [...] with anything inside (more lenient, less prone to hang)
_PAT_VAR = r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]"
_PAT_FMT = r'%\([^)]+\)[sdfi]|%[sdfi]'       # Python formatting: %(var)s or %s (Support for s, d, f, i)
_PAT_QMK = r'\?[A-Za-z]\d{3}\?'              # ?A000? style
_PAT_UNI = r'\u27e6[^\u27e7]+\u27e7'         # ⟦...⟧ style

# Combined pattern string (Order matters: most specific/longest first)
# v2.6.6: Complete escaped pairs MUST match before variables to prevent partial breakage
# Example: [[Phone]] matches as atomic esc pair; bare [[Phone] won't match as [[ so [Phone] matches normally
_PROTECT_PATTERN_STR = f"({_PAT_DISAMBIG}|{_PAT_ESC}|{_PAT_TAG}|{_PAT_FMT}|{_PAT_PCT}|{_PAT_QMK}|{_PAT_UNI}|{_PAT_VAR})"

# Pre-compiled Regexes (Module Level Optimization)
PROTECT_RE = re.compile(_PROTECT_PATTERN_STR)

# Specific Regexes for protect_renpy_syntax logic (Tag extraction)
# These capture the wrapper tags to identify them
# Ren'Py 8 tag list: https://www.renpy.org/doc/html/text.html#text-tags
_OPEN_TAG_RE = re.compile(
    r'^(\{(?:'
    # Style tags
    r'i|b|u|s|plain|'
    # Control tags
    r'fast|nw|done|'
    # Timing tags
    r'w(?:=[\d.]+)?|p(?:=[\d.]+)?|cps(?:=\*?[\d.]+)?|'
    # Visual style tags
    r'color(?:=[^}]+)?|size(?:=[^}]+)?|font(?:=[^}]+)?|outlinecolor(?:=[^}]+)?|'
    r'alpha(?:=[^}]+)?|k(?:=[^}]+)?|'
    # Ruby text (furigana) tags
    r'rb|rt|'
    # Spacing tags
    r'space(?:=[^}]+)?|vspace(?:=[^}]+)?|'
    # Image/Link tags
    r'image(?:=[^}]+)?|a(?:=[^}]+)?|'
    # Accessibility tags (Ren'Py 8)
    r'alt(?:=[^}]+)?|noalt|'
    # Shader/Transform tags (Ren'Py 8)
    r'shader(?:=[^}]+)?|transform(?:=[^}]+)?|'
    # Clear tag (Ren'Py 8)
    r'clear'
    r')\})+'
)

_CLOSE_TAG_RE = re.compile(
    r'(\{/(?:i|b|u|s|plain|color|size|font|outlinecolor|alpha|a|rb|rt|alt|shader|transform)\})+$'
)

# Aggressive spaced pattern for restoration (handles AI adding spaces)
# Aggressive spaced pattern for restoration (handles AI adding spaces)
# Pattern: X R P Y X [CORE with spaces] X R P Y X
# OPTIMIZATION: Use \s* between major tokens (for Google's multi-spaces) but \s? inside chars
SPACED_RE_TEMPLATE = r'X\s?R\s?P\s?Y\s?X\s*{core_spaced}\s*X\s?R\s?P\s?Y\s?X'

def _make_spaced_core_pattern(core: str) -> str:
    """Convert 'VAR0' to 'V\\s?A\\s?R\\s?0' for flexible matching."""
    # OPTIMIZATION: Use \s? instead of \s* for performance
    return r'\s?'.join(re.escape(c) for c in core)


# Unicode PUA Markers - These characters are in the Private Use Area
# and will generally be ignored/preserved by translation engines like Google Translate
# DEPRECATED BUT KEPT FOR FALLBACK
PUA_START = '\uE000'  # Marker for start/end of a placeholder (VAR, TAG, etc)
ESC_OPEN  = '\uE001'  # Marker for [[
ESC_CLOSE = '\uE002'  # Marker for ]]

def protect_renpy_syntax(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Ren'Py sözdizimini HTML TOKEN + WRAPPER yöntemiyle korur (v2.6.7+).
    
    STRATEJİ:
    1. WRAPPER TAGLER → Çıkarılır ve pair'ler (açılış, kapalış) atomik olarak saklanır.
    2. TOKENİZASYON → [var], {tag}, [[ vb. yapılar "VAR0", "ESC_OPEN" gibi tokenlara dönüştürülür.
    3. INNER CLOSING TAGS → Wrapper'ın dışında kapalış tag'ler normal token olarak çalışır,
       ama wrapper içi kapalış tag'ler skip edilir (confusion'ı önlemek için).
    
    v2.6.7+ FIX: Wrapper pair tracking - closing tag'ler ayrı token olarak sayılmaz.
    """
    placeholders: Dict[str, str] = {}
    result_text = text
    
    # AŞAMA 1: Wrapper tag pair'lerini tespit et ve çıkar (START AND END ONLY)
    wrapper_pairs = []  # List of (open_tag, close_tag) tuples
    
    # Extract opening wrapper tags from START of string
    opening_tags = []
    opening_match = _OPEN_TAG_RE.match(result_text)
    if opening_match:
        wrapper_opening_str = opening_match.group(0)
        result_text = result_text[len(wrapper_opening_str):]  # Remove opening tags from start
        for tag_match in re.finditer(r'\{[^}]+\}', wrapper_opening_str):
            opening_tags.append(tag_match.group(0))
    
    # Extract closing wrapper tags from END of string
    closing_tags = []
    closing_match = _CLOSE_TAG_RE.search(result_text)
    if closing_match:
        wrapper_closing_str = closing_match.group(0)
        result_text = result_text[:closing_match.start()]  # Remove closing tags from end
        for tag_match in re.finditer(r'\{/[^}]+\}', wrapper_closing_str):
            closing_tags.append(tag_match.group(0))
        closing_tags.reverse()  # Match them in correct order
    
    # FIX v2.6.7+: Create wrapper pairs instead of separate lists
    # This prevents confusion when inner closing tags are in the content
    if opening_tags and closing_tags:
        # Pair each opening tag with its corresponding closing tag
        for i, open_tag in enumerate(opening_tags):
            if i < len(closing_tags):
                close_tag = closing_tags[i]
                wrapper_pairs.append((open_tag, close_tag))
                # Store wrapper pairs as __WRAPPER_PAIR_0__, __WRAPPER_PAIR_1__, etc.
                placeholders[f"__WRAPPER_PAIR_{i}__"] = (open_tag, close_tag)
    
    # Handle whitespace around content
    if opening_tags and result_text and result_text[0].isspace():
        result_text = result_text.lstrip()
        
    if closing_tags and result_text and result_text[-1].isspace():
        result_text = result_text.rstrip()
        
    result_text = result_text.strip()
    
    # AŞAMA 2: Syntax Koruması (TOKEN mode, HTML NOT)
    counter = 0
    out_parts: List[str] = []
    last = 0
    
    # Inner closing tag pattern for skipping (v2.6.7+ fix)
    # These are closing tags that are part of wrapper pairs
    inner_closing_tags = {tag for _, tag in wrapper_pairs}
    
    for m in PROTECT_RE.finditer(result_text):
        start, end = m.start(), m.end()
        out_parts.append(result_text[last:start])
        
        token = m.group(0)
        
        # SKIP inner closing tags from wrapper pairs (v2.6.7+ fix)
        # This prevents them from becoming separate TAG tokens
        if token in inner_closing_tags:
            out_parts.append(token)  # Keep as-is, don't tokenize
            last = end
            continue
        
        # Token Tipi Belirleme ve İsimlendirme
        # v2.6.6: Check for full escaped bracket/brace PAIRS first (now matched atomically)
        if (token.startswith('[[') and token.endswith(']]')) or (token.startswith('{{') and token.endswith('}}')):
            # Full escaped pair like [[Phone]] or {{comment}} (v2.6.6 atomic matching)
            key_content = f"ESC_PAIR{counter}"
            counter += 1
        elif token == '[[':
            # Legacy: Single [[ without closing ]] (shouldn't happen with new pattern)
            key_content = "ESC_OPEN"
        elif token == ']]':
            # Legacy: Single ]] without opening [[ (shouldn't happen with new pattern)
            key_content = "ESC_CLOSE"
        elif token == '%%':
            key_content = f"PCT{counter}"
            counter += 1
        elif token in ('{{', '}}'):
            # Legacy: Individual braces (shouldn't happen with new pattern)
            key_content = f"ESC{counter}"
            counter += 1
        elif token.startswith('{#'):
            key_content = f"DIS{counter}"
            counter += 1
        elif token.startswith('{') and token.endswith('}'):
            key_content = f"TAG{counter}"
            counter += 1
        elif token.startswith('[') and token.endswith(']'):
            key_content = f"VAR{counter}"
            counter += 1
        else:
            key_content = f"VAR{counter}"
            counter += 1
            
        # Placeholders map'e kaydet (Token -> Orijinal)
        placeholders[key_content] = token
        
        # Metne SADECE token'ı ekle (HTML yok)
        out_parts.append(key_content)
            
        last = end
        
    out_parts.append(result_text[last:])
    protected = ''.join(out_parts)
    
    # Fazla boşlukları temizle
    protected = ' '.join(protected.split())
    
    return protected, placeholders


def restore_renpy_syntax(text: str, placeholders: Dict[str, str]) -> str:
    """
    Tokenları (VAR0, TAG1...) ve eski formatları geri yükler.
    
    STRATEJİ:
    1. Tokenları Geri Yükle (VAR0 -> [var])
    2. HTML Span temizliği (Eğer yanlışlıkla HTML gönderildiyse)
    3. Eski sistemler (PUA, XRPYX) için fallback desteği
    4. Wrapper tagleri geri ekle (v2.6.7+ pair-based system)
    """
    if not text or not placeholders:
        return text
    
    # Wrapper tag'leri ve normal placeholder'ları ayır
    # v2.6.7+ FIX: Support both new wrapper pair system and old separate lists
    wrapper_pairs = []
    
    # Try new wrapper pair system first (v2.6.7+)
    for key, value in placeholders.items():
        if key.startswith("__WRAPPER_PAIR_"):
            if isinstance(value, tuple) and len(value) == 2:
                wrapper_pairs.append(value)
    
    # Fallback to old system for backwards compatibility
    if not wrapper_pairs:
        wrapper_open = placeholders.get("__WRAPPER_OPEN__", [])
        wrapper_close = placeholders.get("__WRAPPER_CLOSE__", [])
        if wrapper_open and wrapper_close:
            # Pair them up: first open with first close, etc.
            for i, open_tag in enumerate(wrapper_open):
                if i < len(wrapper_close):
                    wrapper_pairs.append((open_tag, wrapper_close[i]))
    
    # Normal placeholder'ları filtrele
    vars_only = {k: v for k, v in placeholders.items() 
                 if not k.startswith("__WRAPPER_") and not k.startswith("__TAG_")}
    
    # Eski __TAG_ sistemi için destek
    old_tags = {k: v for k, v in placeholders.items() if k.startswith("__TAG_")}
        
    result = text
    
    # AŞAMA 0.5: Spaced Token Cleanup (Google Translate corruption fix)
    # Google Translate sık sık "VAR 0" -> "VAR0" türü space ekliyor
    # Bunu pre-process'te düzeltmeliyiz
    if vars_only:
        # Spaced token pattern: VAR + optional spaces + digits
        spaced_pattern = re.compile(r'(VAR|TAG|ESC_OPEN|ESC_CLOSE|XRPYX[A-Z]*)\s+(\d+|[A-Z_]*)')
        
        def fix_spaced(match):
            prefix = match.group(1)
            suffix = match.group(2)
            original_token = prefix + suffix
            if original_token in vars_only:
                return original_token
            return match.group(0)
        
        result = spaced_pattern.sub(fix_spaced, result)

    # AŞAMA 1: Token Geri Yükleme (VAR0, ESC_OPEN vb.)
    # Performans için: Önce metinde var mı diye hızlıca bak
    # Tüm keyleri tek bir regex ile aramak en hızlısıdır
    if vars_only:
        # Keyleri uzunluklarına göre sırala
        sorted_keys = sorted(vars_only.keys(), key=len, reverse=True)
        
        # Regex: Tokenları ara (word boundaries YOK - ESC_OPEN, ESC_CLOSE underscore içerdiği için)
        # Underscore ve digits word characters olduğu için \b çalışmıyor
        # Örnek: "ESC_OPENtext" yazılı olduğunda \b sınırı H'den önceki sınırı tanıyor
        pattern_str = '(' + '|'.join(re.escape(k) for k in sorted_keys) + ')'
        token_pattern = re.compile(pattern_str)
        
        def token_replacer(match):
            return vars_only.get(match.group(1), match.group(0))
            
        result = token_pattern.sub(token_replacer, result)

    # AŞAMA 2: HTML Span İçindeki Tokenları Geri Yükle (Fallback)
    # Eğer bir şekilde HTML span içinde token geldiyse (<span...>VAR0</span>)
    # Yukarıdaki adım token'ı değiştirmiş olabilir ama span kalmış olabilir.
    # Yani <span...> [player] </span> olmuş olabilir.
    # Cleaner: Remove spanning tags if they wrap restored content?
    # Better: Just clean spans if explicit tokens were wrapped.
    
    # PUA Fallbacks and cleanups...
    if PUA_START in result:
        pua_pattern = re.compile(rf"{PUA_START}\s*(.*?)\s*{PUA_START}")
        result = pua_pattern.sub(lambda m: vars_only.get(m.group(1).strip(), m.group(0)), result)

    if ESC_OPEN in result.replace("[[", ""): # Check if raw ESC_OPEN string remains
        result = result.replace(ESC_OPEN, placeholders.get(ESC_OPEN, '[['))
    if ESC_CLOSE in result.replace("]]", ""):
        result = result.replace(ESC_CLOSE, placeholders.get(ESC_CLOSE, ']]'))
        
    # XRPYX Fallback
    if "XRPYX" in result:
             for k, v in vars_only.items():
                 if "XRPYX" in k and k in result:
                     result = result.replace(k, v)

    # AŞAMA 4: Wrapper tag pair'lerini geri yerleştir (v2.6.7+ fix)
    # Now using atomic wrapper pairs to prevent confusion
    if wrapper_pairs:
        for open_tag, close_tag in reversed(wrapper_pairs):
            result = open_tag + result + close_tag
    
    # Eski __TAG_ sistemi uyumluluğu
    if old_tags:
        sorted_tags = sorted(old_tags.items(), key=lambda x: x[1][1] if isinstance(x[1], tuple) else 0)
        opening_tags = []
        closing_tags = []
        for tag_key, tag_data in sorted_tags:
            tag_value = tag_data[0] if isinstance(tag_data, tuple) else tag_data
            if tag_value.startswith('{/'):
                closing_tags.append(tag_value)
            elif tag_value.startswith('{') and not tag_value.startswith('{{'):
                opening_tags.append(tag_value)
        for tag in reversed(opening_tags):
            result = tag + result
        for tag in closing_tags:
            result = result + tag
    
    # AŞAMA 5: Final Temizlik (Google Hallucinations)
    result = re.sub(r'\[\s*\[', '[[', result)
    result = re.sub(r'\]\s*\]', ']]', result)
    result = re.sub(r'\[\s+([a-zA-Z0-9_]+)\s+\]', r'[\1]', result)
    result = re.sub(r'\[\s*(\d+)\s*\]', r'[\1]', result)
    
    # Tag Nesting Repair
    result = _repair_broken_tag_nesting(result)

    # Decode HTML entities
    result = result.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")

    return result


def _repair_broken_tag_nesting(text: str) -> str:
    """
    Ren'Py taglerinin ({i}, {b}, {color}...) iç içe geçme sırasını onarır.
    v2.6.6 OPTIMIZATION: Added safety checks to prevent hangs on pathological input.
    """
    try:
        if not text or '{' not in text:
            return text
        if '/' not in text: 
            return text
        
        # Safety: Skip if text is too long (prevent pathological cases)
        # Most realistic game text is < 1000 chars; if longer, skip repair
        if len(text) > 5000:
            return text

        # Regex: Matches {{...}} OR {...} using character classes to avoid JSON escape issues
        tag_re = re.compile(r'([{][{].*?[}][}]|[{][^{}]+[}])')
        
        tokens = tag_re.split(text)
        
        # Safety: If too many tokens, skip (might be pathological)
        if len(tokens) > 200:
            return text
        
        stack = []
        broken_indices = set()
        
        nesting_tags = {'b', 'i', 'u', 's', 'plain', 'font', 'color', 'size', 'alpha', 'k', 'rt', 'rb', 'a', 'cps', 'shader', 'transform'}
        
        for i, token in enumerate(tokens):
            # Skip empty tokens or non-tags
            if not token or not token.startswith('{'):
                continue
                
            if token.startswith('{{'):
                continue
                
            try:
                # Remove { and } and strip whitespaces
                content = token[1:-1].strip()
                if not content: continue
                
                is_closing = content.startswith('/')
                
                if is_closing:
                    # Remove / and get tag name
                    tag_name_part = content[1:].strip()
                    tag_name = tag_name_part.split()[0] if tag_name_part else ""
                else:
                     # Get tag name before = or space
                    tag_name = content.split('=')[0].split()[0]
                
                tag_name = tag_name.lower().strip()
                
                if tag_name not in nesting_tags:
                    continue
                    
                if not is_closing:
                    stack.append((i, tag_name))
                else:
                    if not stack:
                        # ORPHAN CLOSING TAG -> DELETE IT
                        broken_indices.add(i)
                    else:
                        last_idx, last_name = stack[-1]
                        if last_name == tag_name:
                            stack.pop()
                        else:
                            # MISMATCHED NESTING -> DELETE CLOSING
                            broken_indices.add(i)
            except Exception:
                continue
                
        if not broken_indices:
            return text
            
        new_tokens = []
        for i, token in enumerate(tokens):
            if i not in broken_indices:
                new_tokens.append(token)
            
        return "".join(new_tokens)
        
    except Exception:
        # Failsafe: Return original text if anything goes wrong
        return text



def validate_translation_integrity(text: str, placeholders: Dict[str, str]) -> List[str]:
    """
    Çevirinin bütünlüğünü doğrular (tüm orijinal tag'ler yerinde mi?).
    Eksik orijinal tag'lerin listesini döner.
    
    NOT: Bu fonksiyon artık sadece UYARI amaçlıdır, çeviriyi reddetmez.
    Boş liste dönerse tüm placeholder'lar başarıyla geri yüklenmiş demektir.
    
    Optimizasyon: clean_text sadece gerektiğinde hesaplanır (lazy evaluation).
    
    Args:
        text (str): Kontrol edilecek çevrilmiş metin
        placeholders (Dict[str, str]): placeholder -> orijinal değer sözlüğü
        
    Returns:
        List[str]: Eksik orijinal değerlerin listesi (boşsa başarılı)
    """
    if not placeholders:
        return []
        
    missing = []
    clean_text = None  # Lazy: sadece gerekirse hesapla
    
    for key, original in placeholders.items():
        # Wrapper ve eski tag sistemlerini atla
        if key.startswith("__WRAPPER_") or key.startswith("__TAG_"):
            continue
            
        # Liste ise (wrapper tag listesi), atla
        if isinstance(original, list):
            continue
            
        # Tuple ise (eski tag pozisyon bilgisi), atla
        if isinstance(original, tuple):
            continue
            
        # Hızlı yol: direkt kontrol
        if original in text:
            continue
            
        # Yavaş yol: toleranslı kontrol (boşluksuz ve case-insensitive)
        if clean_text is None:
            clean_text = text.replace(" ", "").lower()
            
        clean_original = original.replace(" ", "").lower()
        if clean_original not in clean_text:
            missing.append(original)
                  
    # Strict bracket check (unbalanced brackets at end)
    stripped = text.strip()
    if stripped.endswith('[') or stripped.endswith('{'):
        missing.append("UNBALANCED_BRACKET_END")
        
    # Tag Nesting Check (Post-repair validation)
    # Eğer repair fonksiyonu çalışmasına rağmen hala sorun varsa
    if clean_text: # Lazy computed check re-use
        pass # Şimdilik sadece structural check yeterli, derin nesting analizi pahalı olabilir.

    return missing


# =============================================================================
# HTML WRAP PROTECTION (Zenpy-style)
# =============================================================================
# Google Translate <span class="notranslate"> içindeki metni çevirmiyor.
# Bu yöntem placeholder değiştirmeden çok daha güvenilir.

# HTML koruma için regex (protect_renpy_syntax ile aynı pattern'leri kullanır)
# HTML koruma için regex (protect_renpy_syntax ile aynı pattern'leri kullanır - Shared Source)
HTML_PROTECT_RE = re.compile(_PROTECT_PATTERN_STR)


def protect_renpy_syntax_html(text: str) -> str:
    """
    Ren'Py sözdizimini HTML notranslate tag'leri ile korur.
    
    Google Translate <span class="notranslate">...</span> içindeki metni
    çevirmiyor. Bu yöntem placeholder değiştirmeden çok daha güvenilir.
    
    Args:
        text (str): Korunacak orijinal metin
        
    Returns:
        str: HTML tag'leri eklenmiş metin (Google'a gönderilecek)
    """
    if not text:
        return text
    
    def wrap_match(match: re.Match) -> str:
        """Her eşleşmeyi notranslate span'ı ile sar (Google resmi standartı)."""
        # translate="no" attribute - Google'ın resmi HTML5 standardı
        # class="notranslate" - eski yöntem, yedek olarak
        return f'<span translate="no" class="notranslate">{match.group(0)}</span>'
    
    return HTML_PROTECT_RE.sub(wrap_match, text)


def restore_renpy_syntax_html(text: str) -> str:
    """
    HTML notranslate tag'lerini temizler.
    
    Google'dan dönen metindeki <span class="notranslate">...</span>
    tag'lerini kaldırır ve içeriği korur.
    
    Args:
        text (str): Google'dan dönen HTML içerikli metin
        
    Returns:
        str: Temizlenmiş metin (orijinal tag'ler korunmuş)
    """
    if not text:
        return text
    
    # Pattern: <span class="notranslate">...</span>
    # Ayrıca Google'ın ekleyebileceği varyasyonları da yakala:
    # - <span class="notranslate">
    # - <span class='notranslate'>
    # - <SPAN class="notranslate">
    # - Boşluklu versiyonlar
    # Her iki formatı da destekle:
    # 1. <span translate="no" class="notranslate">...</span>
    # 2. <span class="notranslate">...</span>
    # 3. <span translate="no">...</span>
    pattern = re.compile(
        r'<span(?:\s+translate=["\']no["\'])?(?:\s+class=["\']notranslate["\'])?(?:\s+translate=["\']no["\'])?\s*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL
    )
    
    result = pattern.sub(r'\1', text)
    
    # Google bazen sadece açılış tag'ini bırakabilir (hatalı durum)
    # Kalan orphan span tag'lerini de temizle
    result = re.sub(r'<span[^>]*translate=["\']no["\'][^>]*>', '', result, flags=re.IGNORECASE)
    result = re.sub(r'<span[^>]*class=["\']notranslate["\'][^>]*>', '', result, flags=re.IGNORECASE)
    result = re.sub(r'</span>', '', result, flags=re.IGNORECASE)
    
    # Google bazen fazladan HTML entity ekleyebilir, bunları da temizle
    result = result.replace('&lt;', '<').replace('&gt;', '>')
    result = result.replace('&amp;', '&').replace('&quot;', '"')
    
    return result


# =============================================================================
# XML PLACEHOLDER SYSTEM (LLM Optimized)
# =============================================================================
# LLM'ler (OpenAI, Gemini, vb.) en iyi XML benzeri yapıları korur.
# Bu nedenle XRPYX yerine <ph id="N">...</ph> formatı kullanıyoruz.


def protect_renpy_syntax_xml(text: str) -> Tuple[str, Dict[str, str]]:
    """
    LLM'ler için XML tabanlı koruma (XRPYX yerine).
    
    Format: <ph id="0">[variable]</ph>
    
    Bu format LLM'lerin "code-switching" yapmasını engeller ve
    taglerin içeriğini çevirmeden korumalarını sağlar.
    
    Args:
        text (str): Korunacak metin
        
    Returns:
        Tuple[str, Dict[str, str]]: (XML'li metin, placeholder map)
    """
    placeholders: Dict[str, str] = {}
    result_text = text
    
    counter = 0
    out_parts: List[str] = []
    last = 0
    
    for m in PROTECT_RE.finditer(result_text):
        start, end = m.start(), m.end()
        out_parts.append(result_text[last:start])
        
        token = m.group(0)
        
        # XML ID oluştur
        ph_id = str(counter)
        
        # <ph> tag'i oluştur
        # İçeriği de içinde tutuyoruz ki LLM bağlamı görsün ama dokunmasın
        xml_tag = f'<ph id="{ph_id}">{token}</ph>'
        
        # Map'e kaydet (id -> orijinal)
        placeholders[ph_id] = token
        
        out_parts.append(xml_tag)
        counter += 1
        last = end
        
    out_parts.append(result_text[last:])
    return ''.join(out_parts), placeholders


def restore_renpy_syntax_xml(text: str, placeholders: Dict[str, str]) -> str:
    """
    XML taglerini temizler ve orijinalleri geri yükler.
    
    Regex ile <ph id="N">...</ph> yapılarını bulur ve map'teki
    orijinal değerle (id'ye göre) değiştirir.
    
    Args:
        text (str): XML içeren çevrilmiş metin
        placeholders (Dict[str, str]): id -> orijinal değer
        
    Returns:
        str: Temizlenmiş metin
    """
    if not text or not placeholders:
        return text
    
    # Regex: <ph id="N">...</ph> or <ph id = 'N'>...</ ph>
    # Case insensitive, whitespace tolerant for attributes and closing tag
    ph_pattern = re.compile(
        r'<ph\b[^>]*\bid\s*=\s*["\']?(\d+)["\']?[^>]*>.*?</\s*ph\s*>',
        re.IGNORECASE | re.DOTALL
    )
    
    def replacer(match):
        ph_id = match.group(1)
        # ID map'te varsa orijinali dön, yoksa match'i (veya boşu) dön
        if ph_id in placeholders:
            return placeholders[ph_id]
        return match.group(0) # Bulunamazsa dokunma (integrity check yakalar)
        
    result = ph_pattern.sub(replacer, text)
    
    return result
