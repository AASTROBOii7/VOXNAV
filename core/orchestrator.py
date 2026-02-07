"""
VoxNav Orchestrator - Main entry point that coordinates all components.
"""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .asr import ASREngine
from .intent_dispatcher import IntentDispatcher, Intent, IntentResult
from .slot_filler import SlotFiller, SlotResult, SlotStatus
from .dynamic_prompts import DynamicPromptBuilder
from .multilingual import MultilingualHandler, Language

logger = logging.getLogger(__name__)


@dataclass
class VoxNavResponse:
    """Response from VoxNav processing."""
    
    # Response type
    response_type: str  # 'question', 'action', 'response', 'error'
    
    # The message to speak/display to user
    message: str
    
    # Language of response
    language: str
    
    # If action type, the automation commands
    actions: Optional[list] = None
    
    # Detected intent
    intent: Optional[str] = None
    sub_intent: Optional[str] = None
    
    # Filled slots
    slots: Optional[Dict[str, Any]] = None
    
    # If asking a question, which slot we're filling
    awaiting_slot: Optional[str] = None
    
    # Original transcription
    transcription: Optional[str] = None
    
    # Confidence scores
    asr_confidence: Optional[float] = None
    intent_confidence: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'response_type': self.response_type,
            'message': self.message,
            'language': self.language,
            'actions': self.actions,
            'intent': self.intent,
            'sub_intent': self.sub_intent,
            'slots': self.slots,
            'awaiting_slot': self.awaiting_slot,
            'transcription': self.transcription,
            'asr_confidence': self.asr_confidence,
            'intent_confidence': self.intent_confidence
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class VoxNavOrchestrator:
    """
    Main orchestrator that coordinates ASR, Intent Classification,
    Slot Filling, and Response Generation.
    """
    
    def __init__(
        self,
        asr_model_path: str = "hindi_models/whisper-medium-hi_alldata_multigpu",
        asr_device: str = "cuda",
        openrouter_api_key: Optional[str] = None,
        default_language: str = "hi",
        lazy_load: bool = True
    ):
        """
        Initialize the VoxNav Orchestrator.
        
        Args:
            asr_model_path: Path to the IndicWhisper model
            asr_device: Device for ASR ("cuda" or "cpu")
            openrouter_api_key: OpenRouter API key
            default_language: Default ASR language
            lazy_load: If True, load models on first use
        """
        self.openrouter_api_key = openrouter_api_key
        
        # Initialize components
        self.asr = ASREngine(
            model_path=asr_model_path,
            device=asr_device,
            default_language=default_language
        )
        
        self.intent_dispatcher = IntentDispatcher(api_key=openrouter_api_key)
        self.slot_filler = SlotFiller(api_key=openrouter_api_key)
        self.prompt_builder = DynamicPromptBuilder()
        self.multilingual = MultilingualHandler(api_key=openrouter_api_key)
        
        # User sessions
        self.sessions: Dict[str, Dict] = {}
        
        # OpenRouter client for general responses
        self.openrouter_client = None
        
        if not lazy_load:
            self._load_models()
    
    def _load_models(self):
        """Load all models."""
        self.asr.load_model()
        self._ensure_openrouter()
    
    def _ensure_openrouter(self):
        """Ensure OpenRouter client is loaded."""
        if self.openrouter_client is not None:
            return
            
        from .openrouter_client import OpenRouterClient
        import os
        
        api_key = self.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not provided. Set OPENROUTER_API_KEY env variable.")
        
        self.openrouter_client = OpenRouterClient(api_key=api_key)
    
    def process_audio(
        self,
        audio_input,
        user_id: str,
        current_url: Optional[str] = None,
        page_html: Optional[str] = None,
        language: Optional[str] = None
    ) -> VoxNavResponse:
        """
        Process audio input end-to-end.
        
        Args:
            audio_input: Audio file path, bytes, or numpy array
            user_id: Unique user identifier
            current_url: Current webpage URL (for context)
            page_html: Current page HTML (for context)
            language: Language hint for ASR
            
        Returns:
            VoxNavResponse with result
        """
        try:
            # Step 1: Transcribe audio
            asr_result = self.asr.transcribe(audio_input, language=language)
            transcription = asr_result['text']
            
            logger.info(f"Transcription: {transcription}")
            
            # Step 2: Process the text
            return self.process_text(
                text_input=transcription,
                user_id=user_id,
                current_url=current_url,
                page_html=page_html,
                transcription=transcription
            )
            
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return VoxNavResponse(
                response_type='error',
                message=f"Sorry, I couldn't process that audio. Please try again.",
                language='en'
            )
    
    def process_text(
        self,
        text_input: str,
        user_id: str,
        current_url: Optional[str] = None,
        page_html: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> VoxNavResponse:
        """
        Process text input (transcribed or direct text).
        
        Args:
            text_input: The user's text input
            user_id: Unique user identifier
            current_url: Current webpage URL
            page_html: Current page HTML
            transcription: Original transcription (if from audio)
            
        Returns:
            VoxNavResponse with result
        """
        try:
            # Step 1: Detect language
            lang_result = self.multilingual.detect_language(text_input)
            detected_lang = lang_result.primary_language
            
            logger.info(f"Detected language: {detected_lang.value}")
            
            # Step 2: Check if we're in the middle of slot filling
            session = self.sessions.get(user_id)
            
            if session and session.get('awaiting_slot'):
                # Continue slot filling
                return self._continue_slot_filling(
                    text_input, user_id, session, detected_lang,
                    current_url, page_html, transcription
                )
            
            # Step 3: Classify intent
            context = {}
            if current_url:
                context['url'] = current_url
            if page_html:
                context['page_title'] = self._extract_title(page_html)
            
            intent_result = self.intent_dispatcher.classify(text_input, context)
            
            logger.info(f"Intent: {intent_result.intent.value}, Confidence: {intent_result.confidence}")
            
            # Step 4: Handle based on intent
            if intent_result.intent == Intent.BOOKING:
                return self._handle_booking(
                    text_input, user_id, intent_result, detected_lang,
                    current_url, page_html, transcription
                )
            
            elif intent_result.intent == Intent.SEARCH:
                return self._handle_search(
                    text_input, user_id, intent_result, detected_lang,
                    current_url, transcription
                )
            
            elif intent_result.intent == Intent.CANCEL:
                return self._handle_cancel(user_id, detected_lang, transcription)
            
            elif intent_result.intent == Intent.HELP:
                return self._handle_help(detected_lang, transcription)
            
            else:
                # General response
                return self._handle_general(
                    text_input, intent_result, detected_lang,
                    current_url, page_html, transcription
                )
                
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return VoxNavResponse(
                response_type='error',
                message="Sorry, something went wrong. Please try again.",
                language='en',
                transcription=transcription
            )
    
    def _extract_title(self, html: str) -> str:
        """Extract title from HTML."""
        try:
            import re
            match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else ''
        except:
            return ''
    
    def _handle_booking(
        self,
        text_input: str,
        user_id: str,
        intent_result: IntentResult,
        detected_lang: Language,
        current_url: Optional[str],
        page_html: Optional[str],
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Handle booking intent."""
        
        sub_intent = intent_result.sub_intent or 'train_ticket'
        
        # Try to extract slots
        slot_result = self.slot_filler.extract_slots(
            user_id=user_id,
            user_input=text_input,
            intent="BOOKING",
            sub_intent=sub_intent,
            language=detected_lang.value
        )
        
        if slot_result.status == SlotStatus.COMPLETE:
            # All slots filled - generate action
            return self._generate_action(
                intent_result, slot_result, detected_lang,
                current_url, page_html, transcription
            )
        else:
            # Need more info - ask follow-up question
            self.sessions[user_id] = {
                'intent': 'BOOKING',
                'sub_intent': sub_intent,
                'awaiting_slot': slot_result.next_slot,
                'filled_slots': slot_result.filled_slots
            }
            
            return VoxNavResponse(
                response_type='question',
                message=slot_result.next_question or "Please provide more details.",
                language=detected_lang.value,
                intent='BOOKING',
                sub_intent=sub_intent,
                slots=slot_result.filled_slots,
                awaiting_slot=slot_result.next_slot,
                transcription=transcription,
                intent_confidence=intent_result.confidence
            )
    
    def _continue_slot_filling(
        self,
        text_input: str,
        user_id: str,
        session: Dict,
        detected_lang: Language,
        current_url: Optional[str],
        page_html: Optional[str],
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Continue an existing slot filling session."""
        
        slot_result = self.slot_filler.extract_slots(
            user_id=user_id,
            user_input=text_input,
            intent=session['intent'],
            sub_intent=session['sub_intent'],
            language=detected_lang.value
        )
        
        if slot_result.status == SlotStatus.COMPLETE:
            # Done! Generate action
            del self.sessions[user_id]
            
            # Create a minimal IntentResult for action generation
            intent_result = IntentResult(
                intent=Intent[session['intent']],
                confidence=0.9,
                sub_intent=session['sub_intent'],
                entities=slot_result.filled_slots,
                original_query=text_input
            )
            
            return self._generate_action(
                intent_result, slot_result, detected_lang,
                current_url, page_html, transcription
            )
        else:
            # Still need more
            self.sessions[user_id]['awaiting_slot'] = slot_result.next_slot
            self.sessions[user_id]['filled_slots'] = slot_result.filled_slots
            
            return VoxNavResponse(
                response_type='question',
                message=slot_result.next_question or "Please provide more details.",
                language=detected_lang.value,
                intent=session['intent'],
                sub_intent=session['sub_intent'],
                slots=slot_result.filled_slots,
                awaiting_slot=slot_result.next_slot,
                transcription=transcription
            )
    
    def _generate_action(
        self,
        intent_result: IntentResult,
        slot_result: SlotResult,
        detected_lang: Language,
        current_url: Optional[str],
        page_html: Optional[str],
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Generate browser automation actions."""
        
        self._ensure_openrouter()
        
        if not current_url:
            # No URL context - return confirmation message
            slots = slot_result.filled_slots
            
            if detected_lang == Language.HINGLISH:
                message = f"Okay! Main {intent_result.sub_intent} ke liye ready hoon: {slots.get('source', '')} se {slots.get('destination', '')} for {slots.get('date', '')}. Please open the booking website."
            elif detected_lang == Language.HINDI:
                message = f"ठीक है! मैं तैयार हूं: {slots.get('source', '')} से {slots.get('destination', '')} तारीख {slots.get('date', '')} के लिए। कृपया बुकिंग वेबसाइट खोलें।"
            else:
                message = f"Ready to book {intent_result.sub_intent}: {slots.get('source', '')} to {slots.get('destination', '')} on {slots.get('date', '')}. Please open the booking website."
            
            return VoxNavResponse(
                response_type='response',
                message=message,
                language=detected_lang.value,
                intent=intent_result.intent.value,
                sub_intent=intent_result.sub_intent,
                slots=slot_result.filled_slots,
                transcription=transcription,
                intent_confidence=intent_result.confidence
            )
        
        # Generate actions for the current website
        action_prompt = self.prompt_builder.get_action_prompt(
            intent=intent_result.intent.value,
            sub_intent=intent_result.sub_intent or '',
            slots=slot_result.filled_slots,
            url=current_url
        )
        
        try:
            raw_text = self.openrouter_client.generate(
                prompt=action_prompt,
                temperature=0.1,
                max_tokens=500
            )
            
            raw_text = raw_text.strip()
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[1]
                raw_text = raw_text.rsplit('```', 1)[0]
            
            actions = json.loads(raw_text)
            
            # Create confirmation message
            slots = slot_result.filled_slots
            if detected_lang == Language.HINGLISH:
                message = f"Theek hai, filling the form: {slots.get('source', '')} se {slots.get('destination', '')}..."
            else:
                message = f"Filling the form: {slots.get('source', '')} to {slots.get('destination', '')}..."
            
            return VoxNavResponse(
                response_type='action',
                message=message,
                language=detected_lang.value,
                actions=actions,
                intent=intent_result.intent.value,
                sub_intent=intent_result.sub_intent,
                slots=slot_result.filled_slots,
                transcription=transcription,
                intent_confidence=intent_result.confidence
            )
            
        except Exception as e:
            logger.error(f"Action generation failed: {e}")
            return VoxNavResponse(
                response_type='error',
                message="Sorry, I couldn't generate the actions for this website.",
                language=detected_lang.value,
                transcription=transcription
            )
    
    def _handle_search(
        self,
        text_input: str,
        user_id: str,
        intent_result: IntentResult,
        detected_lang: Language,
        current_url: Optional[str],
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Handle search intent."""
        
        query = intent_result.entities.get('query', '') if intent_result.entities else ''
        if not query:
            query = text_input
        
        if detected_lang == Language.HINGLISH:
            message = f"Search kar raha hoon: {query}"
        elif detected_lang == Language.HINDI:
            message = f"खोज रहा हूं: {query}"
        else:
            message = f"Searching for: {query}"
        
        # Generate search action if on a website
        actions = None
        if current_url:
            config = self.prompt_builder.get_website_config(current_url)
            search_selector = config.form_mappings.get('search')
            if search_selector:
                actions = [
                    {"action": "fill", "selector": search_selector, "value": query},
                    {"action": "submit"}
                ]
        
        return VoxNavResponse(
            response_type='action' if actions else 'response',
            message=message,
            language=detected_lang.value,
            actions=actions,
            intent='SEARCH',
            sub_intent=intent_result.sub_intent,
            slots=intent_result.entities,
            transcription=transcription,
            intent_confidence=intent_result.confidence
        )
    
    def _handle_cancel(
        self,
        user_id: str,
        detected_lang: Language,
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Handle cancel intent."""
        
        # Clear any active session
        if user_id in self.sessions:
            del self.sessions[user_id]
        
        self.slot_filler.clear_session(user_id)
        
        if detected_lang == Language.HINGLISH:
            message = "Theek hai, cancel kar diya. Aur kya help chahiye?"
        elif detected_lang == Language.HINDI:
            message = "ठीक है, रद्द कर दिया। और क्या मदद चाहिए?"
        else:
            message = "Okay, cancelled. How else can I help you?"
        
        return VoxNavResponse(
            response_type='response',
            message=message,
            language=detected_lang.value,
            intent='CANCEL',
            transcription=transcription
        )
    
    def _handle_help(
        self,
        detected_lang: Language,
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Handle help intent."""
        
        if detected_lang == Language.HINGLISH:
            message = """Main aapki yeh help kar sakta hoon:
• Train, flight, hotel book karna
• Weather check karna  
• Products search karna
• Forms fill karna
• Websites navigate karna

Bas bolo kya karna hai!"""
        elif detected_lang == Language.HINDI:
            message = """मैं आपकी ये मदद कर सकता हूं:
• ट्रेन, फ्लाइट, होटल बुक करना
• मौसम देखना
• प्रोडक्ट खोजना
• फॉर्म भरना
• वेबसाइट पर जाना

बस बोलो क्या करना है!"""
        else:
            message = """I can help you with:
• Booking trains, flights, hotels
• Checking weather
• Searching for products
• Filling forms
• Navigating websites

Just tell me what you need!"""
        
        return VoxNavResponse(
            response_type='response',
            message=message,
            language=detected_lang.value,
            intent='HELP',
            transcription=transcription
        )
    
    def _handle_general(
        self,
        text_input: str,
        intent_result: IntentResult,
        detected_lang: Language,
        current_url: Optional[str],
        page_html: Optional[str],
        transcription: Optional[str]
    ) -> VoxNavResponse:
        """Handle general/unclassified intents."""
        
        self._ensure_openrouter()
        
        # Build context-aware prompt
        if current_url:
            prompt = self.prompt_builder.build_prompt(
                user_query=text_input,
                url=current_url,
                html_content=page_html,
                intent=intent_result.intent.value
            )
        else:
            lang_prompt = self.multilingual.get_system_prompt(detected_lang)
            prompt = f"""{lang_prompt}

User says: "{text_input}"

Respond helpfully and concisely."""
        
        try:
            message = self.openrouter_client.generate(
                prompt=prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            message = message.strip()
            
            return VoxNavResponse(
                response_type='response',
                message=message,
                language=detected_lang.value,
                intent=intent_result.intent.value,
                transcription=transcription,
                intent_confidence=intent_result.confidence
            )
            
        except Exception as e:
            logger.error(f"General response generation failed: {e}")
            return VoxNavResponse(
                response_type='error',
                message="Sorry, I couldn't process that. Please try again.",
                language=detected_lang.value,
                transcription=transcription
            )
    
    def clear_session(self, user_id: str) -> None:
        """Clear a user's session."""
        if user_id in self.sessions:
            del self.sessions[user_id]
        self.slot_filler.clear_session(user_id)
