"""
Voice Input Module for VoxNav
Records audio from microphone and converts to text using speech recognition.
"""

import os
import wave
import tempfile
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import optional dependencies
PYAUDIO_AVAILABLE = False
SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    logger.warning("pyaudio not installed. Run: pip install pyaudio")

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    logger.warning("speech_recognition not installed. Run: pip install SpeechRecognition")


@dataclass
class VoiceInputResult:
    """Result from voice input."""
    text: str
    confidence: float
    language: str
    audio_duration: float
    error: Optional[str] = None


class VoiceInput:
    """
    Voice input handler using microphone.
    Supports multiple speech recognition engines.
    """
    
    def __init__(
        self,
        use_google: bool = True,
        use_whisper: bool = False,
        language: str = "hi-IN",  # Hindi-India default
        sample_rate: int = 16000,
        chunk_size: int = 1024
    ):
        """
        Initialize voice input.
        
        Args:
            use_google: Use Google Speech Recognition (free, online)
            use_whisper: Use local Whisper model (offline, needs setup)
            language: Language code for recognition
            sample_rate: Audio sample rate
            chunk_size: Audio chunk size
        """
        self.use_google = use_google
        self.use_whisper = use_whisper
        self.language = language
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        self.recognizer = None
        self.microphone = None
        
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        if not PYAUDIO_AVAILABLE:
            raise ImportError(
                "pyaudio is required. Install with:\n"
                "  pip install pyaudio\n"
                "On Windows, you may need:\n"
                "  pip install pipwin\n"
                "  pipwin install pyaudio"
            )
        
        if not SPEECH_RECOGNITION_AVAILABLE:
            raise ImportError(
                "SpeechRecognition is required. Install with:\n"
                "  pip install SpeechRecognition"
            )
        
        self.recognizer = sr.Recognizer()
    
    def _get_microphone(self) -> sr.Microphone:
        """Get or create microphone instance."""
        if self.microphone is None:
            self.microphone = sr.Microphone(sample_rate=self.sample_rate)
        return self.microphone
    
    def list_microphones(self) -> list:
        """List available microphones."""
        return sr.Microphone.list_microphone_names()
    
    def calibrate(self, duration: float = 1.0):
        """
        Calibrate for ambient noise.
        
        Args:
            duration: Seconds to listen for ambient noise
        """
        mic = self._get_microphone()
        print(f"🎤 Calibrating for ambient noise ({duration}s)...")
        
        with mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=duration)
        
        print("✅ Calibration complete")
    
    def listen(
        self,
        timeout: float = 5.0,
        phrase_time_limit: float = 10.0,
        calibrate_first: bool = True
    ) -> VoiceInputResult:
        """
        Listen for voice input and convert to text.
        
        Args:
            timeout: Max seconds to wait for speech to start
            phrase_time_limit: Max seconds of speech to capture
            calibrate_first: Calibrate for ambient noise before listening
            
        Returns:
            VoiceInputResult with transcribed text
        """
        mic = self._get_microphone()
        
        try:
            with mic as source:
                if calibrate_first:
                    print("🎤 Adjusting for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                print("🎧 Listening... (speak now)")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
            
            print("🔄 Processing speech...")
            
            # Calculate audio duration
            audio_duration = len(audio.frame_data) / (self.sample_rate * 2)  # 16-bit audio
            
            # Transcribe
            text, confidence = self._transcribe(audio)
            
            return VoiceInputResult(
                text=text,
                confidence=confidence,
                language=self.language,
                audio_duration=audio_duration
            )
            
        except sr.WaitTimeoutError:
            return VoiceInputResult(
                text="",
                confidence=0.0,
                language=self.language,
                audio_duration=0.0,
                error="No speech detected (timeout)"
            )
        except Exception as e:
            logger.error(f"Voice input error: {e}")
            return VoiceInputResult(
                text="",
                confidence=0.0,
                language=self.language,
                audio_duration=0.0,
                error=str(e)
            )
    
    def _transcribe(self, audio: sr.AudioData) -> Tuple[str, float]:
        """
        Transcribe audio using configured engine.
        
        Returns:
            Tuple of (text, confidence)
        """
        if self.use_google:
            return self._transcribe_google(audio)
        elif self.use_whisper:
            return self._transcribe_whisper(audio)
        else:
            return self._transcribe_google(audio)  # Default
    
    def _transcribe_google(self, audio: sr.AudioData) -> Tuple[str, float]:
        """Use Google Speech Recognition (free, online)."""
        try:
            # Google supports many Indian languages
            text = self.recognizer.recognize_google(
                audio,
                language=self.language,
                show_all=False
            )
            return text, 0.9  # Google doesn't return confidence
        except sr.UnknownValueError:
            return "", 0.0
        except sr.RequestError as e:
            raise Exception(f"Google Speech API error: {e}")
    
    def _transcribe_whisper(self, audio: sr.AudioData) -> Tuple[str, float]:
        """Use local Whisper model (offline)."""
        try:
            # Requires openai-whisper package
            text = self.recognizer.recognize_whisper(
                audio,
                model="base",
                language=self.language.split("-")[0]  # "hi" from "hi-IN"
            )
            return text, 0.85
        except Exception as e:
            logger.warning(f"Whisper failed: {e}, falling back to Google")
            return self._transcribe_google(audio)


def quick_listen(language: str = "hi-IN") -> str:
    """
    Quick helper to listen and return text.
    
    Args:
        language: Language code (hi-IN for Hindi, en-US for English)
        
    Returns:
        Transcribed text or empty string on error
    """
    try:
        voice = VoiceInput(language=language)
        result = voice.listen()
        
        if result.error:
            print(f"❌ Error: {result.error}")
            return ""
        
        return result.text
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return ""
    except Exception as e:
        print(f"❌ Error: {e}")
        return ""


# Supported Indian languages
INDIAN_LANGUAGES = {
    "hi-IN": "Hindi",
    "en-IN": "English (India)",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "bn-IN": "Bengali",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
    "or-IN": "Odia",
    "ur-IN": "Urdu",
}
