"""Temiz ve stabilize çeviri altyapısı (Google + stub motorlar + cache + adaptif concurrency)."""

from __future__ import annotations

import asyncio
import aiohttp
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from collections import OrderedDict, deque, Counter
import random


# Ren'Py değişken ve tag koruma regex'leri
# [variable], [player], [lang_lady] gibi interpolation değişkenleri
RENPY_VAR_PATTERN = re.compile(r'\[([^\[\]]+)\]')
# {tag}, {i}, {b}, {color=#fff} gibi text tag'leri
RENPY_TAG_PATTERN = re.compile(r'\{([^\{\}]+)\}')
# {{escaped}} çift parantez
RENPY_ESCAPED_PATTERN = re.compile(r'\{\{|\}\}')
# ?V000? / ?T000? / ?F000? gibi runtime placeholder'lar
RENPY_QMARK_PLACEHOLDER_RE = re.compile(r'\?[A-Za-z]\d{3}\?')
# ⟦V000⟧ gibi açılı parantez placeholder'lar
RENPY_ANGLE_PLACEHOLDER_RE = re.compile(r'\u27e6[^\u27e7]+\u27e7')

# Ren'Py syntax protection regexes
PROTECT_RE = re.compile(
    r'(\{\{|\}\}|\{[^\}]+\}|\[[^\[\]]+\]|'
    r'\?[A-Za-z]\d{3}\?|'
    r'\u27e6[^\u27e7]+\u27e7)'
)

# Agresif bozulma temizliği için şablon
# [ [ v 0 ] ], [[V 0]], [[ v0]] gibi durumları yakalamak için
CLEANUP_RE = re.compile(r'\[\s*\[\s*([vteg])\s*(\d+)\s*\]\s*\]', re.IGNORECASE)


