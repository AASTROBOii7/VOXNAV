#!/usr/bin/env python
"""
Test the full VoxNav pipeline:
Voice Input → Whisper → Intent Classification → Gemini Response
"""

import os
import sys

print("""
╔══════════════════════════════════════════════════════════╗
║           VoxNav Full Pipeline Test                      ║
╚══════════════════════════════════════════════════════════╝
""")

# Check Gemini API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not set!")
    print("   Set it with: $env:GEMINI_API_KEY='your-api-key'")
    print()
    api_key = input("Enter your Gemini API key (or press Enter to skip): ").strip()
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

# Import the action executor
try:
    from core.action_executor import ActionExecutor, execute_intent
    print("✅ ActionExecutor loaded")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test cases
test_cases = [
    {
        "intent": "BOOKING",
        "user_input": "Mumbai se Delhi ki train book karo kal subah ke liye",
        "entities": {"source": "Mumbai", "destination": "Delhi", "date": "tomorrow morning"}
    },
    {
        "intent": "SEARCH", 
        "user_input": "Amazon pe iPhone 15 search karo",
        "entities": {"platform": "Amazon", "product": "iPhone 15"}
    },
    {
        "intent": "HELP",
        "user_input": "Tum kya kya kar sakte ho?",
        "entities": {}
    },
    {
        "intent": "CANCEL",
        "user_input": "Meri last booking cancel karo",
        "entities": {}
    },
    {
        "intent": "GENERAL_INFO",
        "user_input": "Namaste! Kaisa hai aap?",
        "entities": {}
    }
]

print()
print("🧪 Testing Intent → Gemini Pipeline")
print("=" * 60)

if not os.getenv("GEMINI_API_KEY"):
    print("\n⚠️ No API key - showing generated prompts only\n")
    
    executor = ActionExecutor()
    for test in test_cases[:2]:  # Just show 2 examples
        print(f"\n📝 Intent: {test['intent']}")
        print(f"   Input: '{test['user_input']}'")
        prompt = executor.generate_prompt(
            test["intent"], test["user_input"], test["entities"]
        )
        print(f"\n   Generated Prompt Preview:")
        print(f"   {prompt[:200]}...")
        print()
else:
    executor = ActionExecutor()
    
    for test in test_cases:
        print(f"\n📝 Intent: {test['intent']}")
        print(f"   Input: '{test['user_input']}'")
        print(f"   Entities: {test['entities']}")
        
        result = executor.execute(
            intent=test["intent"],
            user_input=test["user_input"],
            entities=test["entities"]
        )
        
        if result.success:
            print(f"\n   🤖 Gemini Response:")
            # Truncate long responses
            response = result.response[:300] + "..." if len(result.response) > 300 else result.response
            print(f"   {response}")
        else:
            print(f"   ❌ Error: {result.response}")
        
        print()
        print("-" * 60)

print("\n✅ Pipeline test complete!")
