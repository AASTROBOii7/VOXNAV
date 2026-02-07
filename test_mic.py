#!/usr/bin/env python
"""
VoxNav Voice → Browser Control
With human-like behavior to avoid bot detection
"""

import speech_recognition as sr
import re
import time
import random
import math

print("""
╔══════════════════════════════════════════════════════════╗
║           VoxNav Voice → Browser Control                 ║
║           (Human-like browsing behavior)                 ║
╚══════════════════════════════════════════════════════════╝
""")

# List microphones
mics = sr.Microphone.list_microphone_names()
print("📟 Microphones:")
for i, name in enumerate(mics):
    if "mic" in name.lower() or "headset" in name.lower() or "input" in name.lower():
        print(f"   [{i}] {name[:45]}")

mic_idx = input("\nMicrophone index [default: 2]: ").strip()
mic_idx = int(mic_idx) if mic_idx else 2

print("\n" + "=" * 60)
print("🎤 COMMANDS:")
print("   • Amazon pe iPhone search karo")
print("   • Google weather search karo")
print("   • YouTube kholo / open YouTube")
print("   • Flipkart kholo")
print("   • Type 'quit' to exit")
print("=" * 60)

recognizer = sr.Recognizer()

# Browser globals
browser = None
page = None
pw = None

def human_delay(min_sec=0.5, max_sec=1.5):
    """Random human-like delay."""
    time.sleep(random.uniform(min_sec, max_sec))

def human_type(page, selector, text):
    """Type like a human - character by character with variable speed."""
    element = page.locator(selector)
    element.click()
    human_delay(0.2, 0.5)
    
    for char in text:
        page.keyboard.type(char)
        # Variable delay between keystrokes (60-200 WPM simulation)
        delay = random.uniform(0.05, 0.15)
        # Occasional longer pause (thinking)
        if random.random() < 0.1:
            delay += random.uniform(0.2, 0.5)
        time.sleep(delay)

