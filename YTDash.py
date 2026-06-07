#!/usr/bin/env python3
"""
YouTube Automation Dashboard – Enhanced Two-Column Layout
Features:
- Left column: all input fields + video title/ID/duration
- Right column: Save/Load buttons, channel avatar, thumbnail + video type badge
- Video statistics (views, likes, comments, upload date) below thumbnail
- Subscriber count below channel info
- Selenium/Playwright selector
- Uses yt-dlp for accurate video info
- Auto/Random view type mode
- Sequential cycles with proper process tracking
- Traffic source simulation (Google Search, WhatsApp Web, etc.)
"""

import os
import sys
import json
import webbrowser
import threading
import time
import shutil
import random
import glob
import tempfile
import subprocess
from pathlib import Path
from collections import defaultdict
from flask import Flask, render_template_string, request, jsonify

# Check yt-dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    print("\n" + "="*60)
    print("ERROR: yt-dlp is not installed!")
    print("Please run: pip install yt-dlp")
    print("="*60 + "\n")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from common.input import (
    load_config, save_config, detect_url_type,
    get_applicable_view_types, build_script_config,
    extract_video_id, get_video_title
)

app = Flask(__name__)

# Ensure data directory exists
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

CACHE_PATTERNS = ["yt_direct_cache_*", "yt_search_cache_*", "yt_channel_cache_*", "yt_shorts_cache_*", "yt_ss_cache_*"]

# Auto-cleanup on startup
def auto_cleanup_on_startup():
    try:
        cleaned = 0
        if LOG_DIR.exists():
            for log_file in LOG_DIR.glob("*.log"):
                try:
                    if time.time() - log_file.stat().st_mtime > 86400:
                        log_file.unlink()
                        cleaned += 1
                except:
                    pass
        for config_file in DATA_DIR.glob("launch_config_*.json"):
            try:
                if time.time() - config_file.stat().st_mtime > 86400:
                    config_file.unlink()
                    cleaned += 1
            except:
                pass
        if cleaned > 0:
            print(f"[Auto-Cleanup] Removed {cleaned} old files")
    except Exception as e:
        print(f"[Auto-Cleanup] Error: {e}")

