#!/usr/bin/env python3
"""
Shared PO Token utilities for all automation scripts (Selenium & Playwright)
Place this file in the root 'common/' folder.
"""

import requests
import logging

_script_logger = None

def set_logger(logger):
    global _script_logger
    _script_logger = logger

def get_po_token(video_id, instance_id):
    """
    Fetch PO token and visitor ID from local PO token server.
    Returns (po_token, visitor_id) tuple.
    """
    if not video_id:
        return None, None

    try:
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: Requesting PO token for video {video_id}...")

        response = requests.post(
            "http://127.0.0.1:4416/get_pot",
            json={"video_id": video_id},
            timeout=15,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')      # camelCase
            visitor_id = data.get('visitorId')
            if po_token and _script_logger:
                _script_logger.info(f"Instance {instance_id}: PO token received (length: {len(po_token)})")
                return po_token, visitor_id
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: PO token server returned {response.status_code}")

    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: Cannot connect to PO token server (port 4416). Is it running?")
    except requests.exceptions.Timeout:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: PO token request timed out")
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: PO token error - {e}")

    return None, None

def add_po_token_to_url(url, po_token):
    """Add PO token parameter to URL if available"""
    if not po_token:
        return url
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}pot={po_token}"