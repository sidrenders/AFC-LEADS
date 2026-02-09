#!/usr/bin/env python3
"""
Aftercells Lead Migration - Stage 2: Enrich & Import to Airtable

Reads your LEAD GEN.xlsx, enriches each channel via YouTube API + Claude AI,
and imports everything to Airtable.

WHAT IT DOES:
  Phase 1 (YouTube API):
    - Resolves channel IDs from any URL format
    - Fetches channel metadata (subs, country, language, description)
    - Fetches 3 recent video titles + descriptions
    - Runs auto gate checks (active, long form, English)
    - Normalizes URLs to youtube.com/@handle/videos format
    - Extracts emails from channel descriptions

  Phase 2 (Claude AI):
    - Classifies niche (9 categories)
    - Detects: idea-led content, storytelling/docs/explainer
    - Detects: has sponsors, has Patreon
    - Detects: uses 3D, uses motion graphics/2D, uses stock footage
    - Only runs on channels that passed gate checks

  Phase 3 (Airtable):
    - Imports ALL leads to your Channels table
    - Gate-failed leads imported with basic data (you review manually)
    - Gate-passed leads imported with full AI enrichment

RESUME SUPPORT:
  Progress is saved to progress.json after every batch.
  If YouTube API quota runs out or anything crashes, just run again -
  it picks up exactly where it left off.

USAGE:
    python stage2_enrich.py "LEAD GEN.xlsx" --responses "Response Analysis 3D.xlsx"
    python stage2_enrich.py "LEAD GEN.xlsx" --responses "Response Analysis 3D.xlsx" --limit 10
    python stage2_enrich.py "LEAD GEN.xlsx" --skip-ai    (YouTube + Airtable only, no Claude)
    python stage2_enrich.py --resume                      (continue from progress.json)
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Config
# =============================================================================

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# Gate thresholds
ACTIVE_MONTHS = 5
MIN_AVG_DURATION_MINS = 10
MIN_VIDEOS_TO_CHECK = 5
VIDEOS_FOR_AI = 3  # Number of recent videos to fetch for AI classification

PROGRESS_FILE = "progress.json"

# Valid niches (must match Airtable single-select options exactly)
VALID_NICHES = [
    "Explainer",
    "Documentary",
    "True Crime / Mystery",
    "History & Politics",
    "Science & Space",
    "Nature & Geo",
    "Tech & Innovation",
    "Finance & Business",
    "3D Animated Storytelling",
]


# =============================================================================
# Progress Management
# =============================================================================

def load_progress(filepath):
    """Load progress from JSON file, or return empty state."""
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "phase": "youtube",  # youtube → ai → airtable → done
        "leads": {},  # key = row index, value = enriched lead data
        "youtube_done": [],  # list of row indices completed
        "ai_done": [],  # list of row indices completed
        "airtable_done": [],  # list of row indices completed
        "stats": {
            "youtube_api_units": 0,
            "quota_hit": False,
        },
    }


def save_progress(progress, filepath):
    """Save progress to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, default=str)


# =============================================================================
# YouTube URL Parsing (shared with stage1)
# =============================================================================

def parse_youtube_url(url):
    """Extract channel identifier from various YouTube URL formats."""
    if not url or not isinstance(url, str):
        return ("unknown", None)

    url = url.strip()

    match = re.search(r'youtube\.com/@([^/?&\s]+)', url)
    if match:
        return ("handle", match.group(1))

    match = re.search(r'youtube\.com/channel/(UC[^/?&\s]+)', url)
    if match:
        return ("channel_id", match.group(1))

    match = re.search(r'youtube\.com/c/([^/?&\s]+)', url)
    if match:
        return ("custom_url", match.group(1))

    match = re.search(r'youtube\.com/user/([^/?&\s]+)', url)
    if match:
        return ("username", match.group(1))

    match = re.search(r'(?:youtube\.com/watch\?.*v=|youtu\.be/)([^&\s?]+)', url)
    if match:
        return ("video_id", match.group(1))

    return ("unknown", None)


# =============================================================================
# YouTube API
# =============================================================================

