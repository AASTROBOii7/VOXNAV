"""
Multilingual Handler - Manages language detection and response generation.
Supports Hindi, Hinglish, and regional Indian languages.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"
    BENGALI = "bn"
    TAMIL = "ta"
    TELUGU = "te"
    MARATHI = "mr"
    GUJARATI = "gu"
    KANNADA = "kn"
    MALAYALAM = "ml"
    PUNJABI = "pa"
    ODIA = "or"
    URDU = "ur"


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    primary_language: Language
    script: str  # latin, devanagari, tamil, etc.
    is_romanized: bool
    confidence: float
    detected_patterns: list


# Language-specific configurations
LANGUAGE_CONFIGS = {
    Language.ENGLISH: {
        'name': 'English',
        'script': 'latin',
        'system_prompt': """You are a helpful assistant. Respond in clear, professional English.
Be concise and direct. Use simple language that's easy to understand.""",
    },
    
    Language.HINDI: {
        'name': 'Hindi',
        'script': 'devanagari',
        'system_prompt': """आप एक सहायक AI हैं। कृपया शुद्ध हिंदी में जवाब दें।
- देवनागरी लिपि का उपयोग करें
- सरल और स्पष्ट भाषा में बात करें
- औपचारिक लेकिन मैत्रीपूर्ण स्वर रखें""",
    },
    
    Language.HINGLISH: {
        'name': 'Hinglish',
        'script': 'latin',
        'system_prompt': """You are a friendly assistant that speaks fluent Hinglish (Hindi-English mix).

IMPORTANT RULES:
- Match the user's speaking style exactly
- If they use more Hindi words, respond with more Hindi
- If they use more English, respond with more English
- Use romanized Hindi (Latin script) - NOT Devanagari
- Keep technical terms in English
- Be casual and conversational like talking to a friend
- Use common Hinglish expressions naturally

EXAMPLE RESPONSES:
- "Haan bilkul, main aapki help kar sakta hoon!"
- "Aapko Delhi se Mumbai jaana hai? Koi problem nahi, batao kab travel karna hai"
- "Sure! Ek second, main check karta hoon..."
- "Yeh raha aapka result. Kuch aur chahiye?"

AVOID:
- Mixing Devanagari and Latin in same response
- Being too formal
- Long complicated sentences""",
    },
    
    Language.BENGALI: {
        'name': 'Bengali',
        'script': 'bengali',
        'system_prompt': """আপনি একজন সহায়ক সহকারী। বাংলায় উত্তর দিন।
সহজ এবং স্পষ্ট ভাষা ব্যবহার করুন।""",
    },
    
    Language.TAMIL: {
        'name': 'Tamil',
        'script': 'tamil',
        'system_prompt': """நீங்கள் ஒரு உதவியாளர். தமிழில் பதிலளிக்கவும்.
எளிய மற்றும் தெளிவான மொழியைப் பயன்படுத்துங்கள்.""",
    },
    
    Language.TELUGU: {
        'name': 'Telugu',
        'script': 'telugu',
        'system_prompt': """మీరు సహాయకుడు. తెలుగులో సమాధానం ఇవ్వండి.
సరళమైన మరియు స్పష్టమైన భాషను ఉపయోగించండి.""",
    },
    
    Language.MARATHI: {
        'name': 'Marathi',
        'script': 'devanagari',
        'system_prompt': """तुम्ही एक सहाय्यक आहात. मराठीत उत्तर द्या.
सोपी आणि स्पष्ट भाषा वापरा.""",
    },
    
    Language.GUJARATI: {
        'name': 'Gujarati',
        'script': 'gujarati',
        'system_prompt': """તમે એક સહાયક છો. ગુજરાતીમાં જવાબ આપો.
સરળ અને સ્પષ્ટ ભાષાનો ઉપયોગ કરો.""",
    },
    
    Language.KANNADA: {
        'name': 'Kannada',
        'script': 'kannada',
        'system_prompt': """ನೀವು ಸಹಾಯಕರು. ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.
ಸರಳ ಮತ್ತು ಸ್ಪಷ್ಟ ಭಾಷೆಯನ್ನು ಬಳಸಿ.""",
    },
    
    Language.MALAYALAM: {
        'name': 'Malayalam',
        'script': 'malayalam',
        'system_prompt': """നിങ്ങൾ ഒരു സഹായിയാണ്. മലയാളത്തിൽ മറുപടി നൽകുക.
ലളിതവും വ്യക്തവുമായ ഭാഷ ഉപയോഗിക്കുക.""",
    },
    
    Language.PUNJABI: {
        'name': 'Punjabi',
        'script': 'gurmukhi',
        'system_prompt': """ਤੁਸੀਂ ਇੱਕ ਸਹਾਇਕ ਹੋ। ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।
ਸਰਲ ਅਤੇ ਸਪੱਸ਼ਟ ਭਾਸ਼ਾ ਵਰਤੋ।""",
    },
    
    Language.URDU: {
        'name': 'Urdu',
        'script': 'arabic',
        'system_prompt': """آپ ایک معاون ہیں۔ اردو میں جواب دیں۔
آسان اور واضح زبان استعمال کریں۔""",
    },
}


