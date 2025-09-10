"""
RenPy Script Parser Module - Fixed Version

This module provides functionality to parse Ren'Py script files (.rpy) and
extract translatable text content for localization purposes.
"""

import re
import logging
import tokenize
import io
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Set, Union, Dict, List, Tuple
import chardet

# Set up logger
logger = logging.getLogger(__name__)

class RenPyParser:
    """Parser for Ren'Py script files to extract translatable text."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # We'll implement a pipeline-based extraction using categorized regex sets.
        # The patterns below follow the multi-stage strategy provided by the user.

        # String literal finder (keeps escapes)
        self.string_literal_re = re.compile(r'(["\'])(?P<inner>(?:\\.|(?!\1).)*)\1')

        # Masks to protect tags and placeholders
        self.text_tag_re = re.compile(r'\{/?[a-zA-Z][^}]*\}')
        self.placeholder_re = re.compile(r'\[[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\]')
        self.percent_format_re = re.compile(r'%(?:\([^)]+\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%]')
        self.brace_format_re = re.compile(r'\{[^{}]+\}')

        # Core category regexes (single-line heuristics)
        self.char_dialog_re = re.compile(r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?P<trail>\s+(id\s+"[^"]*")?)?\s*(?:#.*)?$')
        self.narrator_re = re.compile(r'^(?P<indent>\s*)(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:#.*)?$')
        self.menu_choice_re = re.compile(r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*:\s*(?:#.*)?$')
        self.screen_text_re = re.compile(r'^\s*(?:text|label|tooltip)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:#.*)?$')
        self.textbutton_re = re.compile(r'^\s*textbutton\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\b')
        self.define_character_re = re.compile(r'^\s*define\s+[A-Za-z_]\w*\s*=\s*Character\([^#\n]*?(?P<charname>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')

        # Localization calls inside Python
        self.underscore_call_re = re.compile(r'_\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)')
        self.ngettext_call_re = re.compile(r'ngettext\(\s*(?P<quote1>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*,\s*(?P<quote2>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.pgettext_call_re = re.compile(r'pgettext\(\s*(?P<ctx>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*,\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')

        # Blocks to detect and keep context for (translate, python, init python, menu, screen)
        self.block_start_re = re.compile(r'^(?P<indent>\s*)(?P<kw>translate|python|init\s+python|menu|screen|label|transform)\b')

        # Ren'Py specific technical terms that should never be translated
        self.renpy_technical_terms = {
            # Position/alignment keywords
            'left', 'right', 'center', 'centre', 'top', 'bottom', 'middle',
            'truecenter', 'topleft', 'topright', 'bottomleft', 'bottomright',
            
            # Transform/animation keywords  
            'linear', 'ease', 'easein', 'easeout', 'easeinout', 'bounce', 'elastic',
            'alpha', 'rotate', 'zoom', 'xalign', 'yalign', 'xpos', 'ypos', 'xanchor', 'yanchor',
            'xsize', 'ysize', 'xysize', 'xzoom', 'yzoom', 'xrotate', 'yrotate', 'zrotate',
            
            # Display/UI keywords
            'dissolve', 'fade', 'pixellate', 'move', 'slideupleft', 'slideupright',
            'slidedownleft', 'slidedownright', 'slideleft', 'slideright', 'slideup', 'slidedown',
            'irisin', 'irisout', 'blinds', 'squares', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
            
            # Technical identifiers
            'gui', 'config', 'define', 'default', 'persistent', 'preferences', 'renpy',
            'store', 'character', 'narrator', 'extend', 'nvl', 'clear', 'pause',
            
            # File/path related
            'images', 'audio', 'music', 'sound', 'video', 'fonts', 'archive', 'saves',
            
            # Technical single words that might appear as dialogue but shouldn't be translated
            'hair1', 'hair2', 'hair3', 'outfit1', 'outfit2', 'background1', 'background2',
            'sprite1', 'sprite2', 'expression1', 'expression2', 'pose1', 'pose2',
            'variant1', 'variant2', 'state1', 'state2', 'mode1', 'mode2',
            'timecircle', 'fasttravelbackground', 'scrollbar', 'update', 'hidden', 'description',
            
            # Archive/build related
            'all.zip', 'market.zip', 'win.zip', 'mac.zip', 'linux.zip',
            
            # Common technical words
            'true', 'false', 'none', 'null', 'void', 'auto', 'manual', 'normal', 'repeat',
            'hover', 'idle', 'selected', 'focused', 'disabled', 'insensitive',
            
            # File format/extension indicators
            'png', 'jpg', 'jpeg', 'gif', 'webp', 'ogg', 'mp3', 'wav', 'mp4', 'webm', 'ttf', 'otf'
        }
        
        # Placeholders patterns (used for preserve_placeholders)
        # CRITICAL: Case-sensitive placeholder preservation
        self.placeholder_patterns = [
            self.text_tag_re,
            self.placeholder_re,
            self.percent_format_re,
            self.brace_format_re,
            re.compile(r'\([^)]+\)'),  # (expressions) - conservative
        ]
        
        # Enhanced placeholder preservation for Ren'Py variables
        self.renpy_variable_re = re.compile(r'\[[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\]')
        self.renpy_expression_re = re.compile(r'\[([^\[\]]+)\]')  # [any expression]
    
    def extract_strings_with_tokenize(self, line: str) -> List[str]:
        """
        Extract string literals from a line using Python tokenize for safety.
        This handles escaped quotes, multi-line strings, and complex cases better than regex.
        """
        strings = []
        try:
            # Wrap the line to make it tokenize-friendly
            line_bytes = line.encode('utf-8')
            tokens = tokenize.tokenize(io.BytesIO(line_bytes).readline)
            
            for tok in tokens:
                if tok.type == tokenize.STRING:
                    # tok.string includes quotes, we want the inner content
                    raw_string = tok.string
                    # Handle different quote styles: "...", '...', """...""", '''...'''
                    if raw_string.startswith('"""') or raw_string.startswith("'''"):
                        inner = raw_string[3:-3]
                    elif raw_string.startswith('"') or raw_string.startswith("'"):
                        inner = raw_string[1:-1]
                    else:
                        inner = raw_string
                    
                    # Decode escape sequences properly
                    try:
                        decoded = inner.encode('utf-8').decode('unicode_escape')
                        strings.append(decoded)
                    except (UnicodeDecodeError, UnicodeError):
                        # Fallback to raw string if decoding fails
                        strings.append(inner)
                        
        except (tokenize.TokenError, UnicodeDecodeError):
            # Fallback to regex method if tokenize fails
            matches = self.string_literal_re.finditer(line)
            for match in matches:
                strings.append(match.group('inner'))
                
        return strings
    
    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                confidence = result.get('confidence', 0)
                
                if confidence < 0.7:
                    # Try common encodings for Ren'Py files
                    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
                        try:
                            raw_data.decode(enc)
                            encoding = enc
                            break
                        except UnicodeDecodeError:
                            continue
                
                self.logger.debug(f"Detected encoding for {file_path}: {encoding} (confidence: {confidence})")
                return encoding
                
        except Exception as e:
            self.logger.warning(f"Error detecting encoding for {file_path}: {e}")
            return 'utf-8'
    
    def extract_translatable_text(self, file_path: Union[str, Path]) -> Set[str]:
        """
        Extract translatable text from a .rpy file.
        
        Args:
            file_path: Path to the .rpy file
            
        Returns:
            Set of translatable text strings
        """
        translatable_texts: Set[str] = set()
        file_path = Path(file_path)

        if not file_path.exists():
            self.logger.warning(f"File not found: {file_path}")
            return translatable_texts

        encoding = self.detect_encoding(file_path)

        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()

            current_block = None
            block_indent = None

            for line_num, raw_line in enumerate(lines, 1):
                line = raw_line.rstrip('\n')
                stripped = line.lstrip()
                indent = len(line) - len(stripped)

                # Detect block starts (translate, python, init python, menu, screen, label, transform)
                m = self.block_start_re.match(stripped)
                if m:
                    kw = m.group('kw')
                    current_block = kw
                    block_indent = indent

                    # If translate block, we skip old/new lines (they are handled separately)
                    if kw == 'translate':
                        continue

                # If we have left a block due to dedent, reset
                if current_block and indent <= (block_indent or 0) and not stripped.startswith('#'):
                    # end of indented block
                    current_block = None
                    block_indent = None

                # Handle translate block special lines
                if current_block == 'translate':
                    # If user wants source collection, they can enable extracting old "..." lines
                    if stripped.strip().startswith('old '):
                        # old "..." contains source string, extract it
                        q = self.string_literal_re.search(stripped)
                        if q:
                            inner = q.group('inner')
                            if self.is_meaningful_text(inner):
                                translatable_texts.add(inner)
                    # skip new lines and others
                    continue

                # Python blocks: only accept _('...') / ngettext / pgettext
                if current_block in ('python', 'init python'):
                    # Use tokenize-based extraction for better safety
                    line_strings = self.extract_strings_with_tokenize(line)
                    
                    for um in self.underscore_call_re.finditer(line):
                        # Try to match extracted strings with regex positions
                        quote_text = um.group('quote')
                        inner = quote_text[1:-1]  # Remove quotes
                        processed, _ = self.preserve_placeholders(inner)
                        if self.is_meaningful_text(processed):
                            translatable_texts.add(inner)
                    
                    for nm in self.ngettext_call_re.finditer(line):
                        q1 = nm.group('quote1')
                        q2 = nm.group('quote2')
                        inner1 = q1[1:-1]
                        inner2 = q2[1:-1]
                        if self.is_meaningful_text(inner1):
                            translatable_texts.add(inner1)
                        if self.is_meaningful_text(inner2):
                            translatable_texts.add(inner2)
                    
                    for pm in self.pgettext_call_re.finditer(line):
                        q = pm.group('quote')
                        inner = q[1:-1]
                        if self.is_meaningful_text(inner):
                            translatable_texts.add(inner)
                    continue

                # Not a python/translate block: try to match dialogue/screen/menu patterns
                for pat in (self.char_dialog_re, self.narrator_re, self.menu_choice_re, self.screen_text_re, self.textbutton_re, self.define_character_re):
                    m = pat.match(stripped)
                    if not m:
                        continue

                    # Extract quoted parts using tokenize for better accuracy
                    line_strings = self.extract_strings_with_tokenize(stripped)
                    
                    # Also try regex approach as fallback
                    quote = m.groupdict().get('quote') or m.groupdict().get('charname')
                    if quote:
                        # remove surrounding quotes
                        inner = quote[1:-1]
                        if inner not in line_strings:
                            line_strings.append(inner)
                    
                    # Process all extracted strings
                    for inner in line_strings:
                        # mask placeholders/tags before meaningfulness check
                        processed, _ = self.preserve_placeholders(inner)
                        # filter out tag-only or placeholder-only strings
                        if re.fullmatch(r'(?:\s*(?:' + self.text_tag_re.pattern + r'|' + self.placeholder_re.pattern + r'))+\s*', inner):
                            continue

                        if self.is_meaningful_text(processed):
                            translatable_texts.add(inner)

            self.logger.info(f"Extracted {len(translatable_texts)} translatable texts from {file_path}")

        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")

        return translatable_texts
    
    def is_meaningful_text(self, text: str) -> bool:
        """Check if text is meaningful dialogue/story content, not code."""
        if not text or len(text) < 3:
            return False
        
        # Skip file paths (contains / or \ and file extensions)
        if ('/' in text or '\\' in text) and ('.' in text):
            if any(ext in text.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.rpy', '.rpyc', '.ttf', '.otf', '.mp3', '.wav', '.ogg']):
                return False
        
        # Skip paths that look like file/directory paths
        if text.count('/') > 0 or text.count('\\') > 0:
            return False
        
        # Skip if contains common file/path separators and extensions
        if '.' in text and any(text.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.rpy', '.rpyc', '.ttf', '.otf', '.mp3', '.wav', '.ogg']):
            return False
        
        # Skip very short technical terms
        if len(text) < 5 and text.lower() in ['yes', 'no', 'ok', 'auto', 'skip', 'save', 'load', 'menu', 'back', 'next', 'prev']:
            return False
        
        # Skip short phrases that are likely technical or character actions
        if len(text) <= 10:
            lower_text = text.lower().strip()
            # Character actions that shouldn't be translated
            technical_short_phrases = {
                'emily lick', 'emily suck', 'emily kiss', 'hair lick', 'character pose',
                'sprite move', 'audio play', 'music stop', 'scene show', 'image hide',
                'menu show', 'gui hide', 'screen open', 'dialog box', 'text box'
            }
            if lower_text in technical_short_phrases:
                return False
        
        # Skip single words that are likely variable names or technical terms
        words = text.split()
        if len(words) == 1:
            word = words[0].lower()
            
            # Check against Ren'Py technical terms
            if word in self.renpy_technical_terms:
                return False
            
            # Extended GUI/technical terms to skip
            technical_terms = {
                'navigation', 'bubble', 'choice', 'window', 'frame', 'button', 'text', 'image',
                'screen', 'style', 'transform', 'action', 'return', 'menu', 'config', 'gui',
                'save_page_prev', 'bottom_right', 'confirm_prompt', 'vertical', 'return_button',
                'window_top_padding', 'game_menu_content_frame', 'preferences', 'about', 'help',
                'load', 'save', 'auto', 'skip', 'history', 'settings', 'overlay', 'confirm',
                'phone', 'nvl', 'textbox', 'thought', 'dialogue', 'main_menu', 'game_menu',
                'quick_menu', 'navigation', 'say_dialogue', 'input_prompt', 'choice_button',
                'page_label', 'slot_button', 'file_slots', 'preferences_frame', 'bar', 'vbar',
                'hbar', 'slider', 'viewport', 'side', 'label', 'spacing', 'xalign', 'yalign',
                # Archive names from the screenshot
                'all.zip', 'market.zip', 'win.zip', 'emily',
                # Character states and technical identifiers
                'reset', 'font', 'line', 'spacing', 'say-condition-false', 'does', 'the', 'lick'
            }
            if word in technical_terms:
                return False
            
            # Skip if it looks like a variable name (contains numbers or underscores)
            if any(char.isdigit() or char == '_' for char in word):
                return False
        
        # Skip text that's mostly technical (contains many underscores, numbers, or special chars)
        technical_chars = text.count('_') + text.count('-') + text.count('.')
        if technical_chars > len(text) * 0.3:  # More than 30% technical characters
            return False
        
        # Skip if it looks like code or file references
        if any(term in text.lower() for term in ['accessibility', 'action_file', 'build.rpy', 'barvalues']):
            return False
        
        # Must contain at least one letter (not just numbers/symbols)
        if not any(c.isalpha() for c in text):
            return False
        
        # Skip if it contains Ren'Py tags or brackets
        if '{' in text and '}' in text:
            return False
        if '[' in text and ']' in text:
            return False
        
        # Skip pure numbers or technical codes
        if text.isdigit():
            return False
        
        # Additional meaningful content checks
        # Must have at least some actual words (not just technical terms)
        words = text.split()
        if len(words) > 1:
            # For multi-word text, check if it contains technical terms as complete words
            lower_text = ' ' + text.lower() + ' '
            for term in self.renpy_technical_terms:
                # Only filter if the technical term appears as a complete word
                if ' ' + term + ' ' in lower_text and len(words) <= 3:
                    return False
            
            meaningful_words = 0
            for word in words:
                word_lower = word.lower().strip('.,!?;:"')
                if len(word_lower) > 2 and word_lower not in self.renpy_technical_terms:
                    if not any(char.isdigit() or char in '_-.' for char in word_lower):
                        meaningful_words += 1
            
            # At least 50% of words should be meaningful
            if meaningful_words < len(words) * 0.5:
                return False
        
        return True
    
    def scan_directory(self, directory: Union[str, Path], recursive: bool = True) -> List[Path]:
        """
        Scan directory for .rpy files, excluding translation directories.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            List of .rpy file paths (excluding files in tl/ subdirectories)
        """
        directory = Path(directory)
        files = []
        
        if not directory.exists():
            self.logger.warning(f"Directory not found: {directory}")
            return files
        
        try:
            if recursive:
                all_files = list(directory.rglob("*.rpy"))
            else:
                all_files = list(directory.glob("*.rpy"))
            
            # Filter out files in translation directories
            for file_path in all_files:
                # Skip files in any 'tl' directory or subdirectory
                path_parts = file_path.parts
                if 'tl' in path_parts:
                    self.logger.debug(f"Skipping translation file: {file_path}")
                    continue
                
                files.append(file_path)
            
            self.logger.info(f"Found {len(files)} .rpy files in {directory} (excluded {len(all_files) - len(files)} translation files)")
            
        except Exception as e:
            self.logger.error(f"Error scanning directory {directory}: {e}")
        
        return files
    
    def extract_from_directory(self, directory: Union[str, Path], recursive: bool = True) -> Dict[Path, Set[str]]:
        """
        Extract translatable text from all .rpy files in a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            Dictionary mapping file paths to sets of translatable text
        """
        results = {}
        files = self.scan_directory(directory, recursive)
        
        for file_path in files:
            try:
                texts = self.extract_translatable_text(file_path)
                if texts:
                    results[file_path] = texts
                    self.logger.debug(f"Extracted {len(texts)} texts from {file_path}")
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}")

        return results
    
    async def extract_translatable_text_async(self, file_path: Union[str, Path]) -> Set[str]:
        """
        Asynchronously extract translatable text from a .rpy file.
        Useful for large files to avoid blocking the main thread.
        """
        loop = asyncio.get_event_loop()
        
        # Run the blocking operation in a thread pool
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.extract_translatable_text, file_path)
            return await loop.run_in_executor(None, lambda: future.result())
    
    def extract_from_directory_parallel(self, directory: Union[str, Path], 
                                      recursive: bool = True, 
                                      max_workers: int = 4) -> Dict[Path, Set[str]]:
        """
        Extract translatable text from all .rpy files in a directory using parallel processing.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            max_workers: Maximum number of worker threads
            
        Returns:
            Dictionary mapping file paths to sets of translatable text
        """
        results = {}
        files = self.scan_directory(directory, recursive)
        
        if not files:
            return results
        
        self.logger.info(f"Processing {len(files)} files with {max_workers} workers")
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all file processing tasks
            future_to_file = {
                executor.submit(self.extract_translatable_text, file_path): file_path 
                for file_path in files
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    texts = future.result()
                    if texts:
                        results[file_path] = texts
                        self.logger.debug(f"Extracted {len(texts)} texts from {file_path}")
                except Exception as e:
                    self.logger.error(f"Error processing file {file_path}: {e}")
        
        self.logger.info(f"Parallel processing completed: {len(results)} files processed")
        return results
    
    async def extract_from_directory_async(self, directory: Union[str, Path], 
                                         recursive: bool = True,
                                         max_workers: int = 4) -> Dict[Path, Set[str]]:
        """
        Asynchronously extract translatable text from all .rpy files in a directory.
        Combines async with parallel processing for optimal performance.
        """
        loop = asyncio.get_event_loop()
        
        # Run the parallel extraction in a separate thread to avoid blocking
        return await loop.run_in_executor(
            None, 
            self.extract_from_directory_parallel,
            directory, 
            recursive, 
            max_workers
        )
    
    def preserve_placeholders(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Replace placeholders with temporary markers and return mapping.
        This preserves Ren'Py variables, format strings, etc.
        CRITICAL: Preserves exact case and formatting
        """
        placeholder_map = {}
        processed_text = text
        placeholder_counter = 0
        
        # Enhanced patterns including Ren'Py specific ones
        all_patterns = self.placeholder_patterns + [
            self.renpy_variable_re,
            self.renpy_expression_re
        ]
        
        for pattern in all_patterns:
            # Use finditer to preserve order and avoid conflicts
            matches = list(pattern.finditer(processed_text))
            for match in reversed(matches):  # Reverse to maintain positions
                placeholder = match.group(0)
                marker = f"__PLACEHOLDER_{placeholder_counter}__"
                placeholder_map[marker] = placeholder
                
                # Replace from end to start to maintain positions
                start, end = match.span()
                processed_text = processed_text[:start] + marker + processed_text[end:]
                placeholder_counter += 1
        
        return processed_text, placeholder_map
    
    def restore_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """
        Restore placeholders in translated text.
        CRITICAL: Case-insensitive restoration to handle translation engine case changes
        """
        result = text
        
        # First try exact match
        for marker, original in placeholder_map.items():
            result = result.replace(marker, original)
        
        # Then try case-insensitive match for remaining placeholders
        import re
        for marker, original in placeholder_map.items():
            # Handle various case and spacing variations that translation engines might introduce
            marker_variations = [
                marker.lower(),
                marker.upper(), 
                marker.capitalize(),
                marker.replace('PLACEHOLDER', 'placeholder'),
                marker.replace('PLACEHOLDER', 'Placeholder'),
                # Handle spacing issues like "__placeholder_1 __" → "__placeholder_1__"
                marker.replace('_', r'\s*_\s*'),  
            ]
            
            for variant in marker_variations:
                if variant != marker:  # Don't repeat exact match
                    # Create flexible pattern
                    pattern = re.escape(variant)
                    pattern = pattern.replace(r'\s\*\_\s\*', r'\s*_\s*')  # Fix regex escape
                    
                    if variant in result:
                        result = result.replace(variant, original)
                        break  # Found and replaced, move to next marker
            
            # Finally, use regex for complex cases
            # Match placeholder with optional whitespace variations
            pattern = r'__\s*(?i:placeholder)\s*_\s*(\d+)\s*__'
            marker_num = marker.split('_')[-2] if '_' in marker else '0'
            
            def replacement_func(match):
                if match.group(1) == marker_num:
                    return original
                return match.group(0)  # Keep unchanged if not matching number
            
            result = re.sub(pattern, replacement_func, result)
        
        return result
    
    def parse_directory(self, directory: Union[str, Path]) -> List[Dict]:
        """
        Parse directory and return extracted texts in the format expected by MainWindow.
        
        Args:
            directory: Directory to parse
            
        Returns:
            List of dictionaries with text data in MainWindow format
        """
        results = []
        extracted_data = self.extract_from_directory(directory)
        
        for file_path, texts in extracted_data.items():
            for text in texts:
                text_data = {
                    'text': text,
                    'type': 'dialogue',  # Default type
                    'file_path': str(file_path),
                    'line_number': 1,  # We could enhance this later to track actual line numbers
                    'character': '',   # Could be enhanced to extract character names
                    'context': ''      # Additional context if needed
                }
                results.append(text_data)
        
        self.logger.info(f"Parsed directory: {len(results)} translatable texts from {len(extracted_data)} files")
        return results
