import requests
import time
from core.config import settings

PRICE_MAP = {0: "budget", 1: "budget", 2: "mid-range", 3: "premium", 4: "premium"}

class PlacesError(RuntimeError):
    """A safe, actionable Google Places error for the job status response."""

def request_places(url: str, params: dict) -> dict:
    try:
        response = requests.get(url, params=params, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        # Request exception URLs may contain the API key: never expose them.
        raise PlacesError("Google Places could not be reached or returned an invalid response. Try again later.") from exc
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        guidance = {
            "REQUEST_DENIED": "Check the Google Places API key, API restrictions, and billing in Google Cloud. This app uses Places API (Legacy).",
            "OVER_QUERY_LIMIT": "Google Places quota was exceeded. Check usage and billing in Google Cloud.",
            "INVALID_REQUEST": "Google Places rejected the search parameters.",
        }.get(status, "Google Places could not complete this request. Try again later.")
        safe_status = status if status in ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "INVALID_REQUEST", "UNKNOWN_ERROR", "NOT_FOUND") else "UNEXPECTED_RESPONSE"
        raise PlacesError(f"Google Places: {safe_status}. {guidance}")
    return data

def fetch_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,reviews",
        "key": settings.google_places_api_key
    }
    data = request_places(url, params)
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
    data = request_places(url, params)
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
    return fetch_google_places(city, category, locality)
