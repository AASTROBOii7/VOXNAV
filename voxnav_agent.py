#!/usr/bin/env python
"""
VoxNav 2.0 - AI-Powered Voice Browser Agent
Uses Selenium (no asyncio issues) + Ollama for AI
"""

import speech_recognition as sr
import pyttsx3
import json
import re
import time
import random
import os
import requests

print("""
╔══════════════════════════════════════════════════════════╗
║          VoxNav 2.0 - AI Browser Agent                   ║
║          Voice-Controlled • Works on Any Site            ║
╚══════════════════════════════════════════════════════════╝
""")

# ========================
# Configuration
# ========================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:8b"

# ========================
# TTS Engine
# ========================
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 175)

def speak(text):
    """Speak text using TTS."""
    print(f"🔊 VoxNav: {text}")
    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
    except:
        pass  # TTS may fail sometimes

# ========================
# Browser Management (Selenium)
# ========================
driver = None

def get_browser():
    """Open browser using Selenium (no asyncio issues)."""
    global driver
    
    if driver:
        try:
            driver.title  # Check if still alive
            return driver
        except:
            driver = None
    
    print("🌐 Opening browser...")
    
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Use webdriver-manager to auto-download chromedriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Start at Google
    driver.get("https://www.google.com")
    speak("Browser ready.")
    
    return driver

# ========================
# Page Analyzer with Screenshots
# ========================
import base64
import tempfile

def capture_screenshot(driver, name="screenshot"):
    """Capture screenshot and save to project folder."""
    try:
        screenshot_path = os.path.join(os.path.dirname(__file__), f"voxnav_{name}.png")
        driver.save_screenshot(screenshot_path)
        print(f"   📸 Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f"   ⚠️ Screenshot failed: {e}")
        return None

def get_page_elements(driver):
    """Extract clickable elements and text from page."""
    try:
        from selenium.webdriver.common.by import By
        
        elements = {
            "url": driver.current_url,
            "title": driver.title,
            "buttons": [],
            "inputs": [],
            "links": [],
            "popups": []
        }
        
        # Get buttons
        for btn in driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit'], [role='button']")[:15]:
            try:
                text = btn.text or btn.get_attribute("value") or btn.get_attribute("aria-label") or ""
                if text.strip():
                    elements["buttons"].append(text.strip()[:50])
            except:
                pass
        
        # Get input fields
        for inp in driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), textarea")[:10]:
            try:
                ph = inp.get_attribute("placeholder") or inp.get_attribute("name") or inp.get_attribute("id") or ""
                if ph:
                    elements["inputs"].append(ph[:50])
            except:
                pass
        
        # Get links
        for link in driver.find_elements(By.CSS_SELECTOR, "a")[:10]:
            try:
                text = link.text.strip()
                if text and len(text) < 50:
                    elements["links"].append(text)
            except:
                pass
        
        # Detect popups/modals
        popup_selectors = [
            "[class*='modal']", "[class*='popup']", "[class*='dialog']",
            "[class*='overlay']", "[role='dialog']", "[class*='close']",
            "[class*='dismiss']", ".fc-consent-root", "#onetrust-consent-sdk"
        ]
        for sel in popup_selectors:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, sel)[:3]:
                    if el.is_displayed():
                        elements["popups"].append(sel)
                        break
            except:
                pass
        
        return elements
    except Exception as e:
        return {"error": str(e)}

