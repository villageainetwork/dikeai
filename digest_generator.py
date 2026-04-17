"""
DIKE Pulse — Automated Digest Generator
Runs every Monday via GitHub Actions or manual trigger.
Fetches RSS feeds, generates AI analysis, updates digest data.
"""

import os
import json
import datetime
import xml.etree.ElementTree as ET
from groq import Groq

try:
    import requests
except ImportError:
    requests = None

# ─── RSS FEED SOURCES ────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "name": "EDPB (GDPR)",
        "url": "https://www.edpb.europa.eu/feed/news_en",
        "regulation": "GDPR",
        "tag": "gdpr",
        "jurisdiction": "EU"
    },
    {
        "name": "EU AI Office",
        "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",
        "regulation": "EU AI Act",
        "tag": "eu",
        "jurisdiction": "EU"
    },
    {
        "name": "MeitY Press Releases",
        "url": "https://www.meity.gov.in/rss-feeds/press-release",
        "regulation": "DPDP Act 2023",
        "tag": "dpdp",
        "jurisdiction": "India"
    },
    {
        "name": "NASSCOM",
        "url": "https://nasscom.in/feed",
        "regulation": "DPDP Act 2023",
        "tag": "dpdp",
        "jurisdiction": "India"
    },
]

# ─── PENALTY TRACKER ─────────────────────────────────────────────────────────
def fetch_penalty_data():
    """
    Fetch total GDPR fines from enforcementtracker.com.
    Returns dict with total_usd, period, source.
    """
    try:
        if not requests:
            raise Exception("requests not available")

        # enforcementtracker.com has a JSON API
        url = "https://www.enforcementtracker.com/ETid-1.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; DIKE-AI/1.0)"
        }
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            # Sum all fines
            total = 0
            for item in data:
                try:
                    fine = float(str(item.get("Fine", "0")).replace(",", "").replace("€", "").replace("$", "").strip())
                    total += fine
                except Exception:
                    pass
            if total > 0:
                quarter = get_current_quarter()
                return {
                    "penalty_total_usd": int(total),
                    "penalty_period": quarter,
                    "penalty_source": "GDPR Enforcement Tracker (enforcementtracker.com)"
                }
    except Exception:
        pass

    # Fallback — return last known figure
    return {
        "penalty_total_usd": 847000000,
        "penalty_period": get_current_quarter(),
        "penalty_source": "GDPR Enforcement Tracker + public reports"
    }


def get_current_quarter():
    """Return current quarter string like 'Q2 2026'."""
    now = datetime.datetime.now()
    q = (now.month - 1) // 3 + 1
    return f"Q{q} {now.year}"


# ─── RSS FETCHER ─────────────────────────────────────────────────────────────
def fetch_rss_items(feed, days_back=7):
    """Fetch items from an RSS feed published in the last N days."""
    try:
        if not requests:
            return []

        headers = {"User-Agent": "Mozilla/5.0 (compatible; DIKE-AI/1.0)"}
        resp = requests.get(feed["url"], headers=headers, timeout=15)

        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = []
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days_back)

        # Handle both RSS and Atom formats
        channel = root.find("channel")
        if channel is not None:
            entries = channel.findall("item")
        else:
            entries = root.findall("atom:entry", ns) or root.findall("entry")

        for entry in entries[:10]:  # max 10 per feed
            # Get title
            title_el = entry.find("title")
            title = title_el.text if title_el is not None else ""
            if not title:
                title_el = entry.find("atom:title", ns)
                title = title_el.text if title_el is not None else ""

            # Get description/summary
            desc_el = entry.find("description") or entry.find("summary") or entry.find("atom:summary", ns)
            desc = desc_el.text if desc_el is not None else ""

            # Get link
            link_el = entry.find("link")
            link = link_el.text if link_el is not None else ""
            if not link:
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""

            if title and len(title) > 10:
                items.append({
                    "title": title.strip(),
                    "description": (desc or "")[:500].strip(),
                    "link": link,
                    "regulation": feed["regulation"],
                    "tag": feed["tag"],
                    "source": feed["name"]
                })

        return items[:3]  # max 3 per feed

    except Exception:
        return []


