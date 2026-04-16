# DIKE AI v1.2 - Email capture + Monitor PDF
from flask import Flask, request, render_template_string, make_response, session, redirect, url_for
from monitor import analyse_impact, ORG_TYPES
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm
from groq import Groq
import datetime
import io
import json
import os
import csv
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = "governance-audit-secret-key-2024"

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

REGULATIONS = {
    "DPDP Act 2023": {
        "description": "India's Digital Personal Data Protection Act",
        "checklist": """
1. Is there a clear data retention period specified?
2. Is there a grievance redressal mechanism with contact details?
3. Is consent obtained before sharing data with third parties?
4. Is there a provision for users to request data deletion?
5. Are special protections in place for children's data?
6. Is the purpose of data collection clearly stated?
7. Is there a data fiduciary contact or DPO identified?
"""
    },
    "GDPR": {
        "description": "EU General Data Protection Regulation",
        "checklist": """
1. Is a lawful basis for data processing specified?
2. Is there a clear data retention period?
3. Is the right to erasure (right to be forgotten) mentioned?
4. Is data portability offered to users?
5. Are cross-border data transfer safeguards mentioned?
6. Is there a breach notification procedure within 72 hours?
7. Is a Data Protection Officer (DPO) appointed or mentioned?
8. Is there explicit consent for profiling or automated decisions?
"""
    },
    "EU AI Act": {
        "description": "European Union Artificial Intelligence Act",
        "checklist": """
1. Is the AI system risk level identified (prohibited/high-risk/limited/minimal)?
2. Is there a human oversight mechanism described?
3. Is there transparency about AI-generated outputs to users?
4. Are accuracy, robustness and cybersecurity of the AI addressed?
5. Are data governance practices for AI training data described?
6. Is there a conformity assessment or audit process mentioned?
7. Are there provisions for logging and traceability of AI decisions?
8. Is there a process for users to contest AI-generated decisions?
"""
    },
    "UAE PDPL": {
        "description": "UAE Personal Data Protection Law",
        "checklist": """
1. Is consent obtained before collecting personal data?
2. Is the purpose of data processing clearly stated?
3. Are data subject rights (access, correction, deletion) mentioned?
4. Are cross-border data transfer restrictions addressed?
5. Is there a data breach notification procedure?
6. Is a data controller or responsible person identified?
7. Are sensitive data categories given additional protection?
"""
    }
}

# ─── EMAIL STORAGE ────────────────────────────────────────────────────────────
def get_sheet():
    """Get the Google Sheet. Returns None if credentials not available."""
    try:
        import gspread
        import json as json_mod
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Try environment variable first (Railway production)
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json_mod.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            # Fallback to local file (local development)
            creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = os.environ.get("GOOGLE_SHEET_ID", "1dXlj8xmCdk9CM44ctRoCucptFzJlH89oq2tSjw2FFsY")
        return client.open_by_key(sheet_id).sheet1
    except Exception:
        return None


