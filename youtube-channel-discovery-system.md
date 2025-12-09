# YouTube Channel Discovery System
## Lead Generation Tool for Creative Agency

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         YOUTUBE CHANNEL DISCOVERY ENGINE                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │   SEED DB    │───▶│  DISCOVERY       │───▶│  ENRICHMENT & SCORING        │  │
│  │  2000+ Leads │    │  ENGINE          │    │  PIPELINE                    │  │
│  └──────────────┘    └──────────────────┘    └──────────────────────────────┘  │
│         │                    │                           │                      │
│         ▼                    ▼                           ▼                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │ Channel IDs  │    │ • YouTube API    │    │ • ViewStats Analytics        │  │
│  │ Video URLs   │    │ • Recommendations│    │ • Contact Extraction         │  │
│  │ Keywords     │    │ • Similar Finder │    │ • Lead Scoring               │  │
│  │ Niches       │    │ • Keyword Search │    │ • Qualification              │  │
│  └──────────────┘    └──────────────────┘    └──────────────────────────────┘  │
│                                                          │                      │
│                                                          ▼                      │
│                              ┌──────────────────────────────────────────────┐  │
│                              │           QUALIFIED LEADS DATABASE           │  │
│                              │  • Channel Info  • Analytics  • Contact      │  │
│                              │  • Lead Score    • Status     • Notes        │  │
│                              └──────────────────────────────────────────────┘  │
│                                                          │                      │
│                                                          ▼                      │
│                              ┌──────────────────────────────────────────────┐  │
│                              │              EXPORT / CRM SYNC               │  │
│                              │     CSV • JSON • HubSpot • Salesforce        │  │
│                              └──────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Architecture

### 1.1 Database Schema

```sql
-- Core Tables

CREATE TABLE channels (
    id                  UUID PRIMARY KEY,
    youtube_channel_id  VARCHAR(24) UNIQUE NOT NULL,
    channel_name        VARCHAR(255),
    channel_url         VARCHAR(500),
    handle              VARCHAR(100),          -- @handle

    -- Basic Stats
    subscriber_count    BIGINT,
    total_views         BIGINT,
    video_count         INTEGER,
    joined_date         DATE,
    country             VARCHAR(50),

    -- Niche Classification
    primary_niche       VARCHAR(100),
    secondary_niches    TEXT[],                -- Array of niches
    keywords            TEXT[],                -- Extracted keywords

    -- Source Tracking
    discovery_source    VARCHAR(50),           -- 'seed', 'recommendation', 'search', 'similar'
    seed_channel_id     UUID REFERENCES channels(id),  -- Parent channel if discovered

    -- Timestamps
    discovered_at       TIMESTAMP DEFAULT NOW(),
    last_updated        TIMESTAMP,

    -- Status
    status              VARCHAR(20) DEFAULT 'new'  -- new, qualified, contacted, converted, rejected
);

CREATE TABLE channel_analytics (
    id                  UUID PRIMARY KEY,
    channel_id          UUID REFERENCES channels(id),

    -- ViewStats Data
    avg_views_per_video BIGINT,
    views_30d           BIGINT,
    views_90d           BIGINT,
    subscriber_growth_30d INTEGER,
    subscriber_growth_90d INTEGER,
    engagement_rate     DECIMAL(5,2),
    upload_frequency    VARCHAR(50),           -- 'daily', 'weekly', 'monthly'

    -- Performance Metrics
    top_video_views     BIGINT,
    avg_likes_per_video INTEGER,
    avg_comments_per_video INTEGER,

    -- Trends
    growth_trend        VARCHAR(20),           -- 'rising', 'stable', 'declining'
    viral_potential     DECIMAL(5,2),

    recorded_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE channel_contacts (
    id                  UUID PRIMARY KEY,
    channel_id          UUID REFERENCES channels(id),

    -- Contact Info
    email               VARCHAR(255),
    email_verified      BOOLEAN DEFAULT FALSE,
    business_email      VARCHAR(255),          -- From YouTube About page

    -- Social Links
    instagram           VARCHAR(255),
    twitter             VARCHAR(255),
    tiktok              VARCHAR(255),
    website             VARCHAR(500),

    -- Business Info
    has_business_inquiries BOOLEAN,
    management_company   VARCHAR(255),

    extracted_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE lead_scores (
    id                  UUID PRIMARY KEY,
    channel_id          UUID REFERENCES channels(id),

    -- Scoring Components (0-100 each)
    size_score          INTEGER,               -- Based on subscribers
    engagement_score    INTEGER,               -- Based on engagement rate
    growth_score        INTEGER,               -- Based on growth trend
    niche_fit_score     INTEGER,               -- Based on target niches
    activity_score      INTEGER,               -- Based on upload frequency
    contact_score       INTEGER,               -- Based on contact availability

    -- Final Score
    total_score         INTEGER,               -- Weighted combination
    qualification_tier  VARCHAR(10),           -- 'A', 'B', 'C', 'D'

    calculated_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE discovery_jobs (
    id                  UUID PRIMARY KEY,
    job_type            VARCHAR(50),           -- 'keyword_search', 'similar_channels', 'recommendations'
    parameters          JSONB,
    status              VARCHAR(20),           -- 'pending', 'running', 'completed', 'failed'
    channels_found      INTEGER DEFAULT 0,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    error_message       TEXT
);

CREATE TABLE videos (
    id                  UUID PRIMARY KEY,
    youtube_video_id    VARCHAR(11) UNIQUE NOT NULL,
    channel_id          UUID REFERENCES channels(id),
    title               VARCHAR(500),
    views               BIGINT,
    likes               INTEGER,
    comments            INTEGER,
    published_at        TIMESTAMP,
    duration_seconds    INTEGER,
    tags                TEXT[]
);

-- Indexes for performance
CREATE INDEX idx_channels_niche ON channels(primary_niche);
CREATE INDEX idx_channels_subscribers ON channels(subscriber_count);
CREATE INDEX idx_channels_status ON channels(status);
CREATE INDEX idx_lead_scores_total ON lead_scores(total_score DESC);
CREATE INDEX idx_analytics_growth ON channel_analytics(growth_trend);
```

