import os
import re
import sys

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME")
PASSWORD = os.getenv("PASSWORD")
API_URL = os.getenv("API_URL")

# Default CAPTCHA answer to use if parsing fails
DEFAULT_CAPTCHA_ANSWER = "10"


def solve_captcha(captcha_text):
    """
    Parse and solve a simple math CAPTCHA.
    
    Expected format: "What is X + Y = ?" or similar
    Returns the calculated answer as a string, or None if parsing fails.
    """
    # Try to find a pattern like "X + Y" or "X - Y" or "X * Y" in the text
    # Common patterns: "What is 3 + 7 = ?", "4 + 10 = ?", etc.
    
    # Match patterns like: number operator number
    pattern = r'(\d+)\s*([+\-*/])\s*(\d+)'
    match = re.search(pattern, captcha_text)
    
    if match:
        num1 = int(match.group(1))
        operator = match.group(2)
        num2 = int(match.group(3))
        
        # Calculate based on operator
        if operator == '+':
            result = num1 + num2
        elif operator == '-':
            result = num1 - num2
        elif operator == '*':
            result = num1 * num2
        elif operator == '/':
            if num2 == 0:
                print("[WARNING] Division by zero detected in CAPTCHA")
                return None
            result = num1 // num2  # Integer division
        else:
            return None
        
        print(f"[DEBUG] Parsed CAPTCHA: {num1} {operator} {num2} = {result}")
        return str(result)
    
    print(f"[WARNING] Could not parse CAPTCHA question: '{captcha_text}'")
    return None


