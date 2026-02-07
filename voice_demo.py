#!/usr/bin/env python
"""
VoxNav Voice Assistant Demo
Full pipeline: Voice Input → Intent Classification → Action
"""

import os
import sys
import json
import re

print("""
╔══════════════════════════════════════════════════════════╗
║              VoxNav Voice Assistant Demo                 ║
╚══════════════════════════════════════════════════════════╝
""")

# Check dependencies
missing = []
try:
    import pyaudio
except ImportError:
    missing.append("pyaudio")

try:
    import speech_recognition as sr
except ImportError:
    missing.append("SpeechRecognition")

try:
    import requests
except ImportError:
    missing.append("requests")

if missing:
    print("❌ Missing dependencies. Install with:")
    print(f"   pip install {' '.join(missing)}")
    print()
    print("   For pyaudio on Windows:")
    print("   pip install pipwin && pipwin install pyaudio")
    sys.exit(1)

# Check Ollama
try:
    resp = requests.get("http://localhost:11434/api/tags", timeout=2)
    OLLAMA_AVAILABLE = resp.status_code == 200
    if OLLAMA_AVAILABLE:
        models = [m.get("name") for m in resp.json().get("models", [])]
        OLLAMA_MODEL = "llama3.2:3b" if "llama3.2:3b" in models else models[0] if models else None
except:
    OLLAMA_AVAILABLE = False
    OLLAMA_MODEL = None

if not OLLAMA_AVAILABLE:
    print("⚠️ Ollama not running. Start with: ollama serve")
    print("   Voice demo will work but without intent classification.")
    OLLAMA_MODEL = None
else:
    print(f"✅ Ollama ready with model: {OLLAMA_MODEL}")

print()

# Intent classification prompt
INTENT_PROMPT = """You are an intent classifier. Classify the input into ONE category.

Categories:
- BOOKING: book tickets, order food, reserve hotel, cab booking
- SEARCH: find information, weather, product search
- CANCEL: cancel, stop, abort, go back
- HELP: help, assistance, how to
- GENERAL_INFO: greetings, thanks

Input: "{input}"

Reply with ONLY a JSON object:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "action": "brief description"}}"""


def classify_intent(text: str) -> dict:
    """Classify intent using Ollama."""
    if not OLLAMA_MODEL:
        return {"intent": "UNKNOWN", "confidence": 0, "action": "No LLM available"}
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": INTENT_PROMPT.format(input=text),
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 100}
        }
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        response = resp.json().get("response", "")
        
        # Parse JSON
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"intent": "UNKNOWN", "confidence": 0, "raw": response}
    except Exception as e:
        return {"intent": "ERROR", "confidence": 0, "error": str(e)}


def voice_loop():
    """Main voice input loop."""
    recognizer = sr.Recognizer()
    mic = sr.Microphone(sample_rate=16000)
    
    # Supported languages
    languages = {
        "1": ("hi-IN", "Hindi"),
        "2": ("en-IN", "English"),
        "3": ("ta-IN", "Tamil"),
        "4": ("te-IN", "Telugu"),
        "5": ("bn-IN", "Bengali"),
    }
    
    print("🌐 Select language:")
    for key, (code, name) in languages.items():
        print(f"   {key}. {name}")
    print()
    
    choice = input("Enter choice (1-5) [default: 1 Hindi]: ").strip() or "1"
    lang_code, lang_name = languages.get(choice, ("hi-IN", "Hindi"))
    print(f"✅ Using {lang_name} ({lang_code})")
    print()
    
    print("=" * 60)
    print("🎤 Voice commands:")
    print("   - Speak naturally in your language")
    print("   - Say 'exit' or 'quit' to stop")
    print("   - Press Ctrl+C to force quit")
    print("=" * 60)
    print()
    
    while True:
        try:
            with mic as source:
                print("🎧 Listening... (speak now)")
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("🔄 Processing...")
            
            # Transcribe
            try:
                text = recognizer.recognize_google(audio, language=lang_code)
                print(f"📝 You said: \"{text}\"")
            except sr.UnknownValueError:
                print("❓ Could not understand. Try again.")
                continue
            except sr.RequestError as e:
                print(f"❌ Speech API error: {e}")
                continue
            
            # Check for exit
            if text.lower() in ["exit", "quit", "stop", "band karo", "रुको"]:
                print("\n👋 Goodbye!")
                break
            
            # Classify intent
            print("🧠 Classifying intent...")
            result = classify_intent(text)
            
            intent = result.get("intent", "UNKNOWN")
            confidence = result.get("confidence", 0)
            action = result.get("action", "No action")
            
            print(f"🎯 Intent: {intent} (confidence: {confidence})")
            print(f"📌 Action: {action}")
            print()
            print("-" * 40)
            print()
            
        except sr.WaitTimeoutError:
            print("⏱️ No speech detected. Try again...")
            continue
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue


if __name__ == "__main__":
    try:
        voice_loop()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        print()
        print("Troubleshooting:")
        print("1. Make sure microphone is connected")
        print("2. Install: pip install SpeechRecognition pyaudio")
        print("3. On Windows: pip install pipwin && pipwin install pyaudio")
