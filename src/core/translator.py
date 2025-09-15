"""Temiz ve stabilize çeviri altyapısı (Google + stub motorlar + cache + adaptif concurrency)."""

from __future__ import annotations

import asyncio
import aiohttp
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from collections import OrderedDict, deque


class TranslationEngine(Enum):
    GOOGLE = "google"
    DEEPL = "deepl"
    YANDEX = "yandex"
    BING = "bing"
    LIBRETRANSLATOR = "libre"
    DEEP_TRANSLATOR = "deep_translator"
    OPUS_MT = "opus_mt"


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
    metadata: Dict = field(default_factory=dict)


class BaseTranslator(ABC):
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None):
        self.api_key = api_key
        self.proxy_manager = proxy_manager
        self.use_proxy = True
        self.logger = logging.getLogger(self.__class__.__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(limit=256, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(connector=self._connector, timeout=timeout)
        return self._session

    async def close(self):
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
            self._connector = None

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
                raise RuntimeError(f"HTTP {resp.status}")
        elif method.upper() == "POST":
            async with session.post(url, proxy=proxy, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                raise RuntimeError(f"HTTP {resp.status}")
        else:
            raise ValueError("Unsupported method")

    @abstractmethod
    async def translate_single(self, request: TranslationRequest) -> TranslationResult: ...

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        return [await self.translate_single(r) for r in requests]

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]: ...


class GoogleTranslator(BaseTranslator):
    base_url = "https://translate.googleapis.com/translate_a/single"
    multi_q_concurrency = 8  # Aynı anda kaç multi-q isteği
    max_slice_chars = 6000   # Her slice toplam karakter limiti

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        params = {'client':'gtx','sl':request.source_lang,'tl':request.target_lang,'dt':'t','q':request.text}
        try:
            query = urllib.parse.urlencode(params, doseq=True, safe='')
            data = await self._make_request(f"{self.base_url}?{query}")
            if data and isinstance(data, list) and data and data[0]:
                text = ''.join(part[0] for part in data[0] if part and part[0])
                return TranslationResult(request.text, text, request.source_lang, request.target_lang, TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata)
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, "Parse failure", metadata=request.metadata)
        except Exception:
            import requests
            try:
                def do():
                    return requests.get(self.base_url, params=params, timeout=5, headers={'User-Agent':'Mozilla/5.0'})
                resp = await asyncio.to_thread(do)
                if resp.status_code == 200:
                    data2 = resp.json()
                    if data2 and isinstance(data2, list) and data2 and data2[0]:
                        text = ''.join(part[0] for part in data2[0] if part and part[0])
                        return TranslationResult(request.text, text, request.source_lang, request.target_lang, TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata)
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, f"HTTP {resp.status_code}", metadata=request.metadata)
            except Exception as e2:
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, str(e2), metadata=request.metadata)

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Optimize edilmiş toplu çeviri:
        1. Aynı metinleri tek sefer çevir (dedup)
        2. Büyük listeyi karakter limitine göre slice'lara böl
        3. Slice'ları paralel (bounded) multi-q istekleriyle çalıştır
        4. Orijinal sıra korunur
        """
        if not requests:
            return []
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

        # Slice oluştur
        slices: List[List[Tuple[int, TranslationRequest]]] = []
        cur: List[Tuple[int, TranslationRequest]] = []
        cur_chars = 0
        for item in unique_list:
            text_len = len(item[1].text)
            if cur and cur_chars + text_len > self.max_slice_chars:
                slices.append(cur)
                cur = []
                cur_chars = 0
            cur.append(item)
            cur_chars += text_len
        if cur:
            slices.append(cur)

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
        return final_results

    async def _multi_q(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        if not batch: return []
        if len(batch) == 1: return [await self.translate_single(batch[0])]
        params: List[Tuple[str,str]] = [('client','gtx'),('sl',batch[0].source_lang),('tl',batch[0].target_lang),('dt','t')]
        for r in batch: params.append(('q', r.text))
        query = urllib.parse.urlencode(params, doseq=True, safe='')
        try:
            data = await self._make_request(f"{self.base_url}?{query}")
            segs = data[0] if isinstance(data, list) and data else None
            if not segs: raise ValueError('no segments')
            originals = [r.text for r in batch]
            mapped = [""]*len(batch)
            idx=0; acc_o=""; acc_t=""
            for seg in segs:
                if not seg or len(seg)<2: continue
                tpart, opart = seg[0], seg[1]
                if opart is None: continue
                acc_o += opart; acc_t += tpart
                if idx < len(originals) and acc_o == originals[idx]:
                    mapped[idx]=acc_t; idx+=1; acc_o=""; acc_t=""; 
                    if idx>=len(originals): break
                elif idx < len(originals) and len(acc_o) > len(originals[idx]) + 20:
                    raise ValueError('align fail')
            if any(not m for m in mapped): raise ValueError('incomplete')
            return [TranslationResult(r.text, t, r.source_lang, r.target_lang, TranslationEngine.GOOGLE, True, confidence=0.9) for r,t in zip(batch,mapped)]
        except Exception:
            return await super().translate_batch(batch)

    def get_supported_languages(self) -> Dict[str,str]:
        return {'auto':'Auto','en':'English','tr':'Turkish'}


class DeepLTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, "API key required")
        return TranslationResult(request.text, request.text, request.source_lang, request.target_lang, TranslationEngine.DEEPL, True, confidence=0.5)

    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}


class YandexTranslator(BaseTranslator):
    base_url = "https://translate.yandex.net/api/v1.5/tr.json/translate"
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, "API key required")
        import requests
        try:
            lang_pair = f"{request.source_lang}-{request.target_lang}" if request.source_lang != 'auto' else request.target_lang
            params = {'key': self.api_key,'text':request.text,'lang':lang_pair,'format':'plain'}
            proxies=None
            if self.use_proxy and self.proxy_manager:
                p=self.proxy_manager.get_next_proxy();
                if p: proxies={'http':p.url,'https':p.url}
            resp = await asyncio.to_thread(lambda: requests.post(self.base_url,data=params,timeout=10,proxies=proxies))
            if resp.status_code==200:
                data=resp.json()
                if data.get('code')==200 and 'text' in data:
                    txt=' '.join(data['text'])
                    return TranslationResult(request.text, txt, request.source_lang, request.target_lang, TranslationEngine.YANDEX, True, confidence=0.9)
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, data.get('message','API error'))
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, f"HTTP {resp.status_code}")
        except Exception as e:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, str(e))

    def get_supported_languages(self) -> Dict[str,str]: return {'auto':'Auto','en':'English','tr':'Turkish'}


class BingTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.BING, False, "Not implemented")
    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}


class LibreTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(request.text, request.text, request.source_lang, request.target_lang, TranslationEngine.LIBRETRANSLATOR, True, confidence=0.5)
    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}


class DeepTranslator(BaseTranslator):
    """Deep-Translator - Multi-engine translation wrapper."""
    
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None):
        super().__init__(api_key, proxy_manager)
        self.engine_name = "google"  # Default engine
        self._translator = None
        self._init_translator()
        
    def _init_translator(self):
        """Initialize the deep-translator instance."""
        try:
            from deep_translator import GoogleTranslator
            self._translator = GoogleTranslator(source='auto', target='en')
            self.logger.info("Deep-Translator initialized successfully")
        except ImportError:
            self.logger.error("Deep-Translator not installed. Install with: pip install deep-translator")
            raise ImportError("Deep-Translator not available.")
        except Exception as e:
            self.logger.error(f"Failed to initialize Deep-Translator: {e}")
            raise
    
    def _setup_translator_for_languages(self, from_code: str, to_code: str):
        """Setup translator for specific language pair."""
        try:
            from deep_translator import GoogleTranslator
            
            # Handle 'auto' source language
            source_lang = from_code if from_code != 'auto' else 'auto'
            
            # Create translator for this language pair
            translator = GoogleTranslator(source=source_lang, target=to_code)
            return translator
            
        except Exception as e:
            self.logger.error(f"Failed to setup translator for {from_code}->{to_code}: {e}")
            return None
    
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single text using Deep-Translator."""
        try:
            # Setup translator for this language pair
            translator = self._setup_translator_for_languages(request.source_lang, request.target_lang)
            if not translator:
                return TranslationResult(
                    request.text, "", request.source_lang, request.target_lang,
                    TranslationEngine.ARGOS, False, 
                    f"Failed to setup translator for {request.source_lang}->{request.target_lang}",
                    metadata=request.metadata
                )
            
            # Perform translation
            translated_text = await asyncio.to_thread(translator.translate, request.text)
            
            if not translated_text or translated_text == request.text:
                # Fallback or no translation occurred
                confidence = 0.3
                success = bool(translated_text)
            else:
                confidence = 0.85  # Deep-Translator typically provides good quality
                success = True
                
            return TranslationResult(
                request.text, translated_text or "", 
                request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, success,
                confidence=confidence, metadata=request.metadata
            )
            
        except ImportError:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, False, "Deep-Translator not installed",
                metadata=request.metadata
            )
        except Exception as e:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, False, f"Deep-Translator error: {str(e)}",
                metadata=request.metadata
            )
    
    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Batch translation using Deep-Translator."""
        if not requests:
            return []
        
        if len(requests) == 1:
            return [await self.translate_single(requests[0])]
        
        # Group by language pair for efficiency
        grouped = {}
        for i, req in enumerate(requests):
            key = (req.source_lang, req.target_lang)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append((i, req))
        
        results = [None] * len(requests)
        
        # Process each language pair group
        for (from_lang, to_lang), group in grouped.items():
            # Setup translator for this language pair
            translator = self._setup_translator_for_languages(from_lang, to_lang)
            if not translator:
                # Fill with error results
                for idx, req in group:
                    results[idx] = TranslationResult(
                        req.text, "", req.source_lang, req.target_lang,
                        TranslationEngine.ARGOS, False,
                        f"Failed to setup translator for {from_lang}->{to_lang}",
                        metadata=req.metadata
                    )
                continue
            
            # Translate all texts in this group
            try:
                # Extract texts and translate them one by one (Deep-Translator doesn't have native batching)
                for idx, req in group:
                    try:
                        translated_text = await asyncio.to_thread(translator.translate, req.text)
                        
                        if not translated_text or translated_text == req.text:
                            confidence = 0.3
                            success = bool(translated_text)
                        else:
                            confidence = 0.85
                            success = True
                        
                        results[idx] = TranslationResult(
                            req.text, translated_text or "",
                            req.source_lang, req.target_lang,
                            TranslationEngine.ARGOS, success,
                            confidence=confidence, metadata=req.metadata
                        )
                    except Exception as e:
                        results[idx] = TranslationResult(
                            req.text, "", req.source_lang, req.target_lang,
                            TranslationEngine.ARGOS, False, f"Translation error: {str(e)}",
                            metadata=req.metadata
                        )
                    
            except Exception as e:
                # Fill with error results
                for idx, req in group:
                    results[idx] = TranslationResult(
                        req.text, "", req.source_lang, req.target_lang,
                        TranslationEngine.ARGOS, False, f"Batch setup error: {str(e)}",
                        metadata=req.metadata
                    )
        
        return results
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language codes and names."""
        # Common languages supported by Argos Translate
        return {
            'auto': 'Auto-detect',
            'en': 'English',
            'tr': 'Turkish', 
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'nl': 'Dutch',
            'pl': 'Polish',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish',
            'el': 'Greek',
            'he': 'Hebrew',
            'cs': 'Czech',
            'sk': 'Slovak',
            'hu': 'Hungarian',
            'uk': 'Ukrainian',
            'ca': 'Catalan',
            'eu': 'Basque',
            'eo': 'Esperanto',
            'ga': 'Irish',
            'cy': 'Welsh'
        }