### 1.2 Target Niche Configuration

```python
# config/niches.py

TARGET_NICHES = {
    "tech": {
        "keywords": ["tech review", "gadgets", "software", "coding", "programming"],
        "min_subscribers": 5000,
        "max_subscribers": 5000000,
        "priority": "high"
    },
    "business": {
        "keywords": ["entrepreneur", "startup", "business tips", "marketing", "ecommerce"],
        "min_subscribers": 10000,
        "max_subscribers": 2000000,
        "priority": "high"
    },
    "lifestyle": {
        "keywords": ["lifestyle", "vlog", "day in my life", "routine"],
        "min_subscribers": 20000,
        "max_subscribers": 3000000,
        "priority": "medium"
    },
    "education": {
        "keywords": ["tutorial", "how to", "learn", "course", "explained"],
        "min_subscribers": 5000,
        "max_subscribers": 2000000,
        "priority": "high"
    },
    "fitness": {
        "keywords": ["workout", "fitness", "gym", "health", "nutrition"],
        "min_subscribers": 10000,
        "max_subscribers": 2000000,
        "priority": "medium"
    }
}

QUALIFICATION_CRITERIA = {
    "min_subscribers": 5000,
    "max_subscribers": 10000000,
    "min_avg_views": 1000,
    "min_videos": 10,
    "max_days_since_upload": 30,  # Must be active
    "min_engagement_rate": 2.0,   # Percentage
    "excluded_countries": [],
    "required_contact": True       # Must have discoverable contact
}
```

---

## Phase 2: Discovery Engine Components

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DISCOVERY ENGINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        DISCOVERY STRATEGIES                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │   │
│  │  │   STRATEGY   │  │   STRATEGY   │  │   STRATEGY   │  │STRATEGY │ │   │
│  │  │      1       │  │      2       │  │      3       │  │    4    │ │   │
│  │  │              │  │              │  │              │  │         │ │   │
│  │  │   Keyword    │  │   Similar    │  │    Video     │  │  Niche  │ │   │
│  │  │   Search     │  │   Channels   │  │   Recom.     │  │ Crawl   │ │   │
│  │  │              │  │              │  │              │  │         │ │   │
│  │  │ YouTube API  │  │  3rd Party   │  │   Scraper    │  │ Hybrid  │ │   │
│  │  │  + Apify     │  │    APIs      │  │              │  │         │ │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬────┘ │   │
│  │         │                 │                 │                │      │   │
│  │         └─────────────────┴────────┬────────┴────────────────┘      │   │
│  │                                    │                                 │   │
│  └────────────────────────────────────┼─────────────────────────────────┘   │
│                                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      DEDUPLICATION LAYER                             │   │
│  │         Check youtube_channel_id against existing database           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                       │                                      │
│                                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       RAW CHANNELS QUEUE                             │   │
│  │                    (Redis/PostgreSQL Queue)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Discovery Strategy Implementations

