import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from collections import Counter

analyzer = SentimentIntensityAnalyzer()

def score_sentiment(text: str) -> float:
    if not text:
        return 0.0
    return analyzer.polarity_scores(text)["compound"]

def get_price_band(businesses: list[dict]) -> str:
    bands = [b.get("price_range") for b in businesses if b.get("price_range")]
    if not bands:
        return "unknown"
    count = Counter(bands)
    most_common = count.most_common()
    all_bands = {"budget", "mid-range", "premium"}
    present = set(count.keys())
    missing = all_bands - present
    if missing:
        return missing.pop()
    return f"all price bands covered, most common: {most_common[0][0]}"

def get_competition_density(total: int) -> str:
    if total < 5:
        return "low"
    elif total < 15:
        return "medium"
    return "high"

def get_common_complaints(businesses: list[dict]) -> str:
    all_complaints = []
    for b in businesses:
        complaints = b.get("top_complaints", [])
        if isinstance(complaints, list):
            all_complaints.extend(complaints)
        elif isinstance(complaints, str):
            try:
                parsed = json.loads(complaints)
                all_complaints.extend(parsed)
            except Exception:
                pass
    if not all_complaints:
        return "no complaints data available"
    count = Counter(all_complaints)
    top = [item for item, _ in count.most_common(3)]
    return ", ".join(top)

def run_analytics(businesses: list[dict]) -> dict:
    ratings = [b.get("rating") for b in businesses if b.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    for b in businesses:
        reviews = b.get("reviews", [])
        if isinstance(reviews, list):
            complaints = b.get("top_complaints", [])
            if isinstance(complaints, str):
                import json
                complaints = json.loads(complaints)
            review_text = " ".join(complaints) if complaints else " ".join(reviews)
        else:
            review_text = ""
        b["sentiment_score"] = score_sentiment(review_text)

    return {
        "total_businesses": len(businesses),
        "avg_rating": avg_rating,
        "competition_density": get_competition_density(len(businesses)),
        "underserved_price_band": get_price_band(businesses),
        "common_complaints": get_common_complaints(businesses)
    }
