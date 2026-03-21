import google.generativeai as genai

# Your free Gemini API key
genai.configure(api_key="AIzaSyDrKv5iF_StrmTyRZXH_QgDoMNoD6ZY_XM")

# The policy document we want to audit
policy_document = """
Our company collects user names, emails, and location data.
We use this data to improve our services and share it with
third-party advertising partners. Users can contact us at
support@company.com if they have questions. We store data
on servers in the United States. Children are allowed to
use our platform with parental consent.
"""

# The compliance checklist - this is YOUR domain expertise
checklist = """
1. Is there a clear data retention period specified?
2. Is there a grievance redressal mechanism with contact details?
3. Is consent obtained before sharing data with third parties?
4. Is there a provision for users to request data deletion?
5. Are special protections in place for children's data?
"""

# Set up the model
model = genai.GenerativeModel("gemini-2.5-flash-lite")

# Send the document for analysis
response = model.generate_content(f"""You are an AI governance compliance expert 
specialising in India's Digital Personal Data Protection Act 2023.

Analyse this company policy document against the checklist below.
For each checklist item, say PASS, FAIL, or PARTIAL and explain why 
in one sentence.

POLICY DOCUMENT:
{policy_document}

COMPLIANCE CHECKLIST:
{checklist}

Format your response as:
1. [PASS/FAIL/PARTIAL] - explanation
2. [PASS/FAIL/PARTIAL] - explanation
etc.""")

print("DPDP COMPLIANCE AUDIT RESULT")
print("=" * 40)
print(response.text)