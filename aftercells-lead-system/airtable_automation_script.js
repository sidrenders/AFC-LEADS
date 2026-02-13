// =============================================================================
// AFTERCELLS — Airtable Automation Script
// Auto-enrich new leads when you add a Channel URL
//
// SETUP:
//   1. Go to Airtable → Automations (top-right lightning bolt icon)
//   2. Click "+ Create automation"
//   3. Trigger: "When record matches conditions"
//      - Table: Channels
//      - Condition: "Channel URL" is not empty AND "Added By" is empty
//        (this ensures it only runs on new manual entries, not imports)
//   4. Action: "Run a script"
//   5. Paste this ENTIRE script
//   6. In the left sidebar, add these Input Variables:
//      - recordId    → click the blue + → Record ID
//      - channelUrl  → click the blue + → Channel URL field
//   7. Click "Test" to verify, then turn on the automation
//
// API KEYS (set in the script below):
//   - YOUTUBE_API_KEY: your YouTube Data API v3 key
//   - ANTHROPIC_API_KEY: your Claude API key
// =============================================================================

// ─── CONFIG ──────────────────────────────────────────────────────────────────
const YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE";
const ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY_HERE";

// Gate thresholds
const ACTIVE_MONTHS = 5;
const MIN_AVG_DURATION_MINS = 10;
const VIDEOS_TO_FETCH = 5;

// Valid niches (must match your Airtable single-select options)
const VALID_NICHES = [
    "Explainer",
    "Documentary",
    "True Crime / Mystery",
    "History & Politics",
    "Science & Space",
    "Nature & Geo",
    "Tech & Innovation",
    "Finance & Business",
    "3D Animated Storytelling",
];

// ─── INPUT ───────────────────────────────────────────────────────────────────
const inputConfig = input.config();
const recordId = inputConfig.recordId;
const channelUrl = inputConfig.channelUrl;

if (!channelUrl) {
    console.log("No Channel URL provided — skipping.");
    return;
}

console.log(`\n🔍 Enriching: ${channelUrl}`);

// ─── YOUTUBE URL PARSING ─────────────────────────────────────────────────────

function parseYouTubeUrl(url) {
    if (!url) return { type: "unknown", value: null };
    url = url.trim();

    let match;

    match = url.match(/youtube\.com\/@([^/?&\s]+)/);
    if (match) return { type: "handle", value: match[1] };

    match = url.match(/youtube\.com\/channel\/(UC[^/?&\s]+)/);
    if (match) return { type: "channel_id", value: match[1] };

    match = url.match(/youtube\.com\/c\/([^/?&\s]+)/);
    if (match) return { type: "custom_url", value: match[1] };

    match = url.match(/youtube\.com\/user\/([^/?&\s]+)/);
    if (match) return { type: "username", value: match[1] };

    match = url.match(/(?:youtube\.com\/watch\?.*v=|youtu\.be\/)([^&\s?]+)/);
    if (match) return { type: "video_id", value: match[1] };

    return { type: "unknown", value: null };
}

// ─── YOUTUBE API HELPERS ─────────────────────────────────────────────────────

async function ytApiGet(endpoint, params) {
    params.key = YOUTUBE_API_KEY;
    const queryString = Object.entries(params)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join("&");
    const url = `https://www.googleapis.com/youtube/v3/${endpoint}?${queryString}`;

    let resp = await fetch(url);
    if (!resp.ok) {
        console.log(`  YouTube API error ${resp.status}: ${await resp.text()}`);
        return null;
    }
    return await resp.json();
}

