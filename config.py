"""
VoxNav Configuration
Central configuration for the voice-activated assistant.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class ASRConfig:
    """Automatic Speech Recognition Configuration"""
    model_path: str = "hindi_models/whisper-medium-hi_alldata_multigpu"
    device: str = "cuda"  # "cuda" or "cpu"
    default_language: str = "hi"
    batch_size: int = 1
    
    # Supported language codes
    supported_languages: Dict[str, str] = field(default_factory=lambda: {
        'hindi': 'hi',
        'sanskrit': 'sa',
        'bengali': 'bn',
        'tamil': 'ta',
        'telugu': 'te',
        'gujarati': 'gu',
        'kannada': 'kn',
        'malayalam': 'ml',
        'marathi': 'mr',
        'odia': 'or',
        'punjabi': 'pa',
        'urdu': 'ur',
    })


@dataclass
class OpenRouterConfig:
    """OpenRouter API Configuration"""
    api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model_name: str = "openrouter/free"
    max_output_tokens: int = 1024
    temperature: float = 0.3  # Lower for more deterministic responses


@dataclass
class SlotConfig:
    """Slot Filling Configuration"""
    max_attempts: int = 5  # Max follow-up questions before giving up
    session_timeout_seconds: int = 300  # 5 minutes


@dataclass
class VoxNavConfig:
    """Main VoxNav Configuration"""
    asr: ASRConfig = field(default_factory=ASRConfig)
    openrouter: OpenRouterConfig = field(default_factory=OpenRouterConfig)
    slots: SlotConfig = field(default_factory=SlotConfig)
    
    # Enable/disable components
    enable_multilingual: bool = True
    enable_dynamic_prompts: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "voxnav.log"


# Default configuration instance
config = VoxNavConfig()
