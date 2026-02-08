"""
Aftercells Lead Management System - Airtable Schema Definition

This file defines the complete schema for the Aftercells lead management
Airtable base. It serves as both documentation and the source of truth
for the setup script.
"""

# =============================================================================
# TABLE 1: CHANNELS (Main leads table)
# =============================================================================
# This is your primary table. Every YouTube channel you discover goes here.

CHANNELS_TABLE = {
    "name": "Channels",
    "fields": [
        # --- BASIC INFO ---
        {
            "name": "Channel Name",
            "type": "singleLineText",
            "description": "YouTube channel name"
        },
        {
            "name": "Channel URL",
            "type": "url",
            "description": "Link to the YouTube channel"
        },
        {
            "name": "Subscriber Count",
            "type": "number",
            "options": {"precision": 0},
            "description": "Approximate subscriber count at time of discovery"
        },
        {
            "name": "Contact Email",
            "type": "email",
            "description": "Email from their YouTube bio or website"
        },
        {
            "name": "Email Domain Note",
            "type": "singleLineText",
            "description": "If email has a company/agency domain (e.g. @lighthouseagents.com), note it here"
        },
        {
            "name": "Social Links",
            "type": "multilineText",
            "description": "Twitter, Instagram, LinkedIn, website - one per line"
        },
        {
            "name": "Has Email in Bio",
            "type": "checkbox",
            "description": "Does the channel have an email listed in their YouTube bio?"
        },

        # --- NICHE ---
        {
            "name": "Primary Niche",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Explainer", "color": "blueDark2"},
                    {"name": "Documentary", "color": "cyanDark2"},
                    {"name": "True Crime / Mystery", "color": "redDark2"},
                    {"name": "History & Politics", "color": "orangeDark2"},
                    {"name": "Science & Space", "color": "purpleDark2"},
                    {"name": "Nature & Geo", "color": "greenDark2"},
                    {"name": "Tech & Innovation", "color": "grayDark2"},
                    {"name": "Finance & Business", "color": "yellowDark2"},
                    {"name": "3D Animated Storytelling", "color": "pinkDark2"},
                ]
            },
            "description": "Primary niche category the channel falls into"
        },
        {
            "name": "Sub-Niche Notes",
            "type": "singleLineText",
            "description": "Any sub-niche detail (e.g. 'military history', 'deep sea exploration')"
        },

        # --- GATE CHECKS (must pass ALL to be a valid lead) ---
        {
            "name": "GATE: Active Channel",
            "type": "checkbox",
            "description": "Has posted at least 1 video in the last 5 months"
        },
        {
            "name": "GATE: Long Form Content",
            "type": "checkbox",
            "description": "Videos are >= 10 minutes"
        },
        {
            "name": "GATE: English Speaking",
            "type": "checkbox",
            "description": "Channel content is in English"
        },
        {
            "name": "GATE: Idea-Led Content",
            "type": "checkbox",
            "description": "Content is idea-first, cannot be shown with real footage"
        },
        {
            "name": "GATE: No Distinct Custom Style",
            "type": "checkbox",
            "description": "The channel does NOT use a single locked-in custom style throughout (they're open to visual change)"
        },
        {
            "name": "GATE: Storytelling/Docs/Explainer",
            "type": "checkbox",
            "description": "Content falls into storytelling / documentary / explainer category"
        },
        {
            "name": "Passes Gate",
            "type": "formula",
            "options": {
                "formula": "IF(AND({GATE: Active Channel}, {GATE: Long Form Content}, {GATE: English Speaking}, {GATE: Idea-Led Content}, {GATE: No Distinct Custom Style}, {GATE: Storytelling/Docs/Explainer}), 'YES', 'NO')"
            },
            "description": "Auto-calculated: does the channel pass all gate checks?"
        },

        # --- VIDEO INSIGHTS (for tier sorting) ---
        {
            "name": "Uses 3D",
            "type": "checkbox",
            "description": "Channel uses 3D visuals/animation in videos"
        },
        {
            "name": "Uses Motion Graphics / 2D",
            "type": "checkbox",
            "description": "Channel uses 2D motion graphics in videos"
        },
        {
            "name": "Uses Stock Footage / Photo",
            "type": "checkbox",
            "description": "Channel relies on stock footage or photos"
        },
        {
            "name": "Video Insights Count",
            "type": "formula",
            "options": {
                "formula": "IF({Uses 3D}, 1, 0) + IF({Uses Motion Graphics / 2D}, 1, 0) + IF({Uses Stock Footage / Photo}, 1, 0)"
            },
            "description": "Auto-count of positive video insights checked"
        },

        # --- NEGATIVE INSIGHTS ---
        {
            "name": "NEG: Filmed Footage Primary",
            "type": "checkbox",
            "description": "Filmed footage is the PRIMARY source of value (negative signal)"
        },
        {
            "name": "NEG: Face Cam / Personality Primary",
            "type": "checkbox",
            "description": "Face cam / personality is the PRIMARY driver of engagement (negative signal)"
        },
        {
            "name": "Negative Insight Triggered",
            "type": "formula",
            "options": {
                "formula": "IF(OR({NEG: Filmed Footage Primary}, {NEG: Face Cam / Personality Primary}), 'YES', 'NO')"
            },
            "description": "Auto-calculated: is any negative insight triggered?"
        },

        # --- CHANNEL INSIGHTS (monetization) ---
        {
            "name": "Has Sponsors",
            "type": "checkbox",
            "description": "Channel has sponsor integrations in videos"
        },
        {
            "name": "Has Patreon / Membership",
            "type": "checkbox",
            "description": "Channel has Patreon or membership"
        },
        {
            "name": "Patreon Revenue Note",
            "type": "singleLineText",
            "description": "If Patreon, note approximate revenue (must be 4+ digits to count as monetized)"
        },
        {
            "name": "Has Product",
            "type": "checkbox",
            "description": "Channel sells a product (course, merch, etc.)"
        },

        # --- CHANNEL LOOK ---
        {
            "name": "Consistent Branding",
            "type": "checkbox",
            "description": "Channel has consistent branding and thumbnails"
        },

        # --- TIER (auto-calculated) ---
        {
            "name": "Tier",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "A", "color": "greenDark2"},
                    {"name": "B", "color": "blueDark2"},
                    {"name": "C", "color": "orangeDark2"},
                    {"name": "D", "color": "grayDark2"},
                ]
            },
            "description": "Lead tier: A (monetized, high signal), B (monetization-ready), C (low signal), D (manual review)"
        },
        # NOTE: Tier is a manual select because Airtable formula fields can't output
        # single-select values. But there's a formula field below that RECOMMENDS a tier.
        {
            "name": "Recommended Tier",
            "type": "formula",
            "options": {
                "formula": (
                    "IF({Passes Gate} = 'NO', 'DOES NOT PASS GATE', "
                    "IF(AND("
                    "  OR(AND({Video Insights Count} >= 2, {Uses 3D}), {Video Insights Count} >= 2, {Uses 3D}),"
                    "  {Negative Insight Triggered} = 'NO',"
                    "  {Has Sponsors},"
                    "  {Consistent Branding}"
                    "), 'A', "
                    "IF(AND("
                    "  OR({Video Insights Count} >= 1, {Uses 3D}),"
                    "  {Negative Insight Triggered} = 'NO'"
                    "), 'B', "
                    "'C')))"
                )
            },
            "description": "Auto-recommended tier based on your scoring rules. Use this to guide the manual Tier field."
        },

        # --- OUTREACH ---
        {
            "name": "Model Fit",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Salt", "color": "yellowDark2"},
                    {"name": "Full Meal", "color": "greenDark2"},
                    {"name": "Both", "color": "blueDark2"},
                    {"name": "Undecided", "color": "grayDark2"},
                ]
            },
            "description": "Salt = premium addon (3D/MG for hooks). Full Meal = we produce the entire video."
        },
        {
            "name": "Outreach Status",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "New Lead", "color": "grayDark2"},
                    {"name": "Researching", "color": "blueDark2"},
                    {"name": "Ready to Reach Out", "color": "cyanDark2"},
                    {"name": "Contacted", "color": "yellowDark2"},
                    {"name": "In Conversation", "color": "orangeDark2"},
                    {"name": "Proposal Sent", "color": "pinkDark2"},
                    {"name": "Won - Active Client", "color": "greenDark2"},
                    {"name": "Lost", "color": "redDark2"},
                    {"name": "Not a Fit", "color": "grayDark2"},
                ]
            },
            "description": "Current outreach status"
        },
        {
            "name": "Hiring Signal",
            "type": "checkbox",
            "description": "Saw a signal of hiring on socials or website"
        },
        {
            "name": "Team Signal",
            "type": "singleLineText",
            "description": "Notes about their team: writer, editor, studio, etc."
        },

        # --- NOTES & META ---
        {
            "name": "Discovery Notes",
            "type": "multilineText",
            "description": "How you found them, first impressions, anything notable"
        },
        {
            "name": "Sample Video URL",
            "type": "url",
            "description": "Link to a representative video you reviewed"
        },
        {
            "name": "Date Added",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}},
            "description": "When this lead was added"
        },
        {
            "name": "Last Updated",
            "type": "lastModifiedTime",
            "description": "Auto-tracked: when this record was last modified"
        },
        {
            "name": "Added By",
            "type": "singleLineText",
            "description": "Who added this lead (for when you scale the team)"
        },
    ]
}