def protect_renpy_syntax(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Ren'Py değişkenlerini ve tag'lerini çeviriden korur.
    Placeholder'larla değiştirir ve geri dönüşüm sözlüğü döner.
    """
    # Single-pass scanning to avoid nested replacement collisions.
    placeholders: Dict[str, str] = {}
    counter = 0

    out_parts: List[str] = []
    last = 0
    for m in PROTECT_RE.finditer(text):
        start, end = m.start(), m.end()
        # Append text between matches
        out_parts.append(text[last:start])
        token = m.group(0)
        if token in ('{{', '}}'):
            prefix = 'e'  # escaped
        elif token.startswith('{') and token.endswith('}'):
            prefix = 't'  # tag
        else:
            prefix = 'v'  # variable
        key = f" [[{prefix}{counter}]] "  # Etrafına boşluk ekle (Tampon)
        placeholders[key.strip()] = token
        out_parts.append(key)
        counter += 1
        last = end
    out_parts.append(text[last:])
    protected = ''.join(out_parts)
    
    # Fazla boşlukları temizle (isteğe bağlı ama temizlik iyidir)
    # protected = re.sub(r'\s{2,}', ' ', protected)

    return protected, placeholders


def restore_renpy_syntax(text: str, placeholders: Dict[str, str]) -> str:
    """Placeholder'ları orijinal değerleriyle değiştirir. Case-insensitive support for AI stability."""
    if not text or not placeholders:
        return text
    result = text
    # Sort placeholders by length descending to avoid partial replacement of similar keys
    sorted_placeholders = sorted(placeholders.items(), key=lambda x: len(x[0]), reverse=True)
    
    for placeholder, original in sorted_placeholders:
        # 1. Tam eşleşme (Hızlı)
        if placeholder in result:
            result = result.replace(placeholder, original)
            continue

        # 2. Case-insensitive ve boşluk temizliği (Daha yavaş ama güvenli)
        # Motorlar bazen "[[ v0 ]]" veya "[[V0]]" döndürebiliyor.
        # CLEANUP_RE zaten tüm varyasyonları standart [[v0]] haline getirmeye odaklı.
        core_match = re.search(r'\[\[([vteg]\d+)\]\]', placeholder)
        if core_match:
            core = core_match.group(1) # v0, t1 vb.
            # Boşlukları ve büyük/küçük harf farklarını temizleyen regex
            # [[ v 0 ]], [ [v0] ], [[V0]] vb. her şeyi yakalar
            pattern = re.compile(
                r'\[\s*\[\s*' + re.escape(core[0]) + r'\s*' + re.escape(core[1:]) + r'\s*\]\s*\]',
                re.IGNORECASE
            )
            result = pattern.sub(original, result)
            
    # Eğer hala temizlenmemiş "[[...]]" kalıntıları varsa (farklı bir ID kalmışsa vb.)
    # onları da en son bir kez daha temizlemeyi deneyebiliriz ama placeholders içindekiler öncelikli.
                
    return result


class TranslationEngine(Enum):
    GOOGLE = "google"
    DEEPL = "deepl"
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL_LLM = "local_llm"
    PSEUDO = "pseudo"  # Pseudo-localization for UI testing


@dataclass
class TranslationRequest:
    text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    metadata: Dict = field(default_factory=dict)


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    success: bool
    error: Optional[str] = None
    confidence: float = 0.0
    quota_exceeded: bool = False  # Flag for API quota exhaustion
    metadata: Dict = field(default_factory=dict)
    text_type: Optional[str] = None  # Type of text: 'paragraph', 'dialogue', etc.


class BaseTranslator(ABC):
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None, config_manager=None):
        self.api_key = api_key
        self.proxy_manager = proxy_manager
        self.config_manager = config_manager
        self.use_proxy = True
        self.logger = logging.getLogger(self.__class__.__name__)
        self.status_callback: Optional[Callable[[str, str], None]] = None  # (level, message)
        self.should_stop_callback: Optional[Callable[[], bool]] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    def emit_log(self, level: str, message: str):
        """Emits log to both standard logger and UI status callback."""
        if level.lower() == 'error':
            self.logger.error(message)
        elif level.lower() == 'warning':
            self.logger.warning(message)
        else:
            self.logger.info(message)
            
        if self.status_callback:
            self.status_callback(level, message)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(limit=256, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(connector=self._connector, timeout=timeout)
        return self._session

    def _get_text(self, key: str, default: str, **kwargs) -> str:
        """Helper to get localized text from config_manager."""
        if self.config_manager:
            return self.config_manager.get_ui_text(key, default).format(**kwargs)
        return default.format(**kwargs)

    async def close(self):
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
            self._connector = None

    async def close_session(self):
        """Alias for close() to match naming convention used in detection logic."""
        await self.close()

    def set_proxy_enabled(self, enabled: bool):
        self.use_proxy = enabled

    async def _make_request(self, url: str, method: str = "GET", **kwargs):
        session = await self._get_session()
        proxy = None
        if self.use_proxy and self.proxy_manager:
            p = self.proxy_manager.get_next_proxy()
            if p:
                proxy = p.url
        if method.upper() == "GET":
            async with session.get(url, proxy=proxy, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                raise RuntimeError(self._get_text('error_http', f"HTTP {resp.status}", status=resp.status))
        elif method.upper() == "POST":
            async with session.post(url, proxy=proxy, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                raise RuntimeError(self._get_text('error_http', f"HTTP {resp.status}", status=resp.status))
        else:
            raise ValueError(self._get_text('error_unsupported_method', "Unsupported method"))

    @abstractmethod
    async def translate_single(self, request: TranslationRequest) -> TranslationResult: ...

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        return [await self.translate_single(r) for r in requests]

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]: ...

    def _check_integrity(self, text: str, placeholders: Dict[str, str]) -> bool:
        """
        Check if all original placeholder values (e.g., [name], {{tag}}) are present in the text.
        Returns False if any placeholder value is missing.
        """
        if not placeholders:
            return True
        
        # Orijinal tokenlerin (örn: [name]) çevrilmiş metinde geçip geçmediğine bak
        # Case-insensitive arama yapalım çünkü AI bazen büyük/küçük harf değiştirebilir
        text_lower = text.lower()
        for orig_val in placeholders.values():
            if orig_val.lower().strip() not in text_lower:
                return False
        return True

class GoogleTranslator(BaseTranslator):
    """Multi-endpoint Google Translator with Lingva fallback.
    
    Uses multiple Google mirrors in parallel for faster translation,
    with Lingva Translate as a free fallback when Google fails.
    """
    
    # Multiple Google endpoints for parallel requests
    google_endpoints = [
        "https://translate.googleapis.com/translate_a/single",
        "https://translate.google.com/translate_a/single",
        "https://translate.google.com.tr/translate_a/single",
        "https://translate.google.co.uk/translate_a/single",
        "https://translate.google.de/translate_a/single",
        "https://translate.google.fr/translate_a/single",
        "https://translate.google.ru/translate_a/single",
        "https://translate.google.jp/translate_a/single",
        "https://translate.google.ca/translate_a/single",
        "https://translate.google.com.au/translate_a/single",
        "https://translate.google.pl/translate_a/single",
        "https://translate.google.es/translate_a/single",
        "https://translate.google.it/translate_a/single",
        # Gerekirse aşağıdaki satırları silebilirsiniz
    ]
    
    # Lingva instances (free, no API key needed)
    lingva_instances = [
        "https://lingva.ml",
        "https://lingva.lunar.icu",
        "https://lingva.garudalinux.org",  # Extra fallback; avoids AV warnings seen with plausibility.cloud
    ]
    
    # Default values (can be overridden from config)
    multi_q_concurrency = 16  # Paralel endpoint istekleri
    max_slice_chars = 3000   # Bir istekteki maksimum karakter
    max_texts_per_slice = 25  # Maximum texts per slice
    use_multi_endpoint = True  # Çoklu endpoint kullan
    enable_lingva_fallback = True  # Lingva fallback aktif

    # Mirror Health Check Settings
    MIRROR_MAX_FAILURES = 5   # Max failures before temp ban
    MIRROR_BAN_TIME = 300     # Ban duration in seconds (5 min)

    def __init__(self, *args, config_manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._endpoint_index = 0
        self._lingva_index = 0
        self._endpoint_health: Dict[str, dict] = {}  # {url: {'fails': int, 'banned_until': float}}
        
        # Initialize health tracking for all endpoints
        for ep in self.google_endpoints:
            self._endpoint_health[ep] = {'fails': 0, 'banned_until': 0.0}

        # Load settings from config if available
        if config_manager:
            ts = config_manager.translation_settings
            self.use_multi_endpoint = getattr(ts, 'use_multi_endpoint', True)
            self.enable_lingva_fallback = getattr(ts, 'enable_lingva_fallback', True)
            # Slider ile kontrol edilen 'max_concurrent_threads' değerini baz alıyoruz
            self.multi_q_concurrency = getattr(ts, 'max_concurrent_threads', 16)
            self.max_slice_chars = getattr(ts, 'max_chars_per_request', 5000)
            self.max_texts_per_slice = getattr(ts, 'max_batch_size', 200)  # Use general batch size for Google
            self.aggressive_retry = getattr(ts, 'aggressive_retry_translation', False)
        else:
            self.aggressive_retry = False
        # Keep a baseline to restore when proxy adaptasyonu devre dışı
        self._base_multi_q_concurrency = self.multi_q_concurrency
    
    def _get_next_endpoint(self) -> str:
        """Round-robin endpoint selection with health checks."""
        now = time.time()
        
        # Filter available endpoints (not banned)
        available = []
        for ep in self.google_endpoints:
            health = self._endpoint_health.get(ep, {'fails': 0, 'banned_until': 0.0})
            if now > health['banned_until']:
                # Unban if time expired
                if health['banned_until'] > 0:
                     health['banned_until'] = 0.0
                     health['fails'] = 0 # Reset failures after ban
                available.append(ep)
        
        if not available:
            # If all banned, force unban all (emergency reset)
            self.logger.warning("All Google mirrors banned! Resetting health checks.")
            for ep in self.google_endpoints:
                self._endpoint_health[ep] = {'fails': 0, 'banned_until': 0.0}
            available = self.google_endpoints
            
        self._endpoint_index = (self._endpoint_index + 1) % len(available)
        return available[self._endpoint_index]
    
    def _get_next_lingva(self) -> str:
        """Round-robin Lingva instance selection."""
        self._lingva_index = (self._lingva_index + 1) % len(self.lingva_instances)
        return self.lingva_instances[self._lingva_index]
    
    async def _translate_via_lingva(self, text: str, source: str, target: str) -> Optional[str]:
        """Translate using Lingva (free Google proxy, no API key)."""
        # Lingva uses different language codes
        lingva_source = source if source != 'auto' else 'auto'
        
        for _ in range(len(self.lingva_instances)):
            instance = self._get_next_lingva()
            url = f"{instance}/api/v1/{lingva_source}/{target}/{urllib.parse.quote(text)}"
            
            try:
                session = await self._get_session()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and 'translation' in data:
                            return data['translation']
            except Exception as e:
                self.logger.debug(f"Lingva {instance} failed: {e}")
                continue
        
        return None

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate single text with multi-endpoint + Lingva fallback."""
        
        # Ren'Py değişkenlerini ve tag'lerini koru
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
        params = {'client':'gtx','sl':request.source_lang,'tl':request.target_lang,'dt':'t','q':protected_text}
        
        # Try Google endpoints first (parallel race)
        async def try_endpoint(endpoint: str) -> Optional[str]:
            try:
                query = urllib.parse.urlencode(params, doseq=True, safe='')
                url = f"{endpoint}?{query}"
                session = await self._get_session()
                
                proxy = None
                if self.use_proxy and self.proxy_manager:
                    p = self.proxy_manager.get_next_proxy()
                    if p:
                        proxy = p.url
                
                async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if data and isinstance(data, list) and data[0]:
                            text = ''.join(part[0] for part in data[0] if part and part[0])
                            # Reset failure count on success
                            if endpoint in self._endpoint_health:
                                self._endpoint_health[endpoint]['fails'] = 0
                            return text
                    
                    # Track failure (HTTP error)
                    if endpoint in self._endpoint_health:
                        self._endpoint_health[endpoint]['fails'] += 1
                        if self._endpoint_health[endpoint]['fails'] >= self.MIRROR_MAX_FAILURES:
                             self._endpoint_health[endpoint]['banned_until'] = time.time() + self.MIRROR_BAN_TIME
                             self.logger.warning(f"Google Mirror BANNED temporarily (5min): {endpoint}")

            except Exception as e:
                # Track failure (Exception)
                if endpoint in self._endpoint_health:
                    self._endpoint_health[endpoint]['fails'] += 1
                    if self._endpoint_health[endpoint]['fails'] >= self.MIRROR_MAX_FAILURES:
                            self._endpoint_health[endpoint]['banned_until'] = time.time() + self.MIRROR_BAN_TIME
                            self.logger.warning(f"Google Mirror BANNED temporarily (5min): {endpoint} ({str(e)[:50]})")
            return None
        
        translated_text = None
        max_unchanged_retries = 2  # Retry limit for unchanged translations
        
        # Multi-endpoint mode: Try 2 endpoints in parallel (fastest wins)
        if self.use_multi_endpoint:
            endpoints_to_try = [self._get_next_endpoint(), self._get_next_endpoint()]
            tasks = [asyncio.create_task(try_endpoint(ep)) for ep in endpoints_to_try]
            
            # Wait for first successful result
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    # Cancel remaining tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    
                    # Check if translation is unchanged (same as original)
                    final_text = restore_renpy_syntax(result, placeholders)
                    
                    # If translation equals original and aggressive_retry is enabled, try alternative methods
                    if self.aggressive_retry and final_text.strip() == request.text.strip():
                        self.logger.debug(f"Translation unchanged, retrying with Lingva: {request.text[:50]}")
                        
                        # Try Lingva fallback for unchanged translations
                        if self.enable_lingva_fallback:
                            for retry in range(max_unchanged_retries):
                                lingva_result = await self._translate_via_lingva(
                                    protected_text, request.source_lang, request.target_lang
                                )
                                if lingva_result:
                                    lingva_final = restore_renpy_syntax(lingva_result, placeholders)
                                    if lingva_final.strip() != request.text.strip():
                                        return TranslationResult(
                                            request.text, lingva_final, request.source_lang, request.target_lang,
                                            TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                                        )
                                await asyncio.sleep(0.5)  # Brief delay between retries
                        
                        # Try different Google endpoints sequentially
                        for retry in range(max_unchanged_retries):
                            alt_endpoint = self._get_next_endpoint()
                            alt_result = await try_endpoint(alt_endpoint)
                            if alt_result:
                                alt_final = restore_renpy_syntax(alt_result, placeholders)
                                
                                # INTEGRITY CHECK
                                if placeholders and not self._check_integrity(alt_final, placeholders):
                                     self.logger.warning("Integrity check failed (Retry): Placeholders missing. Using original.")
                                     alt_final = request.text
                                
                                if alt_final.strip() != request.text.strip():
                                    return TranslationResult(
                                        request.text, alt_final, request.source_lang, request.target_lang,
                                        TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                                    )
                            await asyncio.sleep(0.3)
                        
                        # All retries failed, return the unchanged text with lower confidence
                        self.logger.warning(f"Translation unchanged after retries: {request.text[:50]}")
                    
                    # INTEGRITY CHECK
                    if placeholders and not self._check_integrity(final_text, placeholders):
                         self.logger.warning("Integrity check failed (Google Multi): Placeholders missing. Using original.")
                         final_text = request.text
                    
                    return TranslationResult(
                        request.text, final_text, request.source_lang, request.target_lang,
                        TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata
                    )
        else:
            # Single endpoint mode
            result = await try_endpoint(self._get_next_endpoint())
            if result:
                final_text = restore_renpy_syntax(result, placeholders)
                
                # Retry if unchanged and aggressive_retry is enabled
                if self.aggressive_retry and final_text.strip() == request.text.strip():
                    self.logger.debug(f"Single-mode: translation unchanged, retrying: {request.text[:50]}")
                    
                    # Try Lingva
                    if self.enable_lingva_fallback:
                        lingva_result = await self._translate_via_lingva(
                            protected_text, request.source_lang, request.target_lang
                        )
                        if lingva_result:
                            lingva_final = restore_renpy_syntax(lingva_result, placeholders)
                            if lingva_final.strip() != request.text.strip():
                                return TranslationResult(
                                    request.text, lingva_final, request.source_lang, request.target_lang,
                                    TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                                )
                    
                    # Try alternative endpoints
                    for _ in range(max_unchanged_retries):
                        alt_result = await try_endpoint(self._get_next_endpoint())
                        if alt_result:
                            alt_final = restore_renpy_syntax(alt_result, placeholders)
                            if alt_final.strip() != request.text.strip():
                                return TranslationResult(
                                    request.text, alt_final, request.source_lang, request.target_lang,
                                    TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                                )
                        await asyncio.sleep(0.3)
                
                # INTEGRITY CHECK
                if placeholders and not self._check_integrity(final_text, placeholders):
                     self.logger.warning("Integrity check failed (Google Single): Placeholders missing. Using original.")
                     final_text = request.text
                
                return TranslationResult(
                    request.text, final_text, request.source_lang, request.target_lang,
                    TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata
                )
        
        # All Google endpoints failed, try Lingva fallback (if enabled)
        if self.enable_lingva_fallback:
            self.logger.debug("Google endpoints failed, trying Lingva fallback...")
            lingva_result = await self._translate_via_lingva(
                protected_text, request.source_lang, request.target_lang
            )
            
            if lingva_result:
                # Ren'Py değişkenlerini geri koy
                final_text = restore_renpy_syntax(lingva_result, placeholders)
                
                # BÜTÜNLÜK KONTROLÜ
                if placeholders and not self._check_integrity(final_text, placeholders):
                        self.logger.warning(f"Integrity check failed (Lingva): Placeholders missing in translation. Using original text.")
                        final_text = request.text

                return TranslationResult(
                    request.text, final_text, request.source_lang, request.target_lang,
                    TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                )
        
        # Last resort: sync requests library
        try:
            import requests as req_lib
            def do():
                return req_lib.get(
                    self.google_endpoints[0], 
                    params=params, 
                    timeout=5, 
                    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
            resp = await asyncio.to_thread(do)
            if resp.status_code == 200:
                data2 = resp.json()
                if data2 and isinstance(data2, list) and data2[0]:
                    text = ''.join(part[0] for part in data2[0] if part and part[0])
                    # Ren'Py değişkenlerini geri koy
                    # Ren'Py değişkenlerini geri koy
                    final_text = restore_renpy_syntax(text, placeholders)
                    
                    # BÜTÜNLÜK KONTROLÜ
                    if placeholders and not self._check_integrity(final_text, placeholders):
                        self.logger.warning(f"Integrity check failed (Fallback): Placeholders missing. Using original text.")
                        final_text = request.text

                    return TranslationResult(
                        request.text, final_text, request.source_lang, request.target_lang,
                        TranslationEngine.GOOGLE, True, confidence=0.8, metadata=request.metadata
                    )
        except Exception as e:
            pass
        
        return TranslationResult(
            request.text, "", request.source_lang, request.target_lang,
            TranslationEngine.GOOGLE, False, self._get_text('error_all_engines_failed', "All translation methods failed"), metadata=request.metadata
        )

    # =====================================================================
    # SMART LANGUAGE DETECTION
    # =====================================================================
    # Detect source language by analyzing multiple text samples using
    # majority voting. This prevents incorrect detection when games have
    # mixed-language content (e.g., English game with some Russian dialogue).
    # =====================================================================
    
    # Detection configuration constants
    DETECT_MIN_TEXT_LENGTH = 30      # Minimum characters for a sample to be valid
    DETECT_SAMPLE_SIZE = 15          # Number of samples to analyze
    DETECT_CONFIDENCE_THRESHOLD = 0.70  # Minimum 70% agreement required
    
    async def detect_language(self, texts: List[str], target_lang: str = None) -> Optional[str]:
        """
        Detects source language from a list of text samples using majority voting.
        
        This method analyzes multiple text samples and uses a confidence threshold
        to ensure reliable detection. If the confidence is below the threshold,
        it returns None, signaling that 'auto' mode should be used.
        
        Args:
            texts: List of text strings to analyze
            target_lang: Target language code (to avoid detecting target as source)
            
        Returns:
            ISO 639-1 language code (e.g., 'en', 'fr', 'ru') or None if confidence is low
        """
        # Filter meaningful texts (long enough for reliable detection)
        candidates = [t for t in texts if len(t.strip()) >= self.DETECT_MIN_TEXT_LENGTH]
        
        if not candidates:
            self.logger.debug("No suitable text samples for language detection")
            return None
        
        # Take random sample to avoid bias from specific game sections
        sample_size = min(self.DETECT_SAMPLE_SIZE, len(candidates))
        samples = random.sample(candidates, sample_size)
        
        self.logger.info(f"[Smart Detect] Analyzing {sample_size} text samples for language detection...")
        
        # Detect language for each sample
        detected_langs: List[str] = []
        for text in samples:
            lang = await self._detect_single_language(text)
            if lang:
                detected_langs.append(lang)
        
        if not detected_langs:
            self.logger.warning("[Smart Detect] Could not detect language from any sample")
            return None
        
        # Majority voting
        counter = Counter(detected_langs)
        winner, count = counter.most_common(1)[0]
        confidence = count / len(detected_langs)
        
        self.logger.info(f"[Smart Detect] Results: {dict(counter)} | Winner: {winner} ({confidence:.0%})")
        
        # Safety check: detected language should not equal target language
        if target_lang and winner.lower() == target_lang.lower():
            self.logger.warning(f"[Smart Detect] Detected language ({winner}) equals target language. Falling back to auto.")
            return None
        
        # Apply confidence threshold
        if confidence >= self.DETECT_CONFIDENCE_THRESHOLD:
            self.logger.info(f"[Smart Detect] ✓ Confirmed source language: {winner}")
            return winner
        else:
            self.logger.warning(f"[Smart Detect] Confidence {confidence:.0%} below threshold {self.DETECT_CONFIDENCE_THRESHOLD:.0%}. Using auto mode.")
            return None
    
    async def _detect_single_language(self, text: str) -> Optional[str]:
        """
        Detects the language of a single text using Google Translate API.
        
        Args:
            text: Text to analyze (should be 30+ characters for accuracy)
            
        Returns:
            ISO 639-1 language code or None on error
        """
        # Use Google's language detection endpoint
        params = {
            'client': 'gtx',
            'sl': 'auto',
            'tl': 'en',  # Target doesn't matter for detection
            'dt': 't',
            'q': text[:500]  # Limit text length for API efficiency
        }
        
        try:
            endpoint = self._get_next_endpoint()
            session = await self._get_session()
            
            async with session.get(
                endpoint,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=False
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    # Google returns detected language at index [2]
                    # Format: [[["translated", "original", null, null, 10]], null, "detected_lang"]
                    if data and isinstance(data, list) and len(data) > 2:
                        detected = data[2]
                        if isinstance(detected, str) and len(detected) >= 2:
                            return detected.lower()
        except Exception as e:
            self.logger.debug(f"Language detection failed for sample: {e}")
        
        return None

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Optimize edilmiş toplu çeviri:
        1. Aynı metinleri tek sefer çevir (dedup)
        2. Büyük listeyi karakter limitine göre slice'lara böl
        3. Slice'ları paralel (bounded) multi-q istekleriyle çalıştır
        4. Orijinal sıra korunur
        """
        if not requests:
            return []

        # Apply adaptive concurrency only when proxy kullanımda ve havuz var
        try:
            if (
                hasattr(self, 'proxy_manager') and self.proxy_manager
                and getattr(self, 'use_proxy', False)
                and getattr(self.proxy_manager, 'proxies', None)
            ):
                adaptive = self.proxy_manager.get_adaptive_concurrency()
                adaptive = max(2, min(adaptive, 64))
                self.logger.debug(f"Adaptive concurrency applied: {adaptive}")
                self.multi_q_concurrency = adaptive
            else:
                # Proxy yoksa başlangıç değerine dön
                base = getattr(self, '_base_multi_q_concurrency', None)
                if base:
                    self.multi_q_concurrency = base
        except Exception:
            pass
        
        self.logger.info(f"Starting batch translation: {len(requests)} texts, max_slice_chars={self.max_slice_chars}, concurrency={self.multi_q_concurrency}")
        
        # Dil çifti karışık ise fallback
        sl = {r.source_lang for r in requests}; tl = {r.target_lang for r in requests}
        if len(sl) > 1 or len(tl) > 1:
            return await super().translate_batch(requests)

        # Deduplikasyon
        indexed = list(enumerate(requests))
        unique_map: Dict[str, int] = {}
        unique_list: List[Tuple[int, TranslationRequest]] = []
        dup_links: Dict[int, int] = {}  # original_index -> unique_index
        for idx, req in indexed:
            key = req.text
            if key in unique_map:
                dup_links[idx] = unique_map[key]
            else:
                u_index = len(unique_list)
                unique_map[key] = u_index
                unique_list.append((idx, req))
                dup_links[idx] = u_index

        # Slice oluştur (karakter limiti + metin sayısı limiti)
        slices: List[List[Tuple[int, TranslationRequest]]] = []
        cur: List[Tuple[int, TranslationRequest]] = []
        cur_chars = 0
        for item in unique_list:
            text_len = len(item[1].text)
            # Hem karakter hem metin sayısı limitini kontrol et
            if cur and (cur_chars + text_len > self.max_slice_chars or len(cur) >= self.max_texts_per_slice):
                slices.append(cur)
                cur = []
                cur_chars = 0
            cur.append(item)
            cur_chars += text_len
        if cur:
            slices.append(cur)
        
        self.logger.info(f"Dedup: {len(requests)} -> {len(unique_list)} unique, {len(slices)} slices")

        # Paralel çalıştır (bounded)
        sem = asyncio.Semaphore(self.multi_q_concurrency)

        async def run_slice(slice_items: List[Tuple[int, TranslationRequest]]):
            async with sem:
                reqs = [r for _, r in slice_items]
                results = await self._multi_q(reqs)
                # slice içindeki index eşleşmesi (aynı uzunluk varsayımı)
                return [(slice_items[i][0], results[i]) for i in range(len(results))]

        tasks = [asyncio.create_task(run_slice(s)) for s in slices]
        gathered: List[List[Tuple[int, TranslationResult]]] = await asyncio.gather(*tasks)
        # Unique sonuç tablosu (unique sıraya göre)
        unique_results: Dict[int, TranslationResult] = {}
        for lst in gathered:
            for orig_idx, res in lst:
                # orig_idx burada unique_list içindeki orijinal global indeks değil; unique_list'te kaydettiğimiz idx
                # slice_items'te (global_index, request) vardı => orig_idx global index
                # unique index'i bulmak için dup_links'den tersine gerek yok; map oluşturalım
                # Hız için text'e göre de eşleyebilirdik; burada global index'ten unique index'e gidelim
                # unique index bul:
                # performans için bir kere hesaplanıyor
                pass

        # Daha hızlı yol: unique_list sırasına göre slice çıktılarından doldur
        # unique_list[i][0] = global index; onun sonucunu bulmak için hashedict
        global_to_result: Dict[int, TranslationResult] = {}
        for lst in gathered:
            for global_idx, res in lst:
                global_to_result[global_idx] = res

        # Şimdi tüm orijinal indeksleri sırayla doldururken dedup'u kopyala
        final_results: List[TranslationResult] = [None] * len(requests)  # type: ignore
        for original_idx, req in indexed:
            unique_idx = dup_links[original_idx]
            unique_global_index = unique_list[unique_idx][0]
            base_res = global_to_result[unique_global_index]
            if base_res is None:
                # Güvenlik fallback
                final_results[original_idx] = TranslationResult(req.text, "", req.source_lang, req.target_lang, TranslationEngine.GOOGLE, False, "Missing base result")
            else:
                # Aynı referansı paylaşmak yerine kopya (metadata farklı olabilir)
                final_results[original_idx] = TranslationResult(
                    original_text=req.text,
                    translated_text=base_res.translated_text,
                    source_lang=req.source_lang,
                    target_lang=req.target_lang,
                    engine=base_res.engine,
                    success=base_res.success,
                    error=base_res.error,
                    confidence=base_res.confidence,
                    metadata=req.metadata
                )
        
        # POST-BATCH RETRY: Check for unchanged translations and retry them individually
        # Only enabled when aggressive_retry is True (configurable in settings)
        if self.aggressive_retry:
            unchanged_indices = []
            for idx, (req, res) in enumerate(zip(requests, final_results)):
                if res and res.success and res.translated_text.strip() == req.text.strip():
                    unchanged_indices.append(idx)
            
            if unchanged_indices and len(unchanged_indices) <= 100:  # Limit retry batch size
                self.logger.info(f"Batch retry: {len(unchanged_indices)} unchanged translations found, retrying individually...")
                
                # Retry unchanged translations with translate_single (which has full retry logic)
                sem = asyncio.Semaphore(self.multi_q_concurrency)
                
                async def retry_one(idx: int) -> Tuple[int, TranslationResult]:
                    async with sem:
                        req = requests[idx]
                        result = await self.translate_single(req)
                        return (idx, result)
                
                retry_tasks = [asyncio.create_task(retry_one(idx)) for idx in unchanged_indices]
                retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
                
                retry_success = 0
                for item in retry_results:
                    if isinstance(item, Exception):
                        continue
                    idx, new_result = item
                    if new_result.success and new_result.translated_text.strip() != requests[idx].text.strip():
                        final_results[idx] = new_result
                        retry_success += 1
                
                if retry_success > 0:
                    self.logger.info(f"Batch retry success: {retry_success}/{len(unchanged_indices)} translations recovered")
        
        return final_results

    # Separator for batch translation
    # Using a unique pattern that translation engines are unlikely to modify
    # Numbers and specific pattern make it very unlikely to be translated
    BATCH_SEPARATOR = "\n|||RNLSEP999|||\n"
    
    # Alternative separators to try if first fails
    BATCH_SEPARATORS = [
        "\n|||RNLSEP999|||\n",
        "\n[[[SEP777]]]\n", 
        "\n###TXTSEP###\n",
    ]
    
    async def _multi_q(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Batch translation - tries separator method first, falls back to parallel individual.

        For better performance, uses parallel individual translation when batch method fails.
        """
        if not batch:
            return []
        if len(batch) == 1:
            return [await self.translate_single(batch[0])]

        total_chars = sum(len(r.text) for r in batch)

        # Küçük batch'ler için separator dene (daha hızlı)
        if len(batch) <= 25 and total_chars <= 4000:
            result = await self._try_batch_separator(batch)
            if result:
                return result

        # Separator başarısız veya batch büyük - paralel çeviri
        self.logger.debug(f"Using parallel translation for {len(batch)} texts")
        return await self._translate_parallel(batch)
    
    async def _try_batch_separator(self, batch: List[TranslationRequest]) -> Optional[List[TranslationResult]]:
        """Try batch translation with separator. Returns None if fails."""
        combined_text = self.BATCH_SEPARATOR.join(r.text for r in batch)
        
        params = {
            'client': 'gtx',
            'sl': batch[0].source_lang,
            'tl': batch[0].target_lang,
            'dt': 't',
            'q': combined_text
        }
        query = urllib.parse.urlencode(params)
        
        async def try_endpoint(endpoint: str) -> Optional[List[str]]:
            """Try a single endpoint, return list of translations or None."""
            try:
                url = f"{endpoint}?{query}"
                session = await self._get_session()
                
                proxy = None
                if self.use_proxy and self.proxy_manager:
                    p = self.proxy_manager.get_next_proxy()
                    if p:
                        proxy = p.url
                
                async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        if endpoint in self._endpoint_health:
                            self._endpoint_health[endpoint]['fails'] += 1
                            if self._endpoint_health[endpoint]['fails'] >= self.MIRROR_MAX_FAILURES:
                                self._endpoint_health[endpoint]['banned_until'] = time.time() + self.MIRROR_BAN_TIME
                                self.logger.warning(f"Google Mirror BANNED temporarily (5min): {endpoint}")
                        self.logger.debug(f"Batch-sep {endpoint}: HTTP {resp.status}")
                        return None
                    
                    data = await resp.json(content_type=None)
                    segs = data[0] if isinstance(data, list) and data else None
                    if not segs:
                        self.logger.debug(f"Batch-sep {endpoint}: No segments in response")
                        return None
                    
                    # Combine all translation segments
                    full_translation = ""
                    for seg in segs:
                        if seg and seg[0]:
                            full_translation += seg[0]
                    
                    # Split by separator
                    parts = full_translation.split(self.BATCH_SEPARATOR)
                    
                    # Verify count matches
                    if len(parts) != len(batch):
                        self.logger.debug(f"Batch-sep {endpoint}: Part count mismatch - expected {len(batch)}, got {len(parts)}")
                        return None
                    
                    # Success - reset endpoint failures
                    if endpoint in self._endpoint_health:
                        self._endpoint_health[endpoint]['fails'] = 0
                    return parts
            
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if endpoint in self._endpoint_health:
                    self._endpoint_health[endpoint]['fails'] += 1
                    if self._endpoint_health[endpoint]['fails'] >= self.MIRROR_MAX_FAILURES:
                        self._endpoint_health[endpoint]['banned_until'] = time.time() + self.MIRROR_BAN_TIME
                        self.logger.warning(f"Google Mirror BANNED temporarily (5min): {endpoint} ({str(e)[:50]})")
                self.logger.debug(f"Batch-sep failed on {endpoint}: {e}")
                return None
        
        # Parallel endpoint racing (if enabled)
        if self.use_multi_endpoint:
            endpoints_to_try = [self._get_next_endpoint() for _ in range(min(3, len(self.google_endpoints)))]
            tasks = [asyncio.create_task(try_endpoint(ep)) for ep in endpoints_to_try]
            
            try:
                # Wait for first successful result
                for coro in asyncio.as_completed(tasks):
                    try:
                        result = await coro
                        if result:
                            # Cancel remaining tasks
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                            self.logger.debug(f"Batch-sep success: {len(batch)} texts translated")
                            return [
                                TranslationResult(
                                    original_text=r.text,
                                    translated_text=t.strip(),
                                    source_lang=r.source_lang,
                                    target_lang=r.target_lang,
                                    engine=TranslationEngine.GOOGLE,
                                    success=True,
                                    confidence=0.9,
                                    metadata=r.metadata
                                )
                                for r, t in zip(batch, result)
                            ]
                    except asyncio.CancelledError:
                        raise
                # Avoid spamming user console; keep detailed info in debug logs only
                self.logger.debug(f"Batch-sep: All Google endpoints failed for {len(batch)} texts")
            except asyncio.CancelledError:
                # Cancel all tasks on cancellation
                for t in tasks:
                    if not t.done():
                        t.cancel()
                raise
        else:
            # Single endpoint mode (sequential)
            for _ in range(3):
                result = await try_endpoint(self._get_next_endpoint())
                if result:
                    return [
                        TranslationResult(
                            original_text=r.text,
                            translated_text=t.strip(),
                            source_lang=r.source_lang,
                            target_lang=r.target_lang,
                            engine=TranslationEngine.GOOGLE,
                            success=True,
                            confidence=0.9,
                            metadata=r.metadata
                        )
                        for r, t in zip(batch, result)
                    ]
                result = await try_endpoint(self._get_next_endpoint())
                if result:
                    return [
                        TranslationResult(
                            original_text=r.text,
                            translated_text=t,
                            source_lang=r.source_lang,
                            target_lang=r.target_lang,
                            engine=TranslationEngine.GOOGLE,
                            success=True,
                            confidence=0.9,
                            metadata=r.metadata
                        )
                        for r, t in zip(batch, result)
                    ]
        
        # Batch separator failed
        return None
    
    async def _translate_parallel(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Translate texts in parallel using multiple endpoints for speed."""
        if not batch:
            return []
        
        # Paralel çeviri için semaphore (aynı anda çok fazla istek atmamak için)
        sem = asyncio.Semaphore(self.multi_q_concurrency)
        
        async def translate_one(req: TranslationRequest) -> TranslationResult:
            async with sem:
                return await self.translate_single(req)
        
        # Tüm çevirileri paralel başlat
        tasks = [asyncio.create_task(translate_one(req)) for req in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sonuçları işle
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.debug(f"Parallel translation failed for text {i+1}: {result}")
                final_results.append(TranslationResult(
                    batch[i].text, "", batch[i].source_lang, batch[i].target_lang,
                    TranslationEngine.GOOGLE, False, str(result)
                ))
            else:
                final_results.append(result)
        
        success_count = sum(1 for r in final_results if r.success)
        self.logger.debug(f"Parallel translation: {success_count}/{len(batch)} successful")
        
        return final_results
    
    async def _translate_individually(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Translate texts one by one as fallback."""
        results = []
        for i, req in enumerate(batch):
            try:
                result = await self.translate_single(req)
                results.append(result)
                # Rate limiting - small delay between requests
                if i < len(batch) - 1:
                    await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.debug(f"Individual translation failed for text {i+1}: {e}")
                results.append(TranslationResult(
                    req.text, "", req.source_lang, req.target_lang,
                    TranslationEngine.GOOGLE, False, str(e)
                ))
            
            # Log progress every 10 texts
            if (i + 1) % 10 == 0:
                self.logger.debug(f"Individual translation progress: {i+1}/{len(batch)}")
        
        return results

    def get_supported_languages(self) -> Dict[str,str]:
        return {'auto':'Auto','en':'English','tr':'Turkish'}


class PseudoTranslator(BaseTranslator):
    """
    Pseudo-Localization Engine for testing UI bounds and font compatibility.
    
    This translator doesn't call any API - it transforms text locally to help:
    1. Test UI text overflow (adds expansion markers)
    2. Test font compatibility (uses accented characters)
    3. Identify untranslated strings (wrapped markers are visible)
    
    Modes:
    - 'expand': Adds [!!! ... !!!] markers for length testing
    - 'accent': Replaces vowels with accented versions
    - 'both': Combines expansion and accenting (default)
    """
    
    # Vowel accent mapping for pseudo-localization
    ACCENT_MAP = str.maketrans(
        "aeiouAEIOUyY",
        "àéîõüÀÉÎÕÜýÝ"
    )
    
    # Extended accent map for more thorough testing
    EXTENDED_ACCENT_MAP = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "àḃċḋéḟġḣíjḳĺṁńöṗqŕśṫûṿẁẍÿźÀḂĊḊÉḞĠḢÍJḲĹṀŃÖṖQŔŚṪÛṾẀẌŸŹ"
    )
    
    def __init__(self, *args, mode: str = "both", **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode  # 'expand', 'accent', or 'both'
    
    def _apply_accents(self, text: str) -> str:
        """Replace ASCII letters with accented versions."""
        return text.translate(self.ACCENT_MAP)
    
    def _apply_expansion(self, text: str) -> str:
        """Add expansion markers to test UI bounds."""
        # ~30% expansion typical for EN->DE/FR, simulate this
        return f"[!!! {text} !!!]"
    
    def _pseudo_transform(self, text: str) -> str:
        """
        Transform text based on mode:
        - expand: [!!! text !!!]
        - accent: tëxt wïth àccénts
        - both: [!!! tëxt wïth àccénts !!!]
        """
        if not text or not text.strip():
            return text
        
        result = text
        
        if self.mode in ('accent', 'both'):
            result = self._apply_accents(result)
        
        if self.mode in ('expand', 'both'):
            result = self._apply_expansion(result)
        
        return result
    
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Pseudo-translate a single text (no API call)."""
        # Protect Ren'Py syntax before transformation
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
        # Split by placeholders (both Ren'Py and Glossary ones)
        # Pattern matches XRPYX...XRPYX
        parts = re.split(r'(XRPYX[A-Z0-9]+XRPYX)', protected_text)
        new_parts = []
        for part in parts:
            if part.startswith('XRPYX') and part.endswith('XRPYX'):
                # It's a placeholder, keep it as is
                new_parts.append(part)
            else:
                # Translatable text, apply pseudo-transformation
                new_parts.append(self._pseudo_transform(part))
        
        pseudo_text = "".join(new_parts)
        
        # Restore Ren'Py syntax
        final_text = restore_renpy_syntax(pseudo_text, placeholders)
        
        return TranslationResult(
            original_text=request.text,
            translated_text=final_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            engine=TranslationEngine.PSEUDO,
            success=True,
            confidence=1.0,  # Always succeeds
            metadata={**request.metadata, 'pseudo_mode': self.mode}
        )
    
    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Pseudo-translate a batch (all local, very fast)."""
        return [await self.translate_single(r) for r in requests]
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Pseudo-localization works for any language."""
        return {
            'pseudo': 'Pseudo-Localization (Test)',
            'expand': 'Expansion Test [!!! !!!]',
            'accent': 'Accent Test (àccénts)',
        }


class DeepLTranslator(BaseTranslator):
    base_url_paid = "https://api.deepl.com/v2/translate"
    base_url_free = "https://api-free.deepl.com/v2/translate"

    def _map_lang(self, lang: str, is_target: bool = True) -> str:
        """Map generic language codes to DeepL specific codes."""
        if not lang: return "EN"
        l = lang.lower()
        
        # DeepL specific target mappings
        if is_target:
            if l == 'en': return 'EN-US'
            if l == 'pt': return 'PT-PT'
            if l == 'zh-cn': return 'ZH'
            if l == 'zh-tw': return 'ZH'
        
        # Source mappings
        if l == 'en': return 'EN'
        if l == 'ja': return 'JA'
        if l == 'ko': return 'KO'
        if l == 'zh-cn' or l == 'zh-tw': return 'ZH'
        
        return l.upper()

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, self._get_text('error_deepl_key_required', "DeepL API key required"))

        batch_res = await self.translate_batch([request])
        return batch_res[0]

    # DeepL retry settings
    MAX_RETRIES = 3
    RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff delays in seconds
    
    # DeepL formality options
    FORMALITY_OPTIONS = {
        "default": None,      # DeepL decides
        "formal": "more",     # More formal (Sie in DE, Usted in ES, etc.)
        "informal": "less"    # Less formal (Du in DE, tú in ES, etc.)
    }

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        if not requests: return []
        if not self.api_key:
            return [TranslationResult(r.text, "", r.source_lang, r.target_lang, TranslationEngine.DEEPL, False, "API Key Missing") for r in requests]

        source_lang = self._map_lang(requests[0].source_lang, False) if requests[0].source_lang and requests[0].source_lang != "auto" else None
        target_lang = self._map_lang(requests[0].target_lang, True)
        
        # DeepL XML tag handling is much more robust for placeholders
        # Replace XRPYX style placeholders with XML tags
        xml_protected_texts = []
        all_placeholders = []
        
        for r in requests:
            p_text, p_holders = protect_renpy_syntax(r.text)
            # Map XRPYX to <x id="N"/> tags
            # We must be careful not to break the mapping
            temp_text = p_text
            for i, (ph, orig) in enumerate(p_holders.items()):
                # Use a very short tag to save characters/quota
                xml_tag = f'<x i="{i}"/>'
                temp_text = temp_text.replace(ph, xml_tag)
            
            xml_protected_texts.append(temp_text)
            all_placeholders.append(p_holders)

        data = {
            "auth_key": self.api_key,
            "target_lang": target_lang,
            "text": xml_protected_texts,
            "tag_handling": "xml",
            "ignore_tags": "x" # Tell DeepL to ignore our 'x' tag
        }
        if source_lang:
            data["source_lang"] = source_lang
        
        # Add formality if configured and supported by target language
        # Formality is supported for: DE, FR, IT, ES, NL, PL, PT, RU, JA
        formality_languages = {'de', 'fr', 'it', 'es', 'nl', 'pl', 'pt', 'ru', 'ja'}
        formality_setting = getattr(self.config_manager, 'deepl_formality', 'default') if self.config_manager else 'default'
        formality_value = self.FORMALITY_OPTIONS.get(formality_setting)
        if formality_value and target_lang.lower()[:2] in formality_languages:
            data["formality"] = formality_value

        base_url = self.base_url_free if ":fx" in self.api_key or self.api_key.startswith("free:") else self.base_url_paid
        
        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                session = await self._get_session()
                proxy = self.proxy_manager.get_next_proxy().url if self.use_proxy and self.proxy_manager else None

                async with session.post(base_url, data=data, proxy=proxy, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                    if resp.status != 200:
                        try:
                            err_data = await resp.json()
                            msg = err_data.get('message', f"HTTP {resp.status}")
                            if resp.status == 456:
                                msg = "Quota Exceeded"
                                is_quota = True
                            else:
                                is_quota = False
                        except:
                            msg = await resp.text()
                            is_quota = False
                        
                        # Don't retry on quota exceeded or auth errors
                        if resp.status in (401, 403, 456):
                            return [TranslationResult(r.text, "", r.source_lang, r.target_lang, TranslationEngine.DEEPL, False, f"DeepL Error: {msg[:120]}", quota_exceeded=is_quota) for r in requests]
                        
                        # Retry on transient errors (5xx, timeout, etc.)
                        last_error = f"HTTP {resp.status}: {msg[:100]}"
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAYS[attempt])
                            continue
                        return [TranslationResult(r.text, "", r.source_lang, r.target_lang, TranslationEngine.DEEPL, False, f"DeepL Error: {last_error}", quota_exceeded=is_quota) for r in requests]

                payload = await resp.json(content_type=None)
                translations = payload.get("translations", [])
                
                results = []
                for i, r in enumerate(requests):
                    if i < len(translations):
                        translated = translations[i].get("text", "")
                        # Map XML tags back to XRPYX placeholders
                        final_v = translated
                        for j, (ph, orig) in enumerate(all_placeholders[i].items()):
                            xml_tag = f'<x i="{j}"/>'
                            # Also handle cases where DeepL might add spaces: <x i = "0" />
                            final_v = final_v.replace(xml_tag, ph)
                            if ph not in final_v:
                                # Regex fallback for corrupted tags
                                pattern = re.compile(rf'<x\s+i\s*=\s*"{j}"\s*/>', re.IGNORECASE)
                                final_v = pattern.sub(ph, final_v)
                        
                        # Apply standard restoration
                        final_text = restore_renpy_syntax(final_v, all_placeholders[i])
                        
                        # --- DeepL Space Cleanup for Ren'Py Tags ---
                        # Fix common cases where DeepL adds spaces inside Ren'Py tags:
                        # { i } -> {i}, { b } -> {b}, { /i } -> {/i}, etc.
                        # This regex finds { tag } patterns and removes internal spaces
                        renpy_tag_cleanup = [
                            # {i}, {b}, {u}, {s}, {/i}, {/b}, {/u}, {/s}, {plain}, {/plain}
                            (r'\{\s*/?\s*(i|b|u|s|plain|fast|nw|p|w|cps|color|font|size|alpha|outlinecolor|k|rb|rt)\s*\}', 
                             lambda m: '{' + m.group(1).strip().replace(' ', '') + '}'),
                            # {/i}, {/b} etc with slash
                            (r'\{\s*/\s*(i|b|u|s|plain|fast|nw|p|w|cps|color|font|size|alpha|outlinecolor|k|rb|rt)\s*\}',
                             lambda m: '{/' + m.group(1).strip() + '}'),
                            # {color=...}, {size=...}, {font=...} with values
                            (r'\{\s*(color|size|font|alpha|outlinecolor|cps|k)\s*=\s*([^}]+?)\s*\}',
                             lambda m: '{' + m.group(1).strip() + '=' + m.group(2).strip() + '}'),
                            # [variable] - remove internal spaces: [ variable ] -> [variable]
                            (r'\[\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\]',
                             lambda m: '[' + m.group(1).strip() + ']'),
                        ]
                        
                        for pattern, replacement in renpy_tag_cleanup:
                            final_text = re.sub(pattern, replacement, final_text, flags=re.IGNORECASE)
                        
                        results.append(TranslationResult(r.text, final_text, r.source_lang, r.target_lang, TranslationEngine.DEEPL, True, confidence=0.98))
                    else:
                        results.append(TranslationResult(r.text, "", r.source_lang, r.target_lang, TranslationEngine.DEEPL, False, "Missing translation in response"))
                return results

            except Exception as e:
                # Retry on network/timeout errors
                last_error = str(e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAYS[attempt])
                    continue
        
        # All retries exhausted
        msg = last_error or "Unknown error after retries"
        is_quota = "456" in msg or "quota" in msg.lower()
        if is_quota:
            msg = "Quota Exceeded"
        return [TranslationResult(r.text, "", r.source_lang, r.target_lang, TranslationEngine.DEEPL, False, f"DeepL Error: {msg}", quota_exceeded=is_quota) for r in requests]

    def get_supported_languages(self) -> Dict[str,str]:
        return {
            'bg': 'Bulgarian', 'cs': 'Czech', 'da': 'Danish', 'de': 'German', 'el': 'Greek',
            'en': 'English', 'es': 'Spanish', 'et': 'Estonian', 'fi': 'Finnish', 'fr': 'French',
            'hu': 'Hungarian', 'id': 'Indonesian', 'it': 'Italian', 'ja': 'Japanese', 'ko': 'Korean',
            'lt': 'Lithuanian', 'lv': 'Latvian', 'nb': 'Norwegian', 'nl': 'Dutch', 'pl': 'Polish',
            'pt': 'Portuguese', 'ro': 'Romanian', 'ru': 'Russian', 'sk': 'Slovak', 'sl': 'Slovenian',
            'sv': 'Swedish', 'tr': 'Turkish', 'uk': 'Ukrainian', 'zh': 'Chinese'
        }

class TranslationManager:
    def __init__(self, proxy_manager=None, config_manager=None):
        self.proxy_manager = proxy_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.translators: Dict[TranslationEngine, BaseTranslator] = {}
        self.should_stop_callback: Optional[Callable[[], bool]] = None
        self.max_retries = 1
        self.retry_delays = [0.1, 0.2, 0.5, 1.0]
        self.max_batch_size = 500
        self.max_concurrent_requests = 32

        # Sync with config if available
        if self.config_manager:
            ts = self.config_manager.translation_settings
            self.max_retries = getattr(ts, 'max_retries', 1)
            self.max_batch_size = getattr(ts, 'max_batch_size', 500)
            self.max_concurrent_requests = getattr(ts, 'max_concurrent_threads', 32)
            self.use_cache = getattr(ts, 'use_cache', True)
        else:
            self.use_cache = True

        self.cache_capacity = 20000
        self._cache: OrderedDict = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self.cache_hits = 0
        self.cache_misses = 0
        # Adaptive
        self.adaptive_enabled = True
        self.max_concurrency_cap = 512
        self.min_concurrency_floor = 4
        self._recent_metrics = deque(maxlen=500)
        self._adapt_lock = asyncio.Lock()
        self._last_adapt_time = 0.0
        self.adapt_interval_sec = 5.0
        self.ai_request_delay = 1.5  # Default, will be updated by Pipeline

    def add_translator(self, engine: TranslationEngine, translator: BaseTranslator):
        self.translators[engine] = translator

    def remove_translator(self, engine: TranslationEngine):
        self.translators.pop(engine, None)

    def set_proxy_enabled(self, enabled: bool):
        for t in self.translators.values():
            t.set_proxy_enabled(enabled)

    def set_max_concurrency(self, value: int):
        self.max_concurrent_requests = max(1, int(value))

    async def close_all(self):
        tasks = []
        for t in self.translators.values():
            if hasattr(t, 'close'):
                tasks.append(t.close())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _cache_get(self, key: Tuple[str,str,str,str]) -> Optional[TranslationResult]:
        if not self.use_cache:
            return None
        async with self._cache_lock:
            val = self._cache.get(key)
            if val:
                self._cache.move_to_end(key)
            return val

    async def _cache_put(self, key: Tuple[str,str,str,str], val: TranslationResult):
        if not self.use_cache or not val.success:
            return
        async with self._cache_lock:
            self._cache[key] = val
            self._cache.move_to_end(key)
            if len(self._cache) > self.cache_capacity:
                self._cache.popitem(last=False)

    async def translate_with_retry(self, req: TranslationRequest) -> TranslationResult:
        tr = self.translators.get(req.engine)
        if not tr:
            return TranslationResult(req.text, "", req.source_lang, req.target_lang, req.engine, False, f"Translator {req.engine.value} not available")
        key = (req.engine.value, req.source_lang, req.target_lang, req.text)
        cached = await self._cache_get(key)
        if cached:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        last_err = None
        start = time.time()
        for attempt in range(self.max_retries + 1):
            try:
                res = await tr.translate_single(req)
                print(f"[DEBUG] translate_single returned: success={res.success}, text='{res.translated_text[:50] if res.translated_text else 'EMPTY'}', error={res.error}")
                if res.success:
                    await self._cache_put(key, res)
                    print(f"[DEBUG] Added to cache: {req.text[:30]}...")
                    await self._record_metric(time.time() - start, True)
                    return res
                last_err = res.error
            except Exception as e:
                print(f"[DEBUG] translate_single EXCEPTION: {e}")
                last_err = str(e)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
        await self._record_metric(time.time() - start, False)
        return TranslationResult(req.text, "", req.source_lang, req.target_lang, req.engine, False, f"Failed: {last_err}")

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        if not requests:
            return []
        
        # 1. Merkezi Deduplikasyon ve Cache Kontrolü
        indexed = list(enumerate(requests))
        final_results: List[Optional[TranslationResult]] = [None] * len(requests)
        
        # Benzersiz metinleri topla
        unique_req_map: Dict[Tuple[str, str, str, str], List[int]] = {}  # (engine, src, tgt, text) -> [original_indices]
        for idx, req in indexed:
            key = (req.engine.value, req.source_lang, req.target_lang, req.text)
            unique_req_map.setdefault(key, []).append(idx)
        
        # Cache'den kontrol et
        remaining_indices: List[int] = []
        for key, indices in unique_req_map.items():
            cached = await self._cache_get(key)
            if cached:
                self.cache_hits += 1
                for idx in indices:
                    # Kopyala ki metadata bozulmasın
                    final_results[idx] = TranslationResult(
                        original_text=requests[idx].text,
                        translated_text=cached.translated_text,
                        source_lang=cached.source_lang,
                        target_lang=cached.target_lang,
                        engine=cached.engine,
                        success=True,
                        metadata=requests[idx].metadata
                    )
            else:
                self.cache_misses += 1
                # Sadece ilk indeksi çeviriye gönder, diğerleri bunun sonucunu bekleyecek
                remaining_indices.append(indices[0])
        
        if not remaining_indices:
            return final_results # type: ignore

        # 2. Motorlara Göre Grupla (Sadece cache'de olmayanlar)
        groups: Dict[TranslationEngine, List[Tuple[int, TranslationRequest]]] = {}
        for idx in remaining_indices:
            req = requests[idx]
            groups.setdefault(req.engine, []).append((idx, req))
        
        for engine, items in groups.items():
            if self.should_stop_callback and self.should_stop_callback():
                break
            tr = self.translators.get(engine)
            if not tr:
                for idx, r in items:
                    final_results[idx] = TranslationResult(r.text, "", r.source_lang, r.target_lang, r.engine, False, f"Translator {engine.value} not available")
                continue
            
            is_ai = engine in (TranslationEngine.OPENAI, TranslationEngine.GEMINI, TranslationEngine.LOCAL_LLM)
            only = [r for _, r in items]
            
            # Batch çeviri desteği kontrolü
            can_batch = (isinstance(tr, GoogleTranslator) or is_ai or isinstance(tr, DeepLTranslator))
            
            translated_items: List[TranslationResult] = []
            if can_batch and len(only) > 1:
                try:
                    bout = await tr.translate_batch(only)
                    if bout and len(bout) == len(only):
                        translated_items = bout
                    else:
                        # Fallback to single if batch returns invalid size
                        translated_items = []
                except Exception as e:
                    self.logger.debug(f"Batch fail {engine.value}: {e}")
                    translated_items = []
            
            if translated_items:
                # Toplu sonuçları yerleştir
                for (idx, _), res in zip(items, translated_items):
                    final_results[idx] = res
                    if res.success:
                        key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                        await self._cache_put(key2, res)
            else:
                # Tekil çeviri akışı
                concurrency = self.max_concurrent_requests
                if is_ai:
                    concurrency = 2
                    if self.config_manager and hasattr(self.config_manager.translation_settings, 'ai_concurrency'):
                        concurrency = self.config_manager.translation_settings.ai_concurrency
                
                sem = asyncio.Semaphore(concurrency)
                async def run_single(ix: int, rq: TranslationRequest):
                    async with sem:
                        if self.should_stop_callback and self.should_stop_callback():
                            return ix, TranslationResult(rq.text, "", rq.source_lang, rq.target_lang, rq.engine, False, "Stopped by user")
                        res = await self.translate_with_retry(rq)
                        if is_ai and self.ai_request_delay > 0:
                            await asyncio.sleep(self.ai_request_delay)
                        return ix, res

                results = await asyncio.gather(*[run_single(i, r) for i, r in items])
                for idx, res in results:
                    final_results[idx] = res
                    if res and res.success:
                        key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                        await self._cache_put(key2, res)

        # 3. Sonuçları kopya (deduplicated) satırlara dağıt
        for key, indices in unique_req_map.items():
            first_idx = indices[0]
            res = final_results[first_idx]
            if res:
                for other_idx in indices[1:]:
                    # Metadata korunarak kopyalanır
                    final_results[other_idx] = TranslationResult(
                        original_text=requests[other_idx].text,
                        translated_text=res.translated_text,
                        source_lang=res.source_lang,
                        target_lang=res.target_lang,
                        engine=res.engine,
                        success=res.success,
                        error=res.error,
                        confidence=res.confidence,
                        metadata=requests[other_idx].metadata
                    )

        await self._maybe_adapt_concurrency()
        return [r if r else TranslationResult(requests[i].text, "", requests[i].source_lang, requests[i].target_lang, requests[i].engine, False, "Translation failed") for i, r in enumerate(final_results)]

    def get_cache_stats(self) -> Dict[str, float]:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total else 0.0
        return {'size': len(self._cache), 'capacity': self.cache_capacity, 'hits': self.cache_hits, 'misses': self.cache_misses, 'hit_rate': round(hit_rate, 2)}

    async def _record_metric(self, dur: float, ok: bool):
        if not self.adaptive_enabled:
            return
        self._recent_metrics.append((dur, ok))
        if len(self._recent_metrics) % 25 == 0:
            await self._maybe_adapt_concurrency()

    def report_rate_limit(self, engine: TranslationEngine):
        """Signal that a rate limit was hit, triggering immediate concurrency reduction."""
        if not self.adaptive_enabled:
            return
            
        # Immediate reaction to rate limit
        self.ai_request_delay = min(5.0, self.ai_request_delay + 0.5)
        
        # Reduce AI concurrency in settings if possible
        if self.config_manager and hasattr(self.config_manager.translation_settings, 'ai_concurrency'):
            current = self.config_manager.translation_settings.ai_concurrency
            new_val = max(1, int(current * 0.5))
            if new_val != current:
                self.config_manager.translation_settings.ai_concurrency = new_val
                self.logger.warning(f"Rate Limit hit! Reduced AI concurrency to {new_val} and increased delay to {self.ai_request_delay}s")

    async def _maybe_adapt_concurrency(self):
        if not self.adaptive_enabled:
            return
        now = time.time()
        if now - self._last_adapt_time < self.adapt_interval_sec:
            return
        if len(self._recent_metrics) < 20:
            return
        async with self._adapt_lock:
            now2 = time.time()
            if now2 - self._last_adapt_time < self.adapt_interval_sec:
                return
            durations = [d for d, _ in self._recent_metrics]
            successes = [s for _, s in self._recent_metrics]
            avg_latency = sum(durations) / len(durations)
            fail_rate = 1 - (sum(1 for s in successes if s) / len(successes))
            old = self.max_concurrent_requests
            new = old
            
            # General concurrency adaptation
            if fail_rate > 0.2 or avg_latency > 1.5:
                new = max(self.min_concurrency_floor, int(old * 0.8))
            elif fail_rate < 0.05 and avg_latency < 0.5:
                # Slowly recover
                new = min(self.max_concurrency_cap, max(old + 1, int(old * 1.1)))
                
                # Also recover AI delay slowly
                if self.ai_request_delay > 1.5:
                    self.ai_request_delay = max(1.5, self.ai_request_delay - 0.1)

            if new != old:
                self.max_concurrent_requests = new
                self.logger.info(f"Adaptive concurrency {old} -> {new} (lat={avg_latency:.3f}s fail={fail_rate:.2%})")
            
            self._last_adapt_time = now2

    def set_concurrency_limit(self, limit: int):
        """Çeviri concurrency limitini dinamik olarak ayarla."""
        # Proxy tabanlı adaptif öneriyi TranslationManager seviyesinde uygulamak için
        # mevcut `set_max_concurrency` metodunu kullanıyoruz.
        try:
            self.set_max_concurrency(int(limit))
        except Exception:
            self.set_max_concurrency(max(1, int(limit)))

    def save_cache(self, file_path: str):
        """Cache içeriğini diske kaydet."""
        print(f"[DEBUG] save_cache called. Cache size: {len(self._cache)}")  # Console'a yaz
        try:
            import json
            data = {}
            for key, val in self._cache.items():
                # key: (engine, sl, tl, text)
                engine_str, sl, tl, text = key
                if engine_str not in data:
                    data[engine_str] = {}
                if sl not in data[engine_str]:
                    data[engine_str][sl] = {}
                if tl not in data[engine_str][sl]:
                    data[engine_str][sl][tl] = {}
                data[engine_str][sl][tl][text] = val.translated_text

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] Cache written to {file_path} with {len(self._cache)} entries")  # Console'a yaz
            self.logger.info(f"Cache saved: {file_path} ({len(self._cache)} entries)")
        except Exception as e:
            print(f"[DEBUG] Cache save FAILED: {e}")  # Console'a yaz
            self.logger.error(f"Failed to save cache: {e}")

    def load_cache(self, file_path: str):
        """Cache içeriğini diskten yükle."""
        if not os.path.exists(file_path):
            return
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            count = 0
            for engine_str, sl_map in data.items():
                try:
                    engine = TranslationEngine(engine_str)
                except:
                    continue
                for sl, tl_map in sl_map.items():
                    for tl, text_map in tl_map.items():
                        for text, translated in text_map.items():
                            key = (engine_str, sl, tl, text)
                            res = TranslationResult(
                                original_text=text,
                                translated_text=translated,
                                source_lang=sl,
                                target_lang=tl,
                                engine=engine,
                                success=True
                            )
                            self._cache[key] = res
                            count += 1
            
            # Keep only the last capacity entries
            while len(self._cache) > self.cache_capacity:
                self._cache.popitem(last=False)
                
            self.logger.info(f"Cache loaded: {file_path} ({count} entries)")
        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")
