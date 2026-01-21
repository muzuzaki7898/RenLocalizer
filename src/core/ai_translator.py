"""AI-based translation engine implementation (OpenAI, Gemini, Local LLM)."""

from __future__ import annotations

import asyncio
import logging
import json
import os
import random
import re
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

try:
    import httpx
except ImportError:
    httpx = None

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
    AI_MAX_RETRIES, AI_LOCAL_TIMEOUT, AI_LOCAL_URL
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
            
        # Get batch size from settings
        batch_size = getattr(self.config_manager.translation_settings, 'ai_batch_size', 50)
        
        # If total requests exceed batch_size, split and process
        if len(requests) > batch_size:
            self.emit_log("info", f"Splitting large AI batch: {len(requests)} texts into chunks of {batch_size}")
            results = []
            for i in range(0, len(requests), batch_size):
                chunk = requests[i:i + batch_size]
                chunk_results = await self._translate_batch_internal(chunk)
                results.extend(chunk_results)
            return results
        
        return await self._translate_batch_internal(requests)

    async def _translate_batch_internal(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Original batch translation logic, now handles a single appropriately sized chunk."""
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
                    self.emit_log("warning", f"AI Batch partially incomplete ({found_count}/{len(unique_requests)}). Retrying items with limited concurrency...")
                    # Fallback to concurrent single translations but LIMITED by a semaphore
                    import asyncio
                    concurrency = getattr(self.config_manager.translation_settings, 'ai_concurrency', 2)
                    sem = asyncio.Semaphore(concurrency)
                    
                    async def sem_translate(req):
                        async with sem:
                            return await self.translate_single(req)
                    
                    results = await asyncio.gather(*[sem_translate(r) for r in requests], return_exceptions=True)
                    
                    # Handle results
                    final_results = []
                    for i, res in enumerate(results):
                        if isinstance(res, Exception):
                            final_results.append(TranslationResult(requests[i].text, "", requests[i].source_lang, requests[i].target_lang, requests[i].engine, False, str(res)))
                        else:
                            final_results.append(res)
                    return final_results
                    
            except Exception as e:
                is_rate_limit = self._is_rate_limit_error(e)
                if is_rate_limit and attempt < max_retries:
                    wait_time = (2.0 ** (attempt + 1)) + random.uniform(0.1, 1.0)
                    self.emit_log("warning", f"AI Rate Limit hit in batch, waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                self.emit_log("error", f"AI Batch Error: {e}. Falling back to limited concurrency...")
                concurrency = getattr(self.config_manager.translation_settings, 'ai_concurrency', 2)
                sem = asyncio.Semaphore(concurrency)
                async def sem_translate(req):
                    async with sem:
                        return await self.translate_single(req)
                return await asyncio.gather(*[sem_translate(r) for r in requests])
                
        concurrency = getattr(self.config_manager.translation_settings, 'ai_concurrency', 2)
        sem = asyncio.Semaphore(concurrency)
        async def sem_translate(req):
            async with sem:
                return await self.translate_single(req)
        return await asyncio.gather(*[sem_translate(r) for r in requests])

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
            
            # Safely extract content from response - handles incomplete/malformed responses
            # from local LLMs like LM Studio/Ollama that may not be fully OpenAI-compatible
            if not response or not hasattr(response, 'choices') or not response.choices:
                raise ValueError(self._get_text('error_ai_no_choices', 
                    "AI response has no choices. Check if your local LLM is running correctly."))
            
            first_choice = response.choices[0]
            if not first_choice or not hasattr(first_choice, 'message') or not first_choice.message:
                raise ValueError(self._get_text('error_ai_no_message', 
                    "AI response has no message. The model may not be loaded properly."))
            
            content = first_choice.message.content
            if not content:
                raise ValueError(self._get_text('error_ai_empty_response', "Empty response from AI"))
                
            # Token usage tracking
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                total_tokens = getattr(response.usage, 'total_tokens', 0)
                self.emit_log("debug", f"OpenAI Token Usage: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
                
            # Basic refusal check
            if hasattr(first_choice, 'finish_reason') and first_choice.finish_reason == 'content_filter':
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


class LocalLLMTranslator(LLMTranslator):
    """
    Translator for local LLM servers (Ollama, LM Studio, etc.).
    Uses simplified prompts because smaller models get confused by complex instructions.
    """
    
    # Super simplified prompt for local models to prevent hallucinations
    LOCAL_SYSTEM_PROMPT = "Translate the gaming text from {source_lang} to {target_lang}. Keep [vars] and {{tags}} unchanged. Return ONLY the translation. No notes."

    def __init__(self, model: str = "llama3.2", base_url: str = AI_LOCAL_URL, api_key: str = "local", 
                 temperature=AI_DEFAULT_TEMPERATURE, timeout=AI_LOCAL_TIMEOUT, 
                 max_tokens=AI_DEFAULT_MAX_TOKENS, config_manager=None, **kwargs):
        super().__init__(api_key=api_key, model=model, temperature=temperature, 
                         timeout=timeout, max_tokens=max_tokens, config_manager=config_manager, **kwargs)
        
        if not httpx:
            raise ImportError("httpx library is not installed. Please install it via: pip install httpx")
            
        self.base_url = base_url.rstrip('/')
        self.server_type = self._detect_server_type(self.base_url)
        self._client: Optional[httpx.AsyncClient] = None
        self._health_checked = False
        self._available_models: List[str] = []
        
    def _detect_server_type(self, url: str) -> str:
        url_lower = url.lower()
        if ":11434" in url_lower or "ollama" in url_lower: return "ollama"
        if ":1234" in url_lower or "lmstudio" in url_lower: return "lmstudio"
        if ":5000" in url_lower or "textgen" in url_lower: return "textgen"
        if ":8080" in url_lower or "localai" in url_lower: return "localai"
        return "unknown"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
                }
            )
        return self._client
    
    async def health_check(self) -> tuple:
        """Check if the local LLM server is running and accessible.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            client = await self._get_client()
            
            # Try models endpoint first (OpenAI-compatible)
            models_url = f"{self.base_url}/models"
            try:
                response = await client.get(models_url, timeout=5.0)
                if response.status_code == 200:
                    self._health_checked = True
                    return (True, self._get_text('log_local_llm_health_ok',
                        "✅ Local LLM server is ready ({server_type})",
                        server_type=self.server_type))
            except Exception:
                pass
            
            # Try Ollama-specific endpoint
            if self.server_type == "ollama":
                ollama_url = self.base_url.replace('/v1', '/api/tags')
                try:
                    response = await client.get(ollama_url, timeout=5.0)
                    if response.status_code == 200:
                        self._health_checked = True
                        return (True, self._get_text('log_local_llm_health_ok',
                            "✅ Local LLM server is ready ({server_type})",
                            server_type="Ollama"))
                except Exception:
                    pass
            
            return (False, self._get_text('error_local_llm_connection',
                "Cannot connect to local LLM server at {url}. Make sure the server is running.",
                url=self.base_url))
                
        except httpx.ConnectError:
            return (False, self._get_text('error_local_llm_connection',
                "Cannot connect to local LLM server at {url}. Make sure the server is running.",
                url=self.base_url))
        except httpx.TimeoutException:
            return (False, self._get_text('error_local_llm_timeout',
                "Connection to local LLM server timed out. The server might be starting up.",
                url=self.base_url))
        except Exception as e:
            return (False, f"Health check failed: {str(e)}")
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models from the server.
        
        Returns:
            List of model names available on the server
        """
        if self._available_models:
            return self._available_models
            
        try:
            client = await self._get_client()
            models = []
            
            # Try OpenAI-compatible endpoint
            try:
                response = await client.get(f"{self.base_url}/models", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and 'data' in data:
                        models = [m.get('id', '') for m in data['data'] if m.get('id')]
                    elif isinstance(data, list):
                        models = [m.get('id', '') or m.get('name', '') for m in data if isinstance(m, dict)]
            except Exception:
                pass
            
            # Try Ollama-specific endpoint
            if not models and self.server_type == "ollama":
                try:
                    ollama_url = self.base_url.replace('/v1', '/api/tags')
                    response = await client.get(ollama_url, timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        if 'models' in data:
                            models = [m.get('name', '').split(':')[0] for m in data['models'] if m.get('name')]
                except Exception:
                    pass
            
            self._available_models = models
            return models
            
        except Exception as e:
            self.logger.warning(f"Failed to get available models: {e}")
            return []
    
    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Generate completion using the local LLM server."""
        try:
            client = await self._get_client()
            
            # Perform health check on first request
            if not self._health_checked:
                success, message = await self.health_check()
                if not success:
                    raise ValueError(message)
                self.emit_log("info", message)
            
            # Build request payload (OpenAI-compatible format)
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }
            
            # Make the request
            chat_url = f"{self.base_url}/chat/completions"
            response = await client.post(chat_url, json=payload)
            
            # Handle different response codes
            if response.status_code == 404:
                raise ValueError(self._get_text('error_local_llm_no_model',
                    "Model '{model}' not found. Please check if the model is loaded in your LLM server.",
                    model=self.model))
            
            if response.status_code == 503:
                raise ValueError(self._get_text('error_local_llm_no_model',
                    "No model loaded. Please load a model in your LLM server (LM Studio/Ollama) first."))
            
            if response.status_code != 200:
                error_text = response.text[:200] if response.text else "Unknown error"
                raise ValueError(f"Local LLM error ({response.status_code}): {error_text}")
            
            # Parse response
            data = response.json()
            
            # Safely extract content - handle various response formats
            content = None
            
            # Standard OpenAI format
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                if isinstance(choice, dict):
                    message = choice.get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content', '')
                    elif isinstance(message, str):
                        content = message
                    # Some servers put content directly in choice
                    if not content:
                        content = choice.get('text', '') or choice.get('content', '')
            
            # Ollama native format fallback
            if not content and 'response' in data:
                content = data['response']
            
            # Direct message format
            if not content and 'message' in data:
                msg = data['message']
                content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
            
            if not content:
                raise ValueError(self._get_text('error_local_llm_empty_response',
                    "Local LLM returned empty response. The model may not be loaded properly or is still generating."))
            
            # Token usage logging (if available)
            if 'usage' in data:
                usage = data['usage']
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)
                self.emit_log("debug", f"Local LLM Token Usage: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
            
            return content.strip()
            
        except httpx.ConnectError:
            raise ValueError(self._get_text('error_local_llm_connection',
                "Cannot connect to local LLM server at {url}. Make sure the server is running.",
                url=self.base_url))
        except httpx.TimeoutException:
            raise ValueError(self._get_text('error_local_llm_timeout',
                "Local LLM took too long to respond ({timeout}s). Try a smaller model or increase timeout in settings.",
                timeout=self.timeout))
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error from local LLM: {e.response.status_code}")
        except json.JSONDecodeError:
            raise ValueError(self._get_text('error_local_llm_invalid_response',
                "Invalid response from local LLM server. The server may be misconfigured."))

    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        await super().close()


class LocalLLMTranslator(LLMTranslator):
    """
    Translator for local LLM servers (Ollama, LM Studio, Text Generation WebUI, LocalAI).
    Uses httpx for direct HTTP requests instead of OpenAI SDK for better control and error handling.
    """
    
    # Optimized prompt for local LLMs (Ollama, LM Studio)
    # Smaller models get confused by long rules; keep it very direct
    LOCAL_SYSTEM_PROMPT = """Translate from {source_lang} to {target_lang}. Preserve Ren'Py [vars] and {{tags}}. Return ONLY the translated text."""
    
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434/v1",
                 api_key: str = "local", temperature=AI_DEFAULT_TEMPERATURE,
                 timeout=AI_LOCAL_TIMEOUT, max_tokens=AI_DEFAULT_MAX_TOKENS, config_manager=None, **kwargs):
        super().__init__(api_key=api_key, model=model, temperature=temperature,
                         timeout=timeout, max_tokens=max_tokens, config_manager=config_manager, **kwargs)
        
        if not httpx:
            raise ImportError("httpx library is not installed. Please install it via: pip install httpx")
        
        self.base_url = base_url.rstrip('/')
        self.server_type = self._detect_server_type(base_url)
        self._client: Optional[httpx.AsyncClient] = None
        self._health_checked = False
        self._available_models: List[str] = []
    
    def _detect_server_type(self, url: str) -> str:
        """Detect the server type from URL."""
        url_lower = url.lower()
        if ":11434" in url_lower or "ollama" in url_lower:
            return "ollama"
        elif ":1234" in url_lower or "lmstudio" in url_lower:
            return "lmstudio"
        elif ":5000" in url_lower or "textgen" in url_lower:
            return "textgen"
        elif ":8080" in url_lower or "localai" in url_lower:
            return "localai"
        return "unknown"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
                }
            )
        return self._client
    
    async def health_check(self) -> tuple:
        """Check if the local LLM server is running and accessible."""
        try:
            client = await self._get_client()
            models_url = f"{self.base_url}/models"
            response = await client.get(models_url, timeout=5.0)
            if response.status_code == 200:
                return (True, "Ready")
            return (False, f"HTTP {response.status_code}")
        except Exception as e:
            return (False, str(e))

    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Direct HTTP call for local LLM completion."""
        try:
            client = await self._get_client()
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data['choices'][0]['message']['content'] or ""
                self.emit_log("debug", f"Local LLM Raw Output: {content[:100]}...")
                return content
            raise RuntimeError(f"API Error {resp.status_code}: {resp.text}")
        except Exception as e:
            raise e

    # ULTRA-MINIMAL prompt for local models - no examples, just direct command
    LOCAL_SYSTEM_PROMPT = """Translate from {source_lang} to {target_lang}. Keep [brackets] and {{braces}} unchanged. Output only the translation.

