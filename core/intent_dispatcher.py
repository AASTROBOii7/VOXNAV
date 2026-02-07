"""
Intent Dispatcher - Classifies user voice input into intent categories using OpenRouter.
Enhanced with improved prompts and few-shot examples for better accuracy.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Supported intent categories."""
    BOOKING = "BOOKING"
    SEARCH = "SEARCH"
    NAVIGATION = "NAVIGATION"
    FORM_FILL = "FORM_FILL"
    GENERAL_INFO = "GENERAL_INFO"
    CANCEL = "CANCEL"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    sub_intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    original_query: str = ""
    language_detected: str = "en"
    raw_response: Optional[str] = None


# Enhanced few-shot examples for better accuracy
FEW_SHOT_EXAMPLES = [
    # BOOKING examples
    {"input": "Book a train ticket from Delhi to Mumbai", 
     "output": {"intent": "BOOKING", "confidence": 0.98, "sub_intent": "train_ticket", "entities": {"source": "Delhi", "destination": "Mumbai"}, "language_detected": "en"}},
    {"input": "Mujhe Delhi se Mumbai ki train book karni hai",
     "output": {"intent": "BOOKING", "confidence": 0.97, "sub_intent": "train_ticket", "entities": {"source": "Delhi", "destination": "Mumbai"}, "language_detected": "hinglish"}},
    {"input": "Flight book karo Bangalore to Chennai",
     "output": {"intent": "BOOKING", "confidence": 0.96, "sub_intent": "flight", "entities": {"source": "Bangalore", "destination": "Chennai"}, "language_detected": "hinglish"}},
    {"input": "Book a cab to airport",
     "output": {"intent": "BOOKING", "confidence": 0.98, "sub_intent": "cab", "entities": {"destination": "airport"}, "language_detected": "en"}},
    {"input": "Zomato pe pizza order karo",
     "output": {"intent": "BOOKING", "confidence": 0.95, "sub_intent": "food_order", "entities": {"platform": "Zomato", "item": "pizza"}, "language_detected": "hinglish"}},
    {"input": "Hotel book karo Goa mein next week",
     "output": {"intent": "BOOKING", "confidence": 0.96, "sub_intent": "hotel", "entities": {"location": "Goa", "date": "next week"}, "language_detected": "hinglish"}},
    {"input": "Swiggy se biryani mangao",
     "output": {"intent": "BOOKING", "confidence": 0.94, "sub_intent": "food_order", "entities": {"platform": "Swiggy", "item": "biryani"}, "language_detected": "hinglish"}},
    
    # SEARCH examples  
    {"input": "Mujhe Bangalore ka weather batao",
     "output": {"intent": "SEARCH", "confidence": 0.97, "sub_intent": "weather", "entities": {"location": "Bangalore"}, "language_detected": "hinglish"}},
    {"input": "Amazon pe iPhone search karo",
     "output": {"intent": "SEARCH", "confidence": 0.96, "sub_intent": "product", "entities": {"query": "iPhone", "platform": "Amazon"}, "language_detected": "hinglish"}},
    {"input": "Flipkart pe mobile search karo",
     "output": {"intent": "SEARCH", "confidence": 0.95, "sub_intent": "product", "entities": {"query": "mobile", "platform": "Flipkart"}, "language_detected": "hinglish"}},
    {"input": "Weather check karo Mumbai ka",
     "output": {"intent": "SEARCH", "confidence": 0.96, "sub_intent": "weather", "entities": {"location": "Mumbai"}, "language_detected": "hinglish"}},
    {"input": "What is the news today",
     "output": {"intent": "SEARCH", "confidence": 0.94, "sub_intent": "news", "entities": {"query": "today's news"}, "language_detected": "en"}},
    {"input": "Find restaurants near me",
     "output": {"intent": "SEARCH", "confidence": 0.95, "sub_intent": "location", "entities": {"query": "restaurants", "location": "near me"}, "language_detected": "en"}},
    {"input": "Google pe Python tutorial search karo",
     "output": {"intent": "SEARCH", "confidence": 0.95, "sub_intent": "general_search", "entities": {"query": "Python tutorial", "platform": "Google"}, "language_detected": "hinglish"}},
    
    # NAVIGATION examples
    {"input": "Go to settings page",
     "output": {"intent": "NAVIGATION", "confidence": 0.97, "sub_intent": "go_to_page", "entities": {"target": "settings"}, "language_detected": "en"}},
    {"input": "Open my profile",
     "output": {"intent": "NAVIGATION", "confidence": 0.96, "sub_intent": "go_to_page", "entities": {"target": "profile"}, "language_detected": "en"}},
    {"input": "Scroll down",
     "output": {"intent": "NAVIGATION", "confidence": 0.98, "sub_intent": "scroll", "entities": {"direction": "down"}, "language_detected": "en"}},
    {"input": "Click on submit button",
     "output": {"intent": "NAVIGATION", "confidence": 0.97, "sub_intent": "click_element", "entities": {"target": "submit button"}, "language_detected": "en"}},
    
    # CANCEL examples
    {"input": "Cancel my booking",
     "output": {"intent": "CANCEL", "confidence": 0.98, "sub_intent": "cancel_booking", "entities": {}, "language_detected": "en"}},
    {"input": "Cancel karo",
     "output": {"intent": "CANCEL", "confidence": 0.97, "sub_intent": "abort_action", "entities": {}, "language_detected": "hinglish"}},
    {"input": "Go back",
     "output": {"intent": "CANCEL", "confidence": 0.95, "sub_intent": "go_back", "entities": {}, "language_detected": "en"}},
    {"input": "Abort this",
     "output": {"intent": "CANCEL", "confidence": 0.96, "sub_intent": "abort_action", "entities": {}, "language_detected": "en"}},
    {"input": "Ruk jao",
     "output": {"intent": "CANCEL", "confidence": 0.94, "sub_intent": "abort_action", "entities": {}, "language_detected": "hinglish"}},
    
    # HELP examples
    {"input": "Help me",
     "output": {"intent": "HELP", "confidence": 0.98, "sub_intent": "how_to", "entities": {}, "language_detected": "en"}},
    {"input": "Tum kya kya kar sakte ho",
     "output": {"intent": "HELP", "confidence": 0.96, "sub_intent": "what_can_you_do", "entities": {}, "language_detected": "hinglish"}},
    {"input": "What can you do",
     "output": {"intent": "HELP", "confidence": 0.97, "sub_intent": "what_can_you_do", "entities": {}, "language_detected": "en"}},
    {"input": "How do I book a ticket",
     "output": {"intent": "HELP", "confidence": 0.95, "sub_intent": "how_to", "entities": {"topic": "book a ticket"}, "language_detected": "en"}},
    
    # FORM_FILL examples
    {"input": "Fill my email as test@example.com",
     "output": {"intent": "FORM_FILL", "confidence": 0.96, "sub_intent": "fill_field", "entities": {"field": "email", "value": "test@example.com"}, "language_detected": "en"}},
    {"input": "Login karo",
     "output": {"intent": "FORM_FILL", "confidence": 0.94, "sub_intent": "login", "entities": {}, "language_detected": "hinglish"}},
    {"input": "Sign up for account",
     "output": {"intent": "FORM_FILL", "confidence": 0.95, "sub_intent": "signup", "entities": {}, "language_detected": "en"}},
    
    # GENERAL_INFO examples
    {"input": "Thank you",
     "output": {"intent": "GENERAL_INFO", "confidence": 0.97, "sub_intent": "thanks", "entities": {}, "language_detected": "en"}},
    {"input": "Hello",
     "output": {"intent": "GENERAL_INFO", "confidence": 0.98, "sub_intent": "greeting", "entities": {}, "language_detected": "en"}},
    {"input": "Dhanyawad",
     "output": {"intent": "GENERAL_INFO", "confidence": 0.96, "sub_intent": "thanks", "entities": {}, "language_detected": "hi"}},
]