class OpusMTTranslator(BaseTranslator):
    """Argos Translate - True offline neural machine translation."""
    
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None):
        super().__init__(api_key, proxy_manager)
        self._installed_packages = set()
        self._available_packages = []
        self._packages_loaded = False
        
    async def _ensure_packages_loaded(self):
        """Ensure language packages are loaded and available."""
        if self._packages_loaded:
            return
            
        try:
            import argostranslate.package
            import argostranslate.translate
            
            # Update package index
            await asyncio.to_thread(argostranslate.package.update_package_index)
            self._available_packages = await asyncio.to_thread(argostranslate.package.get_available_packages)
            self._packages_loaded = True
            
            # Log available packages
            self.logger.info(f"Argos Translate: {len(self._available_packages)} language packages available")
            
        except ImportError:
            self.logger.error("Argos Translate not installed. Install with: pip install argostranslate")
            raise ImportError("Argos Translate not available.")
        except Exception as e:
            self.logger.error(f"Failed to load Argos Translate packages: {e}")
            raise
    
    async def _ensure_language_package(self, from_code: str, to_code: str) -> bool:
        """Ensure the required language package is installed."""
        try:
            await self._ensure_packages_loaded()
            import argostranslate.package
            
            # Handle 'auto' source language
            if from_code == 'auto':
                from_code = 'en'  # Fallback to English for auto-detection
            
            package_key = f"{from_code}-{to_code}"
            
            # Check if already installed
            if package_key in self._installed_packages:
                return True
                
            # Find and install package
            package_to_install = None
            for package in self._available_packages:
                if package.from_code == from_code and package.to_code == to_code:
                    package_to_install = package
                    break
                    
            if not package_to_install:
                self.logger.warning(f"No Argos package found for {from_code}->{to_code}")
                return False
                
            # Download and install package
            self.logger.info(f"Installing Argos package: {from_code}->{to_code}")
            download_path = await asyncio.to_thread(package_to_install.download)
            await asyncio.to_thread(argostranslate.package.install_from_path, download_path)
            
            self._installed_packages.add(package_key)
            self.logger.info(f"Successfully installed Argos package: {package_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install language package {from_code}->{to_code}: {e}")
            return False
    
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single text using Argos Translate."""
        try:
            # Ensure required package is installed
            if not await self._ensure_language_package(request.source_lang, request.target_lang):
                return TranslationResult(
                    request.text, "", request.source_lang, request.target_lang,
                    TranslationEngine.ARGOS, False, 
                    f"Language package {request.source_lang}->{request.target_lang} not available",
                    metadata=request.metadata
                )
            
            import argostranslate.translate
            
            # Handle 'auto' source language
            from_code = request.source_lang
            if from_code == 'auto':
                from_code = 'en'  # Argos doesn't support auto-detection
            
            # Perform translation
            translated_text = await asyncio.to_thread(
                argostranslate.translate.translate,
                request.text,
                from_code,
                request.target_lang
            )
            
            if not translated_text or translated_text == request.text:
                # Fallback or no translation occurred
                confidence = 0.3
                success = bool(translated_text)
            else:
                confidence = 0.85  # Argos typically provides good quality
                success = True
                
            return TranslationResult(
                request.text, translated_text or "", 
                request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, success,
                confidence=confidence, metadata=request.metadata
            )
            
        except ImportError:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, False, "Argos Translate not installed",
                metadata=request.metadata
            )
        except Exception as e:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.ARGOS, False, f"Argos error: {str(e)}",
                metadata=request.metadata
            )
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language codes and names."""
        # Common languages supported by Argos Translate
        return {
            'auto': 'Auto-detect',
            'en': 'English',
            'tr': 'Turkish', 
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'nl': 'Dutch',
            'pl': 'Polish',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish',
            'el': 'Greek',
            'he': 'Hebrew',
            'cs': 'Czech',
            'sk': 'Slovak',
            'hu': 'Hungarian',
            'uk': 'Ukrainian',
            'ca': 'Catalan',
            'eu': 'Basque',
            'eo': 'Esperanto',
            'ga': 'Irish',
            'cy': 'Welsh'
        }


