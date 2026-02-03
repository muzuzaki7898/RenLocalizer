# -*- coding: utf-8 -*-
# MIT License - RenLocalizer
"""
Syntax Guard Module
===================
Ren'Py sözdizimini (değişkenler, tagler, özellikli karakterler) koruma ve geri yükleme işlemlerini yönetir.

v2.5.1 uyumlu stabilize edilmiş sürüm:
- Placeholder formatı: XRPYXVAR0XRPYX (tek kelime prensibi, AI tarafından bozulması zor)
- Fuzzy matching kaldırıldı (false positive riski nedeniyle)
- Validation toleranslı hale getirildi
"""

import re
from typing import Dict, Tuple, List

# Ren'Py variable patterns
RENPY_VAR_PATTERN = re.compile(r'\[([^\[\]]+)\]')  # [variable]
RENPY_TAG_PATTERN = re.compile(r'\{([^\{\}]+)\}')  # {tag}
RENPY_ESCAPED_PATTERN = re.compile(r'\{\{|\}\}')   # {{ }}
RENPY_QMARK_PLACEHOLDER_RE = re.compile(r'\?[A-Za-z]\d{3}\?')
RENPY_ANGLE_PLACEHOLDER_RE = re.compile(r'\u27e6[^\u27e7]+\u27e7')

# Combined protection regex
# Includes: {{, }}, {tag}, [var], ?A000?, ⟦...⟧, %% (double percent = literal %)
PROTECT_RE = re.compile(
    r'(%%|'  # Double percent (literal % in Ren'Py/Python)
    r'\{\{|\}\}|\{[^\}]+\}|\[[^\[\]]+\]|'
    r'\?[A-Za-z]\d{3}\?|'
    r'\u27e6[^\u27e7]+\u27e7)'
)

# Aggressive spaced pattern for restoration (handles AI adding spaces)
# Pattern: X R P Y X [CORE with spaces] X R P Y X
SPACED_RE_TEMPLATE = r'X\s*R\s*P\s*Y\s*X\s*{core_spaced}\s*X\s*R\s*P\s*Y\s*X'

def _make_spaced_core_pattern(core: str) -> str:
    """Convert 'VAR0' to 'V\\s*A\\s*R\\s*0' for flexible matching."""
    return r'\s*'.join(re.escape(c) for c in core)