# Keywords for quick local classification (improves speed and accuracy)
INTENT_KEYWORDS = {
    Intent.BOOKING: [
        "book", "reserve", "order", "ticket", "flight", "train", "bus", "cab", "taxi", 
        "hotel", "appointment", "table", "mangao", "order karo", "book karo", "book karni",
        "booking", "reservation", "zomato", "swiggy", "uber", "ola", "makemytrip", "irctc"
    ],
    Intent.SEARCH: [
        "search", "find", "look", "weather", "news", "show", "batao", "dikha", "kya hai",
        "where", "kahan", "location", "check", "search karo", "dekho", "pata karo",
        "amazon", "flipkart", "google", "youtube"
    ],
    Intent.NAVIGATION: [
        "go to", "open", "navigate", "scroll", "click", "tap", "press", "jao", "kholo",
        "page", "section", "menu", "back", "forward", "home"
    ],
    Intent.CANCEL: [
        "cancel", "stop", "abort", "go back", "undo", "ruk", "band karo", "cancel karo",
        "nahi chahiye", "mat karo", "delete", "remove"
    ],
    Intent.HELP: [
        "help", "assist", "how to", "what can", "kaise", "kya kar sakte", "madad",
        "explain", "guide", "tutorial", "sahayata"
    ],
    Intent.FORM_FILL: [
        "fill", "login", "sign up", "signup", "register", "form", "submit",
        "enter", "type", "likho", "bharo"
    ],
    Intent.GENERAL_INFO: [
        "thank", "thanks", "hello", "hi", "bye", "good", "ok", "okay", "fine",
        "dhanyawad", "shukriya", "namaste", "theek", "accha"
    ]
}