{text}"""

    def _get_lang_name(self, code: str) -> str:
        """Convert language codes to full names for better LLM understanding."""
        names = {
            'tr': 'Turkish', 'en': 'English', 'de': 'German', 'fr': 'French',
            'es': 'Spanish', 'ru': 'Russian', 'it': 'Italian', 'zh': 'Chinese',
            'pt': 'Portuguese', 'ja': 'Japanese', 'ko': 'Korean', 'auto': 'Source Language'
        }
        return names.get(code.lower(), code)

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Single translation with full language names and zero-wrapper prompt."""
        try:
            # Check for custom prompt
            custom_prompt = None
            if self.config_manager:
                custom_prompt = getattr(self.config_manager.translation_settings, 'ai_custom_prompt', None)
            
            # Use full names for better quality
            src_name = self._get_lang_name(request.source_lang)
            tgt_name = self._get_lang_name(request.target_lang)
            
            # Protect text
            protected, placeholders = protect_renpy_syntax(request.text)
            
            if custom_prompt:
                system_prompt = custom_prompt.format(source_lang=src_name, target_lang=tgt_name)
                final_user_prompt = protected
            else:
                # For Local LLM, we combine system and user into a single clear instruction 
                # because some local servers handle "system" role poorly.
                system_prompt = "You are a professional translator."
                final_user_prompt = self.LOCAL_SYSTEM_PROMPT.format(
                    source_lang=src_name,
                    target_lang=tgt_name,
                    text=protected
                )
            
            # Get completion
            raw_text = await self._generate_completion(system_prompt, final_user_prompt)
            
            # Post-processing cleanup (Aggressively remove conversational filler)
            clean_text = raw_text.strip()
            
            # Remove common model headers/intros (Case insensitive & multiline)
            patterns = [
                r'^(Turkish|English|Translation|Çeviri|Output|Result|Here is|Sure|Translated):\s*', 
                r'^.*?çeviriyorum:?\s*', 
                r'^.*?translated text is:?\s*',
                r'^Text to translate:\s*'
            ]
            for p in patterns:
                clean_text = re.sub(p, '', clean_text, flags=re.IGNORECASE | re.MULTILINE)
            
            clean_text = clean_text.split('\n')[0] # Only take the first line (common for single translations)
            clean_text = clean_text.strip(' "«»\'') # Strip quotes and brackets
            
            # Restore
            final_text = restore_renpy_syntax(clean_text, placeholders)
            
            # Last resort: if the model corrupted placeholders or returned empty, use original
            if not final_text or 'XRPYX' in final_text and 'XRPYX' not in request.text:
                 self.emit_log("warning", f"Local LLM corrupted placeholders, using original: {request.text[:50]}...")
                 final_text = request.text

            return TranslationResult(request.text, final_text, request.source_lang, request.target_lang, request.engine, True)
        except Exception as e:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, request.engine, False, str(e))

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Local LLMs often fail with XML-style batching. Process one-by-one instead."""
        results = []
        for req in requests:
            res = await self.translate_single(req)
            results.append(res)
        return results


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
