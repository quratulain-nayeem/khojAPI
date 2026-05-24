import json
import re
import uuid
from groq import Groq
from core.config import settings

client = Groq(api_key=settings.groq_api_key)

PRICE_RANGES = {"budget", "mid-range", "premium"}
COMPLAINT_KEYWORDS = (
    "bad", "rude", "slow", "delay", "delayed", "late", "wait", "waiting",
    "expensive", "costly", "overpriced", "dirty", "poor", "worst",
    "unprofessional", "crowded", "issue", "problem", "complaint", "avoid",
    "refund", "charged", "billing", "not good", "disappointed",
)

SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract structured business "
    "information from raw data. Always respond with valid JSON only. "
    "No explanation, no markdown."
)

USER_PROMPT = """Extract and structure this business listing:
{raw_business}

The 'reviews' field contains real customer review texts. Use them to identify complaints.

Return a JSON object with these exact keys:
- name (string)
- rating (float or null)
- review_count (integer or null)
- price_range (string: must be one of budget/mid-range/premium — infer from name, address, or rating if not explicitly provided)
- phone (string or null)
- address (string — copy exactly from input if present)
- top_complaints (list of max 3 strings — extract real complaints from reviews, empty list if no reviews)
- tags (list of strings describing the business type)
"""

def normalize_price_range(value) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized in PRICE_RANGES else None

def to_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def infer_price_range(raw: dict, extracted: dict) -> str:
    price_range = normalize_price_range(extracted.get("price_range")) or normalize_price_range(raw.get("price_range"))
    if price_range:
        return price_range

    rating = to_number(extracted.get("rating") or raw.get("rating"))
    review_count = to_number(extracted.get("review_count") or raw.get("review_count"))
    if rating >= 4.6 and review_count >= 100:
        return "premium"
    if rating < 4.0:
        return "budget"
    return "mid-range"

def fallback_complaints(raw: dict) -> list[str]:
    complaints = []
    for review in raw.get("reviews", []):
        text = str(review).strip()
        if not text:
            continue
        lowered = text.lower()
        if any(keyword in lowered for keyword in COMPLAINT_KEYWORDS):
            cleaned = re.sub(r"\s+", " ", text)
            complaints.append(cleaned)
        if len(complaints) == 3:
            break
    return complaints

def extract_business(raw: dict) -> dict:
    raw_str = json.dumps(raw)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(raw_business=raw_str)},
            ],
        )
        cleaned = response.choices[0].message.content.strip()
        return json.loads(cleaned)
    except Exception as exc:
        print(f"EXTRACTOR FALLBACK: {exc}")
        return {
            "name": raw.get("name"),
            "rating": raw.get("rating"),
            "review_count": raw.get("review_count"),
            "price_range": infer_price_range(raw, {}),
            "phone": raw.get("phone"),
            "address": raw.get("address"),
            "top_complaints": fallback_complaints(raw),
            "tags": [],
        }

def extract_all(raw_businesses: list[dict]) -> list[dict]:
    extracted = []
    for business in raw_businesses:
        result = extract_business(business)
        result["address"] = result.get("address") or business.get("address")
        result["price_range"] = infer_price_range(business, result)
        if not result.get("top_complaints"):
            result["top_complaints"] = fallback_complaints(business)
        result["reviews"] = business.get("reviews", [])
        result["source"] = business.get("source", "unknown")
        result["id"] = str(uuid.uuid4())
        extracted.append(result)
    return extracted
