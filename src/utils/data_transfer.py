# -*- coding: utf-8 -*-
"""
Data Transfer Utilities
=======================

Handles Import/Export operations for Glossary and other data structures.
Supports: JSON, Excel (.xlsx), CSV (.csv)
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Union, List

logger = logging.getLogger(__name__)

# Try importing pandas and openpyxl, but don't crash if missing (though they should be installed)
try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("pandas not found. Excel/CSV export might be limited.")

def export_glossary_to_file(glossary_data: Dict[str, str], filepath: str) -> bool:
    """
    Exports dictionary glossary to a file (JSON, XLSX, or CSV).
    
    Args:
        glossary_data: Dictionary of {source: target}
        filepath: Destination file path
    """
    try:
        path = Path(filepath)
        ext = path.suffix.lower()
        
        # Determine format
        if ext == '.json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(glossary_data, f, indent=4, ensure_ascii=False)
            return True
            
        elif ext in ['.xlsx', '.xls', '.csv']:
            if pd is None:
                raise ImportError("Pandas library is required for Excel/CSV export.")
            
            # Convert dict to DataFrame
            df = pd.DataFrame(list(glossary_data.items()), columns=['Source', 'Target'])
            
            if ext == '.csv':
                df.to_csv(path, index=False, encoding='utf-8-sig')
            else: # Excel
                df.to_excel(path, index=False)
            return True
            
        else:
            raise ValueError(f"Unsupported file format: {ext}")
            
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise e

def import_glossary_from_file(filepath: str) -> Dict[str, str]:
    """
    Imports glossary from a file (JSON, XLSX, or CSV).
    Returns a dictionary of {source: target}.
    """
    try:
        path = Path(filepath)
        ext = path.suffix.lower()
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        glossary = {}

        if ext == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                 glossary = json.load(f)
                 
        elif ext in ['.xlsx', '.xls', '.csv']:
            if pd is None:
                raise ImportError("Pandas library is required for Excel/CSV import.")
            
            if ext == '.csv':
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
            
            # Normalize columns
            # Expect 'Source' and 'Target' columns, but be flexible
            cols = [c.lower() for c in df.columns]
            
            source_col = None
            target_col = None
            
            # Finds 'source', 'original', 'key'
            for c in df.columns:
                cl = c.lower()
                if cl in ['source', 'original', 'text', 'id', 'key']:
                    source_col = c
                    break
            
            # Finds 'target', 'translation', 'value', 'translated'
            for c in df.columns:
                cl = c.lower()
                if cl in ['target', 'translation', 'value', 'translated', 'tr']:
                    target_col = c
                    break
                    
            if not source_col:
                # If no header found, assume 1st column is source, 2nd is target (if exists)
                if len(df.columns) >= 1:
                    source_col = df.columns[0]
                else:
                    raise ValueError("Could not identify 'Source' column in file.")
            
            if not target_col and len(df.columns) >= 2:
                target_col = df.columns[1]
            
            # Iterate and fill dict
            for index, row in df.iterrows():
                src = str(row[source_col]).strip() if pd.notna(row[source_col]) else ""
                tgt = str(row[target_col]).strip() if target_col and pd.notna(row[target_col]) else ""
                
                if src:
                    glossary[src] = tgt

        else:
            raise ValueError(f"Unsupported file format: {ext}")
            
        return glossary
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise e