def yt_api_get(endpoint, params, progress):
    """Make a YouTube API request. Tracks quota usage."""
    params["key"] = YOUTUBE_API_KEY
    resp = requests.get(f"{YOUTUBE_API_URL}/{endpoint}", params=params)

    if resp.status_code == 403:
        data = resp.json()
        error_reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
        if error_reason == "quotaExceeded":
            print("\n  QUOTA EXCEEDED — saving progress and stopping.")
            print("  Run the script again tomorrow to continue.")
            progress["stats"]["quota_hit"] = True
            save_progress(progress, PROGRESS_FILE)
            sys.exit(0)
        print(f"  API Error 403: {resp.text[:200]}")
        return None

    if resp.status_code != 200:
        print(f"  API Error {resp.status_code}: {resp.text[:200]}")
        return None

    # Track quota (approximate)
    if "search" in endpoint:
        progress["stats"]["youtube_api_units"] += 100
    else:
        progress["stats"]["youtube_api_units"] += 1

    return resp.json()


def resolve_channel_id(url, progress):
    """Take any YouTube URL and return (channel_id, id_type)."""
    id_type, value = parse_youtube_url(url)

    if id_type == "channel_id":
        return value
    elif id_type == "handle":
        data = yt_api_get("channels", {"part": "id", "forHandle": value}, progress)
        if data and data.get("items"):
            return data["items"][0]["id"]
        # Fallback to search
        data = yt_api_get("search", {"part": "snippet", "q": value, "type": "channel", "maxResults": 1}, progress)
        if data and data.get("items"):
            return data["items"][0]["snippet"]["channelId"]
    elif id_type == "username":
        data = yt_api_get("channels", {"part": "id", "forUsername": value}, progress)
        if data and data.get("items"):
            return data["items"][0]["id"]
    elif id_type == "custom_url":
        data = yt_api_get("search", {"part": "snippet", "q": value, "type": "channel", "maxResults": 1}, progress)
        if data and data.get("items"):
            return data["items"][0]["snippet"]["channelId"]
    elif id_type == "video_id":
        data = yt_api_get("videos", {"part": "snippet", "id": value}, progress)
        if data and data.get("items"):
            return data["items"][0]["snippet"]["channelId"]

    return None


def get_channel_details_single(channel_id, progress):
    """Fetch full details for a single channel."""
    data = yt_api_get("channels", {
        "part": "snippet,contentDetails,statistics,brandingSettings",
        "id": channel_id,
    }, progress)
    if data and data.get("items"):
        return data["items"][0]
    return None


def get_recent_videos(channel_data, num_videos, progress):
    """Get recent video details (titles, descriptions, durations) for a channel."""
    uploads_playlist = channel_data.get("contentDetails", {}).get(
        "relatedPlaylists", {}
    ).get("uploads")

    if not uploads_playlist:
        return []

    # Get video IDs from uploads playlist
    data = yt_api_get("playlistItems", {
        "part": "contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": num_videos,
    }, progress)

    if not data or not data.get("items"):
        return []

    video_ids = [item["contentDetails"]["videoId"] for item in data["items"]]

    # Get full video details
    data = yt_api_get("videos", {
        "part": "contentDetails,snippet",
        "id": ",".join(video_ids),
    }, progress)

    if not data:
        return []

    return data.get("items", [])