```python
# discovery/strategies.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import asyncio

class DiscoveryStrategy(ABC):
    """Base class for all discovery strategies"""

    @abstractmethod
    async def discover(self, params: Dict[str, Any]) -> List[Dict]:
        """Return list of discovered channel data"""
        pass


class KeywordSearchStrategy(DiscoveryStrategy):
    """
    Strategy 1: YouTube API + Apify keyword search
    Best for: Finding channels in specific niches
    """

    def __init__(self, youtube_api, apify_client):
        self.youtube_api = youtube_api
        self.apify_client = apify_client

    async def discover(self, params: Dict[str, Any]) -> List[Dict]:
        keywords = params.get('keywords', [])
        min_subs = params.get('min_subscribers', 5000)
        max_subs = params.get('max_subscribers', 5000000)

        channels = []

        # Method A: YouTube Data API (free, limited)
        for keyword in keywords:
            api_results = await self.youtube_api.search_channels(
                query=keyword,
                max_results=50,  # API limit
                order='viewCount'
            )
            channels.extend(api_results)

        # Method B: Apify for scale (paid, unlimited)
        apify_results = await self.apify_client.run_actor(
            'scraper-engine/youtube-channel-finder',
            {
                'keywords': keywords,
                'minSubscribers': min_subs,
                'maxSubscribers': max_subs,
                'maxResults': 500
            }
        )
        channels.extend(apify_results)

        return self._deduplicate(channels)


class SimilarChannelsStrategy(DiscoveryStrategy):
    """
    Strategy 2: Find channels similar to seed channels
    Best for: Expanding from your 2000+ existing leads
    """

    def __init__(self, channel_crawler_api, niche_prowler_api):
        self.channel_crawler = channel_crawler_api
        self.niche_prowler = niche_prowler_api

    async def discover(self, params: Dict[str, Any]) -> List[Dict]:
        seed_channel_ids = params.get('seed_channel_ids', [])

        channels = []

        for seed_id in seed_channel_ids:
            # ChannelCrawler API - 160M+ channel database
            similar = await self.channel_crawler.find_similar(
                channel_id=seed_id,
                limit=20
            )
            for ch in similar:
                ch['discovery_source'] = 'similar'
                ch['seed_channel_id'] = seed_id
            channels.extend(similar)

            # NicheProwler for AI-based similarity
            ai_similar = await self.niche_prowler.find_similar(
                channel_url=f"https://youtube.com/channel/{seed_id}",
                limit=10
            )
            channels.extend(ai_similar)

        return self._deduplicate(channels)


class VideoRecommendationsStrategy(DiscoveryStrategy):
    """
    Strategy 3: Scrape YouTube video recommendations
    Best for: Finding channels YouTube's algorithm relates together
    """

    def __init__(self, scraper):
        self.scraper = scraper  # Playwright/Puppeteer based

    async def discover(self, params: Dict[str, Any]) -> List[Dict]:
        video_urls = params.get('video_urls', [])

        channels = []

        for video_url in video_urls:
            # Scrape the recommendations sidebar
            recommendations = await self.scraper.get_video_recommendations(
                video_url=video_url,
                max_recommendations=20
            )

            # Extract unique channels from recommended videos
            for rec in recommendations:
                channel_data = await self.scraper.extract_channel_from_video(rec['video_id'])
                channel_data['discovery_source'] = 'recommendation'
                channel_data['source_video'] = video_url
                channels.append(channel_data)

        return self._deduplicate(channels)


class NicheCrawlStrategy(DiscoveryStrategy):
    """
    Strategy 4: Comprehensive niche crawling
    Best for: Deep exploration of specific verticals
    """

    def __init__(self, youtube_api, apify_client, scraper):
        self.youtube_api = youtube_api
        self.apify_client = apify_client
        self.scraper = scraper

    async def discover(self, params: Dict[str, Any]) -> List[Dict]:
        niche_config = params.get('niche_config', {})

        channels = []

        # Step 1: Keyword variations
        base_keywords = niche_config.get('keywords', [])
        expanded_keywords = self._expand_keywords(base_keywords)

        # Step 2: Search with all keyword variations
        for kw in expanded_keywords:
            results = await self.youtube_api.search_channels(query=kw, max_results=50)
            channels.extend(results)

        # Step 3: Get top videos in niche and find their channels
        for kw in base_keywords:
            videos = await self.youtube_api.search_videos(
                query=kw,
                order='viewCount',
                max_results=100
            )
            for video in videos:
                ch = await self._get_channel_from_video(video['id'])
                if ch:
                    channels.append(ch)

        # Step 4: Follow recommendation chains
        sample_videos = [ch.get('recent_video_id') for ch in channels[:50] if ch.get('recent_video_id')]
        for video_id in sample_videos:
            recs = await self.scraper.get_video_recommendations(video_id, max_recommendations=10)
            for rec in recs:
                ch = await self._get_channel_from_video(rec['video_id'])
                if ch:
                    channels.append(ch)

        return self._deduplicate(channels)

    def _expand_keywords(self, keywords: List[str]) -> List[str]:
        """Generate keyword variations"""
        expanded = set(keywords)
        suffixes = ['tutorial', 'tips', 'guide', 'review', '2024', '2025', 'for beginners']

        for kw in keywords:
            for suffix in suffixes:
                expanded.add(f"{kw} {suffix}")

        return list(expanded)
```

