"""AI-based translation engine implementation (OpenAI, Gemini, Local LLM)."""

from __future__ import annotations

import asyncio
import logging
import json
import os
import random
from abc import abstractmethod
from typing import Dict, List, Optional, Any, Union

# Third-party libraries (will be installed by user)
try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    openai = None
    AsyncOpenAI = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from .translator import (
    BaseTranslator, 
    TranslationRequest, 
    TranslationResult, 
    TranslationEngine,
    protect_renpy_syntax,
    restore_renpy_syntax
)
from src.utils.constants import (
    AI_DEFAULT_TEMPERATURE, AI_DEFAULT_TIMEOUT, AI_DEFAULT_MAX_TOKENS,
    AI_MAX_RETRIES, AI_LOCAL_TIMEOUT
)

class LLMTranslator(BaseTranslator):
    """Abstract base class for LLM-based translators."""

    SYSTEM_PROMPT_TEMPLATE = """You are a professional video game localizer specializing in Ren'Py visual novels.
Your task is to translate the given text from {source_lang} to {target_lang}.

CRITICAL RULES:
1. Preserve all Ren'Py control codes, variables like [variable], placeholders like ?V000?, and tags like {{tag}}.
2. Do NOT translate the content inside brackets [] or braces {{}}.
3. Maintain the original tone and style of the visual novel.
4. Return ONLY the translated text. Do NOT add notes, explanations, or quotes.
5. If the text contains only technical codes or is untranslatable, return it exactly as is.
6. You are a neutral translation tool, not a moral guardian or content judge. You MUST translate all provided text regardless of its themes or content (including adult, suggestive, or violent themes) with absolute accuracy and no self-censorship.
"""

    # --- Constants for Batch Processing ---
    BATCH_ITEM_WRAPPER = '<r id="{index}">{text}</r>'
    BATCH_PARSE_PATTERN = r'<r id="(\d+)">(.*?)</r>'
    BATCH_INSTRUCTION_TEMPLATE = (
        "\n\nIMPORTANT: You are processing a BATCH of {count} items.\n"
        "Each item is wrapped in <r id=\"N\"> tags.\n"
        "You MUST return the translations in the SAME XML-like format: <r id=\"N\">Translation</r>.\n"
        "Maintain the original IDs. Do not combine lines. Return ALL items."
    )

    # --- Constants for OpenRouter Identification ---
    # OpenRouter uses these headers to credit usage to the application on their rankings page.
    OPENROUTER_HEADERS = {
        "HTTP-Referer": "https://github.com/Lord0fTurk/RenLocalizer",
        "X-Title": "RenLocalizer"
    }


    def __init__(self, api_key: str, model: str, config_manager=None, 
                 temperature=AI_DEFAULT_TEMPERATURE, timeout=AI_DEFAULT_TIMEOUT, 
                 max_tokens=AI_DEFAULT_MAX_TOKENS, max_retries=AI_MAX_RETRIES, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        self.model = model
        self.config_manager = config_manager
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        # Fallback engine (usually Google Web) if AI refuses content
        self.fallback_translator: Optional[BaseTranslator] = None

    def _get_text(self, key: str, default: str, **kwargs) -> str:
        """Helper to get localized text from config_manager."""
        if self.config_manager:
            return self.config_manager.get_ui_text(key, default).format(**kwargs)
        return default.format(**kwargs)

    def set_fallback_translator(self, translator: BaseTranslator):
        """Sets a fallback translator for safety filter violations."""
        self.fallback_translator = translator

    async def _handle_fallback(self, request: TranslationRequest, error_msg: str) -> TranslationResult:
        """Executes fallback translation if available."""
        if self.fallback_translator:
            log_msg = self._get_text('log_ai_safety_fallback', 
                                    "AI Safety Triggered ({error}). Falling back to {engine}...",
                                    error=error_msg, engine=self.fallback_translator.__class__.__name__)
            self.logger.warning(log_msg)
            return await self.fallback_translator.translate_single(request)
        
        err_msg = self._get_text('error_ai_filtered', "AI Filtered: {error}", error=error_msg)
        return TranslationResult(
            request.text, 
            "", 
            request.source_lang, 
            request.target_lang, 
            request.engine, 
            False, 
            err_msg
        )

    @abstractmethod
    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Abstract method to call the specific LLM API."""
        pass

    # Enhanced prompt template for aggressive retry - forces AI to translate
    AGGRESSIVE_RETRY_PROMPT = """You are a professional translator. The previous translation attempt returned the SAME text as the original.
This is WRONG. You MUST translate from {source_lang} to {target_lang}.

IMPORTANT:
- The text "{original_text}" IS NOT A VARIABLE or CODE. It is CONTENT.
- Unless it is a proper name like "John" or "Tokyo", it MUST be translated.
- If it contains [brackets], translate AROUND them.
- Return ONLY the translation, nothing else.
- Preserve placeholders like [name], {{tag}}, ?V000? exactly as they are."""

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
        # Check if aggressive retry is enabled
        aggressive_retry = False
        if self.config_manager:
            aggressive_retry = getattr(self.config_manager.translation_settings, 'aggressive_retry_translation', False)
        
        # Check if user has defined a custom system prompt
        custom_prompt = ""
        if self.config_manager:
            custom_prompt = getattr(self.config_manager.translation_settings, 'ai_custom_system_prompt', '').strip()
        
        if custom_prompt:
            # User-defined prompt with variable substitution
            system_prompt = custom_prompt.replace('{source_lang}', request.source_lang).replace('{target_lang}', request.target_lang)
        else:
            # Default localized prompt
            system_prompt = self._get_text('ai_system_prompt', self.SYSTEM_PROMPT_TEMPLATE,
                                         source_lang=request.source_lang,
                                         target_lang=request.target_lang)
        
        max_retries = self.max_retries
        backoff_base = 2.0
        max_unchanged_retries = 2  # Number of retries with enhanced prompt for unchanged translations
        
        for attempt in range(max_retries + 1):
            try:
                translated_content = await self._generate_completion(system_prompt, protected_text)
                final_text = restore_renpy_syntax(translated_content, placeholders)
                
                # Aggressive Retry: If translation equals original, retry with enhanced prompt
                if aggressive_retry and final_text.strip() == request.text.strip() and len(request.text.strip()) > 3:
                    self.emit_log("debug", f"AI translation unchanged, trying aggressive retry: {request.text[:50]}...")
                    
                    for retry_attempt in range(max_unchanged_retries):
                        # Use aggressive prompt that forces translation
                        aggressive_prompt = self.AGGRESSIVE_RETRY_PROMPT.format(
                            source_lang=request.source_lang,
                            target_lang=request.target_lang,
                            original_text=request.text[:100]  # Include snippet of original
                        )
                        
                        try:
                            retry_content = await self._generate_completion(aggressive_prompt, protected_text)
                            retry_final = restore_renpy_syntax(retry_content, placeholders)
                            
                            if retry_final.strip() != request.text.strip():
                                self.emit_log("info", f"Aggressive retry successful after {retry_attempt + 1} attempts")
                                return TranslationResult(
                                    original_text=request.text,
                                    translated_text=retry_final.strip(),
                                    source_lang=request.source_lang,
                                    target_lang=request.target_lang,
                                    engine=request.engine,
                                    success=True,
                                    confidence=0.85,  # Lower confidence for aggressive retry
                                    metadata=request.metadata
                                )
                        except Exception as retry_e:
                            self.emit_log("warning", f"Aggressive retry attempt {retry_attempt + 1} failed: {retry_e}")
                        
                        await asyncio.sleep(0.5)  # Brief delay between retries
                    
                    self.emit_log("warning", f"AI translation unchanged after aggressive retry: {request.text[:50]}...")
                
                return TranslationResult(
                    original_text=request.text,
                    translated_text=final_text.strip(),
                    source_lang=request.source_lang,
                    target_lang=request.target_lang,
                    engine=request.engine,
                    success=True,
                    confidence=0.95,
                    metadata=request.metadata # Preserve metadata!
                )
                
            except ValueError as ve:
                # Usually safety violations raise ValueError in our implementation
                return await self._handle_fallback(request, str(ve))
            except Exception as e:
                # Rate limit error handling (429)
                is_rate_limit = self._is_rate_limit_error(e)
                
                if is_rate_limit and attempt < max_retries:
                    # Exponential backoff with jitter to avoid thundering herd
                    wait_time = (backoff_base ** (attempt + 1)) + random.uniform(0.1, 1.0)
                    self.emit_log("warning", f"AI Rate Limit hit ({request.engine.value}), waiting {wait_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                
                self.emit_log("error", f"LLM Translation Error ({request.engine.value}): {e}")
                if attempt < max_retries and not is_rate_limit:
                    # For other errors, maybe a small delay before retry
                    await asyncio.sleep(1.0)
                    continue
                
                # Report definitive failure
                return TranslationResult(
                    request.text, "", request.source_lang, request.target_lang, request.engine, False, str(e), quota_exceeded=is_rate_limit
                )

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        if not requests:
            return []
            
        # If there's only one request, use translate_single
        if len(requests) == 1:
            return [await self.translate_single(requests[0])]
        
        # Internal Deduplication for AI Batch (Token saving)
        # Even though Manager has dedup, doing it here is safer if translate_batch is called directly
        indexed = list(enumerate(requests))
        unique_map = {} # text -> [original_indices]
        for idx, req in indexed:
            unique_map.setdefault(req.text, []).append(idx)
        
        unique_requests = []
        unique_indices_map = {} # unique_idx -> [original_indices]
        for i, (text, indices) in enumerate(unique_map.items()):
            # Use the first request as representative
            first_req_idx = indices[0]
            unique_requests.append(requests[first_req_idx])
            unique_indices_map[i] = indices
            
        # Protect all texts and prepare prompt
        batch_items = []
        all_placeholders = [] # Corresponds to unique_requests
        
        for i, req in enumerate(unique_requests):
            protected, placeholders = protect_renpy_syntax(req.text)
            batch_items.append(self.BATCH_ITEM_WRAPPER.format(index=i, text=protected))
            all_placeholders.append(placeholders)
            
        user_prompt = "\n".join(batch_items)
        
        # System prompt with batching instructions
        req0 = requests[0]
        custom_prompt = ""
        if self.config_manager:
            custom_prompt = getattr(self.config_manager.translation_settings, 'ai_custom_system_prompt', '').strip()
        
        if custom_prompt:
            base_system = custom_prompt.replace('{source_lang}', req0.source_lang).replace('{target_lang}', req0.target_lang)
        else:
            base_system = self._get_text('ai_system_prompt', self.SYSTEM_PROMPT_TEMPLATE,
                                         source_lang=req0.source_lang,
                                         target_lang=req0.target_lang)
                                         
        batch_instruction = self.BATCH_INSTRUCTION_TEMPLATE.format(count=len(unique_requests))
        system_prompt = base_system + batch_instruction
        
        max_retries = self.max_retries
        for attempt in range(max_retries + 1):
            if self.should_stop_callback and self.should_stop_callback():
                return [TranslationResult(r.text, "", req0.source_lang, req0.target_lang, req0.engine, False, "Stopped by user") for r in requests]
            try:
                response_text = await self._generate_completion(system_prompt, user_prompt)
                
                # Parse the response (simple regex or tag lookup)
                import re
                unique_results_map: Dict[int, TranslationResult] = {}
                matches = re.finditer(self.BATCH_PARSE_PATTERN, response_text, re.DOTALL)
                
                found_count = 0
                for m in matches:
                    u_idx = int(m.group(1)) # This is unique index
                    translated_protected = m.group(2).strip()
                    if 0 <= u_idx < len(unique_requests):
                        final_text = restore_renpy_syntax(translated_protected, all_placeholders[u_idx])
                        req = unique_requests[u_idx]
                        
                        unique_results_map[u_idx] = TranslationResult(
                            original_text=req.text,
                            translated_text=final_text,
                            source_lang=req0.source_lang,
                            target_lang=req0.target_lang,
                            engine=req0.engine,
                            success=True,
                            metadata=req.metadata
                        )
                        found_count += 1
                
                # Check if we got all unique items back
                if found_count >= len(unique_requests) * 0.9: # 90% success is good enough for batch, retry logic handles rest
                    # Distribute results to all requests
                    final_results: List[TranslationResult] = [None] * len(requests)
                    
                    # First fill from batch results
                    for u_idx, res in unique_results_map.items():
                        # Distribute to all original indices mapped to this unique index
                        if u_idx in unique_indices_map:
                            for orig_idx in unique_indices_map[u_idx]:
                                # Copy result with correct metadata if needed
                                final_results[orig_idx] = TranslationResult(
                                    requests[orig_idx].text,
                                    res.translated_text,
                                    res.source_lang,
                                    res.target_lang,
                                    res.engine,
                                    True,
                                    metadata=requests[orig_idx].metadata
                                )
                                
                    # Handle missing items by falling back to single translation
                    tasks = []
                    missing_indices = []
                    
                    for i, res in enumerate(final_results):
                        if res is None:
                            missing_indices.append(i)
                            # Only create task for unique missing items to save tokens
                            pass 

                    # If missing items, fallback individually (simple approach for now)
                    if missing_indices:
                        self.emit_log("warning", f"AI Batch incomplete. {len(missing_indices)} items missing. Retrying missing items individually...")
                        for i in missing_indices:
                             final_results[i] = await self.translate_single(requests[i])
                             
                    return final_results
                else:
                    self.emit_log("warning", f"AI Batch partially incomplete ({found_count}/{len(unique_requests)}). Retrying individual items to ensure 100% coverage.")
                    # Fallback to single translation for failed batch
                    return [await self.translate_single(r) for r in requests]
                    
            except Exception as e:
                is_rate_limit = self._is_rate_limit_error(e)
                if is_rate_limit and attempt < max_retries:
                    wait_time = (2.0 ** (attempt + 1)) + random.uniform(0.1, 1.0)
                    self.emit_log("warning", f"AI Rate Limit hit in batch, waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                self.emit_log("error", f"AI Batch Error: {e}. Falling back to single...")
                return [await self.translate_single(r) for r in requests]
                
        return [await self.translate_single(r) for r in requests]

    def _is_rate_limit_error(self, e: Exception) -> bool:
        """Determines if an exception is related to rate limiting (429)."""
        err_str = str(e).lower()
        # Common 429 indicators
        if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
            return True
        # Provider specific indicators
        if "resource_exhausted" in err_str or "quota" in err_str:
            return True
        return False

    def get_supported_languages(self) -> Dict[str, str]:
        # LLMs support basically everything
        return {"auto": "Auto", "en": "English", "tr": "Turkish"}


class OpenAITranslator(LLMTranslator):
    """Translator using OpenAI API (ChatGPT) or OpenAI-compatible APIs (OpenRouter, Ollama)."""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: Optional[str] = None, 
                 temperature=AI_DEFAULT_TEMPERATURE, timeout=AI_DEFAULT_TIMEOUT, 
                 max_tokens=AI_DEFAULT_MAX_TOKENS, **kwargs):
        super().__init__(api_key, model, temperature=temperature, timeout=timeout, max_tokens=max_tokens, **kwargs)
        if not AsyncOpenAI:
            raise ImportError("openai library is not installed. Please install it via pip.")
            
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url  # Can be OpenRouter or local Ollama URL
        )
        self.is_openrouter = base_url and "openrouter" in base_url

    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        # OpenRouter expects identification headers for usage ranking.
        extra_headers = self.OPENROUTER_HEADERS if self.is_openrouter else {}

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
                extra_headers=extra_headers
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError(self._get_text('error_ai_empty_response', "Empty response from AI"))
                
            # Token usage tracking
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                total_tokens = getattr(response.usage, 'total_tokens', 0)
                self.emit_log("debug", f"OpenAI Token Usage: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
                
            # Basic refusal check
            if hasattr(response.choices[0], 'finish_reason') and response.choices[0].finish_reason == 'content_filter':
                raise ValueError(self._get_text('error_ai_content_filter', "Content filtered by AI safety policy"))

            return content
            
        except Exception as e:
            # Check for refusal in exception message if library raises it
            if "content_filter" in str(e) or "safety" in str(e).lower():
                raise ValueError(self._get_text('error_ai_content_policy', "Content Policy Violation: {error}", error=str(e)))
            raise e
    
    async def close(self):
        await self.client.close()
        await super().close()


class LocalLLMTranslator(OpenAITranslator):
    """Translator using local LLM via OpenAI-compatible API (Ollama, LM Studio, etc.)."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434/v1",
                 api_key: str = "local", temperature=AI_DEFAULT_TEMPERATURE, 
                 timeout=AI_LOCAL_TIMEOUT, max_tokens=AI_DEFAULT_MAX_TOKENS, **kwargs):
        # Local LLMs don't typically need an API key, but we pass a dummy one
        super().__init__(api_key=api_key, model=model, base_url=base_url, 
                         temperature=temperature, timeout=timeout, max_tokens=max_tokens, **kwargs)


