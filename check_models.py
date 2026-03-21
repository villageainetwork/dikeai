import google.generativeai as genai

genai.configure(api_key="YOUR_ACTUAL_KEY_HERE")

print("Available models on your account:")
print("-" * 40)

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)