import argparse
import json
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
    """Save session cookies to a file with secure permissions."""
    try:
        # Save cookies with restrictive file permissions (owner read/write only)
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(session.cookies, f)
        # Set secure file permissions (0o600 = owner read/write only)
        os.chmod(COOKIE_FILE, 0o600)
        print(f"✓ Cookies saved to {COOKIE_FILE}")
    except Exception as e:
        print(f"[WARNING] Failed to save cookies: {e}")


def load_cookies(session):
    """Load cookies from file into the session."""
    try:
        if os.path.exists(COOKIE_FILE):
            # Check file permissions for security
            stat_info = os.stat(COOKIE_FILE)
            # Warn if file permissions are too permissive
            if stat_info.st_mode & 0o077:
                print(f"[WARNING] Cookie file has insecure permissions. Consider running: chmod 600 {COOKIE_FILE}")
            
            with open(COOKIE_FILE, 'rb') as f:
                cookies = pickle.load(f)
            session.cookies.update(cookies)
            print(f"✓ Cookies loaded from {COOKIE_FILE}")
            return True
    except Exception as e:
        print(f"[WARNING] Failed to load cookies: {e}")
    return False


def are_cookies_valid(session, test_url):
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


def get_sms_ranges(session, base_url, max_results=25, page=1):
    """
    Retrieve SMS ranges from the API endpoint.
    
    Args:
        session: Authenticated requests session
        base_url: Base URL of the application (e.g., http://217.182.195.194/ints)
        max_results: Maximum number of results per page (default: 25)
        page: Page number to retrieve (default: 1)
    
    Returns:
        JSON response data or None if request fails
    """
    # Construct the SMS ranges API endpoint
    api_endpoint = f"{base_url}/agent/res/aj_smsranges.php"
    params = {
        'max': max_results,
        'page': page
    }
    
    # Set headers for AJAX request
    headers = {
        'Accept': 'application/json, text/javascript, */*;q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f"{base_url}/agent/MySMSNumbers"
    }
    
    print(f"→ Fetching SMS ranges (page {page}, max {max_results})...")
    debug_print(f"[DEBUG] API endpoint: {api_endpoint}")
    debug_print(f"[DEBUG] Parameters: {params}")
    
    try:
        response = session.get(api_endpoint, params=params, headers=headers)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        debug_print(f"[DEBUG] Response status: {response.status_code}")
        debug_print(f"[DEBUG] Response data type: {type(data)}")
        
        return data
        
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to fetch SMS ranges. HTTP Status: {e.response.status_code}")
        debug_print(f"[DEBUG] Response text: {e.response.text[:500]}")
        return None
    except requests.RequestException as e:
        print(f"[ERROR] Network error while fetching SMS ranges: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON response: {e}")
        debug_print(f"[DEBUG] Response text: {response.text[:500]}")
        return None


def display_sms_ranges(data):
    """
    Display SMS ranges data in a formatted way.
    
    Args:
        data: JSON data containing SMS ranges information
    """
    if not data:
        print("[WARNING] No data to display")
        return
    
    print("\n" + "="*60)
    print("SMS RANGES")
    print("="*60)
    
    # Handle different possible JSON structures
    if isinstance(data, dict):
        # If data is paginated, look for common pagination keys
        if 'data' in data:
            ranges = data['data']
            print(f"\nTotal records: {data.get('total', 'N/A')}")
            print(f"Current page: {data.get('page', 'N/A')}")
            print(f"Per page: {data.get('per_page', 'N/A')}")
        elif 'ranges' in data:
            ranges = data['ranges']
        elif 'aaData' in data:  # DataTables format
            ranges = data['aaData']
        else:
            ranges = [data]
    elif isinstance(data, list):
        ranges = data
    else:
        print(f"Data: {json.dumps(data, indent=2)}")
        return
    
    if not ranges:
        print("\nNo SMS ranges found.")
        return
    
    print(f"\nFound {len(ranges)} SMS range(s):\n")
    
    # Display each range
    for i, item in enumerate(ranges, 1):
        print(f"{i}. ", end="")
        if isinstance(item, dict):
            # Display key-value pairs
            for key, value in item.items():
                print(f"{key}: {value}", end="  ")
            print()
        elif isinstance(item, list):
            # Display list items
            print(" | ".join(str(x) for x in item))
        else:
            print(item)
    
    print("="*60)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='ARGSMS - Login and interact with SMS management system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrapper.py                    # Show dashboard (default)
  python scrapper.py --action dashboard # Show dashboard
  python scrapper.py --action sms-ranges # Get SMS ranges
  python scrapper.py --action sms-ranges --max 50 --page 2 # Get page 2 with 50 results
        """
    )
    parser.add_argument(
        '--action',
        choices=['dashboard', 'sms-ranges'],
        default='dashboard',
        help='Action to perform (default: dashboard)'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=25,
        help='Maximum results per page for sms-ranges (default: 25)'
    )
    parser.add_argument(
        '--page',
        type=int,
        default=1,
        help='Page number for sms-ranges (default: 1)'
    )
    
    args = parser.parse_args()
    
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

    # Extract base URL from API_URL (remove /login part)
    base_url = API_URL.rsplit('/', 1)[0] if '/login' in API_URL else API_URL.rsplit('/', 2)[0]
    
    # Perform the requested action
    if args.action == 'sms-ranges':
        # Get SMS ranges
        data = get_sms_ranges(session, base_url, max_results=args.max, page=args.page)
        if data:
            display_sms_ranges(data)
        else:
            print("[ERROR] Failed to retrieve SMS ranges")
            sys.exit(1)
    else:
        # Default action: scrape the dashboard
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
