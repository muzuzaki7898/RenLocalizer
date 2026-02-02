# -*- coding: utf-8 -*-
"""
Hassas Veri Maskeleme ve Güvenli Loglama Modülü
===============================================
API anahtarlarını ve hassas verileri loglara yazılmadan önce maskeler.
"""

import logging
import re
from typing import Optional

# Maskelenecek desenler
MASKS = [
    (re.compile(r'(sk-[a-zA-Z0-9\-_]{20,})'), r'sk-***MASKED***'),  # OpenAI / Generic
    (re.compile(r'(AIza[0-9A-Za-z\-_]{30,})'), r'AIza***MASKED***'),  # Google API
    (re.compile(r'(ghp_[a-zA-Z0-9]{30,})'), r'ghp_***MASKED***'),  # Github Token
]

class SensitiveDataFilter(logging.Filter):
    """Log kayıtlarındaki hassas verileri maskeler."""
    
    def filter(self, record):
        if not isinstance(record.msg, str):
            return True
            
        msg = record.msg
        # Mesajin kendisindeki hassas verileri maskele
        for pattern, replacement in MASKS:
            if pattern.search(msg):
                msg = pattern.sub(replacement, msg)
        
        # Argümanlardaki hassas verileri maskele (örn: log.info("Key: %s", key))
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in MASKS:
                        if pattern.search(arg):
                            arg = pattern.sub(replacement, arg)
                new_args.append(arg)
            record.args = tuple(new_args)
            
        record.msg = msg
        return True

def setup_logger(name: str = "RenLocalizer", log_file: str = "renlocalizer.log", level=logging.DEBUG):
    """Güvenli logger yapılandırması."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Mevcut handlerları temizle (tekrar eklememek için)
    if logger.handlers:
        logger.handlers = []

    # Format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File Handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SensitiveDataFilter()) # Filtreyi ekle
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter()) # Filtreyi ekle
    logger.addHandler(console_handler)
    
    return logger