### 2.3 Discovery Orchestrator

```python
# discovery/orchestrator.py

import asyncio
from datetime import datetime
from typing import List, Dict

class DiscoveryOrchestrator:
    """
    Main orchestrator that coordinates all discovery strategies
    and manages the discovery pipeline
    """

    def __init__(self, db, strategies: Dict[str, DiscoveryStrategy]):
        self.db = db
        self.strategies = strategies
        self.rate_limiter = RateLimiter()

    async def run_discovery_cycle(self, config: Dict) -> Dict:
        """Run a complete discovery cycle"""

        job = await self.db.create_job({
            'job_type': 'full_cycle',
            'parameters': config,
            'status': 'running',
            'started_at': datetime.utcnow()
        })

        results = {
            'total_discovered': 0,
            'new_channels': 0,
            'duplicates_skipped': 0,
            'strategies_run': []
        }

        try:
            # Strategy 1: Leverage existing seed database
            if config.get('use_seed_expansion', True):
                seed_results = await self._run_seed_expansion()
                results['strategies_run'].append({
                    'name': 'seed_expansion',
                    'channels_found': len(seed_results)
                })
                results['total_discovered'] += len(seed_results)

            # Strategy 2: Keyword search for target niches
            if config.get('keyword_search', True):
                keyword_results = await self._run_keyword_search(config.get('niches', []))
                results['strategies_run'].append({
                    'name': 'keyword_search',
                    'channels_found': len(keyword_results)
                })
                results['total_discovered'] += len(keyword_results)

            # Strategy 3: Video recommendations from top performers
            if config.get('recommendations', True):
                rec_results = await self._run_recommendations_crawl()
                results['strategies_run'].append({
                    'name': 'recommendations',
                    'channels_found': len(rec_results)
                })
                results['total_discovered'] += len(rec_results)

            # Update job status
            await self.db.update_job(job['id'], {
                'status': 'completed',
                'completed_at': datetime.utcnow(),
                'channels_found': results['total_discovered']
            })

        except Exception as e:
            await self.db.update_job(job['id'], {
                'status': 'failed',
                'error_message': str(e)
            })
            raise

        return results

    async def _run_seed_expansion(self) -> List[Dict]:
        """Expand from existing 2000+ seed channels"""

        # Get high-performing seed channels
        seed_channels = await self.db.get_channels(
            status='qualified',
            order_by='lead_score',
            limit=100
        )

        # Find similar channels for each seed
        strategy = self.strategies['similar_channels']
        all_similar = []

        for batch in self._batch(seed_channels, size=10):
            channel_ids = [ch['youtube_channel_id'] for ch in batch]
            similar = await strategy.discover({'seed_channel_ids': channel_ids})

            # Filter out existing channels
            new_channels = await self._filter_existing(similar)
            all_similar.extend(new_channels)

            # Save to database
            await self._save_channels(new_channels)

            # Rate limiting
            await self.rate_limiter.wait()

        return all_similar

    async def _run_keyword_search(self, niches: List[str]) -> List[Dict]:
        """Search for channels by niche keywords"""

        strategy = self.strategies['keyword_search']
        all_channels = []

        for niche in niches:
            niche_config = TARGET_NICHES.get(niche, {})
            channels = await strategy.discover({
                'keywords': niche_config.get('keywords', []),
                'min_subscribers': niche_config.get('min_subscribers', 5000),
                'max_subscribers': niche_config.get('max_subscribers', 5000000)
            })

            # Tag with niche
            for ch in channels:
                ch['primary_niche'] = niche

            new_channels = await self._filter_existing(channels)
            all_channels.extend(new_channels)
            await self._save_channels(new_channels)

        return all_channels

    async def _run_recommendations_crawl(self) -> List[Dict]:
        """Crawl video recommendations from top performers"""

        # Get recent top-performing videos from seed channels
        top_videos = await self.db.query("""
            SELECT v.youtube_video_id, v.views, c.primary_niche
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.views > 100000
            AND v.published_at > NOW() - INTERVAL '90 days'
            ORDER BY v.views DESC
            LIMIT 200
        """)

        strategy = self.strategies['video_recommendations']
        all_channels = []

        for batch in self._batch(top_videos, size=20):
            video_urls = [f"https://youtube.com/watch?v={v['youtube_video_id']}" for v in batch]
            channels = await strategy.discover({'video_urls': video_urls})

            new_channels = await self._filter_existing(channels)
            all_channels.extend(new_channels)
            await self._save_channels(new_channels)

            await asyncio.sleep(2)  # Be respectful

        return all_channels
```

