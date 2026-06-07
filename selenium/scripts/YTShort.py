#!/usr/bin/env python3
"""
YouTube Shorts Automation - Short Feeds (Config-only)
With PO token support using shared driver
"""

import sys
import json
import os
import random
import shutil
import time
import logging
import re
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
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

from common.utils import (
    get_random_resolution, handle_cookies, wait_for_page_load, get_variable_watch_time
)
from common.human_behavior import ensure_video_playback
from common.shortinteract import delayed_mute

# Import shared PO token modules
from common.po_token import get_po_token, inject_visitor_cookie, set_logger as set_po_logger
from common.po_driver import create_driver_with_po_token, set_logger as set_driver_logger

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTShort_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTShort")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# Share logger with PO modules
set_po_logger(logger)
set_driver_logger(logger)


@dataclass
class SessionConfig:
    instance_id: int
    url: str
    constructed_url: str
    video_id: str
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int = 1
    min_watch_time: int = 15
    max_watch_time: int = 30
    suggested_min: int = 3
    suggested_max: int = 8
    po_token: str = None
    visitor_id: str = None


def get_current_video_id(driver) -> str:
    """Extract video ID from current URL."""
    current_url = driver.current_url
    patterns = [
        r'shorts/([a-zA-Z0-9_-]{11})',
        r'watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, current_url)
        if match:
            return match.group(1)
    return ""


def natural_swipe_up(driver, instance_id, attempt):
    """Perform natural swipe up using mouse drag."""
    try:
        viewport = driver.execute_script("""
            return {
                width: window.innerWidth,
                height: window.innerHeight
            };
        """)
        
        swipe_percentage = [0.7, 0.85, 1.0][attempt - 1]
        swipe_distance = int(viewport['height'] * swipe_percentage)
        
        start_x = int(viewport['width'] / 2)
        start_y = int(viewport['height'] / 2)
        
        action = ActionChains(driver)
        action.move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), start_x, start_y)
        action.click_and_hold()
        action.move_by_offset(0, -swipe_distance)
        action.release()
        action.perform()
        
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Natural swipe UP failed - {e}")
        return False


def natural_swipe_down(driver, instance_id, attempt):
    """Perform natural swipe down using mouse drag."""
    try:
        viewport = driver.execute_script("""
            return {
                width: window.innerWidth,
                height: window.innerHeight
            };
        """)
        
        swipe_percentage = [0.7, 0.85, 1.0][attempt - 1]
        swipe_distance = int(viewport['height'] * swipe_percentage)
        
        start_x = int(viewport['width'] / 2)
        start_y = int(viewport['height'] / 2)
        
        action = ActionChains(driver)
        action.move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), start_x, start_y)
        action.click_and_hold()
        action.move_by_offset(0, swipe_distance)
        action.release()
        action.perform()
        
        time.sleep(1)
        return True
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Natural swipe DOWN failed - {e}")
        return False


def keyboard_arrow_down(driver, instance_id):
    """Fallback: Press DOWN arrow key."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_DOWN)
        logger.info(f"Instance {instance_id}: Keyboard DOWN arrow (fallback)")
        time.sleep(0.8)
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Keyboard DOWN failed - {e}")
        return False


def keyboard_arrow_up(driver, instance_id):
    """Fallback: Press UP arrow key."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_UP)
        logger.info(f"Instance {instance_id}: Keyboard UP arrow (fallback)")
        time.sleep(0.8)
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Keyboard UP failed - {e}")
        return False


def swipe_up_with_fallback(driver, instance_id, po_token=None):
    """Try natural swipe, then fallback to keyboard."""
    old_url = driver.current_url
    
    for attempt in range(1, 4):
        if natural_swipe_up(driver, instance_id, attempt):
            time.sleep(1.5)
            new_url = driver.current_url
            if new_url != old_url:
                new_video_id = get_current_video_id(driver)
                logger.info(f"Instance {instance_id}: Swiped to new Short: {new_video_id}")
                return True
        time.sleep(0.5)
    
    if keyboard_arrow_down(driver, instance_id):
        time.sleep(1)
        new_url = driver.current_url
        if new_url != old_url:
            logger.info(f"Instance {instance_id}: Keyboard fallback succeeded")
            return True
    
    return False


def swipe_down_with_fallback(driver, instance_id, target_video_id):
    """Try natural swipe down, then fallback to keyboard."""
    old_url = driver.current_url
    
    for attempt in range(1, 4):
        if natural_swipe_down(driver, instance_id, attempt):
            time.sleep(1.5)
            new_video_id = get_current_video_id(driver)
            if new_video_id == target_video_id:
                logger.info(f"Instance {instance_id}: Swiped back to original Short")
                return True
        time.sleep(0.5)
    
    if keyboard_arrow_up(driver, instance_id):
        time.sleep(1)
        new_video_id = get_current_video_id(driver)
        if new_video_id == target_video_id:
            logger.info(f"Instance {instance_id}: Keyboard fallback returned to original")
            return True
    
    return False


