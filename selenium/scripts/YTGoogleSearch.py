#!/usr/bin/env python3
"""
YouTube Automation - GOOGLE SEARCH ENTRY MODE
Simulates coming from Google Search (highest trust traffic source)
Searches Google for the video title, then clicks the YouTube result
"""

import sys
import json
import os
import random
import shutil
import time
import logging
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

from common.utils import (
    get_random_resolution, handle_cookies, get_variable_watch_time, wait_for_page_load,
    human_delay, is_login_page
)
from common.human_behavior import (
    watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
    ensure_video_playback
)

# Import shared PO token modules
from common.po_token import get_po_token, inject_visitor_cookie, set_logger as set_po_logger
from common.po_driver import create_driver_with_po_token, set_logger as set_driver_logger

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTGoogleSearch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTGoogleSearch")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# Share logger with PO modules
set_po_logger(logger)
set_driver_logger(logger)


def sanitize_text(text):
    """Remove emoji and non-BMP characters for ChromeDriver compatibility"""
    if not text:
        return ""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    # Remove non-BMP characters (emojis, etc.) - keep only BMP characters
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


@dataclass
class SessionConfig:
    instance_id: int
    url: str
    video_id: str
    video_title: str
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int = 1
    po_token: str = None
    visitor_id: str = None


def fetch_video_title_from_url(video_url):
    """Fetch video title using yt-dlp and sanitize it"""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get('title', '')
            return sanitize_text(title)
    except Exception as e:
        logger.debug(f"Could not fetch title: {e}")
        return ""


def simulate_google_search_entry(driver, instance_id, video_title, video_id, po_token):
    """
    Simulate coming from Google Search.
    Searches Google for the video title, then clicks the YouTube result.
    """
    try:
        # Sanitize the search query (remove emojis, non-BMP chars)
        search_query = sanitize_text(video_title) if video_title else video_id
        if not search_query:
            search_query = "youtube video"
        
        # If search query is too short or just video ID, add "youtube" to help
        if len(search_query) < 5 and search_query == video_id:
            search_query = f"{video_id} youtube"
        
        logger.info(f"Instance {instance_id}: Simulating Google Search entry")
        logger.info(f"Instance {instance_id}: Searching Google for: {search_query}")
        
        # Go to Google
        driver.get("https://www.google.com")
        wait_for_page_load(driver, 10)
        
        # Accept cookies if present
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(., 'Accept') or contains(., 'I agree')]")
            accept_btn.click()
            time.sleep(1)
        except:
            pass
        
        # Find search box
        search_box = driver.find_element(By.NAME, "q")
        human_delay(0.5, 1)
        
        # Type the search query naturally (each character is safe now)
        for char in search_query[:60]:
            try:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            except:
                # If a character fails, skip it
                continue
        
        time.sleep(random.uniform(0.5, 1))
        search_box.send_keys(Keys.RETURN)
        
        # Wait for results
        time.sleep(3)
        
        # Scroll through results naturally
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)
        
        # Find and click the YouTube result for our specific video
        clicked = False
        
        # First try to find by video ID in the URL
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='youtube.com/watch']")
            for elem in elements:
                href = elem.get_attribute('href')
                if href and video_id in href:
                    driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                    time.sleep(0.5)
                    
                    # Inject PO token into the link before clicking
                    if po_token and 'pot=' not in href:
                        separator = '&' if '?' in href else '?'
                        new_href = f"{href}{separator}pot={po_token}"
                        driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", elem)
                        logger.info(f"Instance {instance_id}: Injected PO token into Google result")
                    
                    driver.execute_script("arguments[0].click();", elem)
                    clicked = True
                    logger.info(f"Instance {instance_id}: Clicked YouTube result from Google Search (by video ID)")
                    break
        except Exception as e:
            logger.debug(f"Search by video ID failed: {e}")
        
        # If not found, try to find any YouTube result related to the search
        if not clicked:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='youtube.com']")
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and ('/watch?v=' in href or 'youtu.be/' in href):
                        driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        time.sleep(0.5)
                        
                        # Inject PO token
                        if po_token and 'pot=' not in href:
                            separator = '&' if '?' in href else '?'
                            new_href = f"{href}{separator}pot={po_token}"
                            driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", elem)
                        
                        driver.execute_script("arguments[0].click();", elem)
                        clicked = True
                        logger.info(f"Instance {instance_id}: Clicked YouTube result from Google Search (first result)")
                        break
            except Exception as e:
                logger.debug(f"Search general failed: {e}")
        
        if not clicked:
            logger.warning(f"Instance {instance_id}: Could not find YouTube result, navigating directly")
            driver.get(f"https://www.youtube.com/watch?v={video_id}")
            if po_token:
                # Use execute_script to add token without reload issues
                current_url = driver.current_url
                if 'pot=' not in current_url:
                    driver.execute_script(f"window.location.href = window.location.href + '&pot={po_token}';")
            return True
        
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Google Search simulation failed - {e}")
        # Fallback: direct navigation
        try:
            driver.get(f"https://www.youtube.com/watch?v={video_id}")
            if po_token and 'pot=' not in driver.current_url:
                driver.execute_script(f"window.location.href = window.location.href + '&pot={po_token}';")
        except:
            pass
        return True


