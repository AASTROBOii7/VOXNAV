#!/usr/bin/env python
"""
Test VoxNav with Ollama for local intent classification.
"""

import os
import time
import json
import re
import requests

print("""
╔══════════════════════════════════════════════════════════╗
║           VoxNav + Ollama Integration Test               ║
╚══════════════════════════════════════════════════════════╝
""")

# Check if Ollama is running
try:
    resp = requests.get("http://localhost:11434/api/tags", timeout=5)
    if resp.status_code != 200:
        raise Exception("Ollama not responding")
except:
    print("❌ Ollama is not running!")
    print("   Start with: ollama serve")
    exit(1)

print("✅ Ollama is running!")

# List available models
models = [m.get("name") for m in resp.json().get("models", [])]
print(f"📦 Available models: {models}")

# Prefer llama3.2:3b
model = "llama3.2:3b" if "llama3.2:3b" in models else models[0]
print(f"🤖 Using model: {model}")
print()

# Better prompt (simpler, works with llama3.2)
INTENT_PROMPT = """You are an intent classifier. Classify the input into ONE category.

Categories:
- BOOKING: book tickets, order food, reserve hotel, cab booking
- SEARCH: find information, weather, product search
- CANCEL: cancel, stop, abort, go back
- HELP: help, assistance, how to
- GENERAL_INFO: greetings, thanks

Input: "{input}"

Reply with ONLY a JSON object, nothing else:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "sub_intent": "type"}}"""

# Test basic generation
print("🔬 Testing basic generation...")
start = time.perf_counter()
payload = {
    "model": model,
    "prompt": "Say 'Hello VoxNav!' in exactly 3 words.",
    "stream": False,
    "options": {"temperature": 0.1, "num_predict": 50}
}
resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
response_text = resp.json().get("response", "")
latency = (time.perf_counter() - start) * 1000
print(f"   Response: {response_text.strip()[:50]}")
print(f"   Latency: {latency:.0f}ms")
print()

# Test intent classification
print("🎯 Testing Intent Classification")
print("=" * 50)

test_cases = [
    ("Book a train ticket from Delhi to Mumbai", "BOOKING"),
    ("Mujhe Delhi se Mumbai ki train book karni hai", "BOOKING"),
    ("Zomato pe pizza order karo", "BOOKING"),
    ("Amazon pe iPhone search karo", "SEARCH"),
    ("Weather batao Bangalore ka", "SEARCH"),
    ("Cancel my booking", "CANCEL"),
    ("Help me", "HELP"),
    ("Thank you", "GENERAL_INFO"),
]

correct = 0
total_latency = 0

for query, expected in test_cases:
    prompt = INTENT_PROMPT.format(input=query)
    
    start = time.perf_counter()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 100}
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
    response = resp.json().get("response", "")
    latency = (time.perf_counter() - start) * 1000
    total_latency += latency
    
    # Extract intent from response
    intent = "UNKNOWN"
    try:
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            intent = result.get("intent", "UNKNOWN").upper()
    except:
        pass
    
    is_correct = intent == expected
    status = "✅" if is_correct else "❌"
    if is_correct:
        correct += 1
    
    display_query = f"'{query[:35]}...'" if len(query) > 35 else f"'{query}'"
    print(f"{status} {display_query}")
    print(f"   Expected: {expected} | Got: {intent} | {latency:.0f}ms")

print()
print("=" * 50)
accuracy = (correct / len(test_cases)) * 100
avg_latency = total_latency / len(test_cases)

print(f"📊 Accuracy: {correct}/{len(test_cases)} = {accuracy:.0f}%")
print(f"⏱️ Avg Latency: {avg_latency:.0f}ms")
print()

if accuracy >= 85:
    print("🎉 EXCELLENT! Ollama intent classification is working great!")
elif accuracy >= 70:
    print("✅ GOOD. Intent classification is working.")
else:
    print("⚠️ Needs improvement.")

print()
print("💡 Ollama is ~2x faster than OpenRouter with unlimited usage!")