# =============================================================================
# TABLE 2: OUTREACH LOG
# =============================================================================
# Track every touchpoint with a lead. Linked to Channels table.

OUTREACH_LOG_TABLE = {
    "name": "Outreach Log",
    "fields": [
        {
            "name": "Channel",
            "type": "multipleRecordLinks",
            "options": {"linkedTableId": "Channels"},
            "description": "Link to the channel this outreach is for"
        },
        {
            "name": "Date",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}},
            "description": "Date of this touchpoint"
        },
        {
            "name": "Type",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Email", "color": "blueDark2"},
                    {"name": "DM (Twitter)", "color": "cyanDark2"},
                    {"name": "DM (Instagram)", "color": "pinkDark2"},
                    {"name": "DM (LinkedIn)", "color": "blueDark2"},
                    {"name": "YouTube Comment", "color": "redDark2"},
                    {"name": "Call", "color": "greenDark2"},
                    {"name": "Meeting", "color": "purpleDark2"},
                    {"name": "Other", "color": "grayDark2"},
                ]
            },
            "description": "Type of outreach"
        },
        {
            "name": "Direction",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Outbound (we reached out)", "color": "orangeDark2"},
                    {"name": "Inbound (they reached out)", "color": "greenDark2"},
                ]
            },
            "description": "Who initiated?"
        },
        {
            "name": "Subject / Summary",
            "type": "singleLineText",
            "description": "Brief summary of what was communicated"
        },
        {
            "name": "Message / Notes",
            "type": "multilineText",
            "description": "Full message or detailed notes"
        },
        {
            "name": "Response Received",
            "type": "checkbox",
            "description": "Did they respond?"
        },
        {
            "name": "Follow-Up Date",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}},
            "description": "When to follow up next"
        },
    ]
}