---

## Phase 3: Enrichment Pipeline

### 3.1 Enrichment Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENRICHMENT PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  RAW CHANNEL                                                                 │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: Basic Info (YouTube API)                                    │   │
│  │  • Subscriber count, total views, video count                        │   │
│  │  • Channel description, keywords, country                            │   │
│  │  • Recent upload date, join date                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: Deep Analytics (ViewStats API)                              │   │
│  │  • 30/90 day growth trends                                           │   │
│  │  • Average views per video                                           │   │
│  │  • Engagement rate calculation                                       │   │
│  │  • Upload frequency analysis                                         │   │
│  │  • Viral potential score                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: Contact Extraction (Scraper)                                │   │
│  │  • Email from About page / description                               │   │
│  │  • Business inquiries email                                          │   │
│  │  • Social media links (Instagram, Twitter, TikTok)                   │   │
│  │  • Website URL                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: Niche Classification (AI/ML)                                │   │
│  │  • Primary niche detection from content                              │   │
│  │  • Secondary niche tags                                              │   │
│  │  • Content style classification                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 5: Lead Scoring                                                │   │
│  │  • Calculate component scores                                        │   │
│  │  • Apply weights                                                     │   │
│  │  • Assign qualification tier (A/B/C/D)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ENRICHED & SCORED LEAD                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Enrichment Implementation

```python
# enrichment/pipeline.py

class EnrichmentPipeline:
    """
    Multi-stage enrichment pipeline for discovered channels
    """

    def __init__(self, youtube_api, viewstats_api, scraper, classifier):
        self.youtube_api = youtube_api
        self.viewstats_api = viewstats_api
        self.scraper = scraper
        self.classifier = classifier

    async def enrich_channel(self, channel_id: str) -> Dict:
        """Full enrichment for a single channel"""

        result = {'channel_id': channel_id}

        # Step 1: Basic YouTube API data
        basic_info = await self._get_basic_info(channel_id)
        result['basic'] = basic_info

        # Step 2: ViewStats analytics
        analytics = await self._get_viewstats_analytics(channel_id)
        result['analytics'] = analytics

        # Step 3: Contact extraction
        contacts = await self._extract_contacts(channel_id)
        result['contacts'] = contacts

        # Step 4: Niche classification
        niche = await self._classify_niche(channel_id, basic_info)
        result['niche'] = niche

        # Step 5: Lead scoring
        score = self._calculate_lead_score(result)
        result['score'] = score

        return result

    async def _get_basic_info(self, channel_id: str) -> Dict:
        """Get basic channel info from YouTube API"""

        channel = await self.youtube_api.get_channel(
            channel_id,
            parts=['snippet', 'statistics', 'brandingSettings', 'contentDetails']
        )

        return {
            'name': channel['snippet']['title'],
            'description': channel['snippet']['description'],
            'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
            'total_views': int(channel['statistics'].get('viewCount', 0)),
            'video_count': int(channel['statistics'].get('videoCount', 0)),
            'country': channel['snippet'].get('country'),
            'joined_date': channel['snippet'].get('publishedAt'),
            'keywords': channel['brandingSettings'].get('channel', {}).get('keywords', ''),
            'custom_url': channel['snippet'].get('customUrl')
        }

    async def _get_viewstats_analytics(self, channel_id: str) -> Dict:
        """Get deep analytics from ViewStats API"""

        try:
            stats = await self.viewstats_api.get_channel_stats(channel_id)

            return {
                'avg_views_per_video': stats.get('averageViews'),
                'views_30d': stats.get('views30d'),
                'views_90d': stats.get('views90d'),
                'subscriber_growth_30d': stats.get('subscriberGrowth30d'),
                'subscriber_growth_90d': stats.get('subscriberGrowth90d'),
                'engagement_rate': stats.get('engagementRate'),
                'upload_frequency': self._calculate_upload_frequency(stats),
                'growth_trend': self._determine_growth_trend(stats),
                'viral_potential': stats.get('viralScore')
            }
        except Exception as e:
            # Fallback to calculated metrics
            return await self._calculate_analytics_fallback(channel_id)

    async def _extract_contacts(self, channel_id: str) -> Dict:
        """Extract contact information from channel"""

        contacts = {
            'email': None,
            'business_email': None,
            'instagram': None,
            'twitter': None,
            'tiktok': None,
            'website': None,
            'has_business_inquiries': False
        }

        # Scrape the About page
        about_data = await self.scraper.get_channel_about(channel_id)

        # Extract email from description
        if about_data.get('description'):
            emails = self._extract_emails(about_data['description'])
            if emails:
                contacts['email'] = emails[0]

        # Get business email if available
        if about_data.get('businessEmail'):
            contacts['business_email'] = about_data['businessEmail']
            contacts['has_business_inquiries'] = True

        # Extract social links
        for link in about_data.get('links', []):
            if 'instagram.com' in link:
                contacts['instagram'] = link
            elif 'twitter.com' in link or 'x.com' in link:
                contacts['twitter'] = link
            elif 'tiktok.com' in link:
                contacts['tiktok'] = link
            elif not any(social in link for social in ['youtube', 'facebook', 'linkedin']):
                contacts['website'] = link

        return contacts

    async def _classify_niche(self, channel_id: str, basic_info: Dict) -> Dict:
        """Classify channel into niches using AI"""

        # Get recent video titles for classification
        videos = await self.youtube_api.get_channel_videos(channel_id, max_results=20)
        video_titles = [v['title'] for v in videos]

        # Use classifier (could be OpenAI, local model, or rule-based)
        classification = await self.classifier.classify(
            channel_name=basic_info['name'],
            description=basic_info['description'],
            keywords=basic_info['keywords'],
            video_titles=video_titles
        )

        return {
            'primary_niche': classification['primary'],
            'secondary_niches': classification.get('secondary', []),
            'confidence': classification.get('confidence', 0)
        }
```