def explore_shorts(driver, instance_id, explore_count, po_token):
    """Explore multiple shorts by swiping up."""
    explored = 0
    for i in range(explore_count):
        logger.info(f"Instance {instance_id}: Exploring Short {i + 1}/{explore_count}")
        if swipe_up_with_fallback(driver, instance_id, po_token):
            explored += 1
        else:
            logger.warning(f"Instance {instance_id}: Failed to explore Short {i + 1}")
            break
        time.sleep(random.uniform(0.3, 0.6))
    return explored


def return_to_original(driver, instance_id, original_video_id, explore_count):
    """Swipe down to return to original Short."""
    for i in range(explore_count):
        if swipe_down_with_fallback(driver, instance_id, original_video_id):
            return True
        time.sleep(0.5)
    
    logger.warning(f"Instance {instance_id}: Could not swipe back, navigating directly")
    driver.get(f"https://www.youtube.com/shorts/{original_video_id}")
    time.sleep(2)
    return True


def start_video_with_unmute(driver, instance_id, is_mobile=False):
    """Start video and ensure it's unmuted."""
    try:
        ensure_video_playback(driver, instance_id)
        
        if is_mobile:
            try:
                video = driver.find_element(By.TAG_NAME, "video")
                video.click()
                time.sleep(0.3)
            except:
                pass
        
        is_muted = driver.execute_script("""
            var v = document.querySelector('video');
            return v ? v.muted : false;
        """)
        
        if is_muted:
            driver.execute_script("document.querySelector('video').muted = false;")
            time.sleep(0.3)
        
        initial_volume = random.uniform(0.3, 0.8)
        driver.execute_script(f"""
            var v = document.querySelector('video');
            if (v) v.volume = {initial_volume};
        """)
        logger.info(f"Instance {instance_id}: Volume set to {int(initial_volume*100)}%")
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        # Use shared driver creator
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_shorts_cache")
        
        # Build URL with PO token injected directly
        watch_url = cfg.constructed_url
        if cfg.po_token:
            separator = '&' if '?' in watch_url else '?'
            watch_url = f"{watch_url}{separator}pot={cfg.po_token}"
            logger.info(f"Instance {cfg.instance_id}: Added PO token to initial Shorts URL")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            logger.info(f"Instance {cfg.instance_id}: Loading Shorts URL: {watch_url}")
            driver.get(watch_url)
            wait_for_page_load(driver, 15)
            handle_cookies(driver, cfg.instance_id)
            
            original_video_id = get_current_video_id(driver)
            logger.info(f"Instance {cfg.instance_id}: Original video ID: {original_video_id}")
            
            start_video_with_unmute(driver, cfg.instance_id, cfg.is_mobile)
            delayed_mute(driver, delay_range=(0, 4), volume_range=(0.3, 0.8))
            
            original_watch = random.randint(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching original Short for {original_watch}s")
            time.sleep(original_watch)
            
            explore_count = random.randint(2, 4)
            logger.info(f"Instance {cfg.instance_id}: Will explore {explore_count} Shorts")
            
            explored = explore_shorts(driver, cfg.instance_id, explore_count, cfg.po_token)
            logger.info(f"Instance {cfg.instance_id}: Explored {explored} Shorts")
            
            for i in range(explored):
                explore_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                logger.info(f"Instance {cfg.instance_id}: Watching explored Short {i+1} for {explore_watch}s")
                ensure_video_playback(driver, cfg.instance_id)
                time.sleep(explore_watch)
            
            return_to_original(driver, cfg.instance_id, original_video_id, explored)
            
            return_watch = random.randint(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching original Short again for {return_watch}s")
            ensure_video_playback(driver, cfg.instance_id)
            time.sleep(return_watch)
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 12)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s before next cycle")
                time.sleep(pause_duration)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycle(s)")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
    finally:
        if driver:
            driver.quit()
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTShort.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTShort with {len(instances)} instance(s)")
    processes = []
    
    for d in instances:
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        if video_id:
            po_token, visitor_id = get_po_token(video_id, d["instance_id"])
        
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d.get("url", ""),
            constructed_url=d.get("constructed_url", ""),
            video_id=video_id,
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", ""),
            is_mobile=d.get("is_mobile", False),
            cycles=d.get("cycles", 1),
            min_watch_time=d.get("min_watch_time", 15),
            max_watch_time=d.get("max_watch_time", 30),
            suggested_min=d.get("suggested_min", 3),
            suggested_max=d.get("suggested_max", 8),
            po_token=po_token,
            visitor_id=visitor_id
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        time.sleep(random.uniform(1, 2))
    
    for p in processes:
        p.join()
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()