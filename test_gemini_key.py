"""
Standalone Gemini API key tester.
Run this BEFORE starting the full app to quickly check if your key works,
without needing to spin up the backend/frontend.

Usage (from the RAGent project folder, with venv activated):
    python test_gemini_key.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY", "")

print("=" * 60)
print("RAGent — Gemini API Key Tester")
print("=" * 60)

if not api_key or api_key == "PASTE_YOUR_REAL_GEMINI_KEY_HERE":
    print("❌ No key found in .env — set GEMINI_API_KEY first.")
    raise SystemExit(1)

masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key
print(f"Found key: {masked}")

if api_key.startswith("AIza"):
    print("Format: Standard key (AIza...) — the older format.")
elif api_key.startswith("AQ."):
    print("Format: Auth key (AQ...) — the newer format Google now issues.")
else:
    print("⚠️  Format doesn't match either known Gemini key pattern — double check it was copied correctly from aistudio.google.com.")

print("\nTrying a live test call via the official google-genai SDK...\n")

try:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents="Reply with exactly one word: OK",
    )
    print("✅ SUCCESS — Gemini responded:")
    print(f"   {response.text!r}")
    print("\nYour key works. The full RAGent app should work too.")

except Exception as e:
    print("❌ FAILED — the API call did not succeed.")
    print(f"   Error: {e}")
    print("""
This usually means one of:
  1. The key is genuinely invalid/expired — regenerate at aistudio.google.com
  2. You're hitting Google's known rollout bug with new "AQ." keys on some
     accounts (actively being reported on Google's developer forum as of
     mid-2026) — this is on Google's side, not your setup.
  3. Billing/region restrictions on your Google Cloud project.

If this keeps failing after regenerating the key and double-checking it was
copied correctly, it's worth trying a different account, or checking
Google's AI Studio status/forum for the latest on this specific bug.
""")
