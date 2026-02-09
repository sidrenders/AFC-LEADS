#!/usr/bin/env python3
"""
Aftercells Lead Migration - Stage 1: Auto-Filter

Reads your Google Sheet export (CSV or XLSX), checks each YouTube channel
via the YouTube Data API, and automatically filters out leads that don't
pass the gate checks.

WHAT IT CHECKS (auto gate):
  - Is the channel still active? (posted in last 5 months)
  - Is the content long form? (average video duration >= 10 min)
  - Is the channel English?
  - Does the channel still exist?

WHAT IT OUTPUTS:
  - passed_leads.csv    → Leads that passed all auto-checks (import to Airtable)
  - rejected_leads.csv  → Leads that failed + reason why
  - summary.txt         → Quick stats

SETUP:
  1. Get a YouTube Data API key (free):
     - Go to https://console.cloud.google.com/
     - Create a project (or use existing)
     - Enable "YouTube Data API v3"
     - Go to Credentials → Create Credentials → API Key
     - Copy the key

  2. Add to your .env file:
     YOUTUBE_API_KEY=your_key_here

  3. Export your Google Sheet:
     - Option A: File → Download → CSV (.csv)
     - Option B: File → Download → Excel (.xlsx) — preserves green highlighting

  4. Run:
     python stage1_autofilter.py your_export.csv
     OR
     python stage1_autofilter.py your_export.xlsx

USAGE:
    python stage1_autofilter.py <path_to_csv_or_xlsx> [--dry-run] [--limit N] [--responses <response_sheet.xlsx>]

    --dry-run   Show what would happen without calling YouTube API
    --limit N   Only process the first N rows (for testing)
"""

import os
import sys
import csv
import json
import time
import re
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# Gate thresholds
ACTIVE_MONTHS = 5           # Must have posted within this many months
MIN_AVG_DURATION_MINS = 10  # Average video must be >= this many minutes
MIN_VIDEOS_TO_CHECK = 5     # Check this many recent videos for duration


# =============================================================================
# YouTube URL Parsing
# =============================================================================

def parse_youtube_url(url):
    """
    Extract channel identifier from various YouTube URL formats.
    Returns (id_type, value) where id_type is one of:
      'channel_id'  → UC... format, can query API directly
      'handle'      → @name format
      'custom_url'  → /c/name format
      'username'    → /user/name format
      'video_id'    → need to look up channel from video
      'unknown'     → couldn't parse
    """
    if not url or not isinstance(url, str):
        return ("unknown", None)

    url = url.strip()

    # Handle @handle format: youtube.com/@ColdFusion or youtube.com/@ColdFusion/videos
    match = re.search(r'youtube\.com/@([^/?&\s]+)', url)
    if match:
        return ("handle", match.group(1))

    # Handle /channel/UCxxxxxx format
    match = re.search(r'youtube\.com/channel/(UC[^/?&\s]+)', url)
    if match:
        return ("channel_id", match.group(1))

    # Handle /c/CustomName format
    match = re.search(r'youtube\.com/c/([^/?&\s]+)', url)
    if match:
        return ("custom_url", match.group(1))

    # Handle /user/Username format
    match = re.search(r'youtube\.com/user/([^/?&\s]+)', url)
    if match:
        return ("username", match.group(1))

    # Handle video URLs: youtube.com/watch?v=xxx or youtu.be/xxx
    match = re.search(r'(?:youtube\.com/watch\?.*v=|youtu\.be/)([^&\s]+)', url)
    if match:
        return ("video_id", match.group(1))

    return ("unknown", None)


# =============================================================================
# YouTube API Calls
# =============================================================================

def api_get(endpoint, params):
    """Make a YouTube API request with error handling."""
    params["key"] = YOUTUBE_API_KEY
    resp = requests.get(f"{YOUTUBE_API_URL}/{endpoint}", params=params)

    if resp.status_code == 403:
        data = resp.json()
        error_reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
        if error_reason == "quotaExceeded":
            print("\n  ERROR: YouTube API daily quota exceeded (10,000 units/day).")
            print("  Try again tomorrow or use a different API key.")
            sys.exit(1)
        print(f"  API Error 403: {resp.text[:200]}")
        return None

    if resp.status_code != 200:
        print(f"  API Error {resp.status_code}: {resp.text[:200]}")
        return None

    return resp.json()