def parse_duration(iso_duration):
    """Parse ISO 8601 duration (PT1H2M3S) to total minutes."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 60 + minutes + seconds / 60


def extract_email_from_text(text):
    """Extract email addresses from text (channel description)."""
    if not text:
        return None
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    # Filter out common non-personal emails
    filtered = [e for e in emails if not any(
        x in e.lower() for x in ["@gmail.com.tr", "@example", "noreply", "no-reply"]
    )]
    return filtered[0] if filtered else None


def get_channel_handle(channel_data):
    """Extract @handle from channel data, if available."""
    snippet = channel_data.get("snippet", {})
    custom_url = snippet.get("customUrl", "")
    if custom_url and custom_url.startswith("@"):
        return custom_url[1:]  # Remove the @
    return None


# =============================================================================
# Gate Checks
# =============================================================================

def run_gate_checks(channel_data, video_details):
    """Run auto gate checks. Returns dict of gate results."""
    results = {
        "gate_active": False,
        "gate_long_form": False,
        "gate_english": False,
        "gate_passed": False,
        "gate_fail_reasons": [],
        "last_upload_date": None,
        "avg_duration_mins": None,
    }

    if not channel_data:
        results["gate_fail_reasons"].append("Channel not found")
        return results

    snippet = channel_data.get("snippet", {})
    country = snippet.get("country", "")
    language = snippet.get("defaultLanguage", "")

    # English check — only auto-reject channels with non-Latin script titles
    # (Chinese, Arabic, Cyrillic, Korean, Thai, etc.)
    # Latin-script languages (German, French, Spanish) pass the gate —
    # Claude AI will detect actual language in Phase 2 for manual review.
    is_english = True
    if video_details:
        titles = [vid.get("snippet", {}).get("title", "") for vid in video_details if vid.get("snippet", {}).get("title")]
        if titles:
            combined = " ".join(titles)
            # Count characters that are Latin-based (includes accented: é, ü, ñ etc.)
            # Latin Extended range covers Western European languages
            latin_chars = sum(1 for c in combined if (
                ord(c) < 0x0250  # Basic Latin + Latin Extended-A/B
                or c in "–—''""…•"  # Common punctuation
            ))
            total_chars = len(combined.replace(" ", ""))
            if total_chars > 0:
                latin_ratio = latin_chars / (total_chars + len([c for c in combined if c == " "]))
                # If less than 60% Latin, it's clearly a non-Latin script channel
                is_english = latin_ratio >= 0.60

    results["gate_english"] = is_english
    if not is_english:
        sample_titles = [vid.get("snippet", {}).get("title", "")[:50] for vid in video_details[:2]]
        results["gate_fail_reasons"].append(f"Non-Latin script titles: {'; '.join(sample_titles)}")

    # Active check
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
                results["gate_fail_reasons"].append(f"Inactive (last upload: {results['last_upload_date']})")
        else:
            results["gate_fail_reasons"].append("Could not determine last upload date")
    else:
        results["gate_fail_reasons"].append("No videos found")

    # Long form check
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
                results["gate_fail_reasons"].append(f"Short form (avg {results['avg_duration_mins']} min)")
    else:
        results["gate_fail_reasons"].append("No video data for duration check")

    results["gate_passed"] = (
        results["gate_active"]
        and results["gate_long_form"]
        and results["gate_english"]
    )

    return results


# =============================================================================
# Claude AI Classification
# =============================================================================

def classify_with_claude(channel_name, channel_description, videos, progress):
    """
    Use Claude to classify a channel's niche and content signals.
    videos = list of {title, description} dicts.
    """
    video_text = ""
    for i, v in enumerate(videos, 1):
        video_text += f"\n  Video {i}: {v['title']}\n  Description: {v['description'][:500]}\n"

    prompt = f"""You are classifying a YouTube channel for a creative agency that does 3D/2D motion graphics for storytelling YouTubers.

CHANNEL: {channel_name}
CHANNEL DESCRIPTION: {(channel_description or 'N/A')[:800]}

RECENT VIDEOS:{video_text}

Classify this channel. Respond in EXACTLY this JSON format, nothing else:
{{
  "primary_niche": "<one of: Explainer, Documentary, True Crime / Mystery, History & Politics, Science & Space, Nature & Geo, Tech & Innovation, Finance & Business, 3D Animated Storytelling>",
  "sub_niche": "<short description like 'military history' or 'deep sea biology'>",
  "is_idea_led": <true if content is concept/idea-driven and CANNOT be shown with real filmed footage, false otherwise>,
  "is_storytelling_docs_explainer": <true if the content is storytelling, documentary, or explainer style>,
  "has_sponsors": <true if any video description mentions a sponsor, false otherwise>,
  "has_patreon": <true if any text mentions Patreon, membership, or similar>,
  "uses_3d": <true if evidence of 3D animation/visuals, false or uncertain = false>,
  "uses_motion_graphics_2d": <true if evidence of 2D motion graphics/animation, false or uncertain = false>,
  "uses_stock_footage": <true if likely uses stock footage/photos as primary visuals, false otherwise>,
  "content_language": "<primary language of the content, e.g. 'English', 'German', 'Spanish'>"
}}

