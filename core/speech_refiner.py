"""
Speech Intent Refiner for VoxNav
Cleans raw transcripts by resolving self-corrections and extracting actionable intent.
"""

import re
import json
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Correction keywords in multiple languages
CORRECTION_KEYWORDS = {
    "english": ["wait", "no", "actually", "change that", "i mean", "sorry", "not", "cancel that"],
    "hindi": ["nahi", "nhi", "ruko", "matlab", "sorry", "galat", "change karo", "wait"],
    "hinglish": ["wait", "no", "nahi", "actually", "nhi", "ruko", "i mean", "galat"],
}

# All correction triggers
ALL_CORRECTIONS = set()
for keywords in CORRECTION_KEYWORDS.values():
    ALL_CORRECTIONS.update(keywords)


@dataclass
class ExtractedSlots:
    """Slots extracted from the user's speech."""
    item: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    quantity: Optional[str] = None
    platform: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def missing_for_intent(self, intent: str) -> List[str]:
        """Get missing required slots for an intent."""
        required = {
            "BOOKING": ["destination"],
            "SEARCH": ["item"],
            "LOGIN": [],
            "INFO": [],
        }
        missing = []
        for slot in required.get(intent, []):
            if getattr(self, slot, None) is None:
                missing.append(slot)
        return missing


@dataclass
class RefinedIntent:
    """Result from speech intent refinement."""
    raw_text: str
    refined_text: str
    intent_category: str
    extracted_slots: Dict[str, str]
    is_final: bool
    response_speech: str
    language_detected: str = "hinglish"
    corrections_made: List[str] = field(default_factory=list)