### 3.3 Lead Scoring System

```python
# scoring/lead_scorer.py

class LeadScorer:
    """
    Calculate lead scores based on multiple factors
    Scores range from 0-100, with tier assignments
    """

    WEIGHTS = {
        'size': 0.15,
        'engagement': 0.25,
        'growth': 0.20,
        'niche_fit': 0.15,
        'activity': 0.15,
        'contact': 0.10
    }

    TIERS = {
        'A': (80, 100),   # Hot leads - immediate outreach
        'B': (60, 79),    # Warm leads - priority follow-up
        'C': (40, 59),    # Cool leads - nurture
        'D': (0, 39)      # Low priority
    }

    def calculate_score(self, channel_data: Dict) -> Dict:
        """Calculate comprehensive lead score"""

        scores = {}

        # Size Score (subscriber-based)
        scores['size'] = self._score_size(channel_data['basic']['subscriber_count'])

        # Engagement Score
        scores['engagement'] = self._score_engagement(
            channel_data['analytics'].get('engagement_rate', 0)
        )

        # Growth Score
        scores['growth'] = self._score_growth(
            channel_data['analytics'].get('subscriber_growth_30d', 0),
            channel_data['analytics'].get('growth_trend', 'stable')
        )

        # Niche Fit Score
        scores['niche_fit'] = self._score_niche_fit(
            channel_data['niche']['primary_niche'],
            channel_data['niche'].get('confidence', 0)
        )

        # Activity Score
        scores['activity'] = self._score_activity(
            channel_data['analytics'].get('upload_frequency', 'monthly')
        )

        # Contact Availability Score
        scores['contact'] = self._score_contact(channel_data['contacts'])

        # Calculate weighted total
        total = sum(
            scores[key] * self.WEIGHTS[key]
            for key in scores
        )

        # Determine tier
        tier = self._determine_tier(total)

        return {
            'component_scores': scores,
            'total_score': round(total),
            'tier': tier
        }

    def _score_size(self, subscribers: int) -> int:
        """
        Score based on subscriber count
        Sweet spot: 10K - 500K (most responsive to partnerships)
        """
        if subscribers < 5000:
            return 20
        elif subscribers < 10000:
            return 40
        elif subscribers < 50000:
            return 70  # Sweet spot - small but established
        elif subscribers < 100000:
            return 90  # Sweet spot - growing influence
        elif subscribers < 500000:
            return 100  # Sweet spot - significant reach
        elif subscribers < 1000000:
            return 80  # Larger, might be harder to reach
        else:
            return 60  # Very large, likely have management

    def _score_engagement(self, engagement_rate: float) -> int:
        """Score based on engagement rate percentage"""
        if engagement_rate >= 10:
            return 100
        elif engagement_rate >= 5:
            return 85
        elif engagement_rate >= 3:
            return 70
        elif engagement_rate >= 2:
            return 55
        elif engagement_rate >= 1:
            return 40
        else:
            return 20

    def _score_growth(self, growth_30d: int, trend: str) -> int:
        """Score based on growth metrics"""
        base_score = 50

        # Growth rate bonus
        if growth_30d > 10000:
            base_score += 30
        elif growth_30d > 5000:
            base_score += 20
        elif growth_30d > 1000:
            base_score += 10

        # Trend modifier
        if trend == 'rising':
            base_score += 20
        elif trend == 'declining':
            base_score -= 20

        return min(100, max(0, base_score))

    def _score_niche_fit(self, niche: str, confidence: float) -> int:
        """Score based on niche relevance to agency's targets"""
        niche_priority = TARGET_NICHES.get(niche, {}).get('priority', 'low')

        priority_scores = {
            'high': 90,
            'medium': 70,
            'low': 40
        }

        base = priority_scores.get(niche_priority, 30)

        # Adjust by confidence
        return int(base * confidence) if confidence else base

    def _score_activity(self, frequency: str) -> int:
        """Score based on upload frequency"""
        frequency_scores = {
            'daily': 100,
            'multiple_weekly': 90,
            'weekly': 80,
            'biweekly': 60,
            'monthly': 40,
            'irregular': 20
        }
        return frequency_scores.get(frequency, 30)

    def _score_contact(self, contacts: Dict) -> int:
        """Score based on contact availability"""
        score = 0

        if contacts.get('business_email'):
            score += 50  # Best - official business contact
        if contacts.get('email'):
            score += 30
        if contacts.get('website'):
            score += 10
        if contacts.get('instagram') or contacts.get('twitter'):
            score += 10

        return min(100, score)

    def _determine_tier(self, score: int) -> str:
        """Assign tier based on total score"""
        for tier, (min_score, max_score) in self.TIERS.items():
            if min_score <= score <= max_score:
                return tier
        return 'D'
```

