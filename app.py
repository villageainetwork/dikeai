# DIKE AI v1.1 - UI Redesign
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

        /* Topbar */
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

        /* Body */
        .body { max-width: 760px; margin: 0 auto; padding: 40px 24px 60px; }

        /* Hero */
        .hero { margin-bottom: 32px; }
        .hero-eyebrow { font-family: 'DM Mono', monospace; font-size: 11px; color: #185FA5; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
        .hero-dot { width: 6px; height: 6px; border-radius: 50%; background: #185FA5; display: inline-block; flex-shrink: 0; }
        .hero h1 { font-size: 26px; font-weight: 300; color: #111; letter-spacing: -0.02em; line-height: 1.25; margin: 0 0 8px; }
        .hero h1 strong { font-weight: 500; }
        .hero p { font-size: 14px; color: #777; line-height: 1.6; margin: 0; max-width: 480px; }

        /* Card */
        .card { background: #ffffff; border-radius: 12px; border: 0.5px solid #e8e8e5; padding: 28px; margin-bottom: 16px; }

        /* Section label */
        .section-label { font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #999; margin-bottom: 10px; display: block; }

        /* Regulation grid */
        .reg-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 24px; }
        .reg-option { border: 0.5px solid #e8e8e5; border-radius: 8px; padding: 12px 14px; cursor: pointer; transition: all 0.15s; background: #f9f9f7; }
        .reg-option:hover { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected { border-color: #185FA5; background: #EBF3FB; }
        .reg-option.selected .reg-name { color: #185FA5; }
        .reg-name { font-size: 13px; font-weight: 500; color: #111; margin-bottom: 2px; }
        .reg-desc-text { font-size: 11px; color: #999; line-height: 1.4; }

        /* Textarea */
        .textarea-wrap { position: relative; }
        .dike-textarea { width: 100%; min-height: 160px; padding: 14px 16px; border: 0.5px solid #ddd; border-radius: 8px; font-size: 13px; font-family: 'DM Sans', sans-serif; color: #333; background: #ffffff; resize: vertical; line-height: 1.6; outline: none; transition: border-color 0.15s; }
        .dike-textarea:focus { border-color: #185FA5; }
        .dike-textarea::placeholder { color: #bbb; }
        .char-count { position: absolute; bottom: 10px; right: 12px; font-size: 11px; color: #bbb; font-family: 'DM Mono', monospace; pointer-events: none; }

        /* Loading bar */
        .loading-bar { height: 2px; background: #eee; border-radius: 2px; margin-top: 14px; overflow: hidden; display: none; }
        .loading-fill { height: 100%; width: 0%; background: #185FA5; border-radius: 2px; transition: width 0.3s ease; }
        .loading-text { font-size: 12px; color: #999; margin-top: 8px; font-family: 'DM Mono', monospace; display: none; }

        /* Submit button */
        .submit-btn { width: 100%; padding: 13px; background: #185FA5; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 20px; transition: background 0.15s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .submit-btn:hover { background: #0C447C; }
        .submit-btn svg { width: 16px; height: 16px; flex-shrink: 0; }

        /* Divider */
        .divider { display: flex; align-items: center; gap: 12px; margin: 28px 0; }
        .divider-line { flex: 1; height: 0.5px; background: #e8e8e5; }
        .divider-text { font-size: 11px; color: #bbb; font-family: 'DM Mono', monospace; white-space: nowrap; }

        /* Results */
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

        /* Download button */
        .download-btn { width: 100%; padding: 11px; background: transparent; color: #0F6E56; border: 0.5px solid #1D9E75; border-radius: 8px; font-size: 13px; font-weight: 500; font-family: 'DM Sans', sans-serif; cursor: pointer; margin-top: 16px; transition: all 0.15s; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .download-btn:hover { background: #E1F5EE; }
        .download-btn svg { width: 14px; height: 14px; flex-shrink: 0; }

        /* Footer */
        .footer { text-align: center; font-size: 11px; color: #bbb; margin-top: 32px; padding-top: 20px; border-top: 0.5px solid #e8e8e5; font-family: 'DM Mono', monospace; }
        .footer a { color: #185FA5; text-decoration: none; }

        @media (max-width: 540px) {
            .topbar { padding: 0 16px; }
            .body { padding: 24px 16px 48px; }
            .reg-grid { grid-template-columns: 1fr; }
            .logo-badge { display: none; }
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
        <span class="logo-badge">v1.0</span>
    </div>
    <div class="nav">
        <a href="/" class="active">DIKE Audit</a>
        <a href="/monitor" class="inactive">DIKE Monitor</a>
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
                     onclick="selectReg(this, '{{ reg_name }}', '{{ reg_data.description }}')">
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
        <form method="POST" action="/download-pdf">
            <button type="submit" class="download-btn">
                <svg viewBox="0 0 16 16" fill="none"><path d="M8 2v8M4 7l4 4 4-4M2 13h12" stroke="#0F6E56" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Download PDF report
            </button>
        </form>
    </div>
    {% endif %}

    <div class="footer">
        Powered by <a href="https://strategicpolicylab.com">Strategic Policy Lab</a> &nbsp;·&nbsp; Built with Groq + LLaMA 3.3
    </div>
</div>

<script>
function selectReg(el, name, desc) {
    document.querySelectorAll('.reg-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('regulation-input').value = name;
}
function updateCount() {
    const val = document.getElementById('policy-input').value.trim();
    const words = val ? val.split(/\s+/).length : 0;
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
// Init word count on load
document.addEventListener('DOMContentLoaded', updateCount);
</script>
</body>
</html>
"""

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

        .footer { text-align: center; font-size: 11px; color: #bbb; margin-top: 32px; padding-top: 20px; border-top: 0.5px solid #e8e8e5; font-family: 'DM Mono', monospace; }
        .footer a { color: #185FA5; text-decoration: none; }

        @media (max-width: 540px) {
            .topbar { padding: 0 16px; }
            .body { padding: 24px 16px 48px; }
            .logo-badge { display: none; }
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
        <span class="logo-badge">v1.0</span>
    </div>
    <div class="nav">
        <a href="/" class="inactive">DIKE Audit</a>
        <a href="/monitor" class="active">DIKE Monitor</a>
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
                     onclick="selectOrg(this, '{{ org }}')" style="cursor:pointer;">
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
            <span class="results-title">Impact report — {{ selected_org }}</span>
            <span class="impact-badge {{ impact_level }}">{{ impact_level }} IMPACT</span>
        </div>
        {% for section in sections %}
        <div class="section-block">
            <div class="section-heading">{{ section.title }}</div>
            <div class="section-body">{{ section.content }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <div class="footer">
        Powered by <a href="https://strategicpolicylab.com">Strategic Policy Lab</a> &nbsp;·&nbsp; Built with Groq + LLaMA 3.3
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

    section_titles = ["SUMMARY", "IMPACT LEVEL", "KEY CHANGES", "WHO IS AFFECTED", "REQUIRED ACTIONS", "DEADLINE", "RISK IF IGNORED"]

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


@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    policy = ""
    selected_reg = "DPDP Act 2023"
    fail_count = partial_count = pass_count = 0

    if request.method == "POST":
        policy = request.form.get("policy", "")
        selected_reg = request.form.get("regulation", "DPDP Act 2023")

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
                results = [{"status": "FAIL",
                            "explanation": f"An error occurred: {str(e)}"}]

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
        pass_count=pass_count
    )


@app.route("/monitor", methods=["GET", "POST"])
def monitor():
    sections = []
    regulatory_text = ""
    selected_org = "Indian Startup"
    impact_level = "MEDIUM"

    if request.method == "POST":
        regulatory_text = request.form.get("regulatory_text", "")
        selected_org = request.form.get("org_type", "Indian Startup")

        if regulatory_text.strip():
            try:
                raw_response = analyse_impact(regulatory_text, selected_org)
                sections, impact_level = parse_monitor_results(raw_response)
            except Exception as e:
                sections = [{"title": "ERROR", "content": f"An error occurred: {str(e)}"}]

    return render_template_string(
        MONITOR_PAGE,
        sections=sections,
        regulatory_text=regulatory_text,
        selected_org=selected_org,
        org_types=list(ORG_TYPES.keys()),
        impact_level=impact_level
    )


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    results = session.get("results", [])
    regulation = session.get("selected_reg", "")
    fail_count = session.get("fail_count", 0)
    partial_count = session.get("partial_count", 0)
    pass_count = session.get("pass_count", 0)
    date = datetime.datetime.now().strftime("%d %B %Y")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    blue = HexColor("#185FA5")
    red = HexColor("#9b1c1c")
    green = HexColor("#03543f")
    amber = HexColor("#723b13")
    light_red = HexColor("#fde8e8")
    light_green = HexColor("#def7ec")
    light_amber = HexColor("#fdf3c8")
    grey = HexColor("#666666")

    title_style = ParagraphStyle("title", fontSize=20, textColor=blue,
                                  fontName="Helvetica-Bold", spaceAfter=4)
    meta_style = ParagraphStyle("meta", fontSize=11, textColor=grey, spaceAfter=16)
    heading_style = ParagraphStyle("heading", fontSize=13, textColor=blue,
                                    fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle("body", fontSize=11,
                                 textColor=HexColor("#444444"), leading=16)
    footer_style = ParagraphStyle("footer", fontSize=9, textColor=grey, leading=14)

    story = []
    story.append(Paragraph("DIKE AI — Governance Audit Report", title_style))
    story.append(Paragraph(
        f"Regulation: <b>{regulation}</b> &nbsp;&nbsp; Date: <b>{date}</b>",
        meta_style))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("Compliance summary", heading_style))
    summary_data = [
        ["Failed", "Partial", "Passed"],
        [str(fail_count), str(partial_count), str(pass_count)]
    ]
    summary_table = Table(summary_data, colWidths=[55*mm, 55*mm, 55*mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), light_red),
        ("BACKGROUND", (1, 0), (1, -1), light_amber),
        ("BACKGROUND", (2, 0), (2, -1), light_green),
        ("TEXTCOLOR", (0, 0), (0, -1), red),
        ("TEXTCOLOR", (1, 0), (1, -1), amber),
        ("TEXTCOLOR", (2, 0), (2, -1), green),
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

    story.append(Paragraph("Detailed findings", heading_style))

    for item in results:
        status = item["status"]
        explanation = item["explanation"]
        if status == "FAIL":
            bg, tc = light_red, red
        elif status == "PASS":
            bg, tc = light_green, green
        else:
            bg, tc = light_amber, amber

        safe_explanation = explanation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        row_data = [[
            Paragraph(f"<b>{status}</b>",
                      ParagraphStyle("badge", fontSize=10, textColor=tc,
                                     fontName="Helvetica-Bold")),
            Paragraph(safe_explanation, body_style)
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
        "This report was generated automatically by DIKE AI. "
        "It is intended as a preliminary assessment only and does not constitute "
        "legal advice. Consult a qualified legal professional for formal compliance guidance. "
        "Powered by Strategic Policy Lab — strategicpolicylab.com",
        footer_style
    ))

    doc.build(story)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=dike_ai_compliance_report.pdf"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


