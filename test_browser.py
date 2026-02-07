#!/usr/bin/env python
"""
Test Browser Controller
"""

from core.browser_controller import BrowserController, execute_voice_command

print("""
╔══════════════════════════════════════════════════════════╗
║           VoxNav Browser Controller Test                 ║
╚══════════════════════════════════════════════════════════╝
""")

# Test cases
test_cases = [
    {
        "intent": "SEARCH",
        "slots": {"item": "iPhone 15", "platform": "Amazon"},
        "description": "Search iPhone on Amazon"
    },
    {
        "intent": "SEARCH", 
        "slots": {"item": "weather today", "platform": "Google"},
        "description": "Search weather on Google"
    },
    {
        "intent": "BOOKING",
        "slots": {"destination": "Delhi", "platform": "irctc"},
        "description": "Open IRCTC for train booking"
    },
]

print("🔧 Initializing browser controller...")
controller = BrowserController(headless=False)

try:
    controller.start()
    print("✅ Browser started!\n")
    
    for i, test in enumerate(test_cases, 1):
        print(f"🧪 Test {i}: {test['description']}")
        print(f"   Intent: {test['intent']}, Slots: {test['slots']}")
        
        result = controller.execute_intent(test['intent'], test['slots'])
        
        status = "✅" if result.success else "❌"
        print(f"   {status} {result.message}")
        print()
        
        input("   Press Enter for next test...")
        print()

except Exception as e:
    print(f"❌ Error: {e}")

finally:
    print("🛑 Stopping browser...")
    controller.stop()
    print("✅ Done!")
