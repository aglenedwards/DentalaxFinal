"""
Stripe Subscription Management für Dentalax
Verwendet die Replit Stripe-Integration für API-Keys
"""
import os
import stripe
from flask import redirect, request, url_for
from datetime import datetime, timedelta

# Stripe Price IDs - Diese müssen in Stripe erstellt werden
# Wir verwenden Stripe Subscriptions statt One-Time Payments
SUBSCRIPTION_PRICES = {
    'praxispro': {
        'monatlich': None,  # Wird durch seed_products gesetzt
        'jaehrlich': None,
    },
    'praxisplus': {
        'monatlich': None,
        'jaehrlich': None,
    }
}

# Fallback-Preise in Cent (für Anzeige und Checkout)
PRICES_DISPLAY = {
    'praxispro': {
        'monatlich': 5900,  # 59 EUR/Monat
        'jaehrlich': 63600  # 636 EUR/Jahr (10% Ersparnis)
    },
    'praxisplus': {
        'monatlich': 8900,  # 89 EUR/Monat
        'jaehrlich': 96000  # 960 EUR/Jahr (10% Ersparnis)
    }
}


def get_stripe_credentials():
    """Holt Stripe-Credentials von der Replit Connection API"""
    import json
    
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    repl_identity = os.environ.get('REPL_IDENTITY')
    web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
    
    if repl_identity:
        x_replit_token = f'repl {repl_identity}'
    elif web_repl_renewal:
        x_replit_token = f'depl {web_repl_renewal}'
    else:
        # Fallback auf STRIPE_SECRET_KEY Environment Variable
        secret_key = os.environ.get('STRIPE_SECRET_KEY')
        if secret_key:
            return {'secret_key': secret_key, 'publishable_key': None}
        raise Exception('Keine Stripe-Credentials verfügbar')
    
    is_production = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    target_environment = 'production' if is_production else 'development'
    
    import urllib.request
    import urllib.parse
    
    url = f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=stripe&environment={target_environment}"
    
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('X_REPLIT_TOKEN', x_replit_token)
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        connection_settings = data.get('items', [{}])[0]
        settings = connection_settings.get('settings', {})
        
        if not settings.get('secret') or not settings.get('publishable'):
            raise Exception(f'Stripe {target_environment} connection nicht gefunden')
        
        return {
            'secret_key': settings['secret'],
            'publishable_key': settings['publishable']
        }
    except Exception as e:
        # Fallback auf STRIPE_SECRET_KEY
        secret_key = os.environ.get('STRIPE_SECRET_KEY')
        if secret_key:
            return {'secret_key': secret_key, 'publishable_key': None}
        raise e


def get_stripe_client():
    """Gibt einen konfigurierten Stripe-Client zurück"""
    credentials = get_stripe_credentials()
    stripe.api_key = credentials['secret_key']
    return stripe


def get_domain():
    """Bestimmt die Domain für Redirect-URLs"""
    if os.environ.get('REPLIT_DEPLOYMENT'):
        return os.environ.get('REPLIT_DEV_DOMAIN')
    elif os.environ.get('REPLIT_DOMAINS'):
        return os.environ.get('REPLIT_DOMAINS').split(',')[0]
    else:
        return request.host


def get_or_create_customer(praxis):
    """Erstellt oder holt einen Stripe Customer für eine Praxis"""
    stripe_client = get_stripe_client()
    
    if praxis.stripe_customer_id:
        try:
            customer = stripe_client.Customer.retrieve(praxis.stripe_customer_id)
            if not customer.get('deleted'):
                return customer
        except stripe.error.InvalidRequestError:
            pass
    
    # Neuen Customer erstellen
    customer = stripe_client.Customer.create(
        email=praxis.email,
        name=praxis.name,
        metadata={
            'praxis_id': str(praxis.id),
            'praxis_name': praxis.name
        }
    )
    
    # Customer ID in Praxis speichern
    praxis.stripe_customer_id = customer.id
    from database import db
    db.session.commit()
    
    return customer


