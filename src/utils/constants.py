# -*- coding: utf-8 -*-
"""
Application Constants
=====================

Centralized location for application-wide constants to avoid magic numbers.
"""

# AI & Translation Constants
AI_DEFAULT_TEMPERATURE = 0.3
AI_DEFAULT_TIMEOUT = 120  # seconds
AI_LOCAL_TIMEOUT = 180    # seconds, for local LLMs which might be slower
AI_DEFAULT_MAX_TOKENS = 2048
AI_MAX_RETRIES = 3

# UI Constants
WINDOW_DEFAULT_WIDTH = 1200
WINDOW_DEFAULT_HEIGHT = 800

# Pipeline Constants
MAX_CHARS_PER_REQUEST = 12000
