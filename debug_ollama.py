#!/usr/bin/env python
"""
Debug Ollama intent classification - see raw responses.
"""

import requests
import json
import re

print("🔍 Debugging Ollama Intent Classification")
print("=" * 60)

# Get available models
resp = requests.get("http://localhost:11434/api/tags", timeout=5)
models = [m.get("name") for m in resp.json().get("models", [])]
model = "llama3.2:3b" if "llama3.2:3b" in models else models[0]
print(f"Using model: {model}\n")

# Better prompt with clearer instructions
INTENT_PROMPT = """You are an intent classifier. Classify the input into ONE category.

Categories:
- BOOKING: book tickets, order food, reserve hotel, cab booking
- SEARCH: find information, weather, product search
- CANCEL: cancel, stop, abort, go back
- HELP: help, assistance, how to
- GENERAL_INFO: greetings, thanks

Input: "{input}"

Reply with ONLY a JSON object, nothing else:
{{"intent": "CATEGORY_NAME", "confidence": 0.95}}"""

test_cases = [
    "Book a train ticket from Delhi to Mumbai",
    "Amazon pe iPhone search karo",
    "Cancel my booking",
    "Help me",
]

for query in test_cases:
    prompt = INTENT_PROMPT.format(input=query)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 100}
    }
    
    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
    raw_response = resp.json().get("response", "")
    
    print(f"📝 Query: '{query}'")
    print(f"📤 Raw Response: '{raw_response[:200]}'")
    
    # Try to extract intent
    try:
        # Method 1: Find JSON
        json_match = re.search(r'\{[^{}]*\}', raw_response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            print(f"✅ Parsed: {result}")
        else:
            # Method 2: Look for intent keyword
            for intent in ["BOOKING", "SEARCH", "CANCEL", "HELP", "GENERAL_INFO"]:
                if intent in raw_response.upper():
                    print(f"⚠️ Found keyword: {intent}")
                    break
            else:
                print("❌ Could not parse")
    except Exception as e:
        print(f"❌ Parse error: {e}")
    
    print()