def create_subscription_checkout(praxis_id, paket, zahlweise):
    """
    Erstellt eine Stripe Checkout Session für ein Subscription-Upgrade
    """
    from models import Praxis, PaketBuchung
    from database import db
    
    try:
        stripe_client = get_stripe_client()
        
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        # Customer erstellen/holen
        customer = get_or_create_customer(praxis)
        
        # Domain für Redirect-URLs
        domain = get_domain()
        success_url = f'https://{domain}/zahnarzt-dashboard?page=abrechnung&success=1'
        cancel_url = f'https://{domain}/zahnarzt-dashboard?page=abrechnung&canceled=1'
        
        # Paketname für Anzeige
        paket_name = 'PraxisPro' if paket == 'praxispro' else 'PraxisPlus'
        interval = 'month' if zahlweise == 'monatlich' else 'year'
        price_cents = PRICES_DISPLAY.get(paket, {}).get(zahlweise, 2900)
        
        # Checkout Session mit Subscription Mode erstellen
        checkout_session = stripe_client.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Dentalax {paket_name}',
                        'description': f'Premium-Paket für Ihre Zahnarztpraxis auf Dentalax.de',
                    },
                    'unit_amount': price_cents,
                    'recurring': {
                        'interval': interval,
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url + '&session_id={CHECKOUT_SESSION_ID}',
            cancel_url=cancel_url,
            metadata={
                'praxis_id': str(praxis_id),
                'paket': paket,
                'zahlweise': zahlweise,
                'action': 'upgrade'
            },
            subscription_data={
                'metadata': {
                    'praxis_id': str(praxis_id),
                    'paket': paket,
                }
            }
        )
        
        # Buchung in der Datenbank speichern
        neue_buchung = PaketBuchung(
            paket=paket,
            zahlweise=zahlweise,
            preis=price_cents / 100.0,
            zahlungsmethode='stripe_subscription',
            zahlungsstatus='ausstehend',
            stripe_session_id=checkout_session.id,
            praxis_id=praxis_id,
            erstellt_am=datetime.now()
        )
        db.session.add(neue_buchung)
        db.session.commit()
        
        return {
            'url': checkout_session.url,
            'session_id': checkout_session.id
        }
        
    except Exception as e:
        print(f"Stripe Subscription Fehler: {str(e)}")
        return {'error': str(e)}