def bezier_point(t, p0, p1, p2, p3):
    """Calculate point on cubic Bezier curve."""
    return (
        (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0],
        (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
    )

def human_move_mouse(page, target_x, target_y):
    """Move mouse in curved path like a human."""
    # Get current position (approximate center of viewport)
    viewport = page.viewport_size
    start_x = viewport['width'] // 2
    start_y = viewport['height'] // 2
    
    # Generate control points for Bezier curve
    ctrl1 = (
        start_x + random.uniform(-100, 100),
        start_y + random.uniform(-50, 50)
    )
    ctrl2 = (
        target_x + random.uniform(-100, 100),
        target_y + random.uniform(-50, 50)
    )
    
    # Move along curve
    steps = random.randint(20, 40)
    for i in range(steps + 1):
        t = i / steps
        # Add slight jitter
        jitter_x = random.uniform(-2, 2)
        jitter_y = random.uniform(-2, 2)
        
        x, y = bezier_point(t, (start_x, start_y), ctrl1, ctrl2, (target_x, target_y))
        page.mouse.move(x + jitter_x, y + jitter_y)
        
        # Variable speed (slower at start and end)
        speed = 0.01 + 0.02 * math.sin(t * math.pi)
        time.sleep(speed)

def human_click(page, selector):
    """Click with human-like mouse movement."""
    try:
        element = page.locator(selector)
        box = element.bounding_box()
        if box:
            # Click at random point within element
            target_x = box['x'] + random.uniform(5, box['width'] - 5)
            target_y = box['y'] + random.uniform(5, box['height'] - 5)
            human_move_mouse(page, target_x, target_y)
            human_delay(0.1, 0.3)
            page.mouse.click(target_x, target_y)
        else:
            element.click()
    except:
        page.click(selector)

def get_browser():
    """Open browser only when needed."""
    global browser, page, pw
    
    # Check if browser is still alive
    if page:
        try:
            page.title()  # Test if page is responsive
            return page
        except:
            # Browser was closed, reset
            browser = None
            page = None
            pw = None
    
    print("   🌐 Opening browser...")
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,
        slow_mo=50,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    # Remove webdriver detection
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    return page

def detect_intent(text):
    """Detect platform and query from text."""
    text_lower = text.lower()
    
    # Hindi to English mapping
    hindi_map = {
        "सर्च": "search", "खोजो": "search", "ढूंढो": "search",
        "खोलो": "open", "ओपन": "open", "खोल": "open",
        "आईफोन": "iphone", "लैपटॉप": "laptop", "मोबाइल": "mobile",
        "मौसम": "weather", "वेदर": "weather",
        "अमेज़न": "amazon", "अमेज़ॉन": "amazon", "एमेज़ॉन": "amazon",
        "अमेजॉन": "amazon", "अमेज़न": "amazon", "अमेजन": "amazon",
        "फ्लिपकार्ट": "flipkart", "गूगल": "google",
        "यूट्यूब": "youtube", "ट्रेन": "train", "टिकट": "ticket",
    }
    
    for hindi, eng in hindi_map.items():
        text_lower = text_lower.replace(hindi, eng)
    
    # Detect platform
    if "amazon" in text_lower:
        platform = "amazon"
    elif "flipkart" in text_lower:
        platform = "flipkart"
    elif "youtube" in text_lower:
        platform = "youtube"
    elif "irctc" in text_lower or "train" in text_lower:
        platform = "irctc"
    elif "zomato" in text_lower:
        platform = "zomato"
    else:
        platform = "google"  # Use Google with human-like behavior
    
    # Extract query
    query = text
    for word in ["search", "karo", "करो", "खोजो", "pe", "पे", "पर", "on", "kholo", "खोलो", "open"]:
        query = query.replace(word, " ")
    query = re.sub(r'\s+', ' ', query).strip()
    
    return platform, query

def execute_action(platform, query):
    """Execute browser action with human-like behavior."""
    try:
        p = get_browser()
        
        if platform == "amazon":
            p.goto("https://www.amazon.in", timeout=30000)
            human_delay(1.5, 2.5)
            p.wait_for_load_state("domcontentloaded")
            human_type(p, '#twotabsearchtextbox', query)
            human_delay(0.5, 1.0)
            p.keyboard.press('Enter')
            human_delay(1.0, 2.0)
            print(f"   ✅ Amazon: {query}")
            
        elif platform == "flipkart":
            p.goto("https://www.flipkart.com", timeout=30000)
            human_delay(1.5, 2.5)
            p.wait_for_load_state("domcontentloaded")
            try:
                p.click('button._2KpZ6l._2doB4z', timeout=2000)
                human_delay(0.5, 1.0)
            except:
                pass
            human_type(p, 'input[name="q"]', query)
            human_delay(0.5, 1.0)
            p.keyboard.press('Enter')
            human_delay(1.0, 2.0)
            print(f"   ✅ Flipkart: {query}")
            
        elif platform == "youtube":
            p.goto("https://www.youtube.com", timeout=30000)
            human_delay(1.5, 2.5)
            if query and query.lower() not in ["youtube", "यूट्यूब"]:
                human_type(p, 'input#search', query)
                human_delay(0.5, 1.0)
                p.keyboard.press('Enter')
            print(f"   ✅ YouTube: {query}")
            
        elif platform == "irctc":
            p.goto("https://www.irctc.co.in", timeout=30000)
            human_delay(1.5, 2.5)
            print("   ✅ Opened IRCTC")
            
        elif platform == "zomato":
            p.goto("https://www.zomato.com", timeout=30000)
            human_delay(1.5, 2.5)
            print("   ✅ Opened Zomato")
            
        else:  # Google with human-like behavior
            p.goto("https://www.google.com", timeout=30000)
            human_delay(2.0, 3.5)  # Longer delay for Google
            p.wait_for_load_state("domcontentloaded")
            human_type(p, 'textarea[name="q"]', query)
            human_delay(0.8, 1.5)
            p.keyboard.press('Enter')
            human_delay(2.0, 3.0)  # Wait for results
            print(f"   ✅ Google: {query}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        # Reset browser on error
        global browser, page, pw
        browser = None
        page = None
        pw = None

# Main loop
while True:
    print("\n🎤 Press ENTER to record (or 'quit')...")
    cmd = input()
    if cmd.lower() == 'quit':
        break
    
    print("🔴 SPEAK NOW! (5 seconds)")
    
    try:
        with sr.Microphone(device_index=mic_idx) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=5)
            print("   ✅ Captured!")
    except Exception as e:
        print(f"   ❌ Mic error: {e}")
        continue
    
    # Transcribe
    print("🔄 Transcribing...")
    text = None
    
    try:
        text = recognizer.recognize_google(audio, language="hi-IN")
        print(f"   📝 \"{text}\"")
    except:
        try:
            text = recognizer.recognize_google(audio, language="en-IN")
            print(f"   📝 \"{text}\"")
        except:
            print("   ⚠️ Could not understand")
            continue
    
    if not text:
        continue
    
    # Detect intent
    platform, query = detect_intent(text)
    print(f"   🎯 {platform.upper()}: {query}")
    
    # Execute
    execute_action(platform, query)

# Cleanup
print("\n🛑 Closing...")
try:
    if browser:
        browser.close()
    if pw:
        pw.stop()
except:
    pass
print("✅ Done!")
