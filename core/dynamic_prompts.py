"""
Dynamic Prompt Builder - Adapts prompts based on website context.
Analyzes current webpage to provide contextual assistance.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class WebsiteConfig:
    """Configuration for a specific website."""
    domain: str
    name: str
    capabilities: List[str]
    system_prompt: str
    form_mappings: Dict[str, str] = field(default_factory=dict)
    actions: Dict[str, str] = field(default_factory=dict)


# Pre-configured website contexts
WEBSITE_CONTEXTS: Dict[str, WebsiteConfig] = {
    # Indian Railway Booking
    'irctc.co.in': WebsiteConfig(
        domain='train_booking',
        name='IRCTC Indian Railways',
        capabilities=['book_train', 'check_pnr', 'cancel_ticket', 'check_train_status'],
        system_prompt="""You are helping the user on IRCTC (Indian Railways booking system).
        
AVAILABLE ACTIONS:
- Search for trains between stations
- Book train tickets (requires login)
- Check PNR status
- Cancel booked tickets
- Check train running status

FORM FIELDS TO IDENTIFY:
- From Station (origin)
- To Station (destination)  
- Journey Date
- Travel Class (Sleeper, AC 3-Tier, AC 2-Tier, AC 1-Tier)
- Quota (General, Tatkal, Ladies, Senior Citizen)

Guide the user step by step through the booking process.
If user is not logged in, suggest logging in first.""",
        form_mappings={
            'source': '#fromStation, input[name="source"], #origin',
            'destination': '#toStation, input[name="destination"], #dest',
            'date': '#journeyDate, input[name="journeyDate"]',
            'class': '#journeyClass, select[name="class"]',
            'quota': '#journeyQuota, select[name="quota"]'
        }
    ),
    
    # MakeMyTrip
    'makemytrip.com': WebsiteConfig(
        domain='travel',
        name='MakeMyTrip',
        capabilities=['book_flight', 'book_hotel', 'book_bus', 'book_cab', 'holiday_packages'],
        system_prompt="""You are assisting on MakeMyTrip travel booking platform.

AVAILABLE ACTIONS:
- Search and book flights (domestic/international)
- Book hotels
- Book buses
- Book cabs/rentals
- Browse holiday packages

Help users find the best deals and complete their bookings efficiently.
Compare prices when asked and suggest alternatives.""",
        form_mappings={
            'source': '[data-cy="fromCity"], #fromCity',
            'destination': '[data-cy="toCity"], #toCity',
            'date': '[data-cy="departureDate"], #departure',
            'return_date': '[data-cy="returnDate"], #return',
            'passengers': '[data-cy="travellers"]'
        }
    ),
    
    # Amazon India
    'amazon.in': WebsiteConfig(
        domain='shopping',
        name='Amazon India',
        capabilities=['search_product', 'add_to_cart', 'checkout', 'track_order'],
        system_prompt="""You are helping the user shop on Amazon India.

AVAILABLE ACTIONS:
- Search for products
- Add items to cart
- Apply filters (price, rating, brand)
- Proceed to checkout
- Track existing orders

Help users find products, compare options, and complete purchases.
Mention deals and discounts when visible.""",
        form_mappings={
            'search': '#twotabsearchtextbox, input[name="field-keywords"]',
            'add_to_cart': '#add-to-cart-button',
            'buy_now': '#buy-now-button'
        }
    ),
    
    # Flipkart
    'flipkart.com': WebsiteConfig(
        domain='shopping',
        name='Flipkart',
        capabilities=['search_product', 'add_to_cart', 'checkout', 'track_order'],
        system_prompt="""You are helping the user shop on Flipkart.

AVAILABLE ACTIONS:
- Search products
- Filter by price, brand, rating
- Add to cart
- Buy now
- Track orders

Help users find the best deals on Flipkart.""",
        form_mappings={
            'search': 'input[name="q"], ._3704LK input',
            'add_to_cart': '._2KpZ6l._2U9uOA',
            'buy_now': '._2KpZ6l._2HKlqd'
        }
    ),
    
    # Zomato
    'zomato.com': WebsiteConfig(
        domain='food',
        name='Zomato',
        capabilities=['search_restaurant', 'order_food', 'book_table'],
        system_prompt="""You are helping the user on Zomato.

AVAILABLE ACTIONS:
- Search for restaurants
- Order food delivery
- Book a table
- Browse menus
- Apply filters (cuisine, rating, price)

Help users find great food and restaurants.""",
        form_mappings={
            'search': 'input[placeholder*="Search"]',
            'location': 'input[placeholder*="Location"]'
        }
    ),
    
    # Swiggy
    'swiggy.com': WebsiteConfig(
        domain='food',
        name='Swiggy',
        capabilities=['search_restaurant', 'order_food'],
        system_prompt="""You are helping the user order food on Swiggy.

AVAILABLE ACTIONS:
- Search restaurants or dishes
- Order food for delivery
- Apply offers and coupons
- Track orders

Help users order food quickly.""",
        form_mappings={
            'search': 'input[placeholder*="Search"]'
        }
    ),
    
    # BookMyShow
    'bookmyshow.com': WebsiteConfig(
        domain='entertainment',
        name='BookMyShow',
        capabilities=['book_movie', 'book_event', 'book_show'],
        system_prompt="""You are helping the user on BookMyShow.

AVAILABLE ACTIONS:
- Search and book movie tickets
- Book event tickets
- Book plays/shows
- Select seats
- Apply offers

Help users book entertainment tickets.""",
        form_mappings={
            'search': 'input[placeholder*="Search"]',
            'location': '.gmjPR input'
        }
    ),
    
    # Ola
    'olacabs.com': WebsiteConfig(
        domain='cab_booking',
        name='Ola Cabs',
        capabilities=['book_cab', 'book_rental', 'book_outstation'],
        system_prompt="""You are helping book a cab on Ola.

AVAILABLE ACTIONS:
- Book immediate cab ride
- Schedule a ride
- Book rental cabs
- Book outstation trips""",
        form_mappings={
            'pickup': '#pickup-address',
            'drop': '#drop-address'
        }
    ),
    
    # Uber
    'uber.com': WebsiteConfig(
        domain='cab_booking',
        name='Uber',
        capabilities=['book_cab', 'book_rental'],
        system_prompt="""You are helping book a ride on Uber.

AVAILABLE ACTIONS:
- Book a ride
- Schedule a trip
- Book Uber Rentals""",
        form_mappings={
            'pickup': 'input[data-testid="pickup-input"]',
            'drop': 'input[data-testid="destination-input"]'
        }
    ),
    
    # Google
    'google.com': WebsiteConfig(
        domain='search',
        name='Google Search',
        capabilities=['search', 'navigate'],
        system_prompt="""You are helping the user search on Google.

AVAILABLE ACTIONS:
- Perform web searches
- Navigate to results
- Use specialized searches (Images, Maps, News)""",
        form_mappings={
            'search': 'input[name="q"], textarea[name="q"]'
        }
    ),
}

# Default configuration for unknown websites
DEFAULT_CONFIG = WebsiteConfig(
    domain='general',
    name='Unknown Website',
    capabilities=['navigate', 'search', 'fill_form', 'click'],
    system_prompt="""You are a general-purpose web navigation assistant.

CAPABILITIES:
- Navigate to pages and sections
- Fill forms
- Click buttons and links
- Read and summarize page content
- Search within the website

