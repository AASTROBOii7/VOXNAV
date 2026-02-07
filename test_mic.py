#!/usr/bin/env python
"""
VoxNav - General Purpose Voice Browser Automation
Speak naturally to control any website
"""

import speech_recognition as sr
import re
import time
import random
import math

print("""
╔══════════════════════════════════════════════════════════╗
║     VoxNav - General Purpose Voice Browser Automation    ║
╚══════════════════════════════════════════════════════════╝
""")

print("🎤 Using system default microphone")
print("\n" + "=" * 60)
print("🎤 VOICE COMMANDS (speak naturally):")
print("   • 'Open [website]' - open any website")
print("   • 'Go to [website]' - navigate to site")
print("   • 'Search [query]' - search on Google")
print("   • 'Type [text]' - type text in focused field")
print("   • 'Click [element]' - click on element")
print("   • 'Scroll down/up' - scroll the page")
print("   • 'Go back' - go to previous page")
print("   • 'Refresh' - reload the page")
print("   • 'Close' / 'Quit' - exit")
print("=" * 60)

recognizer = sr.Recognizer()

# Browser globals
browser = None
page = None
pw = None

def human_delay(min_sec=0.5, max_sec=1.5):
    """Random human-like delay."""
    time.sleep(random.uniform(min_sec, max_sec))

def human_type(page, text):
    """Type like a human - character by character."""
    for char in text:
        page.keyboard.type(char)
        delay = random.uniform(0.05, 0.12)
        if random.random() < 0.1:
            delay += random.uniform(0.1, 0.3)
        time.sleep(delay)

# Browser globals - initialized once
import os
_browser = None
page = None

def get_browser():
    """Open browser (reuses existing if open)."""
    global page, _browser
    
    # If page still works, return it
    if page:
        try:
            page.title()
            return page
        except:
            page = None
            _browser = None
    
    print("   🌐 Opening browser...")
    
    # Import here to avoid asyncio issues
    import subprocess
    import sys
    
    # Use subprocess to launch browser to completely avoid asyncio conflict
    from playwright.sync_api import sync_playwright
    
    pw = sync_playwright().start()
    _browser = pw.chromium.launch(
        headless=False,
        slow_mo=30,
        args=['--disable-blink-features=AutomationControlled']
    )
    
    context = _browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'
    )
    
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    page.on("dialog", lambda d: d.dismiss())
    
    return page

def normalize_url(site):
    """Convert site name to URL."""
    site = site.strip().lower()
    
    # Hindi to English site name mapping
    hindi_sites = {
        "आईआरसीटीसी": "irctc", "आई आर सी टी सी": "irctc",
        "अमेज़न": "amazon", "अमेजॉन": "amazon", "अमेज़ॉन": "amazon",
        "फ्लिपकार्ट": "flipkart",
        "यूट्यूब": "youtube", "यू ट्यूब": "youtube",
        "गूगल": "google",
        "फेसबुक": "facebook",
        "इंस्टाग्राम": "instagram",
        "व्हाट्सएप": "whatsapp", "व्हाट्सअप": "whatsapp",
        "ज़ोमैटो": "zomato", "जोमाटो": "zomato",
        "स्विगी": "swiggy",
        "ट्विटर": "twitter",
        "गिटहब": "github",
        "जीमेल": "gmail",
    }
    
    # Convert Hindi site names to English
    for hindi, eng in hindi_sites.items():
        if hindi in site:
            site = eng
            break
    
    # Common site mappings
    sites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "amazon": "https://www.amazon.in",
        "flipkart": "https://www.flipkart.com",
        "facebook": "https://www.facebook.com",
        "twitter": "https://www.twitter.com",
        "instagram": "https://www.instagram.com",
        "linkedin": "https://www.linkedin.com",
        "github": "https://www.github.com",
        "reddit": "https://www.reddit.com",
        "whatsapp": "https://web.whatsapp.com",
        "gmail": "https://mail.google.com",
        "irctc": "https://www.irctc.co.in",
        "zomato": "https://www.zomato.com",
        "swiggy": "https://www.swiggy.com",
    }
    
    # Check if site name matches known sites
    for name, url in sites.items():
        if name in site:
            return url
    
    # If already a URL
    if site.startswith("http"):
        return site
    
    # Only create URL if site name is ASCII (English)
    if all(ord(c) < 128 for c in site.replace(" ", "")):
        # Clean up and add .com if needed
        site = site.replace(" ", "")
        if "." not in site:
            site = site + ".com"
        return "https://www." + site
    
    # For Hindi text that wasn't mapped, return None
    return None

