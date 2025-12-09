"""
Configuration for YouTube Discovery MVP
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/discovery.db")

# Rate limiting
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", 30))
SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY_SECONDS", 2))

# Target niches - customize for your agency
TARGET_NICHES = {
    "tech": {
        "keywords": [
            "tech review", "gadget review", "software tutorial",
            "coding tutorial", "tech tips", "app review"
        ],
        "priority": "high"
    },
    "business": {
        "keywords": [
            "entrepreneur", "startup tips", "business advice",
            "marketing tips", "ecommerce", "side hustle"
        ],
        "priority": "high"
    },
    "education": {
        "keywords": [
            "how to", "tutorial", "explained", "learn",
            "course", "tips and tricks"
        ],
        "priority": "high"
    },
    "lifestyle": {
        "keywords": [
            "vlog", "day in my life", "routine", "lifestyle"
        ],
        "priority": "medium"
    },
    "fitness": {
        "keywords": [
            "workout", "fitness routine", "gym", "health tips"
        ],
        "priority": "medium"
    }
}

# Qualification criteria
QUALIFICATION_CRITERIA = {
    "min_subscribers": 5000,
    "max_subscribers": 5000000,
    "min_videos": 10,
    "min_avg_views": 1000,
    "max_days_since_upload": 60,  # Must be active
}

# Lead scoring weights
SCORING_WEIGHTS = {
    "size": 0.15,
    "engagement": 0.25,
    "growth": 0.20,
    "niche_fit": 0.15,
    "activity": 0.15,
    "contact": 0.10
}
