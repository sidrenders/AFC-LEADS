/*
AFTERCELLS - Airtable Automation Script
Auto-enrich new leads when you add a Channel URL

SETUP:
  1. Go to Airtable > Automations (top-right lightning bolt icon)
  2. Click "+ Create automation"
  3. Trigger: "When record matches conditions"
     - Table: Channels
     - Condition: "Channel URL" is not empty AND "Added By" is empty
  4. Action: "Run a script"
  5. Paste this ENTIRE script
  6. In the left sidebar, add these Input Variables:
     - recordId    > click the blue + > Record ID
     - channelUrl  > click the blue + > Channel URL field
  7. Click "Test" to verify, then turn on the automation
*/

// CONFIG - paste your API keys here
const YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE";
const ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY_HERE";

const ACTIVE_MONTHS = 5;
const MIN_AVG_DURATION_MINS = 10;
const VIDEOS_TO_FETCH = 5;

const VALID_NICHES = [
    "Explainer",
    "Documentary",
    "True Crime / Mystery",
    "History & Politics",
    "Science & Space",
    "Nature & Geo",
    "Tech & Innovation",
    "Finance & Business",
    "3D Animated Storytelling"
];

// INPUT
let inputConfig = input.config();
let recordId = inputConfig.recordId;
let channelUrl = inputConfig.channelUrl;

// HELPER FUNCTIONS

function parseYouTubeUrl(url) {
    if (!url) return { type: "unknown", value: null };
    url = url.trim();
    let match;
    match = url.match(/youtube\.com\/@([^\/?&\s]+)/);
    if (match) return { type: "handle", value: match[1] };
    match = url.match(/youtube\.com\/channel\/(UC[^\/?&\s]+)/);
    if (match) return { type: "channel_id", value: match[1] };
    match = url.match(/youtube\.com\/c\/([^\/?&\s]+)/);
    if (match) return { type: "custom_url", value: match[1] };
    match = url.match(/youtube\.com\/user\/([^\/?&\s]+)/);
    if (match) return { type: "username", value: match[1] };
    match = url.match(/(?:youtube\.com\/watch\?.*v=|youtu\.be\/)([^&\s?]+)/);
    if (match) return { type: "video_id", value: match[1] };
    return { type: "unknown", value: null };
}

async function ytApiGet(endpoint, params) {
    params.key = YOUTUBE_API_KEY;
    let queryString = Object.entries(params)
        .map(function(pair) { return pair[0] + "=" + encodeURIComponent(pair[1]); })
        .join("&");
    let url = "https://www.googleapis.com/youtube/v3/" + endpoint + "?" + queryString;
    let resp = await fetch(url);
    if (!resp.ok) {
        let errText = await resp.text();
        console.log("  YouTube API error " + resp.status + ": " + errText.substring(0, 200));
        return null;
    }
    return await resp.json();
}

async function resolveChannelId(url) {
    let parsed = parseYouTubeUrl(url);
    let type = parsed.type;
    let value = parsed.value;

    if (type === "channel_id") return value;

    if (type === "handle") {
        let data = await ytApiGet("channels", { part: "id", forHandle: value });
        if (data && data.items && data.items.length > 0) return data.items[0].id;
        data = await ytApiGet("search", { part: "snippet", q: value, type: "channel", maxResults: "1" });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    if (type === "username") {
        let data = await ytApiGet("channels", { part: "id", forUsername: value });
        if (data && data.items && data.items.length > 0) return data.items[0].id;
    }

    if (type === "custom_url") {
        let data = await ytApiGet("search", { part: "snippet", q: value, type: "channel", maxResults: "1" });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    if (type === "video_id") {
        let data = await ytApiGet("videos", { part: "snippet", id: value });
        if (data && data.items && data.items.length > 0) return data.items[0].snippet.channelId;
    }

    return null;
}

function parseDuration(iso) {
    if (!iso) return 0;
    let match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!match) return 0;
    let h = parseInt(match[1] || "0");
    let m = parseInt(match[2] || "0");
    let s = parseInt(match[3] || "0");
    return h * 60 + m + s / 60;
}

function extractEmail(text) {
    if (!text) return null;
    let emails = text.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g);
    if (!emails) return null;
    let filtered = emails.filter(function(e) {
        let lower = e.toLowerCase();
        return lower.indexOf("@example") === -1 &&
               lower.indexOf("noreply") === -1 &&
               lower.indexOf("no-reply") === -1;
    });
    return filtered.length > 0 ? filtered[0] : null;
}

// MAIN SCRIPT

