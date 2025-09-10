"""
Output Formatter
===============

Formats translation results into Ren'Py translate block format.
"""

import logging
from typing import List, Dict, Set, TYPE_CHECKING
from pathlib import Path
import re

if TYPE_CHECKING:
    from src.core.translator import TranslationResult

class RenPyOutputFormatter:
    """Formats translations into Ren'Py translate block format."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sanitize_translation_id(self, text: str) -> str:
        """Create a valid Ren'Py translation ID from text."""
        # Remove special characters and replace with underscores
        text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
        
        # Remove multiple underscores
        text = re.sub(r'_+', '_', text)
        
        # Remove leading/trailing underscores
        text = text.strip('_')
        
        # Ensure it starts with a letter or underscore
        if text and text[0].isdigit():
            text = '_' + text
        
        # Limit length
        if len(text) > 50:
            text = text[:50]
        
        # Ensure it's not empty
        if not text:
            text = 'translated_text'
        
        return text
    
    def escape_renpy_string(self, text: str) -> str:
        """Escape special characters for Ren'Py strings."""
        # More careful escaping to avoid breaking translations
        # CRITICAL: Don't break Ren'Py variables and placeholders
        
        # First, temporarily protect Ren'Py variables and expressions
        import re
        
        # Find all Ren'Py variables [variable] and expressions
        variable_pattern = re.compile(r'\[[^\[\]]+\]')
        variables = variable_pattern.findall(text)
        
        # Replace variables with placeholders temporarily
        temp_text = text
        var_map = {}
        for i, var in enumerate(variables):
            placeholder = f"__VAR_{i}__"
            var_map[placeholder] = var
            temp_text = temp_text.replace(var, placeholder, 1)
        
        # Now escape the rest
        temp_text = temp_text.replace('\\', '\\\\')  # Escape backslashes first
        temp_text = temp_text.replace('"', '\\"')     # Escape double quotes
        
        # Restore variables
        for placeholder, original_var in var_map.items():
            temp_text = temp_text.replace(placeholder, original_var)
        
        return temp_text
    
    def generate_translation_block(self, 
                                 original_text: str, 
                                 translated_text: str, 
                                 language_code: str,
                                 translation_id: str = None,
                                 context: str = None,
                                 mode: str = "simple") -> str:
        """Generate a single translation block."""
        
        if not translation_id:
            # Create string-based translation that matches any label
            # This is more compatible with existing Ren'Py games
            import hashlib
            text_hash = hashlib.md5(original_text.encode('utf-8')).hexdigest()[:8]
            translation_id = f"strings_{text_hash}"
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # Old/new format - better for existing games but requires exact match
            block = (
                f"translate {language_code} strings:\n"
                f"    old \"{escaped_original}\"\n"
                f"    new \"{escaped_translated}\"\n\n"
            )
        else:
            # Standard string translation that works with any label
            block = f'''translate {language_code} strings:
    old "{escaped_original}"
    new "{escaped_translated}"

'''
        
        return block
    
    def generate_character_translation(self,
                                     character_name: str,
                                     original_text: str,
                                     translated_text: str,
                                     language_code: str,
                                     translation_id: str = None,
                                     mode: str = "simple") -> str:
        """Generate a character dialogue translation block."""
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # String-based format that works with any character dialogue
            block = (
                f"translate {language_code} strings:\n"
                f"    old {character_name} \"{escaped_original}\"\n"
                f"    new {character_name} \"{escaped_translated}\"\n\n"
            )
        else:
            # Also use string-based format for consistency
            block = f'''translate {language_code} strings:
    old {character_name} "{escaped_original}"
    new {character_name} "{escaped_translated}"

'''
        
        return block
    
    def generate_menu_translation(self,
                                menu_options: List[Dict],
                                language_code: str,
                                menu_id: str = None) -> str:
        """Generate menu translation block."""
        
        if not menu_id:
            menu_id = f"menu_{self.sanitize_translation_id('_'.join([opt['original'] for opt in menu_options[:3]]))}"
        
        # IMPORTANT: Previously we used escaped newline sequences ("\\n") which
        # produced *literal* backslash-n characters in the output file (e.g. "\ntranslate ...")
        # breaking Ren'Py parsing. We now use real newlines.
        block = f"translate {language_code} {menu_id}:\n\n"
        
        for i, option in enumerate(menu_options):
            original = self.escape_renpy_string(option['original'])
            translated = self.escape_renpy_string(option['translated'])
            # Add each choice with real newlines
            block += f'    # "{original}"\n'
            block += f'    "{translated}": # Choice {i+1}\n'
        
        block += "\n"
        return block
    
    def format_translation_file(self,
                              translation_results: List,
                              language_code: str,
                              source_file: Path = None,
                              include_header: bool = True,
                              output_format: str = "old_new") -> str:
        """Format complete translation file."""
        
        output_lines = []
        
        if include_header:
            header = self.generate_file_header(language_code, source_file)
            output_lines.append(header)
        
        # For string-based translations, we need one big strings block
        if output_format == "old_new":
            output_lines.append(f"translate {language_code} strings:")
            output_lines.append("")
            
            seen_translations = set()
            
            for result in translation_results:
                if not result.success or not result.translated_text:
                    continue
                
                # Avoid duplicates
                key = f"{result.original_text}_{result.translated_text}"
                if key in seen_translations:
                    continue
                seen_translations.add(key)
                
                escaped_original = self.escape_renpy_string(result.original_text)
                escaped_translated = self.escape_renpy_string(result.translated_text)
                
                # Check if it's character dialogue
                character = result.metadata.get('character')
                if character and character.strip():
                    output_lines.append(f'    old {character} "{escaped_original}"')
                    output_lines.append(f'    new {character} "{escaped_translated}"')
                else:
                    output_lines.append(f'    old "{escaped_original}"')
                    output_lines.append(f'    new "{escaped_translated}"')
                
                output_lines.append("")  # Empty line between translations
        
        else:
            # Standard format - keep existing logic
            dialogue_translations = []
            other_translations = []
            
            seen_translations = set()
            
            for result in translation_results:
                if not result.success or not result.translated_text:
                    continue
                
                # Avoid duplicates
                key = f"{result.original_text}_{result.translated_text}"
                if key in seen_translations:
                    continue
                seen_translations.add(key)
                
                # Determine translation type from metadata
                text_type = result.metadata.get('type', 'other')
                character = result.metadata.get('character')
                context = result.metadata.get('context', '')
                
                if text_type == 'dialogue' and character:
                    dialogue_translations.append({
                        'character': character,
                        'original': result.original_text,
                        'translated': result.translated_text,
                        'context': context
                    })
                else:
                    other_translations.append({
                        'original': result.original_text,
                        'translated': result.translated_text,
                        'context': context,
                        'type': text_type
                    })
            
            # Generate dialogue translations
            if dialogue_translations:
                output_lines.append("# Character Dialogue Translations")
                output_lines.append("")
                
                for trans in dialogue_translations:
                    block = self.generate_character_translation(
                        trans['character'],
                        trans['original'],
                        trans['translated'],
                        language_code,
                        mode=output_format
                    )
                    output_lines.append(block)
            
            # Generate other translations
            if other_translations:
                output_lines.append("# Other Text Translations")
                output_lines.append("")
                
                for trans in other_translations:
                    translation_id = None
                    if trans['type'] in ['textbutton', 'screen_text', 'text_action']:
                        translation_id = f"{trans['type']}_{self.sanitize_translation_id(trans['original'])}"
                    
                    block = self.generate_translation_block(
                        trans['original'],
                        trans['translated'],
                        language_code,
                        translation_id,
                        trans['context'],
                        mode=output_format
                    )
                    output_lines.append(block)
        
        # Join sections with real newlines
        return "\n".join(output_lines)
    
    def generate_file_header(self, language_code: str, source_file: Path = None) -> str:
        """Generate file header with metadata."""
        from datetime import datetime
        
        header = f"""# Ren'Py Translation File
# Language: {language_code}
# Generated by: RenLocalizer V2
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if source_file:
            header += f"# Source file: {source_file}\\n"
        
        header += """