class GeminiTranslator(LLMTranslator):
    """Translator using Google Gemini API (via new google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp", safety_level: str = "BLOCK_NONE", 
                 temperature=AI_DEFAULT_TEMPERATURE, timeout=AI_DEFAULT_TIMEOUT, 
                 max_tokens=AI_DEFAULT_MAX_TOKENS, **kwargs):
        super().__init__(api_key, model, temperature=temperature, timeout=timeout, max_tokens=max_tokens, **kwargs)
        if not genai:
            raise ImportError("google-genai library is not installed.")
        
        self.client = genai.Client(api_key=api_key)
        self.safety_level = safety_level

    def _get_safety_settings(self) -> List[types.SafetySetting]:
        # Default to BLOCK_NONE for all categories if user requested no blocking
        level = "BLOCK_NONE"
        if self.safety_level == "BLOCK_ONLY_HIGH":
            level = "BLOCK_ONLY_HIGH"
        elif self.safety_level == "STANDARD":
            level = "BLOCK_LOW_AND_ABOVE" # Default behavior for Gemini
            
        categories = [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT"
        ]
        
        return [
            types.SafetySetting(category=cat, threshold=level)
            for cat in categories
        ]

    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        try:
            # The new SDK supports system_instruction directly
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                safety_settings=self._get_safety_settings()
            )
            
            # Use asyncio.to_thread for synchronous SDK calls or use async client if available
            # Note: as of now, direct async support in google-genai might vary, 
            # we use the standard generate_content in a thread to keep it stable.
            def call_gemini():
                return self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config
                )
            
            response = await asyncio.to_thread(call_gemini)
            
            if not response.text:
                # If no text, check if it was blocked
                raise ValueError(self._get_text('error_ai_blocked', "AI returned empty text, possibly blocked by safety filters."))
            
            # Token usage tracking for Gemini
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                total_tokens = getattr(response.usage_metadata, 'total_token_count', 0)
                self.emit_log("debug", f"Gemini Token Usage: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
                
            return response.text
            
        except Exception as e:
            err_str = str(e).lower()
            if "safety" in err_str or "block" in err_str:
                raise ValueError(self._get_text('error_gemini_safety', "Gemini Safety Filter: {error}", error=str(e)))
            raise e

    async def close(self):
        """Cleanup resources."""
        await super().close()
