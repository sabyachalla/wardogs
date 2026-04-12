"""
War Dogs — Signal Refresh Script
Runs hourly via GitHub Actions.
Fetches headlines from free RSS feeds → sends to Google Gemini (free tier) → updates events.json
"""

import os
import sys
import json
import datetime
import re
import requests
import feedparser
import time

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EVENTS_FILE    = "events.json"
MAX_HEADLINES  = 40

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=war+military+geopolitics&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=federal+reserve+interest+rates+inflation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=China+economy+trade+tariffs&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+technology+semiconductor+nvidia&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stock+market+S%26P500+earnings&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=oil+energy+OPEC+commodity+prices&hl=en-US&gl=US&ceid=US:en",
    "https://finance.yahoo.com/rss/topfinstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.npr.org/1017/rss.xml",
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fetch_headlines():
    seen  = set()
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = (entry.get("title") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                summary = re.sub(r"<[^>]+>", "", summary)[:200]
                items.append({"title": title, "summary": summary})
        except Exception as e:
            print(f"[WARN] RSS failed for {url}: {e}")
        if len(items) >= MAX_HEADLINES:
            break
    return items[:MAX_HEADLINES]


def load_existing_events():
    try:
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"events": []}


def build_prompt(headlines, existing):
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
2. Every recommendation MUST name the full ETF/stock and ticker.
3. Be explicit: BUY, SHORT, or ROTATE. Never vague.
4. Rank by impact: HIGH first, then MED, then LOW.
5. freshLabel = human-readable time like "2h ago", "just now"

Return ONLY valid JSON, no explanation, no markdown:

{{
  "lastUpdated": "ISO 8601 UTC timestamp",
  "scanSources": ["Reuters", "Yahoo Finance", "Google News", "Bloomberg"],
  "events": [
    {{
      "id": 1,
      "rank": "HIGH",
      "category": "milgeo",
      "catLabel": "Military-Geo",
      "title": "Short title",
      "summary": "2-3 sentence summary.",
      "fresh": true,
      "freshLabel": "2h ago",
      "risk": "HIGH",
      "window": "Active now — 4–8 week horizon",
      "actions": [
        {{"label": "BUY", "cls": "buy", "target": "Full ETF Name (TICKER)"}},
        {{"label": "SHORT", "cls": "short", "target": "Full ETF Name (TICKER)"}}
      ],
      "reasoning": "3-5 sentence explanation.",
      "timeFrame": {{
        "enter": "When to enter",
        "viable": "How long valid",
        "note": "Key exit trigger"
      }},
      "exitStrategy": "Specific exit conditions.",
      "gains": {{
        "conservative": "+5–8%",
        "conservativeNote": "If X happens",
        "base": "+12–18%",
        "baseNote": "Most likely scenario",
        "extended": "+25%+",
        "extendedNote": "If Y happens",
        "stopLoss": "-8% on TICKER"
      }},
      "adjacentMarkets": ["Gold (safe haven bid)"],
      "otherFactors": ["Factor to watch"]
    }}
  ]
}}"""


def call_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }
    for attempt in range(3):
        resp = requests.post(url, json=payload, timeout=90)
        if resp.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"[WARN] Rate limited. Waiting {wait}s (attempt {attempt+1}/3)...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise Exception("Rate limit exceeded after 3 retries.")


def extract_json(raw):
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed: {e}")
        print(f"[DEBUG] Raw: {raw[:500]}")
        return None


def validate_events(data):
    if not isinstance(data, dict):
        return False
    if "events" not in data or not isinstance(data["events"], list):
        return False
    if len(data["events"]) == 0:
        return False
    required = {"id", "rank", "category", "title", "summary", "actions"}
    for ev in data["events"]:
        if not required.issubset(ev.keys()):
            print(f"[WARN] Event missing keys: {ev.get('title', '?')}")
            return False
    return True


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set.")
        sys.exit(1)

    print("[INFO] Fetching headlines...")
    headlines = fetch_headlines()
    print(f"[INFO] Got {len(headlines)} headlines.")

    if not headlines:
        print("[ERROR] No headlines fetched.")
        sys.exit(1)

    existing = load_existing_events()
    prompt   = build_prompt(headlines, existing)

    print("[INFO] Calling Gemini API...")
    try:
        raw = call_gemini(prompt)
    except Exception as e:
        print(f"[ERROR] Gemini call failed: {e}")
        sys.exit(1)

    data = extract_json(raw)
    if data is None:
        print("[ERROR] Could not extract JSON.")
        sys.exit(1)

    if not validate_events(data):
        print("[ERROR] Validation failed.")
        sys.exit(1)

    data["lastUpdated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(EVENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[SUCCESS] Wrote {len(data['events'])} events.")
    for ev in data["events"]:
        print(f"  [{ev.get('rank','?')}] {ev.get('title','?')}")


if __name__ == "__main__":
    main()
