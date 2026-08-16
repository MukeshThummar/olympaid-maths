"""Quick test to find which Gemini model works with this API key."""
from pathlib import Path
from google import genai
from google.genai import types
import sys

api_key = Path("gemini_api_key.txt").read_text().strip()
client = genai.Client(api_key=api_key)

# Test candidates - prefer newer/faster models
candidates = [
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
]

print("Testing models with a simple text prompt:")
sys.stdout.reconfigure(encoding='utf-8')

for model in candidates:
    try:
        resp = client.models.generate_content(
            model=model,
            contents=[types.Part.from_text(text="Say exactly: HELLO WORLD")],
            config=types.GenerateContentConfig(max_output_tokens=20),
        )
        result_text = resp.text if resp.text else "(no text returned)"
        print(f"  OK   {model}  ->  {result_text.strip()[:50]}")
    except Exception as e:
        err = str(e).replace('\n', ' ')[:100]
        print(f"  FAIL {model}  ->  {err}")
