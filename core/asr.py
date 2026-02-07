"""
ASR Engine - Automatic Speech Recognition using IndicWhisper
Wraps the Vistaar/IndicWhisper models for Hindi and other Indian languages.
"""

import os
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ASREngine:
    """
    Automatic Speech Recognition Engine using IndicWhisper.
    Supports Hindi and 11 other Indian languages.
    """
    
    # Language code mapping
    LANG_CODES = {
        'hindi': 'hi', 'hi': 'hi',
        'sanskrit': 'sa', 'sa': 'sa',
        'bengali': 'bn', 'bn': 'bn',
        'tamil': 'ta', 'ta': 'ta',
        'telugu': 'te', 'te': 'te',
        'gujarati': 'gu', 'gu': 'gu',
        'kannada': 'kn', 'kn': 'kn',
        'malayalam': 'ml', 'ml': 'ml',
        'marathi': 'mr', 'mr': 'mr',
        'odia': 'or', 'or': 'or',
        'punjabi': 'pa', 'pa': 'pa',
        'urdu': 'ur', 'ur': 'ur',
    }
    
    def __init__(
        self,
        model_path: str = "hindi_models/whisper-medium-hi_alldata_multigpu",
        device: str = "cuda",
        default_language: str = "hi"
    ):
        """
        Initialize the ASR Engine.
        
        Args:
            model_path: Path to the IndicWhisper model
            device: Device to run inference on ("cuda" or "cpu")
            default_language: Default language code for transcription
        """
        self.model_path = model_path
        self.device = device
        self.default_language = self._normalize_lang_code(default_language)
        self.pipeline = None
        self._is_loaded = False
        
    def _normalize_lang_code(self, lang: str) -> str:
        """Normalize language name/code to ISO code."""
        return self.LANG_CODES.get(lang.lower(), 'hi')
    
    def load_model(self) -> None:
        """Load the Whisper model and pipeline."""
        if self._is_loaded:
            logger.info("Model already loaded, skipping...")
            return
            
        try:
            from transformers import pipeline
            
            logger.info(f"Loading ASR model from {self.model_path}...")
            
            self.pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_path,
                device=self.device if self.device != "cpu" else -1,
            )
            
            self._is_loaded = True
            logger.info("ASR model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to load ASR model: {e}")
            raise
    
    def _configure_language(self, lang_code: str) -> None:
        """Configure the model for a specific language."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        # Special case for Odia - not natively supported by Whisper
        if lang_code == 'or':
            self.pipeline.model.config.forced_decoder_ids = (
                self.pipeline.tokenizer.get_decoder_prompt_ids(
                    language=None, task="transcribe"
                )
            )
        else:
            self.pipeline.model.config.forced_decoder_ids = (
                self.pipeline.tokenizer.get_decoder_prompt_ids(
                    language=lang_code, task="transcribe"
                )
            )
    
    def transcribe(
        self,
        audio_input: Union[str, bytes, "np.ndarray"],
        language: Optional[str] = None,
        return_timestamps: bool = False
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text.
        
        Args:
            audio_input: Path to audio file, audio bytes, or numpy array
            language: Language code (uses default if not specified)
            return_timestamps: Whether to return word-level timestamps
            
        Returns:
            Dictionary with 'text' and optionally 'chunks' with timestamps
        """
        if not self._is_loaded:
            self.load_model()
        
        # Normalize language code
        lang_code = self._normalize_lang_code(language) if language else self.default_language
        
        # Configure for the target language
        self._configure_language(lang_code)
        
        logger.info(f"Transcribing audio in language: {lang_code}")
        
        try:
            # Run transcription
            result = self.pipeline(
                audio_input,
                return_timestamps=return_timestamps
            )
            
            # Add metadata
            result['language'] = lang_code
            result['model'] = self.model_path
            
            logger.info(f"Transcription complete: {result['text'][:100]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def transcribe_stream(self, audio_chunks: list, language: Optional[str] = None):
        """
        Transcribe streaming audio chunks.
        
        Args:
            audio_chunks: List of audio chunk arrays
            language: Language code
            
        Yields:
            Partial transcription results
        """
        if not self._is_loaded:
            self.load_model()
            
        lang_code = self._normalize_lang_code(language) if language else self.default_language
        self._configure_language(lang_code)
        
        for chunk in audio_chunks:
            try:
                result = self.pipeline(chunk)
                yield result
            except Exception as e:
                logger.error(f"Chunk transcription failed: {e}")
                yield {'text': '', 'error': str(e)}
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._is_loaded
    
    def unload_model(self) -> None:
        """Unload the model to free memory."""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            self._is_loaded = False
            
            # Clear CUDA cache if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
                
            logger.info("ASR model unloaded successfully.")