Be conservative with visual style flags (uses_3d, uses_motion_graphics_2d, uses_stock_footage) — only mark true if there are strong clues. When uncertain, mark false. The team will verify manually.
For content_language, judge by the video TITLES and DESCRIPTIONS — a creator based in Germany making English videos = "English"."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # Validate niche
        if result.get("primary_niche") not in VALID_NICHES:
            result["primary_niche"] = None

        return result

    except Exception as e:
        print(f"    Claude API error: {e}")
        return None


# =============================================================================
# Airtable Import
# =============================================================================

def airtable_request(method, table_name, data=None):
    """Make an Airtable API request."""
    from urllib.parse import quote
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(table_name, safe='')}"

    if method == "GET":
        resp = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        resp = requests.post(url, headers=headers, json=data)
    elif method == "PATCH":
        resp = requests.patch(url, headers=headers, json=data)
    else:
        raise ValueError(f"Unknown method: {method}")

    if resp.status_code == 429:
        # Rate limited — wait and retry
        print("    Airtable rate limited, waiting 30s...")
        time.sleep(30)
        return airtable_request(method, table_name, data)

    if resp.status_code not in (200, 201):
        print(f"    Airtable error {resp.status_code}: {resp.text[:300]}")
        print(f"    URL: {url}")
        return None

    return resp.json()


def build_airtable_record(lead, valid_fields=None):
    """Convert enriched lead data to Airtable record fields."""
    fields = {
        "Channel Name": lead.get("channel_name", ""),
        "Channel URL": lead.get("normalized_url", lead.get("youtube_url", "")),
        "Contact Email": lead.get("email", "") or lead.get("bio_email", ""),
        "Date Added": datetime.now().strftime("%Y-%m-%d"),
        "Added By": "Auto Import (Stage 2)",
    }

    # Subscriber count
    subs = lead.get("subscribers_api") or lead.get("subscribers_parsed")
    if subs:
        fields["Subscriber Count"] = int(subs)

    # Email in bio
    if lead.get("bio_email"):
        fields["Has Email in Bio"] = True

    # Gate checks
    if lead.get("gate_active") is not None:
        fields["GATE: Active Channel"] = bool(lead.get("gate_active"))
    if lead.get("gate_long_form") is not None:
        fields["GATE: Long Form Content"] = bool(lead.get("gate_long_form"))
    if lead.get("gate_english") is not None:
        fields["GATE: English Speaking"] = bool(lead.get("gate_english"))

    # Channel description as discovery notes
    desc = lead.get("channel_description", "")
    notes_parts = []
    if lead.get("about"):
        notes_parts.append(f"Sheet note: {lead['about']}")
    if lead.get("remark"):
        notes_parts.append(f"Remark: {lead['remark']}")
    if lead.get("gate_fail_reasons"):
        notes_parts.append(f"Gate failures: {', '.join(lead['gate_fail_reasons'])}")
    if desc:
        notes_parts.append(f"Channel bio: {desc[:500]}")
    if notes_parts:
        fields["Discovery Notes"] = "\n".join(notes_parts)

    # Outreach status based on replied/worked_with
    if lead.get("worked_with"):
        fields["Outreach Status"] = "Won - Active Client"
    elif lead.get("didnt_work_out"):
        fields["Outreach Status"] = "Lost"
    elif lead.get("replied"):
        fields["Outreach Status"] = "In Conversation"
    else:
        fields["Outreach Status"] = "New Lead"

    # AI classification fields (only if AI was run)
    ai = lead.get("ai_classification")
    if ai:
        # If Claude detected non-English, override the gate
        lang = ai.get("content_language", "").lower()
        if lang and lang != "english" and not lang.startswith("english"):
            fields["GATE: English Speaking"] = False

        if ai.get("primary_niche"):
            fields["Primary Niche"] = ai["primary_niche"]
        if ai.get("sub_niche"):
            fields["Sub-Niche Notes"] = ai["sub_niche"]
        if ai.get("is_idea_led"):
            fields["GATE: Idea-Led Content"] = True
        if ai.get("is_storytelling_docs_explainer"):
            fields["GATE: Storytelling/Docs/Explainer"] = True
        if ai.get("has_sponsors"):
            fields["Has Sponsors"] = True
        if ai.get("has_patreon"):
            fields["Has Patreon / Membership"] = True
        if ai.get("uses_3d"):
            fields["Uses 3D"] = True
        if ai.get("uses_motion_graphics_2d"):
            fields["Uses Motion Graphics / 2D"] = True
        if ai.get("uses_stock_footage"):
            fields["Uses Stock Footage / Photo"] = True

    # Response sheet data
    if lead.get("response_niche") and not ai:
        # Only use response niche if AI didn't classify
        pass  # Response niche is free-text, not a valid select option
    if lead.get("response_video_style"):
        existing_notes = fields.get("Discovery Notes", "")
        fields["Discovery Notes"] = existing_notes + f"\nResponse sheet video style: {lead['response_video_style']}"

    # Sample video URL (first video from the channel)
    if lead.get("sample_video_url"):
        fields["Sample Video URL"] = lead["sample_video_url"]

    # Clean up: remove empty string values (Airtable doesn't like empty emails)
    fields = {k: v for k, v in fields.items() if v not in ("", None)}

    # Filter to only fields that exist in the table
    if valid_fields:
        skipped = [k for k in fields if k not in valid_fields]
        fields = {k: v for k, v in fields.items() if k in valid_fields}
        if skipped:
            pass  # Silently skip unknown fields

    return {"fields": fields}


