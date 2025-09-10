"""
Translation Worker
=================

Background worker for handling translation tasks with placeholder preservation.
"""

import asyncio
import logging
from typing import List, Dict
from pathlib import Path

try:
    from PyQt6.QtCore import QObject, pyqtSignal
except ImportError:
    from PySide6.QtCore import QObject, Signal as pyqtSignal

from src.core.translator import TranslationManager, TranslationRequest, TranslationEngine
from src.core.parser import RenPyParser  # Import for placeholder preservation
from src.utils.config import ConfigManager

class TranslationWorker(QObject):
    """Worker for background translation processing."""
    
    # Signals
    progress_updated = pyqtSignal(int, int, str)  # completed, total, current_text
    translation_completed = pyqtSignal(list)  # translation_results
    error_occurred = pyqtSignal(str)  # error_message
    finished = pyqtSignal()
    
    def __init__(self, texts: List[Dict], source_lang: str, target_lang: str, 
                 engine: TranslationEngine, translation_manager: TranslationManager,
                 config: ConfigManager, use_proxy: bool = True):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        self.texts = texts
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.engine = engine
        self.translation_manager = translation_manager
        self.config = config
        self.use_proxy = use_proxy
        
        # Initialize placeholder preservation system
        self.parser = RenPyParser()
        self.logger.info("Placeholder preservation system initialized")
        
        self.is_running = False
        self.should_stop = False
        self.results = []
    
    def stop(self):
        """Stop the translation process."""
        self.should_stop = True
        self.logger.info("Translation stop requested")
    
    def run(self):
        """Run the translation process."""
        try:
            self.is_running = True
            self.should_stop = False
            
            # Run async translation
            asyncio.run(self._translate_texts())
            
        except Exception as e:
            self.logger.error(f"Translation worker error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            self.is_running = False
            self.finished.emit()
    
    async def _translate_texts(self):
        """Translate all texts asynchronously."""
        try:
            self.logger.info(f"Starting translation of {len(self.texts)} texts")
            
            # Configure proxy usage
            self.translation_manager.set_proxy_enabled(self.use_proxy)
            
            # Create translation requests with placeholder preservation
            requests = []
            placeholder_maps = []  # Store placeholder mappings for restoration
            
            for text_data in self.texts:
                if self.should_stop:
                    break
                
                original_text = text_data['text']
                
                # CRITICAL: Preserve placeholders before translation
                processed_text, placeholder_map = self.parser.preserve_placeholders(original_text)
                
                request = TranslationRequest(
                    text=processed_text,  # Use processed text for translation
                    source_lang=self.source_lang,
                    target_lang=self.target_lang,
                    engine=self.engine,
                    metadata={
                        'type': text_data.get('type', 'unknown'),
                        'character': text_data.get('character'),
                        'context': text_data.get('context', ''),
                        'file_path': text_data.get('file_path', ''),
                        'line_number': text_data.get('line_number', 0),
                        'original_text': original_text,  # Store original text
                        'placeholder_map': placeholder_map  # Store placeholder mapping
                    }
                )
                requests.append(request)
                placeholder_maps.append(placeholder_map)
                
                # Log placeholder preservation
                if placeholder_map:
                    self.logger.debug(f"Preserved {len(placeholder_map)} placeholders in: {original_text[:50]}...")
            
            if self.should_stop:
                self.logger.info("Translation stopped by user")
                return
            
            # Process in batches
            batch_size = self.config.translation_settings.max_batch_size
            total_requests = len(requests)
            completed = 0
            
            self.results = []
            
            for i in range(0, len(requests), batch_size):
                if self.should_stop:
                    break
                
                batch = requests[i:i + batch_size]
                
                # Update progress
                current_text = batch[0].text if batch else ""
                self.progress_updated.emit(completed, total_requests, current_text)
                
                # Translate batch
                batch_results = await self.translation_manager.translate_batch(batch)
                
                # CRITICAL: Restore placeholders in translated text
                for result in batch_results:
                    if result.success and result.translated_text:
                        # Get placeholder map from metadata
                        placeholder_map = result.metadata.get('placeholder_map', {})
                        original_text = result.metadata.get('original_text', result.original_text)
                        
                        if placeholder_map:
                            # Restore placeholders in translated text
                            result.translated_text = self.parser.restore_placeholders(
                                result.translated_text, placeholder_map
                            )
                            
                            # Update original text to the real original
                            result.original_text = original_text
                            
                            # Log restoration
                            self.logger.debug(f"Restored {len(placeholder_map)} placeholders in translated text")
                
                self.results.extend(batch_results)
                
                completed += len(batch_results)
                
                # Update progress
                self.progress_updated.emit(completed, total_requests, "")
                
                self.logger.debug(f"Completed batch {i//batch_size + 1}, total: {completed}/{total_requests}")
            
            if not self.should_stop:
                self.logger.info(f"Translation completed: {len(self.results)} results")
                self.translation_completed.emit(self.results)
            else:
                self.logger.info("Translation stopped")
                
        except Exception as e:
            self.logger.error(f"Error in translation process: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