auto_cleanup_on_startup()

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Automation Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #1e1e2f; padding: 20px; color: #eee; }
        .dashboard-container { display: flex; gap: 20px; max-width: 1600px; margin: 0 auto; }
        .main-content { flex: 1; min-width: 0; }
        .sidebar { width: 35%; min-width: 300px; }
        .card { background: #2d2d3a; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        h1 { font-size: 1.6rem; margin: 0; }
        h2 { font-size: 1.2rem; margin-bottom: 15px; color: #a1a1aa; }
        label { display: block; margin: 10px 0 5px; font-weight: bold; font-size: 0.85rem; }
        input, select, textarea { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #555; background: #3a3a4a; color: #fff; }
        button { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #6366f1; }
        .btn-danger { background: #dc2626; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-success { background: #10b981; }
        .btn-success:hover { background: #059669; }
        .btn-secondary { background: #6b7280; }
        .btn-secondary:hover { background: #4b5563; }
        .row { display: flex; gap: 15px; flex-wrap: wrap; }
        .row .form-group { flex: 1; min-width: 120px; }
        .console { background: #0f0f17; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 0.75rem; height: calc(100vh - 200px); overflow-y: auto; }
        .log { border-left: 3px solid #4f46e5; padding: 4px 8px; margin: 4px 0; word-break: break-word; }
        .log-error { border-left-color: #dc2626; color: #fca5a5; }
        .log-success { border-left-color: #10b981; }
        .log-warning { border-left-color: #f59e0b; }
        .preview-card { background: #1e1e2f; border: 1px solid #4f46e5; border-radius: 8px; padding: 12px; margin-top: 15px; }
        .info-text { font-family: monospace; font-size: 0.75rem; color: #a1a1aa; word-break: break-all; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: bold; }
        .badge-short { background: #dc2626; color: white; }
        .badge-video { background: #10b981; color: white; }
        .flex-between { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
        hr { border-color: #3a3a4a; margin: 15px 0; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #4f46e5; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; margin-left: 10px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { color: #a1a1aa; font-size: 0.75rem; margin-left: 10px; }
        .right-column { flex: 0 0 auto; width: 220px; }
        #channelAvatar, #thumbnailContainer { width: 100%; box-sizing: border-box; }
        .right-buttons { display: flex; gap: 10px; justify-content: flex-end; margin-bottom: 20px; }
        .right-buttons button { flex: 1; min-width: 80px; text-align: center; }
        .video-stats { background: #1e1e2f; border-radius: 8px; padding: 10px; margin-top: 10px; font-size: 0.7rem; }
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .stat-label { color: #a1a1aa; }
        .stat-value { color: #4f46e5; font-weight: bold; }
        .subscriber-count { font-size: 0.7rem; color: #10b981; margin-top: 4px; }
        .traffic-disabled-msg { color: #f59e0b; font-size: 0.7rem; margin-left: 8px; }
    </style>
</head>
<body>
<div class="dashboard-container">
    <div class="main-content">
        <div class="flex-between" style="margin-bottom: 20px;">
            <h1>🎬 YouTube Automation Dashboard</h1>
            <div class="button-group">
                <select id="automation_version" style="width: auto; background: #3a3a4a; padding: 8px 12px;">
                    <option value="selenium">🐍 Selenium (Stable)</option>
                    <option value="playwright">🎭 Playwright (Experimental)</option>
                </select>
                <button class="btn-secondary" onclick="clearConsole()">🗑️ Clear Console</button>
                <button class="btn-danger" onclick="cleanupAll()">🧹 Cleanup All</button>
            </div>
        </div>
        <div class="card">
            <div class="card-header"><h2>📝 Configuration</h2></div>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 300px;">
                    <div class="form-group"><label>📢 Channel Name/Handle</label><input type="text" id="channel_name" placeholder="rajasthanidesidiaries or @handle"></div>
                    <div class="form-group"><label>🔗 YouTube URL</label><input type="text" id="urlInput" placeholder="https://youtube.com/watch?v=... or https://youtube.com/shorts/..."></div>
                    <hr>
                    <div id="videoInfoDisplay" style="background: #1e1e2f; border-radius: 8px; padding: 12px; margin-bottom: 15px; display: none;">
                        <h3 id="videoTitle" style="margin-bottom: 8px; color: #4f46e5; font-size: 0.95rem;">-</h3>
                        <p><strong>🆔 Video ID:</strong> <span id="videoId">-</span></p>
                        <p><strong>⏱️ Duration:</strong> <span id="videoDuration">-</span> seconds</p>
                    </div>
                    <div class="row">
                        <div class="form-group"><label>📊 Instances</label><input type="number" id="num_instances" value="1" min="1" max="10"></div>
                        <div class="form-group"><label>🔄 Cycles (1-100)</label><input type="number" id="cycles" value="1" min="1" max="100"></div>
                        <div class="form-group"><label>🎭 Headless</label><select id="headless"><option value="false">No</option><option value="true">Yes</option></select></div>
                    </div>
                    <div class="row">
                        <div class="form-group"><label>⏱️ Min watch (s)</label><input type="number" id="min_watch" value="15"></div>
                        <div class="form-group"><label>⏱️ Max watch (s)</label><input type="number" id="max_watch" value="30"></div>
                        <div class="form-group"><label>⏭️ Next Suggested min</label><input type="number" id="suggested_min" value="15"></div>
                        <div class="form-group"><label>⏭️ Next Suggested max</label><input type="number" id="suggested_max" value="35"></div>
                    </div>
                    <div class="row">
                        <div class="form-group"><label>🎲 Next Suggested chance (%)</label><input type="range" id="suggested_chance" min="0" max="100" value="40"><span id="chance_val">40%</span></div>
                        <div class="form-group"><label>🔌 Use Proxy</label><select id="use_proxy"><option value="false">No</option><option value="true">Yes</option></select></div>
                        <div class="form-group"><label>🌐 Custom Proxy URL</label><input type="text" id="proxy_url" placeholder="socks5://127.0.0.1:9050"></div>
                    </div>
                </div>
                <div class="right-column">
                    <div class="right-buttons"><button onclick="saveConfig()">💾 Save</button><button onclick="loadConfig()">📂 Load</button></div>
                    <div id="channelAvatar" style="display: none; background: #1e1e2f; border-radius: 12px; padding: 12px; margin-bottom: 15px; text-align: center;">
                        <img id="channelAvatarImg" src="" alt="" style="width: 50px; height: 50px; border-radius: 50%; margin-bottom: 8px;">
                        <div><span id="channelDisplayName" style="font-weight: bold; font-size: 0.85rem; display: block;">-</span><small id="channelHandle" style="color: #a1a1aa; font-size: 0.7rem;">-</small><div id="subscriberCount" class="subscriber-count">-</div></div>
                    </div>
                    <div id="thumbnailContainer" style="display: none; background: #1e1e2f; border-radius: 12px; padding: 12px; text-align: center;">
                        <img id="videoThumbnail" src="" alt="Thumbnail" style="width: 100%; max-width: 160px; border-radius: 6px; margin-bottom: 8px;">
                        <div id="videoTypeBadgeContainer" style="margin-top: 5px;"></div>
                        <div id="videoStats" class="video-stats" style="display: none;">
                            <div class="stat-row"><span class="stat-label">👁️ Views:</span><span class="stat-value" id="viewCount">-</span></div>
                            <div class="stat-row"><span class="stat-label">👍 Likes:</span><span class="stat-value" id="likeCount">-</span></div>
                            <div class="stat-row"><span class="stat-label">💬 Comments:</span><span class="stat-value" id="commentCount">-</span></div>
                            <div class="stat-row"><span class="stat-label">📅 Uploaded:</span><span class="stat-value" id="uploadDate">-</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- View Type & Traffic Source Combined Card -->
        <div class="card">
            <div class="card-header">
                <h2>🎯 View Type & Traffic Source</h2>
                <button class="btn-success" onclick="launch()">🚀 Launch</button>
            </div>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 2; min-width: 200px;">
                    <label>📺 View Type</label>
                    <select id="view_type" style="width:100%; padding:8px;"></select>
                </div>
                <div style="flex: 1; min-width: 180px;">
                    <label>🌐 Traffic Source <span id="trafficSourceDisabledMsg" class="traffic-disabled-msg" style="display:none;">(Only for Direct URL views)</span></label>
                    <select id="traffic_source" style="width:100%; padding:8px;">
                        <option value="direct">Direct / None</option>
                        <option value="google_search">🔍 Google Search</option>
                        <option value="whatsapp_web">💬 WhatsApp Web</option>
                        <option value="instagram">📸 Instagram</option>
                        <option value="telegram_web">📱 Telegram Web</option>
                        <option value="github">🐙 GitHub.io</option>
                        <option value="bing">🔎 Bing</option>
                        <option value="twitter">🐦 Twitter/X</option>
                        <option value="reddit">🤖 Reddit</option>
                        <option value="facebook">📘 Facebook</option>
                        <option value="linkedin">💼 LinkedIn</option>
                    </select>
                </div>
            </div>
            <div id="viewTypeWarning" style="color:#f59e0b; font-size:0.85rem; display:none; margin-top:10px;"></div>
            <div id="trafficSourceInfo" style="color:#10b981; font-size:0.75rem; margin-top:8px; display:none;">
                ⚡ Custom referer will be applied for this traffic source
            </div>
        </div>
    </div>
    <div class="sidebar">
        <div class="card" style="height: 100%; display: flex; flex-direction: column;">
            <div class="card-header"><h2>📋 Activity Log</h2></div>
            <div class="console" id="console"><div class="log">Dashboard ready.</div></div>
            <div id="previewSection" class="preview-card" style="display:none;">
                <h4>🔍 Preview</h4>
                <div id="previewContent"></div>
            </div>
        </div>
    </div>
</div>
<script>
function addLog(msg, type) {
    type = type || 'info';
    var c = document.getElementById('console');
    var d = document.createElement('div');
    d.className = 'log';
    if (type === 'error') d.className += ' log-error';
    if (type === 'success') d.className += ' log-success';
    if (type === 'warning') d.className += ' log-warning';
    d.innerText = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}
function clearConsole() {
    document.getElementById('console').innerHTML = '<div class="log">Console cleared.</div>';
    addLog('Console cleared', 'info');
}
function formatNumber(num) {
    if (!num) return '-';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}
function getRefererUrl(source) {
    var refs = {
        'whatsapp_web': 'https://web.whatsapp.com/',
        'instagram': 'https://www.instagram.com/',
        'telegram_web': 'https://web.telegram.org/',
        'github': 'https://github.io/',
        'bing': 'https://www.bing.com/',
        'twitter': 'https://twitter.com/',
        'reddit': 'https://www.reddit.com/',
        'facebook': 'https://www.facebook.com/',
        'linkedin': 'https://www.linkedin.com/'
    };
    return refs[source] || 'custom';
}
function updateTrafficSourceVisibility() {
    var viewType = document.getElementById('view_type').value;
    var trafficSelect = document.getElementById('traffic_source');
    var disabledMsg = document.getElementById('trafficSourceDisabledMsg');
    var infoDiv = document.getElementById('trafficSourceInfo');
    
    // Traffic source applies to Direct URL view types (including Shorts)
    var directUrlViewTypes = ['Other YouTube features', 'Direct/Unknown', 'Suggested', 'Short Feeds'];
    
    if (directUrlViewTypes.includes(viewType)) {
        trafficSelect.disabled = false;
        if (disabledMsg) disabledMsg.style.display = 'none';
        if (trafficSelect.value !== 'direct') {
            infoDiv.style.display = 'block';
            infoDiv.innerHTML = '⚡ Custom referer will be applied: ' + getRefererUrl(trafficSelect.value);
        } else {
            infoDiv.style.display = 'none';
        }
    } else {
        trafficSelect.disabled = true;
        if (disabledMsg) disabledMsg.style.display = 'inline';
        infoDiv.style.display = 'none';
        // Reset to direct when switching away
        trafficSelect.value = 'direct';
    }
}
async function fetchChannelInfo(handle) {
    if (!handle) return;
    try {
        var res = await fetch('/api/get_channel_info', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({handle: handle})
        });
        var data = await res.json();
        if (data.success) {
            document.getElementById('channelDisplayName').innerText = data.name || handle;
            document.getElementById('channelHandle').innerText = '@' + handle.replace('@', '');
            if (data.avatar_url) document.getElementById('channelAvatarImg').src = data.avatar_url;
            if (data.subscriber_count) document.getElementById('subscriberCount').innerHTML = '👥 ' + data.subscriber_count;
            document.getElementById('channelAvatar').style.display = 'block';
        } else {
            document.getElementById('channelAvatar').style.display = 'none';
        }
    } catch (err) { console.error(err); }
}
async function fetchVideoDetails(url) {
    if (!url) return;
    document.getElementById('videoInfoDisplay').style.display = 'block';
    document.getElementById('videoTitle').innerHTML = '<span class="spinner"></span><span class="loading-text">Fetching...</span>';
    document.getElementById('videoId').innerText = '-';
    document.getElementById('videoDuration').innerText = '-';
    document.getElementById('thumbnailContainer').style.display = 'none';
    document.getElementById('videoStats').style.display = 'none';
    try {
        var res = await fetch('/api/get_video_details', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url})
        });
        var data = await res.json();
        if (data.success) {
            document.getElementById('videoTitle').innerHTML = data.title || 'Untitled';
            document.getElementById('videoId').innerText = data.video_id || '-';
            document.getElementById('videoDuration').innerText = data.duration;
            if (data.thumbnail_url) {
                document.getElementById('videoThumbnail').src = data.thumbnail_url;
                document.getElementById('thumbnailContainer').style.display = 'block';
            }
            var badgeHtml = data.is_short ? '<span class="badge badge-short">📱 SHORT</span>' : '<span class="badge badge-video">🎬 VIDEO</span>';
            document.getElementById('videoTypeBadgeContainer').innerHTML = badgeHtml;
            if (data.view_count || data.like_count || data.comment_count || data.upload_date) {
                document.getElementById('viewCount').innerHTML = formatNumber(data.view_count);
                document.getElementById('likeCount').innerHTML = formatNumber(data.like_count);
                document.getElementById('commentCount').innerHTML = formatNumber(data.comment_count);
                document.getElementById('uploadDate').innerHTML = data.upload_date || '-';
                document.getElementById('videoStats').style.display = 'block';
            }
            if (data.duration && data.duration > 0) {
                var maxWatchField = document.getElementById('max_watch');
                var currentValue = parseInt(maxWatchField.value);
                if (isNaN(currentValue) || currentValue === 30) {
                    maxWatchField.value = data.duration;
                    addLog('Auto-set max watch time to ' + data.duration + 's', 'info');
                }
            }
            await updateViewTypesByType(data.is_short);
            return data;
        } else {
            document.getElementById('videoInfoDisplay').style.display = 'none';
            addLog('Error: ' + data.error, 'error');
            return null;
        }
    } catch (err) {
        addLog('Error: ' + err.message, 'error');
        document.getElementById('videoInfoDisplay').style.display = 'none';
        return null;
    }
}
async function updateViewTypesByType(isShort) {
    try {
        var res = await fetch('/api/get_view_types_by_type', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_short: isShort})
        });
        var data = await res.json();
        var select = document.getElementById('view_type');
        select.innerHTML = '<option value="">-- Select View Type --</option>';
        var types = data.view_types || [];
        for (var i = 0; i < types.length; i++) {
            var opt = document.createElement('option');
            opt.value = types[i];
            opt.text = types[i];
            if (types[i] === 'Auto/Random') opt.style.color = '#8b5cf6';
            if (types[i] === 'Google Search') opt.style.color = '#10b981';
            select.appendChild(opt);
        }
        if (types.length === 1 && types[0] !== 'Auto/Random') {
            select.value = types[0];
            addLog('Auto-selected: ' + types[0], 'success');
            updatePreview();
        }
        updateTrafficSourceVisibility();
    } catch (err) {
        addLog('Error loading view types: ' + err.message, 'error');
    }
}
async function updatePreview() {
    var url = document.getElementById('urlInput').value.trim();
    var viewType = document.getElementById('view_type').value;
    if (!url || !viewType) {
        document.getElementById('previewSection').style.display = 'none';
        return;
    }
    try {
        var res = await fetch('/api/preview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, view_type: viewType})
        });
        var data = await res.json();
        if (data.success) {
            document.getElementById('previewSection').style.display = 'block';
            document.getElementById('previewContent').innerHTML = '<strong>Constructed URL:</strong><br><span class="info-text">' + data.constructed_url + '</span><br><br><strong>Device:</strong><br>' + (data.is_mobile ? '📱 Mobile' : '💻 Desktop');
        } else {
            document.getElementById('previewSection').style.display = 'block';
            document.getElementById('previewContent').innerHTML = '<span style="color:#f59e0b;">⚠️ ' + data.error + '</span>';
        }
    } catch (err) { console.error(err); }
}
async function saveConfig() {
    var config = {
        url: document.getElementById('urlInput').value.trim(),
        num_instances: parseInt(document.getElementById('num_instances').value),
        cycles: parseInt(document.getElementById('cycles').value),
        headless: document.getElementById('headless').value === 'true',
        min_watch_time: parseInt(document.getElementById('min_watch').value),
        max_watch_time: parseInt(document.getElementById('max_watch').value),
        suggested_min: parseInt(document.getElementById('suggested_min').value),
        suggested_max: parseInt(document.getElementById('suggested_max').value),
        suggested_chance: parseInt(document.getElementById('suggested_chance').value) / 100,
        use_proxy: document.getElementById('use_proxy').value === 'true',
        proxy_url: document.getElementById('proxy_url').value,
        channel_name: document.getElementById('channel_name').value,
        view_type: document.getElementById('view_type').value,
        traffic_source: document.getElementById('traffic_source').value
    };
    try {
        var res = await fetch('/api/save_config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(config)});
        if (res.ok) addLog('Configuration saved', 'success');
        else addLog('Save failed', 'error');
    } catch (err) { addLog('Save error: ' + err.message, 'error'); }
}
async function loadConfig() {
    try {
        var res = await fetch('/api/load_config');
        var cfg = await res.json();
        document.getElementById('channel_name').value = cfg.channel_name || '';
        if (cfg.channel_name) fetchChannelInfo(cfg.channel_name.replace('@', ''));
        if (cfg.url) {
            document.getElementById('urlInput').value = cfg.url;
            await fetchVideoDetails(cfg.url);
        }
        document.getElementById('num_instances').value = cfg.num_instances || 1;
        document.getElementById('cycles').value = cfg.cycles || 1;
        document.getElementById('headless').value = cfg.headless ? 'true' : 'false';
        document.getElementById('min_watch').value = cfg.min_watch_time || 15;
        document.getElementById('max_watch').value = cfg.max_watch_time || 30;
        document.getElementById('suggested_min').value = cfg.suggested_min || 15;
        document.getElementById('suggested_max').value = cfg.suggested_max || 35;
        var chanceSlider = document.getElementById('suggested_chance');
        chanceSlider.value = (cfg.suggested_chance || 0.4) * 100;
        document.getElementById('chance_val').innerText = chanceSlider.value + '%';
        document.getElementById('use_proxy').value = cfg.use_proxy ? 'true' : 'false';
        document.getElementById('proxy_url').value = cfg.proxy_url || '';
        if (cfg.view_type) {
            var select = document.getElementById('view_type');
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === cfg.view_type) {
                    select.value = cfg.view_type;
                    break;
                }
            }
            await updatePreview();
        }
        if (cfg.traffic_source) {
            document.getElementById('traffic_source').value = cfg.traffic_source;
        }
        updateTrafficSourceVisibility();
        addLog('Configuration loaded', 'success');
    } catch (err) { addLog('Load error: ' + err.message, 'error'); }
}
async function cleanupAll() {
    if (!confirm('Delete logs, cache folders, and old configs?')) return;
    addLog('Starting cleanup...', 'info');
    try {
        var res = await fetch('/api/cleanup', {method: 'POST'});
        var data = await res.json();
        if (data.success) {
            addLog('Cleanup complete: ' + data.deleted_files + ' files, ' + data.deleted_folders + ' folders deleted', 'success');
            if (data.freed_space_mb > 0) addLog('Freed ~' + data.freed_space_mb + ' MB', 'success');
        } else {
            addLog('Cleanup failed: ' + data.error, 'error');
        }
    } catch (err) { addLog('Cleanup error: ' + err.message, 'error'); }
}
async function launch() {
    var url = document.getElementById('urlInput').value.trim();
    if (!url) { addLog('No URL entered', 'error'); return; }
    var viewType = document.getElementById('view_type').value;
    if (!viewType) { addLog('Select a view type', 'error'); return; }
    var automationVersion = document.getElementById('automation_version').value;
    var trafficSource = document.getElementById('traffic_source').value;
    var cycles = parseInt(document.getElementById('cycles').value);
    
    if (cycles < 1) {
        addLog('Cycles must be at least 1', 'error');
        return;
    }
    
    var config = {
        urls: [url],
        num_instances: parseInt(document.getElementById('num_instances').value),
        cycles: cycles,
        headless: document.getElementById('headless').value === 'true',
        min_watch_time: parseInt(document.getElementById('min_watch').value),
        max_watch_time: parseInt(document.getElementById('max_watch').value),
        suggested_min: parseInt(document.getElementById('suggested_min').value),
        suggested_max: parseInt(document.getElementById('suggested_max').value),
        suggested_chance: parseInt(document.getElementById('suggested_chance').value) / 100,
        use_proxy: document.getElementById('use_proxy').value === 'true',
        proxy_url: document.getElementById('proxy_url').value,
        channel_name: document.getElementById('channel_name').value,
        view_type: viewType,
        automation_version: automationVersion,
        traffic_source: trafficSource
    };
    
    if (trafficSource !== 'direct') {
        var directUrlViewTypes = ['Other YouTube features', 'Direct/Unknown', 'Suggested', 'Short Feeds'];
        if (directUrlViewTypes.includes(viewType)) {
            addLog('🌐 Using traffic source: ' + trafficSource, 'info');
            if (trafficSource === 'google_search') {
                addLog('🔍 Google Search simulation: Will search Google first then click result', 'info');
            } else {
                addLog('🌍 Custom referer: ' + getRefererUrl(trafficSource), 'info');
            }
        } else {
            addLog('⚠️ Traffic source "' + trafficSource + '" only works with Direct URL view types. Using Direct/None.', 'warning');
            config.traffic_source = 'direct';
        }
    }
    
    addLog('Launching ' + config.num_instances + ' instance(s) x ' + config.cycles + ' cycle(s)', 'info');
    try {
        var res = await fetch('/api/launch', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(config)});
        var result = await res.json();
        if (result.success) addLog(result.message, 'success');
        else addLog('Launch error: ' + result.error, 'error');
    } catch (err) { addLog('Launch failed: ' + err.message, 'error'); }
}
document.getElementById('channel_name').addEventListener('blur', function() { if (this.value.trim()) fetchChannelInfo(this.value.trim().replace('@', '')); });
document.getElementById('urlInput').addEventListener('blur', function() { if (this.value.trim()) fetchVideoDetails(this.value.trim()); });
document.getElementById('view_type').addEventListener('change', function() {
    updatePreview();
    updateTrafficSourceVisibility();
});
document.getElementById('traffic_source').addEventListener('change', function() {
    var info = document.getElementById('trafficSourceInfo');
    var viewType = document.getElementById('view_type').value;
    var directUrlViewTypes = ['Other YouTube features', 'Direct/Unknown', 'Suggested', 'Short Feeds'];
    if (directUrlViewTypes.includes(viewType) && this.value !== 'direct') {
        info.style.display = 'block';
        info.innerHTML = '⚡ Custom referer will be applied: ' + getRefererUrl(this.value);
    } else {
        info.style.display = 'none';
    }
});
document.getElementById('suggested_chance').oninput = function() { document.getElementById('chance_val').innerText = this.value + '%'; };
window.onload = function() { loadConfig(); };
</script>
</body>
</html>
'''

# ==================== Helper Functions ====================

def format_number(num):
    if not num or num == 0:
        return ""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def get_video_details_ytdlp(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'po_token': ['web.gvs+http://127.0.0.1:4416'],
                }
            },
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'success': True,
                'video_id': info.get('id', ''),
                'title': info.get('title', 'Untitled'),
                'duration': info.get('duration', 0),
                'thumbnail_url': info.get('thumbnail', ''),
                'is_short': 'shorts' in url or info.get('duration', 0) <= 60,
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'upload_date': info.get('upload_date', ''),
                'channel_name': info.get('channel', ''),
                'channel_id': info.get('channel_id', ''),
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_channel_info_ytdlp(channel_handle: str) -> dict:
    result = {"name": channel_handle, "avatar_url": "", "subscriber_count": ""}
    handle = channel_handle.lstrip('@')
    channel_url = f"https://www.youtube.com/@{handle}"
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
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if info:
                result["name"] = info.get('channel', channel_handle)
                thumbnails = info.get('thumbnails', [])
                if thumbnails:
                    result["avatar_url"] = thumbnails[-1].get('url', '')
                subscriber_count = info.get('channel_follower_count', 0)
                if subscriber_count:
                    result["subscriber_count"] = format_number(subscriber_count) + " subscribers"
    except Exception as e:
        print(f"yt-dlp channel error: {e}")
    return result

def get_preview_info(url: str, view_type: str):
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    DESKTOP_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
    MOBILE_AGENTS = ["Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"]
    
    if view_type == "Auto/Random":
        return {"success": True, "constructed_url": f"Auto-selected per instance", "user_agent": "Random", "is_mobile": "Random", "video_id": video_id}
    
    if view_type == "Google Search":
        return {"success": True, "constructed_url": f"Via Google Search → {url}", "user_agent": "Random", "is_mobile": "Random", "video_id": video_id}
    
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
    
    return {"success": True, "constructed_url": constructed_url, "user_agent": ua, "is_mobile": is_mobile, "video_id": video_id}

def cleanup_all():
    deleted_files = 0
    deleted_folders = 0
    total_size = 0
    
    if LOG_DIR.exists():
        for log_file in LOG_DIR.glob("*.log"):
            try:
                total_size += log_file.stat().st_size
                log_file.unlink()
                deleted_files += 1
            except:
                pass
    
    for config_file in DATA_DIR.glob("launch_config_*.json"):
        try:
            total_size += config_file.stat().st_size
            config_file.unlink()
            deleted_files += 1
        except:
            pass
    
    for pattern in CACHE_PATTERNS:
        for folder in BASE_DIR.glob(pattern):
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
        for folder in BASE_DIR.glob(f"*/{pattern}"):
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
    
    temp_base = os.path.join(tempfile.gettempdir(), "yt_automation")
    if os.path.exists(temp_base):
        try:
            for folder in os.listdir(temp_base):
                folder_path = os.path.join(temp_base, folder)
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path)
                    deleted_folders += 1
        except:
            pass
    
    chrome_temp_patterns = [
        os.path.join(tempfile.gettempdir(), "scoped_dir*"),
        os.path.join(tempfile.gettempdir(), "chrome_*"),
        os.path.join(tempfile.gettempdir(), "Crashpad*")
    ]
    
    for pattern in chrome_temp_patterns:
        for folder in glob.glob(pattern):
            if os.path.isdir(folder):
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
    
    freed_space_mb = round(total_size / (1024 * 1024), 2)
    return {"deleted_files": deleted_files, "deleted_folders": deleted_folders, "freed_space_mb": freed_space_mb}

# ==================== Flask Routes ====================

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/get_channel_info', methods=['POST'])
def api_get_channel_info():
    handle = request.json.get('handle', '')
    info = get_channel_info_ytdlp(handle)
    return jsonify({"success": True, **info})

@app.route('/api/save_config', methods=['POST'])
def api_save_config():
    save_config(request.json)
    return jsonify({"success": True})

@app.route('/api/load_config')
def api_load_config():
    return jsonify(load_config())

@app.route('/api/get_video_details', methods=['POST'])
def api_get_video_details():
    url = request.json.get('url', '')
    result = get_video_details_ytdlp(url)
    return jsonify(result)

@app.route('/api/get_view_types_by_type', methods=['POST'])
def api_get_view_types_by_type():
    is_short = request.json.get('is_short', False)
    if is_short:
        view_types = ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        view_types = ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    return jsonify({"view_types": view_types})

@app.route('/api/detect_view_types', methods=['POST'])
def api_detect_view_types():
    urls = request.json.get('urls', [])
    if not urls:
        return jsonify({"view_types": []})
    if '/shorts/' in urls[0]:
        return jsonify({"view_types": ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]})
    else:
        return jsonify({"view_types": ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]})

@app.route('/api/validate_view_type', methods=['POST'])
def api_validate_view_type():
    url = request.json.get('url', '')
    view_type = request.json.get('view_type', '')
    
    if view_type in ("Auto/Random", "Google Search"):
        return jsonify({"valid": True})
    
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"valid": False, "error": details.get('error', 'Could not determine video type')})
    
    is_short = details.get('is_short', False)
    
    if is_short:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    
    return jsonify({"valid": view_type in valid_types})

@app.route('/api/preview', methods=['POST'])
def api_preview():
    url = request.json.get('url', '')
    view_type = request.json.get('view_type', '')
    info = get_preview_info(url, view_type)
    return jsonify(info)

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    try:
        result = cleanup_all()
        return jsonify({"success": True, "deleted_files": result["deleted_files"], "deleted_folders": result["deleted_folders"], "freed_space_mb": result.get("freed_space_mb", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/launch', methods=['POST'])
def api_launch():
    data = request.json
    view_type = data['view_type']
    automation_version = data.get('automation_version', 'selenium')
    url = data['urls'][0]
    cycles = data.get('cycles', 1)
    num_instances = data.get('num_instances', 1)
    traffic_source = data.get('traffic_source', 'direct')
    
    if cycles < 1:
        return jsonify({"success": False, "error": "Cycles must be at least 1"})
    
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"success": False, "error": f"Could not validate video: {details.get('error', 'Unknown error')}"})
    
    is_short = details.get('is_short', False)
    
    if is_short:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    
    if view_type not in ["Auto/Random", "Google Search"] and view_type not in available_types:
        return jsonify({"success": False, "error": f"View type '{view_type}' not valid for this video"})
    
    # Mapping from view type to script file
    view_to_script = {
        "Google Search": "YTGoogleSearch.py",
        "Other YouTube features": "YTDirect.py",
        "Direct/Unknown": "YTDirect.py",
        "Suggested": "YTDirect.py",
        "Search (Video)": "YTSearch.py",
        "Short Feeds": "YTShort.py",
        "Channel View": "YTChannel.py",
    }
    
    # Referer mapping for traffic sources (only for direct URL view types)
    referer_map = {
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
    
    # Direct URL view types that support traffic source
    direct_url_view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds"]
    
    launched_total = 0
    
    for cycle in range(1, cycles + 1):
        print(f"[DEBUG] Starting Cycle {cycle}/{cycles}")
        cycle_processes = []
        cycle_configs = []
        
        for i in range(num_instances):
            instance_id = (cycle - 1) * num_instances + i + 1
            url = data['urls'][i % len(data['urls'])]
            
            if view_type == "Auto/Random":
                selected_view_type = random.choice(available_types + ["Google Search"])
                is_auto_random = True
            else:
                selected_view_type = view_type
                is_auto_random = False
            
            cfg = build_script_config(instance_id, data, url, selected_view_type)
            cfg['is_auto_random'] = is_auto_random
            cfg['available_view_types'] = available_types if is_auto_random else []
            cfg['cycle_number'] = cycle
            cfg['traffic_source'] = traffic_source
            
            # Add referer only for direct URL view types and non-direct traffic sources
            if selected_view_type in direct_url_view_types and traffic_source != 'direct' and traffic_source in referer_map:
                cfg['referer'] = referer_map[traffic_source]
            
            if data.get('proxy_url'):
                cfg['proxy'] = data['proxy_url']
            
            cycle_configs.append(cfg)
        
        script_groups = defaultdict(list)
        for cfg in cycle_configs:
            script_file = view_to_script.get(cfg['view_type'], "YTDirect.py")
            script_groups[script_file].append(cfg)
        
        for script_file, group_configs in script_groups.items():
            if group_configs:
                group_temp_file = DATA_DIR / f"launch_config_cycle{cycle}_{script_file}_{int(time.time())}.json"
                with open(group_temp_file, 'w') as f:
                    json.dump(group_configs, f, indent=2)
                
                if automation_version == 'playwright':
                    script_path = BASE_DIR / "playwright" / "scripts" / script_file
                else:
                    script_path = BASE_DIR / "selenium" / "scripts" / script_file
                
                if script_path.exists():
                    cmd = [sys.executable, str(script_path), str(group_temp_file)]
                    if sys.platform == "win32":
                        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        proc = subprocess.Popen(cmd)
                    cycle_processes.append(proc)
                    launched_total += len(group_configs)
                else:
                    print(f"[WARNING] Script not found: {script_path}")
        
        for proc in cycle_processes:
            proc.wait()
        
        print(f"[DEBUG] Cycle {cycle} completed")
        
        if cycle < cycles:
            time.sleep(random.uniform(5, 10))
    
    return jsonify({"success": True, "message": f"Completed {cycles} cycle(s) with {num_instances} instance(s) each. Total {launched_total} sessions. Traffic source: {traffic_source}"})

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("Starting YouTube Automation Dashboard at http://127.0.0.1:5000")
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Log directory: {LOG_DIR}")
    print(f"Data directory: {DATA_DIR}")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)