from groq import Groq
import os
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

ORG_TYPES = {
    "Indian Startup": "an early-stage or growth-stage Indian startup handling user data",
    "NGO / Non-profit": "an NGO or non-profit organisation operating in India",
    "MNC / Large Enterprise": "a multinational company with operations in India and internationally",
    "Government Body": "an Indian government agency or public sector organisation",
    "Healthcare Organisation": "a healthcare provider or healthtech company in India",
}


def analyse_impact(regulatory_text, org_type):
    org_description = ORG_TYPES.get(org_type, "an organisation operating in India")

    prompt = f"""You are an expert AI policy analyst specialising in regulatory impact assessment.

A new regulatory development has been shared below. Analyse its impact specifically for {org_description}.

REGULATORY DEVELOPMENT:
{regulatory_text}

Provide a structured impact analysis with exactly these sections:

SUMMARY
One sentence explaining what this regulatory development is.

IMPACT LEVEL
Rate as: HIGH / MEDIUM / LOW — and explain why in one sentence.

KEY CHANGES
List 3-5 specific changes or requirements introduced.

WHO IS AFFECTED
Explain specifically how this affects {org_type}.

REQUIRED ACTIONS
List 3-5 concrete actions this organisation should take.

DEADLINE
State any compliance deadlines mentioned, or "No specific deadline stated."

RISK IF IGNORED
One sentence on consequences of non-compliance."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content
    return result
