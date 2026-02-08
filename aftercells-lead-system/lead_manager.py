#!/usr/bin/env python3
"""
Aftercells Lead Manager - Python API for managing leads in Airtable

This is the foundation for your future AI systems. Use these functions to:
- Add new channel leads
- Update tiers and outreach status
- Query leads by tier, niche, or status
- Log outreach activities
- Get pipeline stats

Usage:
    from lead_manager import LeadManager
    lm = LeadManager()

    # Add a new lead
    lm.add_channel(
        name="ColdFusion",
        url="https://www.youtube.com/@ColdFusion",
        niche="Tech & Innovation",
        subscribers=5000000,
    )

    # Get all Tier A leads
    tier_a = lm.get_channels_by_tier("A")

    # Get pipeline stats
    stats = lm.get_pipeline_stats()
"""

import os
from datetime import datetime
from dotenv import load_dotenv

try:
    from pyairtable import Api, formulas
    from pyairtable.formulas import FIELD, STR_VALUE, match
except ImportError:
    print("Install pyairtable: pip install pyairtable")
    raise

load_dotenv()


class LeadManager:
    """Main interface for managing Aftercells leads in Airtable."""

    VALID_NICHES = [
        "Explainer",
        "Documentary",
        "True Crime / Mystery",
        "History & Politics",
        "Science & Space",
        "Nature & Geo",
        "Tech & Innovation",
        "Finance & Business",
        "3D Animated Storytelling",
    ]

    VALID_TIERS = ["A", "B", "C", "D"]

    VALID_OUTREACH_STATUSES = [
        "New Lead",
        "Researching",
        "Ready to Reach Out",
        "Contacted",
        "In Conversation",
        "Proposal Sent",
        "Won - Active Client",
        "Lost",
        "Not a Fit",
    ]

    VALID_MODELS = ["Salt", "Full Meal", "Both", "Undecided"]

    def __init__(self, token=None, base_id=None):
        self.token = token or os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
        self.base_id = base_id or os.getenv("AIRTABLE_BASE_ID")

        if not self.token or not self.base_id:
            raise ValueError(
                "Missing AIRTABLE_PERSONAL_ACCESS_TOKEN or AIRTABLE_BASE_ID. "
                "Set them in .env or pass directly."
            )

        self.api = Api(self.token)
        self.base = self.api.base(self.base_id)
        self.channels_table = self.base.table("Channels")
        self.outreach_table = self.base.table("Outreach Log")
        self.projects_table = self.base.table("Projects")

    # =========================================================================
    # CHANNEL / LEAD OPERATIONS
    # =========================================================================

    def add_channel(
        self,
        name,
        url,
        niche,
        subscribers=None,
        email=None,
        # Gate checks
        active=True,
        long_form=True,
        english=True,
        idea_led=True,
        no_custom_style=True,
        storytelling=True,
        # Video insights
        uses_3d=False,
        uses_motion_graphics=False,
        uses_stock=False,
        # Negative insights
        filmed_primary=False,
        facecam_primary=False,
        # Channel insights
        has_sponsors=False,
        has_patreon=False,
        has_product=False,
        consistent_branding=False,
        # Outreach
        model_fit="Undecided",
        tier=None,
        notes="",
        sample_video_url=None,
    ):
        """Add a new channel lead to the system."""

        fields = {
            "Channel Name": name,
            "Channel URL": url,
            "Primary Niche": niche,
            "GATE: Active Channel": active,
            "GATE: Long Form Content": long_form,
            "GATE: English Speaking": english,
            "GATE: Idea-Led Content": idea_led,
            "GATE: No Distinct Custom Style": no_custom_style,
            "GATE: Storytelling/Docs/Explainer": storytelling,
            "Uses 3D": uses_3d,
            "Uses Motion Graphics / 2D": uses_motion_graphics,
            "Uses Stock Footage / Photo": uses_stock,
            "NEG: Filmed Footage Primary": filmed_primary,
            "NEG: Face Cam / Personality Primary": facecam_primary,
            "Has Sponsors": has_sponsors,
            "Has Patreon / Membership": has_patreon,
            "Has Product": has_product,
            "Consistent Branding": consistent_branding,
            "Model Fit": model_fit,
            "Outreach Status": "New Lead",
            "Date Added": datetime.now().strftime("%Y-%m-%d"),
        }

        if subscribers:
            fields["Subscriber Count"] = subscribers
        if email:
            fields["Contact Email"] = email
        if tier:
            fields["Tier"] = tier
        if notes:
            fields["Discovery Notes"] = notes
        if sample_video_url:
            fields["Sample Video URL"] = sample_video_url

        record = self.channels_table.create(fields)
        print(f"Added lead: {name} (ID: {record['id']})")
        return record

    def get_all_channels(self):
        """Get all channel leads."""
        return self.channels_table.all()

    def get_channels_by_tier(self, tier):
        """Get channels by tier (A, B, C, or D)."""
        formula = match({"Tier": tier})
        return self.channels_table.all(formula=formula)

    def get_channels_by_niche(self, niche):
        """Get channels by niche category."""
        formula = match({"Primary Niche": niche})
        return self.channels_table.all(formula=formula)

    def get_channels_by_status(self, status):
        """Get channels by outreach status."""
        formula = match({"Outreach Status": status})
        return self.channels_table.all(formula=formula)

    def get_channels_passing_gate(self):
        """Get all channels that pass the gate check."""
        formula = "({Passes Gate} = 'YES')"
        return self.channels_table.all(formula=formula)

    def get_channels_with_hiring_signal(self):
        """Get channels showing hiring signals (great for Full Meal pitch)."""
        formula = "({Hiring Signal} = TRUE())"
        return self.channels_table.all(formula=formula)

    def update_channel(self, record_id, fields):
        """Update a channel record. Pass a dict of field_name: value."""
        return self.channels_table.update(record_id, fields)

    def set_tier(self, record_id, tier):
        """Set the tier for a channel."""
        return self.update_channel(record_id, {"Tier": tier})

    def set_outreach_status(self, record_id, status):
        """Update the outreach status of a channel."""
        return self.update_channel(record_id, {"Outreach Status": status})

    def set_model_fit(self, record_id, model):
        """Set whether the channel is a Salt, Full Meal, or Both fit."""
        return self.update_channel(record_id, {"Model Fit": model})

    # =========================================================================
    # OUTREACH LOG OPERATIONS
    # =========================================================================

    def log_outreach(
        self,
        channel_record_id,
        outreach_type,
        direction,
        summary,
        message="",
        follow_up_date=None,
    ):
        """Log an outreach activity for a channel."""
        fields = {
            "Channel": [channel_record_id],
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Type": outreach_type,
            "Direction": direction,
            "Subject / Summary": summary,
        }

        if message:
            fields["Message / Notes"] = message
        if follow_up_date:
            fields["Follow-Up Date"] = follow_up_date

        return self.outreach_table.create(fields)

    def get_outreach_for_channel(self, channel_record_id):
        """Get all outreach logs for a specific channel."""
        formula = f"FIND('{channel_record_id}', ARRAYJOIN({{Channel}}))"
        return self.outreach_table.all(formula=formula)

    def get_pending_followups(self):
        """Get all outreach entries where follow-up date is today or past."""
        today = datetime.now().strftime("%Y-%m-%d")
        formula = f"AND({{Follow-Up Date}} <= '{today}', {{Response Received}} = FALSE())"
        return self.outreach_table.all(formula=formula)

    # =========================================================================
    # PROJECT OPERATIONS
    # =========================================================================

    def create_project(
        self,
        name,
        channel_record_id,
        model,
        services,
        budget=None,
        deadline=None,
    ):
        """Create a new project for a client channel."""
        fields = {
            "Project Name": name,
            "Channel": [channel_record_id],
            "Model": model,
            "Status": "Scoping",
            "Services": services,
        }

        if budget:
            fields["Budget"] = budget
        if deadline:
            fields["Deadline"] = deadline

        return self.projects_table.create(fields)

    # =========================================================================
    # ANALYTICS / STATS
    # =========================================================================

    def get_pipeline_stats(self):
        """Get a summary of your lead pipeline."""
        all_channels = self.get_all_channels()

        stats = {
            "total_leads": len(all_channels),
            "by_tier": {"A": 0, "B": 0, "C": 0, "D": 0, "Unset": 0},
            "by_status": {},
            "by_niche": {},
            "passes_gate": 0,
            "fails_gate": 0,
            "by_model": {"Salt": 0, "Full Meal": 0, "Both": 0, "Undecided": 0},
        }

        for record in all_channels:
            fields = record["fields"]

            # Tier
            tier = fields.get("Tier", "Unset")
            if tier in stats["by_tier"]:
                stats["by_tier"][tier] += 1
            else:
                stats["by_tier"]["Unset"] += 1

            # Status
            status = fields.get("Outreach Status", "Unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            # Niche
            niche = fields.get("Primary Niche", "Unknown")
            stats["by_niche"][niche] = stats["by_niche"].get(niche, 0) + 1

            # Gate
            if fields.get("Passes Gate") == "YES":
                stats["passes_gate"] += 1
            else:
                stats["fails_gate"] += 1

            # Model
            model = fields.get("Model Fit", "Undecided")
            if model in stats["by_model"]:
                stats["by_model"][model] += 1

        return stats

    def print_pipeline_stats(self):
        """Print a formatted pipeline summary."""
        stats = self.get_pipeline_stats()

        print("\n" + "=" * 50)
        print("  AFTERCELLS LEAD PIPELINE STATS")
        print("=" * 50)
        print(f"\n  Total Leads: {stats['total_leads']}")
        print(f"  Passes Gate: {stats['passes_gate']}")
        print(f"  Fails Gate: {stats['fails_gate']}")

        print(f"\n  BY TIER:")
        for tier, count in stats["by_tier"].items():
            bar = "#" * count
            print(f"    Tier {tier}: {count} {bar}")

        print(f"\n  BY OUTREACH STATUS:")
        for status, count in stats["by_status"].items():
            print(f"    {status}: {count}")

        print(f"\n  BY NICHE:")
        for niche, count in sorted(stats["by_niche"].items(), key=lambda x: -x[1]):
            print(f"    {niche}: {count}")

        print(f"\n  BY MODEL FIT:")
        for model, count in stats["by_model"].items():
            print(f"    {model}: {count}")

        print()


# =============================================================================
# Quick CLI usage
# =============================================================================

if __name__ == "__main__":
    import sys

    lm = LeadManager()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "stats":
            lm.print_pipeline_stats()

        elif cmd == "tier":
            tier = sys.argv[2] if len(sys.argv) > 2 else "A"
            channels = lm.get_channels_by_tier(tier)
            print(f"\nTier {tier} channels ({len(channels)}):")
            for ch in channels:
                f = ch["fields"]
                print(f"  - {f.get('Channel Name', '?')} ({f.get('Subscriber Count', '?')} subs)")

        elif cmd == "followups":
            followups = lm.get_pending_followups()
            print(f"\nPending follow-ups ({len(followups)}):")
            for f in followups:
                fields = f["fields"]
                print(f"  - {fields.get('Subject / Summary', '?')} (due: {fields.get('Follow-Up Date', '?')})")

        else:
            print("Commands: stats, tier [A/B/C/D], followups")
    else:
        print("Aftercells Lead Manager")
        print("Commands: stats, tier [A/B/C/D], followups")
        print("Or import and use as a Python library.")
