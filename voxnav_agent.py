#!/usr/bin/env python
"""
VoxNav 3.0 - Vision-First Universal Web Agent
Uses Set-of-Mark (SoM) Tagging + LLaVA (Ollama) for universal control.
"""

import speech_recognition as sr
import pyttsx3
import json
import re
import time
import os
import requests
import base64
import ast
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

print("""
╔══════════════════════════════════════════════════════════╗
║          VoxNav                                          ║
╚══════════════════════════════════════════════════════════╝
""")

# ========================
# Configuration
# ========================
OLLAMA_URL = "http://localhost:11434/api/generate"
# Start with LLaVA for vision, fallback to others if needed? No, user must have LLaVA.
VISION_MODEL = "llava" 
TEXT_MODEL = "llama3.2"  # Fast text model for extraction and guidance
DEBUG_INPUT = False # Set to True for text input debugging


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
        pass

# ========================
# Browser Management
# ========================
driver = None

def get_browser():
    """Open browser using Selenium."""
    global driver
    if driver:
        try:
            driver.title
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
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Start at Google
    driver.get("https://www.google.com")
    speak("Visual System Online.")
    return driver

# ========================
# Set-of-Mark Tagger
# ========================
class SetOfMarkTagger:
    def __init__(self, driver):
        self.driver = driver
        
    def capture_and_tag(self):
        """
        1. Capture screenshot
        2. Find all visible interactive elements
        3. Draw numbered IDs on screenshot
        4. Return (path_to_tagged_image, id_to_element_map)
        """
        from selenium.webdriver.common.by import By
        
        # 1. Capture raw screenshot
        raw_png = self.driver.get_screenshot_as_png()
        image = Image.open(BytesIO(raw_png)).convert("RGB")
        draw = ImageDraw.Draw(image)
        
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
            
        # 2. Find elements
        interactive_selectors = [
            "button", "input", "a", "select", "textarea", 
            "[role='button']", "[role='link']", "[onclick]"
        ]
        
        # Get window size/device pixel ratio for coordinate mapping
        window_width = self.driver.execute_script("return window.innerWidth;")
        window_height = self.driver.execute_script("return window.innerHeight;")
        
        # Use JS to get bounding boxes efficiently
        js_script = """
            var elements = [];
            var selectors = arguments[0];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    var rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && 
                        rect.top >= 0 && rect.left >= 0 &&
                        rect.bottom <= window.innerHeight && rect.right <= window.innerWidth &&
                        window.getComputedStyle(el).visibility !== 'hidden' &&
                        window.getComputedStyle(el).display !== 'none') {
                        elements.push({
                            'tag_name': el.tagName,
                            'rect': rect,
                            'text': el.innerText.substr(0, 20)
                        });
                    }
                });
            });
            return elements;
        """
        
        # Hybrid approach: Find elements in Python, filter by visibility.
        
        elements_map = {}
        tag_id = 0
        
        # Collect candidates (Python side to keep references)
        candidates = []
        for sel in interactive_selectors:
            found = self.driver.find_elements(By.CSS_SELECTOR, sel)
            candidates.extend(found)
            
        # Deduplicate by object ID
        unique_candidates = {el._id: el for el in candidates}.values()
        
        # FIRST PASS: Collect only valid elements
        valid_elements = []
        
        for el in unique_candidates:
            try:
                if not el.is_displayed(): continue
                
                rect = el.rect # {'x': 10, 'y': 10, 'height': 20, 'width': 20}
                if rect['width'] < 10 or rect['height'] < 10: continue
                
                # Check if on screen
                if rect['x'] < 0 or rect['y'] < 0 or rect['x'] > window_width or rect['y'] > window_height:
                    continue
                
                # Extract semantic text for the prompt
                text_content = el.text.strip()
                if not text_content:
                    text_content = el.get_attribute("value") or el.get_attribute("placeholder") or el.get_attribute("aria-label") or el.get_attribute("title") or ""
                
                # Setup position for tag
                x, y = rect['x'], rect['y']
                
                # Store valid element tuple
                valid_elements.append({
                    "element": el,
                    "rect": rect,
                    "x": x,
                    "y": y,
                    "text": text_content,
                    "tag_name": el.tag_name
                })
                
            except:
                continue
                
        # SECOND PASS: Sort elements TOP-TO-BOTTOM by Y position
        # This ensures IDs are assigned in reading order
        valid_elements.sort(key=lambda item: (item['y'], item['x']))
        
        # THIRD PASS: Prioritize INPUT FIELDS over buttons
        # Move inputs to the front so the model sees them first
        inputs = [e for e in valid_elements if e['tag_name'] in ['input', 'textarea', 'select']]
        others = [e for e in valid_elements if e['tag_name'] not in ['input', 'textarea', 'select']]
        valid_elements = inputs + others  # Inputs get lower IDs
        
        # FOURTH PASS: Draw tags and map IDs with clear type labels
        for item in valid_elements:
            tag_id += 1
            
            # Determine element type for clearer labeling
            tag_name = item['tag_name']
            if tag_name == 'input':
                input_type = item['element'].get_attribute('type') or 'text'
                if input_type in ['text', 'search', 'email', 'tel', 'url']:
                    element_type = "INPUT FIELD"
                elif input_type == 'password':
                    element_type = "PASSWORD FIELD"
                elif input_type == 'date':
                    element_type = "DATE PICKER"
                elif input_type in ['submit', 'button']:
                    element_type = "BUTTON"
                elif input_type == 'checkbox':
                    element_type = "CHECKBOX"
                elif input_type == 'radio':
                    element_type = "RADIO BUTTON"
                else:
                    element_type = f"INPUT ({input_type})"
            elif tag_name == 'textarea':
                element_type = "TEXT AREA"
            elif tag_name == 'select':
                element_type = "DROPDOWN"
            elif tag_name == 'button':
                element_type = "BUTTON"
            elif tag_name == 'a':
                element_type = "LINK"
            else:
                element_type = tag_name.upper()
            
            # Draw ID number
            draw.text((item['x']+2, item['y']+2), str(tag_id), fill="white", font=font)
            
            # Create descriptive info with type
            text_preview = item['text'][:40] if item['text'] else "(empty)"
            elements_map[tag_id] = {
                "element": item['element'],
                "type": element_type,
                "info": f"Tag {tag_id}: [{element_type}] - '{text_preview}'"
            }
                
        # Save tagged image
        tagged_path = os.path.join(os.path.dirname(__file__), "vision_state.jpg")
        image.save(tagged_path)
        
        return tagged_path, elements_map

# ========================
# Context Management System
# ========================
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

@dataclass
class BrowsingContext:
    """Represents the browsing context for a single tab."""
    tab_handle: str
    url: str = ""
    title: str = ""
    domain: str = ""
    task_goal: str = ""  # The user's goal for this tab
    knowledge: Dict[str, Any] = field(default_factory=dict)  # Extracted info for this tab
    history: List[str] = field(default_factory=list)  # Actions taken on this tab
    is_primary: bool = False  # Is this the main task tab?
    last_active_time: float = field(default_factory=time.time)
    page_context: str = "UNKNOWN"  # LOGIN_PAGE, SEARCH_RESULTS, etc.
    
    def update_from_driver(self, driver):
        """Update context from current driver state."""
        try:
            self.url = driver.current_url
            self.title = driver.title
            self.domain = urlparse(self.url).netloc
            self.last_active_time = time.time()
        except:
            pass
    
    def to_summary(self) -> str:
        """Return a brief summary of this context."""
        return f"[{self.domain}] {self.title[:30]}... | Goal: {self.task_goal[:20]}..."

