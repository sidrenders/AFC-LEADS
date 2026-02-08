# Aftercells Lead Management System - Setup Guide

## What This Is

A complete lead management system for Aftercells built on Airtable. It tracks YouTube creator leads through your entire pipeline: discovery → gate check → tier scoring → outreach → client.

## What You Get

### 3 Tables

1. **Channels** - Your main leads table. Every YouTube channel goes here.
2. **Outreach Log** - Track every email, DM, call with a lead. Linked to Channels.
3. **Projects** - When a lead becomes a client, track the project here.

### Auto-Calculated Fields

- **Passes Gate** - Auto YES/NO based on your 6 gate checks
- **Video Insights Count** - Auto-counts how many positive video signals (3D, 2D, stock)
- **Negative Insight Triggered** - Auto YES/NO if filmed footage or face cam is primary
- **Recommended Tier** - Auto-suggests A/B/C based on your scoring rules

### 14 Pre-Designed Views

Tier A, Tier B, Tier C, Tier D, Salt Fit, Full Meal Fit, Ready to Reach Out, In Pipeline, Won Clients, By Niche, Hiring Signals, and more.

---

## Setup (Step by Step)

### Step 1: Create Airtable Account

Go to [airtable.com](https://airtable.com) and sign up (free tier works to start).

### Step 2: Create a Personal Access Token

1. Go to: https://airtable.com/create/tokens
2. Click **"Create new token"**
3. Name it: `Aftercells Lead System`
4. **Scopes** - check these:
   - `data.records:read`
   - `data.records:write`
   - `schema.bases:read`
   - `schema.bases:write`
5. **Access** - select your workspace
6. Click **Create token**
7. **COPY THE TOKEN** (starts with `pat.`) - you won't see it again

### Step 3: Create an Empty Base

1. In Airtable, click **"+ Create"** → **"Start from scratch"**
2. Name it: `Aftercells Leads`
3. Open the base
4. Look at the URL: `https://airtable.com/appXXXXXXXXXXXXXX/...`
5. Copy the part starting with `app` - that's your **Base ID**

### Step 4: Configure Environment

```bash
cd aftercells-lead-system
cp .env.example .env
```

Edit `.env` and paste in your token and base ID:

```
AIRTABLE_PERSONAL_ACCESS_TOKEN=pat.your_actual_token_here
AIRTABLE_BASE_ID=appYourActualBaseId
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Run Setup

```bash
python setup_airtable.py
```

This creates all 3 tables with every field configured.

### Step 7: Create Views (Manual - 5 min)

The Airtable API doesn't support creating views, but it's easy to do manually:

1. Open your base in Airtable
2. Go to the **Channels** table
3. Click the **+** next to "Grid view" in the left sidebar
4. Create each view with the filters listed in the setup script output

**Key views to create first:**
- **Tier A - Hot Leads**: Filter where Tier = A
- **Tier B - Warm Leads**: Filter where Tier = B
- **Ready to Reach Out**: Filter where Outreach Status = "Ready to Reach Out"
- **In Pipeline**: Filter where Outreach Status is any of: Contacted, In Conversation, Proposal Sent

### Step 8: Delete the Default Table

Airtable creates a default "Table 1" - you can right-click it and delete it.

---

## How to Use It

### Adding a Lead (in Airtable UI)

1. Go to Channels table
2. Click the **+** row at the bottom
3. Fill in: Channel Name, Channel URL, Primary Niche
4. Check the 6 GATE boxes (the ones that apply)
5. Check Video Insights (uses 3D, uses 2D, uses stock)
6. Check Channel Insights (sponsors, patreon, product)
7. The **Passes Gate** and **Recommended Tier** fields auto-calculate
8. Set the **Tier** field based on the recommendation
9. Set **Model Fit** (Salt, Full Meal, Both, or Undecided)

### Adding a Lead (via Python - for future AI)

```python
from lead_manager import LeadManager

lm = LeadManager()

lm.add_channel(
    name="ColdFusion",
    url="https://www.youtube.com/@ColdFusion",
    niche="Tech & Innovation",
    subscribers=5000000,
    uses_3d=False,
    uses_motion_graphics=True,
    uses_stock=True,
    has_sponsors=True,
    consistent_branding=True,
    model_fit="Salt",
    notes="Great channel, uses lots of stock footage. Perfect salt candidate.",
)
```

### Getting Pipeline Stats

```bash
python lead_manager.py stats
```

Or in Python:

```python
lm = LeadManager()
lm.print_pipeline_stats()
```

### Logging Outreach

```python
lm.log_outreach(
    channel_record_id="recXXXXXXXXXX",  # from the channel record
    outreach_type="Email",
    direction="Outbound (we reached out)",
    summary="Initial pitch - Salt model for hook sequences",
    message="Full email text here...",
    follow_up_date="2026-02-15",
)
```

---

## The Lead Flow

```
Discovery → Gate Check → Tier Sort → Model Fit → Outreach → Client
```

### Gate (Must Pass ALL)
- [ ] Active channel (posted in last 5 months)
- [ ] Long form content (>= 10 min)
- [ ] English speaking
- [ ] Idea-led content (can't be filmed)
- [ ] No locked-in custom style
- [ ] Storytelling / docs / explainer content

### Tier Scoring
- **A**: 2+ video insights OR 3D, no negative insights, has sponsors, consistent branding
- **B**: 1+ video insights OR 3D, no negative insights
- **C**: Only 1 video insight OR negative insight triggered
- **D**: Manual review (new channels, edge cases)

### Model Fit
- **Salt**: They have a team, just need 3D/MG as a premium addon for hooks
- **Full Meal**: We produce the entire video (script from them)

---

## Future AI Integration

The `lead_manager.py` module is designed as the foundation for AI systems:

```python
# Example: Auto-score channels from YouTube API data
from lead_manager import LeadManager

lm = LeadManager()

# Your future AI can:
# 1. Scrape YouTube channels and auto-populate fields
# 2. Auto-score gate checks from video metadata
# 3. Suggest tier based on signals
# 4. Draft personalized outreach emails
# 5. Track follow-up reminders
# 6. Generate pipeline reports

# All through the same Airtable API
channels = lm.get_channels_by_tier("A")
for ch in channels:
    # AI processes each Tier A lead...
    pass
```
