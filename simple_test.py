#!/usr/bin/env python
"""
VoxNav Simple Test - with rate limit handling
"""
import os
import time

# Check API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not set!")
    exit(1)

print("✅ API Key found")
print("=" * 50)

import google.generativeai as genai
genai.configure(api_key=api_key)

# Test with gemini-2.5-flash (newer, might have better quota)
MODEL_NAME = 'models/gemini-2.5-flash'

print(f"🧪 Testing model: {MODEL_NAME}")
print("-" * 50)

try:
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Simple test
    response = model.generate_content("Say 'Hello VoxNav!' in one line")
    print(f"✅ Model Response: {response.text.strip()}")
    
    print("\n🎯 Testing Intent Classification...")
    print("-" * 50)
    
    # Test intent classification with a simple prompt
    intent_prompt = """Classify this user input into one category: BOOKING, SEARCH, HELP, CANCEL

User: "Mujhe Delhi se Mumbai ki train book karni hai"

Reply with just the category name."""

    response = model.generate_content(intent_prompt)
    print(f"Input: 'Mujhe Delhi se Mumbai ki train book karni hai'")
    print(f"Intent: {response.text.strip()}")
    
    time.sleep(2)  # Small delay to avoid rate limits
    
    # Another test
    response = model.generate_content("""Classify: "Amazon pe iPhone search karo" -> BOOKING or SEARCH?""")
    print(f"\nInput: 'Amazon pe iPhone search karo'")
    print(f"Intent: {response.text.strip()}")
    
    print("\n" + "=" * 50)
    print("✅ VoxNav Gemini integration is working!")
    print("=" * 50)
    
except Exception as e:
    print(f"❌ Error: {e}")
    if "429" in str(e):
        print("\n⏳ Rate limited. Wait 30 seconds and try again:")
        print("   Start-Sleep -Seconds 30; python simple_test.py")