def import_to_airtable(leads_to_import, progress, valid_fields=None):
    """
    Batch import leads to Airtable. 10 records at a time.
    Returns number of successfully imported records.
    """
    imported = 0
    batch_size = 10

    for i in range(0, len(leads_to_import), batch_size):
        batch = leads_to_import[i:i + batch_size]
        records = [build_airtable_record(lead, valid_fields) for _, lead in batch]

        result = airtable_request("POST", "Channels", {"records": records})

        if result and result.get("records"):
            for idx, _ in batch:
                if idx not in progress["airtable_done"]:
                    progress["airtable_done"].append(idx)
            imported += len(result["records"])
            print(f"    Imported batch {i // batch_size + 1}: {len(result['records'])} records")
        else:
            print(f"    Failed batch {i // batch_size + 1}")
            # Try one by one for this batch
            for idx, lead in batch:
                record = build_airtable_record(lead, valid_fields)
                result = airtable_request("POST", "Channels", {"records": [record]})
                if result and result.get("records"):
                    if idx not in progress["airtable_done"]:
                        progress["airtable_done"].append(idx)
                    imported += 1
                else:
                    print(f"      Failed: {lead.get('channel_name', 'unknown')}")
                time.sleep(0.25)

        save_progress(progress, PROGRESS_FILE)
        time.sleep(0.25)  # Airtable rate limit: 5 req/sec

    return imported


# =============================================================================
# File Reading (reused from stage1)
# =============================================================================