def get_channel_id_from_handle(handle):
    """Resolve a @handle to a channel ID."""
    data = api_get("channels", {
        "part": "id",
        "forHandle": handle,
    })
    if data and data.get("items"):
        return data["items"][0]["id"]
    # Sometimes forHandle doesn't work, try search as fallback
    data = api_get("search", {
        "part": "snippet",
        "q": handle,
        "type": "channel",
        "maxResults": 1,
    })
    if data and data.get("items"):
        return data["items"][0]["snippet"]["channelId"]
    return None


def get_channel_id_from_username(username):
    """Resolve a username to a channel ID."""
    data = api_get("channels", {
        "part": "id",
        "forUsername": username,
    })
    if data and data.get("items"):
        return data["items"][0]["id"]
    return None


def get_channel_id_from_video(video_id):
    """Get channel ID from a video ID."""
    data = api_get("videos", {
        "part": "snippet",
        "id": video_id,
    })
    if data and data.get("items"):
        return data["items"][0]["snippet"]["channelId"]
    return None


def get_channel_id_from_custom_url(custom_name):
    """Resolve a custom URL name to channel ID via search."""
    data = api_get("search", {
        "part": "snippet",
        "q": custom_name,
        "type": "channel",
        "maxResults": 1,
    })
    if data and data.get("items"):
        return data["items"][0]["snippet"]["channelId"]
    return None


def resolve_channel_id(url):
    """Take any YouTube URL and return a channel ID."""
    id_type, value = parse_youtube_url(url)

    if id_type == "channel_id":
        return value
    elif id_type == "handle":
        return get_channel_id_from_handle(value)
    elif id_type == "username":
        return get_channel_id_from_username(value)
    elif id_type == "custom_url":
        return get_channel_id_from_custom_url(value)
    elif id_type == "video_id":
        return get_channel_id_from_video(value)
    else:
        return None


def get_channel_details(channel_ids):
    """
    Batch fetch channel details. Up to 50 IDs at a time.
    Returns dict of channel_id → channel data.
    """
    results = {}

    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        data = api_get("channels", {
            "part": "snippet,contentDetails,statistics,brandingSettings",
            "id": ",".join(batch),
        })
        if data:
            for item in data.get("items", []):
                results[item["id"]] = item

        if i + 50 < len(channel_ids):
            time.sleep(0.1)  # Be nice to the API

    return results


def get_recent_video_ids(uploads_playlist_id, max_results=5):
    """Get recent video IDs from a channel's uploads playlist."""
    data = api_get("playlistItems", {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": max_results,
    })
    if not data:
        return []

    return [
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
    ]


def get_video_details(video_ids):
    """Batch fetch video details (duration, publish date). Up to 50 at a time."""
    results = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        data = api_get("videos", {
            "part": "contentDetails,snippet",
            "id": ",".join(batch),
        })
        if data:
            results.extend(data.get("items", []))

        if i + 50 < len(video_ids):
            time.sleep(0.1)

    return results


