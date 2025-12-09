"""
Seed Data Importer
Import your existing 2000+ leads into the system
"""
import asyncio
import re
import csv
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd

from models.database import Database, Channel
from api.youtube_client import YouTubeClient


def extract_channel_id_from_url(url: str) -> Optional[str]:
    """
    Extract YouTube channel ID from various URL formats:
    - https://youtube.com/channel/UC...
    - https://youtube.com/@handle
    - https://youtube.com/c/customname
    - https://youtube.com/user/username
    """
    if not url:
        return None

    url = url.strip()

    # Direct channel ID format
    match = re.search(r'youtube\.com/channel/([a-zA-Z0-9_-]{24})', url)
    if match:
        return match.group(1)

    # Handle format (@username)
    match = re.search(r'youtube\.com/@([a-zA-Z0-9_-]+)', url)
    if match:
        return f"@{match.group(1)}"  # Will need to resolve via API

    # Custom URL format (/c/name)
    match = re.search(r'youtube\.com/c/([a-zA-Z0-9_-]+)', url)
    if match:
        return f"c/{match.group(1)}"  # Will need to resolve via API

    # User format (/user/name)
    match = re.search(r'youtube\.com/user/([a-zA-Z0-9_-]+)', url)
    if match:
        return f"user/{match.group(1)}"  # Will need to resolve via API

    # Check if it's already a channel ID (24 chars)
    if re.match(r'^UC[a-zA-Z0-9_-]{22}$', url):
        return url

    return None


def extract_video_id_from_url(url: str) -> Optional[str]:
    """
    Extract video ID from YouTube video URLs
    """
    if not url:
        return None

    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


