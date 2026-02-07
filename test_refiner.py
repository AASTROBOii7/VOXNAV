#!/usr/bin/env python
"""
Test the Speech Intent Refiner
"""

from core.speech_refiner import SpeechIntentRefiner, refine_speech
import json

print("""
╔══════════════════════════════════════════════════════════╗
║           Speech Intent Refiner Test                     ║
╚══════════════════════════════════════════════════════════╝
""")

# Test cases
test_cases = [
    # Self-correction examples
    "Book a ticket to Delhi for Friday... wait, no, Sunday morning",
    "Mumbai se Chennai ka flight... nahi nahi, Delhi ka flight book karo",
    "Search iPhone on Flipkart... actually Amazon pe search karo",
    
    # Clean inputs
    "Mujhe Delhi ki train ticket chahiye kal ke liye",
    "Amazon pe laptop search karo",
    "Bangalore se Mumbai ki flight book karo Friday evening",
    
    # Hinglish
    "Kal subah ke liye Jaipur ka ticket book kar do",
    "Weather batao Mumbai ka",
]

print("🧪 Testing Speech Intent Refiner")
print("=" * 60)

refiner = SpeechIntentRefiner(use_llm=False)  # Rule-based only

for i, text in enumerate(test_cases, 1):
    print(f"\n📝 Test {i}:")
    print(f"   Raw: \"{text}\"")
    
    result = refiner.refine(text)
    
    print(f"   Refined: \"{result.refined_text}\"")
    print(f"   Intent: {result.intent_category}")
    print(f"   Slots: {json.dumps(result.extracted_slots, ensure_ascii=False)}")
    print(f"   Is Final: {result.is_final}")
    print(f"   Response: \"{result.response_speech}\"")
    
    if result.corrections_made:
        print(f"   Corrections: {result.corrections_made}")
    
    print()

print("=" * 60)
print("✅ Test complete!")
print()
print("💡 Use refine_speech('your text') for quick refinement")
