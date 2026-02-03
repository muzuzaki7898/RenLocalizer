# -*- coding: utf-8 -*-
"""
Font Injector Module (Google Fonts API Integration)
===================================================

Automatically downloads and injects compatible fonts for specific languages into Ren'Py projects.
Uses Google Fonts official download endpoint to ensure reliability and avoid 404 errors.
"""

import os
import requests
import logging
import zipfile
import io
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

class FontInjector:
    """
    Downloads and configures compatible fonts for Ren'Py games using Google Fonts.
    """
    
    # Mapping: Language Code -> (Google Font Family Name, Is RTL?)
    FONT_MAP: Dict[str, Tuple[str, bool]] = {
        "fa": ("Vazirmatn", True),           # Persian
        "ar": ("Noto Sans Arabic", True),    # Arabic
        "he": ("Noto Sans Hebrew", True),    # Hebrew
        "ja": ("Noto Sans JP", False),       # Japanese
        "zh": ("Noto Sans SC", False),       # Chinese Simplified
        "zh_tw": ("Noto Sans TC", False),    # Chinese Traditional
        "ko": ("Noto Sans KR", False),       # Korean
        "ru": ("Noto Sans", False),          # Russian
        "th": ("Noto Sans Thai", False),     # Thai
        "tr": ("Noto Sans", False),          # Turkish
        "uk": ("Noto Sans", False),          # Ukrainian
        "vi": ("Noto Sans", False),          # Vietnamese
    }

    # Mapping: Ren'Py Lang Name -> ISO Code
    LANG_NAME_TO_CODE: Dict[str, str] = {
        "turkish": "tr",
        "russian": "ru",
        "japanese": "ja",
        "chinese": "zh",
        "schinese": "zh",
        "tchinese": "zh_tw",
        "korean": "ko",
        "english": "en",
        "french": "fr",
        "german": "de",
        "spanish": "es",
        "italian": "it",
        "portuguese": "pt",
        "arabic": "ar",
        "persian": "fa",
        "hebrew": "he",
        "thai": "th",
        "vietnamese": "vi",
        "ukrainian": "uk",
        "indonesian": "id",
        "malay": "ms",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_font_map_list(self) -> List[Dict[str, str]]:
        """Returns a list of default mapped fonts for UI."""
        return [{"lang": k, "font": v[0], "rtl": v[1]} for k, v in self.FONT_MAP.items()]

    def inject_font(self, game_dir: str, lang_code: str, force_font_family: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point. 
        If force_font_family is provided, it skips the language mapping lookup.
        """
        # 1. Resolve Language Code and Font Family
        if force_font_family:
            # Manual Selection Mode
            font_family = force_font_family
            # Try to guess RTL/Config from lang_code, but user overrides font
            base_lang = self._normalize_lang_code(lang_code)
            # Default to LTR unless map says otherwise for this lang
            is_rtl = self.FONT_MAP.get(base_lang, ("", False))[1] 
        else:
            # Auto Mode
            base_lang = self._normalize_lang_code(lang_code)
            
            if base_lang not in self.FONT_MAP:
                return {
                    "success": False,
                    "message": f"No auto mapping for '{lang_code}' (norm: {base_lang})",
                    "ui_key": "font_err_no_mapping",
                    "ui_args": {"lang": lang_code}
                }
            
            font_family, is_rtl = self.FONT_MAP[base_lang]
        
        try:
            # 2. Setup Directories
            game_path = Path(game_dir)
            if (game_path / "game").exists():
                game_path = game_path / "game"
                
            fonts_dir = game_path / "tl" / "renlocalizer_fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. Download & Extract
            download_success, result_data = self._download_and_extract_google_font(font_family, fonts_dir)
            
            if not download_success:
                return result_data

            font_filename = result_data 

            # 4. Generate RPY Script
            # We use the ORIGINAL lang_code (e.g. 'turkish') for the Ren'Py translate block
            rpy_path = game_path / "zzz_renlocalizer_font.rpy"
            renpy_font_path = f"tl/renlocalizer_fonts/{font_filename}"
            
            already_exists = self._update_rpy_script(rpy_path, lang_code, renpy_font_path, is_rtl)

            if already_exists:
                return {
                    "success": True,
                    "message": f"Configuration for {lang_code} updated/exists.",
                    "ui_key": "font_warn_already_exists",
                    "ui_args": {"lang": lang_code},
                    "path": str(rpy_path)
                }

            return {
                "success": True, 
                "message": f"Font {font_filename} injected for {lang_code}.",
                "ui_key": "font_success_injected",
                "ui_args": {"font": font_family, "lang": lang_code},
                "path": str(rpy_path)
            }
            
        except Exception as e:
            self.logger.error(f"Injection Critical Error: {e}")
            return {
                "success": False,
                "message": str(e),
                "ui_key": "font_err_download_fail", 
                "ui_args": {"error": str(e)}
            }

    # Popular Google Fonts List for Manual Selection
    POPULAR_FONTS = [
        "Roboto", "Open Sans", "Lato", "Montserrat", "Oswald", "Source Sans Pro", 
        "Slabo 27px", "Raleway", "PT Sans", "Merriweather", "Noto Sans", "Noto Serif",
        "Nunito", "Playfair Display", "Rubik", "Ubuntu", "Poppins", "Kanit", "Inter",
        "Quicksand", "Work Sans", "Fira Sans", "Barlow", "Mulish", "Inconsolata",
        "IBM Plex Sans", "Titillium Web", "DM Sans", "Oxygen", "Arimo", "Assistant",
        "Josefin Sans", "Libre Baskerville", "Anton", "Cairo", "Hind", "Bitter",
        "Vazirmatn", "Noto Sans Arabic", "Noto Sans JP", "Noto Sans SC", "Noto Sans KR",
        "Amiri", "Tajawal", "Almarai", "Harmattan", "Lalezar"
    ]

    def get_available_fonts(self) -> List[str]:
        """Returns list of popular fonts sorted alphabetically."""
        return sorted(self.POPULAR_FONTS)

    def _normalize_lang_code(self, lang_code: str) -> str:
        """Converts 'turkish' -> 'tr', 'zh-CN' -> 'zh', etc."""
        lower_code = lang_code.lower().strip()
        
        # Check name mapping first (turkish -> tr)
        if lower_code in self.LANG_NAME_TO_CODE:
            return self.LANG_NAME_TO_CODE[lower_code]
            
        # Standard normalization
        base = lower_code.split('-')[0]
        
        # Special cases
        if lower_code in ["zh-cn", "zh_cn", "zh-hans", "schinese"]:
            return "zh"
        elif lower_code in ["zh-tw", "zh_tw", "zh-hant", "tchinese"]:
            return "zh_tw"
            
        return base

    def _download_and_extract_google_font(self, font_family: str, target_dir: Path) -> Tuple[bool, Any]:
        """
        Downloads ZIP using google-webfonts-helper API (more reliable for scripts).
        """
        # Font adını ID'ye çevir (Open Sans -> open-sans)
        font_id = font_family.lower().strip().replace(' ', '-')
        
        # Geniş dil desteği için subsetleri ekle
        subsets = "latin,latin-ext,cyrillic,cyrillic-ext,greek,greek-ext,vietnamese"
        
        # API URL (Google Webfonts Helper)
        download_url = f"https://gwfh.mranftl.com/api/fonts/{font_id}?download=zip&subsets={subsets}&variants=regular,400,500,700"
        
        # Fallback URL (alternatif API)
        fallback_url = f"https://api.fontsource.org/v1/fonts/{font_id}/download"
        
        self.logger.info(f"Downloading Font ({font_id}) from: {download_url}")
        
        # Headers (Tarayıcı taklidi)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            # 1. Deneme: GWFH API
            response = requests.get(download_url, headers=headers, timeout=60)
            
            # 404 ise Fallback dene
            if response.status_code != 200:
                self.logger.warning(f"Primary API failed ({response.status_code}), trying fallback...")
                response = requests.get(fallback_url, headers=headers, timeout=60)
                
            response.raise_for_status()
            
            # İçerik kontrolü
            if len(response.content) < 1000:
                self.logger.warning(f"Downloaded file too small: {len(response.content)} bytes.")

            try:
                z = zipfile.ZipFile(io.BytesIO(response.content))
            except zipfile.BadZipFile:
                preview = response.content[:200].decode('utf-8', errors='ignore').replace('\n', ' ')
                self.logger.error(f"CRITICAL: Downloaded content is NOT a ZIP. Preview: {preview}")
                return False, {
                    "success": False,
                    "message": "Server returned invalid data (HTML error).",
                    "ui_key": "font_err_invalid_zip",
                    "ui_args": {}
                }
            
            # Find best font file (TTF > OTF)
            font_files = [f for f in z.namelist() if f.lower().endswith(('.ttf', '.otf'))]
            
            if not font_files:
                return False, {
                    "success": False,
                    "message": "No font file in ZIP",
                    "ui_key": "font_err_no_ttf",
                    "ui_args": {}
                }
            
            # Filter logic: Regular > any
            # GWFH usually returns clean names like 'roboto-v30-latin-regular.ttf'
            regulars = [f for f in font_files if "regular" in f.lower() or "-400" in f.lower()]
            best_file = regulars[0] if regulars else font_files[0]
            
            # Extract
            source = z.open(best_file)
            final_filename = os.path.basename(best_file)
            target_path = target_dir / final_filename
            
            # Eğer dosya zaten varsa boyutu farklıysa üzerine yaz
            write_file = True
            if target_path.exists():
                if target_path.stat().st_size > 0:
                    write_file = False # Zaten var, tekrar indirme (Bant genişliği tasarrufu)
            
            # Ancak kullanıcı manuel seçtiyse veya repair modundaysa zorla yazsın istiyoruz
            # Şimdilik basitlik adına overwrite edelim
            with open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
            
            self.logger.info(f"Extracted font to: {target_path}")
            return True, final_filename
            
        except requests.exceptions.HTTPError as e:
             return False, {
                "success": False,
                "message": f"Font download failed (HTTP {e.response.status_code if e.response else '?'}). Is the font name correct?",
                "ui_key": "font_err_download_fail",
                "ui_args": {"error": f"HTTP Error: {str(e)}"}
            }
        except Exception as e:
            return False, {
                "success": False,
                "message": str(e),
                "ui_key": "font_err_download_fail",
                "ui_args": {"error": str(e)}
            }

    def _update_rpy_script(self, rpy_path: Path, lang_code: str, font_path: str, is_rtl: bool) -> bool:
        """
        Updates script using Runtime Hooking.
        Intercepts ALL font loading calls, replacing them with our font safely.
        """
        
        # Bu yöntem Ren'Py'ın kendi font yükleme fonksiyonunu kancalar (hook).
        # Oyun geliştiricisi fontu kodun içine gömmüş olsa bile (hardcode),
        # oyun "Arial.ttf ver" dediğinde biz "Al sana NotoSans.ttf" deriz.
        # Bu sayede stil hataları (AttributeError) riskine girmeden font değişir.
        
        new_block = f"""
# --- CONFIG: {lang_code.upper()} ---
# Runtime Font Hooking (Inspired by Zenpy / anonymousException)

init -999 python:
    # Font ayarlarını saklayacağımız global sözlük
    if not hasattr(renpy.store, "renlocalizer_fonts"):
        renpy.store.renlocalizer_fonts = {{}}

    # Orijinal fonksiyonu sadece bir kez yedekle
    if not hasattr(renpy.store, "orig_get_font"):
        try:
            renpy.store.orig_get_font = renpy.text.font.get_font
            
            # KANCA (HOOK) FONKSİYONU
            def renlocalizer_get_font_hook(*args):
                # args[0] normalde istenen font dosyasıdır
                # Eğer şu anki dil bizim hedef dilimizse devreye gir
                
                current_lang = _preferences.language
                font_store = renpy.store.renlocalizer_fonts
                
                # Eğer o dil için bir font tanımlamışsak
                if current_lang in font_store and "Default" in font_store[current_lang]:
                    target_font = font_store[current_lang]["Default"]
                    
                    # Sonsuz döngü koruması: Zaten bizim font isteniyorsa dokunma
                    if args[0] != target_font:
                        # Argümanları değiştir: (EskiFont, Boyut, ...) -> (YeniFont, Boyut, ...)
                        # Tuple olduğu için yeniden oluşturuyoruz
                        args = (target_font,) + args[1:]
                        
                # Orijinal (veya modifiye edilmiş) çağrıyı yap
                return renpy.store.orig_get_font(*args)
                
            # Ren'Py'ın font yükleyicisini değiştir
            renpy.text.font.get_font = renlocalizer_get_font_hook
            
        except Exception as e:
            # Bir şeyler ters giderse konsola yaz ama oyunu çökertme
            print("RenLocalizer Font Hook Error: " + str(e))

translate {lang_code} python:
    # 1. Fontumuzu Hook sistemine kaydet
    if not hasattr(renpy.store, "renlocalizer_fonts"):
        renpy.store.renlocalizer_fonts = {{}}
        
    renpy.store.renlocalizer_fonts["{lang_code}"] = {{
        "Default": "{font_path}"
    }}

    # 2. Standart GUI değişkenlerini de güncelle (Ekstra güvenlik)
    gui.text_font = "{font_path}"
    gui.name_text_font = "{font_path}"
    gui.interface_text_font = "{font_path}"
    gui.button_text_font = "{font_path}"
    gui.choice_button_text_font = "{font_path}"
    
    # 3. Stilleri yeniden oluştur
    style.rebuild()
"""
        # Dosyayı SIFIRDAN oluştur (Eski hatalı kodları temizle)
        with open(rpy_path, 'w', encoding='utf-8') as f:
            f.write(new_block)
            
        return False

    def _normalize_lang_code(self, lang_code: str) -> str:
        """Converts 'turkish' -> 'tr', 'zh-CN' -> 'zh', etc."""
        lower_code = lang_code.lower().strip()
        
        # Check name mapping first (turkish -> tr)
        if lower_code in self.LANG_NAME_TO_CODE:
            return self.LANG_NAME_TO_CODE[lower_code]
            
        # Standard normalization
        base = lower_code.split('-')[0]
        
        # Special cases
        if lower_code in ["zh-cn", "zh_cn", "zh-hans", "schinese"]:
            return "zh"
        elif lower_code in ["zh-tw", "zh_tw", "zh-hant", "tchinese"]:
            return "zh_tw"
            
        return base

    def get_available_fonts(self) -> List[str]:
        """Returns a list of popular Google Fonts for manual selection."""
        # Expanded list covering various styles (Sans, Serif, Display, Handwriting, Mono)
        fonts = [
            # Sans Serif (Clean, Modern, Readable)
            "Roboto", "Open Sans", "Lato", "Montserrat", "Source Sans Pro", "Oswald", 
            "Raleway", "Noto Sans", "Nunito", "Poppins", "Ubuntu", "Quicksand", 
            "Work Sans", "Fira Sans", "Barlow", "Josefin Sans", "Rubik", "Mukta",
            "Kanit", "Heebo", "Libre Franklin", "Cabin", "Karla", "Varela Round",
            "Comfortaa", "Exo 2", "Hind", "Maven Pro", "Assistant", "Oxygen",
            
            # Serif (Classic, Elegant, Book-like)
            "Merriweather", "Playfair Display", "Lora", "PT Serif", "Noto Serif",
            "Libre Baskerville", "Arvo", "Bitter", "Crimson Text", "Josefin Slab",
            "Slabo 27px", "Old Standard TT", "Volkhov", "EB Garamond",
            
            # Display / Decorative (Titles, Stylized, Impactful)
            "Bebas Neue", "Anton", "Fjalla One", "Acme", "Righteous", "Lobster",
            "Patua One", "Fredoka One", "Russo One", "Luckiest Guy", "Titan One",
            "Bangers", "Press Start 2P", "Cinzel", "Abril Fatface", "Alfa Slab One",
            "Passion One", "Francois One", "Changa",
            
            # Handwriting / Script (Casual, Artistic, Diary-like)
            "Pacifico", "Shadows Into Light", "Dancing Script", "Indie Flower",
            "Caveat", "Amatic SC", "Courgette", "Patrick Hand", "Satisfy", "Permanent Marker",
            "Sacramento", "Cookie", "Great Vibes", "Kalam", "Handlee",
            
            # Monospace (Scifi, Terminal, Code)
            "Inconsolata", "Roboto Mono", "Source Code Pro", "Space Mono", "VT323",
            "Share Tech Mono", "Cousine", "Anonymous Pro"
        ]
        return sorted(list(set(fonts)))
