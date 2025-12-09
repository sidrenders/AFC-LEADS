# YouTube Channel Discovery Tool

**Free MVP for Lead Generation** - Find YouTube channels for your creative agency without expensive third-party services.

## Cost: $0 to Test

| Component | Cost |
|-----------|------|
| YouTube Data API | FREE (10,000 quota/day) |
| Custom Scraping | FREE (Playwright/httpx) |
| Database | FREE (SQLite) |
| **Total** | **$0** |

## Quick Start (5 minutes)

```bash
# 1. Install dependencies
cd youtube-discovery
pip install -r requirements.txt

# 2. Install Playwright browsers (for advanced scraping)
playwright install chromium

# 3. Copy environment file
cp .env.example .env

# 4. (Optional) Add YouTube API key to .env
# Get free key at: https://console.cloud.google.com/
# Enable "YouTube Data API v3"

# 5. Run quick test (no API key needed!)
python cli.py quick-test

# 6. Initialize database
python cli.py init

# 7. Import your existing leads
python cli.py import-seeds your_leads.csv

# 8. Run discovery
python cli.py discover --limit 50
```

## Features

### Discovery Strategies (All FREE with scraping)

1. **Seed Expansion** - Find channels similar to your existing 2000+ leads
2. **Keyword Search** - Search by niche keywords
3. **Video Recommendations** - Mine YouTube's recommendation algorithm

### Lead Scoring

Channels are automatically scored 0-100 and tiered:
- **Tier A (80-100)**: Hot leads - immediate outreach
- **Tier B (60-79)**: Warm leads - priority follow-up
- **Tier C (40-59)**: Cool leads - nurture
- **Tier D (0-39)**: Low priority

### Contact Extraction

Automatically extracts:
- Email addresses
- Business inquiry emails
- Website URLs
- Social media (Instagram, Twitter, TikTok)

## CLI Commands

```bash
# Import your leads
python cli.py import-seeds leads.csv
python cli.py import-seeds leads.xlsx --channel "Channel URL" --name "Name"

# Run discovery
python cli.py discover                           # All strategies
python cli.py discover --niches tech,business    # Specific niches
python cli.py discover --no-seeds --limit 50     # Keywords only

# View results
python cli.py list-channels                      # All channels
python cli.py list-channels --tier A             # Hot leads only
python cli.py list-channels --export leads.csv   # Export to file

# Test components
python cli.py quick-test                         # Test scraper (FREE)
python cli.py test-api "fitness"                 # Test API (uses quota)
python cli.py test-scraper UCxxx                 # Test on specific channel

# Enrich with contacts
python cli.py enrich --all --limit 100

# View stats
python cli.py stats
```

## API Quota Usage

YouTube API is FREE with 10,000 quota units/day:

| Operation | Quota Cost | Daily Limit |
|-----------|-----------|-------------|
| Search channels | 100 units | ~100 searches |
| Get channel details | 1 unit | ~10,000 lookups |
| Get videos | 1 unit | ~10,000 lookups |

**Pro tip**: Use `--no-enrich` flag to skip API and rely only on FREE scraping.

## Project Structure

```
youtube-discovery/
├── cli.py                 # Command line interface
├── config.py              # Configuration & niches
├── requirements.txt       # Dependencies
├── .env.example           # Environment template
├── api/
│   └── youtube_client.py  # YouTube Data API client
├── scrapers/
│   └── youtube_scraper.py # FREE custom scrapers
├── discovery/
│   └── orchestrator.py    # Discovery engine
├── models/
│   └── database.py        # SQLite database models
├── utils/
│   ├── importer.py        # CSV/Excel importer
│   └── scorer.py          # Lead scoring
└── data/
    └── discovery.db       # SQLite database (auto-created)
```

## Customizing Niches

Edit `config.py` to customize target niches:

```python
TARGET_NICHES = {
    "your_niche": {
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "priority": "high"  # high, medium, low
    }
}
```

## Without API Key (100% FREE)

The system works WITHOUT a YouTube API key using scraping:

```bash
# Run without API
python cli.py discover --no-seeds

# Scraping is slower but completely FREE
# No quota limits
# Works for: search, featured channels, recommendations, contacts
```

## Scaling Up Later

When you're ready to scale:

1. **ViewStats API** (~$50-200/mo) - Deep analytics
2. **Multiple API keys** - Rotate for more quota
3. **PostgreSQL** - Replace SQLite for production
4. **Redis** - Add job queuing

## Troubleshooting

**"Quota exceeded"**
- Wait until midnight Pacific time for quota reset
- Use `--no-enrich` to rely on scraping only

**"No channels found"**
- Make sure you've imported seed data first
- Try different keywords/niches

**"Scraping failed"**
- YouTube may have changed their HTML structure
- Try `playwright install chromium` to update browsers