# This file contains automatic translations.
# Please review and edit as needed.

"""
        return header
    
    def save_translation_file(self,
                            translation_results: List,
                            output_path: Path,
                            language_code: str,
                            source_file: Path = None,
                            output_format: str = "simple") -> bool:
        """Save translations to file."""
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate content
            content = self.format_translation_file(
                translation_results,
                language_code,
                source_file,
                output_format=output_format
            )
            
            # Write file with UTF-8 encoding
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Saved translation file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving translation file {output_path}: {e}")
            return False
    
    def organize_output_files(self,
                            translation_results: List,
                            output_base_dir: Path,
                            language_code: str,
                            source_files: List[Path] = None,
                            output_format: str = "old_new",
                            create_renpy_structure: bool = True) -> List[Path]:
        """Organize translations into language-specific directories."""
        
        output_files = []
        
        # Determine if this is a Ren'Py project and create proper structure
        if create_renpy_structure:
            # Check if we're in a Ren'Py project (has game folder)
            game_dir = self._find_game_directory(output_base_dir)
            if game_dir:
                # Create Ren'Py translation structure: game/tl/[language]/
                lang_dir = game_dir / "tl" / language_code
                self.logger.info(f"Creating Ren'Py translation structure: {lang_dir}")
                
                # Create language initialization file for Ren'Py - do it immediately
                self._create_language_init_file(game_dir, language_code)
            else:
                # Not a Ren'Py project, create standard structure
                lang_dir = output_base_dir / language_code
                self.logger.info(f"Creating standard translation structure: {lang_dir}")
        else:
            # Create language directory
            lang_dir = output_base_dir / language_code
        
        lang_dir.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL FIX: Create ONE translation file for all strings
        # This prevents duplicate string errors in Ren'Py
        
        # Global deduplication - remove duplicates across ALL files
        seen_strings = set()
        unique_results = []
        
        for result in translation_results:
            string_key = result.original_text.strip().lower()
            if string_key not in seen_strings:
                seen_strings.add(string_key)
                unique_results.append(result)
            else:
                self.logger.debug(f"Skipping duplicate string: {result.original_text[:50]}...")
        
        # Create single master translation file
        output_filename = f"translations_{language_code}.rpy"
        output_path = lang_dir / output_filename
        
        if self.save_translation_file(
            unique_results, 
            output_path, 
            language_code, 
            None,  # No specific source file
            output_format=output_format
        ):
            output_files.append(output_path)
            self.logger.info(f"Created master translation file: {output_path} with {len(unique_results)} unique strings")
        
        return output_files
    
    def _find_game_directory(self, base_path: Path) -> Path:
        """Find the game directory in a Ren'Py project."""
        # Check current directory and parent directories for 'game' folder
        current = Path(base_path).resolve()
        
        # Check if current path contains 'game' folder
        if (current / "game").exists() and (current / "game").is_dir():
            return current / "game"
        
        # Check parent directories
        for parent in current.parents:
            game_dir = parent / "game"
            if game_dir.exists() and game_dir.is_dir():
                # Verify it's a Ren'Py game directory by checking for common files
                if any((game_dir / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
                    return game_dir
        
        # Check if current directory itself is the game directory
        if any((current / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
            return current
        
        return None
    
    def _create_language_init_file(self, game_dir: Path, language_code: str):
        """Create language initialization file for Ren'Py (Correct Version)."""
        try:
            # Language display names
            language_names = {
                'tr': 'Türkçe',
                'en': 'English',
                'es': 'Español',
                'fr': 'Français',
                'de': 'Deutsch',
                'it': 'Italiano',
                'pt': 'Português',
                'ru': 'Русский',
                'ja': '日本語',
                'ko': '한국어',
                'zh': '中文',
                'ar': 'العربية'
            }
            
            display_name = language_names.get(language_code, language_code.upper())
            
            # Create simple, working language file
            init_file_path = game_dir / f"a0_{language_code}_language.rpy"
            
            # Simple and reliable language setup
            init_content = f'''# Language Configuration for {display_name}
# Generated by RenLocalizer V2

# Simple language setup without deprecated functions
init -100 python:
    # Set language directly
    config.language = "{language_code}"
    
    # Store in persistent data
    try:
        if hasattr(renpy.store, 'persistent'):
            persistent.language = "{language_code}"
    except:
        pass
    
    print("🌐 Language set to: {display_name} ({language_code})")

# Default persistent language
default persistent.language = "{language_code}"

# Apply language when game starts
init python:
    # Set language immediately
    config.language = "{language_code}"
    
    # Try to change language (may not be needed in newer Ren'Py)
    try:
        renpy.change_language("{language_code}")
    except:
        # If change_language doesn't work, that's fine
        # Just setting config.language should be enough
        pass

'''
            
            with open(init_file_path, 'w', encoding='utf-8') as f:
                f.write(init_content)
            
            self.logger.info(f"Created simple language file: {init_file_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating language init file: {e}")
