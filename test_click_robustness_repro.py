import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Create a dummy HTML file for testing
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Click Test Page</title>
</head>
<body>
    <h1>Click Test</h1>
    
    <!-- Case 1: Simple button -->
    <button id="btn1" onclick="console.log('Clicked Simple Button')">Simple Button</button>
    
    <!-- Case 2: Case sensitivity -->
    <button id="btn2" onclick="console.log('Clicked CASE Button')">CASE SENSITIVE</button>
    
    <!-- Case 3: Nested text -->
    <button id="btn3" onclick="console.log('Clicked Nested Button')">
        <span>Nested</span> <b>Text</b> Button
    </button>
    
    <!-- Case 4: Attribute based (aria-label) -->
    <button id="btn4" aria-label="Aria Label Button" onclick="console.log('Clicked Aria Button')">
        <i class="icon"></i> (Icon Only)
    </button>
    
    <!-- Case 5: Input submit -->
    <input type="submit" value="Submit Input" onclick="console.log('Clicked Submit Input')">
    
    <!-- Case 6: Link pretending to be button -->
    <a href="#" role="button" onclick="console.log('Clicked Link Button'); return false;">Link Button</a>
    
    <!-- Case 7: Partial match -->
    <button id="btn7" onclick="console.log('Clicked Partial Button')">Click Me Please</button>

</body>
</html>
"""

html_path = os.path.abspath("click_test.html")
with open(html_path, "w") as f:
    f.write(html_content)

print(f"Created test file at: {html_path}")

# Initialize driver
options = Options()
options.add_argument("--headless=new") 
driver = webdriver.Chrome(options=options)
driver.get(f"file:///{html_path}")

# Import the new function from voxnav_agent
import sys
sys.path.append(os.getcwd())
from voxnav_agent import find_element_by_fuzzy_text

def test_click_implementation(driver, target):
    try:
        element = find_element_by_fuzzy_text(driver, target)
        if element:
            element.click()
            return True
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

# Test Cases
test_cases = [
    ("Simple Button", True),
    ("simple button", True), # Should fail in old (case sensitive xpath)
    ("CASE SENSITIVE", True),
    ("case sensitive", True), # Should fail
    ("Nested Text Button", True), # Might fail depending on xpath text() behavior with children
    ("Aria Label Button", True), # Will definitely fail in old
    ("Submit Input", True), # Might fail if value attribute isn't checked by text()
    ("Link Button", True),
    ("Click Me", True), # Partial match
]

print("\n--- Testing NEW Implementation ---")
for target, expected in test_cases:
    success = test_click_implementation(driver, target)
    result = "✅ PASS" if success else "❌ FAIL"
    print(f"Target: '{target}' -> {result}")

driver.quit()
