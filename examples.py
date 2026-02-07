#!/usr/bin/env python
"""
VoxNav Example Usage
Demonstrates how to use VoxNav for voice-activated assistance.
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_text_processing():
    """Example: Process text input (simulating transcribed speech)."""
    
    from core import VoxNavOrchestrator
    
    # Initialize VoxNav (lazy loads models)
    voxnav = VoxNavOrchestrator(
        asr_model_path="hindi_models/whisper-medium-hi_alldata_multigpu",
        asr_device="cuda",  # or "cpu"
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )
    
    # Example user inputs
    test_inputs = [
        # Hinglish booking request
        "Mujhe Delhi se Mumbai ki train book karni hai kal ke liye",
        
        # Hindi booking request
        "कल के लिए दिल्ली से जयपुर की फ्लाइट बुक करो",
        
        # English booking
        "Book a hotel in Goa for next weekend",
        
        # Search request
        "Amazon pe iPhone 15 search karo",
        
        # Weather query
        "Bangalore ka weather kaisa hai?",
        
        # Help request
        "Tum kya kya kar sakte ho?",
        
        # Cancel
        "Cancel karo",
    ]
    
    user_id = "test_user_123"
    
    for user_input in test_inputs:
        print("\n" + "="*60)
        print(f"📝 User: {user_input}")
        print("="*60)
        
        # Process the input
        response = voxnav.process_text(
            text_input=user_input,
            user_id=user_id,
            current_url="https://www.irctc.co.in",  # Simulated context
        )
        
        print(f"\n🎯 Intent: {response.intent} ({response.sub_intent})")
        print(f"🌐 Language: {response.language}")
        print(f"📤 Response Type: {response.response_type}")
        print(f"\n💬 VoxNav: {response.message}")
        
        if response.slots:
            print(f"\n📦 Extracted Slots: {response.slots}")
        
        if response.actions:
            print(f"\n🔧 Actions: {response.actions}")
        
        if response.awaiting_slot:
            print(f"\n❓ Waiting for: {response.awaiting_slot}")


def example_audio_processing():
    """Example: Process audio file."""
    
    from core import VoxNavOrchestrator
    
    # Initialize VoxNav
    voxnav = VoxNavOrchestrator(
        asr_model_path="hindi_models/whisper-medium-hi_alldata_multigpu",
        asr_device="cuda",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )
    
    # Example audio file
    audio_file = "test_audio.mp3"
    
    if not os.path.exists(audio_file):
        print(f"⚠️ Audio file '{audio_file}' not found. Creating sample...")
        print("Please provide an audio file to test.")
        return
    
    user_id = "test_user_456"
    
    print(f"\n🎤 Processing audio: {audio_file}")
    
    response = voxnav.process_audio(
        audio_input=audio_file,
        user_id=user_id,
        current_url="https://www.makemytrip.com",
        language="hi"
    )
    
    print(f"\n📝 Transcription: {response.transcription}")
    print(f"🎯 Intent: {response.intent}")
    print(f"💬 Response: {response.message}")


def example_slot_filling_conversation():
    """Example: Multi-turn conversation with slot filling."""
    
    from core import VoxNavOrchestrator
    
    voxnav = VoxNavOrchestrator(
        asr_model_path="hindi_models/whisper-medium-hi_alldata_multigpu",
        asr_device="cuda",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )
    
    user_id = "conversation_user"
    
    # Multi-turn conversation
    conversation = [
        "Train ticket book karna hai",  # Missing: source, destination, date
        "Delhi se",                      # Provides source
        "Mumbai jaana hai",              # Provides destination
        "Parso ke liye",                 # Provides date
    ]
    
    print("\n" + "="*60)
    print("🗣️ MULTI-TURN CONVERSATION EXAMPLE")
    print("="*60)
    
    for turn, user_input in enumerate(conversation, 1):
        print(f"\n--- Turn {turn} ---")
        print(f"👤 User: {user_input}")
        
        response = voxnav.process_text(
            text_input=user_input,
            user_id=user_id,
            current_url="https://www.irctc.co.in"
        )
        
        print(f"🤖 VoxNav: {response.message}")
        
        if response.slots:
            print(f"📦 Slots so far: {response.slots}")
        
        if response.response_type == 'action':
            print("✅ Ready to execute booking!")
            break


def example_intent_classification():
    """Example: Just intent classification."""
    
    from core import IntentDispatcher
    
    dispatcher = IntentDispatcher(api_key=os.getenv("OPENROUTER_API_KEY"))
    
    test_phrases = [
        "Book a cab to airport",
        "Zomato pe pizza order karo",
        "Weather check karo Mumbai ka",
        "Flipkart pe mobile search karo",
        "Cancel my booking",
        "Help me",
    ]
    
    print("\n" + "="*60)
    print("🎯 INTENT CLASSIFICATION EXAMPLES")
    print("="*60)
    
    for phrase in test_phrases:
        result = dispatcher.classify(phrase)
        print(f"\n📝 \"{phrase}\"")
        print(f"   → Intent: {result.intent.value} | Sub: {result.sub_intent} | Confidence: {result.confidence:.2f}")
        print(f"   → Language: {result.language_detected} | Entities: {result.entities}")


def example_language_detection():
    """Example: Language detection."""
    
    from core import MultilingualHandler
    
    handler = MultilingualHandler()
    
    test_texts = [
        "Book a train ticket",
        "Mujhe train ticket book karni hai",
        "ट्रेन टिकट बुक करो",
        "எனக்கு டிக்கெட் வேண்டும்",
        "నాకు టికెట్ కావాలి",
        "মুম্বাই যেতে হবে",
    ]
    
    print("\n" + "="*60)
    print("🌐 LANGUAGE DETECTION EXAMPLES")
    print("="*60)
    
    for text in test_texts:
        result = handler.detect_language(text)
        print(f"\n📝 \"{text}\"")
        print(f"   → Language: {result.primary_language.value} | Script: {result.script} | Confidence: {result.confidence:.2f}")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║                     VoxNav Examples                       ║
║        Voice-Activated Web Navigation Assistant           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  Warning: OPENROUTER_API_KEY not set!")
        print("   Set it with: $env:OPENROUTER_API_KEY = 'your-api-key'")
        print()
    
    # Run examples
    try:
        print("\n🔹 Running Language Detection Example...")
        example_language_detection()
        
        print("\n🔹 Running Intent Classification Example...")
        example_intent_classification()
        
        print("\n🔹 Running Text Processing Example...")
        example_text_processing()
        
        print("\n🔹 Running Slot Filling Conversation Example...")
        example_slot_filling_conversation()
        
        # Audio example (optional)
        # print("\n🔹 Running Audio Processing Example...")
        # example_audio_processing()
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise
