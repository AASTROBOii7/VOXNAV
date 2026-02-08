import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from selenium.webdriver.common.by import By

def get_browser():
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def tag_page(driver):
    # 1. Capture raw screenshot
    raw_png = driver.get_screenshot_as_png()
    image = Image.open(BytesIO(raw_png)).convert("RGB")
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
        
    # 2. Find elements
    interactive_selectors = [
        "button", "input", "a", "select", "textarea", 
        "[role='button']", "[role='link']", "[onclick]"
    ]
    
    window_width = driver.execute_script("return window.innerWidth;")
    window_height = driver.execute_script("return window.innerHeight;")
    
    elements_map = {}
    tag_id = 0
    
    candidates = []
    print("Finding elements...")
    for sel in interactive_selectors:
        found = driver.find_elements(By.CSS_SELECTOR, sel)
        candidates.extend(found)
        
    unique_candidates = {el.id: el for el in candidates}.values()
    print(f"Found {len(unique_candidates)} unique candidates.")
    
    for el in unique_candidates:
        try:
            if not el.is_displayed():
                continue
            
            rect = el.rect
            if rect['width'] < 10 or rect['height'] < 10:
                continue
            
            if rect['x'] < 0 or rect['y'] < 0 or rect['x'] > window_width or rect['y'] > window_height:
                continue
            
            tag_id += 1
            x, y = rect['x'], rect['y']
            draw.text((x+2, y+2), str(tag_id), fill="white", font=font)
            
            text_content = el.text.strip()
            if not text_content:
                text_content = el.get_attribute("value") or el.get_attribute("placeholder") or el.get_attribute("aria-label") or el.get_attribute("title") or ""
            
            elements_map[tag_id] = {
                "tag_name": el.tag_name,
                "text": text_content[:50]
            }
        except Exception as e:
            # print(f"Error processing element: {e}")
            continue
            
    image.save("debug_vision_state.jpg")
    print(f"Tagged {tag_id} elements.")
    return elements_map

if __name__ == "__main__":
    driver = get_browser()
    try:
        print("Navigating to Amazon...")
        driver.get("https://www.amazon.in")
        time.sleep(5)
        
        print("Running tagger...")
        elements = tag_page(driver)
        
        print("\n--- Detected Elements ---")
        for tid, info in elements.items():
            print(f"{tid}: {info}")
            
        # Check for search bar specifically
        search_found = False
        for tid, info in elements.items():
            if "search" in info['text'].lower() or "input" in info['tag_name'].lower():
                print(f"Possible search element: {tid} - {info}")
                search_found = True
        
        if not search_found:
            print("\n❌ CRITICAL: No search-related elements found!")
        else:
            print("\n✅ Search elements found.")
            
    finally:
        # driver.quit()
        pass