def dismiss_popups(driver):
    """Try to close any popups/modals on the page with aggressive approach."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    
    dismissed = False
    
    # IRCTC-specific selectors (most important first)
    irctc_selectors = [
        # IRCTC specific
        ".modal-header button.close",
        ".modal-content button.close",
        "button.btn-primary",  # "OK" buttons
        "button.btn-secondary",
        ".alert button.close",
        "[class*='toast'] button",
        ".cdk-overlay-pane button",
        "mat-dialog-container button",
        # Generic close buttons
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "[class*='close-btn']",
        "[class*='closeBtn']",
        "[class*='close-button']",
        ".modal .close",
        ".popup .close",
        "[class*='dismiss']",
    ]
    
    for sel in irctc_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                if el.is_displayed():
                    try:
                        el.click()
                        dismissed = True
                        time.sleep(0.3)
                        print(f"   ✓ Clicked: {sel}")
                    except:
                        pass
        except:
            pass
    
    # Try clicking buttons by text content
    button_texts = ["OK", "Ok", "CANCEL", "Cancel", "Close", "CLOSE", "Accept", "Got it", 
                    "I understand", "Dismiss", "No Thanks", "Later", "Skip", "×", "X"]
    
    for text in button_texts:
        try:
            # Try exact match
            buttons = driver.find_elements(By.XPATH, f"//button[normalize-space()='{text}']")
            for btn in buttons:
                if btn.is_displayed():
                    btn.click()
                    dismissed = True
                    time.sleep(0.3)
                    print(f"   ✓ Clicked button: '{text}'")
        except:
            pass
        
        try:
            # Try contains match
            buttons = driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
            for btn in buttons:
                if btn.is_displayed():
                    btn.click()
                    dismissed = True
                    time.sleep(0.3)
                    print(f"   ✓ Clicked button containing: '{text}'")
        except:
            pass
    
    # Try clicking any visible modal overlay to dismiss
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR, ".modal-backdrop, .cdk-overlay-backdrop, [class*='overlay']")
        for overlay in overlays:
            if overlay.is_displayed():
                ActionChains(driver).move_to_element(overlay).click().perform()
                time.sleep(0.3)
    except:
        pass
    
    # JavaScript-based popup removal (aggressive)
    try:
        driver.execute_script("""
            // Remove modal backdrops
            document.querySelectorAll('.modal-backdrop, .cdk-overlay-backdrop').forEach(el => el.remove());
            
            // Hide modals
            document.querySelectorAll('.modal, .popup, [role="dialog"], .cdk-overlay-pane').forEach(el => {
                el.style.display = 'none';
            });
            
            // Remove fixed/absolute positioned overlays
            document.querySelectorAll('div').forEach(el => {
                const style = window.getComputedStyle(el);
                if ((style.position === 'fixed' || style.position === 'absolute') && 
                    style.zIndex > 1000 && el.offsetWidth > 200 && el.offsetHeight > 100) {
                    // Likely a popup
                    const rect = el.getBoundingClientRect();
                    if (rect.left > 50 && rect.right < window.innerWidth - 50) {
                        el.style.display = 'none';
                    }
                }
            });
            
            // Enable scrolling
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        """)
        print("   ✓ Applied JavaScript popup removal")
        dismissed = True
    except:
        pass
    
    # Press Escape key
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.2)
    except:
        pass
    
    # Handle browser alerts
    try:
        alert = driver.switch_to.alert
        alert.accept()
        dismissed = True
        print("   ✓ Dismissed browser alert")
    except:
        pass
    
    return dismissed

def analyze_with_ollama(user_goal, page_elements):
    """Ask Ollama what to do next based on page state."""
    prompt = f"""You are a browser automation assistant. 
    
User's goal: {user_goal}

Current page:
- URL: {page_elements.get('url', 'unknown')}
- Title: {page_elements.get('title', 'unknown')}
- Buttons visible: {page_elements.get('buttons', [])}
- Input fields: {page_elements.get('inputs', [])}
- Links: {page_elements.get('links', [])}
- Popups detected: {page_elements.get('popups', [])}

What should I do next? Respond with JSON:
{{
    "action": "click" | "fill" | "wait" | "scroll" | "done",
    "target": "button text or input name",
    "value": "text to type if filling",
    "reason": "brief explanation"
}}

