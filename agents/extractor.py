import json
import uuid
from groq import Groq
from core.config import settings

client = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract structured business "
    "information from raw data. Always respond with valid JSON only. "
    "No explanation, no markdown."
)

USER_PROMPT = """Extract and structure this business listing:
{raw_business}

Return a JSON object with these exact keys:
- name (string)
- rating (float or null)
- review_count (integer or null)
- price_range (string: budget/mid-range/premium or null)
- phone (string or null)
- top_complaints (list of max 3 strings based on any available context)
- tags (list of strings describing the business type)
"""

def extract_business(raw: dict) -> dict:
    raw_str = json.dumps(raw)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(raw_business=raw_str)},
        ],
    )
    try:
        cleaned = response.choices[0].message.content.strip()
        return json.loads(cleaned)
    except Exception:
        return raw

def extract_all(raw_businesses: list[dict]) -> list[dict]:
    extracted = []
    for business in raw_businesses:
        result = extract_business(business)
        result["source"] = business.get("source", "unknown")
        result["id"] = str(uuid.uuid4())
        extracted.append(result)
    return extracted
