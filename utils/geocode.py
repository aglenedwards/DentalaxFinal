import requests
import os

def get_coordinates_from_address(address):
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

    if not api_key:
        print("⚠️ GOOGLE_MAPS_API_KEY nicht gesetzt - Geocoding übersprungen")
        return None, None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key,
        "region": "de"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        print("Geocoding fehlgeschlagen:", data)
        return None, None
