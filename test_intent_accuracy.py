#!/usr/bin/env python
"""
Test the improved intent classification accuracy.
"""

import os
import sys

# Check API key
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("❌ OPENROUTER_API_KEY not set!")
    sys.exit(1)

print("🧪 Testing Improved Intent Classification")
print("=" * 60)

from core.intent_dispatcher import IntentDispatcher

dispatcher = IntentDispatcher(api_key=api_key)

test_cases = [
    # BOOKING
    ("Book a train ticket from Delhi to Mumbai", "BOOKING", "train_ticket"),
    ("Mujhe Delhi se Mumbai ki train book karni hai", "BOOKING", "train_ticket"),
    ("Book a cab to airport", "BOOKING", "cab"),
    ("Zomato pe pizza order karo", "BOOKING", "food_order"),
    ("Hotel book karo Goa mein", "BOOKING", "hotel"),
    ("Swiggy se biryani mangao", "BOOKING", "food_order"),
    
    # SEARCH
    ("Amazon pe iPhone search karo", "SEARCH", "product"),
    ("Weather batao Bangalore ka", "SEARCH", "weather"),
    ("Flipkart pe mobile search karo", "SEARCH", "product"),
    ("What is the news today", "SEARCH", "news"),
    
    # CANCEL
    ("Cancel my booking", "CANCEL", "cancel_booking"),
    ("Cancel karo", "CANCEL", "abort_action"),
    ("Go back", "CANCEL", "go_back"),
    
    # HELP
    ("Help me", "HELP", "how_to"),
    ("Tum kya kya kar sakte ho", "HELP", "what_can_you_do"),
    
    # GENERAL
    ("Thank you", "GENERAL_INFO", "thanks"),
    ("Hello", "GENERAL_INFO", "greeting"),
]

correct = 0
total = len(test_cases)

print(f"\nRunning {total} test cases...\n")

for i, (query, expected_intent, expected_sub) in enumerate(test_cases, 1):
    result = dispatcher.classify(query)
    
    is_correct = result.intent.value == expected_intent
    status = "✅" if is_correct else "❌"
    
    if is_correct:
        correct += 1
    
    print(f"{status} Test {i}: '{query[:40]}...' " if len(query) > 40 else f"{status} Test {i}: '{query}'")
    print(f"   Expected: {expected_intent}/{expected_sub}")
    print(f"   Got:      {result.intent.value}/{result.sub_intent} (conf: {result.confidence:.2f})")
    
    if result.entities:
        print(f"   Entities: {result.entities}")
    print()

accuracy = (correct / total) * 100

print("=" * 60)
print(f"📊 ACCURACY: {correct}/{total} = {accuracy:.1f}%")
print("=" * 60)

if accuracy >= 90:
    print("🎉 EXCELLENT! Intent classification is highly accurate.")
elif accuracy >= 75:
    print("✅ GOOD. Intent classification is working well.")
elif accuracy >= 50:
    print("⚠️ NEEDS IMPROVEMENT. Some intents are being misclassified.")
else:
    print("❌ POOR. Major issues with intent classification.")
