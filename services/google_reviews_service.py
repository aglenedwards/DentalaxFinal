import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '') or os.environ.get('GOOGLE_PLACES_API_KEY', '')


def fetch_google_reviews(place_id):
    if not GOOGLE_PLACES_API_KEY:
        logger.warning("GOOGLE_PLACES_API_KEY nicht konfiguriert")
        return None
    
    if not place_id:
        return None
    
    url = "https://places.googleapis.com/v1/places/" + place_id
    
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': 'rating,userRatingCount,googleMapsUri,displayName'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'rating': data.get('rating'),
                'review_count': data.get('userRatingCount', 0),
                'maps_url': data.get('googleMapsUri', ''),
                'name': data.get('displayName', {}).get('text', ''),
                'success': True
            }
        else:
            logger.error(f"Google Places API Fehler: {response.status_code} - {response.text}")
            return {
                'success': False,
                'error': f"API-Fehler: {response.status_code}"
            }
    except requests.exceptions.Timeout:
        logger.error("Google Places API Timeout")
        return {'success': False, 'error': 'Zeitüberschreitung bei der Anfrage'}
    except Exception as e:
        logger.error(f"Google Places API Exception: {str(e)}")
        return {'success': False, 'error': str(e)}


def search_google_place(query, location=None):
    if not GOOGLE_PLACES_API_KEY:
        return None
    
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.googleMapsUri'
    }
    
    body = {
        'textQuery': query,
        'languageCode': 'de',
        'includedType': 'dentist'
    }
    
    if location:
        body['locationBias'] = {
            'circle': {
                'center': {
                    'latitude': location.get('lat', 0),
                    'longitude': location.get('lng', 0)
                },
                'radius': 5000.0
            }
        }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            places = data.get('places', [])
            results = []
            for place in places[:5]:
                results.append({
                    'place_id': place.get('id', '').replace('places/', ''),
                    'name': place.get('displayName', {}).get('text', ''),
                    'address': place.get('formattedAddress', ''),
                    'rating': place.get('rating'),
                    'review_count': place.get('userRatingCount', 0),
                    'maps_url': place.get('googleMapsUri', '')
                })
            return results
        else:
            logger.error(f"Google Places Search Fehler: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Google Places Search Exception: {str(e)}")
        return []


def sync_praxis_google_reviews(praxis):
    from app import db
    
    if not praxis.google_place_id:
        return {'success': False, 'error': 'Keine Google Place ID hinterlegt'}
    
    result = fetch_google_reviews(praxis.google_place_id)
    
    if result and result.get('success'):
        praxis.google_rating = result.get('rating')
        praxis.google_review_count = result.get('review_count', 0)
        praxis.google_maps_url = result.get('maps_url', '')
        praxis.google_sync_datum = datetime.utcnow()
        db.session.commit()
        return {
            'success': True,
            'rating': praxis.google_rating,
            'review_count': praxis.google_review_count,
            'maps_url': praxis.google_maps_url
        }
    
    return result or {'success': False, 'error': 'Unbekannter Fehler'}
