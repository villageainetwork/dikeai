import os
import csv
import datetime
import json


# ─── SUBSCRIBER STORAGE ──────────────────────────────────────────────────────
def save_subscriber(email, org_type, frequency, jurisdictions):
    """Save Pulse subscriber to Google Sheets or CSV fallback."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, email.strip().lower(), org_type, frequency, jurisdictions]

    # Try Google Sheets first
    sheet = get_pulse_sheet()
    if sheet:
        try:
            sheet.append_row(row)
            return True
        except Exception:
            pass

    # Fallback to CSV
    try:
        f = "pulse_subscribers.csv"
        exists = os.path.isfile(f)
        with open(f, "a", newline="") as fh:
            w = csv.writer(fh)
            if not exists:
                w.writerow(["timestamp", "email", "org_type", "frequency", "jurisdictions"])
            w.writerow(row)
        return True
    except Exception:
        return False


def get_pulse_sheet():
    """Get the Pulse subscribers sheet tab."""
    try:
        import gspread
        import json as json_mod
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json_mod.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = os.environ.get("GOOGLE_SHEET_ID",
                                   "1dXlj8xmCdk9CM44ctRoCucptFzJlH89oq2tSjw2FFsY")
        wb = client.open_by_key(sheet_id)
        # Use second sheet tab for Pulse subscribers
        try:
            return wb.worksheet("Pulse Subscribers")
        except Exception:
            ws = wb.add_worksheet(title="Pulse Subscribers", rows=1000, cols=10)
            ws.append_row(["timestamp", "email", "org_type", "frequency", "jurisdictions"])
            return ws
    except Exception:
        return None


# ─── DEADLINE DATA ────────────────────────────────────────────────────────────
def get_deadlines():
    today = datetime.date.today()

    deadlines = [
        {
            "regulation": "DPDP Act 2023",
            "name": "DPDP Rules enforcement begins",
            "date": datetime.date(2026, 6, 2),
            "tag": "dpdp",
            "action": "Action required",
        },
        {
            "regulation": "EU AI Act",
            "name": "High-risk AI system registration",
            "date": datetime.date(2026, 8, 28),
            "tag": "eu",
            "action": "Plan ahead",
        },
        {
            "regulation": "UAE PDPL",
            "name": "UAE PDPL full enforcement",
            "date": datetime.date(2026, 10, 31),
            "tag": "gcc",
            "action": "Monitor",
        },
        {
            "regulation": "GDPR",
            "name": "GDPR AI systems review",
            "date": datetime.date(2027, 2, 22),
            "tag": "gdpr",
            "action": "On track",
        },
    ]

    for d in deadlines:
        delta = (d["date"] - today).days
        d["days"] = max(0, delta)
        d["date_str"] = d["date"].strftime("%d %b %Y")
        # Urgency level
        if delta <= 60:
            d["urgency"] = "urgent"
        elif delta <= 180:
            d["urgency"] = "soon"
        else:
            d["urgency"] = "ok"
        # Progress bar — how close are we (100% = deadline passed)
        total_days = 365
        d["progress"] = min(100, max(5, int((1 - delta / total_days) * 100)))

    return deadlines


# ─── DIGEST DATA ──────────────────────────────────────────────────────────────
def get_latest_digest():
    """
    Returns the latest weekly digest entries.
    In production this would be AI-generated each Monday.
    For now returns curated static data — update manually each week.
    """
    return {
        "week_of": "14 April 2026",
        "total_developments": 5,
        "jurisdictions": 3,
        "action_required": 2,
        "penalty_total_usd": 847000000,
        "penalty_period": "Q1 2026",
        "penalty_source": "GDPR Enforcement Tracker + public reports",
        "developments": [
            {
                "regulation": "DPDP Act 2023",
                "tag": "dpdp",
                "headline": "MeitY releases draft DPDP Rules 2025 for public consultation",
                "summary": "Significant Data Fiduciaries must appoint India-based DPO and conduct annual third-party audits. Startups need to assess classification immediately.",
                "impact": "HIGH",
                "score": 9.1,
                "deadline": "2 Jun 2026",
                "pro_only": False,
                "full_analysis": "The draft rules introduce a two-tier compliance framework. Tier 1 organisations (Significant Data Fiduciaries) face the heaviest obligations including mandatory DPO appointment, annual audits, and 72-hour breach reporting. Startups processing data of more than 1 lakh users or handling sensitive personal data are likely to qualify. Required actions: (1) Assess whether you qualify as a Significant Data Fiduciary, (2) Begin DPO identification process, (3) Map all personal data flows and document consent mechanisms, (4) Prepare breach notification procedures, (5) Engage a CERT-In empanelled auditor."
            },
            {
                "regulation": "EU AI Act",
                "tag": "eu",
                "headline": "EU AI Office publishes high-risk AI system classification guidance",
                "summary": "Indian companies with EU operations must register high-risk AI systems by August 2026. HR, credit scoring, and education AI explicitly listed.",
                "impact": "HIGH",
                "score": 8.4,
                "deadline": "28 Aug 2026",
                "pro_only": False,
                "full_analysis": "The guidance clarifies which AI systems require conformity assessments before deployment. Key systems now classified as high-risk include: automated CV screening, credit scoring algorithms, student assessment tools, and biometric categorisation. Required actions: (1) Audit all AI systems for high-risk classification, (2) Implement human oversight mechanisms, (3) Document AI training data governance, (4) Register systems in EU AI database before August deadline, (5) Appoint an EU-based authorised representative if you have no EU establishment."
            },
            {
                "regulation": "UAE PDPL",
                "tag": "gcc",
                "headline": "UAE TDRA issues new data localisation guidelines for fintechs",
                "summary": "Financial data must be stored on UAE-based servers. 90-day transition window for existing systems processing UAE user data.",
                "impact": "MEDIUM",
                "score": 6.2,
                "deadline": None,
                "pro_only": False,
                "full_analysis": ""
            },
            {
                "regulation": "GDPR",
                "tag": "gdpr",
                "headline": "EDPB clarifies AI training data rules under GDPR Article 6",
                "summary": "Legitimate interest cannot justify scraping public data for AI training. Explicit consent required.",
                "impact": "MEDIUM",
                "score": 7.8,
                "deadline": None,
                "pro_only": True,
                "full_analysis": ""
            },
            {
                "regulation": "DPDP Act 2023",
                "tag": "dpdp",
                "headline": "Data Protection Board announces first enforcement cases",
                "summary": "Initial cases focus on consent mechanism failures in B2C apps.",
                "impact": "LOW",
                "score": 5.1,
                "deadline": None,
                "pro_only": True,
                "full_analysis": ""
            },
        ]
    }


# ─── CALENDAR DATA ────────────────────────────────────────────────────────────
def get_calendar():
    return [
        {
            "month": "April 2026",
            "events": [
                {"name": "EU AI Act prohibited systems ban effective", "date": "26 Apr 2026", "color": "#185FA5"},
                {"name": "DPDP public consultation closes", "date": "30 Apr 2026", "color": "#E24B4A"},
            ]
        },
        {
            "month": "May 2026",
            "events": [
                {"name": "DPDP Rules gazette notification expected", "date": "Mid May 2026", "color": "#E24B4A"},
                {"name": "UAE PDPL cross-border transfer rules update", "date": "15 May 2026", "color": "#EF9F27"},
            ]
        },
        {
            "month": "June 2026",
            "events": [
                {"name": "DPDP Act enforcement begins", "date": "2 Jun 2026", "color": "#E24B4A"},
                {"name": "EU AI Act GPAI model obligations effective", "date": "12 Jun 2026", "color": "#185FA5"},
            ]
        },
    ]