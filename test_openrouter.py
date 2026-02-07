#!/usr/bin/env python
"""
VoxNav OpenRouter Test - Tests the OpenRouter API integration
"""
import os
import sys

# Check API key
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("❌ OPENROUTER_API_KEY not set!")
    print("\n📝 To set it, run:")
    print('   $env:OPENROUTER_API_KEY = "your-api-key-here"')
    print("\n🔗 Get a free key at: https://openrouter.ai/keys")
    sys.exit(1)

print("✅ API Key found")
print("=" * 60)

# Test OpenRouter client directly
from core.openrouter_client import OpenRouterClient

print("\n🧪 Testing OpenRouter API...")
print("-" * 60)

try:
    client = OpenRouterClient(api_key=api_key)
    
    # Simple test
    response = client.generate("Say 'Hello VoxNav!' in one short sentence")
    print(f"✅ Basic Response: {response.strip()}")
    
    print("\n🎯 Testing Intent Classification...")
    print("-" * 60)
    
    # Test intent classification
    from core.intent_dispatcher import IntentDispatcher
    
    dispatcher = IntentDispatcher(api_key=api_key)
    
    test_inputs = [
        "Book a train ticket from Delhi to Mumbai",
        "Mujhe Bangalore ka weather batao",
        "Amazon pe iPhone search karo"
    ]
    
    for inp in test_inputs:
        result = dispatcher.classify(inp)
        print(f"\n📝 '{inp}'")
        print(f"   → Intent: {result.intent.value}")
        print(f"   → Confidence: {result.confidence:.2f}")
        print(f"   → Sub-intent: {result.sub_intent}")
        if result.entities:
            print(f"   → Entities: {result.entities}")
    
    print("\n" + "=" * 60)
    print("✅ VoxNav + OpenRouter integration is working!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