def login(session, url, username, password):
    """Log in to the website and return the authenticated session."""
    print(f"\n[DEBUG] Attempting to access login page: {url}")
    print(f"[DEBUG] Using username: {username[:3]}***{username[-2:] if len(username) > 4 else '***'}")
    print(f"[DEBUG] Request headers: {dict(session.headers)}")
    
    try:
        login_page = session.get(url)
        print(f"[DEBUG] GET request successful. Status: {login_page.status_code}")
        print(f"[DEBUG] Response headers: {dict(login_page.headers)}")
        print(f"[DEBUG] Cookies received: {dict(session.cookies)}")
        login_page.raise_for_status()
    except requests.HTTPError as e:
        print(f"\n[ERROR] Failed to access login page. HTTP Status: {e.response.status_code}")
        print(f"[DEBUG] Response headers: {dict(e.response.headers)}")
        print(f"[DEBUG] Response body (first 500 chars):")
        print(e.response.text[:500])
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\n[ERROR] Network error while accessing login page: {e}")
        sys.exit(1)

    soup = BeautifulSoup(login_page.text, "html.parser")

    # Extract hidden form fields (e.g. CSRF tokens)
    form = soup.find("form")
    if form is None:
        print(f"\n[ERROR] No login form found on the page at {url}.")
        print(f"[DEBUG] Page title: {soup.title.string if soup.title and soup.title.string else 'N/A'}")
        print(f"[DEBUG] Page content (first 500 chars):")
        print(login_page.text[:500])
        sys.exit(1)

    print(f"[DEBUG] Login form found. Action: {form.get('action', 'N/A')}")
    
    payload = {}
    for hidden_input in form.find_all("input", type="hidden"):
        name = hidden_input.get("name")
        value = hidden_input.get("value", "")
        if name:
            payload[name] = value
    
    if payload:
        print(f"[DEBUG] Hidden form fields found: {list(payload.keys())}")

    # Detect username and password field names from the form
    username_field = form.find("input", attrs={"type": "text"}) or form.find(
        "input", attrs={"name": lambda n: n and "user" in n.lower()}
    )
    password_field = form.find("input", attrs={"type": "password"})

    username_name = username_field.get("name", "username") if username_field else "username"
    password_name = password_field.get("name", "password") if password_field else "password"
    
    print(f"[DEBUG] Username field name: '{username_name}'")
    print(f"[DEBUG] Password field name: '{password_name}'")

    payload[username_name] = username
    payload[password_name] = password

    # Handle CAPTCHA if present - parse the question and solve it dynamically
    captcha_field = form.find("input", attrs={"name": "capt"})
    if captcha_field:
        print("[DEBUG] CAPTCHA field detected: name='capt'")
        
        # Find the CAPTCHA question text in the form
        # It's typically in a label or text near the captcha input field
        captcha_question = None
        
        # Look for the captcha field's parent container
        captcha_container = captcha_field.find_parent("div")
        if captcha_container:
            # Get all text from the container
            captcha_text = captcha_container.get_text(strip=True)
            print(f"[DEBUG] CAPTCHA container text: '{captcha_text}'")
            captcha_question = captcha_text
        
        # If not found in parent div, search the entire form for CAPTCHA-related text
        if not captcha_question:
            form_text = form.get_text(separator=" ", strip=True)
            # Look for patterns like "What is X + Y = ?" or "X + Y = ?"
            captcha_match = re.search(r'(What is.+?\?|\d+\s*[+\-*/]\s*\d+\s*=\s*\?)', form_text)
            if captcha_match:
                captcha_question = captcha_match.group(1)
                print(f"[DEBUG] Found CAPTCHA question in form: '{captcha_question}'")
        
        # Solve the CAPTCHA
        if captcha_question:
            captcha_answer = solve_captcha(captcha_question)
            if captcha_answer:
                payload["capt"] = captcha_answer
                print(f"[DEBUG] CAPTCHA answer calculated: '{captcha_answer}'")
            else:
                print(f"[WARNING] Could not solve CAPTCHA, using default answer '{DEFAULT_CAPTCHA_ANSWER}'")
                payload["capt"] = DEFAULT_CAPTCHA_ANSWER
        else:
            print(f"[WARNING] Could not find CAPTCHA question text, using default answer '{DEFAULT_CAPTCHA_ANSWER}'")
            payload["capt"] = DEFAULT_CAPTCHA_ANSWER
    else:
        print("[DEBUG] No CAPTCHA field found in form")

    # Determine form action URL
    action = form.get("action")
    if action:
        if not action.startswith("http"):
            action = requests.compat.urljoin(url, action)
    else:
        action = url
    
    print(f"[DEBUG] Form action URL: {action}")
    
    # Create a safe version of payload for logging (mask password)
    safe_payload = payload.copy()
    if password_name in safe_payload:
        safe_payload[password_name] = "***MASKED***"
    print(f"[DEBUG] Payload to be submitted: {safe_payload}")
    print(f"[DEBUG] Total fields in payload: {len(payload)}")

    print(f"\n[DEBUG] Submitting login form to: {action}")
    try:
        response = session.post(action, data=payload)
        print(f"[DEBUG] POST request successful. Status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Cookies after login: {dict(session.cookies)}")
        print(f"[DEBUG] Response URL (after redirects): {response.url}")
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"\n[ERROR] Login failed. HTTP Status: {e.response.status_code}")
        print(f"[DEBUG] Response headers: {dict(e.response.headers)}")
        print(f"[DEBUG] Response URL: {e.response.url}")
        print(f"[DEBUG] Response body (first 1000 chars):")
        print(e.response.text[:1000])
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\n[ERROR] Network error during login: {e}")
        sys.exit(1)

    # Check for common signs of failed authentication
    result_soup = BeautifulSoup(response.text, "html.parser")
    page_title = result_soup.title.string if result_soup.title and result_soup.title.string else "N/A"
    print(f"[DEBUG] Response page title: {page_title}")
    
    error_indicators = result_soup.find_all(
        string=lambda t: t and any(
            kw in t.lower() for kw in ["invalid", "incorrect", "failed", "error"]
        )
    )
    if error_indicators:
        print("[WARNING] Login may have failed. Page contains error messages:")
        for msg in error_indicators:
            print(f"  - {msg.strip()}")
    else:
        print("[DEBUG] No obvious error messages found in response")

    print("[DEBUG] Login attempt completed\n")
    return response


def scrape(session, url):
    """Scrape content from a page after login."""
    try:
        response = session.get(url)
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error: Failed to scrape page. HTTP Status: {e.response.status_code}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error: Network error while scraping: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")
    return soup


def main():
    if not LOGIN_USERNAME or not PASSWORD or not API_URL:
        print(
            "Error: LOGIN_USERNAME, PASSWORD, and API_URL must be set in the .env file.\n"
            "Copy .env.example to .env and fill in your credentials."
        )
        sys.exit(1)

    session = requests.Session()
    
    # Add browser-like headers to avoid 403 Forbidden errors
    # Using a recent Chrome User-Agent to mimic a real browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    print(f"[DEBUG] Session headers configured: {dict(session.headers)}\n")

    print(f"Logging in to {API_URL} ...")
    login_response = login(session, API_URL, LOGIN_USERNAME, PASSWORD)
    print(f"Login response status: {login_response.status_code}")

    # After login, scrape the page we were redirected to (usually the dashboard)
    # Use the final URL after any redirects, not the original login URL
    dashboard_url = login_response.url
    print(f"\n[DEBUG] Scraping dashboard at: {dashboard_url}")
    
    soup = scrape(session, dashboard_url)
    page_title = soup.title.string if soup.title and soup.title.string else "N/A"
    print("Page title:", page_title)
    print(soup.get_text(separator="\n", strip=True))


if __name__ == "__main__":
    main()
