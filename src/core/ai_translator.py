"""AI-based translation engine implementation (OpenAI, Gemini, Local LLM)."""

from __future__ import annotations

import asyncio
import logging
import json
import os
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
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
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
"""

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

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
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
        
        try:
            translated_content = await self._generate_completion(system_prompt, protected_text)
            final_text = restore_renpy_syntax(translated_content, placeholders)
            
            return TranslationResult(
                original_text=request.text,
                translated_text=final_text.strip(),
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                engine=request.engine,
                success=True,
                confidence=0.95
            )
            
        except ValueError as ve:
            # Usually safety violations raise ValueError in our implementation
            return await self._handle_fallback(request, str(ve))
        except Exception as e:
            self.logger.error(f"LLM Translation Error: {e}")
            return TranslationResult(
                request.text, "", request.source_lang, request.target_lang, request.engine, False, str(e)
            )

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
        extra_headers = {}
        if self.is_openrouter:
            extra_headers = {
                "HTTP-Referer": "https://github.com/Lord0fTurk/RenLocalizer",
                "X-Title": "RenLocalizer"
            }

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
    """Translator using Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-pro", safety_level: str = "BLOCK_NONE", 
                 temperature=AI_DEFAULT_TEMPERATURE, timeout=AI_DEFAULT_TIMEOUT, 
                 max_tokens=AI_DEFAULT_MAX_TOKENS, **kwargs):
        super().__init__(api_key, model, temperature=temperature, timeout=timeout, max_tokens=max_tokens, **kwargs)
        if not genai:
            raise ImportError("google-generativeai library is not installed.")
        
        genai.configure(api_key=api_key)
        self.safety_level = safety_level
        self._model_instance = genai.GenerativeModel(model)

    def _get_safety_settings(self):
        # Default to BLOCK_NONE for all categories if user requested no blocking
        if self.safety_level == "BLOCK_NONE":
            return {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        elif self.safety_level == "BLOCK_ONLY_HIGH":
             return {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
        return None # Default API settings

    async def _generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        try:
            # Gemini doesn't always support system instructions purely in some versions,
            # but usually we can prepend it or use the system_instruction param in newer libs.
            # For compatibility, we'll just incorporate it into the prompt or chat history.
            
            # Use chat for better context handling usually
            chat = self._model_instance.start_chat()
            
            full_prompt = f"{system_prompt}\n\nUser Input: {user_prompt}"
            
            response = await chat.send_message_async(
                full_prompt,
                safety_settings=self._get_safety_settings(),
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens
                )
            )
            
            if response.prompt_feedback.block_reason:
                raise ValueError(self._get_text('error_ai_blocked', "Blocked: {reason}", reason=str(response.prompt_feedback.block_reason)))
                
            return response.text
            
        except Exception as e:
            if "finish_reason" in str(e) and "SAFETY" in str(e):
                raise ValueError(self._get_text('error_gemini_safety', "Gemini Safety Filter: {error}", error=str(e)))
            raise e

    async def close(self):
        """Cleanup resources."""
        # Gemini doesn't have explicit client cleanup, but we call base
        await super().close()
