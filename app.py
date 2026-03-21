from flask import Flask, request, render_template_string, make_response, session
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

app = Flask(__name__)
app.secret_key = "governance-audit-secret-key-2024"

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", "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"))

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
    <title>DIKE AI — Governance Audit</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f5f5f5;
               min-height: 100vh; padding: 40px 20px; }
        .container { max-width: 720px; margin: 0 auto; }
        .header { margin-bottom: 28px; }
        .header h1 { font-size: 24px; font-weight: 600; color: #111; margin-bottom: 4px; }
        .header p { font-size: 13px; color: #666; }
        .card { background: white; border-radius: 10px; padding: 24px;
                border: 1px solid #e5e5e5; margin-bottom: 20px; }
        label { display: block; font-size: 11px; font-weight: 700;
                text-transform: uppercase; letter-spacing: .06em;
                color: #555; margin-bottom: 6px; }
        select { width: 100%; padding: 10px 12px; border: 1px solid #ddd;
                 border-radius: 6px; font-size: 13px; color: #111;
                 background: white; margin-bottom: 6px; }
        .reg-desc { font-size: 12px; color: #888; margin-bottom: 18px; }
        textarea { width: 100%; height: 140px; padding: 12px;
                   border: 1px solid #ddd; border-radius: 6px;
                   font-size: 13px; resize: vertical; color: #333;
                   line-height: 1.6; margin-bottom: 16px; }
        textarea:focus { outline: none; border-color: #185FA5; }
        button { width: 100%; padding: 12px; background: #185FA5;
                 color: white; border: none; border-radius: 6px;
                 font-size: 14px; font-weight: 600; cursor: pointer; }
        button:hover { background: #0C447C; }
        .results-header { display: flex; align-items: center;
                          justify-content: space-between; margin-bottom: 14px; }
        .results-title { font-size: 14px; font-weight: 600; color: #111; }
        .reg-tag { font-size: 11px; padding: 3px 10px; border-radius: 20px;
                   background: #E6F1FB; color: #0C447C; font-weight: 600; }
        .result-item { display: flex; gap: 12px; align-items: flex-start;
                       padding: 12px; border-radius: 8px; margin-bottom: 8px;
                       border: 1px solid #eee; background: #fafafa; }
        .badge { padding: 3px 9px; border-radius: 4px; font-weight: 700;
                 font-size: 11px; white-space: nowrap; margin-top: 1px; }
        .FAIL { background: #fde8e8; color: #9b1c1c; }
        .PASS { background: #def7ec; color: #03543f; }
        .PARTIAL { background: #fdf3c8; color: #723b13; }
        .result-text { font-size: 13px; color: #444; line-height: 1.5; }
        .summary { display: flex; gap: 10px; margin-bottom: 16px; }
        .sum-box { flex: 1; text-align: center; padding: 10px;
                   border-radius: 8px; border: 1px solid #eee; }
        .sum-num { font-size: 22px; font-weight: 700; }
        .sum-label { font-size: 11px; color: #888; margin-top: 2px; }
        .fail-bg { background: #fde8e8; }
        .pass-bg { background: #def7ec; }
        .partial-bg { background: #fdf3c8; }
        .fail-num { color: #9b1c1c; }
        .pass-num { color: #03543f; }
        .partial-num { color: #723b13; }
        .download-btn { width: 100%; padding: 12px; background: #1D9E75;
                        color: white; border: none; border-radius: 6px;
                        font-size: 14px; font-weight: 600; cursor: pointer;
                        margin-top: 16px; }
        .download-btn:hover { background: #0F6E56; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>DIKE AI</h1>
        <p>Instantly check any policy document against major data protection regulations</p>
    </div>

    <div class="card">
        <form method="POST" action="/">
            <label>Select regulation</label>
            <select name="regulation" onchange="updateDesc(this)">
                {% for reg_name in regulations %}
                <option value="{{ reg_name }}"
                    {% if reg_name == selected_reg %}selected{% endif %}>
                    {{ reg_name }}
                </option>
                {% endfor %}
            </select>
            <p class="reg-desc" id="reg-desc">{{ reg_description }}</p>
            <label>Paste your policy document</label>
            <textarea name="policy"
                placeholder="Paste your company privacy policy or data governance document here...">{{ policy }}</textarea>
            <button type="submit">Analyse document</button>
        </form>
    </div>

    {% if results %}
    <div class="card">
        <div class="results-header">
            <span class="results-title">Compliance audit result</span>
            <span class="reg-tag">{{ selected_reg }}</span>
        </div>
        <div class="summary">
            <div class="sum-box fail-bg">
                <div class="sum-num fail-num">{{ fail_count }}</div>
                <div class="sum-label">Failed</div>
            </div>
            <div class="sum-box partial-bg">
                <div class="sum-num partial-num">{{ partial_count }}</div>
                <div class="sum-label">Partial</div>
            </div>
            <div class="sum-box pass-bg">
                <div class="sum-num pass-num">{{ pass_count }}</div>
                <div class="sum-label">Passed</div>
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
                Download PDF report
            </button>
        </form>
    </div>
    {% endif %}
</div>
<script>
const descriptions = {
    {% for reg_name, reg_data in regulations.items() %}
    "{{ reg_name }}": "{{ reg_data.description }}",
    {% endfor %}
};
function updateDesc(sel) {
    document.getElementById('reg-desc').textContent = descriptions[sel.value];
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
        "This report was generated automatically by AI Governance Audit Tool. "
        "It is intended as a preliminary assessment only and does not constitute "
        "legal advice. Consult a qualified legal professional for formal compliance guidance.",
        footer_style
    ))

    doc.build(story)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=compliance_audit_report.pdf"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)