def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        # Use shared driver creator
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_google_cache")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            # Simulate Google Search entry
            simulate_google_search_entry(driver, cfg.instance_id, cfg.video_title, cfg.video_id, cfg.po_token)
            
            wait_for_page_load(driver, 20)
            if is_login_page(driver):
                logger.warning(f"Instance {cfg.instance_id}: Login page, aborting")
                return

            handle_cookies(driver, cfg.instance_id)
            ensure_video_playback(driver, cfg.instance_id)
            start_video_with_audio_mute(driver, cfg.instance_id, cfg.is_mobile, is_suggested=False)

            main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
            watch_with_human_behavior(driver, main_watch, cfg.is_mobile)

            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                if click_suggested_video(driver, cfg.is_mobile):
                    time.sleep(2)
                    wait_for_page_load(driver, 20)
                    handle_cookies(driver, cfg.instance_id)
                    ensure_video_playback(driver, cfg.instance_id)
                    start_video_with_audio_mute(driver, cfg.instance_id, cfg.is_mobile, is_suggested=True)
                    suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                    logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                    watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
                else:
                    logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s before next cycle")
                time.sleep(pause_duration)
                
                # Clear cookies and return to Google for next cycle
                driver.delete_all_cookies()
                driver.get("https://www.google.com")
                time.sleep(2)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycle(s)")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTGoogleSearch.py <config.json>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"Starting YTGoogleSearch with {len(instances)} instance(s)")
    processes = []
    
    for d in instances:
        try:
            video_id = d.get("video_id", "")
            po_token = None
            visitor_id = None
            if video_id:
                po_token, visitor_id = get_po_token(video_id, d.get("instance_id", 0))
            
            # Get video title from config or fetch it, then sanitize
            video_title = d.get("video_title", "")
            if not video_title and video_id:
                video_title = fetch_video_title_from_url(d.get("url", ""))
                if not video_title:
                    video_title = video_id
            
            # Sanitize title for logging
            safe_title = sanitize_text(video_title)[:50]
            logger.info(f"Instance {d.get('instance_id', 0)}: Video title: {safe_title}...")
            
            cfg = SessionConfig(
                instance_id=d.get("instance_id", 0),
                url=d.get("url", ""),
                video_id=video_id,
                video_title=video_title,  # Will be sanitized before use
                min_watch_time=d.get("min_watch_time", 15),
                max_watch_time=d.get("max_watch_time", 30),
                suggested_min=d.get("suggested_min", 15),
                suggested_max=d.get("suggested_max", 35),
                suggested_chance=d.get("suggested_chance", 0.4),
                headless=d.get("headless", False),
                user_agent=d.get("user_agent", ""),
                is_mobile=d.get("is_mobile", False),
                cycles=d.get("cycles", 1),
                po_token=po_token,
                visitor_id=visitor_id
            )
            
            p = Process(target=run_session, args=(cfg,))
            processes.append(p)
            p.start()
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.error(f"Error creating config for instance: {e}")
    
    for p in processes:
        p.join()
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()