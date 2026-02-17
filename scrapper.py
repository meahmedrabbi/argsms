import os
import pickle
import re
import sys

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME")
PASSWORD = os.getenv("PASSWORD")
API_URL = os.getenv("API_URL")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Default CAPTCHA answer to use if parsing fails
DEFAULT_CAPTCHA_ANSWER = "10"
COOKIE_FILE = ".cookies.pkl"


def debug_print(message):
    """Print debug messages only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(message)


def save_cookies(session):
    """Save session cookies to a file."""
    try:
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(session.cookies, f)
        print(f"✓ Cookies saved to {COOKIE_FILE}")
    except Exception as e:
        print(f"[WARNING] Failed to save cookies: {e}")


def load_cookies(session):
    """Load cookies from file into the session."""
    try:
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'rb') as f:
                session.cookies.update(pickle.load(f))
            print(f"✓ Cookies loaded from {COOKIE_FILE}")
            return True
    except Exception as e:
        print(f"[WARNING] Failed to load cookies: {e}")
    return False


def check_cookies_valid(session, test_url):
    """Check if saved cookies are still valid by accessing a protected page."""
    try:
        response = session.get(test_url)
        # If we get redirected to login page, cookies are invalid
        if "login" in response.url.lower():
            return False
        # Check if we're on a valid dashboard/protected page
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else ""
        # If title contains "Login", cookies are invalid
        if "login" in title.lower():
            return False
        return True
    except Exception:
        return False


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
        
        debug_print(f"[DEBUG] Parsed CAPTCHA: {num1} {operator} {num2} = {result}")
        return str(result)
    
    print(f"[WARNING] Could not parse CAPTCHA question: '{captcha_text}'")
    return None


def login(session, url, username, password):
    """Log in to the website and return the authenticated session."""
    print(f"\n→ Logging in to {url}...")
    debug_print(f"[DEBUG] Using username: {username[:3]}***{username[-2:] if len(username) > 4 else '***'}")
    
    try:
        login_page = session.get(url)
        debug_print(f"[DEBUG] GET request successful. Status: {login_page.status_code}")
        debug_print(f"[DEBUG] Cookies received: {dict(session.cookies)}")
        login_page.raise_for_status()
    except requests.HTTPError as e:
        print(f"\n[ERROR] Failed to access login page. HTTP Status: {e.response.status_code}")
        debug_print(f"[DEBUG] Response body (first 500 chars):")
        debug_print(e.response.text[:500])
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\n[ERROR] Network error while accessing login page: {e}")
        sys.exit(1)

    soup = BeautifulSoup(login_page.text, "html.parser")

    # Extract hidden form fields (e.g. CSRF tokens)
    form = soup.find("form")
    if form is None:
        print(f"\n[ERROR] No login form found on the page at {url}.")
        debug_print(f"[DEBUG] Page title: {soup.title.string if soup.title and soup.title.string else 'N/A'}")
        sys.exit(1)

    debug_print(f"[DEBUG] Login form found. Action: {form.get('action', 'N/A')}")
    
    payload = {}
    for hidden_input in form.find_all("input", type="hidden"):
        name = hidden_input.get("name")
        value = hidden_input.get("value", "")
        if name:
            payload[name] = value
    
    if payload:
        debug_print(f"[DEBUG] Hidden form fields found: {list(payload.keys())}")

    # Detect username and password field names from the form
    username_field = form.find("input", attrs={"type": "text"}) or form.find(
        "input", attrs={"name": lambda n: n and "user" in n.lower()}
    )
    password_field = form.find("input", attrs={"type": "password"})

    username_name = username_field.get("name", "username") if username_field else "username"
    password_name = password_field.get("name", "password") if password_field else "password"
    
    debug_print(f"[DEBUG] Username field name: '{username_name}'")
    debug_print(f"[DEBUG] Password field name: '{password_name}'")

    payload[username_name] = username
    payload[password_name] = password

    # Handle CAPTCHA if present - parse the question and solve it dynamically
    captcha_field = form.find("input", attrs={"name": "capt"})
    if captcha_field:
        debug_print("[DEBUG] CAPTCHA field detected: name='capt'")
        
        # Find the CAPTCHA question text in the form
        # It's typically in a label or text near the captcha input field
        captcha_question = None
        
        # Look for the captcha field's parent container
        captcha_container = captcha_field.find_parent("div")
        if captcha_container:
            # Get all text from the container
            captcha_text = captcha_container.get_text(strip=True)
            debug_print(f"[DEBUG] CAPTCHA container text: '{captcha_text}'")
            captcha_question = captcha_text
        
        # If not found in parent div, search the entire form for CAPTCHA-related text
        if not captcha_question:
            form_text = form.get_text(separator=" ", strip=True)
            # Look for patterns like "What is X + Y = ?" or "X + Y = ?"
            captcha_match = re.search(r'(What is.+?\?|\d+\s*[+\-*/]\s*\d+\s*=\s*\?)', form_text)
            if captcha_match:
                captcha_question = captcha_match.group(1)
                debug_print(f"[DEBUG] Found CAPTCHA question in form: '{captcha_question}'")
        
        # Solve the CAPTCHA
        if captcha_question:
            captcha_answer = solve_captcha(captcha_question)
            if captcha_answer:
                payload["capt"] = captcha_answer
                print(f"  ✓ CAPTCHA solved: '{captcha_answer}'")
            else:
                print(f"[WARNING] Could not solve CAPTCHA, using default answer '{DEFAULT_CAPTCHA_ANSWER}'")
                payload["capt"] = DEFAULT_CAPTCHA_ANSWER
        else:
            print(f"[WARNING] Could not find CAPTCHA question text, using default answer '{DEFAULT_CAPTCHA_ANSWER}'")
            payload["capt"] = DEFAULT_CAPTCHA_ANSWER

    # Determine form action URL
    action = form.get("action")
    if action:
        if not action.startswith("http"):
            action = requests.compat.urljoin(url, action)
    else:
        action = url
    
    debug_print(f"[DEBUG] Form action URL: {action}")
    debug_print(f"[DEBUG] Total fields in payload: {len(payload)}")

    print(f"  → Submitting login form...")
    try:
        response = session.post(action, data=payload)
        debug_print(f"[DEBUG] POST request successful. Status: {response.status_code}")
        debug_print(f"[DEBUG] Response URL (after redirects): {response.url}")
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"\n[ERROR] Login failed. HTTP Status: {e.response.status_code}")
        debug_print(f"[DEBUG] Response URL: {e.response.url}")
        debug_print(f"[DEBUG] Response body (first 1000 chars):")
        debug_print(e.response.text[:1000])
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\n[ERROR] Network error during login: {e}")
        sys.exit(1)

    # Check for common signs of failed authentication
    result_soup = BeautifulSoup(response.text, "html.parser")
    page_title = result_soup.title.string if result_soup.title and result_soup.title.string else "N/A"
    debug_print(f"[DEBUG] Response page title: {page_title}")
    
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
        print("  ✓ Login successful!")

    return response


def scrape(session, url):
    """Scrape content from a page after login."""
    try:
        response = session.get(url)
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to scrape page. HTTP Status: {e.response.status_code}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"[ERROR] Network error while scraping: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")
    return soup


def main():
    if not LOGIN_USERNAME or not PASSWORD or not API_URL:
        print(
            "[ERROR] LOGIN_USERNAME, PASSWORD, and API_URL must be set in the .env file.\n"
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
    
    debug_print(f"[DEBUG] Session headers configured: {dict(session.headers)}\n")

    # Try to load saved cookies
    cookies_loaded = load_cookies(session)
    dashboard_url = None
    
    # If cookies were loaded, check if they're still valid
    if cookies_loaded:
        print("→ Checking if saved cookies are still valid...")
        # Try to access a protected page (we'll use the API_URL and check for redirect)
        try:
            test_response = session.get(API_URL)
            # If we get a successful response and aren't redirected to login
            if test_response.status_code == 200 and "login" not in test_response.url.lower():
                print("  ✓ Saved cookies are valid! Skipping login.\n")
                dashboard_url = test_response.url
            else:
                print("  ✗ Saved cookies expired or invalid. Logging in again...\n")
                cookies_loaded = False
        except Exception as e:
            print(f"  ✗ Error checking cookies: {e}. Logging in again...\n")
            cookies_loaded = False
    
    # If cookies weren't valid or didn't exist, perform login
    if not cookies_loaded or not dashboard_url:
        login_response = login(session, API_URL, LOGIN_USERNAME, PASSWORD)
        dashboard_url = login_response.url
        
        # Save cookies for next time
        save_cookies(session)

    # Scrape the dashboard
    print(f"\n→ Fetching dashboard content from: {dashboard_url}")
    soup = scrape(session, dashboard_url)
    page_title = soup.title.string if soup.title and soup.title.string else "N/A"
    print(f"\n{'='*60}")
    print(f"Page title: {page_title}")
    print(f"{'='*60}\n")
    
    # Print the page content
    content = soup.get_text(separator="\n", strip=True)
    print(content)


if __name__ == "__main__":
    main()