def save_email(email, source, regulation=""):
    """Save email to Google Sheets. Falls back to CSV if Sheets unavailable."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, email.strip().lower(), source, regulation]

    # Try Google Sheets first
    sheet = get_sheet()
    if sheet:
        try:
            sheet.append_row(row)
            return
        except Exception:
            pass

    # Fallback to CSV
    try:
        emails_file = "emails.csv"
        file_exists = os.path.isfile(emails_file)
        with open(emails_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "email", "source", "regulation"])
            writer.writerow(row)
    except Exception:
        pass


# ─── HTML PAGE (AUDIT) ────────────────────────────────────────────────────────
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DIKE AI — Governance Audit</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'DM Sans', sans-serif; background: #f4f4f2; min-height: 100vh; }

        .topbar { background: #ffffff; border-bottom: 0.5px solid #e8e8e5; padding: 0 32px; display: flex; align-items: center; justify-content: space-between; height: 56px; position: sticky; top: 0; z-index: 100; }
        .logo { display: flex; align-items: center; gap: 10px; }
        .logo-mark { width: 28px; height: 28px; background: #185FA5; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .logo-mark svg { width: 16px; height: 16px; }
        .logo-text { font-size: 15px; font-weight: 500; color: #111; letter-spacing: -0.01em; }
        .logo-badge { font-family: 'DM Mono', monospace; font-size: 10px; background: #E6F1FB; color: #185FA5; padding: 2px 7px; border-radius: 4px; font-weight: 500; }
        .nav { display: flex; gap: 4px; }
        .nav a { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; text-decoration: none; transition: all 0.15s; border: 0.5px solid transparent; }
        .nav a.active { background: #185FA5; color: white; border-color: #185FA5; }
        .nav a.inactive { color: #666; border-color: #ddd; }
        .nav a.inactive:hover { background: #f4f4f2; color: #111; }

        .body { max-width: 760px; margin: 0 auto; padding: 40px 24px 60px; }

        .hero { margin-bottom: 32px; }
        .hero-eyebrow { font-family: 'DM Mono', monospace; font-size: 11px; color: #185FA5; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
        .hero-dot { width: 6px; height: 6px; border-radius: 50%; background: #185FA5; display: inline-block; flex-shrink: 0; }
        .hero h1 { font-size: 26px; font-weight: 300; color: #111; letter-spacing: -0.02em; line-height: 1.25; margin: 0 0 8px; }
        .hero h1 strong { font-weight: 500; }
        .hero p { font-size: 14px; color: #777; line-height: 1.6; margin: 0; max-width: 480px; }

        .card { background: #ffffff; border-radius: 12px; border: 0.5px solid #e8e8e5; padding: 28px; margin-bottom: 16px; }

        .section-label { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #999; margin-bottom: 10px; display: block; }

        .reg-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 24px; }
        .reg-option { border: 0.5px solid #e8e8e5; border-radius: 8px; padding: 12px 14px; cursor: pointer; transition: all 0.15s; background: #f9f9f7; }
        .reg-option:hover { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected .reg-name { color: #185FA5; }
        .reg-name { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 2px; }
        .reg-desc-text { font-size: 11px; color: #999; line-height: 1.4; }

        .textarea-wrap { position: relative; }
        .dike-textarea { width: 100%; min-height: 160px; padding: 14px 16px; border: 0.5px solid #ddd; border-radius: 8px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; background: #ffffff; resize: vertical; line-height: 1.6; outline: none; transition: border-color 0.15s; }
        .dike-textarea:focus { border-color: #185FA5; }
        .dike-textarea::placeholder { color: #bbb; }
        .char-count { position: absolute; bottom: 10px; right: 12px; font-size: 11px; color: #bbb; font-family: 'DM Mono', monospace; pointer-events: none; }

        .loading-bar { height: 2px; background: #eee; border-radius: 2px; margin-top: 14px; overflow: hidden; display: none; }
        .loading-fill { height: 100%; width: 0%; background: #185FA5; border-radius: 2px; transition: width 0.3s ease; }
        .loading-text { font-size: 12px; color: #999; margin-top: 8px; font-family: 'DM Mono', monospace; display: none; }

        .submit-btn { width: 100%; padding: 13px; background: #185FA5; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 20px; transition: background 0.15s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .submit-btn:hover { background: #0C447C; }
        .submit-btn svg { width: 16px; height: 16px; flex-shrink: 0; }

        .divider { display: flex; align-items: center; gap: 12px; margin: 28px 0; }
        .divider-line { flex: 1; height: 0.5px; background: #e8e8e5; }
        .divider-text { font-size: 11px; color: #bbb; font-family: 'DM Mono', monospace; white-space: nowrap; }

        .results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .results-title { font-size: 13px; font-weight: 500; color: #111; }
        .reg-pill { font-family: 'DM Mono', monospace; font-size: 10px; background: #E6F1FB; color: #185FA5; padding: 3px 9px; border-radius: 4px; font-weight: 500; }

        .score-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
        .score-box { background: #f9f9f7; border-radius: 8px; padding: 14px; text-align: center; }
        .score-num { font-size: 28px; font-weight: 300; letter-spacing: -0.02em; margin-bottom: 2px; }
        .score-lbl { font-size: 10px; color: #999; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; }
        .fail-num { color: #A32D2D; }
        .pass-num { color: #0F6E56; }
        .partial-num { color: #854F0B; }

        .result-item { display: flex; gap: 12px; align-items: flex-start; padding: 13px; border-radius: 8px; border: 0.5px solid #e8e8e5; margin-bottom: 8px; background: #f9f9f7; }
        .badge { font-size: 10px; font-family: 'DM Mono', monospace; font-weight: 500; padding: 3px 8px; border-radius: 4px; white-space: nowrap; margin-top: 1px; flex-shrink: 0; }
        .FAIL { background: #FCEBEB; color: #791F1F; }
        .PASS { background: #E1F5EE; color: #085041; }
        .PARTIAL { background: #FAEEDA; color: #633806; }
        .result-text { font-size: 13px; color: #555; line-height: 1.5; }

        /* Email capture box */
        .email-gate { background: #f0f6ff; border: 0.5px solid #c5d9f0; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .email-gate-title { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 4px; }
        .email-gate-sub { font-size: 12px; color: #777; margin-bottom: 14px; line-height: 1.5; }
        .email-row { display: flex; gap: 8px; }
        .email-input { flex: 1; padding: 10px 14px; border: 0.5px solid #c5d9f0; border-radius: 7px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; outline: none; background: white; transition: border-color 0.15s; }
        .email-input:focus { border-color: #185FA5; }
        .email-input::placeholder { color: #bbb; }
        .email-btn { padding: 10px 18px; background: #185FA5; color: white; border: none; border-radius: 7px; font-size: 13px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; white-space: nowrap; transition: background 0.15s; display: flex; align-items: center; gap: 6px; }
        .email-btn:hover { background: #0C447C; }
        .email-btn svg { width: 14px; height: 14px; flex-shrink: 0; }
        .email-success { font-size: 12px; color: #0F6E56; margin-top: 8px; display: none; font-family: 'DM Mono', monospace; }

        /* Download button - shown after email */
        .download-btn { width: 100%; padding: 11px; background: transparent; color: #0F6E56; border: 0.5px solid #1D9E75; border-radius: 8px; font-size: 13px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 12px; transition: all 0.15s; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .download-btn:hover { background: #E1F5EE; }
        .download-btn svg { width: 14px; height: 14px; flex-shrink: 0; }

        .footer { text-align: center; font-size: 11px; color: #bbb; margin-top: 32px; padding-top: 20px; border-top: 0.5px solid #e8e8e5; font-family: 'DM Mono', monospace; }
        .footer a { color: #185FA5; text-decoration: none; }

        @media (max-width: 540px) {
            .topbar { padding: 0 16px; }
            .body { padding: 24px 16px 48px; }
            .reg-grid { grid-template-columns: 1fr; }
            .logo-badge { display: none; }
            .email-row { flex-direction: column; }
        }
    </style>
</head>
<body>

<div class="topbar">
    <div class="logo">
        <div class="logo-mark">
            <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="5" height="12" rx="1" fill="white" opacity="0.9"/>
                <rect x="9" y="2" width="5" height="7" rx="1" fill="white" opacity="0.6"/>
                <rect x="9" y="11" width="5" height="3" rx="1" fill="white" opacity="0.6"/>
            </svg>
        </div>
        <span class="logo-text">DIKE AI</span>
        <span class="logo-badge">v1.2</span>
    </div>
    <div class="nav">
        <a href="/" class="active">DIKE Audit</a>
        <a href="/monitor" class="inactive">DIKE Monitor</a>
        <a href="/pulse" class="inactive">DIKE Pulse</a>
    </div>
</div>

<div class="body">
    <div class="hero">
        <div class="hero-eyebrow"><span class="hero-dot"></span> AI Governance Compliance</div>
        <h1>Audit your policy<br><strong>against global regulations</strong></h1>
        <p>Paste any privacy policy or data governance document and get an instant compliance check across major frameworks.</p>
    </div>

    <div class="card">
        <form method="POST" action="/" id="audit-form">
            <span class="section-label">Select regulation</span>
            <div class="reg-grid">
                {% for reg_name, reg_data in regulations.items() %}
                <div class="reg-option {% if reg_name == selected_reg %}selected{% endif %}"
                     onclick="selectReg(this, '{{ reg_name }}')">
                    <div class="reg-name">{{ reg_name }}</div>
                    <div class="reg-desc-text">{{ reg_data.description }}</div>
                </div>
                {% endfor %}
            </div>
            <input type="hidden" name="regulation" id="regulation-input" value="{{ selected_reg }}">

            <span class="section-label">Paste policy document</span>
            <div class="textarea-wrap">
                <textarea class="dike-textarea" name="policy" id="policy-input"
                    placeholder="Paste your company privacy policy or data governance document here..."
                    oninput="updateCount()">{{ policy }}</textarea>
                <span class="char-count" id="char-count">0 words</span>
            </div>

            <div class="loading-bar" id="loading-bar"><div class="loading-fill" id="loading-fill"></div></div>
            <div class="loading-text" id="loading-text">Analysing document...</div>

            <button type="submit" class="submit-btn" onclick="startLoading()">
                <svg viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Analyse document
            </button>
        </form>
    </div>

    {% if results %}
    <div class="divider">
        <div class="divider-line"></div>
        <div class="divider-text">audit results</div>
        <div class="divider-line"></div>
    </div>

    <div class="card">
        <div class="results-header">
            <span class="results-title">Compliance report</span>
            <span class="reg-pill">{{ selected_reg }}</span>
        </div>
        <div class="score-row">
            <div class="score-box">
                <div class="score-num pass-num">{{ pass_count }}</div>
                <div class="score-lbl">Pass</div>
            </div>
            <div class="score-box">
                <div class="score-num partial-num">{{ partial_count }}</div>
                <div class="score-lbl">Partial</div>
            </div>
            <div class="score-box">
                <div class="score-num fail-num">{{ fail_count }}</div>
                <div class="score-lbl">Fail</div>
            </div>
        </div>
        {% for item in results %}
        <div class="result-item">
            <span class="badge {{ item.status }}">{{ item.status }}</span>
            <span class="result-text">{{ item.explanation }}</span>
        </div>
        {% endfor %}

        <!-- Email gate before PDF download -->
        {% if email_captured %}
        <form method="POST" action="/download-pdf">
            <button type="submit" class="download-btn">
                <svg viewBox="0 0 16 16" fill="none"><path d="M8 2v8M4 7l4 4 4-4M2 13h12" stroke="#0F6E56" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Download PDF report
            </button>
        </form>
        {% else %}
        <div class="email-gate">
            <div class="email-gate-title">Download your compliance report</div>
            <div class="email-gate-sub">Enter your email to get the PDF report. We will also keep you updated on regulatory changes that affect your organisation.</div>
            <form method="POST" action="/capture-email" id="email-form">
                <input type="hidden" name="regulation" value="{{ selected_reg }}">
                <div class="email-row">
                    <input type="email" name="email" class="email-input" placeholder="your@email.com" required>
                    <button type="submit" class="email-btn">
                        <svg viewBox="0 0 16 16" fill="none"><path d="M8 2v8M4 7l4 4 4-4M2 13h12" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        Get PDF
                    </button>
                </div>
            </form>
            <div class="email-success" id="email-success">Email saved — downloading your report now.</div>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <div class="footer">
        Powered by <a href="https://strategicpolicylab.com">Strategic Policy Lab</a> &nbsp;&middot;&nbsp; Built with Groq + LLaMA 3.3
    </div>
</div>

<script>
function selectReg(el, name) {
    document.querySelectorAll('.reg-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('regulation-input').value = name;
}
function updateCount() {
    const val = document.getElementById('policy-input').value.trim();
    const words = val ? val.split(/ +/).length : 0;
    document.getElementById('char-count').textContent = words + ' words';
}
function startLoading() {
    const bar = document.getElementById('loading-bar');
    const fill = document.getElementById('loading-fill');
    const txt = document.getElementById('loading-text');
    bar.style.display = 'block';
    txt.style.display = 'block';
    let p = 0;
    const iv = setInterval(() => {
        p += Math.random() * 12;
        if (p >= 90) { p = 90; clearInterval(iv); }
        fill.style.width = p + '%';
    }, 300);
}
document.addEventListener('DOMContentLoaded', updateCount);
</script>
</body>
</html>
"""

