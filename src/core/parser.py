"""
Simple RenPy Parser - Working Version
"""

import re
import logging
from pathlib import Path
from typing import Set, Union, List
import chardet

class RenPyParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Core dialogue patterns
        self.char_dialog_re = re.compile(r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.narrator_re = re.compile(r'^(?P<indent>\s*)(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:#.*)?$')
        
        # Menu and choice patterns - IMPROVED for conditional choices
        self.menu_choice_re = re.compile(r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:if\s+[^:]+)?\s*:\s*')
        self.menu_title_re = re.compile(r'^\s*menu\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')?:')
        
        # UI element patterns
        self.screen_text_re = re.compile(r'^\s*(?:text|label|tooltip)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.textbutton_re = re.compile(r'^\s*textbutton\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Config and GUI patterns  
        self.config_string_re = re.compile(r'^\s*config\.(?:name|version|about|menu_|window_title|save_name)\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.gui_text_re = re.compile(r'^\s*gui\.(?:text|button|label|title|heading|caption|tooltip|confirm)(?:_[a-z_]*)?(?:\[[^\]]*\])?\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')          # Style property assignments
        self.style_property_re = re.compile(r'^\s*style\s*\.\s*[a-zA-Z_]\w*\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Python expressions with $ prefix
        self.python_renpy_re = re.compile(r'^\s*\$\s+.*?(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # RenPy function calls
        self.renpy_function_re = re.compile(r'^\s*(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Technical terms to exclude
        self.renpy_technical_terms = {
            'left', 'right', 'center', 'top', 'bottom', 'gui', 'config',
            'true', 'false', 'none', 'auto', 'png', 'jpg', 'mp3', 'ogg'
        }
        
    def extract_translatable_text(self, file_path: Union[str, Path]) -> Set[str]:
        """Extract translatable text from a .rpy file."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8')
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
            
            lines = content.splitlines()
            translatable_texts = set()
            
            for line_num, line in enumerate(lines, 1):
                patterns = [
                    self.char_dialog_re,
                    self.narrator_re,
                    self.menu_choice_re,
                    self.menu_title_re,
                    self.screen_text_re,
                    self.textbutton_re,
                    self.config_string_re,
                    self.gui_text_re,
                    self.style_property_re,
                    self.python_renpy_re,
                    self.renpy_function_re
                ]
                
                for pattern in patterns:
                    match = pattern.match(line)
                    if match:
                        for group_name in match.groupdict():
                            if 'quote' in group_name and match.group(group_name):
                                text = self._extract_string_content(match.group(group_name))
                                if text and self.is_meaningful_text(text):
                                    translatable_texts.add(text)
                        break
                        
            return translatable_texts
            
        except Exception as e:
            self.logger.error(f"Error parsing {file_path}: {e}")
            return set()
    
    def _extract_string_content(self, quoted_string: str) -> str:
        """Extract content from a quoted string."""
        if not quoted_string:
            return ""
        
        if quoted_string.startswith('"') and quoted_string.endswith('"'):
            content = quoted_string[1:-1]
        elif quoted_string.startswith("'") and quoted_string.endswith("'"):
            content = quoted_string[1:-1]
        else:
            content = quoted_string
        
        content = content.replace('\\"', '"').replace("\\'", "'")
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        
        return content.strip()
    
    def is_meaningful_text(self, text: str) -> bool:
        """Check if text is meaningful dialogue/story content."""
        if not text or len(text.strip()) < 2:
            return False
        
        text_lower = text.lower().strip()
        
        if text_lower in self.renpy_technical_terms:
            return False
        
        # IMPROVED: Skip technical patterns
        technical_patterns = [
            r'^#[0-9a-fA-F]+$',  # Color codes
            r'\.ttf$',           # Font files
            r'^%s[%\s]*$',       # %s patterns
            r'fps|renderer|ms$', # Performance metrics
            r'^[0-9.]+$',        # Pure numbers
            r'game_menu|sync|input|overlay', # UI technical terms
            r'vertical|horizontal|linear',   # Layout terms
            r'touch_keyboard|subtitle|empty' # More technical terms
        ]
        
        for pattern in technical_patterns:
            if re.search(pattern, text_lower):
                return False
        
        if any(ext in text_lower for ext in ['.png', '.jpg', '.mp3', '.ogg']):
            return False
        
        # Skip pure numbers but allow version numbers (contain dots)
        if re.match(r'^[-+]?\d+$', text.strip()):
            return False
        
        # Allow version-like strings (numbers with dots, e.g., "1.0.0", "2.1")
        if re.match(r'^\d+(?:\.\d+)+$', text.strip()):
            return True
        
        if re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜ]', text) and len(text.strip()) >= 2:
            return True
        
        return False
    
    def determine_text_type(self, text: str, context_line: str = "") -> str:
        """Determine the type of text based on content and context."""
        if not context_line:
            return 'dialogue'
        
        context_lower = context_line.lower()
        
        if 'textbutton' in context_lower:
            return 'button'
        elif 'menu' in context_lower:
            return 'menu'
        elif 'screen' in context_lower:
            return 'ui'
        elif 'config.' in context_lower:
            return 'config'
        elif 'gui.' in context_lower:
            return 'gui'
        elif 'style.' in context_lower:
            return 'style'
        else:
            return 'dialogue'
    
    def parse_directory(self, directory: Union[str, Path]) -> List[dict]:
        """Parse all .rpy files in a directory and return formatted text data."""
        directory = Path(directory)
        results = []
        # Find all .rpy files, ama 'game/tl/' içerenleri hariç tut
        rpy_files = [f for f in directory.glob("**/*.rpy") if "game/tl/" not in str(f).replace('\\', '/')]
        self.logger.info(f"Found {len(rpy_files)} .rpy files in {directory} (excluding game/tl/)")
        for rpy_file in rpy_files:
            try:
                # Extract texts from file
                extracted_texts = self.extract_translatable_text(rpy_file)
                # Read file content to get line numbers
                with open(rpy_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                # Convert to GUI format
                for text in extracted_texts:
                    # Try to find line number and context
                    line_number = 1
                    context = ""
                    character = ""
                    # Search for the text in file lines to get context
                    for i, line in enumerate(lines):
                        if text in line:
                            line_number = i + 1
                            context = line.strip()
                            # Try to extract character name if it's dialogue
                            if '"' in line or "'" in line:
                                char_match = re.match(r'\s*([A-Za-z_]\w*)\s+["\']', line.strip())
                                if char_match:
                                    character = char_match.group(1)
                            break
                    # Determine text type based on context
                    text_type = self.determine_text_type(text, context)
                    text_data = {
                        'text': text,
                        'type': text_type,
                        'file_path': str(rpy_file),
                        'line_number': line_number,
                        'character': character,
                        'context': context
                    }
                    results.append(text_data)
            except Exception as e:
                self.logger.error(f"Error parsing file {rpy_file}: {e}")
        self.logger.info(f"Total extracted texts: {len(results)}")
        return results
    
    def extract_from_directory_parallel(self, directory: Union[str, Path], recursive: bool = True, max_workers: int = 4):
        """Extract texts from all .rpy files in parallel (for compatibility with GUI)."""
        directory = Path(directory)
        results = {}
        # Find all .rpy files, ama 'game/tl/' içerenleri hariç tut
        if recursive:
            rpy_files = [f for f in directory.glob("**/*.rpy") if "game/tl/" not in str(f).replace('\\', '/')]
        else:
            rpy_files = [f for f in directory.glob("*.rpy") if "game/tl/" not in str(f).replace('\\', '/')]
        self.logger.info(f"Found {len(rpy_files)} .rpy files for parallel processing (excluding game/tl/)")
        
        # For now, use sequential processing but return the expected format
        for rpy_file in rpy_files:
            try:
                extracted_texts = self.extract_translatable_text(rpy_file)
                results[rpy_file] = extracted_texts
            except Exception as e:
                self.logger.error(f"Error processing file {rpy_file}: {e}")
                results[rpy_file] = set()
        
        total_texts = sum(len(texts) for texts in results.values())
        self.logger.info(f"Parallel processing completed: {len(results)} files, {total_texts} total texts")
        return results
    
    def preserve_placeholders(self, text: str):
        """
        Preserve placeholders in text during translation.
        Returns tuple of (processed_text, placeholder_map)
        """
        if not text:
            return text, {}
        
        placeholder_map = {}
        processed_text = text
        placeholder_counter = 0
        
        # RenPy variable placeholders like [variable_name]
        renpy_var_pattern = r'\[([^\]]+)\]'
        for match in re.finditer(renpy_var_pattern, text):
            placeholder_id = f"__PLACEHOLDER_{placeholder_counter}__"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # RenPy text tags like {color=#ff0000}, {/color}, {b}, {/b}, etc.
        renpy_tag_pattern = r'\{[^}]*\}'
        for match in re.finditer(renpy_tag_pattern, text):
            placeholder_id = f"__PLACEHOLDER_{placeholder_counter}__"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # Python-style format strings like %(variable)s, %s, %d, etc.
        python_format_pattern = r'%\([^)]+\)[sdif]|%[sdif]'
        for match in re.finditer(python_format_pattern, text):
            placeholder_id = f"__PLACEHOLDER_{placeholder_counter}__"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # Python 3.6+ f-string style placeholders like {variable}
        fstring_pattern = r'\{[^}]+\}'
        for match in re.finditer(fstring_pattern, processed_text):  # Use processed_text to avoid double replacement
            # Skip if already replaced by RenPy tag pattern
            if not match.group(0).startswith('__PLACEHOLDER_'):
                placeholder_id = f"__PLACEHOLDER_{placeholder_counter}__"
                placeholder_map[placeholder_id] = match.group(0)
                processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
                placeholder_counter += 1
        
        return processed_text, placeholder_map
    
    def restore_placeholders(self, translated_text: str, placeholder_map: dict) -> str:
        """
        Restore placeholders in translated text.
        """
        if not translated_text or not placeholder_map:
            return translated_text
        
        restored_text = translated_text
        
        # First try exact match
        for placeholder_id, original_placeholder in placeholder_map.items():
            restored_text = restored_text.replace(placeholder_id, original_placeholder)
        
        # Also try case-insensitive match for different case scenarios
        import re
        for placeholder_id, original_placeholder in placeholder_map.items():
            # Create a case-insensitive pattern
            pattern = re.escape(placeholder_id).replace(r'\_\_PLACEHOLDER\_', r'__[Pp][Ll][Aa][Cc][Ee][Hh][Oo][Ll][Dd][Ee][Rr]_')
            restored_text = re.sub(pattern, original_placeholder, restored_text, flags=re.IGNORECASE)
        
        return restored_text