---

## Phase 4: API & Integration Layer

### 4.1 REST API Endpoints

```python
# api/routes.py

from fastapi import FastAPI, BackgroundTasks, Query
from typing import List, Optional

app = FastAPI(title="YouTube Channel Discovery API")

# ============== Discovery Endpoints ==============

@app.post("/api/v1/discovery/run")
async def run_discovery(
    background_tasks: BackgroundTasks,
    config: DiscoveryConfig
):
    """
    Start a discovery job

    Config options:
    - niches: List of target niches
    - use_seed_expansion: bool
    - keyword_search: bool
    - recommendations: bool
    """
    job_id = await create_discovery_job(config)
    background_tasks.add_task(run_discovery_pipeline, job_id, config)

    return {"job_id": job_id, "status": "started"}


@app.get("/api/v1/discovery/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get discovery job status and progress"""
    return await get_job(job_id)


@app.post("/api/v1/discovery/similar")
async def find_similar_channels(
    channel_ids: List[str],
    limit: int = 20
):
    """Find channels similar to provided channel IDs"""
    return await similar_channels_strategy.discover({
        'seed_channel_ids': channel_ids,
        'limit': limit
    })


# ============== Channel Endpoints ==============

@app.get("/api/v1/channels")
async def list_channels(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    niche: Optional[str] = None,
    min_score: Optional[int] = None,
    min_subscribers: Optional[int] = None,
    max_subscribers: Optional[int] = None,
    sort_by: str = "score",
    page: int = 1,
    per_page: int = 50
):
    """
    List discovered channels with filters
    """
    filters = {
        'status': status,
        'tier': tier,
        'niche': niche,
        'min_score': min_score,
        'min_subscribers': min_subscribers,
        'max_subscribers': max_subscribers
    }

    return await db.get_channels(
        filters=filters,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )


@app.get("/api/v1/channels/{channel_id}")
async def get_channel(channel_id: str):
    """Get full channel details with analytics and contacts"""
    return await db.get_channel_full(channel_id)


@app.post("/api/v1/channels/{channel_id}/enrich")
async def enrich_channel(channel_id: str, background_tasks: BackgroundTasks):
    """Trigger enrichment for a specific channel"""
    background_tasks.add_task(enrichment_pipeline.enrich_channel, channel_id)
    return {"status": "enrichment_started"}


@app.patch("/api/v1/channels/{channel_id}/status")
async def update_channel_status(channel_id: str, status: str):
    """Update channel status (new, qualified, contacted, converted, rejected)"""
    return await db.update_channel_status(channel_id, status)


# ============== Export Endpoints ==============

@app.post("/api/v1/export")
async def export_channels(
    format: str = Query(..., enum=["csv", "json", "xlsx"]),
    filters: ExportFilters = None
):
    """Export channels to various formats"""
    channels = await db.get_channels(filters=filters.dict() if filters else {})

    if format == "csv":
        return create_csv_export(channels)
    elif format == "json":
        return create_json_export(channels)
    elif format == "xlsx":
        return create_excel_export(channels)


# ============== Analytics Endpoints ==============

@app.get("/api/v1/analytics/summary")
async def get_analytics_summary():
    """Get overall discovery analytics"""
    return {
        "total_channels": await db.count_channels(),
        "by_tier": await db.count_by_tier(),
        "by_niche": await db.count_by_niche(),
        "by_status": await db.count_by_status(),
        "discovered_today": await db.count_discovered_today(),
        "avg_lead_score": await db.avg_lead_score()
    }


@app.get("/api/v1/analytics/niches")
async def get_niche_analytics():
    """Get analytics broken down by niche"""
    return await db.get_niche_analytics()
```