def build_intent_prompt() -> str:
    """Build the enhanced intent classification prompt with few-shot examples."""
    examples_text = "\n".join([
        f'Input: "{ex["input"]}"\nOutput: {json.dumps(ex["output"])}\n'
        for ex in FEW_SHOT_EXAMPLES[:15]  # Use top 15 examples
    ])
    
    return f"""You are an Intent Classifier for VoxNav, a voice-activated assistant for Indian users.

TASK: Classify the user's input into exactly ONE intent category and extract relevant entities.

INTENT CATEGORIES:
1. BOOKING - Book/reserve tickets, hotels, food orders, appointments, cabs
   Sub-intents: train_ticket, flight, hotel, bus, cab, food_order, appointment, restaurant
2. SEARCH - Find information, products, weather, news, or lookup anything
   Sub-intents: weather, product, news, location, general_search
3. NAVIGATION - Navigate to pages, scroll, click elements
   Sub-intents: go_to_page, scroll, click_element
4. FORM_FILL - Fill forms, login, signup, enter data
   Sub-intents: login, signup, fill_field, payment
5. CANCEL - Cancel, abort, stop, go back
   Sub-intents: cancel_booking, abort_action, go_back
6. HELP - Ask for help, capabilities, or guidance
   Sub-intents: how_to, what_can_you_do, explain
7. GENERAL_INFO - Greetings, thanks, casual chat
   Sub-intents: greeting, thanks, chitchat, clarification

LANGUAGE CODES: en (English), hi (Hindi), hinglish (Hindi-English mix), ta, te, bn, mr, gu, kn, ml, pa, or, ur

EXAMPLES:
{examples_text}

RULES:
1. Return ONLY valid JSON, no markdown or extra text
2. Set confidence between 0.85-0.99 based on clarity
3. Extract ALL relevant entities (source, destination, date, location, query, platform, item)
4. For food orders (Zomato, Swiggy), use BOOKING with sub_intent "food_order"
5. For product searches (Amazon, Flipkart), use SEARCH with sub_intent "product"
6. Detect language accurately (hinglish if mixed Hindi-English)

RESPONSE FORMAT:
{{"intent": "INTENT_NAME", "confidence": 0.XX, "sub_intent": "sub_intent_name", "entities": {{}}, "language_detected": "code"}}

Now classify this input:"""


