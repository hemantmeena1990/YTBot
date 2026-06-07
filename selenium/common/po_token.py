#!/usr/bin/env python3
"""
Shared PO Token utilities for all Selenium scripts
Provides functions for fetching PO tokens, injecting visitor cookies,
and adding tokens to URLs - all with no page reloads.
"""

import requests
import socket
import time

# Global logger - will be set by each script
_script_logger = None


def set_logger(logger):
    """
    Set the logger for this module.
    Call this after creating your logger in each script.
    
    Usage:
        from common.po_token import set_logger
        set_logger(logger)
    """
    global _script_logger
    _script_logger = logger


def check_po_server(timeout=3):
    """
    Check if PO token server is running on port 4416.
    Returns True if server is reachable.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex(('127.0.0.1', 4416))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_po_token(video_id, instance_id, timeout=30):
    """
    Fetch PO token and visitor ID from local HTTP server.
    
    Args:
        video_id: YouTube video ID (11 characters)
        instance_id: Instance number for logging
        timeout: Request timeout in seconds
    
    Returns:
        (po_token, visitor_id) tuple, or (None, None) if failed
    """
    if not video_id:
        if _script_logger:
            _script_logger.debug(f"Instance {instance_id}: No video_id provided, skipping PO token")
        return None, None
    
    try:
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: Requesting PO token for video {video_id}...")
        
        response = requests.post(
            "http://127.0.0.1:4416/get_pot",
            json={"video_id": video_id},
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')
            visitor_id = data.get('visitorId')
            
            if po_token and _script_logger:
                _script_logger.info(f"Instance {instance_id}: PO token received (length: {len(po_token)})")
                if visitor_id:
                    _script_logger.debug(f"Instance {instance_id}: Visitor ID received (length: {len(visitor_id)})")
                return po_token, visitor_id
            else:
                if _script_logger:
                    _script_logger.warning(f"Instance {instance_id}: Response missing poToken. Keys: {list(data.keys())}")
                return None, None
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: Server returned HTTP {response.status_code}")
            return None, None
            
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: Cannot connect to PO token server on port 4416")
            _script_logger.info(f"Instance {instance_id}: Make sure the server is running: node build/main.js --port 4416")
        return None, None
    except requests.exceptions.Timeout:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: PO token request timed out after {timeout}s")
        return None, None
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: PO token error - {e}")
        return None, None


def add_po_token_to_url(url, po_token):
    """
    Add PO token parameter to URL if available.
    Does NOT reload the page - only modifies the URL string.
    
    Args:
        url: Original URL
        po_token: PO token string
    
    Returns:
        URL with pot parameter appended
    """
    if not po_token:
        return url
    if not url:
        return url
    
    # Check if token already present
    if 'pot=' in url:
        return url
    
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}pot={po_token}"


def inject_visitor_cookie(driver, instance_id, visitor_id):
    """
    Inject VISITOR_INFO1_LIVE cookie into the driver.
    This cookie helps YouTube identify the session as legitimate.
    
    Args:
        driver: Selenium WebDriver instance
        instance_id: Instance number for logging
        visitor_id: Visitor ID from PO token server
    
    Returns:
        True if successful, False otherwise
    """
    if not visitor_id:
        if _script_logger:
            _script_logger.debug(f"Instance {instance_id}: No visitor_id provided, skipping cookie injection")
        return False
    
    try:
        # Navigate to youtube domain first (required before setting cookies)
        driver.get("https://www.youtube.com/robots.txt")
        time.sleep(0.5)
        
        # Add the visitor cookie
        driver.add_cookie({
            'name': 'VISITOR_INFO1_LIVE',
            'value': visitor_id,
            'domain': '.youtube.com',
            'path': '/'
        })
        
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: Injected VISITOR_INFO1_LIVE cookie")
        return True
        
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: Could not inject visitor cookie - {e}")
        return False


def inject_po_token_into_link(driver, instance_id, video_id, po_token, link_selector=None):
    """
    Find a video link and inject PO token into its href attribute.
    This allows the token to be present when the link is clicked naturally.
    
    Args:
        driver: Selenium WebDriver instance
        instance_id: Instance number for logging
        video_id: Target video ID
        po_token: PO token to inject
        link_selector: Optional custom CSS selector for the link
    
    Returns:
        True if successful, False otherwise
    """
    if not po_token or not video_id:
        return False
    
    from selenium.webdriver.common.by import By
    
    try:
        # Default selectors for video links
        selectors = link_selector or [
            f"a[href*='/watch?v={video_id}']",
            f"a[href*='{video_id}']",
            "a#video-title",
            "a[href*='/watch?v=']"
        ]
        
        video_link = None
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and video_id in href:
                        video_link = elem
                        break
                if video_link:
                    break
            except:
                continue
        
        if not video_link:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: Could not find video link for {video_id}")
            return False
        
        # Get original href
        original_href = video_link.get_attribute('href')
        
        # Check if token already present
        if 'pot=' in original_href:
            if _script_logger:
                _script_logger.debug(f"Instance {instance_id}: PO token already in link")
            return True
        
        # Inject token into href
        separator = '&' if '?' in original_href else '?'
        new_href = f"{original_href}{separator}pot={po_token}"
        
        # Use JavaScript to modify the href attribute (no page reload)
        driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
        
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: Injected PO token into video link href")
        
        return True
        
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: Failed to inject token into link - {e}")
        return False


def click_with_po_token(driver, instance_id, video_id, po_token, link_selector=None):
    """
    Inject PO token into a video link and click it naturally.
    This is a convenience function that combines injection and click.
    
    Args:
        driver: Selenium WebDriver instance
        instance_id: Instance number for logging
        video_id: Target video ID
        po_token: PO token to inject
        link_selector: Optional custom CSS selector for the link
    
    Returns:
        True if successful, False otherwise
    """
    if not po_token:
        if _script_logger:
            _script_logger.debug(f"Instance {instance_id}: No PO token, using normal click")
        return False
    
    try:
        # Inject token into the link
        if not inject_po_token_into_link(driver, instance_id, video_id, po_token, link_selector):
            return False
        
        # Find the link again and click it
        from selenium.webdriver.common.by import By
        
        selectors = link_selector or [
            f"a[href*='/watch?v={video_id}']",
            f"a[href*='{video_id}']",
            "a#video-title",
            "a[href*='/watch?v=']"
        ]
        
        video_link = None
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and video_id in href:
                        video_link = elem
                        break
                if video_link:
                    break
            except:
                continue
        
        if not video_link:
            return False
        
        # Scroll to and click the link
        driver.execute_script("arguments[0].scrollIntoView(true);", video_link)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", video_link)
        
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: Clicked video with pre-injected PO token")
        
        return True
        
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: Click with PO token failed - {e}")
        return False


def get_current_url_with_token(driver, po_token):
    """
    Get current URL and add PO token if not already present.
    Returns the URL with token, does NOT navigate.
    """
    if not po_token:
        return driver.current_url
    
    current_url = driver.current_url
    if 'pot=' in current_url:
        return current_url
    
    separator = '&' if '?' in current_url else '?'
    return f"{current_url}{separator}pot={po_token}"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'set_logger',
    'check_po_server',
    'get_po_token',
    'add_po_token_to_url',
    'inject_visitor_cookie',
    'inject_po_token_into_link',
    'click_with_po_token',
    'get_current_url_with_token',
]