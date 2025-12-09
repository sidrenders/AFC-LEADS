"""
YouTube Data API v3 Client
FREE tier: 10,000 quota units per day

Quota costs:
- search.list: 100 units
- channels.list: 1 unit
- videos.list: 1 unit

So you can do ~100 searches OR ~10,000 channel lookups per day for FREE
"""
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import YOUTUBE_API_KEY


class YouTubeClient:
    """
    YouTube Data API v3 client with quota-aware methods
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YouTube API key required. Set YOUTUBE_API_KEY in .env")

        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.quota_used = 0

    def _track_quota(self, cost: int):
        """Track API quota usage"""
        self.quota_used += cost

    async def search_channels(
        self,
        query: str,
        max_results: int = 50,
        order: str = 'relevance',
        region_code: str = None,
        published_after: datetime = None
    ) -> List[Dict]:
        """
        Search for channels by keyword
        Cost: 100 quota units per call
        """
        try:
            params = {
                'q': query,
                'type': 'channel',
                'part': 'snippet',
                'maxResults': min(max_results, 50),  # API max is 50
                'order': order
            }

            if region_code:
                params['regionCode'] = region_code
            if published_after:
                params['publishedAfter'] = published_after.isoformat() + 'Z'

            # Run in thread pool to not block async
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.youtube.search().list(**params).execute()
            )

            self._track_quota(100)

            channels = []
            for item in response.get('items', []):
                channels.append({
                    'youtube_channel_id': item['snippet']['channelId'],
                    'channel_name': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_url': f"https://youtube.com/channel/{item['snippet']['channelId']}",
                    'discovery_source': 'search'
                })

            return channels

        except HttpError as e:
            if e.resp.status == 403:
                print(f"Quota exceeded or API key issue: {e}")
            raise

    async def get_channel_details(self, channel_id: str) -> Optional[Dict]:
        """
        Get detailed channel information
        Cost: 1 quota unit (very cheap!)
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.youtube.channels().list(
                    part='snippet,statistics,brandingSettings,contentDetails',
                    id=channel_id
                ).execute()
            )

            self._track_quota(1)

            items = response.get('items', [])
            if not items:
                return None

            channel = items[0]
            snippet = channel.get('snippet', {})
            stats = channel.get('statistics', {})
            branding = channel.get('brandingSettings', {}).get('channel', {})

            # Extract email from description
            description = snippet.get('description', '')
            email = self._extract_email(description)

            return {
                'youtube_channel_id': channel_id,
                'channel_name': snippet.get('title'),
                'description': description,
                'handle': snippet.get('customUrl'),
                'channel_url': f"https://youtube.com/channel/{channel_id}",
                'subscriber_count': int(stats.get('subscriberCount', 0)),
                'total_views': int(stats.get('viewCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
                'country': snippet.get('country'),
                'keywords': branding.get('keywords', ''),
                'email': email
            }

        except HttpError as e:
            print(f"Error getting channel {channel_id}: {e}")
            return None

    async def get_channels_batch(self, channel_ids: List[str]) -> List[Dict]:
        """
        Get multiple channels in one API call (up to 50)
        Cost: 1 quota unit per call (regardless of how many channels)
        """
        if not channel_ids:
            return []

        channels = []

        # Process in batches of 50
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i+50]

            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.youtube.channels().list(
                        part='snippet,statistics,brandingSettings',
                        id=','.join(batch)
                    ).execute()
                )

                self._track_quota(1)

                for channel in response.get('items', []):
                    snippet = channel.get('snippet', {})
                    stats = channel.get('statistics', {})
                    description = snippet.get('description', '')

                    channels.append({
                        'youtube_channel_id': channel['id'],
                        'channel_name': snippet.get('title'),
                        'description': description,
                        'handle': snippet.get('customUrl'),
                        'channel_url': f"https://youtube.com/channel/{channel['id']}",
                        'subscriber_count': int(stats.get('subscriberCount', 0)),
                        'total_views': int(stats.get('viewCount', 0)),
                        'video_count': int(stats.get('videoCount', 0)),
                        'country': snippet.get('country'),
                        'email': self._extract_email(description)
                    })

            except HttpError as e:
                print(f"Error in batch request: {e}")

        return channels

    async def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 20,
        order: str = 'date'
    ) -> List[Dict]:
        """
        Get recent videos from a channel
        Cost: 100 units for search + 1 unit for video details
        """
        try:
            # Search for videos from this channel
            loop = asyncio.get_event_loop()
            search_response = await loop.run_in_executor(
                None,
                lambda: self.youtube.search().list(
                    part='snippet',
                    channelId=channel_id,
                    type='video',
                    order=order,
                    maxResults=min(max_results, 50)
                ).execute()
            )

            self._track_quota(100)

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

            if not video_ids:
                return []

            # Get video statistics
            video_response = await loop.run_in_executor(
                None,
                lambda: self.youtube.videos().list(
                    part='statistics,contentDetails,snippet',
                    id=','.join(video_ids)
                ).execute()
            )

            self._track_quota(1)

            videos = []
            for video in video_response.get('items', []):
                stats = video.get('statistics', {})
                snippet = video.get('snippet', {})

                videos.append({
                    'youtube_video_id': video['id'],
                    'channel_id': channel_id,
                    'title': snippet.get('title'),
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'published_at': snippet.get('publishedAt')
                })

            return videos

        except HttpError as e:
            print(f"Error getting videos for {channel_id}: {e}")
            return []

    async def search_videos(
        self,
        query: str,
        max_results: int = 50,
        order: str = 'viewCount'
    ) -> List[Dict]:
        """
        Search for videos by keyword
        Cost: 100 quota units
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.youtube.search().list(
                    q=query,
                    type='video',
                    part='snippet',
                    maxResults=min(max_results, 50),
                    order=order
                ).execute()
            )

            self._track_quota(100)

            videos = []
            for item in response.get('items', []):
                videos.append({
                    'youtube_video_id': item['id']['videoId'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_name': item['snippet']['channelTitle'],
                    'title': item['snippet']['title']
                })

            return videos

        except HttpError as e:
            print(f"Error searching videos: {e}")
            return []

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from text"""
        if not text:
            return None

        # Common email patterns
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(email_pattern, text)

        # Filter out common non-business emails
        filtered = [
            email for email in matches
            if not any(x in email.lower() for x in ['example.com', 'email.com', 'youremail'])
        ]

        return filtered[0] if filtered else None

    def get_quota_usage(self) -> dict:
        """Get quota usage stats"""
        return {
            'used': self.quota_used,
            'limit': 10000,
            'remaining': 10000 - self.quota_used,
            'searches_remaining': (10000 - self.quota_used) // 100
        }
