#!/usr/bin/env python3
"""
Fetch Thoughty2 videos from 2025 and sort by views
"""
import asyncio
import sys
sys.path.insert(0, '/home/user/test/youtube-discovery')

from scrapers.youtube_scraper import YouTubeScraper
from datetime import datetime

async def main():
    scraper = YouTubeScraper()

    print("Fetching videos from @Thoughty2 channel...")
    videos = await scraper.get_channel_videos("@Thoughty2", max_videos=200)

    print(f"\nTotal videos fetched: {len(videos)}")

    # Filter for 2025 videos (last year)
    videos_2025 = []
    for v in videos:
        pub_date = v.get('published_date')
        if pub_date and pub_date.year == 2025:
            videos_2025.append(v)
        elif v.get('published_text'):
            # If we can't parse the date but see "year ago" it might be from 2025
            pub_text = v['published_text'].lower()
            if '1 year ago' in pub_text:
                videos_2025.append(v)

    print(f"Videos from 2025: {len(videos_2025)}")

    # Sort by views (descending)
    videos_2025.sort(key=lambda x: x.get('views', 0), reverse=True)

    # Print results
    print("\n" + "="*80)
    print("THOUGHTY2 - 2025 VIDEOS SORTED BY VIEWS")
    print("="*80 + "\n")

    for i, video in enumerate(videos_2025, 1):
        views = video.get('views', 0)
        view_str = f"{views:,}" if views else video.get('view_text', 'N/A')
        print(f"{i:2}. {video['title'][:60]:<60}")
        print(f"    Views: {view_str} | Published: {video.get('published_text', 'N/A')} | Duration: {video.get('duration', 'N/A')}")
        print(f"    URL: {video['url']}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