# ─── MONITOR PAGE ─────────────────────────────────────────────────────────────
MONITOR_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DIKE Monitor — Regulatory Impact Analyser</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'DM Sans', sans-serif; background: #f4f4f2; min-height: 100vh; }

        .topbar { background: #ffffff; border-bottom: 0.5px solid #e8e8e5; padding: 0 32px; display: flex; align-items: center; justify-content: space-between; height: 56px; position: sticky; top: 0; z-index: 100; }
        .logo { display: flex; align-items: center; gap: 10px; }
        .logo-mark { width: 28px; height: 28px; background: #185FA5; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .logo-mark svg { width: 16px; height: 16px; }
        .logo-text { font-size: 15px; font-weight: 500; color: #111; letter-spacing: -0.01em; }
        .logo-badge { font-family: 'DM Mono', monospace; font-size: 10px; background: #E6F1FB; color: #185FA5; padding: 2px 7px; border-radius: 4px; font-weight: 500; }
        .nav { display: flex; gap: 4px; }
        .nav a { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; text-decoration: none; transition: all 0.15s; border: 0.5px solid transparent; }
        .nav a.active { background: #185FA5; color: white; border-color: #185FA5; }
        .nav a.inactive { color: #666; border-color: #ddd; }
        .nav a.inactive:hover { background: #f4f4f2; color: #111; }

        .body { max-width: 760px; margin: 0 auto; padding: 40px 24px 60px; }

        .hero { margin-bottom: 32px; }
        .hero-eyebrow { font-family: 'DM Mono', monospace; font-size: 11px; color: #185FA5; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
        .hero-dot { width: 6px; height: 6px; border-radius: 50%; background: #185FA5; display: inline-block; flex-shrink: 0; }
        .hero h1 { font-size: 26px; font-weight: 300; color: #111; letter-spacing: -0.02em; line-height: 1.25; margin: 0 0 8px; }
        .hero h1 strong { font-weight: 500; }
        .hero p { font-size: 14px; color: #777; line-height: 1.6; margin: 0; max-width: 480px; }

        .card { background: #ffffff; border-radius: 12px; border: 0.5px solid #e8e8e5; padding: 28px; margin-bottom: 16px; }
        .section-label { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #999; margin-bottom: 10px; display: block; }

        .reg-option { border: 0.5px solid #e8e8e5; border-radius: 8px; padding: 12px 14px; cursor: pointer; transition: all 0.15s; background: #f9f9f7; }
        .reg-option:hover { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected .reg-name { color: #185FA5; }
        .reg-name { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 2px; }

        .dike-textarea { width: 100%; min-height: 160px; padding: 14px 16px; border: 0.5px solid #ddd; border-radius: 8px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; background: #ffffff; resize: vertical; line-height: 1.6; outline: none; transition: border-color 0.15s; }
        .dike-textarea:focus { border-color: #185FA5; }
        .dike-textarea::placeholder { color: #bbb; }

        .loading-bar { height: 2px; background: #eee; border-radius: 2px; margin-top: 14px; overflow: hidden; display: none; }
        .loading-fill { height: 100%; width: 0%; background: #185FA5; border-radius: 2px; transition: width 0.3s ease; }
        .loading-text { font-size: 12px; color: #999; margin-top: 8px; font-family: 'DM Mono', monospace; display: none; }

        .submit-btn { width: 100%; padding: 13px; background: #185FA5; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 20px; transition: background 0.15s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .submit-btn:hover { background: #0C447C; }
        .submit-btn svg { width: 16px; height: 16px; flex-shrink: 0; }

        .divider { display: flex; align-items: center; gap: 12px; margin: 28px 0; }
        .divider-line { flex: 1; height: 0.5px; background: #e8e8e5; }
        .divider-text { font-size: 11px; color: #bbb; font-family: 'DM Mono', monospace; white-space: nowrap; }

        .results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }
        .results-title { font-size: 13px; font-weight: 500; color: #111; }
        .impact-badge { font-family: 'DM Mono', monospace; font-size: 10px; padding: 3px 9px; border-radius: 4px; font-weight: 500; }
        .HIGH { background: #FCEBEB; color: #791F1F; }
        .MEDIUM { background: #FAEEDA; color: #633806; }
        .LOW { background: #E1F5EE; color: #085041; }

        .section-block { margin-bottom: 20px; padding-bottom: 20px; border-bottom: 0.5px solid #f0f0ee; }
        .section-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .section-heading { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #185FA5; margin-bottom: 8px; }
        .section-body { font-size: 13px; color: #555; line-height: 1.7; white-space: pre-wrap; }

        /* Download button - same style as audit */
        .download-btn { width: 100%; padding: 11px; background: transparent; color: #0F6E56; border: 0.5px solid #1D9E75; border-radius: 8px; font-size: 13px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 20px; transition: all 0.15s; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .download-btn:hover { background: #E1F5EE; }
        .download-btn svg { width: 14px; height: 14px; flex-shrink: 0; }

        .footer { text-align: center; font-size: 11px; color: #bbb; margin-top: 32px; padding-top: 20px; border-top: 0.5px solid #e8e8e5; font-family: 'DM Mono', monospace; }
        .footer a { color: #185FA5; text-decoration: none; }

        /* Email gate - same as audit */
        .email-gate { background: #f0f6ff; border: 0.5px solid #c5d9f0; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .email-gate-title { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 4px; }
        .email-gate-sub { font-size: 12px; color: #777; margin-bottom: 14px; line-height: 1.5; }
        .email-row { display: flex; gap: 8px; }
        .email-input { flex: 1; padding: 10px 14px; border: 0.5px solid #c5d9f0; border-radius: 7px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; outline: none; background: white; transition: border-color 0.15s; }
        .email-input:focus { border-color: #185FA5; }
        .email-input::placeholder { color: #bbb; }
        .email-btn { padding: 10px 18px; background: #185FA5; color: white; border: none; border-radius: 7px; font-size: 13px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; white-space: nowrap; transition: background 0.15s; display: flex; align-items: center; gap: 6px; }
        .email-btn:hover { background: #0C447C; }
        .email-btn svg { width: 14px; height: 14px; flex-shrink: 0; }

        @media (max-width: 540px) {
            .topbar { padding: 0 16px; }
            .body { padding: 24px 16px 48px; }
            .logo-badge { display: none; }
            .email-row { flex-direction: column; }
        }
    </style>
</head>
<body>

<div class="topbar">
    <div class="logo">
        <div class="logo-mark">
            <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="5" height="12" rx="1" fill="white" opacity="0.9"/>
                <rect x="9" y="2" width="5" height="7" rx="1" fill="white" opacity="0.6"/>
                <rect x="9" y="11" width="5" height="3" rx="1" fill="white" opacity="0.6"/>
            </svg>
        </div>
        <span class="logo-text">DIKE AI</span>
        <span class="logo-badge">v1.2</span>
    </div>
    <div class="nav">
        <a href="/" class="inactive">DIKE Audit</a>
        <a href="/monitor" class="active">DIKE Monitor</a>
        <a href="/pulse" class="inactive">DIKE Pulse</a>
    </div>
</div>

<div class="body">
    <div class="hero">
        <div class="hero-eyebrow"><span class="hero-dot"></span> AI Monitoring Intelligence</div>
        <h1>Monitor emerging<br><strong>regulatory developments</strong></h1>
        <p>Analyse the impact of new regulatory changes on your organisation type, powered by real-time AI analysis.</p>
    </div>

    <div class="card">
        <form method="POST" action="/monitor" id="monitor-form">
            <span class="section-label">Organisation type</span>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 24px;">
                {% for org in org_types %}
                <div class="reg-option {% if org == selected_org %}selected{% endif %}"
                     onclick="selectOrg(this, '{{ org }}')">
                    <div class="reg-name">{{ org }}</div>
                </div>
                {% endfor %}
            </div>
            <input type="hidden" name="org_type" id="org-input" value="{{ selected_org }}">

            <span class="section-label">Paste regulatory update or news</span>
            <textarea class="dike-textarea" name="regulatory_text"
                placeholder="Paste any regulatory update, policy announcement, new law, or compliance news here...">{{ regulatory_text }}</textarea>

            <div class="loading-bar" id="loading-bar"><div class="loading-fill" id="loading-fill"></div></div>
            <div class="loading-text" id="loading-text">Analysing regulatory impact...</div>

            <button type="submit" class="submit-btn" onclick="startLoading()">
                <svg viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Analyse impact
            </button>
        </form>
    </div>

    {% if sections %}
    <div class="divider">
        <div class="divider-line"></div>
        <div class="divider-text">impact analysis</div>
        <div class="divider-line"></div>
    </div>

    <div class="card">
        <div class="results-header">
            <span class="results-title">Impact report &mdash; {{ selected_org }}</span>
            <span class="impact-badge {{ impact_level }}">{{ impact_level }} IMPACT</span>
        </div>
        {% for section in sections %}
        <div class="section-block">
            <div class="section-heading">{{ section.title }}</div>
            <div class="section-body">{{ section.content }}</div>
        </div>
        {% endfor %}

        <!-- Email gate before Monitor PDF download -->
        {% if monitor_email_captured %}
        <form method="POST" action="/download-monitor-pdf">
            <input type="hidden" name="selected_org" value="{{ selected_org }}">
            <input type="hidden" name="impact_level" value="{{ impact_level }}">
            <input type="hidden" name="sections_json" value="{{ sections | tojson | e }}">
            <button type="submit" class="download-btn">
                <svg viewBox="0 0 16 16" fill="none"><path d="M8 2v8M4 7l4 4 4-4M2 13h12" stroke="#0F6E56" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Download impact report PDF
            </button>
        </form>
        {% else %}
        <div class="email-gate">
            <div class="email-gate-title">Download your impact report</div>
            <div class="email-gate-sub">Enter your email to get the PDF report. We will keep you updated on regulatory changes relevant to your organisation.</div>
            <form method="POST" action="/capture-monitor-email">
                <input type="hidden" name="selected_org" value="{{ selected_org }}">
                <input type="hidden" name="impact_level" value="{{ impact_level }}">
                <input type="hidden" name="sections_json" value="{{ sections | tojson | e }}">
                <div class="email-row">
                    <input type="email" name="email" class="email-input" placeholder="your@email.com" required>
                    <button type="submit" class="email-btn">
                        <svg viewBox="0 0 16 16" fill="none"><path d="M8 2v8M4 7l4 4 4-4M2 13h12" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        Get PDF
                    </button>
                </div>
            </form>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <div class="footer">
        Powered by <a href="https://strategicpolicylab.com">Strategic Policy Lab</a> &nbsp;&middot;&nbsp; Built with Groq + LLaMA 3.3
    </div>
</div>

<script>
function startLoading() {
    const bar = document.getElementById('loading-bar');
    const fill = document.getElementById('loading-fill');
    const txt = document.getElementById('loading-text');
    bar.style.display = 'block';
    txt.style.display = 'block';
    let p = 0;
    const iv = setInterval(() => {
        p += Math.random() * 12;
        if (p >= 90) { p = 90; clearInterval(iv); }
        fill.style.width = p + '%';
    }, 300);
}
function selectOrg(el, name) {
    document.querySelectorAll('.reg-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('org-input').value = name;
}
</script>
</body>
</html>
"""


# ─── PARSERS ──────────────────────────────────────────────────────────────────
PULSE_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DIKE Pulse — Regulatory Intelligence Digest</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'DM Sans', sans-serif; background: #f4f4f2; min-height: 100vh; }
        .topbar { background: #fff; border-bottom: 0.5px solid #e8e8e5; padding: 0 32px; display: flex; align-items: center; justify-content: space-between; height: 56px; position: sticky; top: 0; z-index: 100; }
        .logo { display: flex; align-items: center; gap: 10px; }
        .logo-mark { width: 28px; height: 28px; background: #185FA5; border-radius: 6px; display: flex; align-items: center; justify-content: center; }
        .logo-mark svg { width: 16px; height: 16px; }
        .logo-text { font-size: 15px; font-weight: 500; color: #111; }
        .logo-badge { font-family: 'DM Mono', monospace; font-size: 10px; background: #E6F1FB; color: #185FA5; padding: 2px 7px; border-radius: 4px; }
        .nav { display: flex; gap: 4px; }
        .nav a { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; text-decoration: none; border: 0.5px solid transparent; transition: all 0.15s; }
        .nav a.active { background: #185FA5; color: white; border-color: #185FA5; }
        .nav a.inactive { color: #666; border-color: #ddd; }
        .nav a.inactive:hover { background: #f4f4f2; color: #111; }
        .body { max-width: 760px; margin: 0 auto; padding: 36px 24px 60px; }
        .hero { margin-bottom: 24px; }
        .eyebrow { font-family: 'DM Mono', monospace; font-size: 11px; color: #185FA5; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .hero-dot { width: 6px; height: 6px; border-radius: 50%; background: #185FA5; display: inline-block; }
        .hero h1 { font-size: 26px; font-weight: 300; color: #111; letter-spacing: -0.02em; line-height: 1.25; margin: 0 0 8px; }
        .hero h1 strong { font-weight: 500; }
        .hero p { font-size: 14px; color: #777; line-height: 1.6; max-width: 520px; }
        .card { background: #fff; border-radius: 12px; border: 0.5px solid #e8e8e5; padding: 24px; margin-bottom: 16px; }
        .slabel { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #999; margin-bottom: 10px; display: block; }

        /* Stats banner */
        .stats-banner { background: #185FA5; border-radius: 12px; padding: 18px 24px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
        .sb-item { text-align: center; }
        .sb-num { font-size: 28px; font-weight: 300; color: white; letter-spacing: -0.02em; line-height: 1; margin-bottom: 4px; }
        .sb-lbl { font-size: 10px; color: rgba(255,255,255,0.7); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'DM Mono', monospace; }

        /* Penalty box */
        .penalty-box { background: #1a1a2e; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
        .penalty-left {}
        .penalty-label { font-family: 'DM Mono', monospace; font-size: 10px; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px; }
        .penalty-amount { font-size: 32px; font-weight: 300; color: #ff6b6b; letter-spacing: -0.03em; line-height: 1; margin-bottom: 4px; }
        .penalty-period { font-size: 12px; color: rgba(255,255,255,0.5); }
        .penalty-source { font-size: 10px; color: rgba(255,255,255,0.35); font-family: 'DM Mono', monospace; margin-top: 2px; }
        .penalty-right { text-align: right; }
        .penalty-cta { font-size: 12px; color: rgba(255,255,255,0.7); line-height: 1.5; max-width: 200px; }
        .penalty-cta strong { color: white; }

        /* Deadline tracker */
        .dl-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        .dl-item { border-radius: 8px; padding: 14px; border: 0.5px solid #e8e8e5; }
        .dl-urgent { background: #fde8e8; border-color: #f09595; }
        .dl-soon { background: #fdf3c8; border-color: #fac775; }
        .dl-ok { background: #f9f9f7; }
        .dl-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
        .dl-reg { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 4px; }
        .tag-dpdp { background: #E6F1FB; color: #0C447C; }
        .tag-eu { background: #EAF3DE; color: #3B6D11; }
        .tag-gcc { background: #FAEEDA; color: #633806; }
        .tag-gdpr { background: #EEEDFE; color: #3C3489; }
        .dl-days { font-size: 22px; font-weight: 300; color: #111; letter-spacing: -0.02em; }
        .dl-days-lbl { font-size: 11px; color: #999; margin-left: 2px; }
        .dl-name { font-size: 12px; font-weight: 500; color: #111; margin-bottom: 2px; }
        .dl-date { font-size: 11px; color: #777; }
        .dl-bar { height: 3px; border-radius: 2px; background: rgba(0,0,0,0.08); margin-top: 8px; overflow: hidden; }
        .dl-fill-urgent { height: 100%; border-radius: 2px; background: #E24B4A; }
        .dl-fill-soon { height: 100%; border-radius: 2px; background: #EF9F27; }
        .dl-fill-ok { height: 100%; border-radius: 2px; background: #185FA5; }

        /* Tier grid */
        .tier-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .tier-card { border: 0.5px solid #e8e8e5; border-radius: 10px; padding: 18px; background: #f9f9f7; }
        .tier-card.pro { border: 2px solid #185FA5; background: #fff; }
        .tier-badge { font-size: 10px; font-weight: 500; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-bottom: 10px; font-family: 'DM Mono', monospace; }
        .free-badge { background: #f4f4f2; color: #999; border: 0.5px solid #ddd; }
        .pro-badge { background: #185FA5; color: white; }
        .tier-price { font-size: 24px; font-weight: 300; color: #111; letter-spacing: -0.02em; margin-bottom: 2px; }
        .tier-price span { font-size: 12px; color: #999; }
        .tier-desc { font-size: 12px; color: #777; margin-bottom: 12px; line-height: 1.5; }
        .tier-feat { list-style: none; }
        .tier-feat li { font-size: 12px; color: #555; padding: 3px 0; display: flex; align-items: flex-start; gap: 8px; line-height: 1.4; }
        .check { width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; margin-top: 1px; display: flex; align-items: center; justify-content: center; }
        .check-free { background: #ddd; }
        .check-pro { background: #185FA5; }
        .tier-btn { width: 100%; padding: 10px; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; margin-top: 14px; font-family: 'DM Sans', sans-serif; border: 0.5px solid #ddd; background: transparent; color: #666; }
        .pro-btn { background: #185FA5; color: white; border-color: #185FA5; }

        /* Subscribe form */
        .org-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 16px; }
        .opt { border: 0.5px solid #e8e8e5; border-radius: 7px; padding: 8px 10px; cursor: pointer; background: #f9f9f7; font-size: 12px; color: #555; text-align: center; transition: all 0.15s; }
        .opt.sel { border-color: #185FA5; background: #E6F1FB; color: #185FA5; font-weight: 500; }
        .opt:hover { border-color: #185FA5; }
        .jur-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
        .jur-opt { border: 0.5px solid #e8e8e5; border-radius: 20px; padding: 5px 12px; cursor: pointer; background: #f9f9f7; font-size: 11px; color: #555; font-family: 'DM Mono', monospace; transition: all 0.15s; }
        .jur-opt.sel { border-color: #185FA5; background: #E6F1FB; color: #185FA5; }
        .freq-row { display: flex; gap: 8px; margin-bottom: 16px; }
        .freq-opt { flex: 1; border: 0.5px solid #e8e8e5; border-radius: 7px; padding: 8px; text-align: center; cursor: pointer; background: #f9f9f7; font-size: 12px; color: #555; transition: all 0.15s; }
        .freq-opt.sel { border-color: #185FA5; background: #E6F1FB; color: #185FA5; font-weight: 500; }
        .email-row { display: flex; gap: 8px; }
        .email-row input { flex: 1; padding: 10px 14px; border: 0.5px solid #ddd; border-radius: 7px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; background: #fff; outline: none; }
        .email-row input:focus { border-color: #185FA5; }
        .sub-btn { padding: 10px 20px; background: #185FA5; color: white; border: none; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; font-family: 'DM Sans', sans-serif; white-space: nowrap; }
        .sub-btn:hover { background: #0C447C; }
        .success-msg { background: #E1F5EE; border: 0.5px solid #1D9E75; border-radius: 8px; padding: 14px; font-size: 13px; color: #085041; display: none; margin-top: 12px; }

        /* Divider */
        .divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; }
        .div-line { flex: 1; height: 0.5px; background: #e8e8e5; }
        .div-text { font-family: 'DM Mono', monospace; font-size: 11px; color: #bbb; white-space: nowrap; }

        /* Digest */
        .digest-card { background: #fff; border-radius: 10px; border: 0.5px solid #e8e8e5; padding: 20px; margin-bottom: 12px; }
        .dh { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .dh-title { font-size: 13px; font-weight: 500; color: #111; }
        .dh-meta { font-size: 11px; color: #999; font-family: 'DM Mono', monospace; }
        .d-item { display: flex; gap: 12px; padding: 12px 0; border-bottom: 0.5px solid #f0f0ee; position: relative; }
        .d-item:last-child { border-bottom: none; padding-bottom: 0; }
        .d-content { flex: 1; }
        .d-headline { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 4px; line-height: 1.4; }
        .d-summary { font-size: 12px; color: #666; line-height: 1.5; margin-bottom: 8px; }
        .d-bottom { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .impact-pill { font-family: 'DM Mono', monospace; font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 500; }
        .HIGH { background: #FCEBEB; color: #791F1F; }
        .MEDIUM { background: #FAEEDA; color: #633806; }
        .LOW { background: #E1F5EE; color: #085041; }
        .score-pill { font-family: 'DM Mono', monospace; font-size: 10px; padding: 2px 7px; border-radius: 4px; background: #f4f4f2; color: #666; border: 0.5px solid #e8e8e5; }
        .dl-pill { font-family: 'DM Mono', monospace; font-size: 10px; padding: 2px 7px; border-radius: 4px; background: #FCEBEB; color: #791F1F; }
        .pro-blur-wrap { position: relative; }
        .pro-blur-content { filter: blur(4px); pointer-events: none; user-select: none; }
        .pro-lock-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
        .pro-lock-btn { font-size: 12px; color: #185FA5; font-weight: 500; background: #E6F1FB; padding: 6px 16px; border-radius: 20px; border: 0.5px solid #185FA5; cursor: pointer; font-family: 'DM Mono', monospace; }

        /* Calendar */
        .cal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .cal-item { border: 0.5px solid #e8e8e5; border-radius: 8px; padding: 14px; background: #f9f9f7; }
        .cal-month { font-family: 'DM Mono', monospace; font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
        .cal-event { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
        .cal-event:last-child { margin-bottom: 0; }
        .cal-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
        .cal-text { font-size: 12px; color: #444; line-height: 1.4; }
        .cal-date { font-size: 10px; color: #999; font-family: 'DM Mono', monospace; margin-top: 1px; }

        .footer { text-align: center; font-size: 11px; color: #bbb; margin-top: 28px; padding-top: 16px; border-top: 0.5px solid #e8e8e5; font-family: 'DM Mono', monospace; }
        .footer a { color: #185FA5; text-decoration: none; }

        @media (max-width: 560px) {
            .stats-banner { grid-template-columns: repeat(2, 1fr); }
            .dl-grid, .tier-grid, .org-grid, .cal-grid { grid-template-columns: 1fr; }
            .topbar { padding: 0 16px; }
            .body { padding: 24px 16px 48px; }
            .logo-badge { display: none; }
            .penalty-box { flex-direction: column; }
        }
    </style>
</head>
<body>
<div class="topbar">
    <div class="logo">
        <div class="logo-mark">
            <svg viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="12" rx="1" fill="white" opacity="0.9"/><rect x="9" y="2" width="5" height="7" rx="1" fill="white" opacity="0.6"/><rect x="9" y="11" width="5" height="3" rx="1" fill="white" opacity="0.6"/></svg>
        </div>
        <span class="logo-text">DIKE AI</span>
        <span class="logo-badge">v1.3</span>
    </div>
    <div class="nav">
        <a href="/" class="inactive">DIKE Audit</a>
        <a href="/monitor" class="inactive">DIKE Monitor</a>
        <a href="/pulse" class="active">DIKE Pulse</a>
    </div>
</div>

<div class="body">
    <div class="hero">
        <div class="eyebrow"><span class="hero-dot"></span> Regulatory Intelligence Digest</div>
        <h1>Never miss a regulation<br><strong>that affects your organisation</strong></h1>
        <p>Weekly personalised digest of regulatory developments across India, EU, and GCC &mdash; with impact scores, compliance deadlines, and penalty data.</p>
    </div>

    <!-- Stats banner -->
    <div class="stats-banner">
        <div class="sb-item">
            <div class="sb-num">{{ digest.total_developments }}</div>
            <div class="sb-lbl">This week</div>
        </div>
        <div class="sb-item">
            <div class="sb-num">{{ digest.jurisdictions }}</div>
            <div class="sb-lbl">Jurisdictions</div>
        </div>
        <div class="sb-item">
            <div class="sb-num">{{ deadlines[0].days }}</div>
            <div class="sb-lbl">Days to DPDP</div>
        </div>
        <div class="sb-item">
            <div class="sb-num">{{ deadlines[1].days }}</div>
            <div class="sb-lbl">Days to EU AI Act</div>
        </div>
    </div>

    <!-- Penalty box -->
    <div class="penalty-box">
        <div class="penalty-left">
            <div class="penalty-label">Global data protection fines</div>
            <div class="penalty-amount">${{ "{:,.0f}".format(digest.penalty_total_usd / 1000000) }}M</div>
            <div class="penalty-period">{{ digest.penalty_period }} &mdash; publicly reported enforcement actions</div>
            <div class="penalty-source">Source: {{ digest.penalty_source }}</div>
        </div>
        <div class="penalty-right">
            <div class="penalty-cta">Non-compliance is no longer a theoretical risk.<br><strong>Is your policy ready?</strong></div>
        </div>
    </div>

    <!-- Deadline tracker -->
    <div class="card">
        <span class="slabel">Compliance deadline tracker</span>
        <div class="dl-grid">
            {% for dl in deadlines %}
            <div class="dl-item dl-{{ dl.urgency }}">
                <div class="dl-top">
                    <span class="dl-reg tag-{{ dl.tag }}">{{ dl.regulation }}</span>
                    <div><span class="dl-days">{{ dl.days }}<span class="dl-days-lbl"> days</span></span></div>
                </div>
                <div class="dl-name">{{ dl.name }}</div>
                <div class="dl-date">{{ dl.date_str }} &middot; {{ dl.action }}</div>
                <div class="dl-bar">
                    <div class="dl-fill-{{ dl.urgency }}" style="width: {{ dl.progress }}%"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Pricing tiers -->
    <div class="card">
        <span class="slabel">Choose your plan</span>
        <div class="tier-grid">
            <div class="tier-card">
                <span class="tier-badge free-badge">Free</span>
                <div class="tier-price">&#8377;0 <span>/ month</span></div>
                <div class="tier-desc">Weekly digest with headlines, impact levels, and deadline tracker.</div>
                <ul class="tier-feat">
                    <li><span class="check check-free"></span>5 regulatory headlines per week</li>
                    <li><span class="check check-free"></span>HIGH / MEDIUM / LOW impact rating</li>
                    <li><span class="check check-free"></span>Jurisdiction filter</li>
                    <li><span class="check check-free"></span>Organisation type personalisation</li>
                    <li><span class="check check-free"></span>Compliance deadline tracker</li>
                    <li><span class="check check-free"></span>Global penalty tracker</li>
                </ul>
                <button class="tier-btn" onclick="document.getElementById('subscribe-form').scrollIntoView({behavior:'smooth'})">Subscribe free</button>
            </div>
            <div class="tier-card pro">
                <span class="tier-badge pro-badge">Pro &mdash; Coming soon</span>
                <div class="tier-price">&#8377;499 <span>/ month</span></div>
                <div class="tier-desc">Full analysis, PDF digest, impact scores, and priority alerts.</div>
                <ul class="tier-feat">
                    <li><span class="check check-pro"></span>Everything in Free</li>
                    <li><span class="check check-pro"></span>Full 7-section impact analysis</li>
                    <li><span class="check check-pro"></span>Numerical impact score (1&ndash;10)</li>
                    <li><span class="check check-pro"></span>Required actions with deadlines</li>
                    <li><span class="check check-pro"></span>Downloadable PDF digest every Monday</li>
                    <li><span class="check check-pro"></span>Priority email alerts</li>
                    <li><span class="check check-pro"></span>Regulatory calendar (90-day view)</li>
                </ul>
                <button class="tier-btn pro-btn" onclick="document.getElementById('subscribe-form').scrollIntoView({behavior:'smooth'})">Join Pro waitlist</button>
            </div>
        </div>
    </div>

    <!-- Subscribe form -->
    <div class="card" id="subscribe-form">
        <span class="slabel">Subscribe to DIKE Pulse</span>

        {% if subscribed %}
        <div style="background:#E1F5EE;border:0.5px solid #1D9E75;border-radius:8px;padding:16px;font-size:13px;color:#085041;">
            You are subscribed to DIKE Pulse. Your first digest will arrive next Monday morning.
        </div>
        {% else %}
        <form method="POST" action="/pulse" id="pulse-form">
            <span class="slabel">Organisation type</span>
            <div class="org-grid">
                {% set orgs = ["Indian Startup", "NGO / Non-profit", "MNC / Enterprise", "Government Body", "Healthcare Org", "Legal / Consulting"] %}
                {% for org in orgs %}
                <div class="opt {% if org == selected_org %}sel{% endif %}"
                     onclick="selectOpt(this, 'org-input', '{{ org }}')">{{ org }}</div>
                {% endfor %}
            </div>
            <input type="hidden" name="org_type" id="org-input" value="{{ selected_org }}">

            <span class="slabel">Jurisdictions to track</span>
            <div class="jur-row">
                {% set jurs = ["India (DPDP)", "EU (GDPR + AI Act)", "GCC (UAE PDPL)", "Global"] %}
                {% for j in jurs %}
                <div class="jur-opt {% if j in selected_jurs %}sel{% endif %}"
                     onclick="toggleJur(this, '{{ j }}')">{{ j }}</div>
                {% endfor %}
            </div>
            <input type="hidden" name="jurisdictions" id="jur-input" value="{{ selected_jurs | join(',') }}">

            <span class="slabel">Frequency</span>
            <div class="freq-row">
                {% for f in ["Weekly", "Fortnightly", "Monthly"] %}
                <div class="freq-opt {% if f == selected_freq %}sel{% endif %}"
                     onclick="selectOpt(this, 'freq-input', '{{ f }}')">{{ f }}</div>
                {% endfor %}
            </div>
            <input type="hidden" name="frequency" id="freq-input" value="{{ selected_freq }}">

            <span class="slabel">Your email</span>
            <div class="email-row">
                <input type="email" name="email" placeholder="your@email.com" required>
                <button type="submit" class="sub-btn">Subscribe</button>
            </div>
            <p style="font-size:11px;color:#bbb;margin-top:8px;">Free to start. Upgrade to Pro anytime. No spam.</p>
        </form>
        {% endif %}
    </div>

    <!-- Latest digest -->
    <div class="divider">
        <div class="div-line"></div>
        <div class="div-text">latest digest &mdash; week of {{ digest.week_of }}</div>
        <div class="div-line"></div>
    </div>

    <div class="digest-card">
        <div class="dh">
            <span class="dh-title">This week in governance</span>
            <span class="dh-meta">{{ digest.total_developments }} developments &middot; {{ digest.action_required }} require action</span>
        </div>

        {% for item in digest.items %}
        {% if item.pro_only %}
        <div class="d-item pro-blur-wrap">
            <div class="pro-blur-content" style="display:flex;gap:12px;width:100%;">
                <span class="dl-reg tag-{{ item.tag }}">{{ item.regulation }}</span>
                <div class="d-content">
                    <div class="d-headline">{{ item.headline }}</div>
                    <div class="d-summary">{{ item.summary }}</div>
                    <div class="d-bottom">
                        <span class="impact-pill {{ item.impact }}">{{ item.impact }}</span>
                        <span class="score-pill">Score: {{ item.score }} / 10</span>
                    </div>
                </div>
            </div>
            <div class="pro-lock-overlay">
                <span class="pro-lock-btn">Pro &mdash; full analysis</span>
            </div>
        </div>
        {% else %}
        <div class="d-item">
            <span class="dl-reg tag-{{ item.tag }}">{{ item.regulation }}</span>
            <div class="d-content">
                <div class="d-headline">{{ item.headline }}</div>
                <div class="d-summary">{{ item.summary }}</div>
                <div class="d-bottom">
                    <span class="impact-pill {{ item.impact }}">{{ item.impact }}</span>
                    <span class="score-pill">Score: {{ item.score }} / 10</span>
                    {% if item.deadline %}<span class="dl-pill">Deadline: {{ item.deadline }}</span>{% endif %}
                </div>
            </div>
        </div>
        {% endif %}
        {% endfor %}
    </div>

    <!-- Regulatory calendar -->
    <div class="card">
        <span class="slabel">Regulatory calendar &mdash; next 90 days</span>
        <div class="cal-grid">
            {% for month in calendar %}
            <div class="cal-item">
                <div class="cal-month">{{ month.month }}</div>
                {% for ev in month.events %}
                <div class="cal-event">
                    <div class="cal-dot" style="background:{{ ev.color }};"></div>
                    <div>
                        <div class="cal-text">{{ ev.name }}</div>
                        <div class="cal-date">{{ ev.date }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="footer">
        Powered by <a href="https://strategicpolicylab.com">Strategic Policy Lab</a> &nbsp;&middot;&nbsp; Built with Groq + LLaMA 3.3
    </div>
</div>

<script>
function selectOpt(el, inputId, val) {
    el.closest('.org-grid, .freq-row') && el.closest('.org-grid, .freq-row').querySelectorAll('.opt,.freq-opt').forEach(o => o.classList.remove('sel'));
    el.classList.add('sel');
    document.getElementById(inputId).value = val;
}
var selectedJurs = {{ selected_jurs | tojson }};
function toggleJur(el, val) {
    if (selectedJurs.includes(val)) {
        selectedJurs = selectedJurs.filter(j => j !== val);
        el.classList.remove('sel');
    } else {
        selectedJurs.push(val);
        el.classList.add('sel');
    }
    document.getElementById('jur-input').value = selectedJurs.join(',');
}
</script>
</body>
</html>
"""


def parse_results(ai_response):
    results = []
    lines = ai_response.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        line_upper = line.upper()
        if "FAIL" in line_upper:
            for keyword in ["[FAIL]", "FAIL:", "**FAIL**", "FAIL"]:
                if keyword.upper() in line_upper:
                    idx = line_upper.find(keyword.upper())
                    explanation = line[idx + len(keyword):].strip(" -:")
                    if explanation:
                        results.append({"status": "FAIL", "explanation": explanation})
                        break
        elif "PARTIAL" in line_upper:
            for keyword in ["[PARTIAL]", "PARTIAL:", "**PARTIAL**", "PARTIAL"]:
                if keyword.upper() in line_upper:
                    idx = line_upper.find(keyword.upper())
                    explanation = line[idx + len(keyword):].strip(" -:")
                    if explanation:
                        results.append({"status": "PARTIAL", "explanation": explanation})
                        break
        elif "PASS" in line_upper:
            for keyword in ["[PASS]", "PASS:", "**PASS**", "PASS"]:
                if keyword.upper() in line_upper:
                    idx = line_upper.find(keyword.upper())
                    explanation = line[idx + len(keyword):].strip(" -:")
                    if explanation:
                        results.append({"status": "PASS", "explanation": explanation})
                        break
    if not results:
        results.append({
            "status": "PARTIAL",
            "explanation": "Analysis completed but response format was unexpected. Please try again."
        })
    return results


def parse_monitor_results(ai_response):
    sections = []
    impact_level = "MEDIUM"
    current_title = ""
    current_content = []
    section_titles = ["SUMMARY", "IMPACT LEVEL", "KEY CHANGES", "WHO IS AFFECTED",
                      "REQUIRED ACTIONS", "DEADLINE", "RISK IF IGNORED"]

    for line in ai_response.split("\n"):
        line = line.strip()
        line = line.lstrip("#").strip()
        if not line:
            continue
        matched_title = None
        for title in section_titles:
            if line.upper().startswith(title):
                matched_title = title
                break
        if matched_title:
            if current_title and current_content:
                sections.append({"title": current_title, "content": "\n".join(current_content).strip()})
            current_title = matched_title
            remainder = line[len(matched_title):].strip(" :-")
            current_content = [remainder] if remainder else []
        else:
            if current_title:
                current_content.append(line)

    if current_title and current_content:
        sections.append({"title": current_title, "content": "\n".join(current_content).strip()})

    for section in sections:
        if section["title"] == "IMPACT LEVEL":
            content_upper = section["content"].upper()
            if "HIGH" in content_upper:
                impact_level = "HIGH"
            elif "LOW" in content_upper:
                impact_level = "LOW"
            else:
                impact_level = "MEDIUM"

    return sections, impact_level


# ─── PDF HELPERS ──────────────────────────────────────────────────────────────
def build_pdf_styles():
    blue = HexColor("#185FA5")
    red = HexColor("#9b1c1c")
    green = HexColor("#03543f")
    amber = HexColor("#723b13")
    grey = HexColor("#666666")
    return {
        "blue": blue, "red": red, "green": green, "amber": amber, "grey": grey,
        "light_red": HexColor("#fde8e8"),
        "light_green": HexColor("#def7ec"),
        "light_amber": HexColor("#fdf3c8"),
        "title": ParagraphStyle("title", fontSize=20, textColor=blue, fontName="Helvetica-Bold", spaceAfter=4),
        "meta": ParagraphStyle("meta", fontSize=11, textColor=grey, spaceAfter=16),
        "heading": ParagraphStyle("heading", fontSize=13, textColor=blue, fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=8),
        "body": ParagraphStyle("body", fontSize=11, textColor=HexColor("#444444"), leading=16),
        "section_title": ParagraphStyle("section_title", fontSize=10, textColor=blue, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4),
        "footer": ParagraphStyle("footer", fontSize=9, textColor=grey, leading=14),
    }


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    policy = ""
    selected_reg = "DPDP Act 2023"
    fail_count = partial_count = pass_count = 0
    email_captured = session.get("email_captured", False)

    if request.method == "POST":
        policy = request.form.get("policy", "")
        selected_reg = request.form.get("regulation", "DPDP Act 2023")
        # New audit resets email gate
        session.pop("email_captured", None)
        email_captured = False

        if policy.strip():
            reg_data = REGULATIONS[selected_reg]
            prompt = f"""You are an AI governance compliance expert specialising
in {selected_reg} — {reg_data['description']}.

Analyse this policy document against the checklist below.
For each item say PASS, FAIL, or PARTIAL and explain why in one sentence.

POLICY DOCUMENT:
{policy}

COMPLIANCE CHECKLIST:
{reg_data['checklist']}

Format your response strictly as:
1. [PASS/FAIL/PARTIAL] - explanation
One line per checklist item. No extra text."""

            try:
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_response = response.choices[0].message.content
                results = parse_results(raw_response)
            except Exception as e:
                results = [{"status": "FAIL", "explanation": f"An error occurred: {str(e)}"}]

            fail_count = sum(1 for r in results if r["status"] == "FAIL")
            partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
            pass_count = sum(1 for r in results if r["status"] == "PASS")

            session["results"] = results
            session["selected_reg"] = selected_reg
            session["fail_count"] = fail_count
            session["partial_count"] = partial_count
            session["pass_count"] = pass_count

    reg_description = REGULATIONS[selected_reg]["description"]

    return render_template_string(
        HTML_PAGE,
        results=results,
        policy=policy,
        selected_reg=selected_reg,
        reg_description=reg_description,
        regulations=REGULATIONS,
        fail_count=fail_count,
        partial_count=partial_count,
        pass_count=pass_count,
        email_captured=email_captured
    )


@app.route("/capture-email", methods=["POST"])
def capture_email():
    """Save email then redirect to PDF download."""
    email = request.form.get("email", "").strip()
    regulation = request.form.get("regulation", "")
    if email:
        save_email(email, "audit_pdf", regulation)
        session["email_captured"] = True
    return redirect(url_for("download_pdf"))


@app.route("/monitor", methods=["GET", "POST"])
def monitor():
    sections = []
    regulatory_text = ""
    selected_org = "Indian Startup"
    impact_level = "MEDIUM"

    if request.method == "POST":
        regulatory_text = request.form.get("regulatory_text", "")
        selected_org = request.form.get("org_type", "Indian Startup")
        session.pop("monitor_email_captured", None)

        if regulatory_text.strip():
            try:
                raw_response = analyse_impact(regulatory_text, selected_org)
                sections, impact_level = parse_monitor_results(raw_response)
            except Exception as e:
                sections = [{"title": "ERROR", "content": f"An error occurred: {str(e)}"}]

            session["monitor_sections"] = sections
            session["monitor_org"] = selected_org
            session["monitor_impact"] = impact_level
            session["monitor_text"] = regulatory_text

    monitor_email_captured = session.get('monitor_email_captured', False)

    return render_template_string(
        MONITOR_PAGE,
        sections=sections,
        regulatory_text=regulatory_text,
        selected_org=selected_org,
        org_types=list(ORG_TYPES.keys()),
        impact_level=impact_level,
        monitor_email_captured=monitor_email_captured
    )


@app.route("/download-pdf", methods=["GET", "POST"])
def download_pdf():
    results = session.get("results", [])
    regulation = session.get("selected_reg", "")
    fail_count = session.get("fail_count", 0)
    partial_count = session.get("partial_count", 0)
    pass_count = session.get("pass_count", 0)
    date = datetime.datetime.now().strftime("%d %B %Y")

    s = build_pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []
    story.append(Paragraph("DIKE AI — Governance Audit Report", s["title"]))
    story.append(Paragraph(f"Regulation: <b>{regulation}</b> &nbsp;&nbsp; Date: <b>{date}</b>", s["meta"]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Compliance summary", s["heading"]))

    summary_data = [["Failed", "Partial", "Passed"], [str(fail_count), str(partial_count), str(pass_count)]]
    summary_table = Table(summary_data, colWidths=[55*mm, 55*mm, 55*mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), s["light_red"]),
        ("BACKGROUND", (1, 0), (1, -1), s["light_amber"]),
        ("BACKGROUND", (2, 0), (2, -1), s["light_green"]),
        ("TEXTCOLOR", (0, 0), (0, -1), s["red"]),
        ("TEXTCOLOR", (1, 0), (1, -1), s["amber"]),
        ("TEXTCOLOR", (2, 0), (2, -1), s["green"]),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("FONTSIZE", (0, 1), (-1, 1), 22),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Detailed findings", s["heading"]))

    for item in results:
        status = item["status"]
        explanation = item["explanation"]
        if status == "FAIL":
            bg, tc = s["light_red"], s["red"]
        elif status == "PASS":
            bg, tc = s["light_green"], s["green"]
        else:
            bg, tc = s["light_amber"], s["amber"]

        safe_exp = explanation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        row_data = [[
            Paragraph(f"<b>{status}</b>", ParagraphStyle("badge", fontSize=10, textColor=tc, fontName="Helvetica-Bold")),
            Paragraph(safe_exp, s["body"])
        ]]
        row_table = Table(row_data, colWidths=[22*mm, 143*mm])
        row_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), bg),
            ("BACKGROUND", (1, 0), (1, 0), HexColor("#fafafa")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "This report was generated automatically by DIKE AI. It is intended as a preliminary "
        "assessment only and does not constitute legal advice. Consult a qualified legal professional "
        "for formal compliance guidance. Powered by Strategic Policy Lab — strategicpolicylab.com",
        s["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=dike_ai_compliance_report.pdf"
    return response


@app.route("/capture-monitor-email", methods=["POST"])
def capture_monitor_email():
    """Save email then generate PDF directly — no redirect needed."""
    import html as html_module
    email = request.form.get("email", "").strip()
    org = request.form.get("selected_org", "")
    impact_level = request.form.get("impact_level", "MEDIUM")
    sections_json = request.form.get("sections_json", "[]")

    if email:
        save_email(email, "monitor_pdf", org)
        session["monitor_email_captured"] = True

    try:
        sections = json.loads(html_module.unescape(sections_json))
    except Exception:
        sections = session.get("monitor_sections", [])

    # Generate and return PDF directly without redirecting
    return _build_monitor_pdf(sections, org, impact_level)


def _build_monitor_pdf(sections, org, impact_level):
    """Shared PDF builder for Monitor reports."""
    date = datetime.datetime.now().strftime("%d %B %Y")
    impact_colors = {
        "HIGH": (HexColor("#fde8e8"), HexColor("#9b1c1c")),
        "MEDIUM": (HexColor("#fdf3c8"), HexColor("#723b13")),
        "LOW": (HexColor("#def7ec"), HexColor("#03543f")),
    }
    badge_bg, badge_tc = impact_colors.get(impact_level, impact_colors["MEDIUM"])
    s = build_pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []
    story.append(Paragraph("DIKE AI — Regulatory Impact Report", s["title"]))
    story.append(Paragraph(f"Organisation: <b>{org}</b> &nbsp;&nbsp; Date: <b>{date}</b>", s["meta"]))
    story.append(Spacer(1, 4*mm))
    badge_data = [[f"{impact_level} IMPACT"]]
    badge_table = Table(badge_data, colWidths=[40*mm])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
        ("TEXTCOLOR", (0, 0), (-1, -1), badge_tc),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 6*mm))
    for section in sections:
        title = section.get("title", "")
        content = section.get("content", "")
        safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(title, s["section_title"]))
        for line in safe_content.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 2*mm))
                continue
            story.append(Paragraph(line, s["body"]))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "This report was generated automatically by DIKE AI. It is intended as a preliminary "
        "assessment only and does not constitute legal advice. Consult a qualified legal professional "
        "for formal compliance guidance. Powered by Strategic Policy Lab — strategicpolicylab.com",
        s["footer"]
    ))
    doc.build(story)
    buffer.seek(0)
    resp = make_response(buffer.read())
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "attachment; filename=dike_ai_impact_report.pdf"
    return resp


@app.route("/download-monitor-pdf-get", methods=["GET"])
def download_monitor_pdf_get():
    """GET version - reads from session after email capture redirect."""
    sections = session.get("monitor_sections", [])
    org = session.get("monitor_org", "")
    impact_level = session.get("monitor_impact", "MEDIUM")
    return _build_monitor_pdf(sections, org, impact_level)


@app.route("/download-monitor-pdf", methods=["POST"])
def download_monitor_pdf():
    """Generate PDF for DIKE Monitor impact report."""
    import html as html_module
    sections_json = request.form.get("sections_json", "[]")
    try:
        sections = json.loads(html_module.unescape(sections_json))
    except Exception:
        sections = session.get("monitor_sections", [])
    org = request.form.get("selected_org", "") or session.get("monitor_org", "")
    impact_level = request.form.get("impact_level", "") or session.get("monitor_impact", "MEDIUM")
    date = datetime.datetime.now().strftime("%d %B %Y")

    impact_colors = {
        "HIGH": (HexColor("#fde8e8"), HexColor("#9b1c1c")),
        "MEDIUM": (HexColor("#fdf3c8"), HexColor("#723b13")),
        "LOW": (HexColor("#def7ec"), HexColor("#03543f")),
    }
    badge_bg, badge_tc = impact_colors.get(impact_level, impact_colors["MEDIUM"])

    s = build_pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []

    # Header
    story.append(Paragraph("DIKE AI — Regulatory Impact Report", s["title"]))
    story.append(Paragraph(
        f"Organisation: <b>{org}</b> &nbsp;&nbsp; Date: <b>{date}</b>",
        s["meta"]
    ))
    story.append(Spacer(1, 4*mm))

    # Impact level badge as a small table
    badge_data = [[f"{impact_level} IMPACT"]]
    badge_table = Table(badge_data, colWidths=[40*mm])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
        ("TEXTCOLOR", (0, 0), (-1, -1), badge_tc),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 6*mm))

    # Sections
    for section in sections:
        title = section.get("title", "")
        content = section.get("content", "")
        safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        story.append(Paragraph(title, s["section_title"]))

        # Render content line by line to preserve bullet-style lists
        for line in safe_content.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 2*mm))
                continue
            story.append(Paragraph(line, s["body"]))

        story.append(Spacer(1, 3*mm))

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "This report was generated automatically by DIKE AI. It is intended as a preliminary "
        "assessment only and does not constitute legal advice. Consult a qualified legal professional "
        "for formal compliance guidance. Powered by Strategic Policy Lab — strategicpolicylab.com",
        s["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=dike_ai_impact_report.pdf"
    return response



@app.route("/pulse", methods=["GET", "POST"])
def pulse():
    from pulse import save_subscriber, get_deadlines, get_latest_digest, get_calendar
    subscribed = False
    selected_org = "Indian Startup"
    selected_freq = "Weekly"
    selected_jurs = ["India (DPDP)", "EU (GDPR + AI Act)", "GCC (UAE PDPL)"]

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        org_type = request.form.get("org_type", "Indian Startup")
        frequency = request.form.get("frequency", "Weekly")
        jurisdictions = request.form.get("jurisdictions", "India (DPDP)")

        if email:
            save_subscriber(email, org_type, frequency, jurisdictions)
            subscribed = True
            selected_org = org_type
            selected_freq = frequency
            selected_jurs = [j.strip() for j in jurisdictions.split(",") if j.strip()]

    return render_template_string(
        PULSE_PAGE,
        digest=get_latest_digest(),
        deadlines=get_deadlines(),
        calendar=get_calendar(),
        subscribed=subscribed,
        selected_org=selected_org,
        selected_freq=selected_freq,
        selected_jurs=selected_jurs
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