class IntentDispatcher:
    """
    Dispatches user voice input to appropriate intent handlers using OpenRouter.
    Enhanced with keyword matching and improved prompt engineering.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Intent Dispatcher.
        
        Args:
            api_key: OpenRouter API key (optional, uses env var if not provided)
        """
        self.api_key = api_key
        self.client = None
        
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
        logger.info("OpenRouter client initialized successfully.")
    
    def _quick_classify(self, user_input: str) -> Optional[Intent]:
        """
        Quick keyword-based classification for common patterns.
        Returns None if no confident match, otherwise returns the intent.
        """
        text = user_input.lower()
        
        # Score each intent based on keyword matches
        scores = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[intent] = score
        
        if not scores:
            return None
        
        # Get the intent with highest score
        best_intent = max(scores, key=scores.get)
        
        # Only return if score is significantly higher than others
        if scores[best_intent] >= 2:
            return best_intent
        
        return None
    
    def _detect_language(self, text: str) -> str:
        """Quick language detection based on script and keywords."""
        # Check for Devanagari (Hindi)
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        # Check for Tamil
        if re.search(r'[\u0B80-\u0BFF]', text):
            return "ta"
        # Check for Telugu  
        if re.search(r'[\u0C00-\u0C7F]', text):
            return "te"
        # Check for Bengali
        if re.search(r'[\u0980-\u09FF]', text):
            return "bn"
        # Check for Hinglish (Hindi words in Latin script)
        hinglish_words = ["mujhe", "karo", "batao", "chahiye", "kya", "kaise", "hai", "hain", 
                         "karna", "karni", "aap", "tum", "yeh", "woh", "pe", "se", "ko", "ka", "ki", "ke"]
        if any(word in text.lower().split() for word in hinglish_words):
            return "hinglish"
        return "en"
    
    def classify(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        Classify user input into an intent category.
        
        Args:
            user_input: The transcribed voice input
            context: Optional context (current URL, page content, etc.)
            
        Returns:
            IntentResult with classified intent and extracted entities
        """
        self._ensure_client()
        
        # Quick language detection
        detected_lang = self._detect_language(user_input)
        
        # Build prompt
        prompt = build_intent_prompt()
        
        if context:
            context_str = f'\nContext: URL={context.get("url", "N/A")}, Page={context.get("page_title", "N/A")}\n'
            prompt += context_str
        
        prompt += f'\nInput: "{user_input}"'
        
        try:
            # Call OpenRouter
            raw_text = self.client.generate(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistency
                max_tokens=300
            )
            
            raw_text = raw_text.strip()
            
            # Clean markdown if present
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[1] if '\n' in raw_text else raw_text[3:]
                raw_text = raw_text.rsplit('```', 1)[0]
            
            # Remove any leading/trailing non-JSON content
            json_match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group()
            
            # Parse JSON response
            result = json.loads(raw_text)
            
            # Validate and convert intent
            intent_str = result.get("intent", "UNKNOWN").upper()
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.UNKNOWN
            
            return IntentResult(
                intent=intent,
                confidence=float(result.get("confidence", 0.5)),
                sub_intent=result.get("sub_intent"),
                entities=result.get("entities", {}),
                original_query=user_input,
                language_detected=result.get("language_detected", detected_lang),
                raw_response=raw_text
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Fall back to quick classification
            quick_intent = self._quick_classify(user_input)
            return IntentResult(
                intent=quick_intent or Intent.UNKNOWN,
                confidence=0.6 if quick_intent else 0.0,
                original_query=user_input,
                language_detected=detected_lang,
                raw_response=raw_text if 'raw_text' in locals() else None
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Fall back to quick classification
            quick_intent = self._quick_classify(user_input)
            return IntentResult(
                intent=quick_intent or Intent.UNKNOWN,
                confidence=0.5 if quick_intent else 0.0,
                original_query=user_input,
                language_detected=detected_lang
            )
    
    def get_sub_intents(self, intent: Intent) -> List[str]:
        """Get available sub-intents for a given intent category."""
        sub_intents = {
            Intent.BOOKING: ["train_ticket", "flight", "hotel", "bus", "cab", "food_order", "appointment", "restaurant"],
            Intent.SEARCH: ["weather", "product", "news", "location", "general_search"],
            Intent.NAVIGATION: ["go_to_page", "scroll", "click_element"],
            Intent.FORM_FILL: ["login", "signup", "fill_field", "payment"],
            Intent.CANCEL: ["cancel_booking", "abort_action", "go_back"],
            Intent.HELP: ["how_to", "what_can_you_do", "explain"],
            Intent.GENERAL_INFO: ["greeting", "thanks", "chitchat", "clarification"],
        }
        return sub_intents.get(intent, [])