def read_xlsx_file(filepath):
    """Read XLSX file into normalized rows."""
    try:
        import openpyxl
    except ImportError:
        print("  pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    rows = []
    for row in ws.iter_rows(min_row=2, values_only=False):
        values = {headers[i]: (cell.value or "") for i, cell in enumerate(row) if i < len(headers)}
        normalized = normalize_row(values)
        rows.append(normalized)
    return rows


def read_csv_file(filepath):
    """Read CSV file into normalized rows."""
    import csv
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(normalize_row(row))
    return rows


def normalize_row(row):
    """Normalize column names to consistent keys."""
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

    # Check status text for "replied"
    if "replied" in normalized["status"].lower():
        normalized["replied"] = True

    return normalized


def parse_subscriber_count(sub_str):
    """Parse '164K', '1.04M' to an integer."""
    if not sub_str:
        return 0
    sub_str = str(sub_str).strip().upper().replace(",", "")
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
    return int(num)


def read_response_sheet(filepath):
    """Read Response Analysis 3D sheet. Returns lookup dict."""
    try:
        import openpyxl
        from stage1_autofilter import _is_green_color, _is_red_color
    except ImportError:
        print("  Need openpyxl and stage1_autofilter.py in same directory")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    lookup = {}
    for row in ws.iter_rows(min_row=2, values_only=False):
        values = {headers[i]: (cell.value or "") for i, cell in enumerate(row) if i < len(headers)}

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


# =============================================================================
# Main Pipeline
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Aftercells Stage 2: Enrich leads and import to Airtable"
    )
    parser.add_argument("input_file", nargs="?", help="Path to LEAD GEN.xlsx")
    parser.add_argument("--responses", help="Path to Response Analysis XLSX")
    parser.add_argument("--limit", type=int, help="Only process first N rows")
    parser.add_argument("--skip-ai", action="store_true", help="Skip Claude AI classification")
    parser.add_argument("--resume", action="store_true", help="Resume from progress.json")

    args = parser.parse_args()

    print("=" * 65)
    print("  AFTERCELLS LEAD MIGRATION - STAGE 2: ENRICH & IMPORT")
    print("=" * 65)

    # --- Validate keys ---
    missing = []
    if not YOUTUBE_API_KEY:
        missing.append("YOUTUBE_API_KEY")
    if not ANTHROPIC_API_KEY and not args.skip_ai:
        missing.append("ANTHROPIC_API_KEY")
    if not AIRTABLE_TOKEN:
        missing.append("AIRTABLE_PERSONAL_ACCESS_TOKEN")
    if not AIRTABLE_BASE_ID:
        missing.append("AIRTABLE_BASE_ID")
    if missing:
        print(f"\n  ERROR: Missing in .env: {', '.join(missing)}")
        sys.exit(1)

    # --- Test Airtable connection & get valid fields ---
    print(f"\n  Testing Airtable connection...")
    print(f"    Base ID: {AIRTABLE_BASE_ID}")
    test = airtable_request("GET", "Channels")
    if test is None:
        print("\n  ERROR: Can't connect to Airtable. Check your token and base ID.")
        print("  Make sure the 'Channels' table exists in your base.")
        sys.exit(1)
    print(f"    Connected! Found {len(test.get('records', []))} existing records.")

    # Get valid field names from existing records or table metadata
    valid_fields = set()
    # Fetch table schema via metadata API
    schema_resp = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
    )
    if schema_resp.status_code == 200:
        for table in schema_resp.json().get("tables", []):
            if table["name"] == "Channels":
                valid_fields = {f["name"] for f in table.get("fields", [])}
                break
    if valid_fields:
        print(f"    Found {len(valid_fields)} fields in Channels table")
    else:
        print("    WARNING: Could not fetch table schema, will try all fields")

    # --- Load progress ---
    progress = load_progress(PROGRESS_FILE)

    if args.resume:
        if not Path(PROGRESS_FILE).exists():
            print(f"\n  ERROR: No {PROGRESS_FILE} found. Run without --resume first.")
            sys.exit(1)
        print(f"\n  Resuming from {PROGRESS_FILE}...")
        print(f"    YouTube done: {len(progress['youtube_done'])}")
        print(f"    AI done: {len(progress['ai_done'])}")
        print(f"    Airtable done: {len(progress['airtable_done'])}")
        print(f"    API units used: {progress['stats']['youtube_api_units']}")

        # Need to reload leads from progress file
        if not progress.get("leads"):
            print("  ERROR: No lead data in progress file. Start fresh.")
            sys.exit(1)
    else:
        if not args.input_file:
            parser.error("input_file is required (unless using --resume)")

    # --- Read input files (only if not resuming) ---
    if not args.resume:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"\n  ERROR: File not found: {args.input_file}")
            sys.exit(1)

        # Read response sheet
        response_lookup = {}
        if args.responses:
            responses_path = Path(args.responses)
            if not responses_path.exists():
                print(f"\n  ERROR: Response sheet not found: {args.responses}")
                sys.exit(1)
            print(f"\n  Loading response sheet: {responses_path.name}...")
            response_lookup = read_response_sheet(args.responses)
            print(f"  Found {len(response_lookup)} channels in response sheet")

        # Read lead sheet
        print(f"\n  Reading {input_path.name}...")
        if input_path.suffix.lower() == ".xlsx":
            rows = read_xlsx_file(args.input_file)
        else:
            rows = read_csv_file(args.input_file)

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

        if args.limit:
            rows = rows[:args.limit]
            print(f"  (Limited to first {args.limit})")

        # Store leads in progress (keyed by row index as string for JSON)
        for i, row in enumerate(rows):
            idx = str(i)
            if idx not in progress["leads"]:
                progress["leads"][idx] = {
                    **row,
                    "subscribers_parsed": parse_subscriber_count(row.get("subscribers", "")),
                }

        save_progress(progress, PROGRESS_FILE)

    # --- Get total lead count ---
    all_indices = sorted(progress["leads"].keys(), key=int)
    total = len(all_indices)

    # =========================================================================
    # PHASE 1: YouTube API
    # =========================================================================
    youtube_todo = [idx for idx in all_indices if int(idx) not in progress["youtube_done"]]

    if youtube_todo:
        print(f"\n{'='*65}")
        print(f"  PHASE 1: YouTube API ({len(youtube_todo)} remaining of {total})")
        print(f"{'='*65}")
        print(f"  Estimated API units: ~{len(youtube_todo) * 3} (quota: 10,000/day)")
        print(f"  Units used so far: {progress['stats']['youtube_api_units']}")

        for count, idx in enumerate(youtube_todo, 1):
            lead = progress["leads"][idx]
            name = lead.get("channel_name", f"Row {idx}")
            url = lead.get("youtube_url", "")

            print(f"\n  [{count}/{len(youtube_todo)}] {name}...", end=" ", flush=True)

            if not url:
                lead["gate_fail_reasons"] = ["No YouTube URL"]
                lead["gate_passed"] = False
                progress["youtube_done"].append(int(idx))
                print("SKIP (no URL)")
                continue

            # Resolve channel ID
            channel_id = resolve_channel_id(url, progress)
            if not channel_id:
                lead["gate_fail_reasons"] = ["Could not resolve channel ID"]
                lead["gate_passed"] = False
                progress["youtube_done"].append(int(idx))
                print("FAILED (can't resolve)")
                continue

            lead["channel_id"] = channel_id

            # Fetch channel details
            ch_data = get_channel_details_single(channel_id, progress)
            if not ch_data:
                lead["gate_fail_reasons"] = ["Channel data not found (may be deleted)"]
                lead["gate_passed"] = False
                progress["youtube_done"].append(int(idx))
                print("FAILED (deleted?)")
                continue

            # Extract metadata
            snippet = ch_data.get("snippet", {})
            stats = ch_data.get("statistics", {})

            lead["channel_description"] = snippet.get("description", "")
            lead["subscribers_api"] = int(stats.get("subscriberCount", 0))
            lead["video_count"] = int(stats.get("videoCount", 0))
            lead["country"] = snippet.get("country", "")
            lead["language"] = snippet.get("defaultLanguage", "")

            # Normalize URL to @handle/videos format
            handle = get_channel_handle(ch_data)
            if handle:
                lead["normalized_url"] = f"https://www.youtube.com/@{handle}/videos"
            else:
                lead["normalized_url"] = f"https://www.youtube.com/channel/{channel_id}/videos"

            # Extract email from bio if we don't have one
            bio_email = extract_email_from_text(lead["channel_description"])
            if bio_email:
                lead["bio_email"] = bio_email
                if not lead.get("email"):
                    lead["email"] = bio_email

            # Fetch recent videos
            videos = get_recent_videos(ch_data, max(MIN_VIDEOS_TO_CHECK, VIDEOS_FOR_AI), progress)

            # Store video data for AI classification
            lead["video_data"] = []
            for vid in videos[:VIDEOS_FOR_AI]:
                lead["video_data"].append({
                    "title": vid.get("snippet", {}).get("title", ""),
                    "description": vid.get("snippet", {}).get("description", ""),
                })

            # Sample video URL (first video)
            if videos:
                first_vid_id = videos[0].get("id", "")
                if first_vid_id:
                    lead["sample_video_url"] = f"https://www.youtube.com/watch?v={first_vid_id}"

            # Run gate checks
            gate_results = run_gate_checks(ch_data, videos)
            lead.update(gate_results)

            status = "PASS" if gate_results["gate_passed"] else f"FAIL ({', '.join(gate_results['gate_fail_reasons'])})"
            print(f"{status} | {lead.get('subscribers_api', 0):,} subs")

            progress["youtube_done"].append(int(idx))

            # Save every 25 channels
            if count % 25 == 0:
                save_progress(progress, PROGRESS_FILE)
                print(f"\n  [Saved progress — {count}/{len(youtube_todo)} done, ~{progress['stats']['youtube_api_units']} API units used]")

            # Rate limit
            time.sleep(0.2)

        save_progress(progress, PROGRESS_FILE)
        print(f"\n  Phase 1 complete. API units used: {progress['stats']['youtube_api_units']}")

    else:
        print(f"\n  Phase 1: YouTube API — already complete ({total} channels)")

    # =========================================================================
    # PHASE 2: Claude AI Classification
    # =========================================================================
    if not args.skip_ai:
        # Only classify channels that passed gates and have video data
        ai_todo = [
            idx for idx in all_indices
            if int(idx) not in progress["ai_done"]
            and progress["leads"][idx].get("gate_passed")
            and progress["leads"][idx].get("video_data")
        ]

        if ai_todo:
            print(f"\n{'='*65}")
            print(f"  PHASE 2: AI Classification ({len(ai_todo)} channels)")
            print(f"{'='*65}")

            for count, idx in enumerate(ai_todo, 1):
                lead = progress["leads"][idx]
                name = lead.get("channel_name", f"Row {idx}")

                print(f"  [{count}/{len(ai_todo)}] {name}...", end=" ", flush=True)

                result = classify_with_claude(
                    name,
                    lead.get("channel_description", ""),
                    lead.get("video_data", []),
                    progress,
                )

                if result:
                    lead["ai_classification"] = result
                    niche = result.get("primary_niche", "?")
                    print(f"{niche}")
                else:
                    print("FAILED")

                progress["ai_done"].append(int(idx))

                # Save every 25
                if count % 25 == 0:
                    save_progress(progress, PROGRESS_FILE)
                    print(f"\n  [Saved progress — {count}/{len(ai_todo)} classified]")

                # Small delay to avoid rate limits
                time.sleep(0.3)

            save_progress(progress, PROGRESS_FILE)
            print(f"\n  Phase 2 complete. {len(ai_todo)} channels classified.")

        else:
            passed_count = sum(1 for idx in all_indices if progress["leads"][idx].get("gate_passed"))
            print(f"\n  Phase 2: AI Classification — already complete ({passed_count} channels)")

    else:
        print(f"\n  Phase 2: AI Classification — SKIPPED (--skip-ai)")

    # =========================================================================
    # PHASE 3: Import to Airtable
    # =========================================================================
    airtable_todo = [
        (int(idx), progress["leads"][idx])
        for idx in all_indices
        if int(idx) not in progress["airtable_done"]
    ]

    if airtable_todo:
        print(f"\n{'='*65}")
        print(f"  PHASE 3: Import to Airtable ({len(airtable_todo)} leads)")
        print(f"{'='*65}")

        imported = import_to_airtable(airtable_todo, progress, valid_fields)
        save_progress(progress, PROGRESS_FILE)
        print(f"\n  Phase 3 complete. Imported {imported} leads to Airtable.")

    else:
        print(f"\n  Phase 3: Airtable Import — already complete ({total} leads)")

    # =========================================================================
    # Summary
    # =========================================================================
    passed = sum(1 for idx in all_indices if progress["leads"][idx].get("gate_passed"))
    failed = total - passed
    ai_done = len(progress["ai_done"])
    airtable_done = len(progress["airtable_done"])

    print(f"\n{'='*65}")
    print(f"  MIGRATION COMPLETE")
    print(f"{'='*65}")
    print(f"\n  Total leads:         {total}")
    print(f"  Passed gates:        {passed} ({passed * 100 // max(total, 1)}%)")
    print(f"  Failed gates:        {failed} ({failed * 100 // max(total, 1)}%)")
    print(f"  AI classified:       {ai_done}")
    print(f"  Imported to Airtable: {airtable_done}")
    print(f"  YouTube API units:   ~{progress['stats']['youtube_api_units']}")
    print(f"\n  Progress saved to {PROGRESS_FILE}")
    print(f"  If anything failed, run: python stage2_enrich.py --resume")
    print()


if __name__ == "__main__":
    main()
