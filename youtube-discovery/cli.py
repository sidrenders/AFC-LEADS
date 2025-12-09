#!/usr/bin/env python3
"""
YouTube Channel Discovery CLI
Test and run the discovery system from command line
"""
import asyncio
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import pandas as pd

app = typer.Typer(help="YouTube Channel Discovery Tool - Lead Generation for Creative Agencies")
console = Console()


def async_run(coro):
    """Run async function"""
    return asyncio.get_event_loop().run_until_complete(coro)


@app.command()
def init():
    """Initialize the database"""
    from config import DATABASE_URL
    from models.database import Database

    async def _init():
        # Ensure data directory exists
        Path("./data").mkdir(exist_ok=True)

        db = Database(DATABASE_URL)
        await db.init()
        console.print("[green]Database initialized successfully![/green]")

    async_run(_init())


@app.command()
def import_seeds(
    file: str = typer.Argument(..., help="Path to CSV or Excel file with your leads"),
    channel_column: Optional[str] = typer.Option(None, "--channel", "-c", help="Column name for channel URLs"),
    video_column: Optional[str] = typer.Option(None, "--video", "-v", help="Column name for video URLs"),
    name_column: Optional[str] = typer.Option(None, "--name", "-n", help="Column name for channel names"),
    no_enrich: bool = typer.Option(False, "--no-enrich", is_flag=True, help="Skip API enrichment (faster, uses no quota)")
):
    """
    Import your existing leads from CSV/Excel file

    Example:
        python cli.py import-seeds my_leads.csv --channel "Channel URL"
    """
    from config import DATABASE_URL, YOUTUBE_API_KEY
    from models.database import Database
    from api.youtube_client import YouTubeClient
    from utils.importer import SeedImporter

    async def _import():
        # Initialize
        Path("./data").mkdir(exist_ok=True)
        db = Database(DATABASE_URL)
        await db.init()

        youtube = None
        if not no_enrich and YOUTUBE_API_KEY:
            youtube = YouTubeClient(YOUTUBE_API_KEY)
            console.print("[dim]API enrichment enabled[/dim]")
        else:
            console.print("[dim]Running without API enrichment (no quota used)[/dim]")

        importer = SeedImporter(db, youtube)

        console.print(f"\n[bold]Importing from:[/bold] {file}")

        if file.endswith(('.xlsx', '.xls')):
            results = await importer.import_from_excel(
                file,
                channel_column=channel_column,
                video_column=video_column,
                name_column=name_column,
                enrich=not no_enrich
            )
        else:
            results = await importer.import_from_csv(
                file,
                channel_column=channel_column,
                video_column=video_column,
                name_column=name_column,
                enrich=not no_enrich
            )

        # Display results
        console.print("\n")
        console.print(Panel.fit(
            f"[green]Imported:[/green] {results['imported']}\n"
            f"[yellow]Duplicates:[/yellow] {results['skipped_duplicates']}\n"
            f"[red]Invalid:[/red] {results['skipped_invalid']}\n"
            f"[dim]Total rows:[/dim] {results['total_rows']}",
            title="Import Results"
        ))

        if youtube:
            quota = youtube.get_quota_usage()
            console.print(f"\n[dim]API quota used: {quota['used']}/10,000[/dim]")

    async_run(_import())