async function resolveChannelId(url) {
    const { type, value } = parseYouTubeUrl(url);

    if (type === "channel_id") return value;

    if (type === "handle") {
        let data = await ytApiGet("channels", { part: "id", forHandle: value });
        if (data && data.items && data.items.length > 0) return data.items[0].id;
        // Fallback to search
        data = await ytApiGet("search", { part: "snippet", q: value, type: "channel", maxResults: 1 });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    if (type === "username") {
        let data = await ytApiGet("channels", { part: "id", forUsername: value });
        if (data && data.items && data.items.length > 0) return data.items[0].id;
    }

    if (type === "custom_url") {
        let data = await ytApiGet("search", { part: "snippet", q: value, type: "channel", maxResults: 1 });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    if (type === "video_id") {
        let data = await ytApiGet("videos", { part: "snippet", id: value });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    return null;
}

// ─── DURATION PARSER ─────────────────────────────────────────────────────────

function parseDuration(iso) {
    const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!match) return 0;
    const h = parseInt(match[1] || 0);
    const m = parseInt(match[2] || 0);
    const s = parseInt(match[3] || 0);
    return h * 60 + m + s / 60;
}

// ─── EMAIL EXTRACTOR ─────────────────────────────────────────────────────────

function extractEmail(text) {
    if (!text) return null;
    const emails = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g);
    if (!emails) return null;
    const filtered = emails.filter(e =>
        !e.toLowerCase().includes("@example") &&
        !e.toLowerCase().includes("noreply") &&
        !e.toLowerCase().includes("no-reply")
    );
    return filtered.length > 0 ? filtered[0] : null;
}

// ─── MAIN ENRICHMENT ─────────────────────────────────────────────────────────

// Step 1: Resolve channel ID
const channelId = await resolveChannelId(channelUrl);
if (!channelId) {
    console.log("Could not resolve channel ID. Check the URL.");
    let table = base.getTable("Channels");
    await table.updateRecordAsync(recordId, {
        "Discovery Notes": "AUTO-ENRICH FAILED: Could not resolve channel ID from URL",
        "Added By": "Manual Entry",
    });
    return;
}
console.log(`  Channel ID: ${channelId}`);

// Step 2: Fetch channel details
const chData = await ytApiGet("channels", {
    part: "snippet,contentDetails,statistics,brandingSettings",
    id: channelId,
});

if (!chData || !chData.items || chData.items.length === 0) {
    console.log("Channel not found (may be deleted).");
    let table = base.getTable("Channels");
    await table.updateRecordAsync(recordId, {
        "Discovery Notes": "AUTO-ENRICH FAILED: Channel not found (may be deleted)",
        "Added By": "Manual Entry",
    });
    return;
}

const channel = chData.items[0];
const snippet = channel.snippet || {};
const stats = channel.statistics || {};
const channelName = snippet.title || "";
const description = snippet.description || "";
const subscriberCount = parseInt(stats.subscriberCount || 0);

// Get handle for normalized URL
const customUrl = snippet.customUrl || "";
let normalizedUrl = channelUrl;
if (customUrl && customUrl.startsWith("@")) {
    normalizedUrl = `https://www.youtube.com/${customUrl}/videos`;
}

// Extract email from bio
const bioEmail = extractEmail(description);

console.log(`  Channel: ${channelName}`);
console.log(`  Subscribers: ${subscriberCount.toLocaleString()}`);
if (bioEmail) console.log(`  Email found: ${bioEmail}`);

// Step 3: Fetch recent videos
const uploadsPlaylist = channel.contentDetails?.relatedPlaylists?.uploads;
let videos = [];

if (uploadsPlaylist) {
    const playlistData = await ytApiGet("playlistItems", {
        part: "contentDetails",
        playlistId: uploadsPlaylist,
        maxResults: VIDEOS_TO_FETCH,
    });

    if (playlistData && playlistData.items && playlistData.items.length > 0) {
        const videoIds = playlistData.items.map(i => i.contentDetails.videoId).join(",");
        const videoData = await ytApiGet("videos", {
            part: "contentDetails,snippet",
            id: videoIds,
        });
        if (videoData && videoData.items) {
            videos = videoData.items;
        }
    }
}

console.log(`  Fetched ${videos.length} recent videos`);

// Step 4: Gate checks
let gateActive = false;
let gateLongForm = false;
let gateEnglish = true;
let gateFailReasons = [];

// Active check
if (videos.length > 0) {
    const dates = videos
        .map(v => new Date(v.snippet?.publishedAt))
        .filter(d => !isNaN(d));

    if (dates.length > 0) {
        const mostRecent = new Date(Math.max(...dates));
        const cutoff = new Date();
        cutoff.setMonth(cutoff.getMonth() - ACTIVE_MONTHS);
        gateActive = mostRecent >= cutoff;
        if (!gateActive) {
            gateFailReasons.push(`Inactive (last upload: ${mostRecent.toISOString().slice(0, 10)})`);
        }
    }
} else {
    gateFailReasons.push("No videos found");
}

// Long form check
if (videos.length > 0) {
    const durations = videos
        .map(v => parseDuration(v.contentDetails?.duration || ""))
        .filter(d => d > 0);
    if (durations.length > 0) {
        const avgDur = durations.reduce((a, b) => a + b, 0) / durations.length;
        gateLongForm = avgDur >= MIN_AVG_DURATION_MINS;
        if (!gateLongForm) {
            gateFailReasons.push(`Short form (avg ${avgDur.toFixed(1)} min)`);
        }
    }
}

// English check (non-Latin script detection)
if (videos.length > 0) {
    const titles = videos.map(v => v.snippet?.title || "").join(" ");
    const totalChars = titles.replace(/\s/g, "").length;
    if (totalChars > 0) {
        let latinChars = 0;
        for (const c of titles) {
            const code = c.charCodeAt(0);
            if (code < 0x0250 || "–—''\"\"…•".includes(c)) {
                latinChars++;
            }
        }
        const ratio = latinChars / titles.length;
        gateEnglish = ratio >= 0.60;
        if (!gateEnglish) {
            gateFailReasons.push("Non-Latin script titles");
        }
    }
}

const gatePassed = gateActive && gateLongForm && gateEnglish;
console.log(`  Gate: ${gatePassed ? "PASSED" : "FAILED"} ${gateFailReasons.length > 0 ? "(" + gateFailReasons.join(", ") + ")" : ""}`);

// Step 5: AI Classification (only if gate passed)
let aiResult = null;

if (gatePassed && videos.length > 0) {
    console.log("  Running AI classification...");

    const videoText = videos.slice(0, 3).map((v, i) =>
        `\n  Video ${i + 1}: ${v.snippet?.title}\n  Description: ${(v.snippet?.description || "").slice(0, 500)}`
    ).join("\n");

    const prompt = `You are classifying a YouTube channel for a creative agency that does 3D/2D motion graphics for storytelling YouTubers.

CHANNEL: ${channelName}
CHANNEL DESCRIPTION: ${(description || "N/A").slice(0, 800)}

RECENT VIDEOS:${videoText}

Classify this channel. Respond in EXACTLY this JSON format, nothing else:
{
  "primary_niche": "<one of: Explainer, Documentary, True Crime / Mystery, History & Politics, Science & Space, Nature & Geo, Tech & Innovation, Finance & Business, 3D Animated Storytelling>",
  "sub_niche": "<short description like 'military history' or 'deep sea biology'>",
  "is_idea_led": <true if content is concept/idea-driven and CANNOT be shown with real filmed footage, false otherwise>,
  "is_storytelling_docs_explainer": <true if the content is storytelling, documentary, or explainer style>,
  "has_sponsors": <true if any video description mentions a sponsor, false otherwise>,
  "has_patreon": <true if any text mentions Patreon, membership, or similar>,
  "uses_3d": <true if evidence of 3D animation/visuals, false or uncertain = false>,
  "uses_motion_graphics_2d": <true if evidence of 2D motion graphics/animation, false or uncertain = false>,
  "uses_stock_footage": <true if likely uses stock footage/photos as primary visuals, false otherwise>,
  "content_language": "<primary language of the content, e.g. 'English', 'German', 'Spanish'>"
}

Be conservative with visual style flags — only mark true if there are strong clues.
For content_language, judge by the video TITLES and DESCRIPTIONS.`;

    try {
        const aiResp = await fetch("https://api.anthropic.com/v1/messages", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            body: JSON.stringify({
                model: "claude-haiku-4-5-20251001",
                max_tokens: 400,
                messages: [{ role: "user", content: prompt }],
            }),
        });

        if (aiResp.ok) {
            const aiData = await aiResp.json();
            let text = aiData.content[0].text.trim();
            // Handle markdown code blocks
            if (text.includes("```")) {
                text = text.split("```")[1];
                if (text.startsWith("json")) text = text.slice(4);
                text = text.trim();
            }
            aiResult = JSON.parse(text);
            // Validate niche
            if (!VALID_NICHES.includes(aiResult.primary_niche)) {
                aiResult.primary_niche = null;
            }
            console.log(`  AI: ${aiResult.primary_niche || "Unknown niche"} | Language: ${aiResult.content_language}`);
        } else {
            console.log(`  AI error: ${aiResp.status} ${await aiResp.text()}`);
        }
    } catch (e) {
        console.log(`  AI error: ${e.message}`);
    }
}