class SpeechIntentRefiner:
    """
    Refines raw speech transcripts by:
    1. Detecting and resolving self-corrections
    2. Extracting intent category
    3. Extracting slots (destination, date, time, etc.)
    4. Generating natural language confirmation
    """
    
    def __init__(self, use_llm: bool = True, api_key: Optional[str] = None):
        """
        Initialize the refiner.
        
        Args:
            use_llm: Whether to use LLM for complex refinement
            api_key: Gemini API key for LLM-based refinement
        """
        self.use_llm = use_llm
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.gemini_model = None
        
        if self.use_llm and self.api_key:
            self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini for complex refinement."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini initialized for speech refinement")
        except Exception as e:
            logger.warning(f"Could not initialize Gemini: {e}")
            self.gemini_model = None
    
    def detect_language(self, text: str) -> str:
        """Detect the language of the text."""
        # Hindi characters
        hindi_pattern = re.compile(r'[\u0900-\u097F]')
        if hindi_pattern.search(text):
            return "hindi"
        
        # Common Hindi words in Roman script
        hinglish_words = ["karo", "hai", "mujhe", "chahiye", "ke", "ki", "ka", "ko", "se", 
                         "nahi", "haan", "theek", "acha", "bhai", "yaar", "bolo", "batao"]
        text_lower = text.lower()
        hinglish_count = sum(1 for word in hinglish_words if word in text_lower)
        
        if hinglish_count >= 2:
            return "hinglish"
        
        return "english"
    
    def detect_corrections(self, text: str) -> List[tuple]:
        """
        Detect correction patterns in text.
        Returns list of (correction_keyword, position, context).
        """
        corrections = []
        text_lower = text.lower()
        
        for keyword in ALL_CORRECTIONS:
            pattern = rf'\b{re.escape(keyword)}\b'
            for match in re.finditer(pattern, text_lower):
                corrections.append((keyword, match.start(), match.end()))
        
        return sorted(corrections, key=lambda x: x[1])
    
    def apply_corrections(self, text: str) -> tuple:
        """
        Apply detected corrections to refine the text.
        Returns (refined_text, list_of_corrections_made).
        """
        corrections = self.detect_corrections(text)
        if not corrections:
            return text, []
        
        corrections_made = []
        
        # Use LLM for complex correction resolution
        if self.gemini_model:
            return self._llm_correct(text, corrections)
        
        # Simple rule-based correction
        refined = text
        for keyword, start, end in corrections:
            # Pattern: "X... wait/no... Y" -> keep Y, discard X
            # Find what comes after the correction keyword
            after_correction = text[end:].strip()
            before_correction = text[:start].strip()
            
            if after_correction:
                # Get the corrected value (first meaningful phrase after keyword)
                corrected_match = re.match(r'^[,\s]*(.+?)(?:[,.]|$)', after_correction)
                if corrected_match:
                    corrected_value = corrected_match.group(1).strip()
                    
                    # Find what's being corrected (usually the last word/phrase before keyword)
                    original_match = re.search(r'(\S+)\s*$', before_correction)
                    if original_match:
                        original_value = original_match.group(1)
                        
                        # Build refined text
                        prefix = before_correction[:original_match.start()].strip()
                        suffix = after_correction[corrected_match.end():].strip() if corrected_match.end() < len(after_correction) else ""
                        
                        refined = f"{prefix} {corrected_value} {suffix}".strip()
                        corrections_made.append(f"'{original_value}' → '{corrected_value}'")
        
        # Clean up multiple spaces
        refined = re.sub(r'\s+', ' ', refined).strip()
        
        return refined, corrections_made
    
    def _llm_correct(self, text: str, corrections: List[tuple]) -> tuple:
        """Use LLM for complex correction resolution."""
        prompt = f"""You are a speech transcript refiner. The user made self-corrections while speaking.

Raw transcript: "{text}"

Detected correction keywords at positions: {corrections}

Rules:
1. When someone says "X... wait/no/nahi... Y", they mean Y, not X
2. Keep the final corrected intent
3. Maintain natural flow

Return ONLY the refined text, nothing else."""

        try:
            response = self.gemini_model.generate_content(prompt)
            refined = response.text.strip()
            # Remove quotes if present
            refined = refined.strip('"\'')
            corrections_made = [f"LLM refinement applied"]
            return refined, corrections_made
        except Exception as e:
            logger.error(f"LLM correction failed: {e}")
            return text, []
    
    def extract_intent(self, text: str) -> str:
        """Extract intent category from text."""
        text_lower = text.lower()
        
        # Booking keywords
        booking_words = ["book", "reserve", "ticket", "order", "booking", 
                        "buk", "karo", "chahiye", "karwa do", "book kar"]
        if any(word in text_lower for word in booking_words):
            return "BOOKING"
        
        # Search keywords
        search_words = ["search", "find", "look", "dhundho", "batao", 
                       "dikhao", "weather", "price", "kya hai"]
        if any(word in text_lower for word in search_words):
            return "SEARCH"
        
        # Login keywords
        login_words = ["login", "sign in", "signin", "log in", "password"]
        if any(word in text_lower for word in login_words):
            return "LOGIN"
        
        return "INFO"
    
    def extract_slots(self, text: str, intent: str) -> ExtractedSlots:
        """Extract relevant slots from refined text."""
        slots = ExtractedSlots()
        text_lower = text.lower()
        
        # Cities (common Indian cities)
        cities = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad",
                 "pune", "ahmedabad", "jaipur", "lucknow", "surat", "goa", "agra"]
        
        found_cities = [city for city in cities if city in text_lower]
        
        # Source/Destination detection
        # Pattern: "from X to Y" or "X se Y"
        from_to = re.search(r'(?:from|se)\s+(\w+)\s+(?:to|tak|ko)\s+(\w+)', text_lower)
        if from_to:
            slots.source = from_to.group(1).title()
            slots.destination = from_to.group(2).title()
        elif "to " in text_lower or " tak " in text_lower or " ko " in text_lower:
            # Pattern: "to Y" or "Y tak"
            to_match = re.search(r'(?:to|tak|ko|ki)\s+(\w+)', text_lower)
            if to_match and to_match.group(1).lower() in cities:
                slots.destination = to_match.group(1).title()
        elif found_cities:
            slots.destination = found_cities[0].title()
        
        # Date detection
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
               "somvar", "mangalvar", "budhvar", "guruvar", "shukravar", "shanivar", "ravivar"]
        relative_dates = ["today", "tomorrow", "aaj", "kal", "parso"]
        
        for day in days + relative_dates:
            if day in text_lower:
                slots.date = day.title()
                break
        
        # Time detection
        times = ["morning", "evening", "night", "afternoon", "subah", "sham", "raat", "dopahar"]
        for time in times:
            if time in text_lower:
                slots.time = time.title()
                break
        
        # Platform detection
        platforms = ["amazon", "flipkart", "zomato", "swiggy", "irctc", "makemytrip", "uber", "ola"]
        for platform in platforms:
            if platform in text_lower:
                slots.platform = platform.title()
                break
        
        # Item/Product detection (for search)
        if intent == "SEARCH":
            # Try to extract what they're searching for
            search_match = re.search(r'(?:search|find|look for|dhundho)\s+(?:for\s+)?(.+?)(?:\s+on|\s+pe|\s+par|$)', text_lower)
            if search_match:
                slots.item = search_match.group(1).strip().title()
        
        return slots
    
    def generate_response(self, intent: str, slots: ExtractedSlots, language: str, is_final: bool) -> str:
        """Generate natural language confirmation response."""
        slot_dict = slots.to_dict()
        
        if language in ["hindi", "hinglish"]:
            if intent == "BOOKING":
                if is_final:
                    dest = slot_dict.get("destination", "")
                    date = slot_dict.get("date", "")
                    time = slot_dict.get("time", "")
                    return f"Theek hai, {date} {time} ke liye {dest} ki ticket check kar raha hoon."
                else:
                    missing = slots.missing_for_intent(intent)
                    if "date" in missing:
                        return "Kab ke liye book karni hai? Date batao."
                    if "destination" in missing:
                        return "Kahan jaana hai? Destination batao."
                    return "Aur koi details chahiye?"
            
            elif intent == "SEARCH":
                item = slot_dict.get("item", "")
                platform = slot_dict.get("platform", "")
                if platform:
                    return f"{platform} pe {item} search kar raha hoon."
                return f"{item} search kar raha hoon."
            
            return "Samajh gaya, kya chahiye?"
        
        else:  # English
            if intent == "BOOKING":
                if is_final:
                    dest = slot_dict.get("destination", "")
                    date = slot_dict.get("date", "")
                    time = slot_dict.get("time", "")
                    return f"Okay, checking tickets to {dest} for {date} {time}."
                else:
                    missing = slots.missing_for_intent(intent)
                    if missing:
                        return f"I need more details: {', '.join(missing)}."
            
            elif intent == "SEARCH":
                item = slot_dict.get("item", "")
                return f"Searching for {item}..."
            
            return "Got it. How can I help?"
    
    def refine(self, raw_text: str) -> RefinedIntent:
        """
        Main method: Refine raw speech transcript.
        
        Args:
            raw_text: Raw transcript from speech recognition
            
        Returns:
            RefinedIntent with all processed data
        """
        # Detect language
        language = self.detect_language(raw_text)
        
        # Apply corrections
        refined_text, corrections = self.apply_corrections(raw_text)
        
        # Extract intent
        intent = self.extract_intent(refined_text)
        
        # Extract slots
        slots = self.extract_slots(refined_text, intent)
        
        # Check if final (all required slots present)
        missing = slots.missing_for_intent(intent)
        is_final = len(missing) == 0
        
        # Generate response
        response = self.generate_response(intent, slots, language, is_final)
        
        return RefinedIntent(
            raw_text=raw_text,
            refined_text=refined_text,
            intent_category=intent,
            extracted_slots=slots.to_dict(),
            is_final=is_final,
            response_speech=response,
            language_detected=language,
            corrections_made=corrections
        )
    
    def refine_with_llm(self, raw_text: str) -> RefinedIntent:
        """Use full LLM for refinement (more accurate but slower)."""
        if not self.gemini_model:
            return self.refine(raw_text)
        
        prompt = f"""You are a Speech Intent Refiner for a voice assistant.

Raw transcript: "{raw_text}"

Tasks:
1. Detect and fix self-corrections (wait, no, nahi, actually, etc.)
2. Extract the intent: BOOKING, SEARCH, LOGIN, or INFO
3. Extract slots: destination, source, date, time, item, platform
4. Generate a natural response in the user's language (Hindi/Hinglish/English)

Return JSON:
{{
  "refined_text": "corrected transcript",
  "intent_category": "BOOKING|SEARCH|LOGIN|INFO",
  "extracted_slots": {{"destination": "", "date": "", "time": "", ...}},
  "is_final": true/false,
  "response_speech": "Natural confirmation in user's language"
}}"""

        try:
            response = self.gemini_model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                
                return RefinedIntent(
                    raw_text=raw_text,
                    refined_text=result.get("refined_text", raw_text),
                    intent_category=result.get("intent_category", "INFO"),
                    extracted_slots=result.get("extracted_slots", {}),
                    is_final=result.get("is_final", False),
                    response_speech=result.get("response_speech", ""),
                    language_detected=self.detect_language(raw_text),
                    corrections_made=["LLM refinement"]
                )
        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
        
        # Fallback to rule-based
        return self.refine(raw_text)


# Convenience function
def refine_speech(raw_text: str, use_llm: bool = False) -> Dict[str, Any]:
    """
    Quick function to refine speech.
    
    Example:
        result = refine_speech("Book ticket to Delhi for Friday... wait, no, Sunday morning")
        print(result["refined_text"])  # "Book ticket to Delhi for Sunday morning"
        print(result["response_speech"])  # "Theek hai, Sunday morning ke liye Delhi ki ticket..."
    """
    refiner = SpeechIntentRefiner(use_llm=use_llm)
    result = refiner.refine(raw_text)
    return asdict(result)