def protect_renpy_syntax(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Ren'Py sözdizimini AKILLI HİBRİT yöntemle korur.
    
    AKILLI HİBRİT STRATEJİ (v2.6.3+):
    1. WRAPPER TAGLER (tüm cümleyi kaplayan) → Çıkarılır, hafızada tutulur
       - Örnek: "{i}Hello world{/i}" → {i} ve {/i} çıkarılır
       - Koşul: Açılış başta, kapanış sonda olmalı
       - Bu tagler güvenle çıkarılabilir çünkü tüm cümleyi kapsıyorlar
       
    2. PARTIAL TAGLER (cümle içinde) → Placeholder olarak korunur
       - Örnek: "Hello {i}beautiful{/i} world" → {i} ve {/i} placeholder olur
       - Bu tagler konumları önemli olduğu için metinde kalmalı
       
    3. DEĞİŞKENLER ([var]) → Placeholder ile korunur (XRPYXVAR0XRPYX)
    
    Bu yaklaşım:
    - Çeviri kalitesini korur (partial tagler yerinde)
    - Wrapper tag bozulma riskini %0'a indirir
    - Token tasarrufu sağlar
    
    Args:
        text (str): Korunacak metin
        
    Returns:
        Tuple[str, Dict[str, str]]: (Korunan metin, placeholder/tag -> orijinal değer sözlüğü)
    """
    placeholders: Dict[str, str] = {}
    result_text = text
    
    # AŞAMA 1: Wrapper tag'leri tespit et ve çıkar
    # Wrapper = Açılış tag başta + Kapanış tag sonda (tüm cümleyi kaplıyor)
    wrapper_opening = []  # Başta bulunan açılış tagleri
    wrapper_closing = []  # Sonda bulunan kapanış tagleri
    
    # Açılış tag pattern: {i}, {b}, {color=...}, etc. (tüm Ren'Py text tags)
    opening_tag_pattern = re.compile(
        r'^(\{(?:i|b|u|s|plain|fast|nw|w(?:=[\d.]+)?|p(?:=[\d.]+)?|cps(?:=\*?[\d.]+)?|'
        r'color(?:=[^}]+)?|size(?:=[^}]+)?|font(?:=[^}]+)?|outlinecolor(?:=[^}]+)?|'
        r'alpha(?:=[^}]+)?|k(?:=[^}]+)?|rb|rt|space(?:=[^}]+)?|vspace(?:=[^}]+)?|'
        r'image(?:=[^}]+)?|a(?:=[^}]+)?)\})+'
    )
    
    # Kapanış tag pattern: {/i}, {/b}, {/color}, etc.
    closing_tag_pattern = re.compile(
        r'(\{/(?:i|b|u|s|plain|color|size|font|outlinecolor|alpha|a)\})+$'
    )
    
    # Başta açılış tag'leri var mı?
    opening_match = opening_tag_pattern.match(result_text)
    if opening_match:
        wrapper_opening_str = opening_match.group(0)
        result_text = result_text[len(wrapper_opening_str):]
        # Tek tek tag'lere ayır
        for tag_match in re.finditer(r'\{[^}]+\}', wrapper_opening_str):
            wrapper_opening.append(tag_match.group(0))
    
    # Sonda kapanış tag'leri var mı?
    closing_match = closing_tag_pattern.search(result_text)
    if closing_match:
        wrapper_closing_str = closing_match.group(0)
        result_text = result_text[:closing_match.start()]
        # Tek tek tag'lere ayır
        for tag_match in re.finditer(r'\{/[^}]+\}', wrapper_closing_str):
            wrapper_closing.append(tag_match.group(0))
    
    # Wrapper tag'leri hafızaya kaydet
    if wrapper_opening:
        placeholders["__WRAPPER_OPEN__"] = wrapper_opening  # Liste olarak
    if wrapper_closing:
        placeholders["__WRAPPER_CLOSE__"] = wrapper_closing  # Liste olarak
    
    # Wrapper çıkarıldıktan sonra baştaki/sondaki boşlukları temizle
    result_text = result_text.strip()
    
    # AŞAMA 2: Kalan tüm syntax'ı placeholder'a çevir
    # Bu aşamada: partial tagler, değişkenler, escaped karakterler
    protect_pattern = re.compile(
        r'(%%|'  # Double percent
        r'\{\{|\}\}|'  # Escaped braces
        r'\{/?[^}]+\}|'  # Remaining text tags (partial)
        r'%\([^)]+\)[sd]|'  # %(var)s format
        r'\[[^\[\]]+\]|'  # Variables [name]
        r'\?[A-Za-z]\d{3}\?|'  # ?A000? style
        r'\u27e6[^\u27e7]+\u27e7)'  # ⟦...⟧ style
    )
    
    counter = 0
    out_parts: List[str] = []
    last = 0
    
    for m in protect_pattern.finditer(result_text):
        start, end = m.start(), m.end()
        out_parts.append(result_text[last:start])
        
        token = m.group(0)
        if token == '%%':
            prefix = 'PCT'
        elif token in ('{{', '}}'):
            prefix = 'ESC'
        elif token.startswith('{') and token.endswith('}'):
            prefix = 'TAG'
        else:
            prefix = 'VAR'
            
        key = f"XRPYX{prefix}{counter}XRPYX"
        placeholders[key] = token
        # Placeholder etrafına boşluk ekle (Google'ın ayrı kelime algılaması için)
        out_parts.append(f" {key} ")
        counter += 1
        last = end
        
    out_parts.append(result_text[last:])
    protected = ''.join(out_parts)
    
    # Fazla boşlukları temizle
    protected = ' '.join(protected.split())
    
    return protected, placeholders


def restore_renpy_syntax(text: str, placeholders: Dict[str, str]) -> str:
    """
    Placeholder'ları ve wrapper tag'leri orijinal değerleriyle değiştirir.
    
    AKILLI HİBRİT RESTORE STRATEJİSİ (v2.6.3+):
    1. Placeholder'ları geri yükle (XRPYXVAR0XRPYX → [variable])
    2. Wrapper tag'leri başa/sona ekle (__WRAPPER_OPEN/CLOSE__)
    
    Geri Yükleme Aşamaları:
    1. Tam eşleşme (hızlı) - Çoğu durumda bu yeterli
    2. Case-insensitive eşleşme (AI büyük/küçük harf değiştirmiş olabilir)
    3. Boşluklu eşleşme (AI boşluk eklemiş olabilir)
    4. Wrapper tag'leri geri yerleştir (başa açılış, sona kapanış)
    
    Args:
        text (str): Geri yüklenecek metin
        placeholders (Dict[str, str]): placeholder/tag -> orijinal değer sözlüğü
        
    Returns:
        str: Orijinal değerleri geri yüklenmiş metin
    """
    if not text or not placeholders:
        return text
    
    # Wrapper tag'leri ve normal placeholder'ları ayır
    wrapper_open = placeholders.get("__WRAPPER_OPEN__", [])
    wrapper_close = placeholders.get("__WRAPPER_CLOSE__", [])
    
    # Normal placeholder'ları filtrele (wrapper hariç)
    vars_only = {k: v for k, v in placeholders.items() 
                 if not k.startswith("__WRAPPER_") and not k.startswith("__TAG_")}
    
    # Eski __TAG_ sistemi için de destek (geriye uyumluluk)
    old_tags = {k: v for k, v in placeholders.items() if k.startswith("__TAG_")}
        
    result = text
    remaining_placeholders = []
    
    # AŞAMA 1: Hızlı tam eşleşme (regex ile boşluk temizleme)
    # Placeholder etrafındaki fazla boşlukları da temizle
    for placeholder, original in vars_only.items():
        # Tuple değerleri atla (eski tag sistemi kalıntısı)
        if isinstance(original, tuple):
            continue
            
        if placeholder in result:
            # Placeholder + etrafındaki opsiyonel boşlukları bul ve orijinalle değiştir
            # Bu, protect aşamasında eklenen boşlukları düzgün temizler
            spaced_pattern = re.compile(r'\s*' + re.escape(placeholder) + r'\s*')
            result = spaced_pattern.sub(original, result)
        else:
            remaining_placeholders.append((placeholder, original))
    
    # Eğer tüm placeholder'lar bulunduysa ve wrapper yoksa, doğrudan dön
    if not remaining_placeholders and not wrapper_open and not wrapper_close and not old_tags:
        return result
    
    # AŞAMA 2: Kalan placeholder'lar için regex tabanlı arama
    # (Sadece bozulmuş placeholder'lar için)
    still_remaining = []
    for placeholder, original in remaining_placeholders:
        if placeholder.startswith("XRPYX") and placeholder.endswith("XRPYX"):
            core = placeholder[5:-5]  # VAR0, TAG1, ESC2, etc.
            
            # Case-insensitive basit regex
            pattern = re.compile(re.escape(placeholder), re.IGNORECASE)
            result = pattern.sub(original, result)
            
            # Eğer hala bulamadıysa boşluklu halini dene
            if original not in result:
                core_spaced = _make_spaced_core_pattern(core)
                spaced_pattern = re.compile(
                    SPACED_RE_TEMPLATE.format(core_spaced=core_spaced), 
                    re.IGNORECASE
                )
                result = spaced_pattern.sub(original, result)
                
            # Hala bulamadıysak kalan listeye ekle
            if original not in result:
                still_remaining.append((placeholder, original, core))
        else:
            # Fallback: basit case-insensitive
            pattern = re.compile(re.escape(placeholder), re.IGNORECASE)
            result = pattern.sub(original, result)
    
    # AŞAMA 3: Fuzzy Recovery - Yaygın bozulma kalıpları
    # Google Translate bazen placeholder'ları bozuyor:
    # - XRPYCTAG0 (X→C), XRPYXTAG3XRPY (sonunda X eksik), XRPYXXTAG0 (çift X)
    # - {i}XRPYXTAG1XRPy (orijinal tag kalmış + küçük harf)
    for placeholder, original, core in still_remaining:
        # Core örneği: TAG0, VAR1, ESC2
        core_type = ''.join(c for c in core if c.isalpha())  # TAG, VAR, ESC
        core_num = ''.join(c for c in core if c.isdigit())   # 0, 1, 2
        
        # Boşluklu core pattern (T A G 0 gibi)
        spaced_type = r'\s*'.join(core_type)
        spaced_num = r'\s*'.join(core_num) if core_num else ''
        spaced_core = spaced_type + r'\s*' + spaced_num if core_num else spaced_type
        
        # Bozuk kalıpları yakala (en spesifikten en genele)
        fuzzy_patterns = [
            # XRPYXX (çift X) + herhangi sonlandırma
            rf'XRPYXX\s*{spaced_core}(?:\s*XRPY[A-Z]?)?',
            # XRPYX...XRPy (küçük y ile biten)
            rf'XRPYX\s*{spaced_core}\s*XRPY',
            # Sadece başlangıç XRPY ve core (sonlandırma eksik)
            rf'XRPY[A-Z]?\s*{spaced_core}(?:\s*XRPY)?(?![A-Z])',
            # Son harfi yanlış olanlar (XRPYC, XRPYY vs)
            rf'XRPY[A-Z]\s*{spaced_core}\s*XRPY[A-Z]?',
            # Boşluklu tam pattern
            rf'X\s*R\s*P\s*Y\s*X?\s*{spaced_core}\s*(?:X\s*R\s*P\s*Y\s*X?)?',
        ]
        
        for fp in fuzzy_patterns:
            try:
                fuzzy_re = re.compile(fp, re.IGNORECASE)
                new_result = fuzzy_re.sub(original, result)
                if new_result != result:  # Değişiklik olduysa
                    result = new_result
                    if original in result:
                        break  # Bulunduysa diğer pattern'leri deneme
            except re.error:
                continue
    
    # AŞAMA 4: Wrapper tag'leri geri yerleştir
    # Wrapper açılış tagleri başa, kapanış tagleri sona eklenir
    if wrapper_open:
        # Açılış taglerini TERS sırayla başa ekle ki orijinal sıra korunsun
        # Örn: ["{i}", "{color}"] -> Önce {color} eklenir, sonra {i} -> Sonuç: "{i}{color}..."
        for tag in reversed(wrapper_open):
            result = tag + result
    
    if wrapper_close:
        # Kapanış taglerini sırayla sona ekle
        for tag in wrapper_close:
            result = result + tag
    
    # Eski __TAG_ sistemi için geriye uyumluluk
    if old_tags:
        # Eski tag'leri pozisyonlarına göre sırala
        sorted_tags = sorted(old_tags.items(), key=lambda x: x[1][1] if isinstance(x[1], tuple) else 0)
        
        opening_tags = []
        closing_tags = []
        
        for tag_key, tag_data in sorted_tags:
            if isinstance(tag_data, tuple):
                tag_value, _ = tag_data
            else:
                tag_value = tag_data
            
            if tag_value.startswith('{/'):
                closing_tags.append(tag_value)
            elif tag_value.startswith('{') and not tag_value.startswith('{{'):
                opening_tags.append(tag_value)
        
        for tag in reversed(opening_tags):
            result = tag + result
        
        for tag in closing_tags:
            result = result + tag
                
    return result



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
        
    return missing


# =============================================================================
# HTML WRAP PROTECTION (Zenpy-style)
# =============================================================================
# Google Translate <span class="notranslate"> içindeki metni çevirmiyor.
# Bu yöntem placeholder değiştirmeden çok daha güvenilir.

# HTML koruma için regex (protect_renpy_syntax ile aynı pattern'leri kullanır)
HTML_PROTECT_RE = re.compile(
    r'(%%|'  # Double percent
    r'\{\{|\}\}|'  # Escaped braces
    r'\{[^\}]+\}|'  # Text tags {i}, {color=#xxx}, etc.
    r'\[[^\[\]]+\]|'  # Variables [name], [player.name], etc.
    r'\?[A-Za-z]\d{3}\?|'  # ?A000? style
    r'\u27e6[^\u27e7]+\u27e7|'  # ⟦...⟧ style
    r'%\([^)]+\)[sd])'  # %(var)s or %(var)d format
)


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