@app.command()
def discover(
    seeds: bool = typer.Option(True, "--seeds", help="Use seed expansion strategy"),
    no_seeds: bool = typer.Option(False, "--no-seeds", help="Skip seed expansion"),
    keywords: bool = typer.Option(True, "--keywords", help="Use keyword search strategy"),
    no_keywords: bool = typer.Option(False, "--no-keywords", help="Skip keyword search"),
    recommendations: bool = typer.Option(True, "--recs", help="Use recommendations strategy"),
    no_recs: bool = typer.Option(False, "--no-recs", help="Skip recommendations"),
    niches: Optional[str] = typer.Option(None, "--niches", help="Comma-separated niches (e.g., 'tech,business')"),
    limit: int = typer.Option(100, "--limit", help="Max channels per strategy")
):
    """
    Run channel discovery

    Example:
        python cli.py discover --niches tech,business --limit 50
    """
    from config import DATABASE_URL, YOUTUBE_API_KEY
    from models.database import Database
    from api.youtube_client import YouTubeClient
    from discovery.orchestrator import DiscoveryOrchestrator

    async def _discover():
        db = Database(DATABASE_URL)
        await db.init()

        youtube = YouTubeClient(YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

        if not youtube:
            console.print("[yellow]Warning: No API key. Using scraping only (slower but FREE)[/yellow]\n")

        orchestrator = DiscoveryOrchestrator(db, youtube)

        niche_list = niches.split(',') if niches else None

        results = await orchestrator.run_full_discovery(
            use_seeds=seeds and not no_seeds,
            use_keywords=keywords and not no_keywords,
            use_recommendations=recommendations and not no_recs,
            niches=niche_list,
            max_per_strategy=limit
        )

        return results

    async_run(_discover())


@app.command()
def test_scraper(
    channel_id: str = typer.Argument(..., help="YouTube channel ID to test scraping"),
):
    """
    Test the scraper on a single channel (FREE, no API)

    Example:
        python cli.py test-scraper UCBcRF18a7Qf58cCRy5xuWwQ
    """
    from scrapers.youtube_scraper import YouTubeScraper

    async def _test():
        scraper = YouTubeScraper()

        console.print(f"\n[bold]Testing scraper on channel:[/bold] {channel_id}\n")

        # Test featured channels
        console.print("[yellow]1. Getting featured channels...[/yellow]")
        featured = await scraper.get_featured_channels(channel_id)
        console.print(f"   Found {len(featured)} featured channels")
        for ch in featured[:5]:
            console.print(f"   - {ch.get('channel_name', 'Unknown')} ({ch.get('subscriber_count', 0):,} subs)")

        # Test about page
        console.print("\n[yellow]2. Getting contact info from About page...[/yellow]")
        about = await scraper.get_channel_about(channel_id)
        console.print(f"   Email: {about.get('email') or about.get('business_email') or 'Not found'}")
        console.print(f"   Website: {about.get('website') or 'Not found'}")
        console.print(f"   Instagram: {about.get('instagram') or 'Not found'}")
        console.print(f"   Links found: {len(about.get('links', []))}")

        console.print("\n[green]Scraper test complete![/green]")

    async_run(_test())


@app.command()
def test_api(
    query: str = typer.Argument("tech review", help="Search query to test"),
):
    """
    Test the YouTube API (uses quota)

    Example:
        python cli.py test-api "fitness tips"
    """
    from config import YOUTUBE_API_KEY
    from api.youtube_client import YouTubeClient

    if not YOUTUBE_API_KEY:
        console.print("[red]Error: YOUTUBE_API_KEY not set in .env[/red]")
        raise typer.Exit(1)

    async def _test():
        youtube = YouTubeClient(YOUTUBE_API_KEY)

        console.print(f"\n[bold]Testing YouTube API with query:[/bold] '{query}'\n")

        # Test search
        console.print("[yellow]1. Searching channels...[/yellow]")
        channels = await youtube.search_channels(query, max_results=5)
        console.print(f"   Found {len(channels)} channels")

        if channels:
            # Test channel details
            console.print("\n[yellow]2. Getting channel details...[/yellow]")
            details = await youtube.get_channel_details(channels[0]['youtube_channel_id'])
            if details:
                console.print(f"   Name: {details.get('channel_name')}")
                console.print(f"   Subscribers: {details.get('subscriber_count', 0):,}")
                console.print(f"   Videos: {details.get('video_count', 0)}")
                console.print(f"   Email: {details.get('email') or 'Not in description'}")

        quota = youtube.get_quota_usage()
        console.print(f"\n[dim]Quota used: {quota['used']}/10,000[/dim]")
        console.print("[green]API test complete![/green]")

    async_run(_test())


@app.command()
def list_channels(
    tier: Optional[str] = typer.Option(None, "--tier", "-t", help="Filter by tier (A/B/C/D)"),
    niche: Optional[str] = typer.Option(None, "--niche", "-n", help="Filter by niche"),
    min_subs: Optional[int] = typer.Option(None, "--min-subs", help="Minimum subscribers"),
    max_subs: Optional[int] = typer.Option(None, "--max-subs", help="Maximum subscribers"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of results"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export to file (csv/xlsx)")
):
    """
    List discovered channels with filters

    Example:
        python cli.py list-channels --tier A --limit 50
        python cli.py list-channels --niche tech --export leads.csv
    """
    from config import DATABASE_URL
    from models.database import Database

    async def _list():
        db = Database(DATABASE_URL)
        await db.init()

        channels = await db.get_channels(
            tier=tier,
            niche=niche,
            min_subscribers=min_subs,
            max_subscribers=max_subs,
            limit=limit
        )

        if not channels:
            console.print("[yellow]No channels found matching criteria[/yellow]")
            return

        # Create table
        table = Table(title=f"Discovered Channels ({len(channels)} results)")
        table.add_column("Name", style="cyan", max_width=30)
        table.add_column("Subs", justify="right")
        table.add_column("Score", justify="center")
        table.add_column("Tier", justify="center")
        table.add_column("Niche")
        table.add_column("Email", max_width=25)
        table.add_column("Source")

        for ch in channels:
            subs = f"{ch.subscriber_count:,}" if ch.subscriber_count else "-"
            tier_style = {"A": "green", "B": "yellow", "C": "white", "D": "dim"}.get(ch.tier, "white")

            table.add_row(
                ch.channel_name or "-",
                subs,
                str(ch.lead_score or 0),
                f"[{tier_style}]{ch.tier or '-'}[/{tier_style}]",
                ch.primary_niche or "-",
                ch.email or ch.business_email or "-",
                ch.discovery_source or "-"
            )

        console.print(table)

        # Export if requested
        if export:
            data = [ch.to_dict() for ch in channels]
            df = pd.DataFrame(data)

            if export.endswith('.xlsx'):
                df.to_excel(export, index=False)
            else:
                df.to_csv(export, index=False)

            console.print(f"\n[green]Exported to {export}[/green]")

    async_run(_list())


@app.command()
def stats():
    """
    Show database statistics
    """
    from config import DATABASE_URL
    from models.database import Database

    async def _stats():
        db = Database(DATABASE_URL)
        await db.init()

        stats = await db.get_stats()

        console.print("\n")
        console.print(Panel.fit(
            f"[bold]Total Channels:[/bold] {stats['total_channels']}\n\n"
            f"[bold]By Tier:[/bold]\n"
            + "\n".join(f"  {k or 'Unscored'}: {v}" for k, v in (stats.get('by_tier') or {}).items())
            + "\n\n[bold]By Source:[/bold]\n"
            + "\n".join(f"  {k or 'Unknown'}: {v}" for k, v in (stats.get('by_source') or {}).items()),
            title="Database Statistics"
        ))

    async_run(_stats())


@app.command()
def enrich(
    channel_id: Optional[str] = typer.Option(None, "--channel", "-c", help="Specific channel to enrich"),
    all_channels: bool = typer.Option(False, "--all", "-a", help="Enrich all channels"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max channels to enrich")
):
    """
    Enrich channels with additional data (contacts, analytics)

    Example:
        python cli.py enrich --all --limit 50
    """
    from config import DATABASE_URL, YOUTUBE_API_KEY
    from models.database import Database
    from api.youtube_client import YouTubeClient
    from discovery.orchestrator import DiscoveryOrchestrator

    async def _enrich():
        db = Database(DATABASE_URL)
        await db.init()

        youtube = YouTubeClient(YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None
        orchestrator = DiscoveryOrchestrator(db, youtube)

        if channel_id:
            console.print(f"Enriching channel: {channel_id}")
            result = await orchestrator.enrich_channel(channel_id)
            if result:
                console.print("[green]Enrichment complete![/green]")
                console.print(f"  Email: {result.get('email') or result.get('business_email') or 'Not found'}")
                console.print(f"  Score: {result.get('lead_score')} (Tier {result.get('tier')})")
        elif all_channels:
            await orchestrator.enrich_all_channels(limit=limit)
        else:
            console.print("[yellow]Specify --channel or --all[/yellow]")

    async_run(_enrich())


@app.command()
def quick_test():
    """
    Quick test to verify everything is working (no API key needed)
    """
    from scrapers.youtube_scraper import YouTubeScraper

    async def _test():
        console.print("\n[bold blue]Running Quick Test (FREE - No API Key Required)[/bold blue]\n")

        scraper = YouTubeScraper()

        # Test with a known channel (MKBHD)
        test_channel_id = "UCBJycsmduvYEL83R_U4JriQ"
        console.print(f"Testing with channel: MKBHD ({test_channel_id})")

        # Test 1: Featured channels
        console.print("\n[yellow]Test 1: Scraping featured channels...[/yellow]")
        try:
            featured = await scraper.get_featured_channels(test_channel_id)
            console.print(f"[green]SUCCESS![/green] Found {len(featured)} featured channels")
            if featured:
                console.print(f"  Sample: {featured[0].get('channel_name', 'Unknown')}")
        except Exception as e:
            console.print(f"[red]FAILED:[/red] {e}")

        # Test 2: About page
        console.print("\n[yellow]Test 2: Scraping About page...[/yellow]")
        try:
            about = await scraper.get_channel_about(test_channel_id)
            console.print(f"[green]SUCCESS![/green] Got about data")
            console.print(f"  Links found: {len(about.get('links', []))}")
        except Exception as e:
            console.print(f"[red]FAILED:[/red] {e}")

        # Test 3: Search scraping
        console.print("\n[yellow]Test 3: Scraping search results...[/yellow]")
        try:
            results = await scraper.get_channels_from_search_page("tech review", max_results=5)
            console.print(f"[green]SUCCESS![/green] Found {len(results)} channels")
            if results:
                console.print(f"  Sample: {results[0].get('channel_name', 'Unknown')}")
        except Exception as e:
            console.print(f"[red]FAILED:[/red] {e}")

        console.print("\n[bold green]Quick test complete![/bold green]")
        console.print("\nNext steps:")
        console.print("  1. Copy .env.example to .env")
        console.print("  2. Add your YouTube API key (optional, but recommended)")
        console.print("  3. Run: python cli.py init")
        console.print("  4. Run: python cli.py import-seeds your_leads.csv")
        console.print("  5. Run: python cli.py discover")

    async_run(_test())


if __name__ == "__main__":
    app()