# =============================================================================
# TABLE 3: PROJECTS
# =============================================================================
# When a lead converts to a client, track the project here.

PROJECTS_TABLE = {
    "name": "Projects",
    "fields": [
        {
            "name": "Project Name",
            "type": "singleLineText",
            "description": "Name of the project"
        },
        {
            "name": "Channel",
            "type": "multipleRecordLinks",
            "options": {"linkedTableId": "Channels"},
            "description": "Link to the client channel"
        },
        {
            "name": "Model",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Salt", "color": "yellowDark2"},
                    {"name": "Full Meal", "color": "greenDark2"},
                ]
            },
            "description": "Salt (addon) or Full Meal (full production)"
        },
        {
            "name": "Status",
            "type": "singleSelect",
            "options": {
                "choices": [
                    {"name": "Scoping", "color": "grayDark2"},
                    {"name": "In Production", "color": "blueDark2"},
                    {"name": "Review", "color": "orangeDark2"},
                    {"name": "Delivered", "color": "greenDark2"},
                    {"name": "On Hold", "color": "yellowDark2"},
                    {"name": "Cancelled", "color": "redDark2"},
                ]
            },
            "description": "Project status"
        },
        {
            "name": "Video URL",
            "type": "url",
            "description": "Link to the video being worked on"
        },
        {
            "name": "Services",
            "type": "multipleSelects",
            "options": {
                "choices": [
                    {"name": "3D Animation", "color": "purpleDark2"},
                    {"name": "2D Motion Graphics", "color": "blueDark2"},
                    {"name": "Video Editing", "color": "greenDark2"},
                    {"name": "Hook Sequence", "color": "orangeDark2"},
                ]
            },
            "description": "What services are included in this project"
        },
        {
            "name": "Budget",
            "type": "currency",
            "options": {"precision": 0, "symbol": "$"},
            "description": "Project budget"
        },
        {
            "name": "Start Date",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}},
            "description": "When production starts"
        },
        {
            "name": "Deadline",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}},
            "description": "Delivery deadline"
        },
        {
            "name": "Notes",
            "type": "multilineText",
            "description": "Project notes, client preferences, etc."
        },
    ]
}


