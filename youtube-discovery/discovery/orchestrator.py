"""
Discovery Orchestrator
Coordinates all discovery strategies and enrichment
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from models.database import Database, Channel
from api.youtube_client import YouTubeClient
from scrapers.youtube_scraper import YouTubeScraper
from utils.scorer import LeadScorer
from config import TARGET_NICHES, SCRAPE_DELAY_SECONDS

console = Console()


class DiscoveryOrchestrator:
    """
    Main orchestrator for YouTube channel discovery
    """

    def __init__(self, db: Database, youtube_client: YouTubeClient = None):
        self.db = db
        self.youtube = youtube_client
        self.scraper = YouTubeScraper()
        self.scorer = LeadScorer()
        self.stats = {
            'total_discovered': 0,
            'new_channels': 0,
            'duplicates': 0,
            'enriched': 0,
            'scored': 0
        }

    async def run_full_discovery(
        self,
        use_seeds: bool = True,
        use_keywords: bool = True,
        use_recommendations: bool = True,
        niches: List[str] = None,
        max_per_strategy: int = 100
    ) -> Dict:
        """
        Run complete discovery cycle with all strategies
        """
        console.print("\n[bold blue]Starting YouTube Channel Discovery[/bold blue]\n")

        results = {
            'started_at': datetime.utcnow().isoformat(),
            'strategies': [],
            'total_new': 0,
            'total_discovered': 0
        }

        # Strategy 1: Expand from seed channels
        if use_seeds:
            console.print("[yellow]Strategy 1:[/yellow] Seed Expansion")
            seed_results = await self.run_seed_expansion(limit=max_per_strategy)
            results['strategies'].append({
                'name': 'seed_expansion',
                **seed_results
            })
            results['total_new'] += seed_results['new_channels']
            results['total_discovered'] += seed_results['total_found']

        # Strategy 2: Keyword search
        if use_keywords:
            console.print("\n[yellow]Strategy 2:[/yellow] Keyword Search")
            target_niches = niches or list(TARGET_NICHES.keys())
            keyword_results = await self.run_keyword_search(
                niches=target_niches,
                max_per_niche=max_per_strategy // len(target_niches)
            )
            results['strategies'].append({
                'name': 'keyword_search',
                **keyword_results
            })
            results['total_new'] += keyword_results['new_channels']
            results['total_discovered'] += keyword_results['total_found']

        # Strategy 3: Video recommendations
        if use_recommendations:
            console.print("\n[yellow]Strategy 3:[/yellow] Video Recommendations")
            rec_results = await self.run_recommendations(limit=max_per_strategy)
            results['strategies'].append({
                'name': 'recommendations',
                **rec_results
            })
            results['total_new'] += rec_results['new_channels']
            results['total_discovered'] += rec_results['total_found']

        results['completed_at'] = datetime.utcnow().isoformat()

        # Print summary
        console.print("\n[bold green]Discovery Complete![/bold green]")
        console.print(f"  Total discovered: {results['total_discovered']}")
        console.print(f"  New channels: {results['total_new']}")

        if self.youtube:
            quota = self.youtube.get_quota_usage()
            console.print(f"  API quota used: {quota['used']}/10,000")

        return results

    async def run_seed_expansion(self, limit: int = 100) -> Dict:
        """
        Find similar channels based on seed database
        Uses scraping (FREE, no API quota)
        """
        results = {'total_found': 0, 'new_channels': 0, 'source': 'seed_expansion'}

        # Get top seed channels
        seeds = await self.db.get_seed_channels(limit=20)

        if not seeds:
            console.print("  [dim]No seed channels found. Import your leads first.[/dim]")
            return results

        console.print(f"  Using {len(seeds)} seed channels for expansion")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Finding similar channels...", total=len(seeds))

            for seed in seeds:
                # Get featured/related channels (FREE - scraping)
                similar = await self.scraper.get_featured_channels(seed.youtube_channel_id)

                for channel_data in similar:
                    results['total_found'] += 1

                    # Check if exists
                    exists = await self.db.channel_exists(channel_data['youtube_channel_id'])
                    if exists:
                        continue

                    # Enrich with API data (1 quota unit per batch of 50)
                    if self.youtube:
                        details = await self.youtube.get_channel_details(channel_data['youtube_channel_id'])
                        if details:
                            channel_data.update(details)

                    # Score the channel
                    score_result = self.scorer.calculate_score(channel_data)
                    channel_data['lead_score'] = score_result['total_score']
                    channel_data['tier'] = score_result['tier']

                    # Save to database
                    await self.db.add_channel(channel_data)
                    results['new_channels'] += 1

                    if results['new_channels'] >= limit:
                        break

                progress.update(task, advance=1)

                if results['new_channels'] >= limit:
                    break

                await asyncio.sleep(SCRAPE_DELAY_SECONDS)

        console.print(f"  Found {results['new_channels']} new channels from seed expansion")
        return results

    async def run_keyword_search(
        self,
        niches: List[str] = None,
        max_per_niche: int = 50
    ) -> Dict:
        """
        Search for channels by niche keywords
        Uses API (100 quota per search) OR scraping (FREE)
        """
        results = {'total_found': 0, 'new_channels': 0, 'source': 'keyword_search'}

        target_niches = niches or list(TARGET_NICHES.keys())

        for niche in target_niches:
            niche_config = TARGET_NICHES.get(niche, {})
            keywords = niche_config.get('keywords', [niche])

            console.print(f"  Searching niche: [cyan]{niche}[/cyan]")

            for keyword in keywords[:3]:  # Limit keywords per niche
                # Choose method based on API availability
                if self.youtube:
                    # Use API (costs quota but more reliable)
                    channels = await self.youtube.search_channels(
                        query=keyword,
                        max_results=20
                    )
                else:
                    # Use scraping (FREE)
                    channels = await self.scraper.get_channels_from_search_page(
                        query=keyword,
                        max_results=20
                    )

                for channel_data in channels:
                    results['total_found'] += 1

                    # Skip if exists
                    exists = await self.db.channel_exists(channel_data['youtube_channel_id'])
                    if exists:
                        continue

                    # Set niche
                    channel_data['primary_niche'] = niche
                    channel_data['discovery_source'] = 'search'

                    # Enrich with details
                    if self.youtube:
                        details = await self.youtube.get_channel_details(channel_data['youtube_channel_id'])
                        if details:
                            channel_data.update(details)

                    # Score
                    score_result = self.scorer.calculate_score(channel_data)
                    channel_data['lead_score'] = score_result['total_score']
                    channel_data['tier'] = score_result['tier']

                    # Save
                    await self.db.add_channel(channel_data)
                    results['new_channels'] += 1

                await asyncio.sleep(1)  # Rate limiting

        console.print(f"  Found {results['new_channels']} new channels from keyword search")
        return results

    async def run_recommendations(self, limit: int = 100) -> Dict:
        """
        Discover channels from video recommendations
        Uses scraping (FREE, no API quota)
        """
        results = {'total_found': 0, 'new_channels': 0, 'source': 'recommendations'}

        # Get high-performing videos from existing channels
        channels = await self.db.get_channels(
            min_subscribers=10000,
            limit=20
        )

        if not channels:
            console.print("  [dim]No channels with enough subscribers for recommendation mining.[/dim]")
            return results

        console.print(f"  Mining recommendations from {len(channels)} channels")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Getting recommendations...", total=len(channels))

            for channel in channels:
                # Get recent videos from channel
                if self.youtube:
                    videos = await self.youtube.get_channel_videos(
                        channel.youtube_channel_id,
                        max_results=5
                    )

                    for video in videos[:3]:
                        # Get recommendations (FREE - scraping)
                        recs = await self.scraper.get_video_recommendations(
                            video['youtube_video_id'],
                            max_results=10
                        )

                        for channel_data in recs:
                            results['total_found'] += 1

                            # Skip if exists
                            exists = await self.db.channel_exists(channel_data['youtube_channel_id'])
                            if exists:
                                continue

                            channel_data['seed_channel_id'] = channel.youtube_channel_id

                            # Enrich
                            if self.youtube:
                                details = await self.youtube.get_channel_details(channel_data['youtube_channel_id'])
                                if details:
                                    channel_data.update(details)

                            # Score
                            score_result = self.scorer.calculate_score(channel_data)
                            channel_data['lead_score'] = score_result['total_score']
                            channel_data['tier'] = score_result['tier']

                            # Save
                            await self.db.add_channel(channel_data)
                            results['new_channels'] += 1

                            if results['new_channels'] >= limit:
                                break

                        await asyncio.sleep(SCRAPE_DELAY_SECONDS)

                progress.update(task, advance=1)

                if results['new_channels'] >= limit:
                    break

        console.print(f"  Found {results['new_channels']} new channels from recommendations")
        return results

    async def enrich_channel(self, channel_id: str) -> Optional[Dict]:
        """
        Full enrichment for a single channel
        """
        channel = await self.db.get_channel(channel_id)
        if not channel:
            return None

        updates = {}

        # Get API details
        if self.youtube:
            details = await self.youtube.get_channel_details(channel_id)
            if details:
                updates.update(details)

        # Scrape About page for contacts
        about = await self.scraper.get_channel_about(channel_id)
        if about:
            if about.get('email'):
                updates['email'] = about['email']
            if about.get('business_email'):
                updates['business_email'] = about['business_email']
            if about.get('website'):
                updates['website'] = about['website']
            if about.get('instagram'):
                updates['instagram'] = about['instagram']
            if about.get('twitter'):
                updates['twitter'] = about['twitter']

        # Calculate analytics
        if self.youtube and updates.get('video_count', 0) > 0:
            videos = await self.youtube.get_channel_videos(channel_id, max_results=20)
            if videos:
                total_views = sum(v.get('views', 0) for v in videos)
                updates['avg_views_per_video'] = total_views // len(videos)

                # Most recent upload
                if videos[0].get('published_at'):
                    updates['last_upload_date'] = videos[0]['published_at']

        # Recalculate score
        merged = {**channel.to_dict(), **updates}
        score_result = self.scorer.calculate_score(merged)
        updates['lead_score'] = score_result['total_score']
        updates['tier'] = score_result['tier']

        # Update database
        await self.db.update_channel(channel_id, updates)

        return updates

    async def enrich_all_channels(self, limit: int = 100):
        """
        Enrich all channels that need updating
        """
        channels = await self.db.get_channels(limit=limit)

        console.print(f"Enriching {len(channels)} channels...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Enriching...", total=len(channels))

            for channel in channels:
                await self.enrich_channel(channel.youtube_channel_id)
                progress.update(task, advance=1)
                await asyncio.sleep(0.5)

        console.print("[green]Enrichment complete![/green]")