# Common Hinglish patterns for detection
HINGLISH_PATTERNS = {
    'greetings': ['namaste', 'namaskar', 'kya haal', 'kaise ho', 'theek hai', 'hello ji'],
    'confirmations': ['haan', 'ji', 'bilkul', 'theek', 'sahi', 'accha', 'ok ji', 'done'],
    'negations': ['nahi', 'nahin', 'mat', 'nope nahi', 'cancel karo'],
    'queries': ['kya', 'kaise', 'kab', 'kahan', 'kitna', 'kaun', 'kyun', 'konsa'],
    'verbs': ['karo', 'karna', 'batao', 'dikhao', 'kholo', 'band karo', 'bhejo'],
    'common_words': ['mujhe', 'mera', 'tera', 'uska', 'yeh', 'woh', 'aur', 'lekin', 'toh'],
    'booking_terms': ['book karo', 'booking', 'reserve', 'cancel', 'ticket'],
    'travel_terms': ['train', 'flight', 'bus', 'hotel', 'cab', 'delhi', 'mumbai'],
}

# Script detection patterns
SCRIPT_PATTERNS = {
    'devanagari': r'[\u0900-\u097F]',
    'bengali': r'[\u0980-\u09FF]',
    'tamil': r'[\u0B80-\u0BFF]',
    'telugu': r'[\u0C00-\u0C7F]',
    'gujarati': r'[\u0A80-\u0AFF]',
    'kannada': r'[\u0C80-\u0CFF]',
    'malayalam': r'[\u0D00-\u0D7F]',
    'gurmukhi': r'[\u0A00-\u0A7F]',
    'arabic': r'[\u0600-\u06FF\u0750-\u077F]',
}


