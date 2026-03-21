# We'll use a simple text string instead of a PDF
# Same logic - real product will accept uploaded PDFs from users

dpdp_text = """
CHAPTER I - PRELIMINARY
Section 1 - Short title and commencement
Section 2 - Definitions

CHAPTER II - OBLIGATIONS OF DATA FIDUCIARY  
Section 3 - Grounds for processing personal data
Section 4 - Notice
Section 5 - Consent

CHAPTER III - RIGHTS AND DUTIES OF DATA PRINCIPAL
Section 11 - Right to access information
Section 12 - Right to correction and erasure
Section 13 - Right to grievance redressal
Section 14 - Right to nominate

CHAPTER IV - SPECIAL PROVISIONS
Section 16 - Processing of personal data of children

CHAPTER V - DATA PROTECTION BOARD OF INDIA
Section 18 - Establishment of Board

CHAPTER VI - PENALTIES
Section 33 - Penalties
"""

print("Scanning DPDP Act structure...")
print("-" * 40)

lines = dpdp_text.split("\n")

chapters = []
sections = []

for line in lines:
    line = line.strip()
    if line.startswith("CHAPTER"):
        chapters.append(line)
        print(f"CHAPTER FOUND: {line}")
    elif line.startswith("Section"):
        sections.append(line)
        print(f"  Section found: {line}")

print("-" * 40)
print(f"Total chapters: {len(chapters)}")
print(f"Total sections: {len(sections)}")