// Step 6: Build the update fields
let updateFields = {
    "Channel Name": channelName,
    "Channel URL": normalizedUrl,
    "Subscriber Count": subscriberCount,
    "Active Channel": gateActive,
    "Long Form Content": gateLongForm,
    "English Speaking": gateEnglish,
    "Added By": "Manual Entry",
    "Date Added": new Date().toISOString().slice(0, 10),
};

// Email
if (bioEmail) {
    updateFields["Contact Email"] = bioEmail;
    updateFields["Has Email in Bio"] = true;
}

// Sample video
if (videos.length > 0) {
    updateFields["Sample Video URL"] = `https://www.youtube.com/watch?v=${videos[0].id}`;
}

// Discovery notes
let notes = [];
if (gateFailReasons.length > 0) {
    notes.push(`Gate failures: ${gateFailReasons.join(", ")}`);
}
if (description) {
    notes.push(`Channel bio: ${description.slice(0, 500)}`);
}
if (notes.length > 0) {
    updateFields["Discovery Notes"] = notes.join("\n");
}

// Outreach status
if (!gatePassed) {
    updateFields["Outreach Status"] = { name: "Not a Fit" };
} else {
    updateFields["Outreach Status"] = { name: "New Lead" };
}

// AI fields
if (aiResult) {
    // Language override
    const lang = (aiResult.content_language || "").toLowerCase();
    if (lang && lang !== "english" && !lang.startsWith("english")) {
        updateFields["English Speaking"] = false;
    }

    if (aiResult.primary_niche) {
        updateFields["Primary Niche"] = { name: aiResult.primary_niche };
    }
    if (aiResult.sub_niche) {
        updateFields["Sub-Niche Notes"] = aiResult.sub_niche;
    }
    if (aiResult.is_idea_led) {
        updateFields["Idea-Led Content"] = true;
    }
    if (aiResult.is_storytelling_docs_explainer) {
        updateFields["Storytelling/Docs/Explainer"] = true;
    }
    if (aiResult.has_sponsors) {
        updateFields["Has Sponsors"] = true;
    }
    if (aiResult.has_patreon) {
        updateFields["Has Patreon / Membership"] = true;
    }
    if (aiResult.uses_3d) {
        updateFields["Uses 3D"] = true;
    }
    if (aiResult.uses_motion_graphics_2d) {
        updateFields["Uses Motion Graphics / 2D"] = true;
    }
    if (aiResult.uses_stock_footage) {
        updateFields["Uses Stock Footage / Photo"] = true;
    }
}

// Step 7: Update the record in Airtable
let table = base.getTable("Channels");
await table.updateRecordAsync(recordId, updateFields);

console.log(`\n✅ Done! ${channelName} enriched successfully.`);
console.log(`   Gate: ${gatePassed ? "PASSED" : "FAILED"}`);
if (aiResult) {
    console.log(`   Niche: ${aiResult.primary_niche}`);
    console.log(`   Language: ${aiResult.content_language}`);
}
console.log(`   Subs: ${subscriberCount.toLocaleString()}`);