def handle_subscription_success(session_id):
    """
    Verarbeitet erfolgreiche Subscription-Zahlungen
    """
    from models import PaketBuchung, Praxis
    from database import db
    
    try:
        stripe_client = get_stripe_client()
        
        # Session von Stripe abrufen
        session = stripe_client.checkout.Session.retrieve(session_id)
        
        if session.payment_status != 'paid':
            return {'error': 'Zahlung noch nicht abgeschlossen'}
        
        # Buchung in der Datenbank finden
        buchung = PaketBuchung.query.filter_by(stripe_session_id=session_id).first()
        if not buchung:
            return {'error': 'Buchung nicht gefunden'}
        
        if buchung.zahlungsstatus == 'bezahlt':
            # Bereits verarbeitet
            return {'success': True, 'already_processed': True}
        
        # Praxis laden
        praxis = Praxis.query.get(buchung.praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        # Subscription-ID aus Session holen
        subscription_id = session.subscription
        
        # Zahlungsstatus aktualisieren
        buchung.zahlungsstatus = 'bezahlt'
        buchung.bezahlt_am = datetime.now()
        
        # Praxis-Paket und Subscription aktualisieren
        praxis.paket = buchung.paket
        praxis.zahlungsart = buchung.zahlweise
        praxis.stripe_subscription_id = subscription_id
        praxis.stripe_subscription_status = 'active'
        
        # Gültigkeitsdauer setzen
        if buchung.zahlweise == 'jaehrlich':
            praxis.paket_aktiv_bis = datetime.now() + timedelta(days=365)
        else:
            praxis.paket_aktiv_bis = datetime.now() + timedelta(days=30)
        
        db.session.commit()
        
        return {'success': True, 'praxis_id': praxis.id, 'paket': praxis.paket}
        
    except Exception as e:
        print(f"Fehler bei Subscription-Verarbeitung: {str(e)}")
        return {'error': str(e)}


def create_customer_portal_session(praxis_id):
    """
    Erstellt eine Stripe Customer Portal Session für Abo-Verwaltung
    """
    from models import Praxis
    
    try:
        stripe_client = get_stripe_client()
        
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        if not praxis.stripe_customer_id:
            return {'error': 'Kein Stripe-Customer vorhanden'}
        
        domain = get_domain()
        return_url = f'https://{domain}/zahnarzt-dashboard?page=abrechnung'
        
        portal_session = stripe_client.billing_portal.Session.create(
            customer=praxis.stripe_customer_id,
            return_url=return_url,
        )
        
        return {'url': portal_session.url}
        
    except Exception as e:
        print(f"Stripe Portal Fehler: {str(e)}")
        return {'error': str(e)}


def cancel_subscription(praxis_id, at_period_end=True):
    """
    Kündigt ein Subscription (zum Ende der Laufzeit)
    """
    from models import Praxis
    from database import db
    
    try:
        stripe_client = get_stripe_client()
        
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        if not praxis.stripe_subscription_id:
            return {'error': 'Kein aktives Abonnement vorhanden'}
        
        if at_period_end:
            # Kündigung zum Ende der Laufzeit
            subscription = stripe_client.Subscription.modify(
                praxis.stripe_subscription_id,
                cancel_at_period_end=True
            )
            praxis.stripe_subscription_status = 'cancel_at_period_end'
        else:
            # Sofortige Kündigung
            subscription = stripe_client.Subscription.cancel(
                praxis.stripe_subscription_id
            )
            praxis.stripe_subscription_status = 'canceled'
            praxis.paket = 'basic'
        
        db.session.commit()
        
        return {'success': True, 'subscription': subscription}
        
    except Exception as e:
        print(f"Stripe Kündigung Fehler: {str(e)}")
        return {'error': str(e)}


def change_subscription_plan(praxis_id, new_paket, new_zahlweise):
    """
    Wechselt zu einem anderen Plan (Upgrade oder Downgrade)
    """
    from models import Praxis
    from database import db
    
    try:
        stripe_client = get_stripe_client()
        
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        if not praxis.stripe_subscription_id:
            # Keine aktive Subscription - neue erstellen
            return create_subscription_checkout(praxis_id, new_paket, new_zahlweise)
        
        # Für Plan-Wechsel: Neue Checkout Session erstellen
        # Stripe handhabt Prorating automatisch
        return create_subscription_checkout(praxis_id, new_paket, new_zahlweise)
        
    except Exception as e:
        print(f"Stripe Plan-Wechsel Fehler: {str(e)}")
        return {'error': str(e)}


def get_subscription_details(praxis_id):
    """
    Holt Details zur aktuellen Subscription einer Praxis
    """
    from models import Praxis
    
    try:
        stripe_client = get_stripe_client()
        
        praxis = Praxis.query.get(praxis_id)
        if not praxis:
            return {'error': 'Praxis nicht gefunden'}
        
        if not praxis.stripe_subscription_id:
            return {
                'has_subscription': False,
                'paket': praxis.paket,
                'aktiv_bis': praxis.paket_aktiv_bis
            }
        
        subscription = stripe_client.Subscription.retrieve(praxis.stripe_subscription_id)
        
        return {
            'has_subscription': True,
            'paket': praxis.paket,
            'status': subscription.status,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
            'aktiv_bis': praxis.paket_aktiv_bis
        }
        
    except Exception as e:
        print(f"Stripe Details Fehler: {str(e)}")
        return {'error': str(e)}


def handle_webhook_event(payload, sig_header):
    """
    Verarbeitet Stripe Webhook Events
    """
    from models import Praxis
    from database import db
    
    try:
        stripe_client = get_stripe_client()
        
        # Webhook Secret aus Environment (muss in Stripe konfiguriert werden)
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if webhook_secret:
            event = stripe_client.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Ohne Webhook Secret (nur für Development)
            import json
            event = json.loads(payload)
        
        event_type = event.get('type') if isinstance(event, dict) else event.type
        data = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event.data.object
        
        if event_type == 'customer.subscription.updated':
            subscription_id = data.get('id') if isinstance(data, dict) else data.id
            status = data.get('status') if isinstance(data, dict) else data.status
            
            praxis = Praxis.query.filter_by(stripe_subscription_id=subscription_id).first()
            if praxis:
                praxis.stripe_subscription_status = status
                if status == 'canceled':
                    praxis.paket = 'basic'
                db.session.commit()
        
        elif event_type == 'customer.subscription.deleted':
            subscription_id = data.get('id') if isinstance(data, dict) else data.id
            
            praxis = Praxis.query.filter_by(stripe_subscription_id=subscription_id).first()
            if praxis:
                praxis.stripe_subscription_status = 'canceled'
                praxis.paket = 'basic'
                praxis.stripe_subscription_id = None
                db.session.commit()
        
        elif event_type == 'invoice.payment_succeeded':
            subscription_id = data.get('subscription') if isinstance(data, dict) else data.subscription
            
            praxis = Praxis.query.filter_by(stripe_subscription_id=subscription_id).first()
            if praxis:
                # Verlängere paket_aktiv_bis
                if praxis.zahlungsart == 'jaehrlich':
                    praxis.paket_aktiv_bis = datetime.now() + timedelta(days=365)
                else:
                    praxis.paket_aktiv_bis = datetime.now() + timedelta(days=30)
                db.session.commit()
        
        elif event_type == 'invoice.payment_failed':
            subscription_id = data.get('subscription') if isinstance(data, dict) else data.subscription
            
            praxis = Praxis.query.filter_by(stripe_subscription_id=subscription_id).first()
            if praxis:
                praxis.stripe_subscription_status = 'past_due'
                db.session.commit()
        
        return {'success': True}
        
    except Exception as e:
        print(f"Webhook Fehler: {str(e)}")
        return {'error': str(e)}
