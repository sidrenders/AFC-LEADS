"""
Lead Scoring System
Score channels based on multiple factors for lead qualification
"""
from typing import Dict, Optional
from datetime import datetime, timedelta

from config import SCORING_WEIGHTS, TARGET_NICHES, QUALIFICATION_CRITERIA


class LeadScorer:
    """
    Calculate lead scores based on channel metrics
    """

    TIERS = {
        'A': (80, 100),   # Hot leads
        'B': (60, 79),    # Warm leads
        'C': (40, 59),    # Cool leads
        'D': (0, 39)      # Low priority
    }

    def calculate_score(self, channel_data: Dict) -> Dict:
        """
        Calculate comprehensive lead score

        Args:
            channel_data: Dictionary with channel metrics

        Returns:
            Dict with component scores, total score, and tier
        """
        scores = {}

        # Size Score
        scores['size'] = self._score_size(
            channel_data.get('subscriber_count', 0)
        )

        # Engagement Score
        scores['engagement'] = self._score_engagement(
            channel_data.get('engagement_rate', 0),
            channel_data.get('avg_views_per_video', 0),
            channel_data.get('subscriber_count', 0)
        )

        # Growth Score (estimated without ViewStats)
        scores['growth'] = self._score_growth(
            channel_data.get('total_views', 0),
            channel_data.get('video_count', 0),
            channel_data.get('subscriber_count', 0)
        )

        # Niche Fit Score
        scores['niche_fit'] = self._score_niche_fit(
            channel_data.get('primary_niche'),
            channel_data.get('keywords', '')
        )

        # Activity Score
        scores['activity'] = self._score_activity(
            channel_data.get('last_upload_date'),
            channel_data.get('upload_frequency_days'),
            channel_data.get('video_count', 0)
        )

        # Contact Score
        scores['contact'] = self._score_contact(
            channel_data.get('email'),
            channel_data.get('business_email'),
            channel_data.get('website'),
            channel_data.get('instagram'),
            channel_data.get('twitter')
        )

        # Calculate weighted total
        total = sum(
            scores[key] * SCORING_WEIGHTS.get(key, 0.15)
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
        Sweet spot for creative agency: 10K - 500K
        """
        if subscribers < 1000:
            return 10
        elif subscribers < 5000:
            return 30
        elif subscribers < 10000:
            return 50
        elif subscribers < 50000:
            return 80  # Sweet spot - established but accessible
        elif subscribers < 100000:
            return 95  # Great - significant reach, still personal
        elif subscribers < 500000:
            return 100  # Ideal - major influence
        elif subscribers < 1000000:
            return 85  # Good but harder to reach
        elif subscribers < 5000000:
            return 70  # Large, likely has management
        else:
            return 50  # Very large, enterprise deals only

    def _score_engagement(
        self,
        engagement_rate: float,
        avg_views: int,
        subscribers: int
    ) -> int:
        """Score based on engagement metrics"""

        # If engagement rate is provided
        if engagement_rate and engagement_rate > 0:
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
                return 25

        # Fallback: estimate from views vs subscribers
        if avg_views and subscribers and subscribers > 0:
            view_ratio = avg_views / subscribers
            if view_ratio >= 0.5:
                return 95  # Excellent - videos get 50%+ of sub count
            elif view_ratio >= 0.3:
                return 80
            elif view_ratio >= 0.2:
                return 65
            elif view_ratio >= 0.1:
                return 50
            else:
                return 30

        return 40  # Default

    def _score_growth(
        self,
        total_views: int,
        video_count: int,
        subscribers: int
    ) -> int:
        """
        Estimate growth score without historical data
        Uses views-to-subscriber ratio as proxy
        """
        if not subscribers or subscribers == 0:
            return 30

        # Views per subscriber indicates channel health
        views_per_sub = total_views / subscribers if subscribers else 0

        if views_per_sub >= 200:
            return 95  # Viral content, high growth
        elif views_per_sub >= 100:
            return 80
        elif views_per_sub >= 50:
            return 65
        elif views_per_sub >= 20:
            return 50
        else:
            return 35

    def _score_niche_fit(self, niche: str, keywords: str) -> int:
        """Score based on niche relevance to agency targets"""

        if niche and niche in TARGET_NICHES:
            priority = TARGET_NICHES[niche].get('priority', 'low')
            if priority == 'high':
                return 95
            elif priority == 'medium':
                return 70
            else:
                return 45

        # Check keywords for niche match
        if keywords:
            keywords_lower = keywords.lower()
            for niche_name, niche_config in TARGET_NICHES.items():
                niche_keywords = niche_config.get('keywords', [])
                matches = sum(1 for kw in niche_keywords if kw.lower() in keywords_lower)
                if matches >= 2:
                    return 80
                elif matches >= 1:
                    return 60

        return 40  # Unknown niche

    def _score_activity(
        self,
        last_upload: datetime,
        upload_frequency_days: float,
        video_count: int
    ) -> int:
        """Score based on upload activity"""

        score = 50  # Base score

        # Last upload recency
        if last_upload:
            if isinstance(last_upload, str):
                try:
                    last_upload = datetime.fromisoformat(last_upload.replace('Z', '+00:00'))
                except ValueError:
                    last_upload = None

            if last_upload:
                days_since = (datetime.now(last_upload.tzinfo) - last_upload).days if last_upload.tzinfo else (datetime.utcnow() - last_upload).days

                if days_since <= 7:
                    score = 100  # Very active
                elif days_since <= 14:
                    score = 90
                elif days_since <= 30:
                    score = 75
                elif days_since <= 60:
                    score = 55
                elif days_since <= 90:
                    score = 40
                else:
                    score = 20  # Inactive

        # Upload frequency bonus
        if upload_frequency_days:
            if upload_frequency_days <= 3:
                score = min(100, score + 10)  # Multiple per week
            elif upload_frequency_days <= 7:
                score = min(100, score + 5)  # Weekly

        # Video count factor
        if video_count and video_count < 10:
            score = max(20, score - 20)  # New channel penalty

        return score

    def _score_contact(
        self,
        email: str,
        business_email: str,
        website: str,
        instagram: str,
        twitter: str
    ) -> int:
        """Score based on contact availability"""

        score = 0

        if business_email:
            score += 50  # Best - official business contact
        if email:
            score += 30
        if website:
            score += 10
        if instagram:
            score += 5
        if twitter:
            score += 5

        return min(100, score)

    def _determine_tier(self, score: float) -> str:
        """Assign tier based on total score"""
        for tier, (min_score, max_score) in self.TIERS.items():
            if min_score <= score <= max_score:
                return tier
        return 'D'

    def is_qualified(self, channel_data: Dict) -> bool:
        """
        Check if channel meets minimum qualification criteria
        """
        criteria = QUALIFICATION_CRITERIA

        subscribers = channel_data.get('subscriber_count', 0)
        if subscribers < criteria.get('min_subscribers', 0):
            return False
        if subscribers > criteria.get('max_subscribers', float('inf')):
            return False

        video_count = channel_data.get('video_count', 0)
        if video_count < criteria.get('min_videos', 0):
            return False

        avg_views = channel_data.get('avg_views_per_video', 0)
        if avg_views < criteria.get('min_avg_views', 0):
            return False

        return True


def score_channel(channel_data: Dict) -> Dict:
    """Convenience function to score a channel"""
    scorer = LeadScorer()
    return scorer.calculate_score(channel_data)