If there are popups, first action should be to close them.
Respond ONLY with JSON, no markdown."""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get("response", "")
            
            # Remove thinking tags
            ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL).strip()
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if json_match:
                return json.loads(json_match.group())
    except Exception as e:
        print(f"   ⚠️ Ollama error: {e}")
    
    return {"action": "wait", "reason": "Could not analyze page"}

def execute_ai_step(driver, action_plan):
    """Execute a single step from AI analysis."""
    from selenium.webdriver.common.by import By
    
    action = action_plan.get("action", "")
    target = action_plan.get("target", "")
    value = action_plan.get("value", "")
    
    try:
        if action == "click":
            # Try to find and click element by text
            element = driver.find_element(By.XPATH, f"//*[contains(text(), '{target}')]")
            element.click()
            print(f"   → Clicked: {target}")
            return True
            
        elif action == "fill":
            # Find input and fill
            for inp in driver.find_elements(By.CSS_SELECTOR, "input, textarea"):
                ph = inp.get_attribute("placeholder") or inp.get_attribute("name") or ""
                if target.lower() in ph.lower():
                    inp.clear()
                    inp.send_keys(value)
                    print(f"   → Filled {target} with: {value}")
                    return True
                    
        elif action == "scroll":
            driver.execute_script("window.scrollBy(0, 300)")
            print("   → Scrolled down")
            return True
            
        elif action == "wait":
            time.sleep(2)
            return True
            
        elif action == "done":
            return True
            
    except Exception as e:
        print(f"   ⚠️ Step failed: {e}")
    
    return False

# ========================
# Translate Hindi to English
# ========================
def translate_to_english(text):
    """Translate Hindi text to English using Ollama."""
    if all(ord(c) < 128 or c.isspace() for c in text):
        return text  # Already English
    
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": f"Translate this Hindi text to English. Output ONLY the English translation, nothing else: {text}",
            "stream": False,
            "options": {"temperature": 0}
        }, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            translated = result.get("response", "").strip()
            # Remove any thinking tags from deepseek
            translated = re.sub(r'<think>.*?</think>', '', translated, flags=re.DOTALL).strip()
            if translated and len(translated) < len(text) * 3:
                print(f"   🔄 Translated: {text} → {translated}")
                return translated
    except Exception as e:
        print(f"   ⚠️ Translation failed: {e}")
    
    return text

# ========================
# Voice Recognition
# ========================
recognizer = sr.Recognizer()

def listen():
    """Listen for voice input."""
    print("\n🎤 Listening... (speak now)")
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            recognizer.pause_threshold = 2.0
            audio = recognizer.listen(source, timeout=15, phrase_time_limit=15)
            print("   ✅ Captured!")
            
            # Try Hindi first, then English
            for lang in ["hi-IN", "en-IN"]:
                try:
                    text = recognizer.recognize_google(audio, language=lang)
                    print(f"   📝 \"{text}\"")
                    return text
                except:
                    continue
                    
            return None
    except Exception as e:
        print(f"   ❌ Mic error: {e}")
        return None

# ========================
# Command Handler
# ========================
def handle_command(cmd, driver):
    """Handle voice commands with Hindi support."""
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from urllib.parse import quote
    
    # Hindi to English mapping for actions
    hindi_actions = {
        "खोलो": "open", "ओपन": "open",
        "सर्च": "search", "खोजो": "search", "ढूंढो": "search",
        "क्लिक": "click",
        "स्क्रॉल": "scroll", "नीचे": "down", "ऊपर": "up",
        "वापस": "back", "बैक": "back",
        "रिफ्रेश": "refresh",
        "टाइप": "type", "लिखो": "type",
        "प्ले": "play", "चलाओ": "play",
        "एंड": "and", "और": "and",
    }
    
    # Hindi to English mapping for sites
    hindi_sites = {
        "अमेजॉन": "amazon", "अमेज़न": "amazon", "एमेज़ॉन": "amazon",
        "युटुब": "youtube", "यूट्यूब": "youtube",
        "फ्लिपकार्ट": "flipkart",
        "गूगल": "google",
        "आईआरसीटीसी": "irctc",
        "फेसबुक": "facebook",
        "इंस्टाग्राम": "instagram",
        "ट्विटर": "twitter",
        "जोमाटो": "zomato",
        "स्विगी": "swiggy",
    }
    
    # Hindi to English for common search terms
    hindi_words = {
        "चॉकलेट": "chocolate", "चॉकलेट्स": "chocolates",
        "जूते": "shoes", "कपड़े": "clothes",
        "फोन": "phone", "मोबाइल": "mobile",
        "लैपटॉप": "laptop", "कंप्यूटर": "computer",
    }
    
    # Convert Hindi to English in the command
    cmd_lower = cmd.lower()
    for hindi, eng in hindi_actions.items():
        cmd_lower = cmd_lower.replace(hindi, eng)
    for hindi, eng in hindi_sites.items():
        cmd_lower = cmd_lower.replace(hindi, eng)
    for hindi, eng in hindi_words.items():
        cmd_lower = cmd_lower.replace(hindi, eng)
    
    # More Hindi mappings for popup/close
    popup_words = {
        "पॉपअप": "popup", "पॉप": "popup", "पॉप्स": "popup",
        "ब्लॉक": "close", "बंद": "close", "हटाओ": "close",
        "क्लोज": "close"
    }
    for hindi, eng in popup_words.items():
        cmd_lower = cmd_lower.replace(hindi, eng)
    
    print(f"   🔄 Processed: {cmd_lower}")
    
    # Site URLs
    sites = {
        "amazon": "https://www.amazon.in",
        "youtube": "https://www.youtube.com",
        "flipkart": "https://www.flipkart.com",
        "google": "https://www.google.com",
        "irctc": "https://www.irctc.co.in",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "twitter": "https://www.twitter.com",
        "linkedin": "https://www.linkedin.com",
        "zomato": "https://www.zomato.com",
        "swiggy": "https://www.swiggy.com",
    }
    
    # CLOSE POPUP / DISMISS POPUP command (expanded triggers)
    popup_triggers = ["close", "popup", "pops", "remove", "dismiss", "block", "hide", 
                      "cancel", "clear", "kill", "stop", "alert"]
    if any(word in cmd_lower for word in popup_triggers):
        print("   🔍 Attempting to close popups...")
        
        # First, show what's on the page for debugging
        try:
            from selenium.webdriver.common.by import By
            modals = driver.find_elements(By.CSS_SELECTOR, ".modal, [role='dialog'], .popup, [class*='modal'], [class*='popup']")
            print(f"   📋 Found {len(modals)} potential popups on page")
            for m in modals[:3]:
                try:
                    print(f"      - {m.get_attribute('class')[:50] if m.get_attribute('class') else 'no class'}")
                except:
                    pass
        except:
            pass
        
        dismissed = dismiss_popups(driver)
        time.sleep(0.5)
        dismissed = dismiss_popups(driver) or dismissed  # Try again
        time.sleep(0.5)
        dismissed = dismiss_popups(driver) or dismissed  # Third try
        
        if dismissed:
            speak("Closed the popup")
        else:
            speak("Tried to close popups. If still visible, I may need to look at the page more carefully.")
        return True
    
    # SCREENSHOT command
    if "screenshot" in cmd_lower or "screen" in cmd_lower or "capture" in cmd_lower or "photo" in cmd_lower:
        path = capture_screenshot(driver, "debug")
        if path:
            speak(f"Screenshot saved to project folder. Check voxnav_debug.png")
            # Also try to open it
            try:
                os.startfile(path)
            except:
                pass
        else:
            speak("Could not capture screenshot")
        return True
    
    # COMPOUND COMMAND: "open X and search Y"
    compound_match = re.search(r'open\s+(\w+)\s+and\s+search\s+(.+)', cmd_lower)
    if compound_match:
        site_name = compound_match.group(1).strip()
        query = compound_match.group(2).strip()
        
        if site_name in sites:
            print(f"   → Opening {site_name} and searching {query}...")
            
            if site_name == "youtube":
                driver.get(f"https://www.youtube.com/results?search_query={quote(query)}")
            elif site_name == "amazon":
                driver.get(f"https://www.amazon.in/s?k={quote(query)}")
            elif site_name == "flipkart":
                driver.get(f"https://www.flipkart.com/search?q={quote(query)}")
            else:
                driver.get(sites[site_name])
                time.sleep(2)
                driver.get(f"https://www.google.com/search?q={quote(query)}+site:{site_name}.com")
            
            time.sleep(2)
            speak(f"Opened {site_name} and searched for {query}")
            return True
    
    # BOOK TRAIN TICKET (IRCTC)
    if "book" in cmd_lower and ("ticket" in cmd_lower or "train" in cmd_lower or "irctc" in cmd_lower):
        # Extract from and to cities
        from_to_match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', cmd_lower)
        if from_to_match:
            from_city = from_to_match.group(1).strip().upper()
            to_city = from_to_match.group(2).strip().upper()
            
            print(f"   → Opening IRCTC for {from_city} to {to_city}...")
            driver.get("https://www.irctc.co.in/nget/train-search")
            time.sleep(3)
            
            # Dismiss any popups first
            print("   🔍 Checking for popups...")
            dismiss_popups(driver)
            time.sleep(1)
            dismiss_popups(driver)  # Try again
            
            user_goal = f"Book train ticket from {from_city} to {to_city}"
            
            # Try multiple times with AI assistance
            for attempt in range(5):
                print(f"   📊 Analyzing page (attempt {attempt+1})...")
                page_elements = get_page_elements(driver)
                
                # If popups detected, dismiss them first
                if page_elements.get("popups"):
                    print("   ⚠️ Popup detected, dismissing...")
                    dismiss_popups(driver)
                    time.sleep(1)
                    continue
                
                # Try to fill FROM field
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    from selenium.webdriver.common.keys import Keys
                    from selenium.webdriver.common.action_chains import ActionChains
                    
                    # Wait longer for page to fully load
                    time.sleep(2)
                    
                    # Wait for FROM input to be clickable
                    from_selectors = [
                        "input[aria-autocomplete='list']",
                        "p-autocomplete input",
                        "input.ng-star-inserted",
                        "#origin input",
                        "input#origin",
                        ".from-stn input",
                        "input[placeholder*='From']",
                        "input[placeholder*='from']",
                        "input[formcontrolname='origin']"
                    ]
                    
                    from_input = None
                    for sel in from_selectors:
                        try:
                            from_input = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                            )
                            if from_input:
                                print(f"   ✓ Found input: {sel}")
                                break
                        except:
                            pass
                    
                    if not from_input:
                        # Try finding all inputs and use first visible one
                        inputs = driver.find_elements(By.CSS_SELECTOR, "input")
                        for inp in inputs:
                            if inp.is_displayed() and inp.is_enabled():
                                ph = inp.get_attribute("placeholder") or ""
                                if "from" in ph.lower() or "origin" in ph.lower() or not ph:
                                    from_input = inp
                                    print(f"   ✓ Found input by placeholder: {ph}")
                                    break
                    
                    if from_input:
                        # Use ActionChains for more reliable clicking
                        ActionChains(driver).move_to_element(from_input).click().perform()
                        time.sleep(0.5)
                        
                        # Clear using JavaScript
                        driver.execute_script("arguments[0].value = '';", from_input)
                        
                        # Type using JavaScript for reliability
                        driver.execute_script(f"arguments[0].value = '{from_city}';", from_input)
                        from_input.send_keys(" ")  # Trigger autocomplete
                        from_input.send_keys(Keys.BACKSPACE)
                        time.sleep(1.5)
                        
                        # Click first autocomplete suggestion
                        try:
                            suggestion = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".ui-autocomplete li, p-autocomplete-panel li, .cdk-overlay-pane li, [class*='autocomplete'] li"))
                            )
                            suggestion.click()
                            print(f"   ✓ Selected FROM: {from_city}")
                        except:
                            from_input.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
                        
                        time.sleep(1)
                        
                        # Now fill TO station - find the second input
                        to_input = None
                        for sel in from_selectors:
                            try:
                                inputs = driver.find_elements(By.CSS_SELECTOR, sel)
                                if len(inputs) >= 2:
                                    to_input = inputs[1]
                                    break
                            except:
                                pass
                        
                        if not to_input:
                            inputs = driver.find_elements(By.CSS_SELECTOR, "input")
                            input_count = 0
                            for inp in inputs:
                                if inp.is_displayed() and inp.is_enabled():
                                    input_count += 1
                                    if input_count == 2:  # Second input is usually TO
                                        to_input = inp
                                        break
                        
                        if to_input:
                            ActionChains(driver).move_to_element(to_input).click().perform()
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].value = '';", to_input)
                            driver.execute_script(f"arguments[0].value = '{to_city}';", to_input)
                            to_input.send_keys(" ")
                            to_input.send_keys(Keys.BACKSPACE)
                            time.sleep(1.5)
                            
                            try:
                                suggestion = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".ui-autocomplete li, p-autocomplete-panel li, .cdk-overlay-pane li, [class*='autocomplete'] li"))
                                )
                                suggestion.click()
                                print(f"   ✓ Selected TO: {to_city}")
                            except:
                                to_input.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
                            
                            speak(f"Filled from {from_city} to {to_city}. Please select date and search.")
                            return True
                    
                    raise Exception("Could not find input fields")
                    
                except Exception as e:
                    print(f"   ⚠️ Attempt {attempt+1} failed: {e}")
                    
                    # Use Ollama to figure out what to do
                    print("   🤖 Asking AI for help...")
                    action_plan = analyze_with_ollama(user_goal, page_elements)
                    print(f"   AI suggests: {action_plan.get('action', 'unknown')} - {action_plan.get('reason', '')}")
                    
                    if action_plan.get("action") == "done":
                        break
                    
                    execute_ai_step(driver, action_plan)
                    time.sleep(2)
            
            speak(f"Opened IRCTC. Please enter: From {from_city}, To {to_city}")
            return True
        else:
            # Just open IRCTC
            driver.get("https://www.irctc.co.in/nget/train-search")
            time.sleep(2)
            dismiss_popups(driver)
            speak("Opened IRCTC. Tell me where you want to go - say 'from city to city'")
            return True
    
    # IRCTC: SELECT DATE (when already on IRCTC)
    if ("irctc" in driver.current_url.lower() or "date" in cmd_lower) and any(word in cmd_lower for word in ["date", "july", "june", "january", "february", "march", "april", "may", "august", "september", "october", "november", "december"]):
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Extract date (format: "2 july 2026" or "22 july")
            date_pattern = r'(\d{1,2})\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{4})?'
            date_match = re.search(date_pattern, cmd_lower)
            
            if date_match:
                day = date_match.group(1)
                month = date_match.group(2)
                year = date_match.group(3) or "2026"
                
                # Month mapping
                months = {"jan": "01", "january": "01", "feb": "02", "february": "02", "mar": "03", "march": "03",
                         "apr": "04", "april": "04", "may": "05", "jun": "06", "june": "06",
                         "jul": "07", "july": "07", "aug": "08", "august": "08", "sep": "09", "september": "09",
                         "oct": "10", "october": "10", "nov": "11", "november": "11", "dec": "12", "december": "12"}
                
                month_num = months.get(month.lower(), "01")
                
                # Click date picker
                date_input = driver.find_element(By.CSS_SELECTOR, "input[formcontrolname='jDate'], p-calendar input, input[placeholder*='Date'], .p-calendar input")
                date_input.click()
                time.sleep(0.5)
                
                # Try to find and click the date
                date_val = f"{day.zfill(2)}/{month_num}/{year}"
                driver.execute_script(f"arguments[0].value = '{date_val}';", date_input)
                date_input.send_keys(Keys.ESCAPE)
                
                print(f"   ✓ Selected date: {day} {month} {year}")
                speak(f"Selected date {day} {month}")
                return True
        except Exception as e:
            print(f"   ⚠️ Date selection failed: {e}")
    
    # IRCTC: SELECT CLASS
    if "irctc" in driver.current_url.lower() and any(word in cmd_lower for word in ["class", "sleeper", "ac", "chair", "3a", "2a", "1a", "sl", "second", "first"]):
        try:
            from selenium.webdriver.common.by import By
            
            # Class mapping
            class_map = {
                "sleeper": "SL", "sl": "SL",
                "3a": "3A", "3 ac": "3A", "third ac": "3A",
                "2a": "2A", "2 ac": "2A", "second ac": "2A",
                "1a": "1A", "1 ac": "1A", "first ac": "1A",
                "chair": "CC", "chair car": "CC", "ac chair": "CC",
                "second": "2S", "second class": "2S", "general": "2S"
            }
            
            selected_class = None
            for pattern, code in class_map.items():
                if pattern in cmd_lower:
                    selected_class = code
                    break
            
            if selected_class:
                # Click class dropdown
                class_dropdown = driver.find_element(By.CSS_SELECTOR, "p-dropdown[formcontrolname='class'], select[name='class'], .class-dropdown")
                class_dropdown.click()
                time.sleep(0.5)
                
                # Find and click the option
                options = driver.find_elements(By.CSS_SELECTOR, "p-dropdownitem li, .p-dropdown-item, option")
                for opt in options:
                    if selected_class in opt.text.upper():
                        opt.click()
                        print(f"   ✓ Selected class: {selected_class}")
                        speak(f"Selected class {selected_class}")
                        return True
        except Exception as e:
            print(f"   ⚠️ Class selection failed: {e}")
    
    # IRCTC: CLICK SEARCH TRAINS BUTTON
    if "irctc" in driver.current_url.lower() and any(word in cmd_lower for word in ["find", "search train", "find train", "submit", "search"]):
        try:
            from selenium.webdriver.common.by import By
            
            # Find search button
            search_btn = driver.find_element(By.CSS_SELECTOR, "button[label='Search'], button.search-btn, button[type='submit'], .trainSearch button")
            search_btn.click()
            print("   ✓ Clicked Search Trains")
            speak("Searching for trains...")
            return True
        except Exception as e:
            print(f"   ⚠️ Search button click failed: {e}")
            return True
    
    # OPEN WEBSITE
    if "open" in cmd_lower:
        for site_name, url in sites.items():
            if site_name in cmd_lower:
                print(f"   → Opening {site_name}...")
                driver.get(url)
                time.sleep(2)
                
                # Auto-dismiss popups
                print("   🔍 Checking for popups...")
                dismiss_popups(driver)
                time.sleep(0.5)
                dismiss_popups(driver)  # Try again
                
                speak(f"Opened {site_name}. What would you like to do?")
                return True
    
    # SEARCH
    if "search" in cmd_lower:
        match = re.search(r'search\s+(?:for\s+)?(.+)', cmd_lower)
        if match:
            query = match.group(1).strip()
            current_url = driver.current_url.lower()
            
            if "youtube" in current_url:
                driver.get(f"https://www.youtube.com/results?search_query={quote(query)}")
            elif "amazon" in current_url:
                driver.get(f"https://www.amazon.in/s?k={quote(query)}")
            elif "flipkart" in current_url:
                driver.get(f"https://www.flipkart.com/search?q={quote(query)}")
            else:
                driver.get(f"https://www.google.com/search?q={quote(query)}")
            
            time.sleep(2)
            speak(f"Searching for {query}")
            return True
    
    # SCROLL
    if "scroll" in cmd_lower:
        if "down" in cmd_lower:
            driver.execute_script("window.scrollBy(0, 500)")
            speak("Scrolled down")
        else:
            driver.execute_script("window.scrollBy(0, -500)")
            speak("Scrolled up")
        return True
    
    # GO BACK
    if "back" in cmd_lower:
        driver.back()
        speak("Going back")
        return True
    
    # REFRESH
    if "refresh" in cmd_lower or "reload" in cmd_lower:
        driver.refresh()
        speak("Page refreshed")
        return True
    
    # CLICK
    if "click" in cmd_lower:
        match = re.search(r'click\s+(?:on\s+)?(.+)', cmd_lower)
        if match:
            target = match.group(1).strip()
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{target}')]")
                element.click()
                time.sleep(1)
                speak(f"Clicked {target}")
                return True
            except:
                speak(f"Could not find {target} to click")
                return True
    
    # PLAY VIDEO (YouTube)
    if "play" in cmd_lower:
        match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:video)?', cmd_lower)
        if match:
            video_num = int(match.group(1))
            try:
                videos = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer, ytd-grid-video-renderer")
                if video_num <= len(videos):
                    videos[video_num - 1].click()
                    speak(f"Playing video {video_num}")
                    return True
            except:
                speak("Could not find video")
                return True
    
    # TYPE TEXT
    if "type" in cmd_lower:
        match = re.search(r'type\s+(.+)', cmd_lower)
        if match:
            text = match.group(1).strip()
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.send_keys(text)
            actions.perform()
            speak(f"Typed: {text}")
            return True
    
    # Not handled
    return False

# ========================
# Main Loop
# ========================
def main():
    speak("VoxNav ready. How can I help you?")
    
    while True:
        # Get voice input
        input("\n⏎ Press ENTER to speak (or type 'quit')... ")
        cmd = listen()
        
        if not cmd:
            speak("I didn't catch that. Please try again.")
            continue
        
        # Check for quit
        if any(word in cmd.lower() for word in ["quit", "exit", "stop", "band", "बंद"]):
            speak("Goodbye!")
            break
        
        # Translate if needed
        english_cmd = translate_to_english(cmd)
        print(f"   📝 Command: {english_cmd}")
        
        # Get browser
        browser = get_browser()
        
        # Handle command
        handled = handle_command(english_cmd, browser)
        
        if not handled:
            speak("I'm not sure how to do that. Try saying 'open', 'search', 'scroll', 'click', or 'go back'.")
    
    # Cleanup
    print("\n🛑 Closing...")
    try:
        if driver:
            driver.quit()
    except:
        pass
    print("✅ Done!")

if __name__ == "__main__":
    main()