### 4.2 Scheduler Configuration

```python
# scheduler/jobs.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Daily discovery job - runs at 2 AM
scheduler.add_job(
    run_daily_discovery,
    CronTrigger(hour=2, minute=0),
    id='daily_discovery',
    name='Daily Channel Discovery',
    kwargs={
        'config': {
            'use_seed_expansion': True,
            'keyword_search': True,
            'recommendations': True,
            'niches': ['tech', 'business', 'education']
        }
    }
)

# Enrichment refresh - runs every 6 hours
scheduler.add_job(
    refresh_stale_enrichments,
    CronTrigger(hour='*/6'),
    id='enrichment_refresh',
    name='Refresh Stale Enrichments',
    kwargs={
        'max_age_days': 7,
        'batch_size': 100
    }
)

# Score recalculation - runs weekly
scheduler.add_job(
    recalculate_all_scores,
    CronTrigger(day_of_week='sun', hour=3),
    id='score_recalc',
    name='Weekly Score Recalculation'
)

# Data cleanup - runs monthly
scheduler.add_job(
    cleanup_old_data,
    CronTrigger(day=1, hour=4),
    id='monthly_cleanup',
    name='Monthly Data Cleanup'
)
```

---

## Phase 5: Implementation Roadmap

### Week 1-2: Foundation
- [ ] Set up PostgreSQL database with schema
- [ ] Create base project structure (FastAPI + async)
- [ ] Implement YouTube API client wrapper
- [ ] Set up authentication and API keys management
- [ ] Import existing 2000+ leads into seed database

### Week 3-4: Discovery Engine
- [ ] Implement KeywordSearchStrategy
- [ ] Implement SimilarChannelsStrategy (integrate ChannelCrawler/Apify)
- [ ] Implement VideoRecommendationsStrategy (Playwright scraper)
- [ ] Build DiscoveryOrchestrator
- [ ] Add deduplication layer

### Week 5-6: Enrichment Pipeline
- [ ] Integrate ViewStats API
- [ ] Build contact extraction scraper
- [ ] Implement niche classifier (rule-based + optional AI)
- [ ] Create LeadScorer with weighted algorithm
- [ ] Build enrichment queue system

### Week 7-8: API & Dashboard
- [ ] Complete REST API endpoints
- [ ] Build simple admin dashboard (React/Vue)
- [ ] Add export functionality (CSV, JSON, Excel)
- [ ] Implement CRM webhook integrations

### Week 9-10: Automation & Polish
- [ ] Set up scheduled discovery jobs
- [ ] Add monitoring and alerting
- [ ] Performance optimization
- [ ] Documentation and testing
- [ ] Deploy to production

---

## Cost Estimation

| Component | Service | Monthly Cost |
|-----------|---------|--------------|
| YouTube Data API | Google | Free (10K quota/day) |
| ViewStats API | ViewStats | ~$50-200 |
| Apify Actors | Apify | ~$49 (starter) |
| ChannelCrawler API | ChannelCrawler | ~$99 |
| Database | PostgreSQL (managed) | ~$20-50 |
| Server | VPS/Cloud | ~$40-100 |
| **Total Estimated** | | **~$250-500/month** |

---

## Quick Start Commands

```bash
# Clone and setup
git clone <repo>
cd youtube-discovery-system

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python -m alembic upgrade head

# Import seed data
python scripts/import_seeds.py --file your_2000_leads.csv

# Run discovery
python -m discovery.cli run --niches tech,business --seed-expansion

# Start API server
uvicorn api.main:app --reload
```