def parse_command(text):
    """Parse voice command into action and parameters."""
    text_lower = text.lower().strip()
    original_text = text
    
    # Hindi to English mapping for commands
    hindi_cmd = {
        "खोलो": "open", "ओपन": "open",
        "जाओ": "go", "पर जाओ": "go to",
        "सर्च": "search", "खोजो": "search",
        "टाइप": "type", "लिखो": "type",
        "क्लिक": "click",
        "स्क्रॉल": "scroll", "नीचे": "down", "ऊपर": "up",
        "वापस": "back", "बैक": "back",
        "रिफ्रेश": "refresh",
        "बंद": "close", "रुको": "stop",
        "एंड": "and", "और": "and",
    }
    
    # Hindi to English mapping for site names
    hindi_sites = {
        "युटुब": "youtube", "यूट्यूब": "youtube",
        "अमेज़न": "amazon", "अमेजॉन": "amazon", "एमेज़ॉन": "amazon",
        "फ्लिपकार्ट": "flipkart",
        "गूगल": "google",
        "आईआरसीटीसी": "irctc",
        "फेसबुक": "facebook",
        "इंस्टाग्राम": "instagram",
        "व्हाट्सएप": "whatsapp",
        "जोमाटो": "zomato",
        "लाइनक्स": "linux", "लाइनेक्स": "linux",
    }
    
    for hindi, eng in hindi_cmd.items():
        text_lower = text_lower.replace(hindi, eng)
    for hindi, eng in hindi_sites.items():
        text_lower = text_lower.replace(hindi, eng)
    
    # Check for compound command: "open X and search Y"
    compound_match = re.search(r'open\s+(\w+)\s+and\s+search\s+(.+)', text_lower)
    if compound_match:
        return "open_and_search", (compound_match.group(1).strip(), compound_match.group(2).strip())
    
    # Detect action type
    action = None
    target = ""
    
    # OPEN/GO TO website
    if re.search(r'\b(open|go to|go|visit|navigate)\b', text_lower):
        action = "open"
        # Extract website name (stop at 'and' or end)
        match = re.search(r'(?:open|go to|go|visit|navigate)\s+(\w+)', text_lower)
        if match:
            target = match.group(1).strip()
    
    # SEARCH
    elif re.search(r'\b(search|find|look for|google)\b', text_lower):
        action = "search"
        match = re.search(r'(?:search|find|look for|google)\s+(.+?)(?:\s+on|\s*$)', text_lower)
        if match:
            target = match.group(1).strip()
    
    # TYPE
    elif re.search(r'\b(type|write|enter|input)\b', text_lower):
        action = "type"
        match = re.search(r'(?:type|write|enter|input)\s+(.+)', text_lower)
        if match:
            target = match.group(1).strip()
    
    # CLICK
    elif re.search(r'\b(click|press|tap|select)\b', text_lower):
        action = "click"
        match = re.search(r'(?:click|press|tap|select)\s+(?:on\s+)?(.+)', text_lower)
        if match:
            target = match.group(1).strip()
    
    # SCROLL
    elif re.search(r'\b(scroll)\b', text_lower):
        action = "scroll"
        if "down" in text_lower or "neeche" in text_lower:
            target = "down"
        elif "up" in text_lower or "upar" in text_lower:
            target = "up"
        else:
            target = "down"
    
    # GO BACK
    elif re.search(r'\b(back|previous|goback)\b', text_lower):
        action = "back"
    
    # REFRESH
    elif re.search(r'\b(refresh|reload)\b', text_lower):
        action = "refresh"
    
    # QUIT
    elif re.search(r'\b(quit|exit|close|stop|band)\b', text_lower):
        action = "quit"
    
    return action, target

