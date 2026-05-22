import requests
import time
from core.config import settings

PRICE_MAP = {0: "budget", 1: "budget", 2: "mid-range", 3: "premium", 4: "premium"}

def fetch_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,reviews",
        "key": settings.google_places_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    result = data.get("result", {})
    
    reviews = result.get("reviews", [])
    review_texts = [r.get("text", "") for r in reviews if r.get("text")]
    
    return {
        "phone": result.get("formatted_phone_number"),
        "reviews": review_texts
    }

def fetch_google_places(city: str, category: str, locality: str) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{category} in {locality}, {city}",
        "key": settings.google_places_api_key,
        "region": "in"
    }
    response = requests.get(url, params=params)
    data = response.json()
    results = []

    for place in data.get("results", [])[:settings.max_results_per_source]:
        place_id = place.get("place_id")
        price_level = place.get("price_level")

        # fetch reviews and phone for each business
        details = fetch_place_details(place_id)
        time.sleep(settings.request_delay_seconds)

        results.append({
            "name": place.get("name"),
            "rating": place.get("rating"),
            "review_count": place.get("user_ratings_total"),
            "address": place.get("formatted_address"),
            "phone": details.get("phone"),
            "price_range": PRICE_MAP.get(price_level),
            "reviews": details.get("reviews", []),
            "source": "google_places"
        })

    return results

def crawl(city: str, category: str, locality: str) -> list[dict]:
    results = []
    try:
        results += fetch_google_places(city, category, locality)
    except Exception as e:
        print(f"CRAWLER ERROR: {e}")
    return results