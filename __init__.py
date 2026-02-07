"""
VoxNav - Voice-Activated Web Navigation Assistant

A multilingual voice assistant supporting Hindi, Hinglish, and 
Indian regional languages using IndicWhisper for ASR and Gemini 
for intent understanding.
"""

__version__ = "0.1.0"
__author__ = "VoxNav Team"

from .core import (
    ASREngine,
    IntentDispatcher,
    SlotFiller,
    DynamicPromptBuilder,
    MultilingualHandler,
    VoxNavOrchestrator
)

from .config import VoxNavConfig, config

__all__ = [
    'ASREngine',
    'IntentDispatcher',
    'SlotFiller', 
    'DynamicPromptBuilder',
    'MultilingualHandler',
    'VoxNavOrchestrator',
    'VoxNavConfig',
    'config'
]