def parse_duration(iso_duration):
    """Parse ISO 8601 duration (PT1H2M3S) to total minutes."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 60 + minutes + seconds / 60


# =============================================================================
# Gate Checks
# =============================================================================

def check_gates(channel_data, video_details):
    """
    Run auto gate checks on a channel.
    Returns (passed: bool, results: dict with details).
    """
    results = {
        "gate_active": False,
        "gate_long_form": False,
        "gate_english": False,
        "channel_exists": True,
        "rejection_reasons": [],
        "last_upload_date": None,
        "avg_duration_mins": None,
        "language": None,
        "country": None,
        "video_count": None,
        "description": None,
    }

    if not channel_data:
        results["channel_exists"] = False
        results["rejection_reasons"].append("Channel not found or deleted")
        return False, results

    snippet = channel_data.get("snippet", {})
    stats = channel_data.get("statistics", {})
    results["description"] = snippet.get("description", "")
    results["video_count"] = int(stats.get("videoCount", 0))

    # --- GATE: English ---
    country = snippet.get("country", "")
    default_language = snippet.get("defaultLanguage", "")
    results["country"] = country
    results["language"] = default_language

    # English-speaking countries or English language setting
    english_countries = {
        "US", "GB", "CA", "AU", "NZ", "IE", "ZA", "SG", "IN",
        "PH", "KE", "NG", "GH", "PK",  # Large English-speaking populations
    }
    is_english = (
        default_language.lower().startswith("en")
        or country in english_countries
        or not country  # If no country set, don't auto-reject (check manually)
    )
    results["gate_english"] = is_english
    if not is_english:
        results["rejection_reasons"].append(
            f"Not English (country={country}, lang={default_language})"
        )

    # --- GATE: Active ---
    if video_details:
        dates = []
        for vid in video_details:
            pub_date = vid.get("snippet", {}).get("publishedAt", "")
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    dates.append(dt)
                except ValueError:
                    pass

        if dates:
            most_recent = max(dates)
            results["last_upload_date"] = most_recent.strftime("%Y-%m-%d")
            cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVE_MONTHS * 30)
            results["gate_active"] = most_recent >= cutoff
            if not results["gate_active"]:
                results["rejection_reasons"].append(
                    f"Inactive (last upload: {results['last_upload_date']})"
                )
        else:
            results["rejection_reasons"].append("Could not determine last upload date")
    else:
        results["rejection_reasons"].append("No videos found")

    # --- GATE: Long Form ---
    if video_details:
        durations = []
        for vid in video_details:
            dur_str = vid.get("contentDetails", {}).get("duration", "")
            dur_mins = parse_duration(dur_str)
            if dur_mins > 0:
                durations.append(dur_mins)

        if durations:
            avg_dur = sum(durations) / len(durations)
            results["avg_duration_mins"] = round(avg_dur, 1)
            results["gate_long_form"] = avg_dur >= MIN_AVG_DURATION_MINS
            if not results["gate_long_form"]:
                results["rejection_reasons"].append(
                    f"Short form content (avg {results['avg_duration_mins']} min)"
                )
    else:
        results["rejection_reasons"].append("No video data for duration check")

    passed = (
        results["channel_exists"]
        and results["gate_active"]
        and results["gate_long_form"]
        and results["gate_english"]
    )

    return passed, results


# =============================================================================
# CSV / XLSX Reading
# =============================================================================

def read_csv_file(filepath):
    """Read a CSV export from Google Sheets."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(normalize_row(row))
    return rows


def _is_green_color(cell):
    """
    Check if a cell has a green-ish fill color.
    Handles direct RGB, theme colors, and indexed colors from Google Sheets exports.
    """
    fill = cell.fill
    if not fill or fill.patternType is None or fill.patternType == "none":
        return False

    # Check both fgColor and bgColor (Google Sheets exports sometimes use bgColor)
    for color_attr in (fill.fgColor, fill.bgColor):
        if not color_attr:
            continue

        rgb = None

        # Direct RGB value (most common)
        if color_attr.rgb and str(color_attr.rgb) not in ("00000000", "0", "None"):
            rgb = str(color_attr.rgb)

        # Theme color with tint — resolve to approximate RGB
        elif color_attr.theme is not None:
            # Theme index 0-9 maps to standard theme colors
            # We can't resolve exactly without the theme, but we can skip
            # known non-green themes (0=white, 1=black, etc.)
            # Instead, skip theme-based detection and rely on response sheet
            continue

        # Indexed color (legacy Excel)
        elif color_attr.indexed is not None and color_attr.indexed not in (64, 65):
            # Can't easily resolve indexed colors; skip
            continue

        if not rgb:
            continue

        rgb = rgb.lower()

        # Known green hex values from Google Sheets / Excel
        known_greens = [
            "00ff00", "92d050", "00b050", "a9d08e", "c6efce",
            "b6d7a8", "6aa84f", "38761d", "274e13", "93c47d",
            "d9ead3", "e2efda",
        ]
        # Strip alpha prefix if present (e.g., "FF92D050" → "92d050")
        hex_rgb = rgb[-6:] if len(rgb) >= 6 else rgb

        if any(g == hex_rgb for g in known_greens):
            return True

        # Flexible check: parse RGB and see if green channel dominates
        if len(hex_rgb) == 6:
            try:
                r = int(hex_rgb[0:2], 16)
                g = int(hex_rgb[2:4], 16)
                b = int(hex_rgb[4:6], 16)
                # Green-dominant: green channel significantly higher than red and blue
                # and not too dark (g > 80) and not white/gray (some color saturation)
                if g > 80 and g > r * 1.3 and g > b * 1.3 and (g - min(r, b)) > 40:
                    return True
            except ValueError:
                pass

    return False


