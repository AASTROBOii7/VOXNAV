"""
Action Executor for VoxNav
Takes intent output and generates appropriate prompts for Gemini API.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Run: pip install google-generativeai")


@dataclass
class ActionResult:
    """Result from action execution."""
    success: bool
    response: str
    action_type: str
    follow_up_needed: bool = False
    follow_up_prompt: Optional[str] = None
    data: Optional[Dict] = None


# Intent-specific prompt templates
INTENT_PROMPTS = {
    "BOOKING": """You are a helpful booking assistant for Indian users.
The user wants to make a booking. Based on their request, help them complete the booking.

User's request: "{user_input}"
Detected entities: {entities}

Instructions:
1. If missing required info (date, time, location, etc.), ask for it politely in Hindi/Hinglish
2. If all info is available, confirm the booking details
3. Provide step-by-step guidance if needed
4. Be conversational and friendly

Respond in the same language the user used (Hindi/Hinglish/English).""",

    "SEARCH": """You are a helpful search assistant for Indian users.
The user wants to search for something. Help them find what they're looking for.

User's request: "{user_input}"
Detected entities: {entities}

Instructions:
1. Understand what they're searching for
2. If it's a product search, provide helpful suggestions
3. If it's a weather query, provide weather information format
4. If it's a general search, provide relevant information
5. Be helpful and informative

Respond in the same language the user used.""",

    "CANCEL": """You are a helpful assistant for Indian users.
The user wants to cancel something.

User's request: "{user_input}"
Detected entities: {entities}

Instructions:
1. Confirm what they want to cancel
2. Ask for any required details (booking ID, order number, etc.)
3. Guide them through the cancellation process
4. Be understanding and helpful

Respond in the same language the user used.""",

    "HELP": """You are VoxNav, a voice-activated assistant for Indian users.
The user is asking for help.

User's request: "{user_input}"

Instructions:
1. Explain what you can do:
   - Book tickets (train, flight, hotel, cab)
   - Search for products, weather, information
   - Cancel bookings
   - Navigate websites
   - Fill forms
2. Give examples of commands they can use
3. Be friendly and encouraging

Respond in Hindi/Hinglish if the user used Hindi words, otherwise in English.""",

    "GENERAL_INFO": """You are VoxNav, a friendly voice assistant for Indian users.
The user is having a casual conversation.

User's request: "{user_input}"

Instructions:
1. Respond naturally and conversationally
2. If it's a greeting, greet back warmly
3. If it's thanks, acknowledge gracefully
4. Keep the response brief and friendly

Respond in the same language the user used.""",

    "NAVIGATION": """You are a web navigation assistant.
The user wants to navigate to a specific page or element.

User's request: "{user_input}"
Detected entities: {entities}

Instructions:
1. Understand where they want to go
2. Provide clear navigation instructions
3. If on a specific website, give site-specific guidance

Respond in the same language the user used.""",

    "FORM_FILL": """You are a form-filling assistant.
The user wants to fill out a form.

User's request: "{user_input}"
Detected entities: {entities}

Instructions:
1. Understand what form they're filling
2. Ask for any missing required information
3. Guide them step by step

Respond in the same language the user used.""",
}

# Default prompt for unknown intents
DEFAULT_PROMPT = """You are VoxNav, a helpful voice assistant for Indian users.

User's request: "{user_input}"

Instructions:
1. Try to understand what the user wants
2. Provide helpful guidance
3. If unsure, ask clarifying questions

Respond in the same language the user used (Hindi/Hinglish/English)."""


class ActionExecutor:
    """
    Executes actions based on detected intent.
    Generates dynamic prompts and sends to Gemini.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the action executor.
        
        Args:
            api_key: Gemini API key (uses env var if not provided)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini API."""
        if not GEMINI_AVAILABLE:
            logger.error("google-generativeai not installed")
            return
        
        if not self.api_key:
            logger.warning("No Gemini API key provided. Set GEMINI_API_KEY env var.")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
    
    def generate_prompt(
        self,
        intent: str,
        user_input: str,
        entities: Optional[Dict] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Generate a prompt based on the detected intent.
        
        Args:
            intent: Detected intent (BOOKING, SEARCH, etc.)
            user_input: Original user input
            entities: Extracted entities from the intent
            context: Additional context (current URL, page info, etc.)
            
        Returns:
            Generated prompt string
        """
        # Get the template for this intent
        template = INTENT_PROMPTS.get(intent.upper(), DEFAULT_PROMPT)
        
        # Format entities
        entities_str = json.dumps(entities or {}, ensure_ascii=False, indent=2)
        
        # Generate the prompt
        prompt = template.format(
            user_input=user_input,
            entities=entities_str
        )
        
        # Add context if provided
        if context:
            context_str = "\n\nAdditional Context:\n"
            if "current_url" in context:
                context_str += f"- Current website: {context['current_url']}\n"
            if "page_title" in context:
                context_str += f"- Page title: {context['page_title']}\n"
            if "user_language" in context:
                context_str += f"- User's preferred language: {context['user_language']}\n"
            prompt += context_str
        
        return prompt
    
    def execute(
        self,
        intent: str,
        user_input: str,
        entities: Optional[Dict] = None,
        context: Optional[Dict] = None
    ) -> ActionResult:
        """
        Execute an action based on intent.
        
        Args:
            intent: Detected intent
            user_input: Original user input
            entities: Extracted entities
            context: Additional context
            
        Returns:
            ActionResult with response
        """
        if not self.model:
            return ActionResult(
                success=False,
                response="Gemini API not available. Please set GEMINI_API_KEY.",
                action_type=intent
            )
        
        # Generate the prompt
        prompt = self.generate_prompt(intent, user_input, entities, context)
        
        try:
            # Call Gemini API
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Check if follow-up is needed (contains questions)
            follow_up_needed = "?" in response_text
            
            return ActionResult(
                success=True,
                response=response_text,
                action_type=intent,
                follow_up_needed=follow_up_needed,
                data=entities
            )
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ActionResult(
                success=False,
                response=f"Error: {str(e)}",
                action_type=intent
            )
    
    def execute_with_intent_result(
        self,
        intent_result: Dict,
        context: Optional[Dict] = None
    ) -> ActionResult:
        """
        Execute action from intent classification result.
        
        Args:
            intent_result: Result from intent classifier containing:
                - intent: str
                - entities: dict
                - original_query: str
            context: Additional context
            
        Returns:
            ActionResult
        """
        intent = intent_result.get("intent", "UNKNOWN")
        user_input = intent_result.get("original_query") or intent_result.get("action", "")
        entities = intent_result.get("entities", {})
        
        return self.execute(intent, user_input, entities, context)


# Convenience function
def execute_intent(
    intent: str,
    user_input: str,
    api_key: Optional[str] = None,
    entities: Optional[Dict] = None,
    context: Optional[Dict] = None
) -> ActionResult:
    """
    Quick function to execute an intent action.
    
    Example:
        result = execute_intent(
            intent="BOOKING",
            user_input="Mumbai se Delhi ki train book karo",
            entities={"source": "Mumbai", "destination": "Delhi"}
        )
        print(result.response)
    """
    executor = ActionExecutor(api_key=api_key)
    return executor.execute(intent, user_input, entities, context)
