"""
RPYMC File Reader for RenLocalizer (v2.6.4).

This module reads compiled Ren'Py screen cache files (.rpymc) and extracts 
translatable text from Screen Language 2 (SL2) structures.

It leverages the robust 'Fake' classes and 'RenpyUnpickler' from rpyc_reader 
to ensure maximum compatibility with Ren'Py 8.5.2 and safe unpickling.
"""
from __future__ import annotations

import io
import zlib
import pickle
import logging
from typing import List, Dict, Any, Generator, Tuple
from pathlib import Path

# Reuse the robust infrastructure from rpyc_reader
from .rpyc_reader import (
    RenpyUnpickler, 
    FakeSLScreen, 
    FakeSLDisplayable, 
    FakeSLIf, 
    FakeSLFor, 
    FakeSLUse,
    FakeSLDrag,
    FakeSLBar,
    FakeASTBase
)

logger = logging.getLogger(__name__)

def extract_text_from_rpymc(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts translatable text from a .rpymc file.
    Returns a list of dicts: {'text': str, 'line': int, 'context': str, 'type': str}
    """
    try:
        data = _read_rpymc_data(file_path)
        if not data:
            return []
            
        # .rpymc usually contains a dict or list of Screen objects
        # We assume the root is a structure containing SLScreen objects
        unpickler = RenpyUnpickler(io.BytesIO(data))
        root_obj = unpickler.load()
        
        extractor = ScreenTextExtractor(file_path)
        extractor.walk(root_obj)
        return extractor.extracted_entries
        
    except Exception as e:
        logger.error(f"Failed to extract from {file_path}: {e}")
        return []

def _read_rpymc_data(file_path: str) -> bytes:
    """Reads and decompresses .rpymc file content."""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            
        if not raw_data.startswith(b'RENPY'):
            return b""
            
        # Zlib stream starts after the header (usually found by 'x' signature or fixed offset)
        # Standard Ren'Py header is "RENPY RPC2" + slots + padding
        # We look for zlib magic bytes (78 9C, 78 01, 78 DA)
        header_end = -1
        for magic in [b'\x78\x9c', b'\x78\x01', b'\x78\xda']:
            idx = raw_data.find(magic)
            if idx != -1:
                header_end = idx
                break
                
        if header_end != -1:
            return zlib.decompress(raw_data[header_end:])
            
        return b""
    except Exception:
        return b""

class ScreenTextExtractor:
    """
    Traverses FakeSL* objects to extract UI text.
    """
    def __init__(self, filename: str):
        self.filename = Path(filename).name
        self.extracted_entries: List[Dict[str, Any]] = []
        
    def walk(self, node: Any, context: str = ""):
        """Recursively walks screen nodes."""
        if node is None:
            return

        # Handle List/Dict containers
        if isinstance(node, (list, tuple)):
            for item in node:
                self.walk(item, context)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                self.walk(value, f"{context}/{key}")
            return
            
        # Process specific SL2 Nodes
        if isinstance(node, FakeSLScreen):
            screen_name = getattr(node, 'name', 'unknown')
            self._scan_children(node, f"screen:{screen_name}")
            
        elif isinstance(node, FakeSLDisplayable):
            # Extract text from positional args (e.g., text "Hello")
            self._extract_from_displayable(node, context)
            self._scan_children(node, context)
            
        elif isinstance(node, (FakeSLIf, FakeSLFor, FakeSLUse)):
            self._scan_children(node, context)
            
        elif isinstance(node, (FakeSLDrag, FakeSLBar)):
             self._extract_from_displayable(node, context)
             self._scan_children(node, context)

        # Handle Action classes (Confirm, Notify, etc.) inside action lists
        elif hasattr(node, '__class__') and node.__class__.__name__ == 'FakeConfirm':
             if hasattr(node, 'prompt') and isinstance(node.prompt, str):
                 self._add_entry(node.prompt, 0, f"{context}/Confirm", "ui_confirm")

        elif hasattr(node, '__class__') and node.__class__.__name__ == 'FakeNotify':
             if hasattr(node, 'message') and isinstance(node.message, str):
                 self._add_entry(node.message, 0, f"{context}/Notify", "ui_notify")

        elif hasattr(node, '__class__') and node.__class__.__name__ == 'FakeTooltip':
             if hasattr(node, 'value') and isinstance(node.value, str):
                 self._add_entry(node.value, 0, f"{context}/Tooltip", "ui_tooltip")

        elif hasattr(node, '__class__') and node.__class__.__name__ == 'FakeHelp':
             if hasattr(node, 'help') and isinstance(node.help, str):
                 self._add_entry(node.help, 0, f"{context}/Help", "ui_help")

    def _scan_children(self, node: Any, context: str):
        """Scans children of a node."""
        children = getattr(node, 'children', [])
        if children:
            self.walk(children, context)
        
        # Also check for 'entries' in SLIf
        entries = getattr(node, 'entries', [])
        if entries:
            for entry in entries:
                # content is usually the second element of the tuple
                if isinstance(entry, (list, tuple)) and len(entry) > 1:
                    self.walk(entry[1], context)

    def _extract_from_displayable(self, node: FakeSLDisplayable, context: str):
        """Extracts text from displayable properties (positional & keywords)."""
        line_num = getattr(node, 'location', (0, 0))[1] if hasattr(node, 'location') else 0
        
        # 1. Positional Arguments (e.g. text "String")
        # In SL2, 'text' displayable often has the string as the first positional arg
        # We need to be careful not to extract code.
        positional = getattr(node, 'positional', [])
        if positional:
             for arg in positional:
                 if isinstance(arg, str) and self._is_translatable_text(arg):
                     self._add_entry(arg, line_num, f"{context}/text", "ui_text")

        # 2. Keyword Arguments (e.g. textbutton "Ok", tooltip "Tip", action=Confirm(...))
        keywords = getattr(node, 'keyword', [])
        for kw in keywords:
            if isinstance(kw, (list, tuple)) and len(kw) == 2:
                key, val = kw
                if key in ('text', 'label', 'caption', 'tooltip', 'alt', 'help', 
                          'hover_text', 'selected_text', 'prefix', 'suffix', 'default',
                          'hint', 'subtitle', 'credits', 'about', 'version_name'):
                    if isinstance(val, str) and self._is_translatable_text(val):
                        self._add_entry(val, line_num, f"{context}/{key}", f"ui_{key}")
                
                # Recurse into complex values (e.g. action=Confirm(...))
                if key in ('action', 'hovered', 'unhovered', 'changed'):
                    self.walk(val, f"{context}/{key}")

    def _is_translatable_text(self, text: str) -> bool:
        """Heuristic to filter out code/variables while keeping UI text."""
        if not text: return False
        
        # 1. Technical prefixes
        if text.startswith(('gui.', 'config.', 'persistent.', 'store.', 'SetVariable')): 
            return False
            
        # 2. Must contain at least one letter (unless it's a whitelisted symbol?)
        # No, allowing symbols is dangerous for code. Requiring letters is safer.
        if not any(c.isalpha() for c in text): 
            return False
            
        # 3. Short string heuristics (The "Yes/No" fix)
        # Old logic: if ' ' not in text and text.islower(): return False
        # New logic: Allow Title Case (Start, Back) or whitelist.
        if ' ' not in text:
            # Block pure lowercase technical ids (e.g. 'vbox', 'style_name')
            # But allow if it's in our standard whitelist or looks like a proper noun
            is_technical = text.islower() and '_' in text # snake_case likely variable
            is_proper = text[0].isupper() and text[1:].islower() # 'Start', 'Back'
            
            # Whitelist for common short UI words
            common_ui = {'on', 'off', 'yes', 'no', 'back', 'skip', 'auto', 'save', 'load', 'help'}
            
            if text.lower() in common_ui:
                return True
                
            if is_technical:
                return False
                
            # If strictly lowercase and not in whitelist -> suspect variable
            if text.islower():
                return False

        return True

    def _add_entry(self, text: str, line: int, context: str, type_: str):
        self.extracted_entries.append({
            'text': text,
            'line': line,
            'context': context,
            'type': type_
        })