class OpusMTTranslator(BaseTranslator):
    """OPUS-MT - Offline neural machine translation using Hugging Face Transformers."""
    
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None):
        super().__init__(api_key, proxy_manager)
        self._models_cache = {}
        self._tokenizers_cache = {}
        self._main_window = None  # Will be set by GUI
        
    def _get_model_name(self, from_code: str, to_code: str) -> Optional[str]:
        """Get OPUS-MT model name for language pair."""
        # Handle auto-detect
        if from_code == 'auto':
            from_code = 'en'  # Default to English
            
        # OPUS-MT model mappings (real Hugging Face model names)
        model_mappings = {
            # Turkish models
            ('en', 'tr'): 'Helsinki-NLP/opus-mt-tc-big-en-tr',
            ('tr', 'en'): 'Helsinki-NLP/opus-mt-tc-big-tr-en',
            
            # German models  
            ('en', 'de'): 'Helsinki-NLP/opus-mt-tc-big-en-de',
            ('de', 'en'): 'Helsinki-NLP/opus-mt-tc-big-de-en',
            
            # French models
            ('en', 'fr'): 'Helsinki-NLP/opus-mt-tc-big-en-fr',
            ('fr', 'en'): 'Helsinki-NLP/opus-mt-tc-big-fr-en',
            
            # Spanish models
            ('en', 'es'): 'Helsinki-NLP/opus-mt-tc-big-en-es',
            ('es', 'en'): 'Helsinki-NLP/opus-mt-tc-big-es-en',
            
            # Italian models
            ('en', 'it'): 'Helsinki-NLP/opus-mt-tc-big-en-it',
            ('it', 'en'): 'Helsinki-NLP/opus-mt-tc-big-it-en',
            
            # Russian models
            ('en', 'ru'): 'Helsinki-NLP/opus-mt-tc-big-en-ru',
            ('ru', 'en'): 'Helsinki-NLP/opus-mt-tc-big-ru-en',
            
            # Japanese models (different naming pattern)
            ('en', 'ja'): 'Helsinki-NLP/opus-mt-en-jap',
            ('ja', 'en'): 'Helsinki-NLP/opus-mt-jap-en',
            
            # Chinese models
            ('en', 'zh'): 'Helsinki-NLP/opus-mt-en-zh',
            ('zh', 'en'): 'Helsinki-NLP/opus-mt-zh-en',
            
            # Korean models
            ('en', 'ko'): 'Helsinki-NLP/opus-mt-tc-big-en-ko',
            ('ko', 'en'): 'Helsinki-NLP/opus-mt-tc-big-ko-en',
            
            # Portuguese models
            ('en', 'pt'): 'Helsinki-NLP/opus-mt-tc-big-en-pt',
            ('pt', 'en'): 'Helsinki-NLP/opus-mt-tc-big-pt-en',
            
            # Arabic models
            ('en', 'ar'): 'Helsinki-NLP/opus-mt-tc-big-en-ar',
            ('ar', 'en'): 'Helsinki-NLP/opus-mt-tc-big-ar-en',
            
            # Dutch models
            ('en', 'nl'): 'Helsinki-NLP/opus-mt-tc-big-en-nl',
            ('nl', 'en'): 'Helsinki-NLP/opus-mt-tc-big-nl-en',
            
            # Polish models
            ('en', 'pl'): 'Helsinki-NLP/opus-mt-tc-big-en-pl',
            ('pl', 'en'): 'Helsinki-NLP/opus-mt-tc-big-pl-en',
            
            # Swedish models
            ('en', 'sv'): 'Helsinki-NLP/opus-mt-tc-big-en-sv',
            ('sv', 'en'): 'Helsinki-NLP/opus-mt-tc-big-sv-en',
            
            # Norwegian models
            ('en', 'no'): 'Helsinki-NLP/opus-mt-tc-big-en-no',
            ('no', 'en'): 'Helsinki-NLP/opus-mt-tc-big-no-en',
            
            # Danish models
            ('en', 'da'): 'Helsinki-NLP/opus-mt-tc-big-en-da',
            ('da', 'en'): 'Helsinki-NLP/opus-mt-tc-big-da-en',
        }
        
        return model_mappings.get((from_code, to_code))
    
    def _is_model_available_locally(self, model_name: str) -> bool:
        """Check if model is available locally without downloading."""
        try:
            from transformers import MarianMTModel
            import os
            from pathlib import Path
            
            # Check Hugging Face cache directory
            cache_dir = os.environ.get('TRANSFORMERS_CACHE', 
                                      os.path.join(Path.home(), '.cache', 'huggingface', 'transformers'))
            
            # Look for model files in cache
            model_path = Path(cache_dir) / f"models--{model_name.replace('/', '--')}"
            
            # Check if model directory exists and has required files
            if model_path.exists():
                config_file = model_path / "snapshots" / "refs" / "main"
                if config_file.parent.exists():
                    # Check if there are any snapshot directories
                    snapshots_dir = model_path / "snapshots"
                    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                        return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking model availability: {e}")
            return False
    
    async def _show_download_dialog(self, model_name: str, from_lang: str, to_lang: str) -> bool:
        """Show download confirmation dialog and handle download."""
        try:
            # Signal main window to show dialog and wait for response
            if hasattr(self._main_window, 'show_model_download_dialog'):
                language_pair = f"{from_lang.upper()} → {to_lang.upper()}"
                return await self._main_window.show_model_download_dialog(model_name, language_pair)
            else:
                self.logger.warning("Main window does not support download dialogs")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to show download dialog: {e}")
            return False  # Default to not download if dialog fails
    
    async def _load_model(self, model_name: str, show_download_dialog: bool = True):
        """Load model and tokenizer, cache them."""
        if model_name in self._models_cache:
            return self._models_cache[model_name], self._tokenizers_cache[model_name]
        
        try:
            from transformers import MarianMTModel, MarianTokenizer
            import os
            from pathlib import Path
            
            # Check if model exists locally
            model_cache_dir = Path.home() / ".cache" / "huggingface" / "transformers" / model_name.replace("/", "--")
            model_exists = model_cache_dir.exists() and any(model_cache_dir.glob("*.bin")) or any(model_cache_dir.glob("*.safetensors"))
            
            if not model_exists and show_download_dialog:
                # Model needs to be downloaded - this should trigger UI dialog
                raise FileNotFoundError(f"Model {model_name} not found locally and needs download confirmation")
            
            # Load in separate thread to avoid blocking
            model = await asyncio.to_thread(MarianMTModel.from_pretrained, model_name)
            tokenizer = await asyncio.to_thread(MarianTokenizer.from_pretrained, model_name)
            
            # Cache them
            self._models_cache[model_name] = model
            self._tokenizers_cache[model_name] = tokenizer
            
            self.logger.info(f"Loaded OPUS-MT model: {model_name}")
            return model, tokenizer
            
        except Exception as e:
            self.logger.error(f"Failed to load OPUS-MT model {model_name}: {e}")
            raise
    
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single text using OPUS-MT."""
        try:
            # Get model name
            model_name = self._get_model_name(request.source_lang, request.target_lang)
            if not model_name:
                return TranslationResult(
                    request.text, "", request.source_lang, request.target_lang,
                    TranslationEngine.OPUS_MT, False, 
                    f"No OPUS-MT model for {request.source_lang}->{request.target_lang}",
                    metadata=request.metadata
                )
            
            # Load model and tokenizer (may trigger download dialog)
            try:
                model, tokenizer = await self._load_model(model_name)
            except FileNotFoundError:
                # Model needs download - return specific error for GUI to handle
                return TranslationResult(
                    request.text, "", request.source_lang, request.target_lang,
                    TranslationEngine.OPUS_MT, False, 
                    f"MODEL_DOWNLOAD_REQUIRED:{model_name}:{request.source_lang}:{request.target_lang}",
                    metadata=request.metadata
                )
            
            # Perform translation
            def translate_text():
                # Tokenize input
                inputs = tokenizer([request.text], return_tensors="pt", padding=True)
                
                # Generate translation
                outputs = model.generate(**inputs, max_new_tokens=512, do_sample=False)
                
                # Decode result
                translated = tokenizer.decode(outputs[0], skip_special_tokens=True)
                return translated
            
            translated_text = await asyncio.to_thread(translate_text)
            
            if not translated_text or translated_text == request.text:
                confidence = 0.3
                success = bool(translated_text)
            else:
                confidence = 0.9  # OPUS-MT typically provides high quality
                success = True
                
            return TranslationResult(
                request.text, translated_text or "", 
                request.source_lang, request.target_lang,
                TranslationEngine.OPUS_MT, success,
                confidence=confidence, metadata=request.metadata
            )
            
        except ImportError:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.OPUS_MT, False, "Transformers not installed",
                metadata=request.metadata
            )
        except Exception as e:
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang,
                TranslationEngine.OPUS_MT, False, f"OPUS-MT error: {str(e)}",
                metadata=request.metadata
            )
    
    async def check_model_availability(self, from_lang: str, to_lang: str) -> Tuple[bool, str]:
        """Check if model is available for language pair without downloading."""
        model_name = self._get_model_name(from_lang, to_lang)
        if not model_name:
            return False, f"No OPUS-MT model for {from_lang}->{to_lang}"
        
        if self._is_model_available_locally(model_name):
            return True, "Model available"
        else:
            return False, f"MODEL_DOWNLOAD_REQUIRED:{model_name}:{from_lang}:{to_lang}"
    
    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Translate a batch of texts, checking model availability first."""
        if not requests:
            return []
        
        # Check if we need to download models before processing
        language_pairs = set((req.source_lang, req.target_lang) for req in requests)
        missing_models = []
        
        for from_lang, to_lang in language_pairs:
            available, message = await self.check_model_availability(from_lang, to_lang)
            if not available and "MODEL_DOWNLOAD_REQUIRED" in message:
                missing_models.append(message)
        
        # If any models are missing, return error for all requests
        if missing_models:
            error_message = missing_models[0]  # Use first missing model for dialog
            return [
                TranslationResult(
                    req.text, "", req.source_lang, req.target_lang,
                    TranslationEngine.OPUS_MT, False, error_message,
                    metadata=req.metadata
                ) for req in requests
            ]
        
        # All models available, proceed with translation
        results = []
        for request in requests:
            result = await self.translate_single(request)
            results.append(result)
        
        return results
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language codes and names."""
        # Languages with available OPUS-MT models
        return {
            'auto': 'Auto-detect',
            'en': 'English',
            'tr': 'Turkish', 
            'de': 'German',
            'fr': 'French',
            'es': 'Spanish',
            'it': 'Italian',
            'ru': 'Russian',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'ko': 'Korean',
            'pt': 'Portuguese',
            'ar': 'Arabic',
            'nl': 'Dutch',
            'pl': 'Polish',
            'sv': 'Swedish',
            'no': 'Norwegian',
            'da': 'Danish'
        }


class TranslationManager:
    def __init__(self, proxy_manager=None):
        self.proxy_manager = proxy_manager
        self.logger = logging.getLogger(__name__)
        self.translators: Dict[TranslationEngine, BaseTranslator] = {}
        self.max_retries = 1
        self.retry_delays = [0.1,0.2]
        self.max_batch_size = 500
        self.max_concurrent_requests = 256
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
        async with self._cache_lock:
            val = self._cache.get(key)
            if val:
                self._cache.move_to_end(key)
            return val

    async def _cache_put(self, key: Tuple[str,str,str,str], val: TranslationResult):
        if not val.success:
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
                if res.success:
                    await self._cache_put(key, res)
                    await self._record_metric(time.time() - start, True)
                    return res
                last_err = res.error
            except Exception as e:
                last_err = str(e)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
        await self._record_metric(time.time() - start, False)
        return TranslationResult(req.text, "", req.source_lang, req.target_lang, req.engine, False, f"Failed: {last_err}")

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        if not requests:
            return []
        indexed = list(enumerate(requests))
        groups: Dict[TranslationEngine, List[Tuple[int, TranslationRequest]]] = {}
        for i, r in indexed:
            groups.setdefault(r.engine, []).append((i, r))
        buffer: List[Tuple[int, TranslationResult]] = []
        for engine, items in groups.items():
            tr = self.translators.get(engine)
            if not tr:
                for idx, r in items:
                    buffer.append((idx, TranslationResult(r.text, "", r.source_lang, r.target_lang, r.engine, False, f"Translator {engine.value} not available")))
                continue
            only = [r for _, r in items]
            used_batch = False
            if isinstance(tr, GoogleTranslator) and len(only) > 1:
                try:
                    bout = await tr.translate_batch(only)
                    if bout and len(bout) == len(only):
                        for (idx, _), res in zip(items, bout):
                            if res.success:
                                key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                                await self._cache_put(key2, res)
                            buffer.append((idx, res))
                        used_batch = True
                except Exception as e:
                    self.logger.debug(f"Batch fail {engine.value}: {e}")
            elif isinstance(tr, OpusMTTranslator) and len(only) > 1:
                # OPUS-MT batch processing
                try:
                    bout = await tr.translate_batch(only)
                    if bout and len(bout) == len(only):
                        for (idx, _), res in zip(items, bout):
                            if res.success:
                                key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                                await self._cache_put(key2, res)
                            buffer.append((idx, res))
                        used_batch = True
                except Exception as e:
                    self.logger.debug(f"OPUS-MT batch fail: {e}")
            elif isinstance(tr, DeepTranslator) and len(only) > 1:
                # Deep-Translator batch processing
                try:
                    bout = await tr.translate_batch(only)
                    if bout and len(bout) == len(only):
                        for (idx, _), res in zip(items, bout):
                            if res.success:
                                key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                                await self._cache_put(key2, res)
                            buffer.append((idx, res))
                        used_batch = True
                except Exception as e:
                    self.logger.debug(f"Deep-Translator batch fail: {e}")
            if used_batch:
                continue
            sem = asyncio.Semaphore(self.max_concurrent_requests)
            async def run_single(ix: int, rq: TranslationRequest):
                async with sem:
                    return ix, await self.translate_with_retry(rq)
            results = await asyncio.gather(*[run_single(i, r) for i, r in items])
            buffer.extend(results)
        await self._maybe_adapt_concurrency()
        buffer.sort(key=lambda x: x[0])
        return [r for _, r in buffer]

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
            if fail_rate > 0.2 or avg_latency > 1.5:
                new = max(self.min_concurrency_floor, int(old * 0.8))
            elif fail_rate < 0.05 and avg_latency < 0.5:
                new = min(self.max_concurrency_cap, max(old + 1, int(old * 1.1)))
            if new != old:
                self.max_concurrent_requests = new
                self.logger.info(f"Adaptive concurrency {old} -> {new} (lat={avg_latency:.3f}s fail={fail_rate:.2%})")
            self._last_adapt_time = time.time()
