"""
Browser Controller for VoxNav
Uses Playwright for browser automation based on voice commands.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Run: pip install playwright && python -m playwright install chromium")


@dataclass
class ActionResult:
    success: bool
    action: str
    message: str
    data: Optional[Dict] = None


class BrowserController:
    """Controls browser based on voice commands."""
    
    def __init__(self, headless: bool = False):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed")
        
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._running = False
    
    def start(self):
        """Start browser."""
        if self._running:
            return
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=100  # Slow down for visibility
        )
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        self.page = self.context.new_page()
        self._running = True
        print("✅ Browser started")
    
    def stop(self):
        """Stop browser safely."""
        if not self._running:
            return
        
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        
        self._running = False
        print("🛑 Browser stopped")
    
    def navigate(self, url: str) -> ActionResult:
        """Navigate to URL."""
        if not self._running:
            self.start()
        
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = self.page.title()
            return ActionResult(True, "navigate", f"Opened: {title}")
        except Exception as e:
            return ActionResult(False, "navigate", f"Failed: {e}")
    
    def search_google(self, query: str) -> ActionResult:
        """Search on Google."""
        try:
            self.navigate("https://www.google.com")
            self.page.wait_for_selector('textarea[name="q"]', timeout=10000)
            self.page.fill('textarea[name="q"]', query)
            self.page.press('textarea[name="q"]', "Enter")
            self.page.wait_for_load_state("domcontentloaded")
            return ActionResult(True, "search", f"Searched: {query}")
        except Exception as e:
            return ActionResult(False, "search", f"Failed: {e}")
    
    def search_amazon(self, query: str) -> ActionResult:
        """Search on Amazon India."""
        try:
            self.navigate("https://www.amazon.in")
            self.page.wait_for_selector('#twotabsearchtextbox', timeout=10000)
            self.page.fill('#twotabsearchtextbox', query)
            self.page.press('#twotabsearchtextbox', "Enter")
            self.page.wait_for_load_state("domcontentloaded")
            return ActionResult(True, "search", f"Amazon: {query}")
        except Exception as e:
            return ActionResult(False, "search", f"Failed: {e}")
    
    def search_flipkart(self, query: str) -> ActionResult:
        """Search on Flipkart."""
        try:
            self.navigate("https://www.flipkart.com")
            # Close login popup if present
            try:
                self.page.click('button._2KpZ6l._2doB4z', timeout=3000)
            except:
                pass
            self.page.wait_for_selector('input[name="q"]', timeout=10000)
            self.page.fill('input[name="q"]', query)
            self.page.press('input[name="q"]', "Enter")
            self.page.wait_for_load_state("domcontentloaded")
            return ActionResult(True, "search", f"Flipkart: {query}")
        except Exception as e:
            return ActionResult(False, "search", f"Failed: {e}")
    
    def execute_intent(self, intent: str, slots: Dict) -> ActionResult:
        """Execute action based on intent."""
        intent = intent.upper()
        
        if intent == "SEARCH":
            query = slots.get("item") or slots.get("query", "")
            platform = str(slots.get("platform", "")).lower()
            
            if "amazon" in platform:
                return self.search_amazon(query)
            elif "flipkart" in platform:
                return self.search_flipkart(query)
            else:
                return self.search_google(query)
        
        elif intent == "BOOKING":
            platform = str(slots.get("platform", "")).lower()
            if "irctc" in platform or "train" in str(slots):
                return self.navigate("https://www.irctc.co.in")
            elif "zomato" in platform or "food" in str(slots):
                return self.navigate("https://www.zomato.com")
            else:
                return self.navigate("https://www.makemytrip.com")
        
        elif intent == "NAVIGATION":
            url = slots.get("url", "")
            if url:
                return self.navigate(url)
        
        return ActionResult(False, intent, "Unknown intent")
