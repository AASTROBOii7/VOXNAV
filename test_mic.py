#!/usr/bin/env python
"""
Microphone selector and test.
"""

import speech_recognition as sr

print("🎤 Microphone Selector Test")
print("=" * 50)

# List microphones
mics = sr.Microphone.list_microphone_names()

# Show only input devices (not outputs)
print("\n📟 Available INPUT microphones:")
input_mics = []
for i, name in enumerate(mics):
    # Filter out obvious output devices
    if any(x in name.lower() for x in ["output", "speaker", "headphone"]):
        continue
    if "microphone" in name.lower() or "input" in name.lower() or "headset" in name.lower():
        input_mics.append((i, name))
        print(f"   [{i}] {name[:50]}")

print()
print("Common choices:")
print("   [1] Microphone Array (Realtek) - Laptop mic")
print("   [7] Microphone Array (Realtek Audio) - Same")
print("   [2] Headset (OnePlus Buds 3) - Bluetooth earbuds")
print()

# Get user choice
choice = input("Enter microphone index [default: 1]: ").strip()
mic_index = int(choice) if choice.isdigit() else 1

print(f"\n✅ Using microphone index: {mic_index}")
print(f"   Name: {mics[mic_index][:50]}")
print()

# Test with selected mic
recognizer = sr.Recognizer()

# Lower the energy threshold for better detection
recognizer.energy_threshold = 300  # Lower = more sensitive
recognizer.dynamic_energy_threshold = True

try:
    mic = sr.Microphone(device_index=mic_index, sample_rate=16000)
    
    print("🎧 Calibrating (2 seconds of silence please)...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=2)
    
    print(f"   Energy threshold: {recognizer.energy_threshold:.0f}")
    print()
    
    print("🎤 NOW SPEAK! (10 seconds max, say anything)")
    print("   [Listening...]")
    
    with mic as source:
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
    
    duration = len(audio.frame_data) / (16000 * 2)
    print(f"   ✅ Captured {duration:.1f} seconds of audio!")
    
    print("\n🔄 Recognizing speech...")
    try:
        text = recognizer.recognize_google(audio, language="en-US")
        print(f"   ✅ You said: \"{text}\"")
    except sr.UnknownValueError:
        print("   ⚠️ Could not understand (try speaking louder/clearer)")
    except sr.RequestError as e:
        print(f"   ❌ API Error: {e}")
        
except sr.WaitTimeoutError:
    print("   ⏱️ Timeout - no speech detected")
    print()
    print("   🔧 Troubleshooting:")
    print("   1. Check if microphone is enabled in Windows Settings")
    print("   2. Try a different microphone index")
    print("   3. Speak louder or closer to the mic")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 50)
