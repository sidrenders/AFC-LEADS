"""
Database models for YouTube Discovery MVP
Using SQLite for zero-cost, zero-setup testing
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import json

Base = declarative_base()


class Channel(Base):
    """Core channel data"""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_channel_id = Column(String(24), unique=True, nullable=False, index=True)
    channel_name = Column(String(255))
    channel_url = Column(String(500))
    handle = Column(String(100))  # @handle

    # Stats
    subscriber_count = Column(BigInteger, default=0)
    total_views = Column(BigInteger, default=0)
    video_count = Column(Integer, default=0)
    country = Column(String(50))

    # Niche
    primary_niche = Column(String(100))
    keywords = Column(Text)  # JSON array

    # Discovery tracking
    discovery_source = Column(String(50))  # 'seed', 'search', 'similar', 'recommendation'
    seed_channel_id = Column(String(24))   # Parent channel if discovered via similar/recommendation

    # Contact info
    email = Column(String(255))
    business_email = Column(String(255))
    website = Column(String(500))
    instagram = Column(String(255))
    twitter = Column(String(255))
    description = Column(Text)

    # Scoring
    lead_score = Column(Integer, default=0)
    tier = Column(String(1))  # A, B, C, D

    # Status
    status = Column(String(20), default='new')  # new, qualified, contacted, converted, rejected

    # Timestamps
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_upload_date = Column(DateTime)

    # Analytics (calculated)
    avg_views_per_video = Column(BigInteger)
    engagement_rate = Column(Float)
    upload_frequency_days = Column(Float)

    def to_dict(self):
        return {
            'id': self.id,
            'youtube_channel_id': self.youtube_channel_id,
            'channel_name': self.channel_name,
            'channel_url': self.channel_url,
            'handle': self.handle,
            'subscriber_count': self.subscriber_count,
            'total_views': self.total_views,
            'video_count': self.video_count,
            'country': self.country,
            'primary_niche': self.primary_niche,
            'discovery_source': self.discovery_source,
            'email': self.email,
            'business_email': self.business_email,
            'website': self.website,
            'lead_score': self.lead_score,
            'tier': self.tier,
            'status': self.status,
            'avg_views_per_video': self.avg_views_per_video,
            'engagement_rate': self.engagement_rate
        }


class Video(Base):
    """Video data for analytics"""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_video_id = Column(String(11), unique=True, nullable=False, index=True)
    channel_id = Column(String(24), ForeignKey('channels.youtube_channel_id'))
    title = Column(String(500))
    views = Column(BigInteger, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    published_at = Column(DateTime)
    duration_seconds = Column(Integer)

    discovered_at = Column(DateTime, default=datetime.utcnow)


class DiscoveryJob(Base):
    """Track discovery jobs"""
    __tablename__ = "discovery_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50))
    parameters = Column(Text)  # JSON
    status = Column(String(20), default='pending')
    channels_found = Column(Integer, default=0)
    channels_new = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)


class Database:
    """Database manager"""

    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init(self):
        """Create tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        return self.async_session()

    async def add_channel(self, channel_data: dict) -> Optional[Channel]:
        """Add a channel if it doesn't exist"""
        async with self.async_session() as session:
            from sqlalchemy import select

            # Check if exists
            result = await session.execute(
                select(Channel).where(
                    Channel.youtube_channel_id == channel_data['youtube_channel_id']
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                return None  # Already exists

            channel = Channel(**channel_data)
            session.add(channel)
            await session.commit()
            await session.refresh(channel)
            return channel

    async def update_channel(self, youtube_channel_id: str, data: dict):
        """Update channel data"""
        async with self.async_session() as session:
            from sqlalchemy import select, update

            await session.execute(
                update(Channel)
                .where(Channel.youtube_channel_id == youtube_channel_id)
                .values(**data)
            )
            await session.commit()

    async def get_channel(self, youtube_channel_id: str) -> Optional[Channel]:
        """Get a single channel"""
        async with self.async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Channel).where(
                    Channel.youtube_channel_id == youtube_channel_id
                )
            )
            return result.scalar_one_or_none()

    async def get_channels(
        self,
        status: str = None,
        tier: str = None,
        niche: str = None,
        min_subscribers: int = None,
        max_subscribers: int = None,
        discovery_source: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Channel]:
        """Get channels with filters"""
        async with self.async_session() as session:
            from sqlalchemy import select

            query = select(Channel)

            if status:
                query = query.where(Channel.status == status)
            if tier:
                query = query.where(Channel.tier == tier)
            if niche:
                query = query.where(Channel.primary_niche == niche)
            if min_subscribers:
                query = query.where(Channel.subscriber_count >= min_subscribers)
            if max_subscribers:
                query = query.where(Channel.subscriber_count <= max_subscribers)
            if discovery_source:
                query = query.where(Channel.discovery_source == discovery_source)

            query = query.order_by(Channel.lead_score.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return result.scalars().all()

    async def get_seed_channels(self, limit: int = 50) -> List[Channel]:
        """Get top seed channels for expansion"""
        async with self.async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Channel)
                .where(Channel.discovery_source == 'seed')
                .where(Channel.subscriber_count > 0)
                .order_by(Channel.lead_score.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def channel_exists(self, youtube_channel_id: str) -> bool:
        """Check if channel already exists"""
        async with self.async_session() as session:
            from sqlalchemy import select, func

            result = await session.execute(
                select(func.count()).select_from(Channel).where(
                    Channel.youtube_channel_id == youtube_channel_id
                )
            )
            return result.scalar() > 0

    async def get_stats(self) -> dict:
        """Get database statistics"""
        async with self.async_session() as session:
            from sqlalchemy import select, func

            total = await session.execute(select(func.count()).select_from(Channel))
            by_tier = await session.execute(
                select(Channel.tier, func.count())
                .group_by(Channel.tier)
            )
            by_source = await session.execute(
                select(Channel.discovery_source, func.count())
                .group_by(Channel.discovery_source)
            )

            return {
                'total_channels': total.scalar(),
                'by_tier': dict(by_tier.all()),
                'by_source': dict(by_source.all())
            }
