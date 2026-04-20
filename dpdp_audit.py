"""
DIKE AI — DPDP Guided Audit
5-step questionnaire mapped to DPDP Rules 2025 obligations.
"""

import os
import json
from groq import Groq

# ─── QUESTIONNAIRE STRUCTURE ─────────────────────────────────────────────────
QUESTIONS = [
    {
        "step": 1,
        "title": "What kind of data do you collect?",
        "field": "data_types",
        "type": "multi",
        "options": [
            {"id": "contact", "label": "Names / contact info", "risk": "low"},
            {"id": "financial", "label": "Financial data", "risk": "high"},
            {"id": "health", "label": "Health / medical data", "risk": "high"},
            {"id": "children", "label": "Children's data (under 18)", "risk": "critical"},
            {"id": "behavioural", "label": "Behavioural / usage data", "risk": "medium"},
            {"id": "biometric", "label": "Biometric data", "risk": "critical"},
            {"id": "location", "label": "Location data", "risk": "medium"},
        ]
    },
    {
        "step": 2,
        "title": "Where do you store this data?",
        "field": "storage",
        "type": "multi",
        "options": [
            {"id": "india_cloud", "label": "Indian cloud servers", "risk": "low"},
            {"id": "foreign_cloud", "label": "Foreign cloud (AWS / GCP / Azure)", "risk": "high"},
            {"id": "onpremise", "label": "On-premise servers", "risk": "medium"},
            {"id": "saas", "label": "Third-party SaaS tools", "risk": "high"},
            {"id": "unsure", "label": "Not sure", "risk": "critical"},
        ]
    },
    {
        "step": 3,
        "title": "Do you share data with third parties?",
        "field": "sharing",
        "type": "multi",
        "options": [
            {"id": "vendors", "label": "Yes — vendors / contractors", "risk": "medium"},
            {"id": "marketing", "label": "Yes — marketing / analytics platforms", "risk": "high"},
            {"id": "international", "label": "Yes — international transfers", "risk": "high"},
            {"id": "no_sharing", "label": "No third-party sharing", "risk": "low"},
        ]
    },
    {
        "step": 4,
        "title": "Do you currently have a consent mechanism?",
        "field": "consent",
        "type": "single",
        "options": [
            {"id": "explicit", "label": "Yes — explicit opt-in for each purpose", "risk": "low"},
            {"id": "bundled", "label": "Yes — bundled consent in T&Cs", "risk": "medium"},
            {"id": "preticked", "label": "Yes — pre-ticked boxes", "risk": "critical"},
            {"id": "no_consent", "label": "No consent mechanism", "risk": "critical"},
        ]
    },
    {
        "step": 5,
        "title": "Do you have a data breach response process?",
        "field": "breach",
        "type": "single",
        "options": [
            {"id": "documented", "label": "Yes — fully documented process", "risk": "low"},
            {"id": "informal", "label": "Informal / ad hoc process", "risk": "medium"},
            {"id": "no_process", "label": "No process", "risk": "critical"},
        ]
    }
]

