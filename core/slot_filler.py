"""
Slot Filler - Manages conversational slot filling for booking and form actions.
Asks follow-up questions when required information is missing.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class SlotStatus(Enum):
    """Status of slot filling process."""
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SlotResult:
    """Result of slot filling operation."""
    status: SlotStatus
    filled_slots: Dict[str, Any]
    missing_slots: List[str]
    next_question: Optional[str] = None
    next_slot: Optional[str] = None
    attempts: int = 0


@dataclass
class SlotDefinition:
    """Definition of a slot with validation and prompts."""
    name: str
    required: bool = True
    prompt_en: str = ""
    prompt_hi: str = ""
    prompt_hinglish: str = ""
    validators: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


# Slot definitions for different intents and sub-intents
SLOT_DEFINITIONS = {
    "BOOKING": {
        "train_ticket": {
            "required": ["source", "destination", "date"],
            "optional": ["class", "passengers", "time_preference", "quota"],
            "prompts": {
                "source": {
                    "en": "Where would you like to travel from?",
                    "hi": "आप कहाँ से यात्रा करना चाहते हैं?",
                    "hinglish": "Aap kahan se travel karna chahte ho?"
                },
                "destination": {
                    "en": "Where would you like to go?",
                    "hi": "आप कहाँ जाना चाहते हैं?",
                    "hinglish": "Aap kahan jaana chahte ho?"
                },
                "date": {
                    "en": "When do you want to travel?",
                    "hi": "आप कब यात्रा करना चाहते हैं?",
                    "hinglish": "Aap kab travel karna chahte ho?"
                },
                "class": {
                    "en": "Which class? (Sleeper, AC, General)",
                    "hi": "कौन सी श्रेणी? (स्लीपर, एसी, जनरल)",
                    "hinglish": "Kaun si class? (Sleeper, AC, General)"
                },
                "passengers": {
                    "en": "How many passengers?",
                    "hi": "कितने यात्री?",
                    "hinglish": "Kitne passengers?"
                }
            }
        },
        "flight": {
            "required": ["source", "destination", "date"],
            "optional": ["return_date", "passengers", "class", "airline_preference"],
            "prompts": {
                "source": {
                    "en": "Which city are you departing from?",
                    "hi": "आप किस शहर से निकल रहे हैं?",
                    "hinglish": "Aap kis city se nikal rahe ho?"
                },
                "destination": {
                    "en": "What's your destination city?",
                    "hi": "आपकी मंजिल कौन सा शहर है?",
                    "hinglish": "Aapki destination city kya hai?"
                },
                "date": {
                    "en": "What's your travel date?",
                    "hi": "आपकी यात्रा की तारीख क्या है?",
                    "hinglish": "Aapki travel date kya hai?"
                },
                "return_date": {
                    "en": "When do you want to return? (or say 'one way')",
                    "hi": "आप कब वापस आना चाहते हैं? (या 'एक तरफ़ा' बोलें)",
                    "hinglish": "Aap kab return karna chahte ho? (ya 'one way' bolo)"
                }
            }
        },
        "hotel": {
            "required": ["location", "checkin_date", "checkout_date"],
            "optional": ["guests", "rooms", "room_type", "budget", "amenities"],
            "prompts": {
                "location": {
                    "en": "Which city do you need a hotel in?",
                    "hi": "आपको किस शहर में होटल चाहिए?",
                    "hinglish": "Aapko kis city mein hotel chahiye?"
                },
                "checkin_date": {
                    "en": "When do you want to check in?",
                    "hi": "आप कब चेक-इन करना चाहते हैं?",
                    "hinglish": "Aap kab check-in karna chahte ho?"
                },
                "checkout_date": {
                    "en": "When will you check out?",
                    "hi": "आप कब चेक-आउट करेंगे?",
                    "hinglish": "Aap kab check-out karoge?"
                },
                "guests": {
                    "en": "How many guests?",
                    "hi": "कितने मेहमान?",
                    "hinglish": "Kitne guests?"
                }
            }
        },
        "cab": {
            "required": ["pickup", "drop"],
            "optional": ["time", "cab_type"],
            "prompts": {
                "pickup": {
                    "en": "Where should we pick you up?",
                    "hi": "हम आपको कहाँ से उठाएं?",
                    "hinglish": "Aapko kahan se pick karna hai?"
                },
                "drop": {
                    "en": "Where do you want to go?",
                    "hi": "आप कहाँ जाना चाहते हैं?",
                    "hinglish": "Aap kahan jaana chahte ho?"
                },
                "time": {
                    "en": "When do you need the cab?",
                    "hi": "आपको कैब कब चाहिए?",
                    "hinglish": "Cab kab chahiye aapko?"
                }
            }
        }
    },
    "SEARCH": {
        "weather": {
            "required": ["location"],
            "optional": ["date"],
            "prompts": {
                "location": {
                    "en": "Which city's weather do you want to know?",
                    "hi": "आप किस शहर का मौसम जानना चाहते हैं?",
                    "hinglish": "Kis city ka weather jaanna hai?"
                }
            }
        },
        "product": {
            "required": ["query"],
            "optional": ["platform", "price_range", "brand"],
            "prompts": {
                "query": {
                    "en": "What product are you looking for?",
                    "hi": "आप कौन सा प्रोडक्ट खोज रहे हैं?",
                    "hinglish": "Aap kya search kar rahe ho?"
                }
            }
        }
    }
}


class SlotFiller:
    """
    Manages slot filling for multi-turn conversations.
    Extracts required information and asks follow-up questions.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Slot Filler.
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.client = None
        self.sessions: Dict[str, Dict] = {}  # user_id -> session state
        
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
    
    def get_slot_config(self, intent: str, sub_intent: str) -> Optional[Dict]:
        """Get slot configuration for an intent/sub-intent pair."""
        return SLOT_DEFINITIONS.get(intent, {}).get(sub_intent)
    
    def _extract_slots_prompt(self, user_input: str, slot_config: Dict, filled_slots: Dict) -> str:
        """Build prompt for slot extraction."""
        return f"""Extract information from the user's message to fill the following slots.

REQUIRED SLOTS: {', '.join(slot_config['required'])}
OPTIONAL SLOTS: {', '.join(slot_config.get('optional', []))}

ALREADY FILLED: {json.dumps(filled_slots)}

USER MESSAGE: "{user_input}"

INSTRUCTIONS:
1. Extract only values explicitly mentioned by the user
2. Normalize dates (e.g., "tomorrow" -> actual date, "next Monday" -> actual date)
3. Keep location names as-is (in original language/script)
4. Return null for slots not mentioned

Respond with valid JSON only:
{{"source": "value or null", "destination": "value or null", "date": "YYYY-MM-DD or relative term", ...}}
"""

    async def extract_slots_async(
        self,
        user_id: str,
        user_input: str,
        intent: str,
        sub_intent: str,
        language: str = "en"
    ) -> SlotResult:
        """Async version of extract_slots."""
        return self.extract_slots(user_id, user_input, intent, sub_intent, language)
    
    def extract_slots(
        self,
        user_id: str,
        user_input: str,
        intent: str,
        sub_intent: str,
        language: str = "en"
    ) -> SlotResult:
        """
        Extract slots from user input and manage conversation state.
        
        Args:
            user_id: Unique user identifier
            user_input: The user's message
            intent: Intent category (e.g., "BOOKING")
            sub_intent: Sub-intent (e.g., "train_ticket")
            language: User's language for prompts
            
        Returns:
            SlotResult with current slot status and next question if needed
        """
        self._ensure_client()
        
        # Get slot configuration
        slot_config = self.get_slot_config(intent, sub_intent)
        if not slot_config:
            return SlotResult(
                status=SlotStatus.COMPLETE,
                filled_slots={},
                missing_slots=[]
            )
        
        # Get or create session
        session = self.sessions.get(user_id, {
            'intent': intent,
            'sub_intent': sub_intent,
            'filled_slots': {},
            'attempts': 0
        })
        
        # Build extraction prompt
        prompt = self._extract_slots_prompt(user_input, slot_config, session['filled_slots'])
        
        try:
            # Call OpenRouter for extraction
            raw_text = self.client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            raw_text = raw_text.strip()
            
            # Clean markdown if present
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[1]
                raw_text = raw_text.rsplit('```', 1)[0]
            
            extracted = json.loads(raw_text)
            
            # Merge with existing slots
            for key, value in extracted.items():
                if value is not None and value != "null":
                    session['filled_slots'][key] = value
            
            # Normalize dates
            session['filled_slots'] = self._normalize_dates(session['filled_slots'])
            
        except Exception as e:
            logger.error(f"Slot extraction failed: {e}")
            session['attempts'] += 1
        
        # Check which required slots are missing
        missing = [
            slot for slot in slot_config['required']
            if slot not in session['filled_slots'] or not session['filled_slots'][slot]
        ]
        
        # Update session
        session['attempts'] += 1
        self.sessions[user_id] = session
        
        if not missing:
            # All slots filled!
            self.clear_session(user_id)
            return SlotResult(
                status=SlotStatus.COMPLETE,
                filled_slots=session['filled_slots'],
                missing_slots=[],
                attempts=session['attempts']
            )
        
        # Get next question
        next_slot = missing[0]
        prompts = slot_config['prompts'].get(next_slot, {})
        
        # Select language-appropriate prompt
        if language in ['hi', 'hindi']:
            next_question = prompts.get('hi', prompts.get('en', f"Please provide {next_slot}"))
        elif language in ['hinglish']:
            next_question = prompts.get('hinglish', prompts.get('en', f"Please provide {next_slot}"))
        else:
            next_question = prompts.get('en', f"Please provide {next_slot}")
        
        return SlotResult(
            status=SlotStatus.INCOMPLETE,
            filled_slots=session['filled_slots'],
            missing_slots=missing,
            next_question=next_question,
            next_slot=next_slot,
            attempts=session['attempts']
        )
    
    def _normalize_dates(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize relative date expressions to actual dates."""
        date_fields = ['date', 'checkin_date', 'checkout_date', 'return_date', 'travel_date']
        today = datetime.now()
        
        for field in date_fields:
            if field in slots and slots[field]:
                value = str(slots[field]).lower().strip()
                
                if value in ['today', 'aaj', 'आज']:
                    slots[field] = today.strftime('%Y-%m-%d')
                elif value in ['tomorrow', 'kal', 'कल']:
                    slots[field] = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                elif value in ['day after tomorrow', 'parso', 'परसों']:
                    slots[field] = (today + timedelta(days=2)).strftime('%Y-%m-%d')
                elif 'next week' in value:
                    slots[field] = (today + timedelta(weeks=1)).strftime('%Y-%m-%d')
                # Keep other dates as-is (assume they're already formatted or will be parsed later)
        
        return slots
    
    def clear_session(self, user_id: str) -> None:
        """Clear a user's slot filling session."""
        if user_id in self.sessions:
            del self.sessions[user_id]
    
    def get_session(self, user_id: str) -> Optional[Dict]:
        """Get current session state for a user."""
        return self.sessions.get(user_id)
    
    def has_active_session(self, user_id: str) -> bool:
        """Check if user has an active slot filling session."""
        return user_id in self.sessions
