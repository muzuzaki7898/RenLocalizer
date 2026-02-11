# -*- coding: utf-8 -*-
"""
Core Constants
==============
Centralized configuration constants for the RenLocalizer core.
This file decouples hardcoded values from logic, making updates easier without code changes.
"""

# ============================================================================
# TRANSLATION API ENDPOINTS
# ============================================================================

# Multiple Google Translate endpoints for load balancing and redundancy
GOOGLE_ENDPOINTS = [
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
]

# Lingva Translate instances (Free Google Translate Proxy)
# Ordered purely by preference/reliability history
LINGVA_INSTANCES = [
    "https://lingva.lunar.icu",         # Often fastest
    "https://lingva.garudalinux.org",   # Very stable
    "https://translate.plausibility.cloud", 
    "https://lingva.ml",                # Official (put last due to traffic/downtime)
]

# User Agents for rotating requests to avoid bot detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
]

# ============================================================================
# TIMEOUTS & RETRIES
# ============================================================================

REQUEST_TIMEOUT_TOTAL = 45
REQUEST_TIMEOUT_CONNECT = 10
REQUEST_TIMEOUT_READ = 30

MIRROR_MAX_FAILURES = 5   # Max failures before temp ban
MIRROR_BAN_TIME = 120     # Ban duration in seconds (2 min)
