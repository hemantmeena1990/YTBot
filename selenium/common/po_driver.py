#!/usr/bin/env python3
"""
Extended driver creation with PO token support and custom referer
"""

import os
import time
import tempfile
import uuid
import shutil
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from common.utils import get_random_resolution
from common.po_token import inject_visitor_cookie

# Global logger
_script_logger = None

def set_logger(logger):
    """Set the logger for this module"""
    global _script_logger
    _script_logger = logger


def set_custom_referer(driver, referer_url):
    """Set custom referer using CDP (Chrome DevTools Protocol)"""
    if not referer_url:
        return
    try:
        driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
            'headers': {
                'Referer': referer_url
            }
        })
        if _script_logger:
            _script_logger.debug(f"Set custom referer: {referer_url}")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"Could not set referer: {e}")


def create_driver_with_po_token(cfg, profile_prefix):
    """
    Create Chrome driver with PO token cookie injection and custom referer.
    
    Args:
        cfg: SessionConfig object with attributes:
            - instance_id, headless, user_agent, is_mobile, visitor_id
            - referer (optional): custom referer URL
        profile_prefix: string like "yt_direct_cache_"
    
    Returns:
        (driver, profile_dir) tuple
    """
    opts = Options()
    
    if cfg.headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--lang=en-US")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument(f"user-agent={cfg.user_agent}")
    
    if not cfg.headless:
        w, h = get_random_resolution(cfg.is_mobile)
        opts.add_argument(f"--window-size={w},{h}")
    else:
        opts.add_argument("--window-size=1920,1080")
    
    # Additional Chrome options to prevent conflicts
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-component-extensions-with-background-pages")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-sync")
    opts.add_argument("--disable-translate")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    
    # Use a random remote debugging port to avoid conflicts
    random_port = random.randint(40000, 49999)
    opts.add_argument(f"--remote-debugging-port={random_port}")
    
    # Use system temp directory for profiles
    temp_base = os.path.join(tempfile.gettempdir(), "yt_automation")
    os.makedirs(temp_base, exist_ok=True)
    
    # Clean up old profiles (older than 1 hour)
    try:
        current_time = time.time()
        for item in os.listdir(temp_base):
            item_path = os.path.join(temp_base, item)
            if os.path.isdir(item_path) and item.startswith(profile_prefix[:10]):
                if current_time - os.path.getmtime(item_path) > 3600:
                    shutil.rmtree(item_path, ignore_errors=True)
                    if _script_logger:
                        _script_logger.debug(f"Cleaned old profile: {item_path}")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"Profile cleanup skipped: {e}")
    
    # Create new unique profile directory
    unique_id = f"{int(time.time())}_{cfg.instance_id}_{uuid.uuid4().hex[:12]}"
    profile_dir = os.path.join(temp_base, f"{profile_prefix}_{unique_id}")
    
    # Ensure directory is clean
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except:
            pass
    
    # Create fresh directory
    os.makedirs(profile_dir, exist_ok=True)
    
    # Add a marker file
    marker_file = os.path.join(profile_dir, f"instance_{cfg.instance_id}.lock")
    with open(marker_file, 'w') as f:
        f.write(f"Created at: {time.time()}\nInstance: {cfg.instance_id}")
    
    opts.add_argument(f"--user-data-dir={profile_dir}")
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: Created isolated profile at {profile_dir}")
    
    service = Service(ChromeDriverManager().install())
    service.creation_flags = 0x08000000  # CREATE_NO_WINDOW on Windows
    
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    
    # Set custom referer if configured
    if hasattr(cfg, 'referer') and cfg.referer:
        set_custom_referer(driver, cfg.referer)
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: Applied custom referer: {cfg.referer}")
    
    # Inject visitor cookie if available
    if hasattr(cfg, 'visitor_id') and cfg.visitor_id:
        inject_visitor_cookie(driver, cfg.instance_id, cfg.visitor_id)
    
    return driver, profile_dir