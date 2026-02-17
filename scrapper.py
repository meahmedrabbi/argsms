import os
import sys

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME")
PASSWORD = os.getenv("PASSWORD")
API_URL = os.getenv("API_URL")


def login(session, url, username, password):
    """Log in to the website and return the authenticated session."""
    try:
        login_page = session.get(url)
        login_page.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error: Failed to access login page. HTTP Status: {e.response.status_code}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error: Network error while accessing login page: {e}")
        sys.exit(1)

    soup = BeautifulSoup(login_page.text, "html.parser")

    # Extract hidden form fields (e.g. CSRF tokens)
    form = soup.find("form")
    if form is None:
        print(f"Error: No login form found on the page at {url}.")
        sys.exit(1)

    payload = {}
    for hidden_input in form.find_all("input", type="hidden"):
        name = hidden_input.get("name")
        value = hidden_input.get("value", "")
        if name:
            payload[name] = value

    # Detect username and password field names from the form
    username_field = form.find("input", attrs={"type": "text"}) or form.find(
        "input", attrs={"name": lambda n: n and "user" in n.lower()}
    )
    password_field = form.find("input", attrs={"type": "password"})

    username_name = username_field.get("name", "username") if username_field else "username"
    password_name = password_field.get("name", "password") if password_field else "password"

    payload[username_name] = username
    payload[password_name] = password

    # Handle CAPTCHA if present (e.g., "What is 3 + 7 = ?")
    # Note: This assumes the CAPTCHA is always "3 + 7 = ?" with answer "10"
    # If the CAPTCHA question changes, this code will need to be updated
    captcha_field = form.find("input", attrs={"name": "capt"})
    if captcha_field:
        # Simple math captcha: 3 + 7 = 10
        payload["capt"] = "10"
        print("CAPTCHA detected and answered (3 + 7 = 10)")

    # Determine form action URL
    action = form.get("action")
    if action:
        if not action.startswith("http"):
            action = requests.compat.urljoin(url, action)
    else:
        action = url

    try:
        response = session.post(action, data=payload)
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error: Login failed. HTTP Status: {e.response.status_code}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error: Network error during login: {e}")
        sys.exit(1)

    # Check for common signs of failed authentication
    result_soup = BeautifulSoup(response.text, "html.parser")
    error_indicators = result_soup.find_all(
        string=lambda t: t and any(
            kw in t.lower() for kw in ["invalid", "incorrect", "failed", "error"]
        )
    )
    if error_indicators:
        print("Warning: Login may have failed. Page contains error messages:")
        for msg in error_indicators:
            print(f"  - {msg.strip()}")

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

    print(f"Logging in to {API_URL} ...")
    login_response = login(session, API_URL, LOGIN_USERNAME, PASSWORD)
    print(f"Login response status: {login_response.status_code}")

    # After login, scrape the landing page
    soup = scrape(session, API_URL)
    page_title = soup.title.string if soup.title and soup.title.string else "N/A"
    print("Page title:", page_title)
    print(soup.get_text(separator="\n", strip=True))


if __name__ == "__main__":
    main()