def execute_command(action, target):
    """Execute the parsed command."""
    global browser, page, pw
    
    try:
        p = get_browser()
        
        # Handle compound action: open site AND search
        if action == "open_and_search":
            site, query = target
            url = normalize_url(site)
            if url:
                print(f"   🌐 Opening {url}")
                p.goto(url, timeout=30000)
                human_delay(2.0, 3.0)
                
                # Find search box and search
                selectors = [
                    'input[type="search"]',
                    'input[name="q"]', 'input[name="search_query"]',
                    'input[name="search"]', 'textarea[name="q"]',
                    'input#search', 'input.search', 'input#twotabsearchtextbox',
                ]
                for sel in selectors:
                    try:
                        if p.locator(sel).is_visible(timeout=1000):
                            p.fill(sel, "")
                            human_type(p, query)
                            p.keyboard.press("Enter")
                            print(f"   ✅ Opened {site} and searched: {query}")
                            return True
                    except:
                        continue
                print(f"   ⚠️ Opened {site} but couldn't find search box")
            return True
        
        if action == "open":
            url = normalize_url(target)
            if url is None:
                # Couldn't map site name, try Google search instead
                print(f"   ⚠️ Unknown site '{target}', searching Google...")
                p.goto("https://www.google.com", timeout=30000)
                human_delay(1.0, 1.5)
                human_type(p, target)
                p.keyboard.press("Enter")
                human_delay(1.5, 2.5)
                print(f"   ✅ Searched for: {target}")
            else:
                print(f"   🌐 Opening {url}")
                p.goto(url, timeout=30000)
                human_delay(1.5, 2.5)
                print(f"   ✅ Opened: {target}")
        
        elif action == "search":
            # Use direct URL search (faster than typing)
            from urllib.parse import quote
            query_encoded = quote(target)
            
            # Check current URL to determine which site we're on
            current_url = p.url.lower()
            
            # Direct search URLs for popular sites
            if "youtube" in current_url:
                search_url = f"https://www.youtube.com/results?search_query={query_encoded}"
            elif "amazon" in current_url:
                search_url = f"https://www.amazon.in/s?k={query_encoded}"
            elif "flipkart" in current_url:
                search_url = f"https://www.flipkart.com/search?q={query_encoded}"
            elif "google" in current_url:
                search_url = f"https://www.google.com/search?q={query_encoded}"
            else:
                # Default to Google
                search_url = f"https://www.google.com/search?q={query_encoded}"
            
            print(f"   🔍 Searching: {target}")
            p.goto(search_url, timeout=30000)
            human_delay(1.5, 2.5)
            print(f"   ✅ Search results for: {target}")
        
        elif action == "type":
            human_type(p, target)
            print(f"   ✅ Typed: {target}")
        
        elif action == "click":
            # Try to find and click element by text
            try:
                p.get_by_text(target, exact=False).first.click()
                print(f"   ✅ Clicked: {target}")
            except:
                try:
                    p.get_by_role("button", name=target).click()
                    print(f"   ✅ Clicked button: {target}")
                except:
                    try:
                        p.get_by_role("link", name=target).click()
                        print(f"   ✅ Clicked link: {target}")
                    except:
                        print(f"   ⚠️ Could not find: {target}")
        
        elif action == "scroll":
            if target == "down":
                p.mouse.wheel(0, 500)
                print("   ✅ Scrolled down")
            else:
                p.mouse.wheel(0, -500)
                print("   ✅ Scrolled up")
        
        elif action == "back":
            p.go_back()
            print("   ✅ Went back")
        
        elif action == "refresh":
            p.reload()
            print("   ✅ Refreshed")
        
        elif action == "quit":
            return False
        
        else:
            print(f"   ⚠️ Unknown command: {action}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        browser = None
        page = None
        pw = None
        return True

# Main loop - push to talk
print("\n� READY! Press ENTER to speak, type 'quit' to exit\n")

while True:
    cmd = input("🎤 Press ENTER to record (or 'quit'): ").strip()
    if cmd.lower() == 'quit':
        break
    
    print("🔴 SPEAK NOW! (10 seconds)")
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            recognizer.pause_threshold = 2.0
            audio = recognizer.listen(source, timeout=12, phrase_time_limit=10)
            print("   ✅ Captured!")
            
    except sr.WaitTimeoutError:
        print("   ⚠️ No speech detected")
        continue
    except Exception as e:
        print(f"   ❌ Mic error: {e}")
        continue
    
    # Transcribe
    print("🔄 Transcribing...")
    text = None
    
    for lang in ["hi-IN", "en-IN"]:
        try:
            text = recognizer.recognize_google(audio, language=lang)
            print(f"   📝 \"{text}\"")
            break
        except:
            continue
    
    if not text:
        print("   ⚠️ Could not understand")
        continue
    
    # Parse and execute
    action, target = parse_command(text)
    
    if action:
        print(f"   🎯 Action: {action.upper()} → {target}")
        if not execute_command(action, target):
            print("   👋 Goodbye!")
            break
    else:
        print(f"   ⚠️ Could not parse command")
    
    print("")

# Cleanup
print("\n🛑 Closing...")
try:
    if _browser:
        _browser.close()
except:
    pass
print("✅ Done!")
