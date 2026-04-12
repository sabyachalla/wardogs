"""
War Dogs — Signal Refresh Script
Runs hourly via GitHub Actions.
Fetches headlines from free RSS feeds → sends to Google Gemini (free tier) → updates events.json
"""

import os
import json
import time
import datetime
import feedparser
import google.generativeai as genai

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EVENTS_FILE    = "events.json"
MAX_HEADLINES  = 40   # keep prompt lean to stay in free tier

# Free RSS feeds — no API key required
RSS_FEEDS = [
    # Reuters
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    # Yahoo Finance
    "https://finance.yahoo.com/rss/topfinstories",
    "https://finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    # Google News — geopolitics & markets
    "https://news.google.com/rss/search?q=war+military+geopolitics&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=federal+reserve+interest+rates&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=China+economy+stimulus&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+technology+semiconductor&hl=en-US&gl=US&ceid=US:en",
    # Investing.com
    "https://www.investing.com/rss/news.rss",
]

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetch_headlines() -> list[dict]:
    """Pull titles + summaries from all RSS feeds, deduplicate, return top N."""
    seen   = set()
    items  = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = (entry.get("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                # Strip HTML tags (basic)
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:300]
                items.append({"title": title, "summary": summary[:200]})
        except Exception as e:
            print(f"[WARN] RSS fetch failed for {url}: {e}")
        if len(items) >= MAX_HEADLINES:
            break
    return items[:MAX_HEADLINES]


def load_existing_events() -> dict:
    """Load current events.json for context."""
    try:
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"events": []}


def build_prompt(headlines: list[dict], existing: dict) -> str:
    """Build the Gemini prompt."""
    headline_block = "\n".join(
        f"- {h['title']}" + (f" | {h['summary']}" if h['summary'] else "")
        for h in headlines
    )
    existing_titles = [e.get("title", "") for e in existing.get("events", [])]
    existing_block  = "\n".join(f"- {t}" for t in existing_titles[:10]) or "None"

    return f"""You are War Dogs — an investment signal engine that turns global events into explicit, actionable ETF/stock recommendations for retail investors.

CURRENT NEWS HEADLINES (last hour):
{headline_block}

CURRENTLY ACTIVE SIGNALS (do not duplicate unless materially updated):
{existing_block}

Your task: produce a JSON array of up to 10 investment signals based on today's most impactful global events.

Rules:
1. ONLY include events that have clear, near-term market implications.
2. Every recommendation MUST name the full ETF/stock and ticker — e.g. "Energy Select SPDR ETF (XLE)"
3. Be explicit: BUY, SHORT, or ROTATE. Never vague.
4. Rank by impact: HIGH first, then MED, then LOW.
5. Keep existing signals if still valid. Add new ones from today's news. Remove expired ones.
6. freshLabel = human-readable time like "2h ago", "just now", "1d ago"

Return ONLY valid JSON, no explanation, no markdown. Schema:

{{
  "lastUpdated": "ISO 8601 UTC timestamp",
  "scanSources": ["Reuters", "Yahoo Finance", "Google News", "Bloomberg"],
  "events": [
    {{
      "id": 1,
      "rank": "HIGH",
      "category": "milgeo",
      "catLabel": "Military-Geo",
      "title": "Short descriptive title",
      "summary": "2-3 sentence summary of what is happening and why it matters to investors.",
      "fresh": true,
      "freshLabel": "2h ago",
      "risk": "HIGH",
      "window": "Active now — 4–8 week horizon",
      "actions": [
        {{"label": "BUY",   "cls": "buy",   "target": "Full ETF Name (TICKER)"}},
        {{"label": "SHORT", "cls": "short", "target": "Full ETF Name (TICKER)"}}
      ],
      "reasoning": "3-5 sentence explanation including 'Search ticker X on Vanguard or Fidelity.'",
      "timeFrame": {{
        "enter": "When to enter",
        "viable": "How long the trade is valid",
        "note":   "Key exit trigger"
      }},
      "exitStrategy": "Specific exit conditions.",
      "gains": {{
        "conservative": "+5–8%",
        "conservativeNote": "If X happens",
        "base": "+12–18%",
        "baseNote": "Most likely scenario",
        "extended": "+25%+",
        "extendedNote": "If Y happens",
        "stopLoss": "-8% on [TICKER]"
      }},
      "adjacentMarkets": [
        "Gold (safe haven bid)",
        "USD/JPY (risk-off yen strength)"
      ],
      "otherFactors": [
        "Factor one to watch",
        "Factor two to watch"
      ]
    }}
  ]
}}"""


def call_gemini(prompt: str) -> str:
    """Call Gemini Flash (free tier) and return raw text."""
    genai.configure(api_key=GEMINI_API_KEY)
    model    = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.4,
            max_output_tokens=8192,
        ),
    )
    return response.text


def extract_json(raw: str) -> dict | None:
    """Extract JSON object from Gemini's response (may include extra text)."""
    import re
    # Try to find JSON block
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed: {e}")
        print(f"[DEBUG] Raw excerpt: {raw[:500]}")
        return None


def validate_events(data: dict) -> bool:
    """Basic schema validation."""
    if not isinstance(data, dict):
        return False
    if "events" not in data or not isinstance(data["events"], list):
        return False
    if len(data["events"]) == 0:
        return False
    required_event_keys = {"id", "rank", "category", "title", "summary", "actions"}
    for ev in data["events"]:
        if not required_event_keys.issubset(ev.keys()):
            print(f"[WARN] Event missing keys: {ev.get('title', '?')}")
            return False
    return True


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set. Exiting.")
        return

    print("[INFO] Fetching headlines from RSS feeds...")
    headlines = fetch_headlines()
    print(f"[INFO] Got {len(headlines)} headlines.")

    if not headlines:
        print("[WARN] No headlines fetched. Skipping update.")
        return

    print("[INFO] Loading existing events...")
    existing = load_existing_events()

    print("[INFO] Building Gemini prompt...")
    prompt = build_prompt(headlines, existing)

    print("[INFO] Calling Gemini Flash API...")
    try:
        raw = call_gemini(prompt)
    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {e}")
        raise SystemExit(1)

    print("[INFO] Extracting JSON from response...")
    data = extract_json(raw)

    if data is None:
        print("[ERROR] Could not extract valid JSON. Keeping existing events.")
        return

    if not validate_events(data):
        print("[ERROR] Events validation failed. Keeping existing events.")
        return

    # Ensure lastUpdated is set
    data["lastUpdated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[INFO] Writing {len(data['events'])} events to {EVENTS_FILE}...")
    with open(EVENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print("[SUCCESS] events.json updated.")
    for ev in data["events"]:
        print(f"  [{ev.get('rank','?')}] {ev.get('title','?')}")


if __name__ == "__main__":
    main()
