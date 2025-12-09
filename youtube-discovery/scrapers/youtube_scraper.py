"""
Custom YouTube Scraper
FREE - No API quota used

Scrapes:
- Featured/related channels from channel pages
- Video recommendations sidebar
- Channel contact info from About page
"""
import asyncio
import re
import json
from typing import List, Dict, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

from config import SCRAPE_DELAY_SECONDS


class YouTubeScraper:
    """
    Custom scraper for YouTube data not available via API
    Uses httpx for async requests
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        self.delay = SCRAPE_DELAY_SECONDS

    async def _get_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting"""
        await asyncio.sleep(self.delay)

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_initial_data(self, html: str) -> Optional[dict]:
        """Extract ytInitialData JSON from YouTube page"""
        if not html:
            return None

        # Find the ytInitialData script
        pattern = r'var ytInitialData = ({.*?});'
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Alternative pattern
        pattern2 = r'ytInitialData\s*=\s*({.*?});'
        match2 = re.search(pattern2, html, re.DOTALL)

        if match2:
            try:
                return json.loads(match2.group(1))
            except json.JSONDecodeError:
                pass

        return None

    async def get_featured_channels(self, channel_id: str) -> List[Dict]:
        """
        Get featured/related channels from a channel's page
        These are channels that YouTube or the creator has associated
        """
        url = f"https://www.youtube.com/channel/{channel_id}/channels"
        html = await self._get_page(url)

        if not html:
            return []

        data = self._extract_initial_data(html)
        if not data:
            return []

        channels = []

        try:
            # Navigate the JSON structure to find channel items
            tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])

            for tab in tabs:
                tab_content = tab.get('tabRenderer', {}).get('content', {})
                section_list = tab_content.get('sectionListRenderer', {}).get('contents', [])

                for section in section_list:
                    items_section = section.get('itemSectionRenderer', {}).get('contents', [])

                    for item in items_section:
                        # Grid of channels
                        grid_items = item.get('gridRenderer', {}).get('items', [])

                        for grid_item in grid_items:
                            channel_data = grid_item.get('gridChannelRenderer', {})
                            if channel_data:
                                ch_id = channel_data.get('channelId')
                                if ch_id:
                                    channels.append({
                                        'youtube_channel_id': ch_id,
                                        'channel_name': channel_data.get('title', {}).get('simpleText', ''),
                                        'channel_url': f"https://youtube.com/channel/{ch_id}",
                                        'subscriber_count': self._parse_subscriber_text(
                                            channel_data.get('subscriberCountText', {}).get('simpleText', '')
                                        ),
                                        'discovery_source': 'similar',
                                        'seed_channel_id': channel_id
                                    })

        except Exception as e:
            print(f"Error parsing featured channels: {e}")

        return channels

    async def get_video_recommendations(self, video_id: str, max_results: int = 20) -> List[Dict]:
        """
        Get recommended videos from a video's watch page
        Returns unique channels from recommendations
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        html = await self._get_page(url)

        if not html:
            return []

        data = self._extract_initial_data(html)
        if not data:
            return []

        recommendations = []
        seen_channels = set()

        try:
            # Find secondary results (recommendations sidebar)
            secondary = data.get('contents', {}).get('twoColumnWatchNextResults', {}).get('secondaryResults', {})
            secondary_results = secondary.get('secondaryResults', {}).get('results', [])

            for item in secondary_results[:max_results * 2]:  # Get more to filter duplicates
                video_renderer = item.get('compactVideoRenderer', {})

                if video_renderer:
                    channel_id = video_renderer.get('channelId')

                    if channel_id and channel_id not in seen_channels:
                        seen_channels.add(channel_id)

                        recommendations.append({
                            'youtube_channel_id': channel_id,
                            'channel_name': video_renderer.get('shortBylineText', {}).get('runs', [{}])[0].get('text', ''),
                            'channel_url': f"https://youtube.com/channel/{channel_id}",
                            'source_video_id': video_id,
                            'recommended_video_id': video_renderer.get('videoId'),
                            'recommended_video_title': video_renderer.get('title', {}).get('simpleText', ''),
                            'discovery_source': 'recommendation'
                        })

                        if len(recommendations) >= max_results:
                            break

        except Exception as e:
            print(f"Error parsing recommendations: {e}")

        return recommendations

    async def get_channel_about(self, channel_id: str) -> Dict:
        """
        Scrape channel's About page for contact info
        """
        url = f"https://www.youtube.com/channel/{channel_id}/about"
        html = await self._get_page(url)

        if not html:
            return {}

        data = self._extract_initial_data(html)
        if not data:
            return {}

        about_info = {
            'email': None,
            'business_email': None,
            'links': [],
            'description': '',
            'location': None,
            'joined_date': None
        }

        try:
            # Navigate to about metadata
            tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])

            for tab in tabs:
                tab_renderer = tab.get('tabRenderer', {})
                if tab_renderer.get('title') == 'About':
                    content = tab_renderer.get('content', {})
                    section_list = content.get('sectionListRenderer', {}).get('contents', [])

                    for section in section_list:
                        items = section.get('itemSectionRenderer', {}).get('contents', [])

                        for item in items:
                            about_renderer = item.get('channelAboutFullMetadataRenderer', {})

                            if about_renderer:
                                # Description
                                about_info['description'] = about_renderer.get('description', {}).get('simpleText', '')

                                # Extract email from description
                                about_info['email'] = self._extract_email(about_info['description'])

                                # Business email (if visible)
                                business_email_data = about_renderer.get('primaryLinks', [])
                                for link in business_email_data:
                                    link_url = link.get('navigationEndpoint', {}).get('urlEndpoint', {}).get('url', '')
                                    if 'mailto:' in link_url:
                                        about_info['business_email'] = link_url.replace('mailto:', '')

                                # Links
                                links = about_renderer.get('links', [])
                                for link in links:
                                    link_renderer = link.get('channelExternalLinkViewModel', {})
                                    link_url = link_renderer.get('link', {}).get('commandRuns', [{}])[0].get('onTap', {}).get('innertubeCommand', {}).get('urlEndpoint', {}).get('url', '')
                                    if link_url:
                                        # Clean redirect URLs
                                        if 'redirect' in link_url and 'q=' in link_url:
                                            link_url = link_url.split('q=')[-1].split('&')[0]
                                            from urllib.parse import unquote
                                            link_url = unquote(link_url)
                                        about_info['links'].append(link_url)

                                # Country/Location
                                about_info['location'] = about_renderer.get('country', {}).get('simpleText', '')

                                # Joined date
                                about_info['joined_date'] = about_renderer.get('joinedDateText', {}).get('runs', [{}])[-1].get('text', '')

        except Exception as e:
            print(f"Error parsing about page: {e}")

        # Extract social media from links
        for link in about_info['links']:
            link_lower = link.lower()
            if 'instagram.com' in link_lower:
                about_info['instagram'] = link
            elif 'twitter.com' in link_lower or 'x.com' in link_lower:
                about_info['twitter'] = link
            elif 'tiktok.com' in link_lower:
                about_info['tiktok'] = link
            elif not any(x in link_lower for x in ['youtube', 'facebook', 'discord', 'twitch']):
                if not about_info.get('website'):
                    about_info['website'] = link

        return about_info

    async def get_channels_from_search_page(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Scrape YouTube search results for channels
        Alternative to API search (saves quota)
        """
        from urllib.parse import quote
        url = f"https://www.youtube.com/results?search_query={quote(query)}&sp=EgIQAg%3D%3D"  # Filter: Channels

        html = await self._get_page(url)
        if not html:
            return []

        data = self._extract_initial_data(html)
        if not data:
            return []

        channels = []

        try:
            contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {})
            section_list = contents.get('sectionListRenderer', {}).get('contents', [])

            for section in section_list:
                items = section.get('itemSectionRenderer', {}).get('contents', [])

                for item in items:
                    channel_renderer = item.get('channelRenderer', {})

                    if channel_renderer:
                        ch_id = channel_renderer.get('channelId')
                        if ch_id:
                            channels.append({
                                'youtube_channel_id': ch_id,
                                'channel_name': channel_renderer.get('title', {}).get('simpleText', ''),
                                'channel_url': f"https://youtube.com/channel/{ch_id}",
                                'subscriber_count': self._parse_subscriber_text(
                                    channel_renderer.get('subscriberCountText', {}).get('simpleText', '')
                                ),
                                'description': channel_renderer.get('descriptionSnippet', {}).get('runs', [{}])[0].get('text', ''),
                                'discovery_source': 'search'
                            })

                            if len(channels) >= max_results:
                                break

        except Exception as e:
            print(f"Error parsing search results: {e}")

        return channels

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from text"""
        if not text:
            return None

        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(email_pattern, text)

        # Filter out obvious non-business emails
        filtered = [
            email for email in matches
            if not any(x in email.lower() for x in ['example', '@email', 'youremail', 'your@'])
        ]

        return filtered[0] if filtered else None

    def _parse_subscriber_text(self, text: str) -> int:
        """Parse subscriber count text like '1.5M subscribers' to integer"""
        if not text:
            return 0

        text = text.lower().replace(',', '').replace(' subscribers', '').replace(' subscriber', '').strip()

        try:
            if 'k' in text:
                return int(float(text.replace('k', '')) * 1000)
            elif 'm' in text:
                return int(float(text.replace('m', '')) * 1000000)
            elif 'b' in text:
                return int(float(text.replace('b', '')) * 1000000000)
            else:
                return int(text)
        except ValueError:
            return 0


class PlaywrightScraper:
    """
    Playwright-based scraper for JavaScript-heavy pages
    Use when httpx scraping doesn't work
    """

    def __init__(self):
        self.browser = None
        self.delay = SCRAPE_DELAY_SECONDS

    async def init(self):
        """Initialize Playwright browser"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_video_recommendations_js(self, video_id: str, max_results: int = 20) -> List[Dict]:
        """
        Get recommendations using full browser (handles JS rendering)
        Use this if httpx method fails
        """
        if not self.browser:
            await self.init()

        await asyncio.sleep(self.delay)

        page = await self.browser.new_page()
        recommendations = []

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for recommendations to load
            await page.wait_for_selector('ytd-compact-video-renderer', timeout=10000)

            # Extract recommendation data
            recs = await page.evaluate('''() => {
                const items = document.querySelectorAll('ytd-compact-video-renderer');
                const results = [];
                const seenChannels = new Set();

                items.forEach(item => {
                    const channelLink = item.querySelector('ytd-channel-name a');
                    const videoLink = item.querySelector('#video-title');

                    if (channelLink && videoLink) {
                        const channelUrl = channelLink.href;
                        const channelIdMatch = channelUrl.match(/channel\\/([^/]+)/);
                        const channelId = channelIdMatch ? channelIdMatch[1] : null;

                        if (channelId && !seenChannels.has(channelId)) {
                            seenChannels.add(channelId);
                            results.push({
                                channel_id: channelId,
                                channel_name: channelLink.textContent.trim(),
                                video_title: videoLink.textContent.trim(),
                                video_id: videoLink.href.match(/v=([^&]+)/)?.[1]
                            });
                        }
                    }
                });

                return results;
            }''')

            for rec in recs[:max_results]:
                recommendations.append({
                    'youtube_channel_id': rec['channel_id'],
                    'channel_name': rec['channel_name'],
                    'channel_url': f"https://youtube.com/channel/{rec['channel_id']}",
                    'source_video_id': video_id,
                    'recommended_video_id': rec['video_id'],
                    'recommended_video_title': rec['video_title'],
                    'discovery_source': 'recommendation'
                })

        except Exception as e:
            print(f"Playwright error: {e}")

        finally:
            await page.close()

        return recommendations
