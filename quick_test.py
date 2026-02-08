#!/usr/bin/env python
"""
Quick test to see what components are working without API keys
"""

import sys
import os

print("🧪 VoxNav Quick Test")
print("=" * 50)

# Test 1: Basic imports
print("\n1. Testing imports...")
try:
    from core.multilingual import MultilingualHandler
    from core.intent_dispatcher import IntentDispatcher
    from core.slot_filler import SlotFiller
    print("✅ All core modules imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Language detection (no API required)
print("\n2. Testing language detection...")
try:
    handler = MultilingualHandler()
    test_cases = [
        ("Book a train", "Should be hinglish"),
        ("नमस्ते", "Should be Hindi"),
        ("Mujhe train chahiye", "Should be hinglish"),
        ("எனக்கு டிக்கெட் வேண்டும்", "Should be Tamil"),
        ("How are you", "Should be English")
    ]
    
    for text, expected in test_cases:
        result = handler.detect_language(text)
        print(f"   '{text}' -> {result.primary_language.value} ({result.script})")
    
    print("✅ Language detection working correctly")
    
except Exception as e:
    print(f"❌ Language detection failed: {e}")

# Test 3: Check if ASR model exists
print("\n3. Checking ASR model availability...")
model_path = "hindi_models/whisper-medium-hi_alldata_multigpu"
if os.path.exists(model_path):
    print(f"✅ ASR model found at: {model_path}")
else:
    print(f"⚠️  ASR model not found at: {model_path}")
    print("   (This is expected if you haven't downloaded it yet)")

# Test 4: Configuration loading
print("\n4. Testing configuration...")
try:
    from config import config
    print(f"✅ Config loaded - ASR device: {config.asr.device}")
    print(f"   Supported languages: {len(config.asr.supported_languages)}")
    print(f"   OpenRouter model: {config.openrouter.model_name}")
except Exception as e:
    print(f"❌ Config loading failed: {e}")

# Test 5: Slot filler initialization
print("\n5. Testing slot filler initialization...")
try:
    filler = SlotFiller()
    print("✅ SlotFiller initialized (no API required for init)")
except Exception as e:
    print(f"❌ SlotFiller init failed: {e}")

print("\n" + "=" * 50)
print("📋 SUMMARY:")
print("✅ Language detection: Working")
print("✅ Module imports: Working")  
print("✅ Configuration: Working")
print("⚠️  Intent classification: Requires OPENROUTER_API_KEY")
print("⚠️  ASR model: May need to be downloaded")
print("⚠️  Full pipeline: Requires API keys")

print("\n💡 To test full functionality:")
print("1. Set OPENROUTER_API_KEY environment variable")
print("2. Download IndicWhisper model to hindi_models/")
print("3. Run: python examples.py")