class SeedImporter:
    """
    Import existing leads from CSV/Excel into the database
    """

    def __init__(self, db: Database, youtube_client: YouTubeClient = None):
        self.db = db
        self.youtube = youtube_client

    async def import_from_csv(
        self,
        file_path: str,
        channel_column: str = None,
        video_column: str = None,
        name_column: str = None,
        enrich: bool = True,
        batch_size: int = 50
    ) -> Dict:
        """
        Import channels from CSV file

        Args:
            file_path: Path to CSV file
            channel_column: Column name containing channel URLs/IDs
            video_column: Column name containing video URLs (optional, for extracting channels)
            name_column: Column name containing channel names
            enrich: Whether to fetch additional data from YouTube API
            batch_size: How many channels to process at once
        """
        results = {
            'total_rows': 0,
            'imported': 0,
            'skipped_duplicates': 0,
            'skipped_invalid': 0,
            'errors': []
        }

        # Read CSV
        df = pd.read_csv(file_path)
        results['total_rows'] = len(df)

        # Auto-detect columns if not specified
        if not channel_column:
            channel_column = self._find_column(df, ['channel', 'channel_url', 'youtube_channel', 'link'])
        if not video_column:
            video_column = self._find_column(df, ['video', 'video_url', 'youtube_video'])
        if not name_column:
            name_column = self._find_column(df, ['name', 'channel_name', 'title'])

        print(f"Using columns: channel={channel_column}, video={video_column}, name={name_column}")

        # Extract channel IDs
        channels_to_import = []

        for idx, row in df.iterrows():
            channel_id = None
            channel_name = row.get(name_column, '') if name_column else ''

            # Try channel URL first
            if channel_column and pd.notna(row.get(channel_column)):
                channel_id = extract_channel_id_from_url(str(row[channel_column]))

            # If no channel ID, try video URL
            if not channel_id and video_column and pd.notna(row.get(video_column)):
                video_id = extract_video_id_from_url(str(row[video_column]))
                if video_id:
                    # Will need to resolve channel from video later
                    channels_to_import.append({
                        'video_id': video_id,
                        'channel_name': channel_name,
                        'needs_resolution': True
                    })
                    continue

            if channel_id:
                channels_to_import.append({
                    'youtube_channel_id': channel_id,
                    'channel_name': channel_name,
                    'needs_resolution': channel_id.startswith(('@', 'c/', 'user/'))
                })
            else:
                results['skipped_invalid'] += 1

        print(f"Found {len(channels_to_import)} potential channels to import")

        # Process in batches
        for i in range(0, len(channels_to_import), batch_size):
            batch = channels_to_import[i:i + batch_size]
            print(f"Processing batch {i // batch_size + 1}/{(len(channels_to_import) // batch_size) + 1}")

            # Resolve handles/custom URLs if needed and enrichment is enabled
            if enrich and self.youtube:
                batch = await self._resolve_and_enrich_batch(batch)

            # Import to database
            for channel_data in batch:
                if not channel_data.get('youtube_channel_id'):
                    results['skipped_invalid'] += 1
                    continue

                # Check if valid channel ID format
                ch_id = channel_data['youtube_channel_id']
                if not re.match(r'^UC[a-zA-Z0-9_-]{22}$', ch_id):
                    results['skipped_invalid'] += 1
                    continue

                # Add to database
                channel_data['discovery_source'] = 'seed'

                try:
                    result = await self.db.add_channel(channel_data)
                    if result:
                        results['imported'] += 1
                    else:
                        results['skipped_duplicates'] += 1
                except Exception as e:
                    results['errors'].append(str(e))

        return results

    async def import_from_excel(self, file_path: str, **kwargs) -> Dict:
        """Import from Excel file"""
        # Convert to CSV first for simplicity
        df = pd.read_excel(file_path)
        temp_csv = file_path.replace('.xlsx', '_temp.csv').replace('.xls', '_temp.csv')
        df.to_csv(temp_csv, index=False)

        try:
            results = await self.import_from_csv(temp_csv, **kwargs)
        finally:
            Path(temp_csv).unlink(missing_ok=True)

        return results

    async def _resolve_and_enrich_batch(self, batch: List[Dict]) -> List[Dict]:
        """Resolve handles and enrich with API data"""
        enriched = []

        # Separate channels that need resolution vs direct IDs
        needs_resolution = [c for c in batch if c.get('needs_resolution')]
        direct_ids = [c for c in batch if not c.get('needs_resolution') and c.get('youtube_channel_id')]

        # For direct IDs, batch fetch details
        if direct_ids:
            channel_ids = [c['youtube_channel_id'] for c in direct_ids]
            details = await self.youtube.get_channels_batch(channel_ids)

            details_map = {d['youtube_channel_id']: d for d in details}

            for channel in direct_ids:
                ch_id = channel['youtube_channel_id']
                if ch_id in details_map:
                    merged = {**channel, **details_map[ch_id]}
                    enriched.append(merged)
                else:
                    enriched.append(channel)

        # For handles/custom URLs, need to search (more expensive)
        for channel in needs_resolution:
            if channel.get('video_id'):
                # Get channel from video
                try:
                    videos = await self.youtube.youtube.videos().list(
                        part='snippet',
                        id=channel['video_id']
                    ).execute()

                    if videos.get('items'):
                        ch_id = videos['items'][0]['snippet']['channelId']
                        details = await self.youtube.get_channel_details(ch_id)
                        if details:
                            enriched.append(details)
                except Exception as e:
                    print(f"Error resolving video {channel.get('video_id')}: {e}")

            elif channel.get('youtube_channel_id', '').startswith('@'):
                # Handle format - search for it
                handle = channel['youtube_channel_id']
                try:
                    results = await self.youtube.search_channels(handle, max_results=1)
                    if results:
                        details = await self.youtube.get_channel_details(results[0]['youtube_channel_id'])
                        if details:
                            enriched.append(details)
                except Exception as e:
                    print(f"Error resolving handle {handle}: {e}")

            await asyncio.sleep(0.5)  # Rate limiting

        return enriched

    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Find column by possible names (case-insensitive)"""
        columns_lower = {col.lower(): col for col in df.columns}

        for name in possible_names:
            if name.lower() in columns_lower:
                return columns_lower[name.lower()]

        return None


async def quick_import(csv_path: str, db_url: str = None):
    """
    Quick import function for command line use
    """
    from config import DATABASE_URL, YOUTUBE_API_KEY

    db = Database(db_url or DATABASE_URL)
    await db.init()

    youtube = YouTubeClient(YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

    importer = SeedImporter(db, youtube)
    results = await importer.import_from_csv(csv_path, enrich=youtube is not None)

    print("\n=== Import Results ===")
    print(f"Total rows: {results['total_rows']}")
    print(f"Imported: {results['imported']}")
    print(f"Skipped (duplicates): {results['skipped_duplicates']}")
    print(f"Skipped (invalid): {results['skipped_invalid']}")
    if results['errors']:
        print(f"Errors: {len(results['errors'])}")

    return results