# ─── AI DIGEST GENERATOR ─────────────────────────────────────────────────────
def generate_digest_item(item, groq_client):
    """Use Groq to generate impact analysis for a regulatory development."""
    prompt = f"""You are an expert AI governance analyst. Analyse this regulatory development and provide a structured assessment.

DEVELOPMENT:
Title: {item['title']}
Source: {item['source']}
Regulation: {item['regulation']}
Summary: {item['description']}

Provide a JSON response with exactly these fields:
{{
    "headline": "clear 10-15 word headline",
    "summary": "2 sentence plain English summary of what this means for organisations",
    "impact": "HIGH or MEDIUM or LOW",
    "score": 7.5,
    "has_deadline": false,
    "deadline": null
}}

Impact scoring guide:
- HIGH (7-10): Requires immediate action, new obligations, or significant penalties
- MEDIUM (4-6): Important to monitor, may require preparation
- LOW (1-3): Informational, minor updates

Respond ONLY with valid JSON. No other text."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip()
        # Clean JSON
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        return {
            "regulation": item["regulation"],
            "tag": item["tag"],
            "headline": parsed.get("headline", item["title"][:80]),
            "summary": parsed.get("summary", item["description"][:200]),
            "impact": parsed.get("impact", "MEDIUM"),
            "score": round(float(parsed.get("score", 5.0)), 1),
            "deadline": parsed.get("deadline"),
            "pro_only": False,
            "full_analysis": "",
            "source_url": item.get("link", "")
        }
    except Exception:
        # Fallback if AI fails
        return {
            "regulation": item["regulation"],
            "tag": item["tag"],
            "headline": item["title"][:100],
            "summary": item["description"][:200] if item["description"] else "See source for details.",
            "impact": "MEDIUM",
            "score": 5.0,
            "deadline": None,
            "pro_only": False,
            "full_analysis": "",
            "source_url": item.get("link", "")
        }


# ─── MAIN GENERATOR ──────────────────────────────────────────────────────────
def generate_weekly_digest():
    """
    Main function — fetches RSS feeds, generates AI analysis,
    returns complete digest data dict.
    """
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    # 1. Fetch penalty data
    penalty = fetch_penalty_data()

    # 2. Fetch RSS items from all feeds
    all_items = []
    for feed in RSS_FEEDS:
        items = fetch_rss_items(feed, days_back=7)
        all_items.extend(items)

    # 3. If no RSS items fetched (feeds down), return None
    if not all_items:
        return None

    # 4. Generate AI analysis for each item (max 5)
    developments = []
    for item in all_items[:5]:
        dev = generate_digest_item(item, groq_client)
        developments.append(dev)

    # 5. Mark last 2 as Pro only
    for i, dev in enumerate(developments):
        dev["pro_only"] = i >= 3

    # 6. Calculate stats
    action_required = sum(1 for d in developments if d["impact"] == "HIGH")

    # 7. Build digest
    now = datetime.datetime.now()
    week_of = now.strftime("%-d %B %Y") if os.name != "nt" else now.strftime("%d %B %Y").lstrip("0")

    digest = {
        "week_of": week_of,
        "total_developments": len(developments),
        "jurisdictions": len(set(d["tag"] for d in developments)),
        "action_required": action_required,
        "penalty_total_usd": penalty["penalty_total_usd"],
        "penalty_period": penalty["penalty_period"],
        "penalty_source": penalty["penalty_source"],
        "generated_at": now.isoformat(),
        "developments": developments
    }

    return digest


# ─── SAVE / LOAD DIGEST ──────────────────────────────────────────────────────
DIGEST_FILE = "digest_data.json"


def save_digest(digest):
    """Save digest to JSON file."""
    with open(DIGEST_FILE, "w") as f:
        json.dump(digest, f, indent=2)


def load_digest():
    """Load digest from JSON file. Returns None if not found."""
    try:
        if os.path.isfile(DIGEST_FILE):
            with open(DIGEST_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    print("Generating weekly digest...")
    digest = generate_weekly_digest()
    if digest:
        save_digest(digest)
        print(f"Done — {digest['total_developments']} developments generated")
        print(f"Penalty total: ${digest['penalty_total_usd']:,}")
    else:
        print("No RSS items fetched — using existing digest")

