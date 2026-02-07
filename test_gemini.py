#!/usr/bin/env python
"""
Quick diagnostic to check Gemini API and available models
"""
import os

# Check API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not set!")
    exit(1)

print(f"✅ API Key found: {api_key[:10]}...")

try:
    import google.generativeai as genai
    print(f"✅ google-generativeai version: {genai.__version__}")
except ImportError:
    print("❌ google-generativeai not installed!")
    print("   Run: pip install google-generativeai")
    exit(1)

# Configure and list models
genai.configure(api_key=api_key)

print("\n📋 Available Models:")
print("-" * 50)

try:
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"  • {model.name}")
except Exception as e:
    print(f"❌ Error listing models: {e}")
    exit(1)

# Test a simple generation
print("\n🧪 Testing generation...")
print("-" * 50)

test_models = [
    'gemini-pro',
    'gemini-1.0-pro',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-2.0-flash-exp',
]

for model_name in test_models:
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hi in one word")
        print(f"  ✅ {model_name}: Working!")
        print(f"     Response: {response.text[:50]}...")
        break  # Found a working model
    except Exception as e:
        error_msg = str(e)[:60]
        print(f"  ❌ {model_name}: {error_msg}")

print("\n" + "=" * 50)
print("Use the working model name in VoxNav config!")