# =============================================================================
# VIEWS (for the Channels table)
# =============================================================================
# These are the filtered views you'll use day-to-day

CHANNEL_VIEWS = [
    {
        "name": "All Leads (Passed Gate)",
        "description": "All channels that passed the gate check",
        "filter": "Passes Gate = YES",
        "sort": [{"field": "Tier", "direction": "asc"}, {"field": "Subscriber Count", "direction": "desc"}],
    },
    {
        "name": "Tier A - Hot Leads",
        "description": "Monetized channels with strong signals",
        "filter": "Tier = A AND Passes Gate = YES",
        "sort": [{"field": "Subscriber Count", "direction": "desc"}],
    },
    {
        "name": "Tier B - Warm Leads",
        "description": "Monetization-ready channels",
        "filter": "Tier = B AND Passes Gate = YES",
        "sort": [{"field": "Subscriber Count", "direction": "desc"}],
    },
    {
        "name": "Tier C - Cold Leads",
        "description": "Low signal channels, keep an eye on",
        "filter": "Tier = C AND Passes Gate = YES",
    },
    {
        "name": "Tier D - Manual Review",
        "description": "Channels that need your personal review",
        "filter": "Tier = D",
    },
    {
        "name": "Did Not Pass Gate",
        "description": "Channels that failed gate checks - review why",
        "filter": "Passes Gate = NO",
    },
    {
        "name": "Salt Fit",
        "description": "Channels suited for the Salt model (premium addon)",
        "filter": "Model Fit = Salt OR Model Fit = Both",
    },
    {
        "name": "Full Meal Fit",
        "description": "Channels suited for Full Meal model (full production)",
        "filter": "Model Fit = Full Meal OR Model Fit = Both",
    },
    {
        "name": "Ready to Reach Out",
        "description": "Leads ready for outreach",
        "filter": "Outreach Status = Ready to Reach Out",
        "sort": [{"field": "Tier", "direction": "asc"}],
    },
    {
        "name": "In Pipeline",
        "description": "Active conversations and proposals",
        "filter": "Outreach Status = Contacted OR Outreach Status = In Conversation OR Outreach Status = Proposal Sent",
    },
    {
        "name": "Won Clients",
        "description": "Active clients",
        "filter": "Outreach Status = Won - Active Client",
    },
    {
        "name": "By Niche - Explainer",
        "description": "Explainer channels only",
        "filter": "Primary Niche = Explainer",
    },
    {
        "name": "By Niche - 3D Animated",
        "description": "3D animated storytelling channels",
        "filter": "Primary Niche = 3D Animated Storytelling",
    },
    {
        "name": "Hiring Signals",
        "description": "Channels showing hiring signals (hot for Full Meal)",
        "filter": "Hiring Signal = TRUE",
    },
]


# =============================================================================
# ALL TABLES
# =============================================================================

ALL_TABLES = [CHANNELS_TABLE, OUTREACH_LOG_TABLE, PROJECTS_TABLE]
