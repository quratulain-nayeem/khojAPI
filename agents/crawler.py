"""Fetch business listings using Google Places API (New)."""
import time
from urllib.parse import quote

import requests
from core.config import settings

PLACES_URL = "https://places.googleapis.com/v1/places"
SEARCH_FIELDS = "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress,places.priceLevel"
DETAIL_FIELDS = "nationalPhoneNumber,reviews"
PRICE_MAP = {
    "PRICE_LEVEL_FREE": "budget",
    "PRICE_LEVEL_INEXPENSIVE": "budget",
    "PRICE_LEVEL_MODERATE": "mid-range",
    "PRICE_LEVEL_EXPENSIVE": "premium",
    "PRICE_LEVEL_VERY_EXPENSIVE": "premium",
}


class PlacesError(RuntimeError):
    """A safe, actionable Google Places error for the job status response."""


def request_places(method: str, url: str, fields: str, body=None) -> dict:
    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": fields,
    }
    try:
        response = requests.request(method, url, headers=headers, json=body, timeout=(5, 20))
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PlacesError("Google Places could not be reached or returned an invalid response. Try again later.") from exc
    if not isinstance(data, dict):
        raise PlacesError("Google Places returned an invalid response.")
    if not response.ok or "error" in data:
        error = data.get("error", {})
        if not isinstance(error, dict):
            error = {}
        status = error.get("status")
        reasons = {d.get("reason") for d in error.get("details", []) if isinstance(d, dict)}
        guidance = {
            "PERMISSION_DENIED": "Check Places API (New) is enabled, billing is active, and this server is allowed by the key restrictions.",
            "UNAUTHENTICATED": "Google rejected the API key. Check GOOGLE_PLACES_API_KEY in Space Secrets.",
            "RESOURCE_EXHAUSTED": "Google Places quota was exceeded. Check usage and billing in Google Cloud.",
            "INVALID_ARGUMENT": "Google Places rejected the search parameters or API key.",
            "NOT_FOUND": "Google could not find this place.",
        }
        safe_status = status if status in guidance else f"HTTP_{response.status_code}"
        advice = guidance.get(status, "Google Places could not complete this request. Try again later.")
        # Use only known error reasons; never expose arbitrary provider messages or credentials.
        for reason, message in (
            ("BILLING_DISABLED", "Enable billing on the Google Cloud project that owns this API key."),
            ("SERVICE_DISABLED", "Enable Places API (New) on the Google Cloud project that owns this API key."),
            ("API_KEY_INVALID", "Google rejected the API key. Check GOOGLE_PLACES_API_KEY in Space Secrets."),
            ("API_KEY_SERVICE_BLOCKED", "The key's API restrictions must allow Places API (New)."),
            ("API_KEY_HTTP_REFERRER_BLOCKED", "This is a server request; a website-referrer-restricted key cannot authorize it."),
            ("API_KEY_IP_ADDRESS_BLOCKED", "The key's IP restrictions do not allow this server."),
        ):
            if reason in reasons:
                advice = message
                break
        raise PlacesError(f"Google Places (New): {safe_status}. {advice}")
    return data


def fetch_place_details(place_id: str) -> dict:
    result = request_places("GET", f"{PLACES_URL}/{quote(place_id, safe='')}", DETAIL_FIELDS)
    review_texts = []
    for review in result.get("reviews", []):
        text = (review.get("text") or review.get("originalText") or {}).get("text")
        if text:
            review_texts.append(text)
    return {"phone": result.get("nationalPhoneNumber"), "reviews": review_texts}


def fetch_google_places(city: str, category: str, locality: str) -> list[dict]:
    limit = min(20, max(1, settings.max_results_per_source))
    data = request_places("POST", f"{PLACES_URL}:searchText", SEARCH_FIELDS, {
        "textQuery": f"{category} in {locality}, {city}",
        "regionCode": "IN",
        "pageSize": limit,
    })
    results = []
    for place in data.get("places", [])[:limit]:
        place_id = place.get("id")
        if not place_id:
            raise PlacesError("Google Places returned a listing without a place ID.")
        details = fetch_place_details(place_id)
        time.sleep(settings.request_delay_seconds)
        results.append({
            "name": (place.get("displayName") or {}).get("text"),
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount"),
            "address": place.get("formattedAddress"),
            "phone": details.get("phone"),
            "price_range": PRICE_MAP.get(place.get("priceLevel")),
            "reviews": details.get("reviews", []),
            "source": "google_places",
        })
    return results


def crawl(city: str, category: str, locality: str) -> list[dict]:
    return fetch_google_places(city, category, locality)
