import requests

url = "https://www.meity.gov.in/writereaddata/files/Digital%20Personal%20Data%20Protection%20Act%202023.pdf"

response = requests.get(url)

with open("dpdp_act.pdf", "wb") as f:
    f.write(response.content)

print("Downloaded successfully. File size:", len(response.content), "bytes")