class ContextManager:
    """
    Manages browsing context across multiple tabs with:
    - Context tracking for each tab
    - Intentional tab switching
    - Unintended switch detection and recovery
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.contexts: Dict[str, BrowsingContext] = {}  # tab_handle -> BrowsingContext
        self.primary_tab: Optional[str] = None  # The main task tab handle
        self.expected_tab: Optional[str] = None  # The tab we expect to be on
        self.switch_history: List[Dict] = []  # Log of all tab switches
        
        # Initialize with current tabs
        self._sync_tabs()
        
    def _sync_tabs(self):
        """Sync internal state with browser's actual tabs."""
        current_handles = set(self.driver.window_handles)
        known_handles = set(self.contexts.keys())
        
        # Add new tabs
        for handle in current_handles - known_handles:
            self.contexts[handle] = BrowsingContext(tab_handle=handle)
            
        # Remove closed tabs
        for handle in known_handles - current_handles:
            del self.contexts[handle]
            if self.primary_tab == handle:
                self.primary_tab = None
            if self.expected_tab == handle:
                self.expected_tab = None
    
    def get_current_context(self) -> Optional[BrowsingContext]:
        """Get the context for the currently active tab."""
        self._sync_tabs()
        current_handle = self.driver.current_window_handle
        
        if current_handle in self.contexts:
            ctx = self.contexts[current_handle]
            ctx.update_from_driver(self.driver)
            return ctx
        return None
    
    def set_primary_tab(self, goal: str = "", knowledge: Dict = None):
        """Mark the current tab as the primary task tab."""
        self._sync_tabs()
        current_handle = self.driver.current_window_handle
        
        if current_handle in self.contexts:
            ctx = self.contexts[current_handle]
            ctx.is_primary = True
            ctx.task_goal = goal
            if knowledge:
                ctx.knowledge.update(knowledge)
            ctx.update_from_driver(self.driver)
            self.primary_tab = current_handle
            self.expected_tab = current_handle
            print(f"   📌 Primary tab set: {ctx.title[:40]}...")
    
    def switch_to_tab(self, target_handle: str, reason: str = "intentional") -> bool:
        """
        Intentionally switch to a specific tab.
        Logs the switch and updates expected_tab.
        """
        self._sync_tabs()
        
        if target_handle not in self.contexts:
            print(f"   ⚠️ Tab handle {target_handle} not found")
            return False
        
        old_handle = self.driver.current_window_handle
        self.driver.switch_to.window(target_handle)
        self.expected_tab = target_handle
        
        # Update context
        ctx = self.contexts[target_handle]
        ctx.update_from_driver(self.driver)
        
        # Log the switch
        self.switch_history.append({
            "from": old_handle,
            "to": target_handle,
            "reason": reason,
            "time": time.time(),
            "intentional": True
        })
        
        print(f"   🔄 Switched to tab: {ctx.title[:40]}... (reason: {reason})")
        return True
    
    def switch_to_newest_tab(self, reason: str = "new_tab_opened") -> bool:
        """Switch to the most recently opened tab."""
        self._sync_tabs()
        
        if not self.contexts:
            return False
        
        # Get the last handle in the list (newest)
        newest_handle = self.driver.window_handles[-1]
        
        if newest_handle != self.driver.current_window_handle:
            return self.switch_to_tab(newest_handle, reason)
        return False
    
    def switch_to_primary(self, reason: str = "returning_to_primary") -> bool:
        """Switch back to the primary task tab."""
        if self.primary_tab:
            return self.switch_to_tab(self.primary_tab, reason)
        print("   ⚠️ No primary tab set")
        return False
    
    def detect_unintended_switch(self) -> Optional[Dict]:
        """
        Detect if we're on an unexpected tab (unintended switch).
        Returns info about the switch if detected, None otherwise.
        """
        self._sync_tabs()
        
        current_handle = self.driver.current_window_handle
        
        # Check if we're on a different tab than expected
        if self.expected_tab and current_handle != self.expected_tab:
            old_ctx = self.contexts.get(self.expected_tab)
            new_ctx = self.contexts.get(current_handle)
            
            switch_info = {
                "detected": True,
                "expected_tab": self.expected_tab,
                "actual_tab": current_handle,
                "expected_title": old_ctx.title if old_ctx else "Unknown",
                "actual_title": new_ctx.title if new_ctx else "Unknown",
            }
            
            # Log as unintentional
            self.switch_history.append({
                "from": self.expected_tab,
                "to": current_handle,
                "reason": "unintended",
                "time": time.time(),
                "intentional": False
            })
            
            print(f"   ⚠️ UNINTENDED SWITCH DETECTED!")
            print(f"      Expected: {switch_info['expected_title'][:40]}")
            print(f"      Actual: {switch_info['actual_title'][:40]}")
            
            return switch_info
        
        return None
    
    def recover_from_unintended_switch(self, strategy: str = "return_to_expected") -> bool:
        """
        Recover from an unintended tab switch.
        
        Strategies:
        - "return_to_expected": Go back to the expected tab
        - "adopt_new": Accept the new tab as current context
        - "return_to_primary": Go back to primary tab
        """
        switch_info = self.detect_unintended_switch()
        
        if not switch_info:
            return True  # No recovery needed
        
        if strategy == "return_to_expected":
            if switch_info["expected_tab"] in self.contexts:
                return self.switch_to_tab(switch_info["expected_tab"], "recovery_to_expected")
        
        elif strategy == "adopt_new":
            # Accept the current tab as the new expected
            self.expected_tab = switch_info["actual_tab"]
            ctx = self.get_current_context()
            if ctx:
                ctx.update_from_driver(self.driver)
            print(f"   ✅ Adopted new context: {ctx.title[:40] if ctx else 'Unknown'}...")
            return True
        
        elif strategy == "return_to_primary":
            return self.switch_to_primary("recovery_to_primary")
        
        return False
    
    def handle_new_tab_after_click(self) -> Optional[BrowsingContext]:
        """
        Handle tab changes after a click action.
        Detects new tabs and switches to them, preserving context.
        Returns the new context if switched, None otherwise.
        """
        old_handles = set(self.contexts.keys())
        self._sync_tabs()
        new_handles = set(self.contexts.keys())
        
        new_tabs = new_handles - old_handles
        
        if new_tabs:
            # New tab opened - switch to it
            newest_handle = list(new_tabs)[-1]
            
            # Copy knowledge from current context to new tab
            current_ctx = self.get_current_context()
            new_ctx = self.contexts[newest_handle]
            
            if current_ctx:
                new_ctx.task_goal = current_ctx.task_goal
                new_ctx.knowledge = current_ctx.knowledge.copy()
                new_ctx.history = [f"Opened from: {current_ctx.title[:30]}"]
            
            # Switch to the new tab
            self.switch_to_tab(newest_handle, "new_tab_from_click")
            new_ctx.update_from_driver(self.driver)
            
            return new_ctx
        
        # No new tab - check for unintended switch (e.g., redirect)
        current_handle = self.driver.current_window_handle
        if self.expected_tab and current_handle != self.expected_tab:
            # Page redirected or focus changed
            self.expected_tab = current_handle
            ctx = self.get_current_context()
            if ctx:
                ctx.update_from_driver(self.driver)
            print(f"   📍 Context updated after navigation: {ctx.title if ctx else 'Unknown'}")
            return ctx
        
        return None
    
    def get_context_summary(self) -> str:
        """Get a summary of all active contexts."""
        self._sync_tabs()
        lines = [f"📑 Active Tabs ({len(self.contexts)}):"]
        
        for handle, ctx in self.contexts.items():
            is_current = " ← CURRENT" if handle == self.driver.current_window_handle else ""
            is_primary = " ★ PRIMARY" if handle == self.primary_tab else ""
            lines.append(f"  • {ctx.domain}: {ctx.title[:30]}...{is_current}{is_primary}")
        
        return "\n".join(lines)
    
    def update_knowledge(self, key: str, value: Any):
        """Update knowledge in the current context."""
        ctx = self.get_current_context()
        if ctx:
            ctx.knowledge[key] = value
            print(f"   🧠 Knowledge updated: {key} = {str(value)[:30]}...")
    
    def get_knowledge(self, key: str = None) -> Any:
        """Get knowledge from current context."""
        ctx = self.get_current_context()
        if ctx:
            if key:
                return ctx.knowledge.get(key)
            return ctx.knowledge
        return {} if not key else None