if (!channelUrl) {
    console.log("No Channel URL provided - skipping.");
} else {
    console.log("Enriching: " + channelUrl);

    // Step 1: Resolve channel ID
    let channelId = await resolveChannelId(channelUrl);

    if (!channelId) {
        console.log("Could not resolve channel ID. Check the URL.");
        let table = base.getTable("Channels");
        await table.updateRecordAsync(recordId, {
            "Discovery Notes": "AUTO-ENRICH FAILED: Could not resolve channel ID from URL",
            "Added By": "Manual Entry"
        });
    } else {
        console.log("  Channel ID: " + channelId);

        // Step 2: Fetch channel details
        let chData = await ytApiGet("channels", {
            part: "snippet,contentDetails,statistics,brandingSettings",
            id: channelId
        });

        if (!chData || !chData.items || chData.items.length === 0) {
            console.log("Channel not found (may be deleted).");
            let table = base.getTable("Channels");
            await table.updateRecordAsync(recordId, {
                "Discovery Notes": "AUTO-ENRICH FAILED: Channel not found (may be deleted)",
                "Added By": "Manual Entry"
            });
        } else {
            let channel = chData.items[0];
            let snippet = channel.snippet || {};
            let stats = channel.statistics || {};
            let channelName = snippet.title || "";
            let description = snippet.description || "";
            let subscriberCount = parseInt(stats.subscriberCount || "0");

            // Get handle for normalized URL
            let customUrl = snippet.customUrl || "";
            let normalizedUrl = channelUrl;
            if (customUrl && customUrl.indexOf("@") === 0) {
                normalizedUrl = "https://www.youtube.com/" + customUrl + "/videos";
            }

            // Extract email from bio
            let bioEmail = extractEmail(description);

            console.log("  Channel: " + channelName);
            console.log("  Subscribers: " + subscriberCount);
            if (bioEmail) console.log("  Email found: " + bioEmail);

            // Step 3: Fetch recent videos
            let uploadsPlaylist = null;
            if (channel.contentDetails && channel.contentDetails.relatedPlaylists) {
                uploadsPlaylist = channel.contentDetails.relatedPlaylists.uploads;
            }
            let videos = [];

            if (uploadsPlaylist) {
                let playlistData = await ytApiGet("playlistItems", {
                    part: "contentDetails",
                    playlistId: uploadsPlaylist,
                    maxResults: String(VIDEOS_TO_FETCH)
                });

                if (playlistData && playlistData.items && playlistData.items.length > 0) {
                    let videoIds = playlistData.items.map(function(i) { return i.contentDetails.videoId; }).join(",");
                    let videoData = await ytApiGet("videos", {
                        part: "contentDetails,snippet",
                        id: videoIds
                    });
                    if (videoData && videoData.items) {
                        videos = videoData.items;
                    }
                }
            }

            console.log("  Fetched " + videos.length + " recent videos");

            // Step 4: Gate checks
            let gateActive = false;
            let gateLongForm = false;
            let gateEnglish = true;
            let gateFailReasons = [];

            // Active check
            if (videos.length > 0) {
                let dates = [];
                for (let v of videos) {
                    if (v.snippet && v.snippet.publishedAt) {
                        let d = new Date(v.snippet.publishedAt);
                        if (!isNaN(d.getTime())) dates.push(d);
                    }
                }
                if (dates.length > 0) {
                    let mostRecent = new Date(Math.max.apply(null, dates));
                    let cutoff = new Date();
                    cutoff.setMonth(cutoff.getMonth() - ACTIVE_MONTHS);
                    gateActive = mostRecent >= cutoff;
                    if (!gateActive) {
                        gateFailReasons.push("Inactive (last upload: " + mostRecent.toISOString().slice(0, 10) + ")");
                    }
                }
            } else {
                gateFailReasons.push("No videos found");
            }

            // Long form check
            if (videos.length > 0) {
                let durations = [];
                for (let v of videos) {
                    let dur = 0;
                    if (v.contentDetails && v.contentDetails.duration) {
                        dur = parseDuration(v.contentDetails.duration);
                    }
                    if (dur > 0) durations.push(dur);
                }
                if (durations.length > 0) {
                    let sum = 0;
                    for (let d of durations) sum += d;
                    let avgDur = sum / durations.length;
                    gateLongForm = avgDur >= MIN_AVG_DURATION_MINS;
                    if (!gateLongForm) {
                        gateFailReasons.push("Short form (avg " + avgDur.toFixed(1) + " min)");
                    }
                }
            }

            // English check (non-Latin script detection)
            if (videos.length > 0) {
                let allTitles = "";
                for (let v of videos) {
                    if (v.snippet && v.snippet.title) allTitles += v.snippet.title + " ";
                }
                let totalChars = allTitles.replace(/\s/g, "").length;
                if (totalChars > 0) {
                    let latinChars = 0;
                    for (let i = 0; i < allTitles.length; i++) {
                        let code = allTitles.charCodeAt(i);
                        if (code < 0x0250) latinChars++;
                    }
                    let ratio = latinChars / allTitles.length;
                    gateEnglish = ratio >= 0.60;
                    if (!gateEnglish) {
                        gateFailReasons.push("Non-Latin script titles");
                    }
                }
            }

            let gatePassed = gateActive && gateLongForm && gateEnglish;
            let gateMsg = gatePassed ? "PASSED" : "FAILED";
            if (gateFailReasons.length > 0) gateMsg += " (" + gateFailReasons.join(", ") + ")";
            console.log("  Gate: " + gateMsg);

            // Step 5: AI Classification (only if gate passed)
            let aiResult = null;

            if (gatePassed && videos.length > 0) {
                console.log("  Running AI classification...");

                let videoText = "";
                let aiVideos = videos.slice(0, 3);
                for (let i = 0; i < aiVideos.length; i++) {
                    let v = aiVideos[i];
                    let title = (v.snippet && v.snippet.title) ? v.snippet.title : "";
                    let desc = (v.snippet && v.snippet.description) ? v.snippet.description.substring(0, 500) : "";
                    videoText += "\n  Video " + (i + 1) + ": " + title + "\n  Description: " + desc + "\n";
                }

                let prompt = "You are classifying a YouTube channel for a creative agency that does 3D/2D motion graphics for storytelling YouTubers.\n\n";
                prompt += "CHANNEL: " + channelName + "\n";
                prompt += "CHANNEL DESCRIPTION: " + (description || "N/A").substring(0, 800) + "\n\n";
                prompt += "RECENT VIDEOS:" + videoText + "\n";
                prompt += "Classify this channel. Respond in EXACTLY this JSON format, nothing else:\n";
                prompt += '{\n';
                prompt += '  "primary_niche": "<one of: Explainer, Documentary, True Crime / Mystery, History & Politics, Science & Space, Nature & Geo, Tech & Innovation, Finance & Business, 3D Animated Storytelling>",\n';
                prompt += '  "sub_niche": "<short description like military history or deep sea biology>",\n';
                prompt += '  "is_idea_led": true or false,\n';
                prompt += '  "is_storytelling_docs_explainer": true or false,\n';
                prompt += '  "has_sponsors": true or false,\n';
                prompt += '  "has_patreon": true or false,\n';
                prompt += '  "uses_3d": true or false,\n';
                prompt += '  "uses_motion_graphics_2d": true or false,\n';
                prompt += '  "uses_stock_footage": true or false,\n';
                prompt += '  "content_language": "<primary language e.g. English, German, Spanish>"\n';
                prompt += '}\n\n';
                prompt += "Be conservative with visual style flags - only mark true if there are strong clues.\n";
                prompt += "For content_language, judge by the video TITLES and DESCRIPTIONS.";

                try {
                    let aiResp = await fetch("https://api.anthropic.com/v1/messages", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "x-api-key": ANTHROPIC_API_KEY,
                            "anthropic-version": "2023-06-01"
                        },
                        body: JSON.stringify({
                            model: "claude-haiku-4-5-20251001",
                            max_tokens: 400,
                            messages: [{ role: "user", content: prompt }]
                        })
                    });

                    if (aiResp.ok) {
                        let aiData = await aiResp.json();
                        let text = aiData.content[0].text.trim();
                        // Handle markdown code blocks
                        if (text.indexOf("```") !== -1) {
                            text = text.split("```")[1];
                            if (text.indexOf("json") === 0) text = text.substring(4);
                            text = text.trim();
                        }
                        aiResult = JSON.parse(text);
                        // Validate niche
                        if (VALID_NICHES.indexOf(aiResult.primary_niche) === -1) {
                            aiResult.primary_niche = null;
                        }
                        console.log("  AI: " + (aiResult.primary_niche || "Unknown niche") + " | Language: " + aiResult.content_language);
                    } else {
                        let errText = await aiResp.text();
                        console.log("  AI error: " + aiResp.status + " " + errText.substring(0, 200));
                    }
                } catch (e) {
                    console.log("  AI error: " + e.message);
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
                "Date Added": new Date().toISOString().slice(0, 10)
            };

            if (bioEmail) {
                updateFields["Contact Email"] = bioEmail;
                updateFields["Has Email in Bio"] = true;
            }

            if (videos.length > 0 && videos[0].id) {
                updateFields["Sample Video URL"] = "https://www.youtube.com/watch?v=" + videos[0].id;
            }

            // Discovery notes
            let notesParts = [];
            if (gateFailReasons.length > 0) {
                notesParts.push("Gate failures: " + gateFailReasons.join(", "));
            }
            if (description) {
                notesParts.push("Channel bio: " + description.substring(0, 500));
            }
            if (notesParts.length > 0) {
                updateFields["Discovery Notes"] = notesParts.join("\n");
            }

            // Outreach status
            if (!gatePassed) {
                updateFields["Outreach Status"] = { name: "Not a Fit" };
            } else {
                updateFields["Outreach Status"] = { name: "New Lead" };
            }

            // AI fields
            if (aiResult) {
                let lang = (aiResult.content_language || "").toLowerCase();
                if (lang && lang !== "english" && lang.indexOf("english") !== 0) {
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

            // Step 7: Update the record
            let table = base.getTable("Channels");
            await table.updateRecordAsync(recordId, updateFields);

            console.log("Done! " + channelName + " enriched successfully.");
            console.log("  Gate: " + (gatePassed ? "PASSED" : "FAILED"));
            if (aiResult) {
                console.log("  Niche: " + aiResult.primary_niche);
                console.log("  Language: " + aiResult.content_language);
            }
            console.log("  Subs: " + subscriberCount);
        }
    }
}
