import os
import stripe
from flask import redirect, request, url_for
from datetime import datetime, timedelta
from models import PaketBuchung, Praxis
# Import db später, um zirkuläre Imports zu vermeiden

# Stripe Secret Key aus Umgebungsvariablen laden
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Domain für Redirect-URLs
def get_domain():
    """Bestimmt die Domain für Redirect-URLs"""
    if os.environ.get('REPLIT_DEPLOYMENT'):
        return os.environ.get('REPLIT_DEV_DOMAIN')
    elif os.environ.get('REPLIT_DOMAINS'):
        return os.environ.get('REPLIT_DOMAINS').split(',')[0]
    else:
        return request.host

# Produktpreise (in Cent)
PRICES = {
    'praxispro': {
        'monatlich': 2900,  # 29 EUR/Monat
        'jaehrlich': 25000  # 250 EUR/Jahr
    },
    'praxisplus': {
        'monatlich': 4900,  # 49 EUR/Monat
        'jaehrlich': 45000  # 450 EUR/Jahr
    }
}

def create_checkout_session(praxis_id, paket, zahlweise):
    """
    Erstellt eine Stripe Checkout Session für ein Paket-Upgrade
    """
    try:
        # Praxis aus der Datenbank laden
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
            
        # Domain für Redirect-URLs
        domain = get_domain()
        success_url = f'https://{domain}{url_for("zahlung_erfolgreich")}'
        cancel_url = f'https://{domain}{url_for("paketwahl")}'
        
        # Paketpreis ermitteln
        price_cents = PRICES.get(paket, {}).get(zahlweise)
        if not price_cents:
            return {'error': 'Ungültiges Paket oder Zahlweise'}
            
        # Paketname für Anzeige formatieren
        paket_name = 'PraxisPro' if paket == 'praxispro' else 'PraxisPlus'
        zahlweise_text = 'pro Monat' if zahlweise == 'monatlich' else 'pro Jahr'
        
        # Stripe Checkout Session erstellen
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Dentalax {paket_name} ({zahlweise_text})',
                        'description': f'Premiumpaket für Ihre Zahnarztpraxis auf Dentalax.de',
                    },
                    'unit_amount': price_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'praxis_id': str(praxis_id),
                'paket': paket,
                'zahlweise': zahlweise
            },
        )
        
        # Buchung in der Datenbank speichern
        neue_buchung = PaketBuchung(
            paket=paket,
            zahlweise=zahlweise,
            preis=price_cents / 100.0,  # in Euro umrechnen
            zahlungsmethode='stripe',
            zahlungsstatus='ausstehend',
            stripe_session_id=checkout_session.id,
            praxis_id=praxis_id,
            erstellt_am=datetime.now()
        )
        # Import db hier, um zirkuläre Imports zu vermeiden
        from database import db
        db.session.add(neue_buchung)
        db.session.commit()
        
        return {
            'url': checkout_session.url,
            'session_id': checkout_session.id
        }
        
    except Exception as e:
        print(f"Stripe Fehler: {str(e)}")
        return {'error': str(e)}

def handle_payment_success(session_id):
    """
    Verarbeitet erfolgreiche Zahlungen nach dem Stripe Webhook oder manuellem Aufruf
    """
    try:
        # Buchung in der Datenbank finden
        buchung = PaketBuchung.query.filter_by(stripe_session_id=session_id).first()
        if not buchung:
            return {'error': 'Buchung nicht gefunden'}
            
        # Praxis laden
        praxis = Praxis.query.get(buchung.praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
            
        # Zahlungsstatus aktualisieren
        buchung.zahlungsstatus = 'bezahlt'
        buchung.bezahlt_am = datetime.now()
        
        # Praxis-Paket aktualisieren
        praxis.paket = buchung.paket
        
        # Gültigkeitsdauer setzen
        if buchung.zahlweise == 'jaehrlich':
            praxis.paket_aktiv_bis = datetime.now() + timedelta(days=365)
        else:
            praxis.paket_aktiv_bis = datetime.now() + timedelta(days=30)
        
        # Import db hier, um zirkuläre Imports zu vermeiden
        from database import db
        db.session.commit()
        
        return {'success': True, 'praxis_id': praxis.id, 'paket': praxis.paket}
        
    except Exception as e:
        print(f"Fehler bei Zahlungsverarbeitung: {str(e)}")
        return {'error': str(e)}