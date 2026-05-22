import requests
import time
from bs4 import BeautifulSoup
from core.config import settings

def fetch_google_places(city: str, category: str) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    query = f"{category} in {city} India"
    params = {
        "query": query,
        "key": settings.google_places_api_key,
        "region": "in"
    }
    response = requests.get(url, params=params)
    data = response.json()
    results = []
    for place in data.get("results", [])[:settings.max_results_per_source]:
        results.append({
            "name": place.get("name"),
            "rating": place.get("rating"),
            "review_count": place.get("user_ratings_total"),
            "address": place.get("formatted_address"),
            "price_level": place.get("price_level"),
            "source": "google_places"
        })
    time.sleep(settings.request_delay_seconds)
    return results

def fetch_justdial(city: str, category: str) -> list[dict]:
    category_slug = category.replace(" ", "-").lower()
    city_slug = city.lower()
    url = f"https://www.justdial.com/{city_slug}/{category_slug}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    listings = soup.find_all("li", class_="cntanr")[:settings.max_results_per_source]
    for listing in listings:
        name_tag = listing.find("span", class_="lng_cont_name")
        rating_tag = listing.find("span", class_="green-box")
        address_tag = listing.find("span", class_="cont_fl_addr")
        results.append({
            "name": name_tag.text.strip() if name_tag else None,
            "rating": float(rating_tag.text.strip()) if rating_tag else None,
            "review_count": None,
            "address": address_tag.text.strip() if address_tag else None,
            "price_level": None,
            "source": "justdial"
        })
    time.sleep(settings.request_delay_seconds)
    return results

def crawl(city: str, category: str) -> list[dict]:
    results = []
    try:
        results += fetch_google_places(city, category)
    except Exception:
        pass
    try:
        results += fetch_justdial(city, category)
    except Exception:
        pass
    return results