class MultilingualHandler:
    """
    Handles language detection and multilingual response generation.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Multilingual Handler.
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.client = None
        self.user_language_preferences: Dict[str, Language] = {}
        
    def _ensure_client(self):
        """Ensure OpenRouter client is initialized."""
        if self.client is not None:
            return
            
        from .openrouter_client import OpenRouterClient
        import os
        
        api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not provided. Set OPENROUTER_API_KEY env variable.")
        
        self.client = OpenRouterClient(api_key=api_key)
    
    def detect_script(self, text: str) -> Tuple[str, float]:
        """
        Detect the script used in the text.
        
        Returns:
            Tuple of (script_name, confidence)
        """
        for script_name, pattern in SCRIPT_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                confidence = len(matches) / len(text.replace(' ', ''))
                if confidence > 0.3:
                    return script_name, min(confidence * 1.5, 1.0)
        
        return 'latin', 0.8
    
    def detect_hinglish_patterns(self, text: str) -> Tuple[int, list]:
        """
        Detect Hinglish patterns in text.
        
        Returns:
            Tuple of (score, list of detected patterns)
        """
        lower_text = text.lower()
        score = 0
        detected = []
        
        for category, patterns in HINGLISH_PATTERNS.items():
            for pattern in patterns:
                if pattern in lower_text:
                    score += 1
                    detected.append(f"{category}:{pattern}")
        
        return score, detected
    
    def detect_language(self, text: str) -> LanguageDetectionResult:
        """
        Detect the language of input text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            LanguageDetectionResult with detection details
        """
        # First, check for non-Latin scripts
        script, script_confidence = self.detect_script(text)
        
        if script == 'devanagari':
            # Could be Hindi or Marathi
            return LanguageDetectionResult(
                primary_language=Language.HINDI,
                script='devanagari',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'bengali':
            return LanguageDetectionResult(
                primary_language=Language.BENGALI,
                script='bengali',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'tamil':
            return LanguageDetectionResult(
                primary_language=Language.TAMIL,
                script='tamil',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'telugu':
            return LanguageDetectionResult(
                primary_language=Language.TELUGU,
                script='telugu',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'gujarati':
            return LanguageDetectionResult(
                primary_language=Language.GUJARATI,
                script='gujarati',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'kannada':
            return LanguageDetectionResult(
                primary_language=Language.KANNADA,
                script='kannada',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'malayalam':
            return LanguageDetectionResult(
                primary_language=Language.MALAYALAM,
                script='malayalam',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'gurmukhi':
            return LanguageDetectionResult(
                primary_language=Language.PUNJABI,
                script='gurmukhi',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        if script == 'arabic':
            return LanguageDetectionResult(
                primary_language=Language.URDU,
                script='arabic',
                is_romanized=False,
                confidence=script_confidence,
                detected_patterns=[]
            )
        
        # Latin script - check for Hinglish
        hinglish_score, detected_patterns = self.detect_hinglish_patterns(text)
        
        if hinglish_score >= 2:
            confidence = min(0.5 + (hinglish_score * 0.1), 0.95)
            return LanguageDetectionResult(
                primary_language=Language.HINGLISH,
                script='latin',
                is_romanized=True,
                confidence=confidence,
                detected_patterns=detected_patterns
            )
        
        # Default to English
        return LanguageDetectionResult(
            primary_language=Language.ENGLISH,
            script='latin',
            is_romanized=False,
            confidence=0.7,
            detected_patterns=[]
        )
    
    def get_system_prompt(self, language: Language) -> str:
        """Get the system prompt for a specific language."""
        config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS[Language.ENGLISH])
        return config['system_prompt']
    
    def translate_response(
        self,
        response: str,
        target_language: Language,
        keep_technical: bool = True
    ) -> str:
        """
        Translate a response to the target language.
        
        Args:
            response: The response to translate
            target_language: Target language
            keep_technical: Keep technical terms in English
            
        Returns:
            Translated response
        """
        if target_language == Language.ENGLISH:
            return response
        
        self._ensure_client()
        
        lang_config = LANGUAGE_CONFIGS.get(target_language, LANGUAGE_CONFIGS[Language.ENGLISH])
        
        prompt = f"""Translate the following text to {lang_config['name']}.

RULES:
- {"Keep technical terms, product names, and numbers in English" if keep_technical else "Translate everything"}
- {"Use romanized script (Latin letters)" if target_language == Language.HINGLISH else f"Use {lang_config['script']} script"}
- Keep the meaning and tone intact
- Be natural and conversational

TEXT TO TRANSLATE:
{response}

TRANSLATION:"""

        try:
            result = self.client.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=500
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return response
    
    def set_user_preference(self, user_id: str, language: Language) -> None:
        """Set a user's language preference."""
        self.user_language_preferences[user_id] = language
    
    def get_user_preference(self, user_id: str) -> Language:
        """Get a user's language preference (defaults to English)."""
        return self.user_language_preferences.get(user_id, Language.ENGLISH)
    
    def format_response(
        self,
        response: str,
        detected_language: Language,
        user_id: Optional[str] = None
    ) -> str:
        """
        Format response in the appropriate language.
        
        Args:
            response: The base response (usually in English)
            detected_language: Language detected from user input
            user_id: Optional user ID for preference lookup
            
        Returns:
            Response formatted in the target language
        """
        # Use detected language or user preference
        target_language = detected_language
        if user_id and user_id in self.user_language_preferences:
            target_language = self.user_language_preferences[user_id]
        
        if target_language == Language.ENGLISH:
            return response
        
        return self.translate_response(response, target_language)
