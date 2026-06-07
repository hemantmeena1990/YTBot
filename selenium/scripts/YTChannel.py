#!/usr/bin/env python3
"""
YouTube Automation - CHANNEL VIEW MODE (Config-only)
With PO token support using shared driver
"""

import sys
import json
import os
import random
import shutil
import time
import logging
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
from common.search import DesktopSearch, MobileSearch
from common.find import find_and_click_channel_result, channel_internal_search

# Import shared PO token modules
from common.po_token import get_po_token, inject_visitor_cookie, set_logger as set_po_logger
from common.po_driver import create_driver_with_po_token, set_logger as set_driver_logger

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTChannel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTChannel")
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
    channel_name: str
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


def click_video_with_po_token_in_channel(driver, instance_id, video_id, po_token, is_mobile):
    """
    Find video in channel, inject PO token into its href, then click naturally.
    """
    if not po_token:
        return False
    
    try:
        # Wait for videos to load
        time.sleep(2)
        
        # Find video links in channel page
        video_selectors = [
            f"a[href*='/watch?v={video_id}']",
            "a#video-title",
            "a[href*='/watch?v=']"
        ]
        
        video_link = None
        for selector in video_selectors:
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
            logger.warning(f"Instance {instance_id}: Could not find video link for {video_id}")
            return False
        
        # Get original href
        original_href = video_link.get_attribute('href')
        
        # Inject PO token into the href attribute
        if 'pot=' not in original_href:
            separator = '&' if '?' in original_href else '?'
            new_href = f"{original_href}{separator}pot={po_token}"
            
            # Use JavaScript to modify the href attribute
            driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
            logger.info(f"Instance {instance_id}: Injected PO token into video link href")
        
        # Click the link naturally
        driver.execute_script("arguments[0].scrollIntoView(true);", video_link)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", video_link)
        logger.info(f"Instance {instance_id}: Clicked video with pre-injected PO token")
        
        return True
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error - {e}")
        return False


def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        # Use shared driver creator
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_channel_cache")
        
        search_query = cfg.channel_name
        logger.info(f"Instance {cfg.instance_id}: Searching for channel: {search_query}")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            # Search for channel on YouTube homepage
            if cfg.is_mobile:
                if not MobileSearch.perform_search(driver, cfg.instance_id, search_query):
                    logger.error(f"Instance {cfg.instance_id}: Mobile search failed")
                    return
            else:
                if not DesktopSearch.perform_search(driver, cfg.instance_id, search_query):
                    logger.error(f"Instance {cfg.instance_id}: Desktop search failed")
                    return
            
            # Click channel result
            if not find_and_click_channel_result(driver, cfg.instance_id, search_query, cfg.is_mobile):
                logger.error(f"Instance {cfg.instance_id}: Could not find/click channel result")
                return
            
            time.sleep(2)
            wait_for_page_load(driver, 15)
            
            # Inside channel, search for video
            if not channel_internal_search(driver, cfg.instance_id, cfg.video_id, cfg.is_mobile):
                logger.error(f"Instance {cfg.instance_id}: Could not search within channel")
                return
            
            # Click video result with PO token injection
            if not click_video_with_po_token_in_channel(driver, cfg.instance_id, cfg.video_id, cfg.po_token, cfg.is_mobile):
                logger.error(f"Instance {cfg.instance_id}: Could not click video result")
                return
            
            # Continue with normal video playback
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
                
                # Clear cookies and return to home page for next cycle
                driver.delete_all_cookies()
                driver.get("https://www.youtube.com")
                time.sleep(2)
        
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
        logger.error("Usage: python YTChannel.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r', encoding='utf-8-sig') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTChannel with {len(instances)} instance(s)")
    processes = []
    
    for d in instances:
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        if video_id:
            po_token, visitor_id = get_po_token(video_id, d["instance_id"])
        
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d["url"],
            constructed_url=d["constructed_url"],
            video_id=video_id,
            channel_name=d.get("channel_name", ""),
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d["suggested_min"],
            suggested_max=d["suggested_max"],
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"],
            cycles=d.get("cycles", 1),
            po_token=po_token,
            visitor_id=visitor_id
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()