#!/usr/bin/env python3
"""
Shared configuration module for YouTube Automation Suite
Handles config loading/saving, URL parsing, view type mapping, and script config building.
"""

import json
import re
import random
import unicodedata
from pathlib import Path
from typing import Optional, List, Dict, Any

# Try to import yt-dlp for video title fetching
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# Path to config file
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "user_config.json"

# Default configuration
DEFAULT_CONFIG = {
    "url": "",
    "num_instances": 1,
    "cycles": 1,
    "headless": False,
    "min_watch_time": 15,
    "max_watch_time": 30,
    "suggested_min": 15,
    "suggested_max": 35,
    "suggested_chance": 0.4,
    "use_proxy": False,
    "proxy_url": "",
    "channel_name": "",
    "view_type": "",
    "traffic_source": "direct"
}

# User agent lists
DESKTOP_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6301.2 Mobile Safari/537.36",
]

# Referer mapping for traffic sources
REFERER_MAP = {
    'whatsapp_web': 'https://web.whatsapp.com/',
    'instagram': 'https://www.instagram.com/',
    'telegram_web': 'https://web.telegram.org/',
    'github': 'https://github.io/',
    'bing': 'https://www.bing.com/',
    'twitter': 'https://twitter.com/',
    'reddit': 'https://www.reddit.com/',
    'facebook': 'https://www.facebook.com/',
    'linkedin': 'https://www.linkedin.com/',
}


def sanitize_text(text):
    """
    Remove emoji and non-BMP characters for ChromeDriver compatibility.
    Keeps only characters within the Basic Multilingual Plane (BMP).
    """
    if not text:
        return ""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    # Remove non-BMP characters (emojis, etc.) - keep only BMP characters
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def load_config() -> dict:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'm\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def detect_url_type(url: str) -> str:
    """Detect if URL is for a short or regular video."""
    if '/shorts/' in url:
        return 'shorts'
    return 'video'


def get_applicable_view_types(url: str) -> List[str]:
    """Return list of view types applicable for the given URL."""
    if '/shorts/' in url:
        return ["Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        return ["Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]


def get_video_title(url: str) -> Optional[str]:
    """
    Fetch video title using yt-dlp with PO token support.
    Returns sanitized title (emojis removed) for ChromeDriver compatibility.
    """
    if not YTDLP_AVAILABLE:
        return ""
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'extractor_args': {
                'youtube': {
                    'po_token': ['web.gvs+http://127.0.0.1:4416'],
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '')
            return sanitize_text(title) if title else ""
    except Exception:
        return ""


def build_script_config(instance_id: int, data: dict, url: str, view_type: str) -> dict:
    """
    Build configuration dictionary for a script instance.
    
    Args:
        instance_id: Instance number (1-based)
        data: Dashboard configuration data
        url: Target YouTube URL
        view_type: Selected view type for this instance
    
    Returns:
        Dictionary with all configuration needed by the script
    """
    video_id = extract_video_id(url)
    traffic_source = data.get('traffic_source', 'direct')
    
    # Determine user agent and mobile status based on view type
    if view_type == "Google Search":
        # Google Search can use random device
        is_mobile = random.choice([True, False])
        user_agent = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    elif view_type in ("Other YouTube features", "Direct/Unknown"):
        is_mobile = True
        user_agent = random.choice(MOBILE_AGENTS)
    elif view_type == "Suggested":
        is_mobile = False
        user_agent = random.choice(DESKTOP_AGENTS)
    elif view_type == "Short Feeds":
        is_mobile = random.choice([True, False])
        user_agent = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    else:
        # For Search, Channel View - random device
        is_mobile = random.choice([True, False])
        user_agent = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    
    # Build constructed URL based on view type
    if view_type == "Other YouTube features":
        constructed_url = f"https://youtu.be/{video_id}"
    elif view_type == "Short Feeds":
        constructed_url = f"https://www.youtube.com/shorts/{video_id}"
    elif view_type == "Google Search":
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    config = {
        "instance_id": instance_id,
        "url": url,
        "video_id": video_id,
        "constructed_url": constructed_url,
        "view_type": view_type,
        "min_watch_time": data["min_watch_time"],
        "max_watch_time": data["max_watch_time"],
        "suggested_min": data["suggested_min"],
        "suggested_max": data["suggested_max"],
        "suggested_chance": data["suggested_chance"],
        "headless": data["headless"],
        "user_agent": user_agent,
        "is_mobile": is_mobile,
        "cycles": data.get("cycles", 1),
        "channel_name": data.get("channel_name", ""),
        "traffic_source": traffic_source,
    }
    
    # Add referer for direct URL view types and non-direct traffic sources
    direct_url_view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds"]
    if view_type in direct_url_view_types and traffic_source != 'direct' and traffic_source in REFERER_MAP:
        config['referer'] = REFERER_MAP[traffic_source]
    
    # Add video title for search mode or Google Search
    if view_type == "Search (Video)" or view_type == "Google Search":
        raw_title = get_video_title(url)
        config["video_title"] = raw_title if raw_title else ""
    
    # Add auto/random specific fields if present
    if data.get("is_auto_random"):
        config["is_auto_random"] = True
        config["available_view_types"] = data.get("available_view_types", [])
    
    # Add proxy if configured
    if data.get("proxy_url"):
        config["proxy"] = data["proxy_url"]
    
    return config


def get_preview_info(url: str, view_type: str) -> dict:
    """Generate preview info for a given URL and view type."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    DESKTOP_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
    MOBILE_AGENTS = ["Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"]
    
    if view_type == "Auto/Random":
        return {
            "success": True,
            "constructed_url": f"https://www.youtube.com/watch?v={video_id} (Auto-selected per instance)",
            "user_agent": "Random per instance",
            "is_mobile": "Random per instance",
            "video_id": video_id
        }
    
    if view_type == "Google Search":
        return {
            "success": True,
            "constructed_url": f"Via Google Search → https://www.youtube.com/watch?v={video_id}",
            "user_agent": "Random",
            "is_mobile": "Random",
            "video_id": video_id
        }
    
    if view_type in ("Other YouTube features", "Direct/Unknown"):
        is_mobile = True
        ua = random.choice(MOBILE_AGENTS)
    elif view_type == "Suggested":
        is_mobile = False
        ua = random.choice(DESKTOP_AGENTS)
    elif view_type == "Short Feeds":
        is_mobile = random.choice([True, False])
        ua = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    else:
        is_mobile = random.choice([True, False])
        ua = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    
    if view_type == "Other YouTube features":
        constructed_url = f"https://youtu.be/{video_id}"
    elif view_type == "Short Feeds":
        constructed_url = f"https://www.youtube.com/shorts/{video_id}"
    else:
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return {
        "success": True,
        "constructed_url": constructed_url,
        "user_agent": ua,
        "is_mobile": is_mobile,
        "video_id": video_id
    }


# Export public functions
__all__ = [
    'load_config',
    'save_config',
    'extract_video_id',
    'detect_url_type',
    'get_applicable_view_types',
    'build_script_config',
    'get_video_title',
    'get_preview_info',
    'sanitize_text',
    'REFERER_MAP',
    'DESKTOP_AGENTS',
    'MOBILE_AGENTS',
]