def read_response_sheet(filepath):
    """
    Read the Response Analysis 3D sheet.
    Columns: Channel Name, Niche, Status, Channel keywords, Video style
    Green rows = worked with, Red rows = didn't work out.

    Returns a dict: normalized_channel_name → {
        'replied': True,
        'worked_with': bool (green),
        'didnt_work_out': bool (red),
        'niche': str,
        'status_notes': str,
        'channel_keywords': str,
        'video_style': str,
    }
    """
    try:
        import openpyxl
    except ImportError:
        print("  To read .xlsx files, install openpyxl:")
        print("  pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    headers = [cell.value for cell in ws[1]]

    lookup = {}
    for row in ws.iter_rows(min_row=2, values_only=False):
        values = {headers[i]: (cell.value or "") for i, cell in enumerate(row) if i < len(headers)}

        # Get channel name
        channel_name = ""
        niche = ""
        status_notes = ""
        channel_keywords = ""
        video_style = ""

        for key, value in values.items():
            if not key:
                continue
            k = str(key).strip().lower()
            v = str(value).strip() if value else ""
            if "channel" in k and "name" in k:
                channel_name = v
            elif "niche" in k:
                niche = v
            elif "status" in k:
                status_notes = v
            elif "keyword" in k:
                channel_keywords = v
            elif "video" in k and "style" in k:
                video_style = v

        if not channel_name:
            continue

        # Check row color: green = worked with, red = didn't work out
        is_green = any(_is_green_color(cell) for cell in row)
        is_red = any(_is_red_color(cell) for cell in row)

        name_key = channel_name.strip().lower()
        lookup[name_key] = {
            "replied": True,
            "worked_with": is_green,
            "didnt_work_out": is_red,
            "niche": niche,
            "status_notes": status_notes,
            "channel_keywords": channel_keywords,
            "video_style": video_style,
        }

    return lookup


def _is_red_color(cell):
    """Check if a cell has a red-ish fill color."""
    fill = cell.fill
    if not fill or fill.patternType is None or fill.patternType == "none":
        return False

    for color_attr in (fill.fgColor, fill.bgColor):
        if not color_attr:
            continue

        rgb = None
        if color_attr.rgb and str(color_attr.rgb) not in ("00000000", "0", "None"):
            rgb = str(color_attr.rgb)

        if not rgb:
            continue

        rgb = rgb.lower()
        hex_rgb = rgb[-6:] if len(rgb) >= 6 else rgb

        # Known red hex values
        known_reds = ["ff0000", "ff4444", "cc0000", "e06666", "ea9999",
                      "f4cccc", "ff6d01", "e74c3c", "c0392b"]
        if any(r == hex_rgb for r in known_reds):
            return True

        if len(hex_rgb) == 6:
            try:
                r = int(hex_rgb[0:2], 16)
                g = int(hex_rgb[2:4], 16)
                b = int(hex_rgb[4:6], 16)
                if r > 80 and r > g * 1.3 and r > b * 1.3 and (r - min(g, b)) > 40:
                    return True
            except ValueError:
                pass

    return False


def read_xlsx_file(filepath):
    """Read an XLSX file, preserving green highlight info."""
    try:
        import openpyxl
    except ImportError:
        print("  To read .xlsx files, install openpyxl:")
        print("  pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    # Get headers from first row
    headers = [cell.value for cell in ws[1]]

    rows = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
        values = {headers[i]: (cell.value or "") for i, cell in enumerate(row) if i < len(headers)}

        # Check for green fill (highlighted rows = replied leads)
        is_green = any(_is_green_color(cell) for cell in row)

        normalized = normalize_row(values)
        normalized["replied"] = is_green
        rows.append(normalized)

    return rows


def normalize_row(row):
    """Normalize column names from Google Sheet to consistent keys."""
    # Map various possible column names to standard keys
    normalized = {
        "channel_name": "",
        "subscribers": "",
        "about": "",
        "youtube_url": "",
        "email": "",
        "status": "",
        "remark": "",
        "replied": False,
    }

    for key, value in row.items():
        if not key:
            continue
        k = str(key).strip().lower()
        v = str(value).strip() if value else ""

        if "channel" in k and "name" in k:
            normalized["channel_name"] = v
        elif "number" in k or "sub" in k:
            normalized["subscribers"] = v
        elif "about" in k:
            normalized["about"] = v
        elif "youtube" in k or "link" in k or "url" in k:
            normalized["youtube_url"] = v
        elif "contact" in k or "email" in k:
            normalized["email"] = v
        elif "status" in k:
            normalized["status"] = v
        elif "remark" in k or "note" in k:
            normalized["remark"] = v
        elif "replied" in k:
            normalized["replied"] = v.lower() in ("yes", "true", "1", "y")

    return normalized


def parse_subscriber_count(sub_str):
    """Parse '164K', '1M', '2.02M' to an integer."""
    if not sub_str:
        return 0
    sub_str = sub_str.strip().upper().replace(",", "")

    match = re.match(r'([\d.]+)\s*([KMB])?', sub_str)
    if not match:
        return 0

    num = float(match.group(1))
    suffix = match.group(2)

    if suffix == "K":
        return int(num * 1_000)
    elif suffix == "M":
        return int(num * 1_000_000)
    elif suffix == "B":
        return int(num * 1_000_000_000)
    else:
        return int(num)


# =============================================================================
# Main Pipeline
# =============================================================================

def process_leads(input_file, dry_run=False, limit=None, responses_file=None):
    """Main processing pipeline."""
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"  ERROR: File not found: {input_file}")
        sys.exit(1)

    # Load response sheet cross-reference if provided
    response_lookup = {}
    if responses_file:
        responses_path = Path(responses_file)
        if not responses_path.exists():
            print(f"  ERROR: Response sheet not found: {responses_file}")
            sys.exit(1)
        print(f"\n  Loading response sheet: {responses_path.name}...")
        response_lookup = read_response_sheet(responses_file)
        print(f"  Found {len(response_lookup)} channels in response sheet")
        worked = sum(1 for v in response_lookup.values() if v["worked_with"])
        didnt = sum(1 for v in response_lookup.values() if v["didnt_work_out"])
        neutral = len(response_lookup) - worked - didnt
        print(f"    Worked with (green): {worked}")
        print(f"    Didn't work out (red): {didnt}")
        print(f"    Other/neutral: {neutral}")

    # Read input
    print(f"\n  Reading {input_path.name}...")
    if input_path.suffix.lower() == ".xlsx":
        rows = read_xlsx_file(input_file)
    else:
        rows = read_csv_file(input_file)

    total = len(rows)
    print(f"  Found {total} leads")

    # Cross-reference with response sheet
    if response_lookup:
        matched = 0
        for row in rows:
            name_key = row["channel_name"].strip().lower()
            if name_key in response_lookup:
                resp = response_lookup[name_key]
                row["replied"] = True
                row["worked_with"] = resp["worked_with"]
                row["didnt_work_out"] = resp["didnt_work_out"]
                row["response_niche"] = resp["niche"]
                row["response_status"] = resp["status_notes"]
                row["response_keywords"] = resp["channel_keywords"]
                row["response_video_style"] = resp["video_style"]
                matched += 1
        print(f"  Cross-referenced: {matched} leads matched in response sheet")

    if limit:
        rows = rows[:limit]
        print(f"  (Limited to first {limit} for testing)")

    if dry_run:
        print("\n  DRY RUN - showing parsed data without API calls:\n")
        for i, row in enumerate(rows[:10]):
            id_type, value = parse_youtube_url(row["youtube_url"])
            print(f"  {i+1}. {row['channel_name']}")
            print(f"     URL: {row['youtube_url']}")
            print(f"     Parsed: {id_type} = {value}")
            print(f"     Subs: {row['subscribers']} → {parse_subscriber_count(row['subscribers'])}")
            print(f"     Email: {row['email']}")
            print(f"     Replied: {row['replied']}")
            if row.get("worked_with"):
                print(f"     Response: WORKED WITH (green)")
            elif row.get("didnt_work_out"):
                print(f"     Response: DIDN'T WORK OUT (red)")
            elif row.get("replied"):
                print(f"     Response: Replied (neutral)")
            if row.get("response_niche"):
                print(f"     Niche (from response): {row['response_niche']}")
            print()
        if len(rows) > 10:
            print(f"  ... and {len(rows) - 10} more")
        return

    if not YOUTUBE_API_KEY:
        print("\n  ERROR: YOUTUBE_API_KEY not found in .env")
        print("  See the setup instructions at the top of this file.")
        sys.exit(1)

    # Phase 1: Resolve all channel IDs
    print("\n  Phase 1: Resolving YouTube channel IDs...")
    channel_map = {}  # row_index → channel_id
    failed_resolve = []

    for i, row in enumerate(rows):
        url = row["youtube_url"]
        if not url:
            failed_resolve.append((i, row, "No YouTube URL"))
            continue

        print(f"  [{i+1}/{len(rows)}] {row['channel_name']}...", end=" ", flush=True)
        channel_id = resolve_channel_id(url)

        if channel_id:
            channel_map[i] = channel_id
            print(f"OK ({channel_id})")
        else:
            failed_resolve.append((i, row, "Could not resolve channel ID"))
            print("FAILED")

        # Rate limit: be gentle with API
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    print(f"\n  Resolved: {len(channel_map)} / {len(rows)}")
    print(f"  Failed to resolve: {len(failed_resolve)}")

    # Phase 2: Batch fetch channel details
    print("\n  Phase 2: Fetching channel details...")
    unique_channel_ids = list(set(channel_map.values()))
    channel_details = get_channel_details(unique_channel_ids)
    print(f"  Got details for {len(channel_details)} channels")

    # Phase 3: For each channel, get recent videos and check gates
    print("\n  Phase 3: Checking gates (activity, duration, language)...")
    passed_leads = []
    rejected_leads = []

    for i, row in enumerate(rows):
        if i not in channel_map:
            # Already failed in resolve phase
            continue

        channel_id = channel_map[i]
        ch_data = channel_details.get(channel_id)

        if not ch_data:
            rejected_leads.append({
                **row,
                "channel_id": channel_id,
                "rejection_reason": "Channel data not found (may be deleted)",
            })
            continue

        # Get uploads playlist → recent videos
        uploads_playlist = ch_data.get("contentDetails", {}).get(
            "relatedPlaylists", {}
        ).get("uploads")

        video_details = []
        if uploads_playlist:
            video_ids = get_recent_video_ids(uploads_playlist, MIN_VIDEOS_TO_CHECK)
            if video_ids:
                video_details = get_video_details(video_ids)

        # Run gate checks
        passed, gate_results = check_gates(ch_data, video_details)

        lead_data = {
            **row,
            "channel_id": channel_id,
            "subscribers_parsed": parse_subscriber_count(row["subscribers"]),
            **gate_results,
        }

        if passed:
            passed_leads.append(lead_data)
        else:
            lead_data["rejection_reason"] = " | ".join(gate_results["rejection_reasons"])
            rejected_leads.append(lead_data)

        # Progress
        processed = len(passed_leads) + len(rejected_leads)
        total_to_process = len(channel_map)
        print(
            f"  [{processed}/{total_to_process}] {row['channel_name']}: "
            f"{'PASS' if passed else 'REJECT'}"
            f"{' ← ' + lead_data.get('rejection_reason', '') if not passed else ''}"
        )

        # Rate limit
        if processed % 5 == 0:
            time.sleep(0.3)

    # Add failed resolves to rejected
    for i, row, reason in failed_resolve:
        rejected_leads.append({
            **row,
            "channel_id": "",
            "rejection_reason": reason,
        })

    # Phase 4: Write outputs
    print(f"\n  Phase 4: Writing results...")
    output_dir = input_path.parent

    write_passed_csv(passed_leads, output_dir / "passed_leads.csv")
    write_rejected_csv(rejected_leads, output_dir / "rejected_leads.csv")
    write_summary(passed_leads, rejected_leads, failed_resolve, total, output_dir / "stage1_summary.txt")

    # Print summary
    print("\n" + "=" * 60)
    print("  STAGE 1 AUTO-FILTER COMPLETE")
    print("=" * 60)
    print(f"\n  Total leads processed: {total}")
    print(f"  PASSED gate checks:   {len(passed_leads)} ({len(passed_leads)*100//total}%)")
    print(f"  REJECTED:             {len(rejected_leads)} ({len(rejected_leads)*100//total}%)")
    print(f"    - Could not resolve: {len(failed_resolve)}")
    print(f"    - Failed gate:       {len(rejected_leads) - len(failed_resolve)}")

    replied_passed = sum(1 for l in passed_leads if l.get("replied"))
    if replied_passed:
        print(f"\n  Replied leads that passed: {replied_passed} (PRIORITY)")

    print(f"\n  Output files:")
    print(f"    {output_dir / 'passed_leads.csv'}")
    print(f"    {output_dir / 'rejected_leads.csv'}")
    print(f"    {output_dir / 'stage1_summary.txt'}")
    print()


def write_passed_csv(leads, filepath):
    """Write passed leads to CSV (ready for Airtable import)."""
    if not leads:
        print("  No passed leads to write.")
        return

    fieldnames = [
        "channel_name", "youtube_url", "channel_id", "email",
        "subscribers", "subscribers_parsed",
        "gate_active", "gate_long_form", "gate_english",
        "last_upload_date", "avg_duration_mins",
        "language", "country", "video_count",
        "description", "about",
        "status", "remark", "replied",
        "worked_with", "didnt_work_out",
        "response_niche", "response_status",
        "response_keywords", "response_video_style",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        # Sort: replied leads first, then by subscriber count
        leads_sorted = sorted(
            leads,
            key=lambda x: (not x.get("replied", False), -(x.get("subscribers_parsed", 0) or 0)),
        )
        writer.writerows(leads_sorted)

    print(f"  Wrote {len(leads)} passed leads to {filepath}")


def write_rejected_csv(leads, filepath):
    """Write rejected leads with reasons."""
    if not leads:
        return

    fieldnames = [
        "channel_name", "youtube_url", "email",
        "subscribers", "rejection_reason",
        "last_upload_date", "avg_duration_mins",
        "status", "remark",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    print(f"  Wrote {len(leads)} rejected leads to {filepath}")


def write_summary(passed, rejected, failed_resolve, total, filepath):
    """Write a human-readable summary."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("AFTERCELLS LEAD MIGRATION - STAGE 1 SUMMARY\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"Total leads: {total}\n")
        f.write(f"Passed:      {len(passed)} ({len(passed)*100//max(total,1)}%)\n")
        f.write(f"Rejected:    {len(rejected)} ({len(rejected)*100//max(total,1)}%)\n\n")

        # Rejection breakdown
        reasons = {}
        for lead in rejected:
            for reason in lead.get("rejection_reason", "").split(" | "):
                reason = reason.strip()
                if reason:
                    reasons[reason] = reasons.get(reason, 0) + 1

        f.write("REJECTION REASONS:\n")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            f.write(f"  {count:>4}  {reason}\n")

        # Replied leads
        replied_passed = [l for l in passed if l.get("replied")]
        if replied_passed:
            f.write(f"\nREPLIED LEADS THAT PASSED ({len(replied_passed)}):\n")
            for l in replied_passed:
                tag = ""
                if l.get("worked_with"):
                    tag = " [WORKED WITH]"
                elif l.get("didnt_work_out"):
                    tag = " [DIDN'T WORK OUT]"
                f.write(f"  - {l['channel_name']} ({l['subscribers']}){tag}\n")

    print(f"  Wrote summary to {filepath}")


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Aftercells Stage 1: Auto-filter leads via YouTube API"
    )
    parser.add_argument("input_file", help="Path to CSV or XLSX export from Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="Parse file without calling YouTube API")
    parser.add_argument("--limit", type=int, help="Only process first N rows")
    parser.add_argument("--responses", help="Path to Response Analysis XLSX for cross-referencing replied leads")

    args = parser.parse_args()

    print("=" * 60)
    print("  AFTERCELLS LEAD MIGRATION - STAGE 1: AUTO-FILTER")
    print("=" * 60)

    process_leads(args.input_file, dry_run=args.dry_run, limit=args.limit, responses_file=args.responses)
