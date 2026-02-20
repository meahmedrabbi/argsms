"""Wrapper functions for the scrapper to be used by the Telegram bot."""

import os
import logging
import requests
from scrapper import login, get_sms_ranges, get_sms_numbers, load_cookies, save_cookies, are_cookies_valid
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME")
PASSWORD = os.getenv("PASSWORD")
API_URL = os.getenv("API_URL")


class ScrapperSession:
    """Manages a scrapper session for the bot."""
    
    def __init__(self):
        self.session = requests.Session()
        # Add browser-like headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self._authenticated = False
        self.base_url = None
        
    def ensure_authenticated(self):
        """Ensure the session is authenticated."""
        if self._authenticated:
            return True
            
        # Try to load saved cookies
        cookies_loaded = load_cookies(self.session)
        
        if cookies_loaded:
            # Check if cookies are still valid
            try:
                test_response = self.session.get(API_URL)
                if test_response.status_code == 200 and "login" not in test_response.url.lower():
                    self._authenticated = True
                    self._extract_base_url()
                    return True
            except requests.RequestException as e:
                logger.warning(f"Cookie validation failed: {e}")
        
        # If cookies not valid, perform login
        try:
            login_response = login(self.session, API_URL, LOGIN_USERNAME, PASSWORD)
            save_cookies(self.session)
            self._authenticated = True
            self._extract_base_url()
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def _extract_base_url(self):
        """Extract base URL from API_URL."""
        from urllib.parse import urlparse
        parsed_url = urlparse(API_URL)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}"
    
    def get_sms_ranges(self, max_results=25, page=1):
        """Get SMS ranges from the API."""
        if not self.ensure_authenticated():
            return None
        
        try:
            data = get_sms_ranges(self.session, self.base_url, max_results=max_results, page=page)
            return data
        except Exception as e:
            logger.error(f"Error getting SMS ranges: {e}")
            # Reset authentication flag to force re-login on next attempt
            self._authenticated = False
            return None
    
    def get_sms_numbers(self, range_id, start=0, length=25):
        """Get SMS numbers for a specific range from the API."""
        if not self.ensure_authenticated():
            return None
        
        try:
            data = get_sms_numbers(self.session, self.base_url, range_id, start=start, length=length)
            return data
        except Exception as e:
            logger.error(f"Error getting SMS numbers: {e}")
            # Reset authentication flag to force re-login on next attempt
            self._authenticated = False
            return None


# Global scrapper session instance
_scrapper_session = None


def get_scrapper_session():
    """Get or create the global scrapper session."""
    global _scrapper_session
    if _scrapper_session is None:
        _scrapper_session = ScrapperSession()
    return _scrapper_session