# ========================
# CDP Browser Controller (OpenClaw-style)
# ========================
class CDPBrowserController:
    """
    Direct browser control using Chrome DevTools Protocol via Selenium.
    Uses DOM analysis and Ollama for intelligent guidance instead of visual inference.
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.history = []
        self.knowledge = {}
        self._credential_pages_handled = set()
    
    def get_page_structure(self):
        """Extract semantic page structure using JavaScript."""
        script = """
        function getPageStructure() {
            const elements = [];
            const selectors = 'input, button, a, select, textarea, [role="button"], [onclick]';
            const allElements = document.querySelectorAll(selectors);
            
            let id = 0;
            allElements.forEach((el) => {
                const rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) return;
                if (rect.top < 0 || rect.top > window.innerHeight) return;
                
                id++;
                const tagName = el.tagName.toLowerCase();
                const type = el.getAttribute('type') || '';
                const name = el.getAttribute('name') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                const text = el.innerText?.substring(0, 50) || '';
                const value = el.value || '';
                const isEmpty = !value || value.trim() === '';
                
                let elementType = 'ELEMENT';
                if (tagName === 'input') {
                    if (type === 'password') elementType = 'PASSWORD_FIELD';
                    else if (type === 'submit' || type === 'button') elementType = 'BUTTON';
                    else elementType = 'INPUT_FIELD';
                } else if (tagName === 'button') elementType = 'BUTTON';
                else if (tagName === 'a') elementType = 'LINK';
                else if (tagName === 'select') elementType = 'DROPDOWN';
                else if (tagName === 'textarea') elementType = 'TEXT_AREA';
                
                const description = placeholder || ariaLabel || name || text || type;
                
                elements.push({
                    id: id,
                    tag: tagName,
                    type: elementType,
                    inputType: type,
                    name: name,
                    placeholder: placeholder,
                    text: text.substring(0, 30),
                    description: description.substring(0, 40),
                    isEmpty: isEmpty,
                    value: value.substring(0, 20),
                    selector: id
                });
            });
            
            return {
                url: window.location.href,
                title: document.title,
                elements: elements
            };
        }
        return getPageStructure();
        """
        return self.driver.execute_script(script)
    
    def execute_action(self, action, element_id=None, value=None):
        """Execute an action directly via JavaScript."""
        if action == "type" and element_id and value:
            script = f"""
            const elements = document.querySelectorAll('input, textarea, select, [role="button"], [onclick], button, a');
            const el = elements[{element_id - 1}];
            if (el) {{
                el.focus();
                el.value = '';
                el.value = '{value}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
            """
            result = self.driver.execute_script(script)
            if result:
                print(f"   ✅ Typed '{value}' into element {element_id}")
                self.history.append(f"Typed '{value}' into {element_id}")
            return result
        
        elif action == "click" and element_id:
            script = f"""
            const elements = document.querySelectorAll('input, textarea, select, [role="button"], [onclick], button, a');
            const el = elements[{element_id - 1}];
            if (el) {{
                el.click();
                return true;
            }}
            return false;
            """
            result = self.driver.execute_script(script)
            if result:
                print(f"   ✅ Clicked element {element_id}")
                self.history.append(f"Clicked {element_id}")
            return result
        
        elif action == "scroll_down":
            self.driver.execute_script("window.scrollBy(0, 400);")
            print("   ✅ Scrolled down")
            return True
        
        return False
    
    def ask_ollama_what_to_do(self, goal, page_structure):
        """Ask Ollama to decide the next action based on page structure."""
        elements = page_structure.get("elements", [])[:30]
        
        elements_text = ""
        for el in elements:
            status = "(EMPTY)" if el.get("isEmpty") else f"(value: {el.get('value', '')})"
            elements_text += f"\n  ID {el['id']}: [{el['type']}] {el.get('description', '')} {status}"
        
        prompt = f"""You are a browser automation assistant. Decide the next action.

GOAL: {goal}
PAGE: {page_structure.get('title', '')}

ELEMENTS:{elements_text}

VALUES TO USE:
{json.dumps(self.knowledge, indent=2)}

RULES:
1. If [INPUT_FIELD] is (EMPTY), type into it using matching knowledge value
2. Match: FROM → source, TO → destination, date → date
3. Click [BUTTON] only after inputs are filled

Respond with ONLY JSON:
{{"action": "type", "element_id": 1, "value": "text", "reason": "why"}}
"""
        
        try:
            response = requests.post(OLLAMA_URL, json={
                "model": TEXT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            }, timeout=20)
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                print(f"   📝 Ollama raw: {result[:100]}...")
                match = re.search(r'\{[^{}]*\}', result)
                if match:
                    parsed = json.loads(match.group())
                    return parsed
        except Exception as e:
            print(f"   ⚠️ Ollama error: {e}")
        
        # SMART FALLBACK: Rule-based decision when Ollama fails
        print("   🔄 Using smart fallback...")
        return self._smart_fallback(elements, page_structure)
    
    def _smart_fallback(self, elements, page_structure):
        """Rule-based fallback when Ollama doesn't respond."""
        # Find empty input fields
        empty_inputs = [el for el in elements if el.get("type") == "INPUT_FIELD" and el.get("isEmpty")]
        
        # Keywords to match knowledge to fields
        from_keywords = ["from", "source", "origin", "departure", "depart"]
        to_keywords = ["to", "destination", "arrival", "arrive"]
        date_keywords = ["date", "journey", "travel", "when"]
        
        for inp in empty_inputs:
            desc = (inp.get("description", "") + " " + inp.get("name", "")).lower()
            
            # Try to match this input to knowledge
            if any(kw in desc for kw in from_keywords):
                value = self.knowledge.get("source") or self.knowledge.get("from")
                if value:
                    return {"action": "type", "element_id": inp["id"], "value": value, "reason": "Filling FROM field"}
            
            if any(kw in desc for kw in to_keywords):
                value = self.knowledge.get("destination") or self.knowledge.get("to")
                if value:
                    return {"action": "type", "element_id": inp["id"], "value": value, "reason": "Filling TO field"}
            
            if any(kw in desc for kw in date_keywords):
                value = self.knowledge.get("date")
                if value:
                    return {"action": "type", "element_id": inp["id"], "value": value, "reason": "Filling DATE field"}
        
        # No empty inputs matched - look for search/submit button
        if not empty_inputs:
            buttons = [el for el in elements if el.get("type") == "BUTTON"]
            for btn in buttons:
                desc = (btn.get("description", "") + " " + btn.get("text", "")).lower()
                if any(kw in desc for kw in ["search", "submit", "book", "find", "go"]):
                    return {"action": "click", "element_id": btn["id"], "value": None, "reason": "Clicking submit button"}
        
        # Scroll to find more elements
        return {"action": "scroll_down", "element_id": None, "value": None, "reason": "Looking for more elements"}
    
    def step(self, goal):
        """Execute one step using CDP + Ollama."""
        
        # ========================================
        # STEP 0: HARDCODED PRE-ACTIONS
        # Handle popups, cookies, alerts FIRST
        # ========================================
        
        # 0a. Handle browser-level JavaScript alerts
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            print(f"   🚨 Alert detected: {alert_text[:50]}")
            alert.dismiss()
            print("   ✅ Alert dismissed")
            time.sleep(0.5)
        except:
            pass  # No alert present
        
        # 0b. Close cookie banners and popups via JavaScript
        cookie_popup_script = """
        (function() {
            var closed = 0;
            
            // Cookie consent buttons
            var cookieSelectors = [
                '[class*="cookie"] button[class*="accept"]',
                '[class*="cookie"] button[class*="agree"]',
                '[class*="cookie"] button[class*="ok"]',
                '[class*="consent"] button[class*="accept"]',
                '[id*="cookie"] button',
                'button[id*="accept"]',
                '[class*="gdpr"] button',
                '.cookie-banner button',
                '#onetrust-accept-btn-handler',
                '.onetrust-close-btn-handler'
            ];
            
            // Modal/popup close buttons
            var popupSelectors = [
                '[class*="modal"] [class*="close"]',
                '[class*="popup"] [class*="close"]',
                '[aria-label="Close"]',
                '[aria-label="close"]',
                '[class*="modal"] .btn-close',
                '.popup-close',
                '.modal-close',
                '#closePopup',
                '[class*="overlay"] [class*="close"]',
                '.cdk-overlay-backdrop'
            ];
            
            var allSelectors = cookieSelectors.concat(popupSelectors);
            
            allSelectors.forEach(function(sel) {
                try {
                    var els = document.querySelectorAll(sel);
                    els.forEach(function(el) {
                        if (el.offsetParent !== null) {  // Is visible
                            el.click();
                            closed++;
                        }
                    });
                } catch(e) {}
            });
            
            // Press Escape key to close any remaining modals
            document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27}));
            
            return closed;
        })();
        """
        
        try:
            closed = self.driver.execute_script(cookie_popup_script)
            if closed and closed > 0:
                print(f"   🧹 Closed {closed} popup(s)/cookie banner(s)")
                time.sleep(0.5)
        except:
            pass
        
        # 0c. IRCTC-specific: Close any tour/promo popups
        irctc_popup_script = """
        (function() {
            // IRCTC tour popup
            var tourClose = document.querySelector('.introjs-skipbutton, .introjs-donebutton');
            if (tourClose) { tourClose.click(); return 1; }
            
            // IRCTC promo/ad popup
            var promoClose = document.querySelectorAll('[class*="promo"] [class*="close"], [class*="ad"] [class*="close"]');
            promoClose.forEach(function(el) { if(el.offsetParent) el.click(); });
            
            // Any overlay
            var overlay = document.querySelector('.cdk-overlay-container');
            if (overlay && overlay.children.length > 0) {
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27}));
            }
            
            return 0;
        })();
        """
        
        try:
            self.driver.execute_script(irctc_popup_script)
        except:
            pass
        
        time.sleep(0.3)  # Brief pause after popup handling
        
        # ========================================
        # STEP 1: GET PAGE STRUCTURE
        # ========================================
        print("   📊 Analyzing page structure...")
        page_structure = self.get_page_structure()
        
        # Check for login/payment page
        url = page_structure.get("url", "").lower()
        has_password = any(el.get("inputType") == "password" for el in page_structure.get("elements", []))
        
        if has_password and url not in self._credential_pages_handled:
            self._credential_pages_handled.add(url)
            speak("Login required! Please enter your credentials.")
            print("\n   🔐 Login page detected!")
            print("   ➡️  Enter your credentials and press ENTER when done")
            input()
            print("   ✅ Continuing...")
            return "CONTINUE"
        
        # Ask Ollama what to do
        print("   🧠 Asking Ollama for guidance...")
        decision = self.ask_ollama_what_to_do(goal, page_structure)
        
        if decision:
            action = decision.get("action")
            element_id = decision.get("element_id")
            value = decision.get("value")
            reason = decision.get("reason", "")
            
            print(f"   💡 Decision: {action} {element_id or ''} - {reason}")
            
            if action == "done":
                return "DONE"
            
            self.execute_action(action, element_id, value)
            time.sleep(1.5)
            return "CONTINUE"
        
        return "CONTINUE"


# ========================
# Automatic Vision Agent
# ========================
class VisionAgent:
    def __init__(self, driver):
        self.driver = driver
        self.tagger = SetOfMarkTagger(driver)
        self.history = []
        self.task_state = "IDLE"  # IDLE, NAVIGATING, SEARCHING, FILLING, SUBMITTING, VERIFYING
        self.known_tabs = set(driver.window_handles)  # Track known tabs
        self.context_manager = ContextManager(driver)  # Robust context tracking
    
    def switch_to_newest_tab(self):
        """
        Switch to the newest/most recently opened tab if a new tab was detected.
        Returns True if switched to a new tab, False otherwise.
        """
        current_handles = set(self.driver.window_handles)
        new_tabs = current_handles - self.known_tabs
        
        if new_tabs:
            # Switch to the newest tab
            newest_tab = list(new_tabs)[-1]  # Get the most recently opened
            self.driver.switch_to.window(newest_tab)
            self.known_tabs = current_handles  # Update known tabs
            print(f"   🔄 Switched to new tab: {self.driver.title[:50]}...")
            return True
        
        # Update known tabs in case any were closed
        self.known_tabs = current_handles
        return False
        
    def dismiss_popups(self):
        """Auto-dismiss common popups, modals, cookie banners, and browser alerts."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # First, handle browser-level alerts
        try:
            alert = self.driver.switch_to.alert
            alert.dismiss()
            print("   🧹 Dismissed browser alert")
            time.sleep(0.3)
        except:
            pass  # No alert present
        
        popup_selectors = [
            # Cookie banners - comprehensive list
            "[class*='cookie'] button[class*='accept']",
            "[class*='cookie'] button[class*='agree']",
            "[class*='cookie'] button[class*='ok']",
            "[class*='cookie'] button[class*='dismiss']",
            "[class*='cookie'] button[class*='close']",
            "[id*='cookie'] button[class*='accept']",
            "[id*='cookie'] button",
            "[class*='consent'] button[class*='accept']",
            "[class*='consent'] button[class*='agree']",
            "[class*='gdpr'] button[class*='accept']",
            "button[id*='accept']",
            "button[id*='accept-cookies']",
            
            # IRCTC specific popups
            ".popup-close", ".modal-close", "#closePopup",
            "[class*='popupClose']", "[class*='close-btn']",
            "button[class*='btn-close']",
            ".cdk-overlay-backdrop",
            
            # Modal close buttons
            "[class*='modal'] [class*='close']",
            "[class*='modal'] button[class*='btn-close']",
            "[class*='popup'] [class*='close']",
            "[aria-label='Close']", "[aria-label='close']",
            "[title='Close']", "[title='close']",
            "button[class*='dismiss']",
            ".close-button", ".btn-close",
            
            # Notification prompts
            "[class*='notification'] button[class*='no']",
            "[class*='notification'] button[class*='deny']",
            "[class*='notification'] button[class*='close']",
            
            # Overlay/backdrop clicks
            "[class*='overlay-close']",
            "[class*='backdrop-close']",
        ]
        
        dismissed = 0
        for selector in popup_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        try:
                            el.click()
                            dismissed += 1
                            time.sleep(0.3)
                        except:
                            pass
            except:
                pass
        
        # Fallback: Press Escape to close any modal
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        except:
            pass
            
        if dismissed > 0:
            print(f"   🧹 Dismissed {dismissed} popup(s)")
    
    def ask_ollama_for_guidance(self, user_goal, current_situation, available_elements):
        """
        When confused, ask Ollama text model for guidance on what to do next.
        Returns a suggested action dict or None if unable to help.
        """
        print("   🤔 Confused - consulting Ollama for guidance...")
        
        prompt = f"""You are a helpful assistant guiding a web automation agent that is stuck.

## USER'S GOAL
"{user_goal}"

## CURRENT SITUATION
{current_situation}

## AVAILABLE PAGE ELEMENTS
{available_elements[:2000]}

## RECENT HISTORY
{self.history[-5:]}

## YOUR TASK
The vision agent is confused and needs guidance. Based on the goal and current page state, suggest the SINGLE best next action.

Think step by step:
1. What is the user trying to accomplish?
2. What fields need to be filled first before any submit button?
3. What element should be interacted with next?

Return a JSON object with your recommendation:
```json
{{
    "guidance": "Your explanation of what should be done",
    "suggested_action": "type" | "click" | "scroll_down" | "wait" | "ask_user",
    "target_description": "Description of element to interact with (e.g., 'FROM input field')",
    "value": "Value to type if applicable",
    "confidence": "high" | "medium" | "low"
}}
```
"""
        
        try:
            response = requests.post(OLLAMA_URL, json={
                "model": TEXT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            }, timeout=30)
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                # Clean thinking tags
                result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
                
                # Extract JSON
                match = re.search(r'\{.*\}', result, re.DOTALL)
                if match:
                    guidance = json.loads(match.group())
                    print(f"   💡 Ollama suggests: {guidance.get('guidance', '')[:80]}...")
                    return guidance
        except Exception as e:
            print(f"   ⚠️ Ollama guidance failed: {e}")
        
        return None
    
    def is_stuck_in_loop(self):
        """Detect if agent is repeating the same action."""
        if len(self.history) < 3:
            return False
        
        # Check last 3 actions for repetition
        recent = self.history[-3:]
        if len(set(recent)) == 1:
            print("   ⚠️ Loop detected - same action repeated 3 times!")
            return True
        
        # Check for alternating pattern
        if len(self.history) >= 4:
            if self.history[-1] == self.history[-3] and self.history[-2] == self.history[-4]:
                print("   ⚠️ Loop detected - alternating pattern!")
                return True
        
        return False
    
    def detect_credential_page(self):
        """Detect if current page requires login or payment credentials."""
        try:
            url = self.driver.current_url.lower()
            title = self.driver.title.lower()
            page_source = self.driver.page_source.lower()
            
            # Login page indicators
            login_indicators = [
                "login", "signin", "sign in", "log in", "authenticate",
                "username", "password", "forgot password", "register"
            ]
            
            # Payment page indicators  
            payment_indicators = [
                "payment", "checkout", "card number", "cvv", "expiry",
                "credit card", "debit card", "upi", "netbanking", "pay now",
                "billing", "card holder"
            ]
            
            # Check URL and title
            for indicator in login_indicators:
                if indicator in url or indicator in title:
                    return "LOGIN"
            
            for indicator in payment_indicators:
                if indicator in url or indicator in title:
                    return "PAYMENT"
            
            # Check page content for input fields
            from selenium.webdriver.common.by import By
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
            for inp in inputs:
                try:
                    input_type = (inp.get_attribute("type") or "").lower()
                    input_name = (inp.get_attribute("name") or "").lower()
                    input_id = (inp.get_attribute("id") or "").lower()
                    placeholder = (inp.get_attribute("placeholder") or "").lower()
                    
                    combined = f"{input_type} {input_name} {input_id} {placeholder}"
                    
                    if "password" in combined:
                        return "LOGIN"
                    if any(p in combined for p in ["card", "cvv", "expiry", "upi", "otp"]):
                        return "PAYMENT"
                except:
                    continue
            
            return None
        except:
            return None
    
    def wait_for_user_credentials(self, credential_type):
        """Pause and wait for user to enter credentials manually."""
        if credential_type == "LOGIN":
            message = "Login required! Please enter your username and password manually."
        elif credential_type == "PAYMENT":
            message = "Payment details required! Please enter your payment information manually."
        else:
            message = "Sensitive information required! Please enter it manually."
        
        speak(message)
        print(f"\n   🔐 {message}")
        print("   ⏸️  Waiting for you to enter credentials...")
        print("   ➡️  Press ENTER when you're done entering credentials")
        
        # Wait for user confirmation
        input()
        
        speak("Thank you! Continuing with the task.")
        print("   ✅ User confirmed - continuing...")
        time.sleep(1)
        return True
            
    def detect_page_context(self):
        """Detect the type of page we're on for better context."""
        try:
            url = self.driver.current_url.lower()
            title = self.driver.title.lower()
            
            # Check for common page types
            if "login" in url or "signin" in url or "login" in title:
                return "LOGIN_PAGE"
            elif "search" in url or "results" in url:
                return "SEARCH_RESULTS"
            elif "cart" in url or "basket" in url:
                return "SHOPPING_CART"
            elif "checkout" in url or "payment" in url:
                return "CHECKOUT"
            elif "error" in title or "404" in title or "not found" in title:
                return "ERROR_PAGE"
            elif any(site in url for site in ["google.com", "bing.com", "duckduckgo"]):
                return "SEARCH_ENGINE"
            elif any(site in url for site in ["amazon", "flipkart", "ebay"]):
                return "E_COMMERCE"
            elif any(site in url for site in ["irctc", "makemytrip", "booking"]):
                return "BOOKING_SITE"
            else:
                return "GENERAL"
        except:
            return "UNKNOWN"
     
    def fast_type_in_search(self, query):
        """
        UNIVERSAL FAST SEARCH: Auto-detect search box on ANY website and type directly.
        Returns True if successful, False if no search box found.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        
        # Common search input patterns (works on most websites)
        search_selectors = [
            "input[type='search']",
            "input[name='q']",
            "input[name='query']",
            "input[name='search']",
            "input[name='s']",
            "input[placeholder*='search' i]",
            "input[placeholder*='Search' i]",
            "input[aria-label*='search' i]",
            "input[id*='search' i]",
            "input[class*='search' i]",
            "input[type='text'][name*='search' i]",
            "textarea[name*='search' i]",
            # Site-specific patterns
            "#twotabsearchtextbox",  # Amazon
            "#search_form_input_homepage",  # DuckDuckGo
            "input.gLFyf",  # Google
        ]
        
        for selector in search_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        # Found visible search box!
                        print(f"   ⚡ Found search box: {selector}")
                        el.clear()
                        el.send_keys(query)
                        time.sleep(0.3)
                        el.send_keys(Keys.ENTER)
                        print(f"   ✅ Typed and submitted: '{query}'")
                        return True
            except:
                continue
        
        return False
    
    def fast_click_link(self, link_text):
        """
        UNIVERSAL FAST CLICK: Find and click a link by partial text match.
        Returns True if successful.
        """
        from selenium.webdriver.common.by import By
        
        try:
            # Try exact match first
            links = self.driver.find_elements(By.PARTIAL_LINK_TEXT, link_text)
            for link in links:
                if link.is_displayed():
                    link.click()
                    print(f"   ✅ Clicked link: '{link_text}'")
                    return True
        except:
            pass
        
        # Try button/clickable elements with text
        try:
            xpath = f"//*[contains(text(), '{link_text}')]"
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                    print(f"   ✅ Clicked element with text: '{link_text}'")
                    return True
        except:
            pass
        
        return False
    
    def detect_motion(self, delay=0.5, threshold=5.0):
        """
        Capture two consecutive screenshots and compare them to detect motion/changes.
        Useful for detecting: video playing, loading animations, dynamic content.
        
        Args:
            delay: Time between screenshots (seconds)
            threshold: Percentage difference to consider as "motion" (0-100)
        
        Returns:
            dict with: has_motion (bool), change_percent (float), region (str)
        """
        from io import BytesIO
        import numpy as np
        
        try:
            # Capture first screenshot
            raw_png1 = self.driver.get_screenshot_as_png()
            img1 = Image.open(BytesIO(raw_png1)).convert("RGB")
            arr1 = np.array(img1)
            
            # Wait briefly
            time.sleep(delay)
            
            # Capture second screenshot
            raw_png2 = self.driver.get_screenshot_as_png()
            img2 = Image.open(BytesIO(raw_png2)).convert("RGB")
            arr2 = np.array(img2)
            
            # Compare: Calculate pixel-wise difference
            if arr1.shape != arr2.shape:
                return {"has_motion": False, "error": "Resolution changed"}
            
            diff = np.abs(arr1.astype(float) - arr2.astype(float))
            mean_diff = np.mean(diff)
            
            # Calculate what percentage of pixels changed significantly
            significant_changes = np.sum(diff > 30) / diff.size * 100
            
            has_motion = significant_changes > threshold
            
            # Determine which region has most change
            height = arr1.shape[0]
            width = arr1.shape[1]
            
            # Split into quadrants
            top_half = np.mean(diff[:height//2, :, :])
            bottom_half = np.mean(diff[height//2:, :, :])
            left_half = np.mean(diff[:, :width//2, :])
            right_half = np.mean(diff[:, width//2:, :])
            center = np.mean(diff[height//4:3*height//4, width//4:3*width//4, :])
            
            # Find hotspot
            regions = {
                "center": center,
                "top": top_half,
                "bottom": bottom_half,
                "left": left_half,
                "right": right_half
            }
            hotspot = max(regions, key=regions.get)
            
            result = {
                "has_motion": has_motion,
                "change_percent": round(significant_changes, 2),
                "mean_diff": round(mean_diff, 2),
                "hotspot": hotspot,
                "is_video_likely": has_motion and hotspot == "center" and significant_changes > 10
            }
            
            print(f"   🎥 Motion Detection: {result['change_percent']}% change, hotspot: {result['hotspot']}, video_likely: {result['is_video_likely']}")
            return result
            
        except Exception as e:
            print(f"   ⚠️ Motion detection failed: {e}")
            return {"has_motion": False, "error": str(e)}
    
    def check_page_state(self):
        """
        Comprehensive page state check using multiple signals.
        Returns dict with various state indicators.
        """
        state = {
            "url": self.driver.current_url,
            "title": self.driver.title,
            "page_context": self.detect_page_context()
        }
        
        # Check for video elements
        try:
            videos = self.driver.find_elements(By.CSS_SELECTOR, "video")
            state["has_video_element"] = len(videos) > 0
            
            # Check if any video is playing
            if videos:
                for vid in videos:
                    is_playing = self.driver.execute_script(
                        "return !arguments[0].paused && !arguments[0].ended;", vid
                    )
                    if is_playing:
                        state["video_playing"] = True
                        break
                else:
                    state["video_playing"] = False
        except:
            state["has_video_element"] = False
            state["video_playing"] = False
        
        # Check for loading indicators
        try:
            loading_selectors = [
                "[class*='loading']", "[class*='spinner']", "[class*='progress']",
                "[aria-busy='true']", ".loader", ".loading"
            ]
            for sel in loading_selectors:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(el.is_displayed() for el in els):
                    state["is_loading"] = True
                    break
            else:
                state["is_loading"] = False
        except:
            state["is_loading"] = False
        
        return state
        
    def step(self, user_goal):
        """Execute one step of the See-Think-Act loop."""
        
        # 0a. CONTEXT CHECK: Verify we're on the expected tab
        unintended = self.context_manager.detect_unintended_switch()
        if unintended:
            # Smart recovery: if it's a new tab (like login popup), adopt it
            current_ctx = self.context_manager.get_current_context()
            if current_ctx and "login" in current_ctx.url.lower():
                # Login page detected - adopt it, we need to handle login
                self.context_manager.recover_from_unintended_switch(strategy="adopt_new")
                print("   ⚠️ Login page detected - handling it")
            else:
                # Other unintended switch - adopt for now (could be redirect)
                self.context_manager.recover_from_unintended_switch(strategy="adopt_new")
        
        # 0b. CREDENTIAL CHECK: Detect if login/payment page and wait for user
        credential_type = self.detect_credential_page()
        if credential_type:
            # Check if we've already asked for credentials on this page
            current_url = self.driver.current_url
            if not hasattr(self, '_credential_pages_handled'):
                self._credential_pages_handled = set()
            
            if current_url not in self._credential_pages_handled:
                self._credential_pages_handled.add(current_url)
                self.wait_for_user_credentials(credential_type)
                # After user enters credentials, re-scan the page
                return "CONTINUE"
        
        # Update context with current page info
        ctx = self.context_manager.get_current_context()
        if ctx:
            ctx.page_context = self.detect_page_context()
        
        # 0b. LOOP DETECTION: Check if agent is stuck
        if self.is_stuck_in_loop():
            print("   🔄 Breaking out of loop - asking Ollama for guidance...")
            # Clear recent history to prevent loop
            self.history = self.history[:-2]  # Remove last 2 repeating actions
            
            # Get current page info for guidance
            page_info = f"URL: {self.driver.current_url}\nTitle: {self.driver.title}"
            guidance = self.ask_ollama_for_guidance(
                user_goal, 
                page_info,
                "Check page elements for input fields that need to be filled"
            )
            
            if guidance and guidance.get("suggested_action"):
                suggestion = guidance.get("guidance", "")
                self.history.append(f"GUIDANCE: {suggestion[:50]}...")
                print(f"   📝 Ollama says: {suggestion}")
        
        # 0c. CLEANUP: Dismiss any popups first
        self.dismiss_popups()
        
        # 1. CONTEXT: Detect page type
        page_context = self.detect_page_context()
        print(f"   📍 Page Context: {page_context}")
        
        # 2. SEE: Capture and Tag
        print("   👁️  Scanning page...")
        image_path, element_map = self.tagger.capture_and_tag()
        
        # 2. THINK: Ask LLaVA
        # 2. THINK: Ask LLaVA
        print("   🧠 Thinking...")
        
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        # Build Semantic Map for the Prompt
        # This gives the model "reading glasses" for small text/attributes
        semantic_map_items = []
        for k, v in element_map.items():
            if isinstance(v, dict) and 'info' in v:
                semantic_map_items.append(v['info'])
        
        semantic_map_str = "\n".join(semantic_map_items)
        
        # Knowledge from analysis
        knowledge_str = json.dumps(getattr(self, 'knowledge', {}), indent=2)
        
        # Get valid IDs for the prompt
        valid_ids = list(element_map.keys())
        
        prompt = f"""You are an intelligent autonomous web agent controlling a browser to help users accomplish tasks on ANY website.

## USER GOAL
"{user_goal}"

## CURRENT PAGE
- **Type:** {page_context}
- **URL:** {self.driver.current_url[:80]}...

## PAGE ELEMENTS (Tagged on Screenshot)
{semantic_map_str}

**VALID IDs:** {valid_ids}

## EXTRACTED KNOWLEDGE
{knowledge_str}

## RECENT ACTIONS
{self.history[-5:]}

## STEP-BY-STEP DECISION PROCESS

Follow these steps IN ORDER. Stop at the first step that applies:

**STEP 1: CHECK FOR POPUPS**
- Look at the screenshot. Is there a visible popup, modal, or cookie banner?
- If YES → click the close/dismiss/accept button to close it
- If NO → go to Step 2

**STEP 2: FIND EMPTY INPUT FIELDS**
- Look at the elements list. Find any [INPUT FIELD] with "(empty)" or placeholder text
- If there are empty input fields → go to Step 3
- If all inputs are filled → go to Step 4

**STEP 3: FILL THE NEXT EMPTY INPUT**  
- Find the FIRST empty [INPUT FIELD] (lowest ID number)
- Match it to your KNOWLEDGE:
  - FROM/Source field → type the source value
  - TO/Destination field → type the destination value
  - Date field → type the date value
  - Search field → type the search query
- Type into that field and STOP (don't do anything else this turn)

**STEP 4: ALL INPUTS FILLED - NOW CLICK SUBMIT**
- Only now can you click a [BUTTON] like "Search" or "Submit"
- Find the relevant button and click it

**STEP 5: CHECK IF DONE**
- If the goal is achieved (results visible, booking complete, etc.) → action="done"

## OUTPUT (JSON ONLY)
```json
{{
    "step": "Which step (1-5) I am following",
    "analysis": "What I see and what I'm doing",
    "action": "type" | "click" | "scroll_down" | "done",
    "target_id": <number or null>,
    "value": "<text to type or null>",
    "reason": "Brief explanation"
}}
```
"""

        try:
            response = requests.post(OLLAMA_URL, json={
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 300} # Low temp for deterministic actions
            }, timeout=60)
            
            if response.status_code != 200:
                print(f"   ⚠️ Vision Model Error: {response.text}")
                return False

            result_text = response.json().get("response", "")
            
            # Clean JSON
            result_text = re.sub(r'```json', '', result_text)
            result_text = re.sub(r'```', '', result_text)
            
            # Find JSON block
            match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if not match:
                print(f"   ⚠️ Bad JSON from Vision: {result_text}")
                return False

            json_str = match.group()
            
            # Robust JSON Parsing
            try:
                plan = json.loads(json_str)
            except json.JSONDecodeError:
                # 1. Try cleaning trailing commas
                cleaned = re.sub(r',\s*\}', '}', json_str)
                cleaned = re.sub(r',\s*\]', ']', cleaned)
                try:
                    plan = json.loads(cleaned)
                except:
                    # 2. Try ast.literal_eval for single quotes or Python-like dicts
                    # Replace JSON booleans/null with Python equivalents for evaluating
                    try:
                        eval_str = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
                        plan = ast.literal_eval(eval_str)
                    except:
                        print(f"   ⚠️ Bad JSON from Vision: {json_str}")
                        return False
            
            print(f"   💡 Plan: {plan.get('reason')} (Action: {plan.get('action')} {plan.get('target_id')})")
            
            # VALIDATION LAYER: Check action before execution
            action = plan.get("action")
            target_id = plan.get("target_id")
            value = plan.get("value", "")
            
            # Validate action is recognized
            valid_actions = ["click", "type", "scroll_down", "back", "press_key", "done", "ask_user"]
            if action not in valid_actions:
                print(f"   ⚠️ Invalid action: {action}. Retrying...")
                self.history.append(f"ERROR: Invalid action '{action}'")
                return "CONTINUE"
            
            # Validate target_id for actions that need it
            if action in ["click", "type"] and target_id:
                try:
                    target_id = int(target_id)
                    if target_id not in element_map:
                        print(f"   ⚠️ target_id {target_id} not in valid IDs: {list(element_map.keys())[:10]}...")
                        self.history.append(f"ERROR: target_id {target_id} does not exist. Valid: {list(element_map.keys())[:5]}")
                        return "CONTINUE"
                except (ValueError, TypeError):
                    print(f"   ⚠️ Invalid target_id format: {target_id}")
                    self.history.append(f"ERROR: target_id must be a number, got '{target_id}'")
                    return "CONTINUE"
            
            # Validate 'type' action has value
            if action == "type" and not value:
                print("   ⚠️ 'type' action requires a value")
                self.history.append("ERROR: 'type' action needs a value to type")
                return "CONTINUE"
            
            # 3. ACT: Execute (validation passed)
            return self.execute(plan, element_map)
            
        except Exception as e:
            print(f"   ⚠️ Error during step: {e}")
            return False

    def execute(self, plan, element_map):
        action = plan.get("action")
        target_id = plan.get("target_id")
        value = plan.get("value", "")
        
        # Log to history
        self.history.append(f"{action}: {target_id if target_id else ''} {value}")
        
        if action == "done":
            speak("Task completed.")
            return "DONE"
            
        if action == "ask_user":
            speak(f"I need help: {value}")
            
            # Check for credentials/sensitive info
            sensitive_keywords = ["password", "credential", "pin", "otp", "code", "cvv", "secret", "login"]
            is_sensitive = any(k in value.lower() for k in sensitive_keywords)
            
            if is_sensitive:
                speak("Please type this securely in the terminal.")
                response = input(f"   🔒 Secure Input Needed: {value} > ")
            elif DEBUG_INPUT:
                 # Force text input for debugging
                 response = input(f"   ❓ User Input Needed (DEBUG): {value} > ")
            else:
                # Use voice for normal inputs
                speak("Listening for your answer...")
                response = listen()
                if not response:
                    speak("I didn't catch that. Please type it.")
                    response = input(f"   ❓ User Input Needed: {value} > ")
            
            self.history.append(f"User provided: {response}")
            
            # --- FIX: Update Knowledge with Answer ---
            if response:
                new_info = extract_information(response)
                if new_info:
                    # Update knowledge
                    if not hasattr(self, 'knowledge'): self.knowledge = {}
                    self.knowledge.update(new_info)
                    print(f"   🧠 Updated Knowledge: {self.knowledge}")
                    
                    # Also append to history as a system note
                    self.history.append(f"System Note: Knowledge updated with {new_info}")
            # -----------------------------------------

            return "CONTINUE" # Continue with new info
            
        if action == "scroll_down":
            self.driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(1)
            return "CONTINUE"
            
        if action == "back":
            self.driver.back()
            time.sleep(2)
            return "CONTINUE"
            
        if action == "press_key":
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
            
            key_map = {
                "ENTER": Keys.ENTER,
                "RETURN": Keys.RETURN,
                "TAB": Keys.TAB,
                "ESCAPE": Keys.ESCAPE,
                "DOWN": Keys.ARROW_DOWN,
                "UP": Keys.ARROW_UP
            }
            
            key = key_map.get(value.upper(), None)
            if key:
                try:
                    ActionChains(self.driver).send_keys(key).perform()
                    print(f"   ✅ Pressed Key: {value}")
                    time.sleep(2)
                except Exception as e:
                    print(f"   ⚠️ Key Press failed: {e}")
            else:
                 print(f"   ⚠️ Invalid Key: {value}")
            return "CONTINUE"

        # Element Interactions
        if target_id:
            try:
                target_id = int(target_id)
            except:
                print("   ⚠️ Invalid ID")
                return "CONTINUE"
                
            if target_id not in element_map:
                print(f"   ⚠️ Element ID {target_id} not found in map")
                return "CONTINUE"
                
            element = element_map[target_id]["element"]
            
            # Scroll to element
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
            time.sleep(0.5)
            
            if action == "click":
                # Use ContextManager for robust tab handling
                try:
                    element.click()
                    print(f"   ✅ Clicked ID {target_id}")
                except:
                    # JavaScript fallback
                    self.driver.execute_script("arguments[0].click();", element)
                    print(f"   ✅ Clicked ID {target_id} (JS)")
                time.sleep(2)  # Wait for nav/new tab to open
                
                # Context-aware tab handling
                new_ctx = self.context_manager.handle_new_tab_after_click()
                if new_ctx:
                    # Update current context knowledge
                    if hasattr(self, 'knowledge') and self.knowledge:
                        new_ctx.knowledge.update(self.knowledge)
                    print(f"   📍 New context: {new_ctx.title[:40]}...")
                else:
                    # Check for unintended switches (redirects, popups)
                    unintended = self.context_manager.detect_unintended_switch()
                    if unintended:
                        # Adopt the new context (it's likely a redirect, not a popup)
                        self.context_manager.recover_from_unintended_switch(strategy="adopt_new")
                
                # Update known_tabs for backward compatibility
                self.known_tabs = set(self.driver.window_handles)
                
            elif action == "type":
                try:
                    element.clear()
                    element.send_keys(value)
                    print(f"   ✅ Typed '{value}' into ID {target_id}")
                    # Wait longer for autocomplete/dropdowns to appear
                    time.sleep(1.5)
                except Exception as e:
                    if "stale element" in str(e).lower():
                        print(f"   ⚠️ Element became stale, will retry on next step")
                        self.history.append(f"STALE: Element {target_id} changed after typing")
                    else:
                        print(f"   ⚠️ Type failed: {e}")
                
                
        return "CONTINUE"

# ========================
# Helper: Date Parser Fix
# ========================
def parse_date_natural_language(text):
    """
    Normalizes dates in text like '26th Feb 26' to '26 February 2026'.
    Returns the FULL TEXT with the date replaced, NOT just the date.
    """
    # Remove ordinal suffixes from numbers (1st -> 1, 2nd -> 2, etc.)
    clean_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text, flags=re.IGNORECASE)
    
    # Regex for DD Month YY/YYYY patterns
    match = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{2,4})', clean_text)
    if match:
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        if len(year) == 2: 
            year = "20" + year
        
        # Replace the date pattern in the original text with normalized date
        normalized_date = f"{day} {month} {year}"
        result = clean_text[:match.start()] + normalized_date + clean_text[match.end():]
        return result.strip()
    
    return clean_text  # Return cleaned text even if no date found

# ========================
# Helper: Smart Input Normalization
# ========================
def normalize_voice_input(text):
    """
    Intelligently normalize voice input to handle common recognition errors.
    Fixes misheard words, normalizes site names, city names, and common phrases.
    """
    original = text
    text = text.lower().strip()
    
    # ===== COMMON VOICE RECOGNITION ERRORS =====
    # Format: "misheard": "correct"
    word_corrections = {
        # Action words - be careful not to create duplicate words
        "team": "ticket",   # Very common error
        "tekat": "ticket",
        "ticked": "ticket",
        "bull": "book",
        "searching": "search",
        "searched": "search",
        "opens": "open",
        "opened": "open",
        "go 2": "go to",
        "goto": "go to",
        
        # Site names
        "amazone": "amazon",
        "amazin": "amazon",
        "amazon.in": "amazon",
        "amazon.com": "amazon",
        "you tube": "youtube",
        "u tube": "youtube",
        "utube": "youtube",
        "google.com": "google",
        "flip cart": "flipkart",
        "flipcard": "flipkart",
        "flipcart": "flipkart",
        "irct": "irctc",
        "irtc": "irctc",
        "i r c t c": "irctc",
        "railway": "irctc",
        "train booking": "irctc",
        "zometo": "zomato",
        "swigi": "swiggy",
        "sweegy": "swiggy",
        "wiki": "wikipedia",
        "read it": "reddit",
        
        # City names (Indian cities commonly misheard)
        "kota junction": "kota",
        "kotah": "kota",
        "udaipur city": "udaipur",
        "udaypur": "udaipur",
        "mewad": "mewar",
        "mawar": "mewar",
        "jaipur junction": "jaipur",
        "jaypur": "jaipur",
        "delhi junction": "delhi",
        "new delhi": "delhi",
        "mumbai central": "mumbai",
        "bombay": "mumbai",
        "kolkata": "calcutta",
        "chennai central": "chennai",
        "madras": "chennai",
        "bangalore city": "bangalore",
        "bangaluru": "bangalore",
        "hydrabad": "hyderabad",
        "ahemdabad": "ahmedabad",
        "ahmadabad": "ahmedabad",
        "lucknow junction": "lucknow",
        "varanasi junction": "varanasi",
        "banaras": "varanasi",
        
        # Date/Time common errors
        "to day": "today",
        "to morrow": "tomorrow",
        "to night": "tonight",
        "next weak": "next week",
        "this weak": "this week",
        
        # Prepositions often misheard
        "form": "from",
        "frome": "from",
        "4": "for",
        "2": "to",
        "till": "to",
        "untill": "to",
        "on date": "on",  # "on date 5th" -> "on 5th"
        
        # Hindi/English mix fixes
        "se": "from",
        "tak": "to",
        "ke liye": "for",
        "ka": "of",
        "ki": "of",
        "chahiye": "want",
        "karo": "do",
        "kholo": "open",
        "dhundho": "search",
        "dikhao": "show",
    }
    
    # Apply word corrections
    for wrong, correct in word_corrections.items():
        # Use word boundary matching to avoid replacing parts of words
        pattern = r'\b' + re.escape(wrong) + r'\b'
        text = re.sub(pattern, correct, text, flags=re.IGNORECASE)
    
    # ===== SMART INFERENCE =====
    # If "ticket" or "train" mentioned but no "book", prepend "book"
    if any(w in text for w in ["ticket", "train", "flight", "bus"]) and "book" not in text:
        text = "book " + text
    
    # If site name mentioned but no action, assume "open"
    sites = ["amazon", "youtube", "google", "flipkart", "irctc", "zomato", "swiggy", "wikipedia", "reddit"]
    has_action = any(w in text for w in ["open", "go to", "search", "book", "navigate"])
    has_site = any(s in text for s in sites)
    if has_site and not has_action:
        text = "open " + text
    
    # ===== TRAIN NAME NORMALIZATION =====
    train_names = {
        "mewar express": "12963 Mewar Express",
        "mewad express": "12963 Mewar Express",
        "mawar express": "12963 Mewar Express",
        "rajdhani": "Rajdhani Express",
        "shatabdi": "Shatabdi Express",
        "duronto": "Duronto Express",
        "garib rath": "Garib Rath Express",
    }
    for short, full in train_names.items():
        if short in text:
            text = text.replace(short, full)
    
    # Capitalize first letter
    text = text[0].upper() + text[1:] if text else text
    
    if text.lower() != original.lower():
        print(f"   🔧 Normalized: '{original}' -> '{text}'")
    
    return text

# ========================
# Helper: Information Extraction (The Brain)
# ========================
def extract_information(text):
    """
    Enhanced information extraction with intent detection, context, and self-correction handling.
    Returns structured data for web browsing tasks.
    """
    # FIRST: Normalize the input to fix common errors
    text = normalize_voice_input(text)
    
    print(f"   🧠 Analyzing goal: '{text}'...")
    
    # PRE-PROCESSING: Detect and handle self-corrections
    # Common correction phrases that indicate the user is overwriting previous info
    correction_markers = [
        "no wait", "no, wait", "actually", "I mean", "i mean", 
        "sorry", "correction", "not that", "no no", "wait wait",
        "let me correct", "I meant", "i meant", "change that to",
        "make it", "instead", "rather", "nahi", "matlab", "ruko"  # Hindi corrections too
    ]
    
    # If correction detected, try to extract the FINAL intent
    has_correction = any(marker in text.lower() for marker in correction_markers)
    if has_correction:
        print(f"   🔄 Correction detected in input!")
    
    prompt = f"""You are an intelligent command parser for a voice-controlled web browser.

## USER COMMAND
"{text}"

## IMPORTANT: SELF-CORRECTION HANDLING
The user may correct themselves mid-sentence. Look for phrases like:
- "no wait", "actually", "I mean", "sorry", "not that"
- Example: "search for shoes... no wait, search for laptops" → FINAL intent is "laptops"
- Example: "open amazon... actually youtube" → FINAL target is "youtube"
- Example: "book from Jaipur... I mean from Kota to Delhi" → source is "Kota", destination is "Delhi"

**ALWAYS use the CORRECTED/FINAL information, not the initial one.**

## CURRENT DATE
{time.strftime("%Y-%m-%d")}

## YOUR TASK
1. Detect if the user corrected themselves
2. Extract the FINAL, CORRECTED information only
3. Return structured data with:
   - **intent**: The final action (search, navigate, book, buy, click, scroll, read, login, fill_form)
   - **target_site**: The final website to use (amazon, google, youtube, irctc, flipkart, etc.) or null
   - **search_query**: The final search query (if applicable)
   - **entities**: Any specific data like source, destination, date, product, username, etc.
   - **was_corrected**: true if the user made a correction, false otherwise

## EXAMPLES

"search for shoes on amazon... no wait, search for laptops"
→ {{"intent": "search", "target_site": "amazon", "search_query": "laptops", "was_corrected": true}}

"open youtube... actually I want amazon"
→ {{"intent": "navigate", "target_site": "amazon", "was_corrected": true}}

"book from Jaipur to Delhi... I mean from Kota"
→ {{"intent": "book", "source": "Kota", "destination": "Delhi", "was_corrected": true}}

"search for laptops on amazon"
→ {{"intent": "search", "target_site": "amazon", "search_query": "laptops", "was_corrected": false}}

"scroll down"
→ {{"intent": "scroll", "direction": "down", "was_corrected": false}}

## OUTPUT
Return ONLY valid JSON with the FINAL, CORRECTED information. Be precise.
"""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": TEXT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0}
        }, timeout=60)
        
        if response.status_code == 200:
            result = response.json().get("response", "")
            # Clean thinking tokens
            result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
            result = re.sub(r'```json', '', result)
            result = re.sub(r'```', '', result)
            
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except:
                    # Try robust parsing
                    cleaned = re.sub(r',\s*\}', '}', match.group())
                    data = json.loads(cleaned)
                
                print(f"   💡 Intent: {data.get('intent', '?')} | Site: {data.get('target_site', '?')} | Query: {data.get('search_query', '?')}")
                return data
            else:
                print(f"   ⚠️ No JSON found in response: {result[:100]}")
                
    except Exception as e:
        print(f"   ⚠️ Extraction failed: {e}")
    
    # FALLBACK: Rule-based extraction for common patterns
    text_lower = text.lower()
    fallback = {"intent": "unknown"}
    
    # Detect search intent
    if "search" in text_lower or "find" in text_lower or "look for" in text_lower:
        fallback["intent"] = "search"
        # Extract what comes after "search for", "search", "find"
        for pattern in ["search for ", "search ", "find ", "look for "]:
            if pattern in text_lower:
                query_part = text_lower.split(pattern, 1)[1]
                # Remove site mentions from query
                for site in ["on amazon", "on youtube", "on google", "on flipkart"]:
                    query_part = query_part.replace(site, "").strip()
                fallback["search_query"] = query_part
                break
    
    # Detect navigation intent
    elif "open" in text_lower or "go to" in text_lower or "navigate" in text_lower:
        fallback["intent"] = "navigate"
    
    # Detect scroll
    elif "scroll" in text_lower:
        fallback["intent"] = "scroll"
        fallback["direction"] = "down" if "down" in text_lower else "up"
    
    # Detect click
    elif "click" in text_lower:
        fallback["intent"] = "click"
    
    # Detect back/forward
    elif "back" in text_lower:
        fallback["intent"] = "navigate"
        fallback["action"] = "back"
    
    # Detect target site
    for site in ["amazon", "youtube", "google", "flipkart", "irctc", "zomato", "swiggy", "wikipedia", "reddit"]:
        if site in text_lower:
            fallback["target_site"] = site
            break
    
    if fallback.get("intent") != "unknown":
        print(f"   💡 Fallback: {fallback}")
        return fallback
        
    return {}

# ========================
# Helper: Smart Endpointing (Fast Rule-Based)
# ========================
def check_speech_completeness(transcript):
    """
    FAST rule-based check if user has finished speaking.
    Uses pattern matching instead of slow LLM calls.
    Returns: "COMPLETE" or "INCOMPLETE"
    """
    text = transcript.lower().strip()
    word_count = len(text.split())
    
    # Very short commands are incomplete
    if word_count < 3:
        print(f"   ⏳ Too short ({word_count} words), waiting for more...")
        return "INCOMPLETE"
    
    # Trailing prepositions/conjunctions suggest incomplete
    incomplete_endings = [" on", " to", " from", " for", " and", " or", " the", " a", " in", " at", " with"]
    for ending in incomplete_endings:
        if text.endswith(ending):
            print(f"   ⏳ Ends with '{ending.strip()}', waiting for more...")
            return "INCOMPLETE"
    
    # BOOKING commands: need source, destination, or date
    if any(word in text for word in ["book", "ticket", "train", "flight", "bus"]):
        has_from = any(word in text for word in ["from", "se", "origin"])
        has_to = any(word in text for word in ["to", "tak", "destination"])
        has_date = any(word in text for word in ["march", "april", "may", "june", "july", "august", 
                                                   "september", "october", "november", "december",
                                                   "january", "february", "tomorrow", "today", 
                                                   "monday", "tuesday", "wednesday", "thursday",
                                                   "friday", "saturday", "sunday", "/", "-"])
        
        if has_from and has_to:
            print(f"   ✅ Booking command looks complete (from/to present)")
            return "COMPLETE"
        elif word_count >= 8:  # Long enough, probably complete
            print(f"   ✅ Long booking command ({word_count} words), assuming complete")
            return "COMPLETE"
    
    # SEARCH commands: need a query
    if any(word in text for word in ["search", "find", "look for", "show me"]):
        if word_count >= 4:  # "search for laptops" = 3 words min
            print(f"   ✅ Search command looks complete")
            return "COMPLETE"
    
    # NAVIGATION commands: need a target
    if any(word in text for word in ["open", "go to", "navigate"]):
        if word_count >= 2:  # "open amazon" = 2 words
            print(f"   ✅ Navigation command looks complete")
            return "COMPLETE"
    
    # Default: if command is long enough, assume complete
    if word_count >= 6:
        print(f"   ✅ Command has {word_count} words, assuming complete")
        return "COMPLETE"
    
    print(f"   ⏳ Command may be incomplete, waiting briefly...")
    return "INCOMPLETE"

# ========================
# Main Loop (Voice)
# ========================
def main():
    speak("VoxNav Universal Agent Starting...")
    
    # Check for LLaVA (light check without opening browser)
    try:
        print("   🧠 Checking Vision Model (LLaVA)...")
        res = requests.post(OLLAMA_URL, json={"model": VISION_MODEL, "prompt": "hi", "stream": False}, timeout=15)
        if res.status_code != 200:
            speak(f"Warning: Please ensure {VISION_MODEL} is pulled in Ollama.")
        else:
            print("   ✅ LLaVA ready!")
    except:
        speak(f"Warning: Please ensure {VISION_MODEL} is pulled in Ollama.")

    speak("Microphone calibrating... please be quiet for a moment.")
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        speak("Ready! How can I help you?")
    
    agent = None
    
    while True:
        # Allow text input or just Enter for voice
        user_text = input("\n⏎ Press ENTER to speak (or type your command/quit)... ")
        
        cmd = ""
        
        if user_text.strip():
            cmd = user_text.strip()
            print(f"   📝 Text Input: {cmd}")
        else:
            # Voice Input Loop with Smart Endpointing
            full_command = ""
            while True:
                part = listen()
                
                if not part:
                    if full_command: 
                        # If we have some command but get silence, assume done after one retry
                        break
                    else:
                        speak("I didn't hear anything clearly. Please try again.")
                        break # Break to outer loop to prompt again
                
                full_command += " " + part
                full_command = full_command.strip()
                
                # QUICK BYPASS: Skip LLM check for short, common commands
                quick_commands = ["scroll", "click", "back", "forward", "refresh", "stop", "quit", "exit", "done", "yes", "no", "ok", "okay", "help"]
                is_quick = any(full_command.lower().startswith(q) or full_command.lower() == q for q in quick_commands)
                
                if is_quick:
                    print(f"   ⚡ Quick command detected: '{full_command}'")
                    break
                
            # Check completeness for complex commands
                status = check_speech_completeness(full_command)
                if status == "INCOMPLETE":
                    speak("Go on...")
                    # Loop back to listen again
                    continue
                else:
                    break
            
            cmd = full_command
            print(f"   >>> Full command captured: '{cmd}'")
        
        if not cmd:
            continue
            
        if "quit" in cmd.lower() or "exit" in cmd.lower():
            break
            
        # Fix dates in command
        cmd = parse_date_natural_language(cmd)
        
        # 1. Analyze Goal (Information Capsules)
        goal_info = extract_information(cmd)
        
        # Check for missing info (Simple heuristic for now, can be expanded)
        if goal_info.get("task") == "book_ticket":
            missing = []
            if not goal_info.get("source") and not goal_info.get("from"): missing.append("departure city")
            if not goal_info.get("destination") and not goal_info.get("to"): missing.append("destination city")
            if not goal_info.get("date"): missing.append("date")
            
            if missing:
                speak(f"I need more information about {', '.join(missing)}.")
                continue
        
        # Init browser IF NEEDED (Lazy load)
        driver = get_browser()
        if not agent:
            # Use CDP controller for direct DOM manipulation (more reliable than vision)
            agent = CDPBrowserController(driver)
            print("   🎮 CDP Browser Controller initialized")
        else:
            # New command? Clear history so it doesn't get confused by old tasks
            agent.history = []
        
        # Store knowledge in agent
        if not hasattr(agent, 'knowledge'): agent.knowledge = {}
        agent.knowledge.update(goal_info)  # Merge new info into existing knowledge
            
            
        # SMART START: Auto-navigate or Search
        # Sites with DIRECT SEARCH URLs (skip vision entirely for known patterns)
        direct_search_sites = {
            "amazon": "https://www.amazon.in/s?k={query}",
            "flipkart": "https://www.flipkart.com/search?q={query}",
            "youtube": "https://www.youtube.com/results?search_query={query}",
            "google": "https://www.google.com/search?q={query}",
            "wiki": "https://en.wikipedia.org/wiki/Special:Search?search={query}",
            "reddit": "https://www.reddit.com/search/?q={query}",
        }
        
        # Sites with just homepage URLs
        common_sites = {
            "irctc": "https://www.irctc.co.in/nget/train-search",
            "zomato": "https://www.zomato.com",
            "swiggy": "https://www.swiggy.com",
        }
        
        # Check if we align with a known site
        navigated = False
        search_completed = False
        goal_lower = cmd.lower()
        search_query = goal_info.get("search_query", "")
        
        # Random delay for anti-bot (0.5 to 2 seconds)
        import random
        anti_bot_delay = random.uniform(0.5, 2.0)
        
        # 1. FAST PATH: Direct URL search (skips vision entirely!)
        for site_key, search_url in direct_search_sites.items():
            if site_key in goal_lower and search_query:
                # Use direct search URL
                from urllib.parse import quote
                final_url = search_url.format(query=quote(search_query))
                print(f"   ⚡ FAST: Direct search on {site_key} for '{search_query}'")
                driver.get(final_url)
                time.sleep(2 + anti_bot_delay)
                navigated = True
                search_completed = True
                speak(f"Searching for {search_query} on {site_key}")
                break
        
        # 2. Homepage navigation for sites without direct search
        if not navigated:
            for site_key, site_url in common_sites.items():
                if site_key in goal_lower:
                    if site_key not in driver.current_url:
                        print(f"   🚀 Auto-Navigating to {site_key}...")
                        driver.get(site_url)
                        time.sleep(2 + anti_bot_delay)
                        navigated = True
                    break
                    
        # 3. Also check direct search sites for homepage-only access
        if not navigated:
            for site_key, search_url in direct_search_sites.items():
                if site_key in goal_lower:
                    # Go to homepage (strip search params)
                    base_url = search_url.split("/s?")[0].split("/search")[0].split("/results")[0]
                    if site_key not in driver.current_url:
                        print(f"   🚀 Auto-Navigating to {site_key}...")
                        driver.get(base_url)
                        time.sleep(2 + anti_bot_delay)
                        navigated = True
                    break
                
        # 4. Smart Fallback: Google Search for unknown commands
        if not navigated:
            search_query_fallback = None
            if "open " in goal_lower:
                search_query_fallback = goal_lower.split("open ", 1)[1]
            elif "search for " in goal_lower:
                search_query_fallback = goal_lower.split("search for ", 1)[1]
            elif "google " in goal_lower:
                search_query_fallback = goal_lower.split("google ", 1)[1]
                 
            if search_query_fallback:
                from urllib.parse import quote
                print(f"   🚀 Smart Nav: Searching for '{search_query_fallback}'...")
                driver.get(f"https://www.google.com/search?q={quote(search_query_fallback)}")
                time.sleep(2 + anti_bot_delay)
                navigated = True
                search_completed = True
        
        # If search was completed via direct URL, we might be DONE already
        if search_completed:
            speak(f"Search complete. Results are on screen.")
            # Skip vision loop for simple searches? Let user decide next action
            continue
        
        # UNIVERSAL FAST SEARCH: Try to find search box on current page
        # Works for ANY website, not just hardcoded ones
        if search_query and not search_completed:
            speak(f"Looking for search box...")
            time.sleep(1)  # Wait for page to settle
            if agent.fast_type_in_search(search_query):
                time.sleep(2 + anti_bot_delay)
                speak(f"Searched for {search_query}. Results are on screen.")
                continue  # Done with this command
            else:
                print("   ℹ️ No search box found, falling back to vision agent...")

        # Start Auto-Drive Loop
        speak(f"Analyzing goal: {cmd}")
        
        # Run the agent loop
        agent.goal = cmd
        max_steps = 15
        steps = 0
        
        while steps < max_steps:
            status = agent.step(agent.goal)
            
            if status == "DONE":
                break
            if status == False:
                speak("I'm stuck. Please help.")
                break
                
            steps += 1
            
        if steps >= max_steps:
            speak("I stopped after too many steps. Need verify.")

# ========================
# Voice Recognition
# ========================
recognizer = sr.Recognizer()

def listen():
    # Tuned for longer usage but better noise rejection
    recognizer.energy_threshold = 400  # Default 300 -> 400 (Less sensitive to hum)
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 2.0   # 3.0s was too long for noise; 2.0s is a good balance
    recognizer.phrase_threshold = 0.3
    recognizer.non_speaking_duration = 0.5 

    print("\n🎤 Listening... (Speak now)")
    with sr.Microphone() as source:
        try:
            # Removed phrase_time_limit to allow long inputs
            audio = recognizer.listen(source, timeout=15)
            print("   ✅ Captured")
            text = recognizer.recognize_google(audio)
            print(f"   📝 You said: {text}")
            return text
        except sr.WaitTimeoutError:
            print("   ❌ Timeout: No speech detected")
            return None
        except sr.UnknownValueError:
            print("   ❌ Only noise detected")
            return None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

if __name__ == "__main__":
    main()
