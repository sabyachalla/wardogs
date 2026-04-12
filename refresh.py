"""
War Dogs — Signal Refresh Script
Runs hourly via GitHub Actions.
Fetches headlines from free RSS feeds → sends to Google Gemini (free tier) → updates events.json
"""

import os
import sys
import json
import datetime
import feedparser
import google.generativeai as genai

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EVENTS_FILE    = "events.json"
MAX_HEADLINES  = 40

# Free RSS feeds — no API key required
RSS_FEEDS = [
    # Google News — reliable, broad coverage
    "https://news.google.com/rss/search?q=war+military+geopolitics&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=federal+reserve+interest+rates+inflation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=China+economy+trade+tariffs&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+technology+semiconductor+nvidia&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stock+market+S%26P500+earnings&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=oil+energy+OPEC+commodity+prices&hl=en-US&gl=US&ceid=US:en",
    # Yahoo Finance
    "https://finance.yahoo.com/rss/topfinstories",
    # CNBC
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    # MarketWatch
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    # BBC Business
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # NPR Economy
    "https://feeds.npr.org/1017/rss.xml",
]

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetch_headlines() -> list[dict]:
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
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:300]
                items.append({"title": title, "summary": summary[:200]})
        except Exception as e:
            print(f"[WARN] RSS fetch failed for {url}: {e}")
        if len(items) >= MAX_HEADLINES:
            break
    return items[:MAX_HEADLINES]


def load_existing