Analyze the current page and help the user accomplish their goal.
Identify interactive elements and guide the user.""",
    form_mappings={}
)


@dataclass
class PageContext:
    """Extracted context from a webpage."""
    url: str
    title: str
    domain: str
    interactive_elements: List[str]
    forms: List[Dict[str, Any]]
    current_step: Optional[str] = None
    visible_text_summary: Optional[str] = None


class DynamicPromptBuilder:
    """
    Builds context-aware prompts based on the current website and page content.
    """
    
    def __init__(self, gemini_client=None):
        """
        Initialize the Dynamic Prompt Builder.
        
        Args:
            gemini_client: Optional pre-configured Gemini client for page analysis
        """
        self.gemini_client = gemini_client
        self.page_context: Optional[PageContext] = None
        
    def get_website_config(self, url: str) -> WebsiteConfig:
        """
        Get website configuration for a given URL.
        
        Args:
            url: The current page URL
            
        Returns:
            WebsiteConfig for the website
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ''
            hostname = hostname.replace('www.', '')
            
            # Check for exact or partial matches
            for domain, config in WEBSITE_CONTEXTS.items():
                if domain in hostname:
                    return config
            
            return DEFAULT_CONFIG
            
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return DEFAULT_CONFIG
    
    def extract_page_context(self, html_content: str, url: str) -> PageContext:
        """
        Extract context from HTML content.
        
        Args:
            html_content: The page's HTML
            url: Current page URL
            
        Returns:
            PageContext with extracted information
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else ''
            
            # Extract domain
            parsed = urlparse(url)
            domain = parsed.hostname or ''
            
            # Find interactive elements
            interactive = []
            for elem in soup.select('button, [role="button"], input[type="submit"], a[href]'):
                text = elem.get_text(strip=True) or elem.get('aria-label', '') or elem.get('value', '')
                if text and len(text) < 50:
                    interactive.append(text)
            
            # Find forms
            forms = []
            for form in soup.select('form'):
                form_data = {'action': form.get('action', ''), 'fields': []}
                for inp in form.select('input, select, textarea'):
                    field_name = inp.get('name') or inp.get('id') or inp.get('placeholder', '')
                    if field_name:
                        form_data['fields'].append(field_name)
                if form_data['fields']:
                    forms.append(form_data)
            
            # Detect current step (progress indicators)
            current_step = None
            step_elem = soup.select_one('.step-active, .current-step, [aria-current="step"]')
            if step_elem:
                current_step = step_elem.get_text(strip=True)
            
            return PageContext(
                url=url,
                title=title,
                domain=domain,
                interactive_elements=interactive[:15],  # Limit to 15
                forms=forms[:5],  # Limit to 5 forms
                current_step=current_step
            )
            
        except ImportError:
            logger.warning("BeautifulSoup not installed, using minimal context extraction")
            return PageContext(
                url=url,
                title='',
                domain=urlparse(url).hostname or '',
                interactive_elements=[],
                forms=[]
            )
        except Exception as e:
            logger.error(f"Error extracting page context: {e}")
            return PageContext(
                url=url,
                title='',
                domain='',
                interactive_elements=[],
                forms=[]
            )
    
    def build_prompt(
        self,
        user_query: str,
        url: str,
        html_content: Optional[str] = None,
        intent: Optional[str] = None,
        slots: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a context-aware prompt for Gemini.
        
        Args:
            user_query: The user's request
            url: Current page URL
            html_content: Optional HTML content for context extraction
            intent: Optional classified intent
            slots: Optional filled slots
            
        Returns:
            Complete prompt string for Gemini
        """
        # Get website config
        config = self.get_website_config(url)
        
        # Extract page context if HTML provided
        if html_content:
            self.page_context = self.extract_page_context(html_content, url)
        else:
            self.page_context = PageContext(
                url=url,
                title='',
                domain=urlparse(url).hostname or '',
                interactive_elements=[],
                forms=[]
            )
        
        # Build the prompt
        prompt_parts = [
            config.system_prompt,
            "",
            "═" * 50,
            "CURRENT PAGE CONTEXT:",
            f"• URL: {url}",
            f"• Website: {config.name}",
            f"• Page Title: {self.page_context.title}",
        ]
        
        if self.page_context.interactive_elements:
            prompt_parts.append(f"• Available Actions: {', '.join(self.page_context.interactive_elements[:10])}")
        
        if self.page_context.forms:
            form_summary = [f"Form with fields: {', '.join(f['fields'][:5])}" for f in self.page_context.forms[:3]]
            prompt_parts.append(f"• Forms: {'; '.join(form_summary)}")
        
        if self.page_context.current_step:
            prompt_parts.append(f"• Current Step: {self.page_context.current_step}")
        
        prompt_parts.extend([
            "",
            "═" * 50,
            "WEBSITE CAPABILITIES:",
            *[f"• {cap}" for cap in config.capabilities],
            "",
            "FORM FIELD SELECTORS (for automation):",
            json.dumps(config.form_mappings, indent=2),
        ])
        
        if intent:
            prompt_parts.extend([
                "",
                f"DETECTED INTENT: {intent}",
            ])
        
        if slots:
            prompt_parts.extend([
                f"FILLED SLOTS: {json.dumps(slots)}",
            ])
        
        prompt_parts.extend([
            "",
            "═" * 50,
            f'USER REQUEST: "{user_query}"',
            "",
            "RESPOND WITH:",
            "1. Clear understanding of what the user wants",
            "2. Step-by-step guidance specific to this website",
            "3. Any form fields to fill (with CSS selectors from above)",
            "4. Confirmation before taking any action",
            "",
            "If returning action commands, use this JSON format:",
            '[{"action": "fill", "selector": "...", "value": "..."},',
            ' {"action": "click", "selector": "..."}]'
        ])
        
        return "\n".join(prompt_parts)
    
    def get_action_prompt(
        self,
        intent: str,
        sub_intent: str,
        slots: Dict[str, Any],
        url: str
    ) -> str:
        """
        Build a prompt specifically for generating automation actions.
        
        Args:
            intent: The classified intent
            sub_intent: Specific sub-intent
            slots: Filled slot values
            url: Current page URL
            
        Returns:
            Prompt for generating browser automation commands
        """
        config = self.get_website_config(url)
        
        return f"""Generate browser automation commands for the following action.

WEBSITE: {config.name} ({url})
INTENT: {intent} - {sub_intent}
DATA TO FILL: {json.dumps(slots, ensure_ascii=False)}

AVAILABLE SELECTORS:
{json.dumps(config.form_mappings, indent=2)}

Generate a JSON array of actions to perform in order:
[
  {{"action": "fill", "selector": "<css_selector>", "value": "<value>"}},
  {{"action": "click", "selector": "<css_selector>"}},
  {{"action": "wait", "seconds": <number>}},
  {{"action": "scroll", "direction": "down|up"}}
]

Return ONLY valid JSON array, no explanation."""