# ─── SCORING RUBRIC ───────────────────────────────────────────────────────────
def calculate_scores(answers):
    """
    Calculate compliance scores per category based on answers.
    Returns dict of category -> score (0-100).
    """
    scores = {
        "Consent Management": 100,
        "Data Storage & Security": 100,
        "Third-Party Management": 100,
        "Data Principal Rights": 70,  # base score, improved by AI
        "Breach Response": 100,
        "Documentation": 60,  # base score
    }

    # Consent scoring
    consent = answers.get("consent", [])
    if isinstance(consent, list):
        consent = consent[0] if consent else ""
    if consent == "explicit":
        scores["Consent Management"] = 90
    elif consent == "bundled":
        scores["Consent Management"] = 55
    elif consent == "preticked":
        scores["Consent Management"] = 20
    elif consent == "no_consent":
        scores["Consent Management"] = 0

    # Storage scoring
    storage = answers.get("storage", [])
    if "unsure" in storage:
        scores["Data Storage & Security"] = 20
    elif "foreign_cloud" in storage or "saas" in storage:
        scores["Data Storage & Security"] = 55
    elif "onpremise" in storage:
        scores["Data Storage & Security"] = 75
    elif "india_cloud" in storage:
        scores["Data Storage & Security"] = 90

    # Third-party scoring
    sharing = answers.get("sharing", [])
    if "no_sharing" in sharing:
        scores["Third-Party Management"] = 95
    elif "international" in sharing:
        scores["Third-Party Management"] = 35
    elif "marketing" in sharing:
        scores["Third-Party Management"] = 50
    elif "vendors" in sharing:
        scores["Third-Party Management"] = 70

    # Breach response scoring
    breach = answers.get("breach", [])
    if isinstance(breach, list):
        breach = breach[0] if breach else ""
    if breach == "documented":
        scores["Breach Response"] = 95
    elif breach == "informal":
        scores["Breach Response"] = 45
    elif breach == "no_process":
        scores["Breach Response"] = 0

    # Data types affect Data Principal Rights
    data_types = answers.get("data_types", [])
    if "children" in data_types or "biometric" in data_types:
        scores["Data Principal Rights"] = max(20, scores["Data Principal Rights"] - 30)
    if "health" in data_types or "financial" in data_types:
        scores["Data Principal Rights"] = max(30, scores["Data Principal Rights"] - 15)

    return {k: max(0, min(100, v)) for k, v in scores.items()}


# ─── AI ANALYSIS ─────────────────────────────────────────────────────────────
def generate_dpdp_analysis(answers, scores):
    """Use Groq to generate detailed DPDP compliance analysis."""

    # Build readable answers summary
    answer_lines = []
    for q in QUESTIONS:
        field = q["field"]
        selected = answers.get(field, [])
        if isinstance(selected, str):
            selected = [selected]
        labels = []
        for opt in q["options"]:
            if opt["id"] in selected:
                labels.append(opt["label"])
        if labels:
            answer_lines.append(f"{q['title']}: {', '.join(labels)}")

    answers_text = "\n".join(answer_lines)
    scores_text = "\n".join([f"- {k}: {v}/100" for k, v in scores.items()])
    overall = int(sum(scores.values()) / len(scores))

    prompt = f"""You are a senior DPDP Act 2023 compliance expert. An organisation has completed a guided compliance questionnaire. Analyse their responses and provide specific, actionable compliance findings.

ORGANISATION RESPONSES:
{answers_text}

CALCULATED SCORES:
{scores_text}
Overall: {overall}/100

Provide a JSON response with exactly this structure:
{{
    "overall_score": {overall},
    "risk_level": "HIGH or MEDIUM or LOW",
    "executive_summary": "2-3 sentence plain English summary of compliance status",
    "findings": [
        {{
            "category": "category name",
            "status": "PASS or PARTIAL or FAIL",
            "finding": "specific finding based on their answers",
            "dpdp_clause": "relevant DPDP Rule or Section",
            "recommendation": "specific action to take"
        }}
    ],
    "priority_actions": [
        "Most urgent action 1",
        "Most urgent action 2",
        "Most urgent action 3"
    ],
    "deadline_note": "relevant DPDP enforcement deadline note"
}}

Generate 5-7 findings. Be specific to DPDP Act 2023 and DPDP Rules 2025. Reference actual clauses.
Respond ONLY with valid JSON."""

    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        # Fallback response
        return {
            "overall_score": overall,
            "risk_level": "MEDIUM",
            "executive_summary": f"Based on your responses, your organisation has an overall compliance score of {overall}/100 under the DPDP Act 2023. Several areas require immediate attention before enforcement begins.",
            "findings": [
                {
                    "category": cat,
                    "status": "PASS" if score >= 80 else "PARTIAL" if score >= 50 else "FAIL",
                    "finding": f"Score: {score}/100",
                    "dpdp_clause": "DPDP Act 2023",
                    "recommendation": "Review and update compliance procedures."
                }
                for cat, score in scores.items()
            ],
            "priority_actions": [
                "Review consent mechanisms for DPDP compliance",
                "Document data breach response procedures",
                "Audit third-party data sharing arrangements"
            ],
            "deadline_note": "DPDP Rules enforcement expected by June 2026."
        }