import os
import csv
import math
import json
import stripe
import re
import logging
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from os.path import isfile
from functools import wraps
from random import choice, Random

# Importiere Stripe-Integration
from stripe_integration import create_checkout_session, handle_payment_success

from flask import (
    Flask, render_template, request, redirect, session, url_for, flash, send_file, jsonify
)
from utils.geocode import get_coordinates_from_address
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

# Stripe API Key initialisieren
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Import app und db
from main import app, csrf
from database import db

# Login-Decorator für Admin-Routen
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_eingeloggt"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function

# Flask-Login Manager initialisieren
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "zahnarzt_login"
login_manager.login_message = "Bitte melden Sie sich an, um diese Seite zu nutzen."
login_manager.login_message_category = "info"
login_manager.session_protection = "basic"

# Modelle importieren
from models import Zahnarzt, Patient, Praxis, Oeffnungszeit, Leistung, TeamMitglied, Termin, PraxisBild, PaketBuchung, Claim, Terminanfrage, Bewertung, Behandlungsart, Verfuegbarkeit, Ausnahme, Stellenangebot, Bewerbung, ExternesInserat, JobAlert, SiteSettings

# TheirStack Service für externe Stellenangebote
from services.theirstack_service import sync_external_jobs, should_refresh_jobs, get_external_jobs, get_cities_with_jobs

@login_manager.user_loader
def load_user(user_id):
    try:
        # Versuche zuerst, einen Zahnarzt zu finden
        zahnarzt = Zahnarzt.query.get(int(user_id))
        if zahnarzt:
            return zahnarzt
            
        # Falls kein Zahnarzt gefunden, versuche einen Patienten zu finden
        patient = Patient.query.get(int(user_id))
        if patient:
            return patient
            
    except:
        return None

@app.before_request
def check_maintenance_mode():
    allowed_prefixes = ('/admin', '/static', '/wartung')
    path = request.path
    if any(path.startswith(p) for p in allowed_prefixes):
        return None
    if session.get('maintenance_bypass'):
        return None
    try:
        maintenance_active = SiteSettings.get('maintenance_mode', 'false') == 'true'
    except Exception:
        return None
    if maintenance_active:
        return render_template('maintenance.html'), 503


# Dynamischer SEO-Text - Stadt-basierter Index für konsistente Varianten pro Stadt
def get_city_index(stadt, num_options):
    """Berechnet einen deterministischen Index basierend auf der Stadt.
    Jede Stadt bekommt IMMER die gleiche Variante - vermeidet Duplicate Content."""
    import hashlib
    hash_input = stadt.lower().encode('utf-8')
    hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
    return hash_value % num_options

def seo_intro(stadt):
    texte = [
        f"Sie suchen einen kompetenten Zahnarzt in {stadt}? Auf Dentalax finden Sie moderne Zahnarztpraxen in Ihrer Umgebung.",
        f"In {stadt} finden Sie mit Dentalax schnell eine vertrauenswürdige Zahnarztpraxis – geprüft, nah und zuverlässig.",
        f"Jetzt den passenden Zahnarzt in {stadt} entdecken! Dentalax zeigt Ihnen top-bewertete Praxen aus Ihrer Region."
    ]
    return texte[get_city_index(stadt, len(texte))]

def seo_footer(stadt):
    texte = [
        f"In {stadt} profitieren Patientinnen und Patienten von einer breiten zahnmedizinischen Versorgung. Dentalax listet relevante Praxen basierend auf Entfernung, Fachrichtung und mehr.",
        f"{stadt} bietet ein vielfältiges Spektrum an Zahnärzten – von der klassischen Behandlung bis zu modernen Therapien. Unsere Plattform hilft bei der Auswahl.",
        f"Egal ob Vorsorge, Implantate oder Ästhetik – in {stadt} finden Sie passende Experten. Dentalax erleichtert Ihre Entscheidung mit übersichtlichen Ergebnissen."
    ]
    return texte[get_city_index(stadt, len(texte))]

def haversine_distance(lat1, lon1, lat2, lon2):
    """Berechnet die Haversine-Distanz zwischen zwei Koordinaten in Kilometern."""
    R = 6371  # Erdradius in km
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c

def seo_zahnarzt_h1(stadt):
    """H1-Varianten für Zahnarzt-Stadtseiten - jede Stadt bekommt konsistent dieselbe Variante"""
    texte = [
        f"Zahnarzt in {stadt}",
        f"Zahnärzte in {stadt} finden",
        f"Zahnarztpraxen in {stadt}",
        f"Ihren Zahnarzt in {stadt} finden"
    ]
    return texte[get_city_index(stadt, len(texte))]

def seo_job_h1(stadt):
    texte = [
        f"Dental Jobs in {stadt}",
        f"Stellenangebote Zahnmedizin {stadt}",
        f"Jobs in der Zahnmedizin – {stadt}"
    ]
    return texte[get_city_index(stadt, len(texte))]

def seo_job_intro(stadt):
    texte = [
        f"Finden Sie attraktive Stellenangebote in der Zahnmedizin in {stadt}. Von ZFA über Zahnarzt bis Praxismanagement – entdecken Sie Ihre Karrierechancen bei Top-Praxen.",
        f"Sie suchen einen Job in der Dentalbranche in {stadt}? Dentalax zeigt Ihnen aktuelle Stellenangebote von renommierten Zahnarztpraxen in Ihrer Region.",
        f"Karriere in der Zahnmedizin starten! In {stadt} warten spannende Jobs als ZFA, Dentalhygieniker/in, Zahnarzt/Zahnärztin und mehr auf Sie."
    ]
    return texte[get_city_index(stadt, len(texte))]

def seo_job_h2(stadt):
    texte = [
        f"Warum {stadt} für Ihre Dental-Karriere?",
        f"Arbeiten in der Zahnmedizin in {stadt}",
        f"Ihre berufliche Zukunft in {stadt}"
    ]
    return texte[get_city_index(stadt, len(texte))]

def seo_job_footer(stadt):
    texte = [
        f"{stadt} bietet ein vielfältiges Spektrum an Zahnarztpraxen – von kleinen Einzelpraxen bis zu modernen Gemeinschaftspraxen. Profitieren Sie von attraktiven Arbeitgebern und flexiblen Arbeitsmodellen.",
        f"Die Dentalbranche in {stadt} wächst stetig. Nutzen Sie die Chance, Teil eines dynamischen Teams zu werden. Dentalax verbindet Sie mit den besten Arbeitgebern der Region.",
        f"Egal ob Berufseinsteiger oder erfahrene Fachkraft – in {stadt} finden Sie passende Stellen. Unsere Plattform zeigt Ihnen Premium-Arbeitgeber und externe Stellenangebote auf einen Blick."
    ]
    return texte[get_city_index(stadt, len(texte))]

# Kategorie-Mapping für SEO-Seiten
KATEGORIE_MAPPING = {
    'zfa': {'name': 'ZFA', 'full': 'Zahnmedizinische Fachangestellte', 'plural': 'ZFAs'},
    'zmf': {'name': 'ZMF', 'full': 'Zahnmedizinische Fachassistentin', 'plural': 'ZMFs'},
    'zmv': {'name': 'ZMV', 'full': 'Zahnmedizinische Verwaltungsassistentin', 'plural': 'ZMVs'},
    'zmp': {'name': 'ZMP', 'full': 'Zahnmedizinische Prophylaxeassistentin', 'plural': 'ZMPs'},
    'dh': {'name': 'Dentalhygieniker', 'full': 'Dentalhygieniker/in', 'plural': 'Dentalhygieniker'},
    'prophylaxe': {'name': 'Prophylaxe-Assistent', 'full': 'Prophylaxe-Assistent/in', 'plural': 'Prophylaxe-Assistenten'},
    'zahnarzt': {'name': 'Zahnarzt', 'full': 'Zahnarzt/Zahnärztin', 'plural': 'Zahnärzte'},
    'kfo': {'name': 'Kieferorthopäde', 'full': 'Kieferorthopäde/in', 'plural': 'Kieferorthopäden'},
    'oralchirurg': {'name': 'Oralchirurg', 'full': 'Oralchirurg/in / MKG', 'plural': 'Oralchirurgen'},
    'implantologe': {'name': 'Implantologe', 'full': 'Implantologe/in', 'plural': 'Implantologen'},
    'endodontologe': {'name': 'Endodontologe', 'full': 'Endodontologe/in', 'plural': 'Endodontologen'},
    'parodontologe': {'name': 'Parodontologe', 'full': 'Parodontologe/in', 'plural': 'Parodontologen'},
    'zahntechniker': {'name': 'Zahntechniker', 'full': 'Zahntechniker/in', 'plural': 'Zahntechniker'},
    'praxismanager': {'name': 'Praxismanager', 'full': 'Praxismanager/in', 'plural': 'Praxismanager'},
    'rezeption': {'name': 'Rezeption', 'full': 'Rezeption / Empfang', 'plural': 'Rezeptionisten'},
    'abrechnung': {'name': 'Abrechnung', 'full': 'Abrechnung', 'plural': 'Abrechnungskräfte'},
    'verwaltung': {'name': 'Verwaltung', 'full': 'Verwaltung', 'plural': 'Verwaltungsmitarbeiter'},
    'azubi': {'name': 'Auszubildende', 'full': 'Auszubildende/r', 'plural': 'Auszubildende'},
}

def seo_kategorie_h1(kategorie_slug, stadt=None):
    """H1-Varianten für Kategorie- und Kategorie+Stadt-Seiten"""
    kat = KATEGORIE_MAPPING.get(kategorie_slug, {})
    name = kat.get('name', kategorie_slug.upper())
    full = kat.get('full', name)
    
    if stadt:
        texte = [
            f"{name} Jobs in {stadt}",
            f"Stellenangebote {full} {stadt}",
            f"{name} Stellenangebote in {stadt}"
        ]
        return texte[get_city_index(f"{kategorie_slug}{stadt}", len(texte))]
    else:
        texte = [
            f"{name} Jobs deutschlandweit",
            f"Stellenangebote als {full}",
            f"{name} Stellenangebote finden"
        ]
        return texte[get_city_index(kategorie_slug, len(texte))]

def seo_kategorie_intro(kategorie_slug, stadt=None):
    """Intro-Varianten für Kategorie-Seiten"""
    kat = KATEGORIE_MAPPING.get(kategorie_slug, {})
    name = kat.get('name', kategorie_slug.upper())
    full = kat.get('full', name)
    plural = kat.get('plural', name)
    
    if stadt:
        texte = [
            f"Aktuelle {name} Stellenangebote in {stadt}. Finden Sie Ihren Traumjob als {full} bei renommierten Zahnarztpraxen in der Region.",
            f"Sie suchen einen Job als {full} in {stadt}? Entdecken Sie attraktive Stellenangebote und starten Sie Ihre Karriere.",
            f"Top-Arbeitgeber in {stadt} suchen qualifizierte {plural}. Jetzt bewerben und Teil eines professionellen Teams werden."
        ]
        return texte[get_city_index(f"{kategorie_slug}{stadt}", len(texte))]
    else:
        texte = [
            f"Finden Sie attraktive {name} Stellenangebote in ganz Deutschland. Dentalax zeigt Ihnen die besten Jobs als {full}.",
            f"Karriere als {full} starten! Entdecken Sie aktuelle Stellenangebote von Top-Arbeitgebern in der Zahnmedizin.",
            f"Deutschlandweite {name} Jobs – von der Einzelpraxis bis zum MVZ. Ihre nächste Karrierechance wartet."
        ]
        return texte[get_city_index(kategorie_slug, len(texte))]

def seo_kategorie_footer(kategorie_slug, stadt=None):
    """Footer-Varianten für Kategorie-Seiten"""
    kat = KATEGORIE_MAPPING.get(kategorie_slug, {})
    name = kat.get('name', kategorie_slug.upper())
    full = kat.get('full', name)
    plural = kat.get('plural', name)
    
    if stadt:
        texte = [
            f"{stadt} bietet vielfältige Karrieremöglichkeiten für {plural}. Von modernen Einzelpraxen bis zu großen Gemeinschaftspraxen – finden Sie den Arbeitgeber, der zu Ihnen passt.",
            f"Der Arbeitsmarkt für {plural} in {stadt} ist dynamisch. Nutzen Sie Ihre Chance und bewerben Sie sich bei attraktiven Arbeitgebern in der Region.",
            f"Als {full} in {stadt} profitieren Sie von spannenden Aufgaben und Entwicklungsmöglichkeiten. Dentalax zeigt Ihnen die besten Angebote."
        ]
        return texte[get_city_index(f"{kategorie_slug}{stadt}", len(texte))]
    else:
        texte = [
            f"Der Beruf {full} bietet vielfältige Karrieremöglichkeiten in der Zahnmedizin. Von Prophylaxe bis Assistenz – entdecken Sie Ihren Traumjob.",
            f"Deutschlandweit suchen Zahnarztpraxen qualifizierte {plural}. Profitieren Sie von attraktiven Konditionen und modernen Arbeitsplätzen.",
            f"Ob Vollzeit, Teilzeit oder Ausbildung – als {full} finden Sie bei Dentalax passende Stellenangebote für jeden Karriereschritt."
        ]
        return texte[get_city_index(kategorie_slug, len(texte))]

# Flask app wird aus main.py importiert

# Routen
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/leistungen')
def services():
    return render_template('index.html', active_page='leistungen')

@app.route('/team')
def team():
    return render_template('index.html', active_page='team')

@app.route('/kontakt', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Hier könnten die Formulardaten verarbeitet werden, z.B.:
        # name = request.form.get('name')
        # email = request.form.get('email')
        # telefon = request.form.get('telefon')
        # betreff = request.form.get('betreff')
        # nachricht = request.form.get('nachricht')
        
        # In einer echten Anwendung würden die Daten in einer Datenbank gespeichert
        # oder eine E-Mail-Benachrichtigung gesendet
        
        # Hier simulieren wir eine erfolgreiche Verarbeitung
        flash('Vielen Dank für Ihre Nachricht! Wir werden uns schnellstmöglich bei Ihnen melden.', 'success')
        return redirect(url_for('contact'))
        
    return render_template('kontakt.html', active_page='kontakt')

@app.route('/termine')
def appointments():
    return render_template('index.html', active_page='termine')

@app.route('/zahnarzt-<stadt_slug>')
def zahnarzt_stadt(stadt_slug):
    """SEO-optimierte Stadtseite für Zahnärzte"""
    from models import Praxis, StadtSEO, Bewertung
    from sqlalchemy import func as sql_func
    
    stadt_name = stadt_slug.replace('-', ' ').title()
    umlaute = {'ue': 'ü', 'ae': 'ä', 'oe': 'ö'}
    for key, val in umlaute.items():
        stadt_name = stadt_name.replace(key.title(), val.upper()).replace(key, val)
    
    seite = int(request.args.get('seite', 1))
    umkreis = float(request.args.get('umkreis', 25))
    eintraege_pro_seite = 20
    
    lat, lng = get_coordinates_from_address(stadt_name)
    
    if not lat or not lng:
        flash('Der Ort konnte nicht gefunden werden.', 'warning')
        return redirect(url_for('index'))
    
    alle_praxen = lade_praxen("zahnaerzte.csv")
    
    bewertung_stats = db.session.query(
        Bewertung.praxis_id,
        sql_func.avg(Bewertung.sterne).label('avg_sterne'),
        sql_func.count(Bewertung.id).label('anzahl')
    ).filter(Bewertung.bestaetigt == True).group_by(Bewertung.praxis_id).all()
    bewertung_map = {b.praxis_id: {'avg': round(float(b.avg_sterne), 1), 'anzahl': int(b.anzahl)} for b in bewertung_stats}
    
    from models import Oeffnungszeit as OZ_Stadt
    import pytz
    berlin_tz_stadt = pytz.timezone('Europe/Berlin')
    jetzt_stadt = datetime.now(berlin_tz_stadt)
    wochentag_idx_stadt = jetzt_stadt.weekday()
    tage_stadt = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    aktueller_tag_stadt = tage_stadt[wochentag_idx_stadt]
    aktuelle_zeit_stadt = jetzt_stadt.time()
    
    oz_alle_stadt = OZ_Stadt.query.all()
    oz_by_praxis_stadt = {}
    for oz in oz_alle_stadt:
        if oz.praxis_id not in oz_by_praxis_stadt:
            oz_by_praxis_stadt[oz.praxis_id] = {}
        oz_by_praxis_stadt[oz.praxis_id][oz.tag] = oz
    
    db_praxen = Praxis.query.all()
    for praxis in db_praxen:
        if praxis.latitude and praxis.longitude:
            bew = bewertung_map.get(praxis.id, {'avg': 0, 'anzahl': 0})
            
            oeffnungsstatus = None
            if praxis.ist_verifiziert and praxis.id in oz_by_praxis_stadt:
                oz_dict = oz_by_praxis_stadt[praxis.id]
                if aktueller_tag_stadt in oz_dict:
                    oz_heute = oz_dict[aktueller_tag_stadt]
                    if not oz_heute.geschlossen and oz_heute.von and oz_heute.bis:
                        if oz_heute.von <= aktuelle_zeit_stadt <= oz_heute.bis:
                            oeffnungsstatus = 'geoeffnet'
                        else:
                            oeffnungsstatus = 'geschlossen'
                    else:
                        oeffnungsstatus = 'geschlossen'
                else:
                    oeffnungsstatus = 'geschlossen'
            
            alle_praxen.append({
                'id': praxis.id,
                'name': praxis.name,
                'email': praxis.email or '',
                'telefon': praxis.telefon or '',
                'webseite': praxis.webseite or '',
                'plz': praxis.plz or '',
                'stadt': praxis.stadt or '',
                'straße': praxis.strasse or '',
                'lat': float(praxis.latitude),
                'lng': float(praxis.longitude),
                'slug': praxis.slug,
                'aus_datenbank': True,
                'paket': praxis.paket,
                'landingpage_aktiv': praxis.landingpage_aktiv,
                'beansprucht': 'ja' if praxis.ist_verifiziert else 'nein',
                'bewertung_avg': bew['avg'],
                'bewertung_anzahl': bew['anzahl'],
                'google_rating': praxis.google_rating,
                'google_review_count': praxis.google_review_count or 0,
                'oeffnungsstatus': oeffnungsstatus
            })
    
    gefilterte_praxen = []
    for praxis in alle_praxen:
        distanz = entfernung_km(lat, lng, praxis['lat'], praxis['lng'])
        if distanz <= umkreis:
            praxis['entfernung'] = distanz
            gefilterte_praxen.append(praxis)
    
    import hashlib
    heute = datetime.now().strftime('%Y-%m-%d')
    hash_input = f"{heute}-{stadt_slug}".encode('utf-8')
    rotation_seed = int(hashlib.sha256(hash_input).hexdigest(), 16) % (2**32)
    rng = Random(rotation_seed)
    
    premium_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() in ('premium', 'premiumplus')]
    standard_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() not in ('premium', 'premiumplus')]
    
    rng.shuffle(premium_praxen)
    standard_praxen.sort(key=lambda p: p['entfernung'])
    gefilterte_praxen = premium_praxen + standard_praxen
    
    start = (seite - 1) * eintraege_pro_seite
    end = start + eintraege_pro_seite
    ergebnisse = gefilterte_praxen[start:end]
    gesamt_seiten = math.ceil(len(gefilterte_praxen) / eintraege_pro_seite)
    
    stadt_seo = StadtSEO.query.filter_by(stadt_slug=stadt_slug).first()
    
    import json as json_lib
    
    # SEO-Werte aus der Datenbank oder Fallback
    faq_list = []
    faq_schema_json = None
    meta_title = f"Zahnarzt {stadt_name} | Zahnärzte finden - Dentalax"
    meta_description = f"Finden Sie Ihren Zahnarzt in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und Öffnungszeiten."
    
    if stadt_seo:
        seo_h1 = stadt_seo.h1_titel or f"Zahnarzt in {stadt_name} finden"
        seo_intro = stadt_seo.teaser_text or f"Finden Sie den passenden Zahnarzt in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und vereinbaren Sie Ihren Termin."
        meta_title = stadt_seo.meta_title or meta_title
        meta_description = stadt_seo.meta_description or meta_description
        if stadt_seo.faq_json:
            try:
                faq_list = json_lib.loads(stadt_seo.faq_json)
                if faq_list:
                    faq_schema = {
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        "mainEntity": [
                            {
                                "@type": "Question",
                                "name": faq.get('frage', ''),
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": faq.get('antwort', '')
                                }
                            } for faq in faq_list
                        ]
                    }
                    faq_schema_json = json_lib.dumps(faq_schema, ensure_ascii=False)
            except:
                faq_list = []
    else:
        seo_h1 = f"Zahnarzt in {stadt_name} finden"
        seo_intro = f"Finden Sie den passenden Zahnarzt in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und vereinbaren Sie Ihren Termin."
    
    # ItemList Schema.org vorbereiten
    item_list_schema = None
    if ergebnisse:
        item_list_items = []
        for idx, praxis in enumerate(ergebnisse[:10], 1):
            item = {
                "@type": "ListItem",
                "position": idx,
                "item": {
                    "@type": "Dentist",
                    "name": praxis.get('name', ''),
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": praxis.get('straße', praxis.get('strasse', '')),
                        "postalCode": praxis.get('plz', ''),
                        "addressLocality": praxis.get('stadt', ''),
                        "addressCountry": "DE"
                    }
                }
            }
            if praxis.get('telefon'):
                item["item"]["telephone"] = praxis.get('telefon')
            if praxis.get('webseite'):
                item["item"]["url"] = praxis.get('webseite')
            item_list_items.append(item)
        
        item_list_schema = json_lib.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Zahnärzte in {stadt_name}",
            "description": f"Liste der Zahnarztpraxen in {stadt_name} und Umgebung",
            "numberOfItems": len(ergebnisse),
            "itemListElement": item_list_items
        }, ensure_ascii=False)
    
    # Interne Verlinkung: Verwandte Städte finden
    verwandte_staedte = []
    hauptstadt = None
    vororte = []
    
    if '-' in stadt_slug:
        # Dies ist ein Vorort - finde die Hauptstadt
        hauptstadt_slug = stadt_slug.split('-')[0]
        hauptstadt_seo = StadtSEO.query.filter_by(stadt_slug=hauptstadt_slug).first()
        if hauptstadt_seo:
            hauptstadt = {
                'name': hauptstadt_seo.stadt_name,
                'slug': hauptstadt_seo.stadt_slug
            }
    else:
        # Dies ist eine Hauptstadt - finde Vororte
        vororte_query = StadtSEO.query.filter(
            StadtSEO.stadt_slug.like(f"{stadt_slug}-%")
        ).order_by(StadtSEO.stadt_name).limit(10).all()
        vororte = [{'name': v.stadt_name, 'slug': v.stadt_slug} for v in vororte_query]
    
    canonical_url = url_for('zahnarzt_stadt', stadt_slug=stadt_slug, _external=True)
    
    return render_template(
        'suche.html',
        ort=stadt_name,
        stadt_slug=stadt_slug,
        behandlung=None,
        umkreis=umkreis,
        ergebnisse=ergebnisse,
        seite=seite,
        gesamt_seiten=gesamt_seiten,
        selected_leistungen=[],
        max=max,
        min=min,
        stadt_seo=stadt_seo,
        is_seo_page=True,
        seo_route=True,
        seo_h1=seo_h1,
        seo_intro=seo_intro,
        faq_list=faq_list,
        faq_schema_json=faq_schema_json,
        meta_title=meta_title,
        meta_description=meta_description,
        item_list_schema=item_list_schema,
        hauptstadt=hauptstadt,
        vororte=vororte,
        canonical_url=canonical_url
    )


@app.route('/suche')
def suche():
    from models import Praxis
    
    ort = request.args.get('ort', '').strip()
    behandlung = request.args.get('behandlung')
    umkreis = float(request.args.get('umkreis', 25))
    seite = int(request.args.get('seite', 1))
    eintraege_pro_seite = 20
    
    # Leistungs-Filter aus Checkboxen
    selected_leistungen = request.args.getlist('leistung')
    
    # Geolocation-Koordinaten prüfen
    has_geolocation = False
    lat = None
    lng = None
    
    if request.args.get('lat') and request.args.get('lng'):
        try:
            lat = float(request.args.get('lat'))
            lng = float(request.args.get('lng'))
            has_geolocation = True
            print("Geolocation verwendet:", lat, lng)
        except (ValueError, TypeError):
            has_geolocation = False

    # Wenn weder Ort noch Geolocation angegeben, zur Startseite umleiten
    if not ort and not has_geolocation:
        return redirect(url_for('index'))

    # Wenn kein Geolocation, Ort geocodieren
    if not has_geolocation:
        lat, lng = get_coordinates_from_address(ort)
        print("Geocodierte Koordinaten:", lat, lng)
    
    # Fallback wenn Geokodierung fehlschlägt
    if not lat or not lng:
        flash('Der Ort konnte nicht gefunden werden. Bitte überprüfen Sie Ihre Eingabe.', 'warning')
        return redirect(url_for('index'))

    # CSV-Praxen laden
    alle_praxen = lade_praxen("zahnaerzte.csv")
    
    # Datenbank-Praxen hinzufügen (alle, nicht nur mit aktiver Landingpage)
    from models import Bewertung, Oeffnungszeit
    from sqlalchemy import func as sql_func
    db_praxen = Praxis.query.all()
    
    bewertung_stats = db.session.query(
        Bewertung.praxis_id,
        sql_func.avg(Bewertung.sterne).label('avg_sterne'),
        sql_func.count(Bewertung.id).label('anzahl')
    ).filter(Bewertung.bestaetigt == True).group_by(Bewertung.praxis_id).all()
    bewertung_map = {b.praxis_id: {'avg': round(float(b.avg_sterne), 1), 'anzahl': int(b.anzahl)} for b in bewertung_stats}
    
    import pytz
    berlin_tz = pytz.timezone('Europe/Berlin')
    jetzt_berlin = datetime.now(berlin_tz)
    wochentag_index = jetzt_berlin.weekday()
    tage_reihenfolge_suche = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    aktueller_tag_suche = tage_reihenfolge_suche[wochentag_index]
    aktuelle_zeit_suche = jetzt_berlin.time()
    
    oz_alle = Oeffnungszeit.query.all()
    oz_by_praxis = {}
    for oz in oz_alle:
        if oz.praxis_id not in oz_by_praxis:
            oz_by_praxis[oz.praxis_id] = {}
        oz_by_praxis[oz.praxis_id][oz.tag] = oz
    
    for praxis in db_praxen:
        if praxis.latitude and praxis.longitude:
            bew = bewertung_map.get(praxis.id, {'avg': 0, 'anzahl': 0})
            
            oeffnungsstatus = None
            if praxis.ist_verifiziert and praxis.id in oz_by_praxis:
                oz_dict = oz_by_praxis[praxis.id]
                if aktueller_tag_suche in oz_dict:
                    oz_heute = oz_dict[aktueller_tag_suche]
                    if not oz_heute.geschlossen and oz_heute.von and oz_heute.bis:
                        if oz_heute.von <= aktuelle_zeit_suche <= oz_heute.bis:
                            oeffnungsstatus = 'geoeffnet'
                        else:
                            oeffnungsstatus = 'geschlossen'
                    else:
                        oeffnungsstatus = 'geschlossen'
                else:
                    oeffnungsstatus = 'geschlossen'
            
            alle_praxen.append({
                'id': praxis.id,
                'name': praxis.name,
                'email': praxis.email or '',
                'telefon': praxis.telefon or '',
                'webseite': praxis.webseite or '',
                'plz': praxis.plz or '',
                'stadt': praxis.stadt or '',
                'straße': praxis.strasse or '',
                'lat': float(praxis.latitude),
                'lng': float(praxis.longitude),
                'slug': praxis.slug,
                'aus_datenbank': True,
                'paket': praxis.paket,
                'landingpage_aktiv': praxis.landingpage_aktiv,
                'beansprucht': 'ja' if praxis.ist_verifiziert else 'nein',
                'bewertung_avg': bew['avg'],
                'bewertung_anzahl': bew['anzahl'],
                'google_rating': praxis.google_rating,
                'google_review_count': praxis.google_review_count or 0,
                'oeffnungsstatus': oeffnungsstatus
            })

    gefilterte_praxen = []
    for praxis in alle_praxen:
        distanz = entfernung_km(lat, lng, praxis['lat'], praxis['lng'])
        if distanz <= umkreis:
            praxis['entfernung'] = distanz
            gefilterte_praxen.append(praxis)

    # Trennung in Premium und Standard-Praxen (case-insensitive)
    premium_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() in ('premium', 'premiumplus')]
    standard_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() not in ('premium', 'premiumplus')]
    
    # Tagesbasierte Rotation für Premium-Praxen
    # Seed basiert auf Datum + Ort für konsistente Ergebnisse am selben Tag
    import hashlib
    heute = datetime.now().strftime('%Y-%m-%d')
    hash_input = f"{heute}-{ort.lower()}".encode('utf-8')
    rotation_seed = int(hashlib.sha256(hash_input).hexdigest(), 16) % (2**32)
    rng = Random(rotation_seed)
    rng.shuffle(premium_praxen)
    
    # Standard-Praxen nach Entfernung sortieren
    standard_praxen.sort(key=lambda p: p['entfernung'])
    
    # Kombinieren: Premium zuerst, dann Standard
    gefilterte_praxen = premium_praxen + standard_praxen

    start = (seite - 1) * eintraege_pro_seite
    end = start + eintraege_pro_seite
    ergebnisse = gefilterte_praxen[start:end]
    gesamt_seiten = math.ceil(len(gefilterte_praxen) / eintraege_pro_seite)

    canonical_url = None
    meta_robots = 'noindex, follow'
    
    if ort:
        ort_slug = ort.lower().replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss').replace(' ', '-')
        canonical_url = url_for('zahnarzt_stadt', stadt_slug=ort_slug, _external=True)
    
    return render_template(
        'suche.html',
        ort=ort or "deinem Standort",
        behandlung=behandlung,
        umkreis=umkreis,
        ergebnisse=ergebnisse,
        seite=seite,
        gesamt_seiten=gesamt_seiten,
        selected_leistungen=selected_leistungen,
        max=max,
        min=min,
        canonical_url=canonical_url,
        meta_robots=meta_robots
    )

def lade_praxen(csv_datei):
    """Lädt Praxen aus CSV. csv_id ist immer der Zeilen-Index aus der Originaldatei."""
    praxen = []
    with open(csv_datei, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for original_idx, row in enumerate(reader):
            try:
                raw_lat = row['lat'].replace(',', '').replace('.', '')
                raw_lng = row['lng'].replace(',', '').replace('.', '')
                lat = int(raw_lat) / 1e7
                lng = int(raw_lng) / 1e7

                if 45 <= lat <= 55 and 5 <= lng <= 15:
                    praxen.append({
                        'csv_id': f"csv_{original_idx}",
                        'csv_original_idx': original_idx,
                        'name': row['name'],
                        'email': row['email'],
                        'telefon': row['telefon'],
                        'webseite': row['webseite'],
                        'plz': row['plz'],
                        'stadt': row['stadt'],
                        'straße': row['straße'],
                        'lat': lat,
                        'lng': lng,
                        'paket': '',
                        'beansprucht': 'nein',
                        'aus_csv': True,
                        'google_rating': None,
                        'google_review_count': 0,
                        'bewertung_avg': 0,
                        'bewertung_anzahl': 0
                    })
            except Exception as e:
                print(f"⚠️ Fehler in Zeile: {row}\nGrund: {e}")
                continue
    print(f"{len(praxen)} Praxen geladen")
    return praxen

def entfernung_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 1)

def berechne_preislogik(paket, zahlweise):
    if paket.lower() == "premium":
        monatspreis = 59
    elif paket.lower() == "premiumplus":
        monatspreis = 89
    else:
        monatspreis = 0

    if zahlweise == "jährlich":
        dauer = 12
        rabatt = 0.10
    else:
        dauer = 1
        rabatt = 0

    gesamt_netto = monatspreis * dauer * (1 - rabatt)
    mwst = round(gesamt_netto * 0.19, 2)
    gesamt_brutto = round(gesamt_netto + mwst, 2)

    return {
        "netto": round(gesamt_netto, 2),
        "mwst": mwst,
        "brutto": gesamt_brutto,
        "dauer": dauer,
        "zyklus": zahlweise
    }

@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.route("/register", methods=["GET", "POST"])
def register():
    # URL-Parameter als Fallback für Session (wegen Iframe/Proxy-Umgebung)
    paket = session.get("paket") or request.args.get("paket")
    zahlweise = session.get("zahlweise") or request.args.get("zahlweise", "monatlich")
    
    # URL-Parameter in Session speichern für spätere Verwendung
    if paket and not session.get("paket"):
        session["paket"] = paket
        session["zahlweise"] = zahlweise

    # Wenn kein Paket gewählt wurde, zur Paketauswahl weiterleiten
    if not paket or paket == "Unbekannt":
        flash("Bitte wählen Sie zuerst ein Paket für Ihre Praxis.", "info")
        return redirect("/paketwahl")

    # GET-Methode: Prüfen auf URL-Parameter für Praxisinformationen
    if request.method == "GET":
        strasse = request.args.get("strasse", "")
        plz = request.args.get("plz", "")
        stadt = request.args.get("stadt", "")
        
        # Prüfen, ob die Praxis bereits beansprucht wurde
        if strasse and plz:
            datei = "zahnaerzte.csv"
            if os.path.isfile(datei):
                with open(datei, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row["straße"].strip().lower() == strasse.strip().lower() and
                            row["plz"].strip() == plz.strip()):
                            if row.get("beansprucht", "").strip().lower() == "ja":
                                flash("Hinweis: Diese Praxis wurde bereits beansprucht. Ihre Anfrage wird nach der Registrierung von unserem Team geprüft.", "warning")
                            break

    if request.method == "POST":
        vorname = request.form["vorname"]
        nachname = request.form["nachname"]
        praxisname = request.form["praxisname"]
        strasse = request.form["strasse"]
        plz = request.form["plz"]
        stadt = request.form["stadt"]
        telefon = request.form["telefon"]
        webseite = request.form["webseite"].strip()
        email = request.form["email"]
        passwort = request.form["passwort"]
        passwort_bestaetigen = request.form["passwort_bestaetigen"]
        datenschutz = request.form.get("datenschutz", "nein")
        marketing = request.form.get("marketing", "nein")
        
        # Passwörter prüfen
        if passwort != passwort_bestaetigen:
            flash("Die Passwörter stimmen nicht überein.", "danger")
            return render_template("register.html", paket=paket)

        # Webseite bereinigen
        if webseite and not webseite.startswith(("http://", "https://")):
            webseite = "https://" + webseite

        # Speichere für Checkout alles in der Session
        session["vorname"] = vorname
        session["nachname"] = nachname
        session["praxisname"] = praxisname
        session["strasse"] = strasse
        session["plz"] = plz
        session["stadt"] = stadt
        session["telefon"] = telefon
        session["webseite"] = webseite
        session["email"] = email
        session["marketing"] = marketing
        
        from werkzeug.security import generate_password_hash
        session["passwort_hash"] = generate_password_hash(passwort)

        # Duplikatprüfung (CSV + Datenbank) mit Fuzzy-Matching
        import re as re_mod
        
        def normalize_strasse(s):
            """Straßenname ohne Hausnummer extrahieren und normalisieren"""
            s = s.strip().lower()
            s = re_mod.sub(r'\s*\d+[\s\-/]*\d*\s*[a-zA-Z]?\s*$', '', s)
            s = re_mod.sub(r'\s+', ' ', s).strip()
            s = s.replace('str.', 'straße').replace('strasse', 'straße')
            return s
        
        def normalize_stadt(s):
            """Stadt normalisieren: Stadtteil-Zusatz nach Bindestrich entfernen"""
            s = s.strip().lower()
            return s
        
        def staedte_match(stadt1, stadt2):
            """Prüft ob zwei Städte übereinstimmen (mit/ohne Stadtteil)"""
            s1 = stadt1.strip().lower()
            s2 = stadt2.strip().lower()
            if s1 == s2:
                return True
            base1 = s1.split('-')[0].strip()
            base2 = s2.split('-')[0].strip()
            if base1 == s2 or base2 == s1:
                return True
            if base1 == base2:
                return True
            return False
        
        def extract_domain(url):
            """Extrahiert die Domain aus einer URL (ohne Protokoll/www)"""
            if not url:
                return ""
            url = url.strip().lower()
            url = re_mod.sub(r'^https?://', '', url)
            url = re_mod.sub(r'^www\.', '', url)
            url = url.split('/')[0].strip()
            return url
        
        csv_datei = "zahnaerzte.csv"
        duplikat_gefunden = False
        beansprucht_status = "nein"
        gefundener_name = ""
        gefundene_strasse = ""
        gefundene_plz = ""
        gefundene_stadt = ""
        
        eingabe_strasse_norm = normalize_strasse(strasse)
        eingabe_plz = plz.strip()

        if os.path.isfile(csv_datei):
            with open(csv_datei, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_plz = row["plz"].strip()
                    csv_strasse_norm = normalize_strasse(row["straße"])
                    
                    if (
                        csv_plz == eingabe_plz and
                        csv_strasse_norm == eingabe_strasse_norm and
                        staedte_match(row["stadt"], stadt)
                    ):
                        duplikat_gefunden = True
                        beansprucht_status = row.get("beansprucht", "").strip().lower()
                        gefundener_name = row.get("name", "").strip()
                        gefundene_strasse = row["straße"].strip()
                        gefundene_plz = csv_plz
                        gefundene_stadt = row["stadt"].strip()
                        break

        if not duplikat_gefunden:
            from models import Praxis
            alle_praxen = Praxis.query.filter(Praxis.plz == eingabe_plz).all()
            for p in alle_praxen:
                if (
                    normalize_strasse(p.strasse or '') == eingabe_strasse_norm and
                    staedte_match(p.stadt or '', stadt)
                ):
                    duplikat_gefunden = True
                    beansprucht_status = "ja"
                    gefundener_name = p.name or ""
                    gefundene_strasse = p.strasse or ""
                    gefundene_plz = p.plz or ""
                    gefundene_stadt = p.stadt or ""
                    break

        if not duplikat_gefunden and webseite:
            eingabe_domain = extract_domain(webseite)
            if eingabe_domain:
                if os.path.isfile(csv_datei):
                    with open(csv_datei, newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            csv_domain = extract_domain(row.get("webseite", ""))
                            if csv_domain and csv_domain == eingabe_domain:
                                duplikat_gefunden = True
                                beansprucht_status = row.get("beansprucht", "").strip().lower()
                                gefundener_name = row.get("name", "").strip()
                                gefundene_strasse = row["straße"].strip()
                                gefundene_plz = row["plz"].strip()
                                gefundene_stadt = row["stadt"].strip()
                                break

                if not duplikat_gefunden:
                    from models import Praxis
                    alle_praxen_domain = Praxis.query.filter(Praxis.webseite.isnot(None), Praxis.webseite != '').all()
                    for p in alle_praxen_domain:
                        if extract_domain(p.webseite or '') == eingabe_domain:
                            duplikat_gefunden = True
                            beansprucht_status = "ja"
                            gefundener_name = p.name or ""
                            gefundene_strasse = p.strasse or ""
                            gefundene_plz = p.plz or ""
                            gefundene_stadt = p.stadt or ""
                            break

        if duplikat_gefunden:
            return render_template(
                "register_exists.html",
                praxisname=praxisname,
                strasse=strasse,
                plz=plz,
                stadt=stadt,
                beansprucht=beansprucht_status,
                gefundener_name=gefundener_name,
                gefundene_strasse=gefundene_strasse,
                gefundene_plz=gefundene_plz,
                gefundene_stadt=gefundene_stadt
            )
        else:
            adresse = f"{strasse}, {plz} {stadt}"
            lat, lng = get_coordinates_from_address(adresse)
            print("📍 Neue Koordinaten:", lat, lng)
            
            # Passwort hashen
            from werkzeug.security import generate_password_hash
            passwort_hash = generate_password_hash(passwort)
            
            # Bestätigungstoken erstellen
            import secrets
            from datetime import timedelta
            
            token = secrets.token_urlsafe(32)
            token_gueltig_bis = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            registriert_am = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            neue_datei = "neue_praxen.csv"
            existiert = os.path.isfile(neue_datei)

            with open(neue_datei, "a", newline='', encoding="utf-8") as f:
                fieldnames = [
                    "vorname", "nachname", "name", "email", "telefon", "webseite",
                    "plz", "stadt", "straße", "lat", "lng", "beansprucht", "paket", 
                    "zahlweise", "registriert_am", "passwort_hash", "bestätigt", 
                    "bestätigungs_token", "token_gültig_bis", "marketing"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                if os.stat(neue_datei).st_size == 0:
                    writer.writeheader()

                writer.writerow({
                    "vorname": vorname,
                    "nachname": nachname,
                    "name": praxisname,
                    "email": email,
                    "telefon": telefon,
                    "webseite": webseite,
                    "plz": plz,
                    "stadt": stadt,
                    "straße": strasse,
                    "lat": lat,
                    "lng": lng,
                    "beansprucht": "ja",
                    "paket": paket,
                    "zahlweise": zahlweise,
                    "registriert_am": registriert_am,
                    "passwort_hash": passwort_hash,
                    "bestätigt": "nein",
                    "bestätigungs_token": token,
                    "token_gültig_bis": token_gueltig_bis,
                    "marketing": marketing
                })
                
            bestaetigungs_url = url_for('zahnarzt_bestaetigen', token=token, email=email, _external=True)

            from services.email_service import send_zahnarzt_bestaetigung
            send_zahnarzt_bestaetigung(email, praxisname, bestaetigungs_url)

            session["bestaetigungs_url"] = bestaetigungs_url

            # Je nach gewähltem Paket unterschiedliche Weiterleitung
            if paket.lower() in ["premium", "premiumplus"]:
                # Bei kostenpflichtigen Paketen zur Zahlungsseite weiterleiten
                flash("Vielen Dank für Ihre Registrierung! Bitte schließen Sie den Zahlungsvorgang ab, um die Praxisseite einzurichten.", "success")
                return redirect("/checkout")
            else:
                # Bei Basis-Paket zur Bestätigungsseite weiterleiten
                flash("Vielen Dank für Ihre Registrierung! Bitte überprüfen Sie Ihren E-Mail-Eingang, um Ihre Registrierung zu bestätigen.", "success")
                return redirect("/registrierung-erfolgreich")

    return render_template("register.html", paket=paket)


@app.route("/claim", methods=["POST"])
def claim():
    from flask_login import login_user
    import secrets
    from datetime import timedelta
    
    vorname = session.get("vorname", "")
    nachname = session.get("nachname", "")
    praxisname = session.get("praxisname", "")
    strasse = session.get("strasse", "")
    plz = session.get("plz", "")
    stadt = session.get("stadt", "")
    email = session.get("email", "")
    telefon = session.get("telefon", "")
    webseite = session.get("webseite", "")
    marketing = session.get("marketing", "nein")
    passwort_hash = session.get("passwort_hash", "")
    
    if not email or not praxisname or not passwort_hash:
        flash("Sitzung abgelaufen. Bitte starten Sie die Registrierung erneut.", "danger")
        return redirect("/register")
    
    if Zahnarzt.query.filter_by(email=email).first():
        flash("Diese E-Mail-Adresse ist bereits registriert. Bitte melden Sie sich an.", "danger")
        return redirect("/zahnarzt-login")
    
    datei = "zahnaerzte.csv"
    bereits_beansprucht = False
    csv_lat = 0
    csv_lng = 0
    csv_telefon = ""
    csv_webseite = ""
    csv_fachgebiete = ""
    
    import re as re_mod
    def extract_domain(url):
        if not url:
            return ""
        url = url.strip().lower()
        url = re_mod.sub(r'^https?://', '', url)
        url = re_mod.sub(r'^www\.', '', url)
        url = url.split('/')[0].strip()
        return url
    
    eingabe_domain = extract_domain(webseite)
    
    if os.path.isfile(datei):
        with open(datei, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_strasse = row.get("straße", "").strip().lower()
                csv_plz = row.get("plz", "").strip()
                csv_stadt = row.get("stadt", "").strip().lower()
                adress_match = (
                    csv_strasse == strasse.strip().lower() and
                    csv_plz == plz.strip() and
                    csv_stadt == stadt.strip().lower()
                )
                domain_match = (
                    eingabe_domain and 
                    extract_domain(row.get("webseite", "")) == eingabe_domain
                )
                if adress_match or domain_match:
                    if row.get("beansprucht", "").strip().lower() == "ja":
                        bereits_beansprucht = True
                    csv_lat = row.get("lat", 0)
                    csv_lng = row.get("lng", 0)
                    csv_telefon = row.get("telefon", "")
                    csv_webseite = row.get("webseite", "")
                    csv_fachgebiete = row.get("fachgebiete", "")
                    break
    
    if bereits_beansprucht:
        neuer_claim = Claim(
            praxis_name=praxisname,
            strasse=strasse,
            plz=plz,
            email=email,
            status='pending',
            notizen=f"Vorname: {vorname}, Nachname: {nachname}, Stadt: {stadt}.",
            erstellt_am=datetime.now()
        )
        db.session.add(neuer_claim)
        db.session.commit()
        
        flash("Diese Praxis wurde bereits beansprucht. Ihre Anfrage wird von unserem Team geprüft. Sie erhalten eine E-Mail, sobald die Prüfung abgeschlossen ist.", "warning")
        return redirect("/")
    
    zahnarzt = Zahnarzt(
        email=email,
        vorname=vorname,
        nachname=nachname,
        password_hash=passwort_hash,
        is_active=True,
        marketing=(marketing == "on")
    )
    db.session.add(zahnarzt)
    db.session.flush()
    
    verwendete_telefon = telefon or csv_telefon
    verwendete_webseite = webseite or csv_webseite
    
    try:
        lat_val = float(csv_lat) if csv_lat else 0
        lng_val = float(csv_lng) if csv_lng else 0
    except (ValueError, TypeError):
        lat_val = lng_val = 0
    
    if lat_val == 0 and lng_val == 0:
        adresse = f"{strasse}, {plz} {stadt}"
        lat_val, lng_val = get_coordinates_from_address(adresse)
    
    praxis_slug = slugify(f"{praxisname}-{stadt}")
    slug_base = praxis_slug
    counter = 1
    while Praxis.query.filter_by(slug=praxis_slug).first():
        praxis_slug = f"{slug_base}-{counter}"
        counter += 1
    
    neue_praxis = Praxis(
        name=praxisname,
        slug=praxis_slug,
        strasse=strasse,
        plz=plz,
        stadt=stadt,
        telefon=verwendete_telefon,
        webseite=verwendete_webseite,
        email=email,
        latitude=lat_val,
        longitude=lng_val,
        zahnarzt_id=zahnarzt.id,
        ist_verifiziert=True,
        paket="Basis",
        landingpage_aktiv=False
    )
    db.session.add(neue_praxis)
    db.session.flush()
    
    zahnarzt.praxis_id = neue_praxis.id
    
    db.session.commit()
    
    eintraege = []
    if os.path.isfile(datei):
        with open(datei, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                adress_match = (
                    row.get("straße", "").strip().lower() == strasse.strip().lower() and
                    row.get("plz", "").strip() == plz.strip() and
                    row.get("stadt", "").strip().lower() == stadt.strip().lower()
                )
                domain_match = (
                    eingabe_domain and
                    extract_domain(row.get("webseite", "")) == eingabe_domain
                )
                if adress_match or domain_match:
                    row["beansprucht"] = "ja"
                    row["name"] = praxisname
                    row["email"] = email
                eintraege.append(row)
        
        if eintraege:
            with open(datei, "w", newline="", encoding="utf-8") as f:
                fieldnames = eintraege[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(eintraege)
    
    login_user(zahnarzt)
    session["angemeldet"] = True
    session["benutzer_typ"] = "zahnarzt"
    session["benutzer_email"] = email
    session["email"] = email
    session["benutzer_vorname"] = vorname
    session["benutzer_nachname"] = nachname
    session["praxisname"] = praxisname
    session["paket"] = "Basis"
    session["praxis_id"] = neue_praxis.id
    session["zahnarzt_id"] = zahnarzt.id
    
    token = secrets.token_urlsafe(32)
    bestaetigungs_url = url_for('zahnarzt_bestaetigen', token=token, email=email, _external=True)
    
    try:
        from services.email_service import send_zahnarzt_bestaetigung
        send_zahnarzt_bestaetigung(email, praxisname, bestaetigungs_url)
    except Exception as e:
        print(f"⚠️ Bestätigungs-E-Mail konnte nicht gesendet werden: {e}")
    
    print(f"✅ Praxis '{praxisname}' direkt übernommen von {email} (Zahnarzt-ID: {zahnarzt.id}, Praxis-ID: {neue_praxis.id})")
    
    flash(f"Praxis '{praxisname}' erfolgreich übernommen! Bitte wählen Sie jetzt Ihr Paket.", "success")
    return redirect("/paketwahl")

@app.route("/paket-bestaetigen", methods=["POST"])
def paket_bestaetigen():
    # Nur gültige Pakete erlauben (case-insensitive)
    gueltige_pakete = ["basis", "basic", "premium", "premiumplus"]
    gueltige_zahlweisen = ["monatlich", "jährlich"]
    
    paket_raw = request.form.get("paket", "Basis")
    zahlweise = request.form.get("zahlweise", "monatlich")
    
    # Normalize package name
    paket_lower = paket_raw.lower()
    if paket_lower == "basic":
        paket_lower = "basis"
    
    # Validierung: Nur bekannte Pakete und Zahlweisen akzeptieren
    if paket_lower not in gueltige_pakete:
        flash("Ungültiges Paket ausgewählt. Bitte wählen Sie ein gültiges Paket.", "danger")
        return redirect("/paketwahl")
    
    if zahlweise not in gueltige_zahlweisen:
        zahlweise = "monatlich"  # Fallback auf monatlich

    # Map to display names for UI
    paket_display_map = {"basis": "Basis", "premium": "Premium", "premiumplus": "PremiumPlus"}
    paket_display = paket_display_map.get(paket_lower, "Basis")

    # Speichere Paket in Session für den Registrierungs- und Checkout-Flow
    session["paket"] = paket_lower
    session["zahlweise"] = zahlweise
    
    # Logging für Audit-Trail
    print(f"✅ Paket gewählt: {paket_display} ({zahlweise}) - Weiterleitung zur Registrierung")
    
    # Paketauswahl in CSV protokollieren für Audit
    import csv
    from datetime import datetime
    dateiname = "paket_auswahl_log.csv"
    datei_existiert = os.path.isfile(dateiname)
    
    with open(dateiname, "a", newline="", encoding="utf-8") as f:
        fieldnames = ["zeitstempel", "paket", "zahlweise", "ip_adresse"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not datei_existiert:
            writer.writeheader()
        writer.writerow({
            "zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "paket": paket_lower,
            "zahlweise": zahlweise,
            "ip_adresse": request.remote_addr
        })

    praxis_id = session.get("praxis_id")
    if praxis_id:
        praxis = Praxis.query.get(praxis_id)
        if praxis:
            praxis.paket = paket_display
            if paket_lower in ["premium", "premiumplus"]:
                praxis.landingpage_aktiv = True
            db.session.commit()
            session["paket"] = paket_display

            if paket_lower in ["premium", "premiumplus"]:
                flash(f"Sie haben das {paket_display}-Paket gewählt. Weiter zur Zahlung.", "success")
                return redirect("/checkout")
            else:
                flash(f"Willkommen! Ihr kostenloses Basis-Paket ist aktiv. Sie können jederzeit upgraden.", "success")
                return redirect("/zahnarzt-dashboard")

    if paket_lower in ["premium", "premiumplus"]:
        flash(f"Sie haben das {paket_display}-Paket gewählt. Bitte vervollständigen Sie nun Ihre Registrierung.", "success")
    else:
        flash(f"Sie haben das kostenlose Basis-Paket gewählt. Bitte vervollständigen Sie Ihre Registrierung.", "success")

    return redirect(f"/register?paket={paket_lower}&zahlweise={zahlweise}")



# 🌐 Praxis übernehmen aus CSV - Erstellt Praxis in DB und startet Claim
@app.route("/praxis-uebernehmen-csv/<csv_id>", methods=["GET", "POST"])
def praxis_uebernehmen_csv(csv_id):
    """Seite für das Übernehmen einer CSV-Praxis - erstellt diese zuerst in der DB"""
    import secrets
    from datetime import timedelta
    
    # CSV-Index extrahieren
    if not csv_id.startswith("csv_"):
        flash("Ungültige Praxis-ID.", "danger")
        return redirect(url_for('index'))
    
    try:
        csv_index = int(csv_id.replace("csv_", ""))
    except ValueError:
        flash("Ungültige Praxis-ID.", "danger")
        return redirect(url_for('index'))
    
    # CSV-Praxen laden und die richtige finden (über original_idx)
    alle_praxen = lade_praxen("zahnaerzte.csv")
    
    # Finde die Praxis mit dem passenden csv_original_idx
    csv_praxis = None
    for p in alle_praxen:
        if p.get('csv_original_idx') == csv_index:
            csv_praxis = p
            break
    
    if not csv_praxis:
        flash("Praxis konnte nicht gefunden werden.", "danger")
        return redirect(url_for('index'))
    
    # Prüfen, ob diese CSV-Praxis bereits in der Datenbank existiert (anhand Name + PLZ + Straße)
    existierende_praxis = Praxis.query.filter_by(
        name=csv_praxis['name'],
        plz=csv_praxis.get('plz', ''),
        strasse=csv_praxis.get('straße', '')
    ).first()
    
    if existierende_praxis:
        # Wenn bereits in DB, zur normalen Claim-Route weiterleiten
        if existierende_praxis.ist_verifiziert:
            flash("Diese Praxis wird bereits von einem Inhaber verwaltet.", "warning")
            return redirect(url_for('suche', ort=existierende_praxis.stadt))
        return redirect(url_for('praxis_uebernehmen', praxis_id=existierende_praxis.id))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        vorname = request.form.get("vorname", "").strip()
        nachname = request.form.get("nachname", "").strip()
        
        if not email:
            flash("Bitte geben Sie Ihre E-Mail-Adresse ein.", "danger")
            return render_template("praxis_uebernehmen.html", praxis=csv_praxis)
        
        # Praxis in der Datenbank erstellen
        import re
        slug_base = re.sub(r'[^a-z0-9]+', '-', csv_praxis['name'].lower()).strip('-')
        slug = f"{slug_base}-{secrets.token_hex(4)}"
        
        neue_praxis = Praxis(
            name=csv_praxis['name'],
            email=email,
            telefon=csv_praxis.get('telefon', ''),
            webseite=csv_praxis.get('webseite', ''),
            strasse=csv_praxis.get('straße', ''),
            plz=csv_praxis.get('plz', ''),
            stadt=csv_praxis.get('stadt', ''),
            latitude=csv_praxis.get('lat'),
            longitude=csv_praxis.get('lng'),
            slug=slug,
            paket='',
            ist_verifiziert=False,
            landingpage_aktiv=False
        )
        
        db.session.add(neue_praxis)
        db.session.commit()
        
        # Verifizierungs-Token erstellen
        token = secrets.token_urlsafe(32)
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Claim erstellen
        neuer_claim = Claim(
            email=email,
            praxis_name=neue_praxis.name,
            plz=neue_praxis.plz,
            strasse=neue_praxis.strasse,
            praxis_id=neue_praxis.id,
            status='pending',
            verification_token=token,
            token_expires_at=token_expires,
            verification_method='email'
        )
        
        db.session.add(neuer_claim)
        db.session.commit()
        
        # Bestätigungslink erstellen
        bestaetigungs_url = url_for('praxis_verifizieren', token=token, _external=True)
        
        from services.email_service import send_praxis_verifizierung
        send_praxis_verifizierung(email, neue_praxis.name, bestaetigungs_url)
        
        flash(f"Wir haben eine Bestätigungs-E-Mail an {email} gesendet. Bitte klicken Sie auf den Link in der E-Mail, um die Übernahme zu bestätigen.", "success")
        return render_template("praxis_uebernehmen_gesendet.html", 
                             praxis=neue_praxis, 
                             email=email)
    
    return render_template("praxis_uebernehmen.html", praxis=csv_praxis)

# 🌐 Praxis übernehmen - Start des Claim-Prozesses
@app.route("/praxis-uebernehmen/<int:praxis_id>", methods=["GET", "POST"])
def praxis_uebernehmen(praxis_id):
    """Seite für das Übernehmen einer bestehenden Praxis"""
    import secrets
    from datetime import timedelta
    
    praxis = Praxis.query.get_or_404(praxis_id)
    
    # Prüfen, ob Praxis bereits verifiziert ist
    if praxis.ist_verifiziert and praxis.zahnarzt_id:
        flash("Diese Praxis wird bereits von einem Inhaber verwaltet.", "warning")
        return redirect(url_for('suche', ort=praxis.stadt))
    
    # Prüfen, ob es bereits einen offenen Claim gibt
    offener_claim = Claim.query.filter_by(
        praxis_id=praxis_id,
        status='pending'
    ).first()
    
    if offener_claim:
        flash("Für diese Praxis läuft bereits eine Übernahme-Anfrage. Bitte warten Sie auf die Bestätigung.", "info")
        return redirect(url_for('suche', ort=praxis.stadt))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        vorname = request.form.get("vorname", "").strip()
        nachname = request.form.get("nachname", "").strip()
        
        if not email:
            flash("Bitte geben Sie Ihre E-Mail-Adresse ein.", "danger")
            return render_template("praxis_uebernehmen.html", praxis=praxis)
        
        # Verifizierungs-Token erstellen
        token = secrets.token_urlsafe(32)
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Claim erstellen
        neuer_claim = Claim(
            email=email,
            praxis_name=praxis.name,
            plz=praxis.plz,
            strasse=praxis.strasse,
            praxis_id=praxis_id,
            status='pending',
            verification_token=token,
            token_expires_at=token_expires,
            verification_method='email'
        )
        
        db.session.add(neuer_claim)
        db.session.commit()
        
        # Bestätigungslink erstellen
        bestaetigungs_url = url_for('praxis_verifizieren', token=token, _external=True)
        
        from services.email_service import send_praxis_verifizierung
        send_praxis_verifizierung(email, praxis.name, bestaetigungs_url)
        
        flash(f"Wir haben eine Bestätigungs-E-Mail an {email} gesendet. Bitte klicken Sie auf den Link in der E-Mail, um die Übernahme zu bestätigen.", "success")
        return render_template("praxis_uebernehmen_gesendet.html", 
                             praxis=praxis, 
                             email=email)
    
    return render_template("praxis_uebernehmen.html", praxis=praxis)

# 🌐 Praxis-Verifizierung nach Klick auf E-Mail-Link
@app.route("/praxis-verifizieren/<token>")
def praxis_verifizieren(token):
    """Verifiziert den Claim und leitet zur Paketauswahl weiter"""
    claim = Claim.query.filter_by(verification_token=token).first()
    
    if not claim:
        flash("Ungültiger oder abgelaufener Verifizierungslink.", "danger")
        return redirect(url_for('index'))
    
    # Token abgelaufen?
    if claim.token_expires_at and claim.token_expires_at < datetime.utcnow():
        flash("Der Verifizierungslink ist abgelaufen. Bitte starten Sie die Übernahme erneut.", "warning")
        return redirect(url_for('praxis_uebernehmen', praxis_id=claim.praxis_id))
    
    # Claim als verifiziert markieren
    claim.status = 'verifying'
    claim.verified_at = datetime.utcnow()
    db.session.commit()
    
    # Session-Daten für späteren Prozess speichern
    session['claim_id'] = claim.id
    session['claim_email'] = claim.email
    session['claim_praxis_id'] = claim.praxis_id
    
    # Zur Paketauswahl weiterleiten
    return redirect(url_for('praxis_paket_waehlen', claim_id=claim.id))

# 🌐 Paketauswahl nach Verifizierung
@app.route("/praxis-paket-waehlen/<int:claim_id>", methods=["GET", "POST"])
def praxis_paket_waehlen(claim_id):
    """Paketauswahl für die übernommene Praxis"""
    claim = Claim.query.get_or_404(claim_id)
    praxis = Praxis.query.get_or_404(claim.praxis_id)
    
    # Prüfen, ob Claim valide ist
    if claim.status not in ['verifying', 'pending']:
        flash("Diese Übernahme wurde bereits abgeschlossen oder abgelehnt.", "info")
        return redirect(url_for('index'))
    
    if request.method == "POST":
        paket = request.form.get("paket", "basic")
        zahlweise = request.form.get("zahlweise", "monatlich")
        passwort = request.form.get("passwort")
        passwort_bestaetigen = request.form.get("passwort_bestaetigen")
        
        # Passwort validieren
        if not passwort or passwort != passwort_bestaetigen:
            flash("Die Passwörter stimmen nicht überein.", "danger")
            return render_template("praxis_paket_waehlen.html", claim=claim, praxis=praxis)
        
        # Prüfen, ob Zahnarzt-Account mit dieser E-Mail existiert
        zahnarzt = Zahnarzt.query.filter_by(email=claim.email).first()
        
        if not zahnarzt:
            # Neuen Zahnarzt-Account erstellen
            zahnarzt = Zahnarzt(
                email=claim.email,
                vorname='',
                nachname=''
            )
            zahnarzt.set_password(passwort)
            db.session.add(zahnarzt)
            db.session.flush()
        
        # Praxis dem Zahnarzt zuordnen
        praxis.zahnarzt_id = zahnarzt.id
        praxis.ist_verifiziert = True
        praxis.paket = paket.lower()
        
        # Claim als genehmigt markieren
        claim.status = 'approved'
        claim.zahnarzt_id = zahnarzt.id
        claim.gewaehltes_paket = paket
        claim.bearbeitet_am = datetime.utcnow()
        
        db.session.commit()
        
        # Zahnarzt einloggen
        login_user(zahnarzt)
        
        # Bei kostenpflichtigen Paketen zum Checkout, sonst zum Dashboard
        if paket.lower() in ['premium', 'premiumplus']:
            session['gewaehltes_paket'] = paket
            session['zahlweise'] = zahlweise
            flash(f"Herzlich willkommen! Sie haben das {paket}-Paket gewählt. Bitte schließen Sie den Zahlungsvorgang ab.", "success")
            return redirect(url_for('checkout'))
        else:
            flash(f"Herzlich willkommen! Die Praxis {praxis.name} gehört jetzt zu Ihrem Konto.", "success")
            return redirect(url_for('zahnarzt_dashboard'))
    
    return render_template("praxis_paket_waehlen.html", claim=claim, praxis=praxis)


# 🌐 E-Mail-Bestätigung für Zahnärzte
@app.route("/zahnarzt-bestätigen")
def zahnarzt_bestaetigen():
    token = request.args.get("token")
    email = request.args.get("email")
    
    if not token or not email:
        flash("Ungültige Anfrage. Token oder E-Mail fehlt.", "danger")
        return redirect("/")
    
    # Überprüfen, ob Token gültig ist
    gefunden = False
    eintraege = []
    
    if os.path.isfile("neue_praxen.csv"):
        with open("neue_praxen.csv", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("email") == email and row.get("bestätigungs_token") == token:
                    # Token-Gültigkeit prüfen
                    from datetime import datetime
                    token_gueltig_bis = datetime.strptime(row.get("token_gültig_bis", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
                    
                    if datetime.now() > token_gueltig_bis:
                        flash("Der Bestätigungslink ist abgelaufen. Bitte registrieren Sie sich erneut.", "danger")
                        return redirect("/register")
                    
                    # Token ist gültig
                    row["bestätigt"] = "ja"
                    row["bestätigungs_token"] = ""  # Token nach Verwendung löschen
                    gefunden = True
                    
                eintraege.append(row)
    
    if not gefunden:
        flash("Ungültiger Bestätigungslink oder die E-Mail wurde bereits bestätigt.", "danger")
        return redirect("/")
    
    # Aktualisierte Daten zurückschreiben
    with open("neue_praxen.csv", "w", newline='', encoding='utf-8') as f:
        fieldnames = eintraege[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(eintraege)
    
    flash("Ihre E-Mail-Adresse wurde erfolgreich bestätigt. Sie können sich jetzt anmelden.", "success")
    return redirect("/zahnarzt-login")


# 🌐 Login-Seite für Zahnärzte
@app.route("/zahnarzt-login", methods=["GET", "POST"])
def zahnarzt_login():
    from flask_login import login_user
    from werkzeug.security import check_password_hash
    
    # Weiterleitung nach dem Login prüfen
    next_url = request.args.get("next", "/zahnarzt-dashboard")
    
    if request.method == "POST":
        email = request.form.get("email")
        passwort = request.form.get("passwort")
        
        # Weiterleitung nach dem Login auch aus dem Formular holen (falls vorhanden)
        form_next = request.form.get("next", next_url)
        
        # Zuerst in der Datenbank suchen (neue Registrierungen)
        zahnarzt = Zahnarzt.query.filter_by(email=email).first()
        
        if zahnarzt and zahnarzt.password_hash:
            # Passwort überprüfen
            if check_password_hash(zahnarzt.password_hash, passwort):
                # Flask-Login verwenden
                login_user(zahnarzt)
                
                # Session-Daten für Kompatibilität setzen
                session["angemeldet"] = True
                session["benutzer_typ"] = "zahnarzt"
                session["benutzer_email"] = email
                session["email"] = email
                session["benutzer_vorname"] = zahnarzt.vorname
                session["benutzer_nachname"] = zahnarzt.nachname
                
                # Praxis-Daten laden falls vorhanden
                if zahnarzt.praxis_id:
                    praxis = Praxis.query.get(zahnarzt.praxis_id)
                    if praxis:
                        session["praxisname"] = praxis.name
                        session["paket"] = praxis.paket or "Basis"
                
                flash(f"Willkommen zurück!", "success")
                print(f"✅ Zahnarzt {email} erfolgreich eingeloggt (Datenbank)")
                
                # Weiterleitung
                if form_next == "/praxis-einrichten" or session.get("praxis_einrichten"):
                    return redirect("/praxis-einrichten")
                
                return redirect(form_next)
            else:
                flash("E-Mail-Adresse oder Passwort ungültig.", "danger")
        else:
            flash("E-Mail-Adresse oder Passwort ungültig.", "danger")
    
    return render_template("zahnarzt-login.html", next=next_url)

@app.route("/zahnarzt-passwort-vergessen", methods=["GET", "POST"])
def zahnarzt_passwort_vergessen():
    from itsdangerous import URLSafeTimedSerializer
    
    nachricht = None
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        zahnarzt = Zahnarzt.query.filter_by(email=email).first()
        
        if zahnarzt:
            try:
                s = URLSafeTimedSerializer(app.secret_key)
                token = s.dumps(email, salt="passwort-reset")
                
                reset_url = url_for('zahnarzt_passwort_reset', token=token, _external=True)
                
                from services.email_service import send_passwort_reset_email
                result = send_passwort_reset_email(email, zahnarzt.vorname or "Zahnarzt", reset_url)
                if result:
                    print(f"✅ Passwort-Reset-E-Mail gesendet an {email}")
                else:
                    print(f"❌ Fehler beim Senden der Passwort-Reset-E-Mail an {email}")
            except Exception as e:
                print(f"❌ Passwort-Reset Fehler: {e}")
        
        nachricht = "Falls ein Konto mit dieser E-Mail-Adresse existiert, haben wir Ihnen einen Link zum Zurücksetzen gesendet. Bitte prüfen Sie Ihr Postfach und ggf. den Spam-Ordner."
    
    return render_template("zahnarzt-passwort-vergessen.html", nachricht=nachricht)

@app.route("/zahnarzt-passwort-reset/<token>", methods=["GET", "POST"])
def zahnarzt_passwort_reset(token):
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
    
    s = URLSafeTimedSerializer(app.secret_key)
    
    try:
        email = s.loads(token, salt="passwort-reset", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("Der Link ist ungültig oder abgelaufen. Bitte fordern Sie einen neuen Link an.", "danger")
        return redirect(url_for('zahnarzt_passwort_vergessen'))
    
    if request.method == "POST":
        passwort = request.form.get("passwort", "")
        passwort_bestaetigen = request.form.get("passwort_bestaetigen", "")
        
        if len(passwort) < 8:
            flash("Das Passwort muss mindestens 8 Zeichen lang sein.", "warning")
            return render_template("zahnarzt-passwort-reset.html", token=token)
        
        if passwort != passwort_bestaetigen:
            flash("Die Passwörter stimmen nicht überein.", "warning")
            return render_template("zahnarzt-passwort-reset.html", token=token)
        
        zahnarzt = Zahnarzt.query.filter_by(email=email).first()
        if zahnarzt:
            zahnarzt.set_password(passwort)
            db.session.commit()
            flash("Ihr Passwort wurde erfolgreich geändert. Sie können sich jetzt anmelden.", "success")
            return redirect(url_for('zahnarzt_login'))
        else:
            flash("Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.", "danger")
            return redirect(url_for('zahnarzt_passwort_vergessen'))
    
    return render_template("zahnarzt-passwort-reset.html", token=token)

# 🌐 Seite zur Paketauswahl
@app.route("/paketwahl", methods=["GET"])
def paketwahl():
    return render_template("paketwahl.html", active_page='registrieren')

# ✅ Danke-Seite nach Registrierung (Basis)
@app.route("/danke")
def danke():
        paket = session.get("paket", "unbekannt")
        praxisname = session.get("praxisname", "Ihre Praxis")
        return render_template("danke.html", paket=paket, praxisname=praxisname)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    paket = session.get("paket", "Unbekannt")
    praxisname = session.get("praxisname", "Ihre Praxis")
    email = session.get("email", "keine E-Mail")
    vorname = session.get("vorname", "")
    nachname = session.get("nachname", "")
    strasse = session.get("strasse", "")
    plz = session.get("plz", "")
    stadt = session.get("stadt", "")
    zahlweise = session.get("zahlweise", "monatlich")

    preise = berechne_preislogik(paket, zahlweise)

    return render_template(
        "checkout.html",
        paket=paket,
        praxisname=praxisname,
        email=email,
        vorname=vorname,
        nachname=nachname,
        strasse=strasse,
        plz=plz,
        stadt=stadt,
        zahlweise=zahlweise,
        preis_netto=preise["netto"],
        preis_mwst=preise["mwst"],
        preis_brutto=preise["brutto"]
    )

@app.route("/zahlung-abschliessen", methods=["POST"])
def zahlung_abschliessen():
    methode = request.form.get("zahlung", "Unbekannt")
    paket = session.get("paket", "Unbekannt")
    praxisname = session.get("praxisname", "Ihre Praxis")
    email = session.get("email", "keine E-Mail")
    zahlweise = session.get("zahlweise", "monatlich")
    
    preise = berechne_preislogik(paket, zahlweise)
    brutto_preis = preise["brutto"]
    
    print(f"💳 Gewählte Zahlungsmethode: {methode}")
    
    # Bei Kreditkarte zu Stripe-Checkout-Seite weiterleiten
    if methode == "Kreditkarte":
        try:
            # Domain für Redirect-URLs ermitteln
            your_domain = request.host_url.rstrip('/')
            
            # Produkt- und Preisinformationen dynamisch zusammenstellen
            paket_beschreibung = f"Dentalax {paket}-Paket ({zahlweise})"
            
            # Preis in Cent umrechnen für Stripe
            stripe_preis = int(brutto_preis * 100)
            
            # Alle Stammdaten in Stripe-Metadaten speichern für spätere Wiederherstellung
            vorname = session.get("vorname", "")
            nachname = session.get("nachname", "")
            strasse = session.get("strasse", "")
            plz = session.get("plz", "")
            stadt = session.get("stadt", "")
            telefon = session.get("telefon", "")
            
            # Checkout-Session erstellen mit vollständigen Metadaten
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {
                                'name': paket_beschreibung,
                                'description': f'Zahnärztliches {paket} Listingpaket für {praxisname}'
                            },
                            'unit_amount': stripe_preis,
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url=f'{your_domain}/zahlung-erfolgreich?methode=Kreditkarte&session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'{your_domain}/checkout',
                client_reference_id=email,
                customer_email=email,
                metadata={
                    'paket': paket,
                    'praxisname': praxisname,
                    'zahlweise': zahlweise,
                    'vorname': vorname,
                    'nachname': nachname,
                    'strasse': strasse,
                    'plz': plz,
                    'stadt': stadt,
                    'telefon': telefon,
                    'email': email
                }
            )
            
            # Zu Stripe Checkout weiterleiten
            return redirect(checkout_session.url)
            
        except Exception as e:
            print(f"⚠️ Stripe Fehler: {e}")
            flash(f"Bei der Zahlung ist ein Fehler aufgetreten: {str(e)}", "danger")
            return redirect("/checkout")
    
    # Bei anderen Zahlungsmethoden zur Erfolgsseite weiterleiten
    return redirect(f"/zahlung-erfolgreich?methode={methode}")

@app.route("/zahlung-erfolgreich")
def zahlung_erfolgreich():
    methode = request.args.get("methode", "Unbekannt")
    session_id = request.args.get("session_id")
    
    # Bei Stripe-Zahlungen: Versuchen, Daten aus Stripe-Metadaten wiederherzustellen
    if methode == "Kreditkarte" and session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            # Metadaten aus Stripe-Session lesen und in Flask-Session wiederherstellen
            stripe_metadata = checkout_session.metadata or {}
            
            # Nur überschreiben wenn Session-Daten fehlen oder leer sind
            if stripe_metadata.get('paket') and not session.get('paket'):
                session['paket'] = stripe_metadata.get('paket')
            if stripe_metadata.get('praxisname') and session.get('praxisname') in [None, '', 'Ihre Praxis']:
                session['praxisname'] = stripe_metadata.get('praxisname')
            if stripe_metadata.get('email') and session.get('email') in [None, '', 'keine E-Mail']:
                session['email'] = stripe_metadata.get('email')
            if stripe_metadata.get('zahlweise') and not session.get('zahlweise'):
                session['zahlweise'] = stripe_metadata.get('zahlweise')
            if stripe_metadata.get('vorname') and not session.get('vorname'):
                session['vorname'] = stripe_metadata.get('vorname')
            if stripe_metadata.get('nachname') and not session.get('nachname'):
                session['nachname'] = stripe_metadata.get('nachname')
            if stripe_metadata.get('strasse') and not session.get('strasse'):
                session['strasse'] = stripe_metadata.get('strasse')
            if stripe_metadata.get('plz') and not session.get('plz'):
                session['plz'] = stripe_metadata.get('plz')
            if stripe_metadata.get('stadt') and not session.get('stadt'):
                session['stadt'] = stripe_metadata.get('stadt')
            if stripe_metadata.get('telefon') and not session.get('telefon'):
                session['telefon'] = stripe_metadata.get('telefon')
            
            print(f"🔄 Stripe-Metadaten wiederhergestellt: {stripe_metadata}")
        except Exception as e:
            print(f"⚠️ Fehler beim Abrufen der Stripe-Metadaten: {e}")
    
    # Session-Daten auslesen (jetzt möglicherweise aus Stripe wiederhergestellt)
    paket = session.get("paket", "Unbekannt")
    praxisname = session.get("praxisname", "Ihre Praxis")
    email = session.get("email", "keine E-Mail")
    zahlweise = session.get("zahlweise", "monatlich")
    vorname = session.get("vorname", "")
    nachname = session.get("nachname", "")
    strasse = session.get("strasse", "")
    plz = session.get("plz", "")
    stadt = session.get("stadt", "")
    telefon = session.get("telefon", "")
    
    # Session-Management für den Stripe-Workflow
    # Wir speichern die gesammelten Daten in einer bezahlung_stammdaten-Struktur
    # Diese wird dann im Praxisdaten-Formular ausgelesen
    session["bezahlung_stammdaten"] = {
        "praxisname": praxisname,
        "email": email,
        "vorname": vorname,
        "nachname": nachname,
        "strasse": strasse,
        "plz": plz,
        "stadt": stadt,
        "telefon": telefon,
        "webseite": session.get("webseite", ""),
        "paket": paket,
        "zahlweise": zahlweise
    }
    print(f"✅ Bezahlungsdaten zur Weiterverwendung in Session gespeichert: {session['bezahlung_stammdaten']}")
    
    # Bei Stripe-Zahlungen: Zahlungsstatus überprüfen
    if methode == "Kreditkarte" and session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            payment_status = checkout_session.payment_status
            if payment_status == "paid":
                flash("Ihre Zahlung wurde erfolgreich verarbeitet!", "success")
                
                # Patientendaten aus Checkout-Session auslesen
                if checkout_session.client_reference_id:
                    email = checkout_session.client_reference_id
                
                # Paket im Nutzerprofil in CSV aktualisieren
                if os.path.isfile("neue_praxen.csv"):
                    eintraege = []
                    paket_aktualisiert = False
                    
                    with open("neue_praxen.csv", newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get("email") == email:
                                row["paket"] = paket
                                row["zahlweise"] = zahlweise
                                paket_aktualisiert = True
                            eintraege.append(row)
                    
                    if paket_aktualisiert:
                        with open("neue_praxen.csv", "w", newline='', encoding='utf-8') as f:
                            fieldnames = eintraege[0].keys()
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(eintraege)
                        
                        print(f"✅ Paket für {email} aktualisiert auf {paket} ({zahlweise})")
            else:
                flash("Ihre Zahlung ist noch in Bearbeitung. Wir informieren Sie, sobald sie abgeschlossen ist.", "info")
        except Exception as e:
            print(f"⚠️ Stripe-Fehler beim Abrufen der Session: {e}")
            # Fehlermeldung nur anzeigen, wenn wir erwarten, dass Stripe funktionieren sollte
            # und nicht schon auf der Praxiseinrichtungsseite sind
            if methode == "Kreditkarte" and session_id and not session.get('praxis_einrichten'):
                # Prüfen, ob die Zahlung bereits erfolgreich war
                try:
                    # Versuch, die Session-ID zu überprüfen
                    checkout_session = stripe.checkout.Session.retrieve(session_id)
                    if checkout_session.payment_status == "paid":
                        # Wenn bezahlt, keine Fehlermeldung anzeigen
                        pass
                    else:
                        flash("Es gab ein Problem bei der Überprüfung Ihrer Zahlung. Bitte kontaktieren Sie uns.", "danger")
                except Exception as e:
                    print(f"⚠️ Fehler beim Überprüfen des Zahlungsstatus: {e}")
                    flash("Es gab ein Problem bei der Überprüfung Ihrer Zahlung. Bitte kontaktieren Sie uns.", "danger")

    details = berechne_preislogik(paket, zahlweise)
    heute = datetime.now().strftime("%Y-%m-%d")
    
    # Bei erfolgreicher Zahlung das Paket in neue_praxen.csv aktualisieren
    if methode != "Kreditkarte" or (methode == "Kreditkarte" and session_id):
        # 📄 PDF erstellen
        try:
            erstelle_rechnung_pdf(praxisname, email, paket, details, methode)
            print(f"✅ Rechnung erfolgreich erstellt für {praxisname}")
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Rechnung: {e}")
            # Fehler beim Erstellen der Rechnung, aber keine Fehlermeldung für den Benutzer
    
    # Session-Variablen für den nächsten Schritt setzen
    session['praxis_einrichten'] = True
    session['paket'] = paket
    session['zahlweise'] = zahlweise
    
    # Bei Stripe-Zahlung auch die Session-ID speichern
    if methode == "Kreditkarte" and session_id:
        session['stripe_session_id'] = session_id
    
    # Sicherstellen, dass das Paket im richtigen Format vorliegt (Premium oder PremiumPlus)
    format_paket = paket
    if paket.lower() in ["premium", "premiumplus"]:
        format_paket = paket.title()
        session['paket'] = format_paket
        
    # Zahlweise in Session speichern
    session['zahlweise'] = zahlweise
    
    # Stammdaten aus dem Checkout-Prozess für die Praxiseinrichtung speichern
    session['bezahlung_stammdaten'] = {
        'praxisname': praxisname,
        'email': email,
        'strasse': session.get('strasse', ''),
        'plz': session.get('plz', ''),
        'stadt': session.get('stadt', ''),
        'telefon': session.get('telefon', ''),
        'webseite': session.get('webseite', ''),
        'paket': format_paket,
        'zahlweise': zahlweise
    }
    
    # Praxis erstellen falls noch nicht vorhanden
    # Prüfen ob es bereits einen Zahnarzt mit dieser E-Mail gibt
    zahnarzt = Zahnarzt.query.filter_by(email=email).first()
    
    if not zahnarzt:
        # Neuen Zahnarzt erstellen
        temp_passwort = os.urandom(8).hex()
        marketing_val = session.get('marketing', 'nein') == 'ja'
        zahnarzt = Zahnarzt(
            email=email,
            password_hash=generate_password_hash(temp_passwort),
            vorname=vorname,
            nachname=nachname,
            marketing=marketing_val
        )
        db.session.add(zahnarzt)
        db.session.flush()
    
    # Praxis erstellen falls noch nicht vorhanden
    if not zahnarzt.praxis_id:
        # Koordinaten geocodieren
        praxis_lat, praxis_lng = None, None
        if strasse and plz and stadt:
            try:
                praxis_lat, praxis_lng = get_coordinates_from_address(f"{strasse}, {plz} {stadt}")
            except Exception as e:
                print(f"⚠️ Geocoding fehlgeschlagen: {e}")
        
        neue_praxis = Praxis(
            name=praxisname if praxisname and praxisname != "Ihre Praxis" else f"Praxis {nachname}",
            strasse=strasse if strasse else '',
            plz=plz if plz else '',
            stadt=stadt if stadt else '',
            telefon=telefon if telefon else '',
            webseite=session.get('webseite', ''),
            email=email,
            paket=format_paket,
            zahlungsart=zahlweise,
            slug=slugify(f"{praxisname if praxisname else nachname}-{stadt if stadt else 'deutschland'}"),
            landingpage_aktiv=False,  # Wird erst im Dashboard aktiviert
            latitude=praxis_lat,
            longitude=praxis_lng
        )
        db.session.add(neue_praxis)
        db.session.flush()
        
        zahnarzt.praxis_id = neue_praxis.id
        print(f"✅ Neue Praxis erstellt: {neue_praxis.name} (ID: {neue_praxis.id})")
    else:
        # Paket aktualisieren falls Praxis bereits existiert
        praxis = Praxis.query.get(zahnarzt.praxis_id)
        if praxis:
            praxis.paket = format_paket
            praxis.zahlungsart = zahlweise
    
    db.session.commit()
    
    # Zahnarzt einloggen
    login_user(zahnarzt)
    
    # Direkt ins Dashboard weiterleiten bei Premium-Paketen
    if format_paket.lower() in ['premium', 'premiumplus']:
        flash(f"Willkommen! Ihr {format_paket}-Paket ist jetzt aktiv. Richten Sie Ihre Praxis ein.", "success")
        return redirect(url_for('zahnarzt_dashboard', page='landingpage'))
    
    return render_template("zahlung_erfolgreich.html", methode=methode, paket=format_paket)

def erstelle_rechnung_pdf(praxisname, email, paket, details, methode):
    heute = datetime.now().strftime("%Y-%m-%d")
    dateiname = f"rechnung_{praxisname.replace(' ', '_').lower()}_{heute}.pdf"
    pfad = os.path.join("static/rechnungen", dateiname)
    
    # Erstelle Verzeichnis, falls es nicht existiert
    os.makedirs(os.path.dirname(pfad), exist_ok=True)

    # Lade HTML-Vorlage
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("rechnung_vorlage.html")

    html_content = template.render(
        heute=heute,
        praxisname=praxisname,
        email=email,
        paket=paket,
        methode=methode,
        details=details,
        rechnungsnummer=f"R-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    HTML(string=html_content).write_pdf(pfad)
    print(f"📄 Rechnung erstellt: {pfad}")


# =====================================================
# 🔒 ADMIN-BEREICH - Datenbankbasierte Verwaltung
# =====================================================

@app.route("/admin")
@admin_required
def admin_redirect():
    """Redirect /admin zu /admin/dashboard"""
    return redirect("/admin/dashboard")

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Admin-Dashboard mit Übersicht"""
    from sqlalchemy import func
    
    # Statistiken berechnen
    total_praxen = Praxis.query.count()
    premiumplus_count = Praxis.query.filter(func.lower(Praxis.paket) == 'premiumplus').count()
    premium_count = Praxis.query.filter(func.lower(Praxis.paket) == 'premium').count()
    basic_count = total_praxen - premiumplus_count - premium_count
    
    pending_claims = Claim.query.filter(Claim.status.in_(['pending', 'verifying'])).count()
    externe_jobs = ExternesInserat.query.count()
    
    stats = {
        'total_praxen': total_praxen,
        'premium_praxen': premiumplus_count + premium_count,
        'pending_claims': pending_claims,
        'externe_jobs': externe_jobs,
        'premiumplus_count': premiumplus_count,
        'premium_count': premium_count,
        'basic_count': basic_count
    }
    
    # Neueste Praxen
    neueste_praxen = Praxis.query.order_by(Praxis.erstelldatum.desc()).limit(5).all()
    
    # Offene Claims
    offene_claims = Claim.query.filter(Claim.status.in_(['pending', 'verifying'])).order_by(Claim.erstellt_am.desc()).limit(5).all()
    
    return render_template("admin_dashboard.html", 
                          active_page='dashboard',
                          stats=stats,
                          neueste_praxen=neueste_praxen,
                          offene_claims=offene_claims)

@app.route("/admin/praxen")
@admin_required
def admin_praxen():
    """Alle Praxen aus der Datenbank anzeigen"""
    from sqlalchemy import func
    
    filter_param = request.args.get('filter', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    # Query basierend auf Filter
    query = Praxis.query
    
    if filter_param == 'premiumplus':
        query = query.filter(func.lower(Praxis.paket) == 'premiumplus')
    elif filter_param == 'premium':
        query = query.filter(func.lower(Praxis.paket) == 'premium')
    elif filter_param == 'basic':
        query = query.filter(db.or_(
            func.lower(Praxis.paket) == 'basic',
            Praxis.paket.is_(None),
            Praxis.paket == ''
        ))
    elif filter_param == 'verifiziert':
        query = query.filter(Praxis.ist_verifiziert == True)
    
    # Sortierung: Neueste zuerst
    query = query.order_by(Praxis.erstelldatum.desc())
    
    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    praxen = pagination.items
    
    # Counts für Filter-Tabs
    counts = {
        'all': Praxis.query.count(),
        'premiumplus': Praxis.query.filter(func.lower(Praxis.paket) == 'premiumplus').count(),
        'premium': Praxis.query.filter(func.lower(Praxis.paket) == 'premium').count(),
        'basic': Praxis.query.filter(db.or_(
            func.lower(Praxis.paket) == 'basic',
            Praxis.paket.is_(None),
            Praxis.paket == ''
        )).count(),
        'verifiziert': Praxis.query.filter(Praxis.ist_verifiziert == True).count()
    }
    
    return render_template("admin_praxen_neu.html",
                          active_page='praxen',
                          praxen=praxen,
                          pagination=pagination,
                          filter=filter_param,
                          counts=counts)

@app.route("/admin/praxis/<int:praxis_id>/loeschen", methods=["POST"])
@admin_required
def admin_praxis_loeschen(praxis_id):
    """Praxis und alle zugehörigen Daten löschen"""
    praxis = Praxis.query.get(praxis_id)
    
    if not praxis:
        flash("Praxis nicht gefunden.", "danger")
        return redirect("/admin/praxen")
    
    praxis_name = praxis.name
    
    try:
        # Zugehörige Daten löschen (kaskadierende Löschung)
        
        # Zuerst Bewerbungen löschen (abhängig von Stellenangeboten)
        stellenangebot_ids = [s.id for s in Stellenangebot.query.filter_by(praxis_id=praxis_id).all()]
        if stellenangebot_ids:
            Bewerbung.query.filter(Bewerbung.stellenangebot_id.in_(stellenangebot_ids)).delete(synchronize_session=False)
        
        # Stellenangebote
        Stellenangebot.query.filter_by(praxis_id=praxis_id).delete()
        
        # Termine
        Termin.query.filter_by(praxis_id=praxis_id).delete()
        
        # Öffnungszeiten
        Oeffnungszeit.query.filter_by(praxis_id=praxis_id).delete()
        
        # Verfügbarkeit
        Verfuegbarkeit.query.filter_by(praxis_id=praxis_id).delete()
        
        # Behandlungsarten
        Behandlungsart.query.filter_by(praxis_id=praxis_id).delete()
        
        # Ausnahmen
        Ausnahme.query.filter_by(praxis_id=praxis_id).delete()
        
        # Leistungen
        Leistung.query.filter_by(praxis_id=praxis_id).delete()
        
        # Team-Mitglieder
        TeamMitglied.query.filter_by(praxis_id=praxis_id).delete()
        
        # Praxis-Bilder
        PraxisBild.query.filter_by(praxis_id=praxis_id).delete()
        
        # Paket-Buchungen
        PaketBuchung.query.filter_by(praxis_id=praxis_id).delete()
        
        # Terminanfragen
        Terminanfrage.query.filter_by(praxis_id=praxis_id).delete()
        
        # Bewertungen
        Bewertung.query.filter_by(praxis_id=praxis_id).delete()
        
        # Claims für diese Praxis
        Claim.query.filter_by(praxis_id=praxis_id).delete()
        
        # Zahnarzt-Verknüpfung entfernen (nicht löschen, nur praxis_id auf NULL setzen)
        Zahnarzt.query.filter_by(praxis_id=praxis_id).update({'praxis_id': None})
        
        # Praxis selbst löschen
        db.session.delete(praxis)
        db.session.commit()
        
        flash(f"Praxis '{praxis_name}' und alle zugehörigen Daten wurden erfolgreich gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler beim Löschen: {str(e)}", "danger")
    
    return redirect("/admin/praxen")

@app.route("/admin/praxis/<int:praxis_id>/bearbeiten", methods=["GET", "POST"])
@admin_required
def admin_praxis_bearbeiten(praxis_id):
    praxis = Praxis.query.get(praxis_id)
    if not praxis:
        flash("Praxis nicht gefunden.", "danger")
        return redirect("/admin/praxen")

    if request.method == "POST":
        praxis.name = request.form.get("name", "").strip()
        praxis.slug = request.form.get("slug", "").strip()
        praxis.email = request.form.get("email", "").strip()
        praxis.telefon = request.form.get("telefon", "").strip()
        webseite_val = request.form.get("webseite", "").strip()
        if webseite_val and not webseite_val.startswith(("http://", "https://")):
            webseite_val = "https://" + webseite_val
        praxis.webseite = webseite_val or None
        praxis.strasse = request.form.get("strasse", "").strip()
        praxis.plz = request.form.get("plz", "").strip()
        praxis.stadt = request.form.get("stadt", "").strip()

        lat = request.form.get("latitude", "").strip()
        lng = request.form.get("longitude", "").strip()
        try:
            praxis.latitude = float(lat) if lat else None
        except ValueError:
            praxis.latitude = None
        try:
            praxis.longitude = float(lng) if lng else None
        except ValueError:
            praxis.longitude = None

        praxis.beschreibung = request.form.get("beschreibung", "").strip() or None
        praxis.hero_titel = request.form.get("hero_titel", "").strip() or None
        praxis.hero_untertitel = request.form.get("hero_untertitel", "").strip() or None
        praxis.hero_button_text = request.form.get("hero_button_text", "").strip() or "Termin vereinbaren"
        praxis.ueber_uns_titel = request.form.get("ueber_uns_titel", "").strip() or None
        praxis.ueber_uns_text = request.form.get("ueber_uns_text", "").strip() or None
        praxis.leistungsschwerpunkte = request.form.get("leistungsschwerpunkte", "").strip() or None
        praxis.seo_titel = request.form.get("seo_titel", "").strip() or None
        praxis.seo_beschreibung = request.form.get("seo_beschreibung", "").strip() or None
        praxis.seo_keywords = request.form.get("seo_keywords", "").strip() or None

        praxis.paket = request.form.get("paket", "basic")
        praxis.zahlungsart = request.form.get("zahlungsart", "").strip() or None
        praxis.farbschema = request.form.get("farbschema", "blau")

        praxis.ist_verifiziert = "ist_verifiziert" in request.form
        praxis.landingpage_aktiv = "landingpage_aktiv" in request.form

        praxis.terminbuchung_aktiv = "terminbuchung_aktiv" in request.form
        praxis.terminbuchung_modus = request.form.get("terminbuchung_modus", "dashboard")
        praxis.terminbuchung_url = request.form.get("terminbuchung_url", "").strip() or None
        praxis.formular_email = request.form.get("formular_email", "").strip() or None
        praxis.formular_text = request.form.get("formular_text", "").strip() or None
        praxis.extern_anbieter = request.form.get("extern_anbieter", "").strip() or None
        praxis.termin_dauer = request.form.get("termin_dauer", 30, type=int)
        praxis.vorlaufzeit = request.form.get("vorlaufzeit", 2, type=int)

        praxis.angstpatientenfreundlich = "angstpatientenfreundlich" in request.form
        praxis.kinderfreundlich = "kinderfreundlich" in request.form
        praxis.barrierefrei = "barrierefrei" in request.form
        praxis.abendsprechstunde = "abendsprechstunde" in request.form
        praxis.samstagssprechstunde = "samstagssprechstunde" in request.form
        praxis.sprachen = request.form.get("sprachen", "").strip() or None

        try:
            db.session.commit()
            flash(f"Praxis '{praxis.name}' wurde erfolgreich aktualisiert.", "success")
            return redirect(f"/admin/praxis/{praxis.id}/bearbeiten")
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler beim Speichern: {str(e)}", "danger")

    return render_template("admin_praxis_bearbeiten.html",
                          active_page='praxen',
                          praxis=praxis)

@app.route("/admin/praxis/<int:praxis_id>/verifizieren", methods=["POST"])
@admin_required
def admin_praxis_verifizieren(praxis_id):
    praxis = Praxis.query.get(praxis_id)
    if not praxis:
        flash("Praxis nicht gefunden.", "danger")
        return redirect("/admin/praxen")

    praxis.ist_verifiziert = not praxis.ist_verifiziert
    db.session.commit()

    status = "verifiziert" if praxis.ist_verifiziert else "auf ausstehend gesetzt"
    flash(f"Praxis '{praxis.name}' wurde {status}.", "success")
    return redirect("/admin/praxen")

# Claims-Verwaltung (Datenbankbasiert)
@app.route("/admin/claims")
@admin_required
def admin_claims():
    """Claims aus der Datenbank anzeigen"""
    status_param = request.args.get('status', 'pending')
    
    # Query basierend auf Status
    query = Claim.query
    
    if status_param == 'pending':
        query = query.filter(Claim.status == 'pending')
    elif status_param == 'verifying':
        query = query.filter(Claim.status == 'verifying')
    elif status_param == 'approved':
        query = query.filter(Claim.status == 'approved')
    elif status_param == 'rejected':
        query = query.filter(Claim.status == 'rejected')
    # 'all' zeigt alle
    
    claims = query.order_by(Claim.erstellt_am.desc()).all()
    
    # Counts für Tabs
    counts = {
        'pending': Claim.query.filter(Claim.status == 'pending').count(),
        'verifying': Claim.query.filter(Claim.status == 'verifying').count(),
        'approved': Claim.query.filter(Claim.status == 'approved').count(),
        'rejected': Claim.query.filter(Claim.status == 'rejected').count(),
        'all': Claim.query.count()
    }
    
    return render_template("admin_claims_neu.html",
                          active_page='claims',
                          claims=claims,
                          status=status_param,
                          counts=counts)

@app.route("/admin/pending-claims")
@admin_required
def admin_pending_claims_redirect():
    """Redirect alte URL zu neuer Claims-Seite"""
    return redirect("/admin/claims?status=pending")

# Neue datenbankbasierte Claim-Verwaltung
@app.route("/admin/claim/<int:claim_id>/genehmigen", methods=["POST"])
@admin_required
def admin_claim_genehmigen_db(claim_id):
    """Claim in der Datenbank genehmigen"""
    claim = Claim.query.get(claim_id)
    if not claim:
        flash("Claim nicht gefunden.", "danger")
        return redirect("/admin/claims")
    
    claim.status = 'approved'
    claim.verified_at = datetime.now()
    
    # Falls eine Praxis verknüpft ist, diese verifizieren
    if claim.praxis_id:
        praxis = Praxis.query.get(claim.praxis_id)
        if praxis:
            praxis.ist_verifiziert = True
    
    db.session.commit()
    flash(f"Claim für '{claim.praxis_name}' wurde genehmigt.", "success")
    return redirect("/admin/claims")

@app.route("/admin/claim/<int:claim_id>/ablehnen", methods=["POST"])
@admin_required
def admin_claim_ablehnen_db(claim_id):
    """Claim in der Datenbank ablehnen"""
    claim = Claim.query.get(claim_id)
    if not claim:
        flash("Claim nicht gefunden.", "danger")
        return redirect("/admin/claims")
    
    claim.status = 'rejected'
    db.session.commit()
    flash(f"Claim für '{claim.praxis_name}' wurde abgelehnt.", "success")
    return redirect("/admin/claims")

# Stellenangebote-Verwaltung
@app.route("/admin/stellenangebote")
@admin_required
def admin_stellenangebote():
    """Übersicht aller Stellenangebote"""
    interne_jobs = Stellenangebot.query.order_by(Stellenangebot.erstellt_am.desc()).all()
    externe_jobs = ExternesInserat.query.order_by(ExternesInserat.abgerufen_am.desc()).limit(50).all()
    
    # Bewerbungen zählen
    bewerbungen_count = Bewerbung.query.count() if 'Bewerbung' in dir() else 0
    try:
        bewerbungen_count = Bewerbung.query.count()
    except:
        bewerbungen_count = 0
    
    stats = {
        'interne': len(interne_jobs),
        'externe': len(externe_jobs),
        'bewerbungen': bewerbungen_count
    }
    
    # Letzte Sync-Zeit (vereinfacht)
    letzte_sync = None
    if externe_jobs:
        letzte_sync = externe_jobs[0].abgerufen_am.strftime('%d.%m.%Y %H:%M') if externe_jobs[0].abgerufen_am else None
    
    return render_template("admin_stellenangebote.html",
                          active_page='jobs',
                          interne_jobs=interne_jobs,
                          externe_jobs=externe_jobs,
                          stats=stats,
                          letzte_sync=letzte_sync)

@app.route("/admin/externe-jobs")
@admin_required
def admin_externe_jobs():
    """Zeigt nur externe TheirStack Jobs an"""
    externe_jobs = ExternesInserat.query.order_by(ExternesInserat.abgerufen_am.desc()).all()
    
    # Letzte Sync-Zeit
    letzte_sync = None
    if externe_jobs:
        letzte_sync = externe_jobs[0].abgerufen_am.strftime('%d.%m.%Y %H:%M') if externe_jobs[0].abgerufen_am else None
    
    return render_template("admin_externe_jobs.html",
                          active_page='external-jobs',
                          externe_jobs=externe_jobs,
                          letzte_sync=letzte_sync)

# Admin-Login
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        benutzer = request.form["benutzer"]
        passwort = request.form["passwort"]

        # ⚠️ Einfaches Passwort für Demo-Zwecke!
        if benutzer == "admin" and passwort == "geheim123":
            session["admin_eingeloggt"] = True
            flash("Erfolgreich eingeloggt.", "success")
            return redirect("/admin/dashboard")
        else:
            flash("Login fehlgeschlagen. Bitte überprüfen Sie Ihre Zugangsdaten.", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_eingeloggt", None)
    return redirect("/admin/login")


@app.route("/admin/wartungsmodus", methods=["GET", "POST"])
@admin_required
def admin_wartungsmodus():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle":
            current = SiteSettings.get('maintenance_mode', 'false')
            new_val = 'false' if current == 'true' else 'true'
            SiteSettings.set('maintenance_mode', new_val)
            status = "aktiviert" if new_val == 'true' else "deaktiviert"
            flash(f'Wartungsmodus wurde {status}.', 'success')
        elif action == "set_password":
            pw = request.form.get("maintenance_password", "").strip()
            if pw:
                SiteSettings.set('maintenance_password', pw)
                flash('Wartungsmodus-Passwort wurde aktualisiert.', 'success')
            else:
                flash('Bitte ein Passwort eingeben.', 'warning')
        return redirect(url_for('admin_wartungsmodus'))
    
    maintenance_active = SiteSettings.get('maintenance_mode', 'false') == 'true'
    maintenance_password = SiteSettings.get('maintenance_password', '')
    return render_template("admin_wartungsmodus.html",
                          active_page='wartungsmodus',
                          maintenance_active=maintenance_active,
                          maintenance_password=maintenance_password)


@app.route("/wartung/zugang", methods=["POST"])
@csrf.exempt
def wartung_zugang():
    password = request.form.get("password", "")
    stored_password = SiteSettings.get('maintenance_password', '')
    if stored_password and password == stored_password:
        session['maintenance_bypass'] = True
        return redirect("/")
    return render_template("maintenance.html", error="Falsches Passwort."), 503


@app.route("/admin/externe-jobs-sync")
@admin_required
def admin_externe_jobs_sync():
    """Synchronisiert externe Stellenangebote von TheirStack"""
    try:
        result = sync_external_jobs(limit=25)
        if 'error' in result:
            flash(f"Fehler bei der Synchronisierung: {result['error']}", "danger")
        elif result.get('new', 0) == 0 and result.get('updated', 0) == 0:
            flash("TheirStack Sync: Keine neuen Jobs gefunden. Möglicherweise API-Limit erreicht oder Verbindungsproblem.", "warning")
        else:
            flash(f"TheirStack Sync erfolgreich: {result['new']} neue Jobs, {result['updated']} aktualisiert", "success")
    except Exception as e:
        flash(f"TheirStack Sync fehlgeschlagen: {str(e)}", "danger")
    return redirect("/admin/stellenangebote")

@app.route("/admin/seo-texte")
@admin_required
def admin_seo_texte():
    """Übersicht der Stadt-SEO-Texte mit Paginierung und Suche"""
    from models import StadtSEO
    
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = StadtSEO.query
    if search_query:
        query = query.filter(StadtSEO.stadt_name.ilike(f'%{search_query}%'))
    
    pagination = query.order_by(StadtSEO.stadt_name).paginate(page=page, per_page=per_page, error_out=False)
    seo_eintraege = pagination.items
    
    total_seo_count = StadtSEO.query.count()
    
    staedte_ohne_seo = []
    stadt_set = set()
    with open("zahnaerzte.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stadt = row.get("stadt", "").strip()
            if stadt:
                stadt_set.add(stadt)
    
    existierende_slugs = {s.stadt_slug for s in StadtSEO.query.all()}
    for stadt in sorted(stadt_set):
        slug = stadt.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
        if slug not in existierende_slugs:
            staedte_ohne_seo.append(stadt)
    
    return render_template("admin_seo_texte.html", 
                         seo_eintraege=seo_eintraege,
                         pagination=pagination,
                         search_query=search_query,
                         total_seo_count=total_seo_count,
                         staedte_ohne_seo=staedte_ohne_seo,
                         active_page='seo-texte')

@app.route("/admin/seo-texte/generieren", methods=["POST"])
@admin_required
def admin_seo_generieren():
    """Generiert SEO-Texte für eine Stadt"""
    from models import StadtSEO
    from services.ai_service import generate_city_seo_texts
    
    stadt_name = request.form.get('stadt_name', '').strip()
    if not stadt_name:
        flash("Bitte Stadt angeben.", "danger")
        return redirect("/admin/seo-texte")
    
    stadt_slug = stadt_name.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
    
    existing = StadtSEO.query.filter_by(stadt_slug=stadt_slug).first()
    if existing:
        flash(f"SEO-Texte für {stadt_name} existieren bereits.", "warning")
        return redirect("/admin/seo-texte")
    
    seo_data = generate_city_seo_texts(stadt_name)
    
    import json as json_lib
    faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
    
    new_seo = StadtSEO(
        stadt_slug=stadt_slug,
        stadt_name=stadt_name,
        meta_title=seo_data.get('meta_title', f"Zahnarzt {stadt_name} | Top Zahnärzte finden - Dentalax"),
        meta_description=seo_data.get('meta_description', f"Finden Sie Ihren Zahnarzt in {stadt_name}. Vergleichen Sie Bewertungen und Leistungen."),
        h1_titel=seo_data.get('h1_titel', f"Zahnarzt {stadt_name}: Finden Sie Ihre ideale Praxis"),
        teaser_text=seo_data.get('teaser_text', f"Entdecken Sie qualifizierte Zahnärzte in {stadt_name} und Umgebung."),
        h2_titel_1=seo_data.get('h2_titel_1'),
        seo_text_1=seo_data.get('seo_text_1'),
        h2_titel_2=seo_data.get('h2_titel_2'),
        seo_text_2=seo_data.get('seo_text_2'),
        faq_json=faq_json_str
    )
    
    db.session.add(new_seo)
    db.session.commit()
    
    flash(f"SEO-Texte für {stadt_name} erfolgreich generiert!", "success")
    return redirect("/admin/seo-texte")

@app.route("/admin/seo-texte/batch-generieren", methods=["POST"])
@admin_required
def admin_seo_batch_generieren():
    """Generiert SEO-Texte für mehrere Städte - PARALLEL"""
    from models import StadtSEO
    from services.ai_service import generate_city_seo_texts
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import json as json_lib
    
    anzahl = min(int(request.form.get('anzahl', 10)), 50)  # Max 50 mit paralleler Verarbeitung
    
    stadt_set = set()
    with open("zahnaerzte.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stadt = row.get("stadt", "").strip()
            if stadt:
                stadt_set.add(stadt)
    
    existierende_slugs = {s.stadt_slug for s in StadtSEO.query.all()}
    
    staedte_zu_generieren = []
    for stadt in sorted(stadt_set):
        slug = stadt.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
        if slug not in existierende_slugs:
            staedte_zu_generieren.append((stadt, slug))
    
    staedte_batch = staedte_zu_generieren[:anzahl]
    
    def generate_single(stadt_data):
        stadt_name, stadt_slug = stadt_data
        try:
            seo_data = generate_city_seo_texts(stadt_name)
            return {
                'success': True,
                'stadt_slug': stadt_slug,
                'stadt_name': stadt_name,
                'seo_data': seo_data
            }
        except Exception as e:
            logging.error(f"Fehler bei {stadt_name}: {e}")
            return {'success': False, 'stadt_name': stadt_name, 'error': str(e)}
    
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(generate_single, s): s for s in staedte_batch}
        for future in as_completed(futures):
            results.append(future.result())
    
    from sqlalchemy.exc import IntegrityError
    
    generiert = 0
    skipped = 0
    for result in results:
        if result['success']:
            try:
                if StadtSEO.query.filter_by(stadt_slug=result['stadt_slug']).first():
                    skipped += 1
                    continue
                    
                seo_data = result['seo_data']
                faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
                
                new_seo = StadtSEO(
                    stadt_slug=result['stadt_slug'],
                    stadt_name=result['stadt_name'],
                    meta_title=seo_data.get('meta_title', f"Zahnarzt {result['stadt_name']} | Top Zahnärzte finden - Dentalax"),
                    meta_description=seo_data.get('meta_description', f"Finden Sie Ihren Zahnarzt in {result['stadt_name']}."),
                    h1_titel=seo_data.get('h1_titel', f"Zahnarzt {result['stadt_name']}: Finden Sie Ihre ideale Praxis"),
                    teaser_text=seo_data.get('teaser_text', f"Entdecken Sie qualifizierte Zahnärzte in {result['stadt_name']} und Umgebung."),
                    h2_titel_1=seo_data.get('h2_titel_1'),
                    seo_text_1=seo_data.get('seo_text_1'),
                    h2_titel_2=seo_data.get('h2_titel_2'),
                    seo_text_2=seo_data.get('seo_text_2'),
                    faq_json=faq_json_str
                )
                db.session.add(new_seo)
                db.session.commit()
                generiert += 1
            except IntegrityError:
                db.session.rollback()
                skipped += 1
            except Exception as e:
                logging.error(f"DB-Fehler bei {result['stadt_name']}: {e}")
                db.session.rollback()
    
    msg = f"{generiert} SEO-Texte erfolgreich generiert!"
    if skipped > 0:
        msg += f" ({skipped} bereits vorhanden)"
    flash(msg, "success")
    return redirect("/admin/seo-texte")

@app.route("/admin/seo-texte/regenerieren/<int:seo_id>", methods=["POST"])
@admin_required
def admin_seo_regenerieren(seo_id):
    """Regeneriert SEO-Texte für eine bestehende Stadt"""
    from models import StadtSEO
    from services.ai_service import generate_city_seo_texts
    import json as json_lib
    
    seo_entry = StadtSEO.query.get_or_404(seo_id)
    stadt_name = seo_entry.stadt_name
    
    try:
        seo_data = generate_city_seo_texts(stadt_name)
        faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
        
        seo_entry.meta_title = seo_data.get('meta_title', f"Zahnarzt {stadt_name} | Top Zahnärzte finden - Dentalax")
        seo_entry.meta_description = seo_data.get('meta_description', f"Finden Sie Ihren Zahnarzt in {stadt_name}.")
        seo_entry.h1_titel = seo_data.get('h1_titel', f"Zahnarzt {stadt_name}: Finden Sie Ihre ideale Praxis")
        seo_entry.teaser_text = seo_data.get('teaser_text', f"Entdecken Sie qualifizierte Zahnärzte in {stadt_name}.")
        seo_entry.h2_titel_1 = seo_data.get('h2_titel_1')
        seo_entry.seo_text_1 = seo_data.get('seo_text_1')
        seo_entry.h2_titel_2 = seo_data.get('h2_titel_2')
        seo_entry.seo_text_2 = seo_data.get('seo_text_2')
        seo_entry.faq_json = faq_json_str
        seo_entry.aktualisiert_am = datetime.utcnow()
        
        db.session.commit()
        flash(f"SEO-Texte für {stadt_name} erfolgreich regeneriert!", "success")
    except Exception as e:
        flash(f"Fehler bei Regenerierung: {str(e)}", "danger")
    
    return redirect("/admin/seo-texte")


# =============== LEISTUNG + STADT SEO ADMIN ===============
@app.route("/admin/leistung-seo-texte")
@admin_required
def admin_leistung_seo_texte():
    """Übersicht der Leistung+Stadt SEO-Texte mit Paginierung und Suche"""
    from models import LeistungStadtSEO
    from leistungen_config import LEISTUNGEN
    
    selected_leistung = request.args.get('leistung', 'implantologie')
    if selected_leistung not in LEISTUNGEN:
        selected_leistung = 'implantologie'
    
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = LeistungStadtSEO.query.filter_by(leistung_slug=selected_leistung)
    if search_query:
        query = query.filter(LeistungStadtSEO.stadt_name.ilike(f'%{search_query}%'))
    
    pagination = query.order_by(LeistungStadtSEO.stadt_name).paginate(page=page, per_page=per_page, error_out=False)
    seo_eintraege = pagination.items
    
    counts = {}
    for slug in LEISTUNGEN.keys():
        counts[slug] = LeistungStadtSEO.query.filter_by(leistung_slug=slug).count()
    
    total_count = LeistungStadtSEO.query.count()
    
    stadt_set = set()
    with open("zahnaerzte.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stadt = row.get("stadt", "").strip()
            if stadt:
                stadt_set.add(stadt)
    
    slug_to_stadt = {}
    for stadt in stadt_set:
        slug = stadt.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
        if slug not in slug_to_stadt:
            slug_to_stadt[slug] = stadt
    staedte_liste = sorted(slug_to_stadt.values())
    total_staedte = len(staedte_liste)
    
    existing_slugs_selected = {s.stadt_slug for s in LeistungStadtSEO.query.filter_by(leistung_slug=selected_leistung).all()}
    offene_staedte = total_staedte - len(existing_slugs_selected)
    
    return render_template("admin_leistung_seo_texte.html",
                         seo_eintraege=seo_eintraege,
                         pagination=pagination,
                         search_query=search_query,
                         leistungen=LEISTUNGEN,
                         selected_leistung=selected_leistung,
                         counts=counts,
                         total_count=total_count,
                         staedte_liste=staedte_liste,
                         total_staedte=total_staedte,
                         offene_staedte=offene_staedte,
                         active_page='leistung-seo-texte')


@app.route("/admin/leistung-seo-texte/generieren", methods=["POST"])
@admin_required
def admin_leistung_seo_generieren():
    """Generiert SEO-Texte für eine Leistung+Stadt Kombination"""
    from models import LeistungStadtSEO
    from services.ai_service import generate_leistung_stadt_seo_texts
    from leistungen_config import LEISTUNGEN
    import json as json_lib
    
    leistung_slug = request.form.get('leistung_slug', '').strip()
    stadt_name = request.form.get('stadt_name', '').strip()
    
    if not leistung_slug or leistung_slug not in LEISTUNGEN:
        flash("Ungültige Leistung.", "danger")
        return redirect("/admin/leistung-seo-texte")
    
    if not stadt_name:
        flash("Bitte Stadt angeben.", "danger")
        return redirect(f"/admin/leistung-seo-texte?leistung={leistung_slug}")
    
    leistung_name = LEISTUNGEN[leistung_slug]['name']
    stadt_slug = stadt_name.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
    
    existing = LeistungStadtSEO.query.filter_by(leistung_slug=leistung_slug, stadt_slug=stadt_slug).first()
    if existing:
        flash(f"SEO-Texte für {leistung_name} {stadt_name} existieren bereits.", "warning")
        return redirect(f"/admin/leistung-seo-texte?leistung={leistung_slug}")
    
    seo_data = generate_leistung_stadt_seo_texts(leistung_name, leistung_slug, stadt_name)
    faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
    
    new_seo = LeistungStadtSEO(
        leistung_slug=leistung_slug,
        leistung_name=leistung_name,
        stadt_slug=stadt_slug,
        stadt_name=stadt_name,
        meta_title=seo_data.get('meta_title'),
        meta_description=seo_data.get('meta_description'),
        h1_titel=seo_data.get('h1_titel'),
        teaser_text=seo_data.get('teaser_text'),
        h2_titel_1=seo_data.get('h2_titel_1'),
        seo_text_1=seo_data.get('seo_text_1'),
        h2_titel_2=seo_data.get('h2_titel_2'),
        seo_text_2=seo_data.get('seo_text_2'),
        faq_json=faq_json_str
    )
    
    db.session.add(new_seo)
    db.session.commit()
    
    flash(f"SEO-Texte für {leistung_name} {stadt_name} erfolgreich generiert!", "success")
    return redirect(f"/admin/leistung-seo-texte?leistung={leistung_slug}")


@app.route("/admin/leistung-seo-texte/batch-generieren", methods=["POST"])
@admin_required
def admin_leistung_seo_batch_generieren():
    """Generiert SEO-Texte für mehrere Städte einer Leistung - PARALLEL"""
    from models import LeistungStadtSEO
    from services.ai_service import generate_leistung_stadt_seo_texts
    from leistungen_config import LEISTUNGEN
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import json as json_lib
    
    leistung_slug = request.form.get('leistung_slug', '').strip()
    anzahl = min(int(request.form.get('anzahl', 10)), 50)  # Max 50 mit paralleler Verarbeitung
    
    if not leistung_slug or leistung_slug not in LEISTUNGEN:
        flash("Ungültige Leistung.", "danger")
        return redirect("/admin/leistung-seo-texte")
    
    leistung_name = LEISTUNGEN[leistung_slug]['name']
    
    stadt_set = set()
    with open("zahnaerzte.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stadt = row.get("stadt", "").strip()
            if stadt:
                stadt_set.add(stadt)
    
    slug_to_stadt = {}
    for stadt in stadt_set:
        slug = stadt.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
        if slug not in slug_to_stadt:
            slug_to_stadt[slug] = stadt
    
    existing_slugs = {s.stadt_slug for s in LeistungStadtSEO.query.filter_by(leistung_slug=leistung_slug).all()}
    
    staedte_ohne_seo = []
    for slug in sorted(slug_to_stadt.keys()):
        if slug not in existing_slugs:
            staedte_ohne_seo.append(slug_to_stadt[slug])
    
    staedte_batch = staedte_ohne_seo[:anzahl]
    
    def generate_single(stadt_name):
        try:
            stadt_slug = stadt_name.lower().replace(' ', '-').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe').replace('ß', 'ss')
            seo_data = generate_leistung_stadt_seo_texts(leistung_name, leistung_slug, stadt_name)
            return {
                'success': True,
                'stadt_slug': stadt_slug,
                'stadt_name': stadt_name,
                'seo_data': seo_data
            }
        except Exception as e:
            logging.error(f"Fehler bei {leistung_name} {stadt_name}: {e}")
            return {'success': False, 'stadt_name': stadt_name, 'error': str(e)}
    
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(generate_single, s): s for s in staedte_batch}
        for future in as_completed(futures):
            results.append(future.result())
    
    from sqlalchemy.exc import IntegrityError
    
    count = 0
    skipped = 0
    for result in results:
        if result['success']:
            try:
                if LeistungStadtSEO.query.filter_by(leistung_slug=leistung_slug, stadt_slug=result['stadt_slug']).first():
                    skipped += 1
                    continue
                    
                seo_data = result['seo_data']
                faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
                
                new_seo = LeistungStadtSEO(
                    leistung_slug=leistung_slug,
                    leistung_name=leistung_name,
                    stadt_slug=result['stadt_slug'],
                    stadt_name=result['stadt_name'],
                    meta_title=seo_data.get('meta_title'),
                    meta_description=seo_data.get('meta_description'),
                    h1_titel=seo_data.get('h1_titel'),
                    teaser_text=seo_data.get('teaser_text'),
                    h2_titel_1=seo_data.get('h2_titel_1'),
                    seo_text_1=seo_data.get('seo_text_1'),
                    h2_titel_2=seo_data.get('h2_titel_2'),
                    seo_text_2=seo_data.get('seo_text_2'),
                    faq_json=faq_json_str
                )
                
                db.session.add(new_seo)
                db.session.commit()
                count += 1
            except IntegrityError:
                db.session.rollback()
                skipped += 1
            except Exception as e:
                logging.error(f"DB-Fehler bei {result['stadt_name']}: {e}")
                db.session.rollback()
    
    msg = f"{count} SEO-Texte für {leistung_name} erfolgreich generiert!"
    if skipped > 0:
        msg += f" ({skipped} bereits vorhanden)"
    flash(msg, "success")
    return redirect(f"/admin/leistung-seo-texte?leistung={leistung_slug}")


@app.route("/admin/leistung-seo-texte/regenerieren/<int:seo_id>", methods=["POST"])
@admin_required
def admin_leistung_seo_regenerieren(seo_id):
    """Regeneriert SEO-Texte für eine bestehende Leistung+Stadt Kombination"""
    from models import LeistungStadtSEO
    from services.ai_service import generate_leistung_stadt_seo_texts
    import json as json_lib
    
    seo_entry = LeistungStadtSEO.query.get_or_404(seo_id)
    
    try:
        seo_data = generate_leistung_stadt_seo_texts(seo_entry.leistung_name, seo_entry.leistung_slug, seo_entry.stadt_name)
        faq_json_str = json_lib.dumps(seo_data.get('faq', []), ensure_ascii=False) if seo_data.get('faq') else None
        
        seo_entry.meta_title = seo_data.get('meta_title')
        seo_entry.meta_description = seo_data.get('meta_description')
        seo_entry.h1_titel = seo_data.get('h1_titel')
        seo_entry.teaser_text = seo_data.get('teaser_text')
        seo_entry.h2_titel_1 = seo_data.get('h2_titel_1')
        seo_entry.seo_text_1 = seo_data.get('seo_text_1')
        seo_entry.h2_titel_2 = seo_data.get('h2_titel_2')
        seo_entry.seo_text_2 = seo_data.get('seo_text_2')
        seo_entry.faq_json = faq_json_str
        seo_entry.aktualisiert_am = datetime.utcnow()
        
        db.session.commit()
        flash(f"SEO-Texte für {seo_entry.leistung_name} {seo_entry.stadt_name} erfolgreich regeneriert!", "success")
    except Exception as e:
        flash(f"Fehler bei Regenerierung: {str(e)}", "danger")
    
    return redirect(f"/admin/leistung-seo-texte?leistung={seo_entry.leistung_slug}")


@app.route("/logout")
def logout():
    """Logout für Zahnärzte und Patienten"""
    from flask_login import logout_user
    logout_user()
    session.clear()
    flash("Sie wurden erfolgreich ausgeloggt.", "success")
    return redirect("/")

# Formular zur Einrichtung der Praxisseite nach Zahlung
@app.route("/praxis-einrichten", methods=["GET"])
def praxis_einrichten():
    # Prüfen, ob der Nutzer bereits gezahlt hat
    email = session.get("email")
    
    # Informationen aus der Session für Debugging ausgeben
    session_keys = list(session.keys())
    print(f"🔍 praxis_einrichten - Session Variablen: {session_keys}")
    print(f"🔑 Email in Session: {email}")
    print(f"📦 Paket in Session: {session.get('paket')}")
    print(f"🏥 Praxiseinrichtung Flag: {session.get('praxis_einrichten')}")
    
    # Check für den Stripe-Test-Modus - in diesem Fall Login überspringen
    stripe_test_mode = session.get('stripe_session_id') is not None
    print(f"💳 Stripe Test Mode: {stripe_test_mode}")
    
    # Wenn keine Email in der Session, aber nach Zahlung hier gelandet
    if not email and session.get('praxis_einrichten') and session.get('bezahlung_stammdaten'):
        # Versuche, die Email aus den Bezahlungsdaten zu extrahieren
        email_from_payment = session.get('bezahlung_stammdaten', {}).get('email')
        if email_from_payment:
            print(f"📧 Email aus Bezahlungsdaten wiederhergestellt: {email_from_payment}")
            email = email_from_payment
            session['email'] = email
    
    if not email and not stripe_test_mode:
        flash("Bitte loggen Sie sich zuerst ein.", "warning")
        # Spezieller Parameter, um anzuzeigen, dass der User nach Zahlung zur Praxiseinrichtung soll
        print("⚠️ Keine Email gefunden, Umleitung zum Login mit next=/praxis-einrichten")
        return redirect("/zahnarzt-login?next=/praxis-einrichten")
    
    # Überprüfen, ob ein Paket gebucht wurde oder im Stripe-Test-Modus
    stripe_test_paket = session.get('paket')
    bezahlung_stammdaten = session.get('bezahlung_stammdaten', {})
    
    # Praxisdaten laden (wenn in CSV)
    praxis = {}
    if os.path.isfile("neue_praxen.csv") and email:
        with open("neue_praxen.csv", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("email") == email:
                    praxis = row
                    print(f"📋 Praxisdaten aus CSV gefunden für {email}")
                    break
    
    if praxis.get("paket") in ["Premium", "PremiumPlus"] or stripe_test_mode or session.get('praxis_einrichten'):
        print(f"✅ Praxis hat bezahlt oder ist im Test-Modus. Weiterleitung zur Praxiseinrichtung.")
        print(f"🔍 Session-Daten für Datenbank: {bezahlung_stammdaten}")
        
        # Für Stripe-Test oder nach Bezahlung nutzen wir ggf. Testdaten
        if (stripe_test_mode and stripe_test_paket) or session.get('praxis_einrichten'):
            # Stammdaten aus Bezahlungsprozess in die Session übernehmen, falls verfügbar
            if bezahlung_stammdaten:
                print(f"💾 Bezahlungsdaten werden für Praxiseinrichtung verwendet")
            
            # Test-Praxis nur für Stripe-Test-Modus oder wenn keine Daten vorliegen
            if not praxis and (stripe_test_mode or not bezahlung_stammdaten):
                print("🔄 Verwende Test-Praxisdaten")
                test_praxis = {
                    "name": "Testpraxis Dentalax",
                    "email": email or "test@example.com",
                    "telefon": "030 12345678",
                    "webseite": "www.dentalax.de",
                    "straße": "Teststraße 123",
                    "plz": "10115",
                    "stadt": "Berlin",
                    "paket": stripe_test_paket or "Premium"
                }
                # Mit Daten aus der bezahlung_stammdaten anreichern
                if bezahlung_stammdaten:
                    test_praxis.update(bezahlung_stammdaten)
            
        # Übergabe an DB-basierte Funktion für weiteres Handling
        print("🚀 Weiterleitung zur DB-Version der Praxisdateneinrichtung")
        return redirect("/praxis-daten-eingeben")
    else:
        print("⚠️ Kein kostenpflichtiges Paket gefunden, Umleitung zur Paketwahl")
        flash("Sie müssen ein kostenpflichtiges Paket buchen, um eine eigene Landingpage einzurichten.", "warning")
        return redirect("/paketwahl")

# Speichern der Praxisdaten und Erstellung der Landingpage
@app.route("/praxis-daten-speichern", methods=["POST"])
def praxis_daten_speichern():
    """
    Diese Route dient als Kompatibilitätsschicht für ältere Form-Submissions.
    Sie leitet alle Anfragen an die DB-Version der Funktion weiter.
    """
    print("⚠️ Alte Route '/praxis-daten-speichern' wurde aufgerufen, Umleitung auf DB-Version...")
    
    # Im Falle eines Redirect-Fehlers stellen wir sicher, dass die richtige URL verwendet wird
    form_action = request.form.get('form_action')
    if form_action:
        print(f"📋 Form Action überschrieben: {form_action} -> /praxis-daten-speichern-db")
        # Wenn ein spezifisches Formular-Ziel angegeben wurde, könnten wir es hier anpassen
    
    # Debugging der Formulareinreichung
    form_step = request.form.get('form_step', 'unbekannt')
    final_submit = request.form.get('final_submit', 'nein')
    print(f"📝 Praxisdaten-Weiterleitung - Form Step: {form_step}, Final Submit: {final_submit}")
    print(f"🔑 Session-Email: {session.get('email')}")
    
    # Zur neuen DB-Version weiterleiten
    from db_praxis_route import praxis_daten_speichern_db
    return praxis_daten_speichern_db()
    
    # Praxisdaten aus dem Formular extrahieren
    praxisname = request.form.get("praxisname")
    strasse = request.form.get("strasse")
    plz = request.form.get("plz")
    stadt = request.form.get("stadt")
    telefon = request.form.get("telefon")
    webseite = request.form.get("webseite")
    beschreibung = request.form.get("beschreibung")
    
    # Leistungen aus dem Formular extrahieren
    leistungen = []
    leistung_titel = request.form.getlist("leistung_titel[]")
    leistung_icon = request.form.getlist("leistung_icon[]")
    leistung_beschreibung = request.form.getlist("leistung_beschreibung[]")
    
    for i in range(len(leistung_titel)):
        if leistung_titel[i]:  # Nur hinzufügen, wenn Titel nicht leer ist
            leistungen.append({
                "titel": leistung_titel[i],
                "icon": leistung_icon[i] if i < len(leistung_icon) else "fas fa-tooth",
                "beschreibung": leistung_beschreibung[i] if i < len(leistung_beschreibung) else ""
            })
    
    # Team-Mitglieder aus dem Formular extrahieren
    team = []
    team_name = request.form.getlist("team_name[]")
    team_position = request.form.getlist("team_position[]")
    team_beschreibung = request.form.getlist("team_beschreibung[]")
    
    for i in range(len(team_name)):
        if team_name[i]:  # Nur hinzufügen, wenn Name nicht leer ist
            team.append({
                "name": team_name[i],
                "position": team_position[i] if i < len(team_position) else "",
                "beschreibung": team_beschreibung[i] if i < len(team_beschreibung) else "",
                "foto": None  # Foto-Handling würde hier erfolgen
            })
    
    # Öffnungszeiten aus dem Formular extrahieren
    oeffnungszeiten = {}
    for tag in ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']:
        geschlossen = 'tag_' + tag + '_geschlossen' in request.form
        von = request.form.get('tag_' + tag + '_von')
        bis = request.form.get('tag_' + tag + '_bis')
        
        oeffnungszeiten[tag.capitalize()] = {
            "geschlossen": geschlossen,
            "von": von if not geschlossen else "",
            "bis": bis if not geschlossen else ""
        }
    
    # Schwerpunkte extrahieren
    schwerpunkte_str = request.form.get("schwerpunkte", "")
    schwerpunkte = [s.strip() for s in schwerpunkte_str.split(",") if s.strip()]
    
    # FAQs extrahieren
    faqs = []
    faq_frage = request.form.getlist("faq_frage[]")
    faq_antwort = request.form.getlist("faq_antwort[]")
    
    for i in range(len(faq_frage)):
        if faq_frage[i]:  # Nur hinzufügen, wenn Frage nicht leer ist
            faqs.append({
                "frage": faq_frage[i],
                "antwort": faq_antwort[i] if i < len(faq_antwort) else ""
            })
    
    # Social Media Links
    social_media = {
        "facebook": request.form.get("facebook", ""),
        "instagram": request.form.get("instagram", "")
    }
    
    # Speicherverzeichnis für Uploads erstellen, falls es noch nicht existiert
    uploads_dir = os.path.join('static', 'uploads', email.replace('@', '_').replace('.', '_'))
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Praxisdaten in einer JSON-Datei speichern
    praxis_data = {
        "name": praxisname,
        "strasse": strasse,
        "plz": plz,
        "stadt": stadt,
        "telefon": telefon,
        "email": email,
        "webseite": webseite,
        "beschreibung": beschreibung,
        "oeffnungszeiten": oeffnungszeiten,
        "leistungen": leistungen,
        "team": team,
        "schwerpunkte": schwerpunkte,
        "faqs": faqs,
        "social_media": social_media,
        "bewertung": 4.5,  # Beispielwert
        "bewertung_anzahl": 12,  # Beispielwert
        "bewertungen": [
            {"name": "Max Mustermann", "sterne": 5, "text": "Sehr freundliche und kompetente Behandlung!", "datum": "15.03.2025"},
            {"name": "Anna Schmidt", "sterne": 4, "text": "Tolle Praxis mit moderner Ausstattung.", "datum": "02.04.2025"}
        ]
    }
    
    # Praxisdaten in JSON speichern
    with open(os.path.join(uploads_dir, 'praxis_data.json'), 'w', encoding='utf-8') as f:
        json.dump(praxis_data, f, ensure_ascii=False, indent=2)
    
    # Praxisdaten in der CSV-Datei aktualisieren
    if os.path.isfile("neue_praxen.csv"):
        eintraege = []
        
        with open("neue_praxen.csv", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("email") == email:
                    row["name"] = praxisname
                    row["telefon"] = telefon
                    row["webseite"] = webseite
                    row["straße"] = strasse
                    row["plz"] = plz
                    row["stadt"] = stadt
                    row["praxis_data"] = "gespeichert"
                eintraege.append(row)
        
        with open("neue_praxen.csv", "w", newline='', encoding='utf-8') as f:
            fieldnames = eintraege[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(eintraege)
    
    flash("Ihre Praxisdaten wurden erfolgreich gespeichert. Ihre individuelle Landingpage wurde erstellt!", "success")
    return redirect(f"/zahnarzt/{slugify(praxisname)}")

# Hilfsfunktion zum Erstellen von URL-slugs
def slugify(text):
    # Prüfen auf leere Eingabe
    if not text:
        return "praxis"
        
    # Umlaute und Sonderzeichen ersetzen
    text = str(text).lower()
    text = text.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    
    # Alle nicht-alphanumerischen Zeichen durch Bindestriche ersetzen
    import re
    text = re.sub(r'[^a-z0-9]+', '-', text)
    
    # Führende/nachfolgende Bindestriche entfernen
    text = text.strip('-')
    
    # Sicherstellen, dass der Slug nicht leer ist
    if not text:
        return "praxis"
        
    return text


@app.route("/fuer-zahnaerzte")
def fuer_zahnaerzte():
    return render_template("fuer-zahnaerzte.html")

@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")

@app.route("/impressum")
def impressum():
    return render_template("impressum.html")

@app.route("/agb")
def agb():
    return render_template("agb.html")

@app.route("/praxis/<slug>/bewertung", methods=["POST"])
def bewertung_abgeben(slug):
    import secrets as secrets_mod
    praxis = Praxis.query.filter_by(slug=slug).first()
    if not praxis:
        flash("Praxis nicht gefunden.", "danger")
        return redirect("/")
    
    name = request.form.get("name", "").strip() or "Anonym"
    email = request.form.get("email", "").strip().lower()
    bewertung_wert = request.form.get("bewertung", 0, type=int)
    text = request.form.get("text", "").strip()
    dsgvo_consent = request.form.get("dsgvo_consent")
    
    if not email:
        flash("Bitte geben Sie Ihre E-Mail-Adresse an.", "danger")
        return redirect(f"/praxis/{slug}#bewertungen")
    
    if not text:
        flash("Bitte geben Sie einen Bewertungstext ein.", "danger")
        return redirect(f"/praxis/{slug}#bewertungen")
    
    if bewertung_wert < 1 or bewertung_wert > 5:
        flash("Bitte wählen Sie eine Sternebewertung (1-5).", "danger")
        return redirect(f"/praxis/{slug}#bewertungen")
    
    if not dsgvo_consent:
        flash("Bitte stimmen Sie der Datenschutzerklärung zu, um Ihre Bewertung abzusenden.", "danger")
        return redirect(f"/praxis/{slug}#bewertungen")
    
    bestehende = Bewertung.query.filter_by(praxis_id=praxis.id, email=email).first()
    if bestehende:
        flash("Sie haben diese Praxis bereits bewertet. Pro E-Mail-Adresse ist nur eine Bewertung pro Praxis möglich.", "info")
        return redirect(f"/praxis/{slug}#bewertungen")
    
    token = secrets_mod.token_urlsafe(32)
    
    neue_bewertung = Bewertung(
        name=name,
        email=email,
        bewertung=bewertung_wert,
        sterne=bewertung_wert,
        text=text,
        praxis_id=praxis.id,
        status='ausstehend',
        bestaetigt=False,
        bestaetigungs_token=token
    )
    db.session.add(neue_bewertung)
    db.session.commit()
    
    bestaetigungs_url = url_for('bewertung_bestaetigen', token=token, _external=True)

    from services.email_service import send_bewertung_bestaetigung
    email_sent = send_bewertung_bestaetigung(email, praxis.name, bestaetigungs_url)

    if email_sent:
        flash("Vielen Dank für Ihre Bewertung! Bitte überprüfen Sie Ihr E-Mail-Postfach und klicken Sie auf den Bestätigungslink, um Ihre Bewertung zu veröffentlichen.", "success")
    else:
        flash("Vielen Dank für Ihre Bewertung! Es gab ein Problem beim E-Mail-Versand. Bitte versuchen Sie es später erneut.", "warning")
    return redirect(f"/praxis/{slug}#bewertungen")

@app.route("/bewertung-bestaetigen/<token>")
def bewertung_bestaetigen(token):
    bewertung = Bewertung.query.filter_by(bestaetigungs_token=token).first()
    if not bewertung:
        flash("Ungültiger oder bereits verwendeter Bestätigungslink.", "danger")
        return redirect("/")
    
    bewertung.bestaetigt = True
    bewertung.status = 'freigegeben'
    bewertung.bestaetigungs_token = None
    db.session.commit()
    
    praxis = Praxis.query.get(bewertung.praxis_id)
    slug = praxis.slug if praxis else ""
    
    flash("Ihre Bewertung wurde erfolgreich bestätigt und veröffentlicht. Vielen Dank!", "success")
    return redirect(f"/praxis/{slug}#bewertungen" if slug else "/")

def _get_sitemap_stadt_set():
    stadt_set = set()
    with open("zahnaerzte.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stadt = row.get("stadt", "").strip().lower().replace(" ", "-")
            if stadt:
                stadt_set.add(stadt)
    return stadt_set

def _build_sitemap_xml(urls):
    from xml.dom import minidom
    import xml.etree.ElementTree as ET
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for loc, priority, changefreq in urls:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = loc
        ET.SubElement(url, "changefreq").text = changefreq
        ET.SubElement(url, "priority").text = priority
    rough = ET.tostring(urlset, encoding="unicode", method="xml")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ", encoding="utf-8")

LEISTUNG_SLUGS_SITEMAP = ['implantologie', 'kieferorthopaedie', 'prophylaxe', 'parodontologie',
                           'wurzelbehandlung', 'zahnersatz', 'aesthetik', 'kinderzahnheilkunde',
                           'oralchirurgie', 'angstpatienten']

@app.route("/sitemap.xml")
def sitemap_index():
    from flask import Response
    from xml.dom import minidom
    import xml.etree.ElementTree as ET

    domain = "https://dentalax.de"

    sitemapindex = ET.Element("sitemapindex", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    sitemap_files = [
        f"{domain}/sitemap-main.xml",
        f"{domain}/sitemap-staedte.xml",
    ]
    for leistung in LEISTUNG_SLUGS_SITEMAP:
        sitemap_files.append(f"{domain}/sitemap-{leistung}.xml")
    sitemap_files.append(f"{domain}/sitemap-jobs.xml")

    for loc in sitemap_files:
        sitemap_el = ET.SubElement(sitemapindex, "sitemap")
        ET.SubElement(sitemap_el, "loc").text = loc

    rough = ET.tostring(sitemapindex, encoding="unicode", method="xml")
    parsed = minidom.parseString(rough)
    xml_data = parsed.toprettyxml(indent="  ", encoding="utf-8")
    return Response(xml_data, content_type="application/xml; charset=utf-8")

@app.route("/sitemap-main.xml")
def sitemap_main():
    from flask import Response
    domain = "https://dentalax.de"
    urls = [
        (f"{domain}/", "1.0", "daily"),
        (f"{domain}/fuer-zahnaerzte", "0.8", "weekly"),
        (f"{domain}/kontakt", "0.6", "monthly"),
        (f"{domain}/paketwahl", "0.8", "weekly"),
        (f"{domain}/stellenangebote", "0.9", "daily"),
        (f"{domain}/stellenangebote-nach-staedten", "0.7", "weekly"),
        (f"{domain}/zahnaerzte-nach-staedten", "0.8", "weekly"),
        (f"{domain}/leistungen-uebersicht", "0.8", "weekly"),
    ]
    for leistung in LEISTUNG_SLUGS_SITEMAP:
        urls.append((f"{domain}/{leistung}-nach-staedten", "0.8", "weekly"))
    return Response(_build_sitemap_xml(urls), content_type="application/xml; charset=utf-8")

@app.route("/sitemap-staedte.xml")
def sitemap_staedte():
    from flask import Response
    domain = "https://dentalax.de"
    stadt_set = _get_sitemap_stadt_set()
    urls = [(f"{domain}/zahnarzt-{stadt}", "0.8", "weekly") for stadt in sorted(stadt_set)]
    return Response(_build_sitemap_xml(urls), content_type="application/xml; charset=utf-8")

@app.route("/sitemap-<leistung_slug>.xml")
def sitemap_leistung(leistung_slug):
    from flask import Response, abort
    if leistung_slug not in LEISTUNG_SLUGS_SITEMAP:
        abort(404)
    domain = "https://dentalax.de"
    stadt_set = _get_sitemap_stadt_set()
    urls = [(f"{domain}/{leistung_slug}-{stadt}", "0.7", "weekly") for stadt in sorted(stadt_set)]
    return Response(_build_sitemap_xml(urls), content_type="application/xml; charset=utf-8")

@app.route("/sitemap-jobs.xml")
def sitemap_jobs():
    from flask import Response
    domain = "https://dentalax.de"
    urls = []
    stellenangebote = Stellenangebot.query.filter_by(ist_aktiv=True).all()
    for job in stellenangebote:
        urls.append((f"{domain}/stellenangebot/{job.slug}", "0.9", "daily"))
    job_staedte = ['berlin', 'muenchen', 'hamburg', 'koeln', 'frankfurt', 'duesseldorf',
                   'stuttgart', 'dortmund', 'essen', 'leipzig', 'bremen', 'dresden',
                   'hannover', 'nuernberg']
    for stadt in job_staedte:
        urls.append((f"{domain}/stellenangebote/{stadt}", "0.7", "weekly"))
    job_kategorien = ['zfa', 'zmf', 'zahnarzt', 'dh', 'zahntechniker', 'praxismanager']
    for kategorie in job_kategorien:
        for stadt in job_staedte:
            urls.append((f"{domain}/stellenangebote/{kategorie}/{stadt}", "0.6", "weekly"))
    return Response(_build_sitemap_xml(urls), content_type="application/xml; charset=utf-8")

@app.route("/zahnaerzte-nach-staedten")
def zahnaerzte_nach_städten():
    staedte = [
        "Berlin", "Hamburg", "München", "Köln", "Frankfurt", "Düsseldorf", "Stuttgart",
        "Leipzig", "Dortmund", "Bremen", "Essen", "Dresden", "Nürnberg", "Hannover",
        "Duisburg", "Wuppertal", "Bochum", "Bielefeld", "Bonn", "Mannheim", "Karlsruhe",
        "Münster", "Augsburg", "Wiesbaden", "Mönchengladbach", "Gelsenkirchen", "Aachen",
        "Braunschweig", "Kiel", "Chemnitz", "Magdeburg", "Freiburg", "Krefeld", "Halle",
        "Mainz", "Lübeck", "Erfurt", "Oberhausen", "Rostock", "Kassel", "Hagen",
        "Potsdam", "Saarbrücken", "Hamm", "Oldenburg", "Ludwigshafen", "Mülheim",
        "Leverkusen", "Solingen", "Osnabrück", "Darmstadt", "Regensburg", "Paderborn",
        "Herne", "Heidelberg", "Neuss", "Ingolstadt", "Pforzheim", "Fürth", "Offenbach",
        "Heilbronn", "Wolfsburg", "Ulm", "Würzburg", "Göttingen", "Bottrop", "Reutlingen",
        "Bremerhaven", "Erlangen", "Recklinghausen", "Koblenz", "Remscheid", "Trier",
        "Bergisch Gladbach", "Jena", "Salzgitter", "Siegen", "Moers", "Kaiserslautern",
        "Gütersloh", "Schwerin", "Hildesheim", "Hanau", "Esslingen", "Flensburg",
        "Gera", "Cottbus", "Düren", "Witten", "Iserlohn", "Tübingen",
        "Villingen-Schwenningen", "Gießen", "Ratingen", "Zwickau", "Konstanz", "Marl",
        "Lünen", "Worms"
    ]
    return render_template("zahnaerzte_nach_staedten.html", staedte=staedte)


# =============== LEISTUNGS-SEO-ROUTEN ===============
from leistungen_config import LEISTUNGEN, SEO_STAEDTE, stadt_zu_slug, slug_zu_stadt, get_leistung_seo

@app.route("/<path:full_slug>")
def seo_leistung_stadt(full_slug):
    """SEO-Route für Leistung + Stadt Kombination, z.B. /implantologie-berlin oder /implantologie-aarbergen-kettenbach"""
    from models import Praxis, LeistungStadtSEO
    import json
    
    # Parse: Finde bekannte Leistung am Anfang, Rest ist stadt_slug
    leistung_slug = None
    stadt_slug = None
    
    for known_leistung in LEISTUNGEN.keys():
        prefix = known_leistung + "-"
        if full_slug.startswith(prefix):
            leistung_slug = known_leistung
            stadt_slug = full_slug[len(prefix):]
            break
    
    # Prüfen ob Leistung gefunden wurde
    if not leistung_slug or not stadt_slug:
        return redirect(url_for('index'))
    
    stadt = slug_zu_stadt(stadt_slug)
    seo = get_leistung_seo(leistung_slug, stadt)
    
    # KI-generierte SEO-Texte aus Datenbank laden
    leistung_seo = LeistungStadtSEO.query.filter_by(
        leistung_slug=leistung_slug,
        stadt_slug=stadt_slug
    ).first()
    
    umkreis = float(request.args.get("umkreis", 25))
    seite = 1
    eintraege_pro_seite = 20
    
    lat, lng = get_coordinates_from_address(stadt)
    
    if not lat or not lng:
        flash('Der Ort konnte nicht gefunden werden.', 'warning')
        return redirect(url_for('index'))
    
    alle_praxen = lade_praxen("zahnaerzte.csv")
    
    # Datenbank-Praxen hinzufügen
    db_praxen = Praxis.query.all()
    for praxis in db_praxen:
        if praxis.latitude and praxis.longitude:
            alle_praxen.append({
                'id': praxis.id,
                'name': praxis.name,
                'email': praxis.email or '',
                'telefon': praxis.telefon or '',
                'webseite': praxis.webseite or '',
                'plz': praxis.plz or '',
                'stadt': praxis.stadt or '',
                'straße': praxis.strasse or '',
                'lat': float(praxis.latitude),
                'lng': float(praxis.longitude),
                'slug': praxis.slug,
                'aus_datenbank': True,
                'paket': praxis.paket,
                'beansprucht': 'ja' if praxis.ist_verifiziert else 'nein',
                'leistungsschwerpunkte': praxis.leistungsschwerpunkte or ''
            })
    
    gefilterte_praxen = []
    for praxis in alle_praxen:
        distanz = entfernung_km(lat, lng, praxis['lat'], praxis['lng'])
        if distanz <= umkreis:
            praxis['entfernung'] = distanz
            gefilterte_praxen.append(praxis)
    
    # Hilfsfunktion: Prüft ob Praxis die gesuchte Leistung anbietet
    def hat_leistung(praxis, leistung):
        schwerpunkte = praxis.get('leistungsschwerpunkte', '') or ''
        return leistung in schwerpunkte.lower()
    
    # Premium-Praxen zuerst, dann nach Entfernung
    premium_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() in ('premium', 'premiumplus')]
    standard_praxen = [p for p in gefilterte_praxen if p.get('paket', '').lower() not in ('premium', 'premiumplus')]
    
    # Innerhalb Premium: Praxen mit passender Leistung zuerst
    premium_mit_leistung = [p for p in premium_praxen if hat_leistung(p, leistung_slug)]
    premium_ohne_leistung = [p for p in premium_praxen if not hat_leistung(p, leistung_slug)]
    
    # Innerhalb Standard: Praxen mit passender Leistung zuerst
    standard_mit_leistung = [p for p in standard_praxen if hat_leistung(p, leistung_slug)]
    standard_ohne_leistung = [p for p in standard_praxen if not hat_leistung(p, leistung_slug)]
    
    import hashlib
    heute = datetime.now().strftime('%Y-%m-%d')
    hash_input = f"{heute}-{stadt.lower()}-{leistung_slug}".encode('utf-8')
    rotation_seed = int(hashlib.sha256(hash_input).hexdigest(), 16) % (2**32)
    rng = Random(rotation_seed)
    rng.shuffle(premium_mit_leistung)
    rng.shuffle(premium_ohne_leistung)
    
    standard_mit_leistung.sort(key=lambda p: p['entfernung'])
    standard_ohne_leistung.sort(key=lambda p: p['entfernung'])
    
    # Reihenfolge: Premium mit Leistung > Premium ohne > Standard mit > Standard ohne
    gefilterte_praxen = premium_mit_leistung + premium_ohne_leistung + standard_mit_leistung + standard_ohne_leistung
    
    ergebnisse = gefilterte_praxen[:eintraege_pro_seite]
    gesamt_seiten = math.ceil(len(gefilterte_praxen) / eintraege_pro_seite)
    
    # Template-Variablen vorbereiten - KI-generierte Texte bevorzugen
    template_vars = {
        'ort': stadt,
        'behandlung': None,
        'umkreis': umkreis,
        'ergebnisse': ergebnisse,
        'seite': seite,
        'gesamt_seiten': gesamt_seiten,
        'selected_leistungen': [leistung_slug],
        'seo_route': True,
        'leistung_seo_route': True,
        'meta_title': seo['meta_title'],
        'meta_description': seo['meta_description'],
        'seo_h1': seo['h1'],
        'seo_intro': seo['intro'],
        'seo_footer': seo['footer'],
        'seo_h2': seo['h2'],
        'leistung_name': seo['name'],
        'max': max,
        'min': min
    }
    
    # Interne Verlinkung: Verwandte Städte für Leistung+Stadt finden
    leistung_hauptstadt = None
    leistung_vororte = []

    # Erst prüfen ob es Vororte gibt (diesen Slug als Hauptstadt)
    vororte_query = LeistungStadtSEO.query.filter(
        LeistungStadtSEO.leistung_slug == leistung_slug,
        LeistungStadtSEO.stadt_slug.like(f"{stadt_slug}-%")
    ).order_by(LeistungStadtSEO.stadt_name).limit(15).all()
    leistung_vororte = [
        {'name': v.stadt_name, 'slug': v.stadt_slug, 'leistung_slug': leistung_slug}
        for v in vororte_query
    ]

    # Falls keine Vororte gefunden und der Slug Bindestriche enthält,
    # versuche schrittweise eine übergeordnete Stadt zu finden
    if not leistung_vororte and '-' in stadt_slug:
        parts = stadt_slug.split('-')
        for i in range(len(parts) - 1, 0, -1):
            candidate_slug = '-'.join(parts[:i])
            hauptstadt_seo = LeistungStadtSEO.query.filter_by(
                leistung_slug=leistung_slug,
                stadt_slug=candidate_slug
            ).first()
            if hauptstadt_seo:
                leistung_hauptstadt = {
                    'name': hauptstadt_seo.stadt_name,
                    'slug': hauptstadt_seo.stadt_slug,
                    'leistung_slug': leistung_slug
                }
                break

    template_vars['leistung_hauptstadt'] = leistung_hauptstadt
    template_vars['leistung_vororte'] = leistung_vororte
    template_vars['canonical_url'] = request.url_root.rstrip('/') + '/' + full_slug

    # KI-generierte Texte aus Datenbank überschreiben (falls vorhanden)
    if leistung_seo:
        if leistung_seo.meta_title:
            template_vars['meta_title'] = leistung_seo.meta_title
        if leistung_seo.meta_description:
            template_vars['meta_description'] = leistung_seo.meta_description
        if leistung_seo.h1_titel:
            template_vars['seo_h1'] = leistung_seo.h1_titel
        if leistung_seo.teaser_text:
            template_vars['seo_intro'] = leistung_seo.teaser_text
        if leistung_seo.h2_titel_1:
            template_vars['leistung_h2_titel_1'] = leistung_seo.h2_titel_1
        if leistung_seo.seo_text_1:
            template_vars['leistung_seo_text_1'] = leistung_seo.seo_text_1
        if leistung_seo.h2_titel_2:
            template_vars['leistung_h2_titel_2'] = leistung_seo.h2_titel_2
        if leistung_seo.seo_text_2:
            template_vars['leistung_seo_text_2'] = leistung_seo.seo_text_2
        if leistung_seo.faq_json:
            try:
                faq_list = json.loads(leistung_seo.faq_json)
                template_vars['leistung_faq'] = faq_list
                faq_schema = {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": item.get('frage', ''),
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": item.get('antwort', '')
                            }
                        } for item in faq_list
                    ]
                }
                template_vars['leistung_faq_schema_json'] = json.dumps(faq_schema, ensure_ascii=False)
            except:
                template_vars['leistung_faq'] = []
    
    return render_template("suche.html", **template_vars)

@app.route("/<leistung_slug>-nach-staedten")
def seo_leistung_staedte_uebersicht(leistung_slug):
    """Übersichtsseite für eine Leistung in allen Städten, z.B. /implantologie-nach-staedten"""
    
    # Prüfen ob Leistung existiert
    if leistung_slug not in LEISTUNGEN:
        return redirect(url_for('index'))
    
    leistung = LEISTUNGEN[leistung_slug]
    
    return render_template(
        "leistung_nach_staedten.html",
        leistung=leistung,
        leistung_slug=leistung_slug,
        staedte=SEO_STAEDTE,
        stadt_zu_slug=stadt_zu_slug,
        active_page='zahnaerzte'
    )

@app.route("/leistungen-uebersicht")
def leistungen_uebersicht():
    """Übersicht aller Leistungskategorien"""
    return render_template(
        "leistungen_uebersicht.html",
        leistungen=LEISTUNGEN,
        active_page='zahnaerzte'
    )


@app.route("/stellenangebote-nach-staedten")
def stellenangebote_nach_staedten():
    """Übersicht aller Städte mit Dental-Stellenangeboten"""
    staedte = [
        "Berlin", "Hamburg", "München", "Köln", "Frankfurt", "Düsseldorf", "Stuttgart",
        "Leipzig", "Dortmund", "Bremen", "Essen", "Dresden", "Nürnberg", "Hannover",
        "Duisburg", "Wuppertal", "Bochum", "Bielefeld", "Bonn", "Mannheim", "Karlsruhe",
        "Münster", "Augsburg", "Wiesbaden", "Aachen", "Braunschweig", "Kiel", "Chemnitz",
        "Magdeburg", "Freiburg", "Mainz", "Erfurt", "Rostock", "Kassel", "Potsdam",
        "Saarbrücken", "Oldenburg", "Darmstadt", "Regensburg", "Paderborn", "Heidelberg",
        "Ingolstadt", "Ulm", "Würzburg", "Göttingen", "Reutlingen", "Erlangen", "Koblenz",
        "Trier", "Jena", "Siegen", "Kaiserslautern", "Schwerin", "Hildesheim", "Flensburg",
        "Tübingen", "Konstanz"
    ]
    
    stadt_slugs = []
    for stadt in staedte:
        slug = stadt.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss').replace(' ', '-')
        stadt_slugs.append(slug)
    
    total_jobs = Stellenangebot.query.filter_by(ist_aktiv=True).count() + ExternesInserat.query.filter_by(ist_aktiv=True).count()
    
    return render_template("stellenangebote_nach_staedten.html", 
                          staedte=staedte, 
                          stadt_slugs=stadt_slugs,
                          total_jobs=total_jobs,
                          active_page='stellenangebote')


@app.route("/stellenangebote")
def stellenangebote():
    """Stellenangebote-Übersichtsseite für Jobsuchende"""
    query = request.args.get('query', '')
    position = request.args.get('position', '')
    ort = request.args.get('ort', '')
    umkreis_str = request.args.get('umkreis', '25')
    sortierung = request.args.get('sortierung', 'neuste')
    ansicht = request.args.get('ansicht', 'liste')
    
    # Paginierung
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1
    per_page = 15
    
    try:
        umkreis = float(umkreis_str)
    except ValueError:
        umkreis = 25.0
    
    anstellungsarten = []
    if request.args.get('vollzeit') == 'on':
        anstellungsarten.append('vollzeit')
    if request.args.get('teilzeit') == 'on':
        anstellungsarten.append('teilzeit')
    if request.args.get('ausbildung') == 'on':
        anstellungsarten.append('ausbildung')
    
    from sqlalchemy import or_
    
    # Premium Jobs (Dentalax Inserate)
    jobs_query = Stellenangebot.query.filter_by(ist_aktiv=True)
    
    if query:
        jobs_query = jobs_query.filter(
            or_(
                Stellenangebot.titel.ilike(f'%{query}%'),
                Stellenangebot.position.ilike(f'%{query}%'),
                Stellenangebot.tags.ilike(f'%{query}%')
            )
        )
    
    if position:
        jobs_query = jobs_query.filter(Stellenangebot.position == position)
    
    if anstellungsarten:
        jobs_query = jobs_query.filter(Stellenangebot.anstellungsart.in_(anstellungsarten))
    
    all_premium_jobs = jobs_query.order_by(Stellenangebot.ist_premium.desc(), Stellenangebot.erstellt_am.desc()).all()
    
    # Externe Jobs von TheirStack
    externe_query = ExternesInserat.query.filter_by(ist_aktiv=True)
    
    if query:
        externe_query = externe_query.filter(
            or_(
                ExternesInserat.titel.ilike(f'%{query}%'),
                ExternesInserat.unternehmen.ilike(f'%{query}%'),
                ExternesInserat.beschreibung.ilike(f'%{query}%')
            )
        )
    
    if position:
        externe_query = externe_query.filter(ExternesInserat.position_kategorie == position)
    
    if anstellungsarten:
        externe_query = externe_query.filter(ExternesInserat.anstellungsart.in_(anstellungsarten))
    
    all_externe_jobs = externe_query.order_by(ExternesInserat.veroeffentlicht_am.desc()).all()
    
    # Standortfilter anwenden
    if ort:
        lat, lng = get_coordinates_from_address(ort)
        if lat and lng:
            # Premium Jobs filtern
            premium_jobs = []
            for job in all_premium_jobs:
                praxis = job.praxis
                if praxis and praxis.latitude and praxis.longitude:
                    try:
                        distanz = entfernung_km(lat, lng, float(praxis.latitude), float(praxis.longitude))
                        if distanz <= umkreis:
                            job.distanz = round(distanz, 1)
                            job.ist_extern = False
                            premium_jobs.append(job)
                    except (TypeError, ValueError):
                        pass
            premium_jobs.sort(key=lambda x: (not x.ist_premium, getattr(x, 'distanz', 999)))
            
            # Externe Jobs filtern
            externe_jobs = []
            for job in all_externe_jobs:
                if job.latitude and job.longitude:
                    try:
                        distanz = entfernung_km(lat, lng, float(job.latitude), float(job.longitude))
                        if distanz <= umkreis:
                            job.distanz = round(distanz, 1)
                            job.ist_extern = True
                            externe_jobs.append(job)
                    except (TypeError, ValueError):
                        pass
                elif ort.lower() in (job.standort_stadt or '').lower():
                    job.distanz = None
                    job.ist_extern = True
                    externe_jobs.append(job)
        else:
            premium_jobs = [j for j in all_premium_jobs if ort.lower() in (j.standort_stadt or '').lower() or (j.standort_plz or '').startswith(ort)]
            for j in premium_jobs:
                j.ist_extern = False
            externe_jobs = [j for j in all_externe_jobs if ort.lower() in (j.standort_stadt or '').lower()]
            for j in externe_jobs:
                j.ist_extern = True
    else:
        premium_jobs = all_premium_jobs
        for j in premium_jobs:
            j.ist_extern = False
        externe_jobs = all_externe_jobs
        for j in externe_jobs:
            j.ist_extern = True
    
    # Sortierung anwenden
    if sortierung == 'naechste' and ort:
        # Sortiere nach Distanz (nur wenn Ort angegeben)
        premium_jobs.sort(key=lambda x: (getattr(x, 'distanz', 999) or 999))
        externe_jobs.sort(key=lambda x: (getattr(x, 'distanz', 999) or 999))
    elif sortierung == 'relevanz':
        # Sortiere nach Premium-Status und Suchrelevanz
        premium_jobs.sort(key=lambda x: (not x.ist_premium, -(x.id or 0)))
    # Default: neuste zuerst (bereits so sortiert)
    
    # Premium Jobs zuerst, dann externe Jobs
    all_jobs = premium_jobs + externe_jobs
    total_jobs = len(all_jobs)
    
    # Paginierung anwenden
    total_pages = max(1, (total_jobs + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    jobs = all_jobs[start_idx:end_idx]
    
    meta_title = "Stellenangebote in Zahnarztpraxen | Dentalax"
    meta_description = "Finden Sie Ihren nächsten Job in der Zahnmedizin. Zahlreiche Stellenangebote für ZFAs, ZMPs, Zahntechniker und Zahnärzte in ganz Deutschland."
    
    if ort:
        meta_title = f"Stellenangebote Zahnarzt {ort} | Dentalax"
        meta_description = f"Aktuelle Stellenangebote für Zahnmedizinische Fachangestellte und Zahnärzte in {ort}. Jetzt bewerben!"
    
    vollzeit_checked = 'vollzeit' in anstellungsarten
    teilzeit_checked = 'teilzeit' in anstellungsarten
    ausbildung_checked = 'ausbildung' in anstellungsarten
    
    # Städte mit Jobs für SEO-Links
    staedte_mit_jobs = get_cities_with_jobs()
    
    return render_template('stellenangebote.html', 
                          active_page='stellenangebote',
                          jobs=jobs,
                          premium_count=len(premium_jobs),
                          extern_count=len(externe_jobs),
                          total_jobs=total_jobs,
                          page=page,
                          per_page=per_page,
                          total_pages=total_pages,
                          query=query,
                          position=position,
                          ort=ort,
                          umkreis=umkreis,
                          sortierung=sortierung,
                          ansicht=ansicht,
                          vollzeit_checked=vollzeit_checked,
                          teilzeit_checked=teilzeit_checked,
                          ausbildung_checked=ausbildung_checked,
                          staedte_mit_jobs=staedte_mit_jobs[:10],
                          meta_title=meta_title,
                          meta_description=meta_description)


STADT_MAPPING = {
    'berlin': 'Berlin',
    'muenchen': 'München',
    'hamburg': 'Hamburg',
    'koeln': 'Köln',
    'frankfurt': 'Frankfurt am Main',
    'duesseldorf': 'Düsseldorf',
    'stuttgart': 'Stuttgart',
    'dortmund': 'Dortmund',
    'essen': 'Essen',
    'leipzig': 'Leipzig',
    'bremen': 'Bremen',
    'dresden': 'Dresden',
    'hannover': 'Hannover',
    'nuernberg': 'Nürnberg',
    'duisburg': 'Duisburg',
    'bochum': 'Bochum',
    'wuppertal': 'Wuppertal',
    'bonn': 'Bonn',
    'bielefeld': 'Bielefeld',
    'mannheim': 'Mannheim',
    'karlsruhe': 'Karlsruhe',
    'wiesbaden': 'Wiesbaden',
    'mainz': 'Mainz',
    'augsburg': 'Augsburg',
    'aachen': 'Aachen',
    'freiburg': 'Freiburg',
    'muenster': 'Münster',
    'darmstadt': 'Darmstadt',
}


@app.route("/stellenangebote/<stadt_slug>")
def stellenangebote_stadt(stadt_slug):
    """SEO-Landingpage für Stellenangebote nach Stadt"""
    stadt = STADT_MAPPING.get(stadt_slug.lower())
    if not stadt:
        stadt = stadt_slug.replace('-', ' ').title()
    
    lat, lng = get_coordinates_from_address(stadt)
    umkreis = 25
    
    premium_jobs = Stellenangebot.query.filter_by(ist_aktiv=True).all()
    externe_jobs = ExternesInserat.query.filter_by(ist_aktiv=True).all()
    
    if lat and lng:
        def filter_by_distance(job, is_extern=False):
            if is_extern:
                job_lat = job.latitude
                job_lng = job.longitude
            else:
                if job.praxis:
                    job_lat = job.praxis.latitude
                    job_lng = job.praxis.longitude
                else:
                    return False
            if job_lat and job_lng:
                dist = entfernung_km(lat, lng, job_lat, job_lng)
                return dist <= umkreis
            if is_extern and job.standort_stadt:
                return stadt.lower() in job.standort_stadt.lower()
            if not is_extern and job.standort_stadt:
                return stadt.lower() in job.standort_stadt.lower()
            return False
        
        premium_jobs = [j for j in premium_jobs if filter_by_distance(j, False)]
        externe_jobs = [j for j in externe_jobs if filter_by_distance(j, True)]
    
    for job in premium_jobs:
        job.ist_extern = False
    for job in externe_jobs:
        job.ist_extern = True
    
    premium_jobs.sort(key=lambda x: x.erstellt_am or datetime.min, reverse=True)
    externe_jobs.sort(key=lambda x: x.veroeffentlicht_am or datetime.min, reverse=True)
    
    alle_jobs = premium_jobs + externe_jobs
    total_jobs = len(alle_jobs)
    
    meta_title = f"Dental Jobs in {stadt} | Stellenangebote Zahnmedizin | Dentalax"
    meta_description = f"Aktuelle Stellenangebote in der Zahnmedizin in {stadt}. Finden Sie Jobs als ZFA, Zahnarzt, Dentalhygieniker und mehr bei Top-Arbeitgebern."
    
    jobs = alle_jobs[:15]
    
    return render_template('stellenangebote.html',
                          active_page='stellenangebote',
                          jobs=jobs,
                          premium_count=len(premium_jobs),
                          extern_count=len(externe_jobs),
                          total_jobs=total_jobs,
                          page=1,
                          per_page=15,
                          total_pages=math.ceil(total_jobs / 15) if total_jobs > 0 else 1,
                          query='',
                          position='',
                          ort=stadt,
                          umkreis=umkreis,
                          sortierung='neuste',
                          ansicht='liste',
                          vollzeit_checked=False,
                          teilzeit_checked=False,
                          ausbildung_checked=False,
                          staedte_mit_jobs=[],
                          meta_title=meta_title,
                          meta_description=meta_description,
                          seo_route=True,
                          seo_h1=seo_job_h1(stadt),
                          seo_intro=seo_job_intro(stadt),
                          seo_h2=seo_job_h2(stadt),
                          seo_footer=seo_job_footer(stadt),
                          stadt_name=stadt,
                          stadt_slug=stadt_slug)


@app.route("/stellenangebote/<kategorie_slug>/<stadt_slug>")
def stellenangebote_kategorie_stadt(kategorie_slug, stadt_slug):
    """SEO-Landingpage für Kategorie + Stadt (z.B. ZFA Jobs in Berlin)"""
    if kategorie_slug not in KATEGORIE_MAPPING:
        return redirect(url_for('stellenangebote'))
    
    stadt = STADT_MAPPING.get(stadt_slug.lower())
    if not stadt:
        stadt = stadt_slug.replace('-', ' ').title()
    
    kat = KATEGORIE_MAPPING[kategorie_slug]
    
    lat, lng = get_coordinates_from_address(stadt)
    umkreis = 50
    
    premium_jobs = Stellenangebot.query.filter_by(ist_aktiv=True).all()
    externe_jobs = ExternesInserat.query.filter_by(ist_aktiv=True).all()
    
    def matches_kategorie(job, is_extern=False):
        if not is_extern:
            position = (job.position or '').lower()
            if position == kategorie_slug:
                return True
        
        titel = (job.titel or '').lower()
        
        if is_extern:
            beschreibung = (job.beschreibung or '').lower()
        else:
            beschreibung = ' '.join([
                (job.aufgaben or ''),
                (job.anforderungen or ''),
                (job.wir_bieten or '')
            ]).lower()
        
        search_terms = [kategorie_slug, kat['name'].lower()]
        for term in search_terms:
            if term in titel or term in beschreibung:
                return True
        return False
    
    def matches_stadt(job, is_extern=False):
        stadt_lower = stadt.lower()
        if is_extern:
            job_stadt = (job.standort_stadt or '').lower()
        else:
            job_stadt = (job.standort_stadt or '').lower() if hasattr(job, 'standort_stadt') else ''
            if not job_stadt and job.praxis:
                job_stadt = (job.praxis.stadt or '').lower()
        return stadt_lower in job_stadt or job_stadt in stadt_lower
    
    if lat and lng:
        def filter_job(job, is_extern=False):
            if not matches_kategorie(job, is_extern):
                return False
            if is_extern:
                job_lat, job_lng = job.latitude, job.longitude
            else:
                if job.praxis:
                    job_lat, job_lng = job.praxis.latitude, job.praxis.longitude
                else:
                    return matches_stadt(job, is_extern)
            if job_lat and job_lng:
                return entfernung_km(lat, lng, job_lat, job_lng) <= umkreis
            return matches_stadt(job, is_extern)
        
        premium_jobs = [j for j in premium_jobs if filter_job(j, False)]
        externe_jobs = [j for j in externe_jobs if filter_job(j, True)]
    else:
        def filter_no_coords(job, is_extern=False):
            return matches_kategorie(job, is_extern) and matches_stadt(job, is_extern)
        
        premium_jobs = [j for j in premium_jobs if filter_no_coords(j, False)]
        externe_jobs = [j for j in externe_jobs if filter_no_coords(j, True)]
    
    for job in premium_jobs:
        job.ist_extern = False
    for job in externe_jobs:
        job.ist_extern = True
    
    premium_jobs.sort(key=lambda x: x.erstellt_am or datetime.min, reverse=True)
    externe_jobs.sort(key=lambda x: x.veroeffentlicht_am or datetime.min, reverse=True)
    
    alle_jobs = premium_jobs + externe_jobs
    total_jobs = len(alle_jobs)
    jobs = alle_jobs[:15]
    
    meta_title = f"{kat['name']} Jobs in {stadt} | Stellenangebote {kat['full']} | Dentalax"
    meta_description = f"Aktuelle {kat['name']} Stellenangebote in {stadt}. Jetzt als {kat['full']} bewerben bei Top-Arbeitgebern in der Zahnmedizin."
    
    return render_template('stellenangebote.html',
                          active_page='stellenangebote',
                          jobs=jobs,
                          premium_count=len(premium_jobs),
                          extern_count=len(externe_jobs),
                          total_jobs=total_jobs,
                          page=1,
                          per_page=15,
                          total_pages=math.ceil(total_jobs / 15) if total_jobs > 0 else 1,
                          query='',
                          position=kategorie_slug,
                          ort=stadt,
                          umkreis=umkreis,
                          sortierung='neuste',
                          ansicht='liste',
                          vollzeit_checked=False,
                          teilzeit_checked=False,
                          ausbildung_checked=False,
                          staedte_mit_jobs=[],
                          meta_title=meta_title,
                          meta_description=meta_description,
                          seo_route=True,
                          seo_h1=seo_kategorie_h1(kategorie_slug, stadt),
                          seo_intro=seo_kategorie_intro(kategorie_slug, stadt),
                          seo_h2=f"Jobs als {kat['full']} in {stadt}",
                          seo_footer=seo_kategorie_footer(kategorie_slug, stadt),
                          stadt_name=stadt,
                          stadt_slug=stadt_slug,
                          kategorie_slug=kategorie_slug,
                          kategorie_name=kat['name'])


@app.route("/stellenangebot/<slug>")
def stellenangebot_detail(slug):
    """Detailseite für ein Stellenangebot inkl. Bewerbungsformular"""
    job = Stellenangebot.query.filter_by(slug=slug, ist_aktiv=True).first()
    
    if not job:
        flash('Stellenangebot nicht gefunden.', 'warning')
        return redirect(url_for('stellenangebote'))
    
    meta_title = f"{job.position_display} in {job.standort_stadt} ({job.anstellungsart_display}) | Dentalax"
    meta_description = f"Jetzt bewerben: {job.titel} bei {job.praxis.name} in {job.standort_plz} {job.standort_stadt}. {job.anstellungsart_display}."
    
    return render_template('stellenangebot_detail.html', 
                          active_page='stellenangebote',
                          job=job,
                          praxis=job.praxis,
                          meta_title=meta_title,
                          meta_description=meta_description)


@app.route("/stellenangebot/<slug>/bewerben", methods=["POST"])
def stellenangebot_bewerben(slug):
    """Verarbeitet eine Bewerbung auf ein Stellenangebot"""
    job = Stellenangebot.query.filter_by(slug=slug, ist_aktiv=True).first()
    
    if not job:
        flash('Stellenangebot nicht gefunden.', 'warning')
        return redirect(url_for('stellenangebote'))
    
    vorname = request.form.get('vorname', '').strip()
    nachname = request.form.get('nachname', '').strip()
    email = request.form.get('email', '').strip()
    telefon = request.form.get('telefon', '').strip()
    adresse = request.form.get('adresse', '').strip()
    plz = request.form.get('plz', '').strip()
    ort = request.form.get('ort', '').strip()
    berufserfahrung = request.form.get('erfahrung', '').strip()
    fruehester_eintritt = request.form.get('fruehesteEintritt', '').strip()
    gehaltsvorstellung = request.form.get('gehaltsvorstellung', '').strip()
    nachricht = request.form.get('nachricht', '').strip()
    
    if not vorname or not nachname or not email:
        flash('Bitte füllen Sie alle Pflichtfelder aus.', 'danger')
        return redirect(url_for('stellenangebot_detail', slug=slug) + '#bewerben')
    
    upload_dir = os.path.join('static', 'uploads', 'bewerbungen')
    os.makedirs(upload_dir, exist_ok=True)
    
    def save_upload(field_name, prefix):
        if field_name in request.files:
            file = request.files[field_name]
            if file and file.filename:
                filename = secure_filename(f"{prefix}_{job.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                return f"/static/uploads/bewerbungen/{filename}"
        return None
    
    lebenslauf_pfad = save_upload('lebenslauf', 'cv')
    anschreiben_pfad = save_upload('anschreiben', 'cover')
    zeugnisse_pfad = save_upload('zeugnisse', 'cert')
    
    neue_bewerbung = Bewerbung(
        vorname=vorname,
        nachname=nachname,
        email=email,
        telefon=telefon,
        adresse=adresse,
        plz=plz,
        ort=ort,
        berufserfahrung=berufserfahrung,
        fruehester_eintritt=fruehester_eintritt,
        gehaltsvorstellung=gehaltsvorstellung,
        nachricht=nachricht,
        lebenslauf_pfad=lebenslauf_pfad,
        anschreiben_pfad=anschreiben_pfad,
        zeugnisse_pfad=zeugnisse_pfad,
        stellenangebot_id=job.id
    )
    
    db.session.add(neue_bewerbung)
    db.session.commit()
    
    try:
        from services.email_service import send_bewerbung_bestaetigung_bewerber
        send_bewerbung_bestaetigung_bewerber(email, vorname, job.titel, job.praxis.name)
    except Exception as e:
        logging.error(f"Fehler beim Senden der Bewerbungsbestätigung: {e}")
    
    try:
        from services.email_service import send_bewerbung_benachrichtigung_zahnarzt
        zahnarzt = Zahnarzt.query.filter_by(praxis_id=job.praxis_id).first()
        if zahnarzt and zahnarzt.email:
            dashboard_url = f"https://{os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000'))}/zahnarzt-dashboard?page=stellenangebote"
            send_bewerbung_benachrichtigung_zahnarzt(zahnarzt.email, vorname, nachname, job.titel, job.praxis.name, dashboard_url)
    except Exception as e:
        logging.error(f"Fehler beim Senden der Zahnarzt-Benachrichtigung: {e}")
    
    flash('Vielen Dank für Ihre Bewerbung! Sie erhalten eine Bestätigung per E-Mail.', 'success')
    return redirect(url_for('stellenangebot_detail', slug=slug))


@app.route("/job-alert/anmelden", methods=["POST"])
def job_alert_anmelden():
    email = request.form.get('email', '').strip()
    position = request.form.get('position', '').strip()
    ort = request.form.get('ort', '').strip()
    datenschutz = request.form.get('datenschutz')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if not email or not ort or not datenschutz:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Bitte füllen Sie alle Pflichtfelder aus und akzeptieren Sie die Datenschutzbestimmungen.'}), 400
        flash('Bitte füllen Sie alle Pflichtfelder aus und akzeptieren Sie die Datenschutzbestimmungen.', 'danger')
        return redirect(request.referrer or url_for('stellenangebote'))
    
    import secrets
    token = secrets.token_urlsafe(32)
    
    latitude = None
    longitude = None
    praxis_match = Praxis.query.filter(Praxis.stadt.ilike(f'%{ort}%')).first()
    if praxis_match and praxis_match.latitude and praxis_match.longitude:
        latitude = praxis_match.latitude
        longitude = praxis_match.longitude
    
    existing = JobAlert.query.filter_by(email=email, position=position, ort=ort).first()
    if existing:
        existing.bestaetigungs_token = token
        existing.ist_aktiv = False
        db.session.commit()
    else:
        alert = JobAlert(
            email=email,
            position=position,
            ort=ort,
            latitude=latitude,
            longitude=longitude,
            bestaetigungs_token=token
        )
        db.session.add(alert)
        db.session.commit()
    
    try:
        from services.email_service import send_job_alert_bestaetigung
        confirm_url = f"https://{os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000'))}/job-alert/bestaetigen/{token}"
        send_job_alert_bestaetigung(email, position, ort, confirm_url)
    except Exception as e:
        logging.error(f"Fehler beim Senden der Job-Alert Bestätigung: {e}")
    
    if is_ajax:
        return jsonify({'success': True, 'message': 'Fast geschafft! Bitte bestätigen Sie Ihren Job-Alert über den Link in der E-Mail, die wir Ihnen gerade gesendet haben.'})
    
    flash('Fast geschafft! Bitte bestätigen Sie Ihren Job-Alert über den Link in der E-Mail, die wir Ihnen gerade gesendet haben.', 'success')
    return redirect(request.referrer or url_for('stellenangebote'))


@app.route("/job-alert/bestaetigen/<token>")
def job_alert_bestaetigen(token):
    alert = JobAlert.query.filter_by(bestaetigungs_token=token).first()
    if not alert:
        flash('Ungültiger oder abgelaufener Bestätigungslink.', 'danger')
        return redirect(url_for('stellenangebote'))
    
    alert.ist_aktiv = True
    alert.bestaetigt_am = datetime.now()
    db.session.commit()
    
    flash('Ihr Job-Alert wurde erfolgreich aktiviert! Sie erhalten ab sofort passende Stellenangebote per E-Mail.', 'success')
    return redirect(url_for('stellenangebote'))


@app.route("/job-alert/abmelden/<token>")
def job_alert_abmelden(token):
    alert = JobAlert.query.filter_by(bestaetigungs_token=token).first()
    if not alert:
        flash('Job-Alert nicht gefunden.', 'warning')
        return redirect(url_for('stellenangebote'))
    
    db.session.delete(alert)
    db.session.commit()
    
    flash('Ihr Job-Alert wurde erfolgreich abbestellt.', 'success')
    return redirect(url_for('stellenangebote'))


def notify_matching_job_alerts(stellenangebot):
    """Benachrichtigt alle aktiven Job-Alert Abonnenten, die zur neuen Stelle passen (Position + 50km Umkreis)"""
    import math
    
    matching_alerts = JobAlert.query.filter_by(ist_aktiv=True).all()
    
    if not matching_alerts:
        return
    
    job_lat = None
    job_lng = None
    praxis = stellenangebot.praxis
    if praxis and praxis.latitude and praxis.longitude:
        job_lat = praxis.latitude
        job_lng = praxis.longitude
    
    position_namen = {
        'zfa': 'Zahnmedizinische/r Fachangestellte/r (ZFA)',
        'zmf': 'Zahnmedizinische Fachassistentin (ZMF)',
        'zmp': 'Zahnmedizinische Prophylaxeassistentin (ZMP)',
        'dh': 'Dentalhygieniker/in (DH)',
        'zahnarzt': 'Zahnarzt/Zahnärztin',
    }
    position_display = position_namen.get(stellenangebot.position, stellenangebot.position)
    
    domain = os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000'))
    base_url = f"https://{domain}"
    job_url = f"{base_url}/stellenangebot/{stellenangebot.slug}"
    standort = f"{stellenangebot.standort_plz} {stellenangebot.standort_stadt}"
    
    from services.email_service import send_job_alert_benachrichtigung
    
    sent_count = 0
    for alert in matching_alerts:
        if alert.position and alert.position != stellenangebot.position:
            continue
        
        if job_lat and job_lng and alert.latitude and alert.longitude:
            dist = haversine_distance(job_lat, job_lng, alert.latitude, alert.longitude)
            if dist > (alert.umkreis_km or 50):
                continue
        elif job_lat and job_lng and (not alert.latitude or not alert.longitude):
            continue
        
        abmelde_url = f"{base_url}/job-alert/abmelden/{alert.bestaetigungs_token}"
        
        try:
            send_job_alert_benachrichtigung(
                alert.email,
                stellenangebot.titel,
                position_display,
                praxis.name if praxis else '',
                standort,
                job_url,
                abmelde_url
            )
            sent_count += 1
        except Exception as e:
            logging.error(f"Job-Alert E-Mail Fehler für {alert.email}: {e}")
    
    if sent_count > 0:
        logging.info(f"Job-Alert: {sent_count} Benachrichtigungen für '{stellenangebot.titel}' versendet")


@app.route("/zahnarzt-dashboard")
@login_required
def zahnarzt_dashboard():
    """Zahnarzt-Dashboard mit echten Praxisdaten"""
    from datetime import date
    from sqlalchemy import func
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Sie haben noch keine Praxis angelegt.', 'warning')
        return redirect(url_for('index'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('index'))
    
    oeffnungszeiten = Oeffnungszeit.query.filter_by(praxis_id=praxis.id).order_by(Oeffnungszeit.tag).all()
    oeffnungszeiten_dict = {oz.tag: oz for oz in oeffnungszeiten}
    leistungen = Leistung.query.filter_by(praxis_id=praxis.id).all()
    team_mitglieder = TeamMitglied.query.filter_by(praxis_id=praxis.id).all()
    bilder = PraxisBild.query.filter_by(praxis_id=praxis.id).all()
    terminanfragen_alt = Terminanfrage.query.filter_by(praxis_id=praxis.id).order_by(Terminanfrage.erstellt_am.desc()).limit(10).all()
    bewertungen = Bewertung.query.filter_by(praxis_id=praxis.id).order_by(Bewertung.datum.desc()).all()
    
    heute = date.today()
    from datetime import datetime, timedelta
    
    ausstehende_termine = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.status == 'ausstehend',
        Termin.datum >= heute
    ).order_by(Termin.datum, Termin.uhrzeit).all()
    
    kommende_termine = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.status.in_(['ausstehend', 'bestaetigt']),
        Termin.datum >= heute
    ).order_by(Termin.datum, Termin.uhrzeit).all()
    
    terminanfragen = ausstehende_termine
    
    termine_heute_raw = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.datum == heute
    ).order_by(Termin.uhrzeit).all()
    
    termine_heute = []
    for t in termine_heute_raw:
        end_zeit = getattr(t, 'end_zeit', None)
        if end_zeit:
            t.computed_ende = end_zeit
        else:
            dauer = t.dauer_minuten or 30
            if t.uhrzeit:
                start_dt = datetime.combine(heute, t.uhrzeit)
                end_dt = start_dt + timedelta(minutes=dauer)
                t.computed_ende = end_dt.time()
            else:
                t.computed_ende = None
        termine_heute.append(t)
    
    termine_heute_count = len(termine_heute)
    termine_bestaetigt = len([t for t in termine_heute if t.status == 'bestaetigt'])
    
    termine_gesamt = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.datum >= heute
    ).count()
    ausstehende_count = len(ausstehende_termine)
    
    kommende_termine_woche = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.status.in_(['ausstehend', 'bestaetigt']),
        Termin.datum >= heute,
        Termin.datum <= heute + timedelta(days=7)
    ).order_by(Termin.datum, Termin.uhrzeit).all()
    
    # Bewertungen-Statistik
    freigegebene_bewertungen = [b for b in bewertungen if b.status == 'freigegeben']
    bewertungen_count = len(freigegebene_bewertungen)
    if bewertungen_count > 0:
        bewertungen_durchschnitt = round(sum(b.sterne for b in freigegebene_bewertungen) / bewertungen_count, 1)
    else:
        bewertungen_durchschnitt = 0
    
    hero_bild = next((b for b in bilder if b.typ == 'titelbild'), None)
    logo_bild = next((b for b in bilder if b.typ == 'logo'), None)
    portrait_bild = next((b for b in bilder if b.typ == 'portrait'), None)
    ueber_uns_bild = next((b for b in bilder if b.typ == 'team_foto'), None)
    
    stellenangebote = Stellenangebot.query.filter_by(praxis_id=praxis.id).order_by(Stellenangebot.erstellt_am.desc()).all()
    alle_bewerbungen = []
    for job in stellenangebote:
        alle_bewerbungen.extend(job.bewerbungen)
    alle_bewerbungen.sort(key=lambda x: x.eingegangen_am, reverse=True)
    
    return render_template('zahnarzt-dashboard.html',
                          active_page='fuer-zahnaerzte',
                          praxis=praxis,
                          oeffnungszeiten=oeffnungszeiten,
                          oeffnungszeiten_dict=oeffnungszeiten_dict,
                          leistungen=leistungen,
                          team_mitglieder=team_mitglieder,
                          bewertungen=bewertungen,
                          hero_bild=hero_bild,
                          logo_bild=logo_bild,
                          portrait_bild=portrait_bild,
                          ueber_uns_bild=ueber_uns_bild,
                          terminanfragen=terminanfragen,
                          termine_heute=termine_heute,
                          termine_heute_count=termine_heute_count,
                          termine_bestaetigt=termine_bestaetigt,
                          termine_gesamt=termine_gesamt,
                          ausstehende_count=ausstehende_count,
                          kommende_termine_woche=kommende_termine_woche,
                          bewertungen_count=bewertungen_count,
                          bewertungen_durchschnitt=bewertungen_durchschnitt,
                          stellenangebote=stellenangebote,
                          bewerbungen=alle_bewerbungen,
                          meta_title=f"Dashboard - {praxis.name} | Dentalax",
                          meta_description="Verwalten Sie Ihre Praxis-Landingpage, Termine und mehr.")

@app.route("/ueber-uns")
def ueber_uns():
    """Über Uns Seite mit Information zur Vision und Mission von Dentalax"""
    return render_template("ueber-uns.html", 
                          active_page='ueber-uns',
                          meta_title="Über uns | Dentalax",
                          meta_description="Erfahren Sie mehr über die Vision und Mission von Dentalax. Wir revolutionieren die Zahnarztbranche durch digitale Innovation und setzen neue Maßstäbe.")

@app.route("/api/subscription/upgrade", methods=["POST"])
@login_required
def api_subscription_upgrade():
    """API-Endpunkt für Paket-Upgrade"""
    from stripe_subscription import create_subscription_checkout
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return {'error': 'Keine Praxis vorhanden'}, 400
    
    paket = request.form.get('paket', 'premium')
    zahlweise = request.form.get('zahlweise', 'monatlich')
    
    if paket not in ['premium', 'premiumplus']:
        return {'error': 'Ungültiges Paket'}, 400
    
    if zahlweise not in ['monatlich', 'jaehrlich']:
        return {'error': 'Ungültige Zahlweise'}, 400
    
    result = create_subscription_checkout(current_user.praxis_id, paket, zahlweise)
    
    if 'error' in result:
        flash(f'Fehler beim Erstellen der Checkout-Session: {result["error"]}', 'danger')
        return redirect(url_for('zahnarzt_dashboard') + '?page=abrechnung')
    
    return redirect(result['url'])

@app.route("/api/subscription/portal", methods=["POST"])
@login_required
def api_subscription_portal():
    """Öffnet das Stripe Customer Portal zur Abo-Verwaltung"""
    from stripe_subscription import create_customer_portal_session
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis vorhanden', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    result = create_customer_portal_session(current_user.praxis_id)
    
    if 'error' in result:
        flash(f'Fehler: {result["error"]}', 'danger')
        return redirect(url_for('zahnarzt_dashboard') + '?page=abrechnung')
    
    return redirect(result['url'])

@app.route("/api/subscription/cancel", methods=["POST"])
@login_required
def api_subscription_cancel():
    """Kündigt das aktuelle Abonnement"""
    from stripe_subscription import cancel_subscription
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis vorhanden', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    at_period_end = request.form.get('at_period_end', 'true') == 'true'
    
    result = cancel_subscription(current_user.praxis_id, at_period_end=at_period_end)
    
    if 'error' in result:
        flash(f'Fehler bei der Kündigung: {result["error"]}', 'danger')
    else:
        if at_period_end:
            flash('Ihr Abonnement wird zum Ende der Laufzeit gekündigt.', 'success')
        else:
            flash('Ihr Abonnement wurde sofort gekündigt.', 'success')
    
    return redirect(url_for('zahnarzt_dashboard') + '?page=abrechnung')

# ========================================
# DENTALBERATER CHATBOT API
# ========================================

from main import csrf

@csrf.exempt
@app.route("/api/chat/match", methods=["POST"])
def dental_match_chat():
    """API-Endpoint für den Dental Match KI-Chatbot"""
    from services.ai_service import get_dental_match_response
    from models import Bewertung
    from sqlalchemy import func as sql_func
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Keine Daten empfangen'}), 400
    
    user_message = data.get('message', '').strip()
    location = data.get('location', '').strip()
    filters = data.get('filters', {})
    conversation_history = data.get('history', [])
    
    if not user_message:
        return jsonify({'error': 'Nachricht fehlt'}), 400
    
    # Standort aus Nachricht extrahieren falls nicht explizit angegeben
    import re
    
    db_staedte = db.session.query(Praxis.stadt).distinct().all()
    db_staedte_list = [s[0].strip().lower() for s in db_staedte if s[0]]
    
    bekannte_staedte = ['berlin', 'hamburg', 'münchen', 'muenchen', 'köln', 'koeln', 'frankfurt', 
                       'stuttgart', 'düsseldorf', 'duesseldorf', 'dortmund', 'essen', 'leipzig', 
                       'bremen', 'dresden', 'hannover', 'nürnberg', 'nuernberg', 'duisburg', 
                       'bochum', 'wuppertal', 'bielefeld', 'bonn', 'münster', 'muenster', 
                       'karlsruhe', 'mannheim', 'augsburg', 'wiesbaden', 'mainz', 'aachen']
    
    alle_staedte = set(db_staedte_list) | set(bekannte_staedte)
    
    def extract_location_from_text(text):
        text_lower = text.lower()
        found = None
        
        naehe_match = re.search(r'(?:in\s+der\s+)?n[äa]he\s+(?:von\s+)?([A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß\-]+)', text, re.IGNORECASE)
        if naehe_match:
            kandidat = naehe_match.group(1).strip().lower()
            if kandidat in alle_staedte:
                original = next((s[0].strip() for s in db_staedte if s[0] and s[0].strip().lower() == kandidat), None)
                found = original if original else kandidat.title()
        
        if not found:
            pattern = r'\b(?:in|aus|bei|nach|wohne|lebe|komme)\s+(?:in\s+)?([A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß\-]+)\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for kandidat in matches:
                kandidat_lower = kandidat.strip().lower()
                if kandidat_lower in alle_staedte:
                    original = next((s[0].strip() for s in db_staedte if s[0] and s[0].strip().lower() == kandidat_lower), None)
                    found = original if original else kandidat.title()
                    break
        
        if not found:
            for stadt in alle_staedte:
                if stadt in text_lower:
                    original = next((s[0].strip() for s in db_staedte if s[0] and s[0].strip().lower() == stadt), None)
                    found = original if original else stadt.title()
                    break
        
        return found
    
    if not location:
        location = extract_location_from_text(user_message)
    
    if not location and conversation_history:
        for msg in reversed(conversation_history):
            if msg.get('role') == 'user':
                found = extract_location_from_text(msg.get('content', ''))
                if found:
                    location = found
                    break
    
    praxen_data = []
    user_lat, user_lng = None, None
    max_radius_km = 25  # Maximaler Umkreis in km
    
    if location:
        # Versuche Koordinaten für den Standort zu ermitteln
        try:
            user_lat, user_lng = get_coordinates_from_address(f"{location}, Deutschland")
        except Exception as e:
            logging.warning(f"Geocoding fehlgeschlagen für {location}: {e}")
        
        # Bewertungsdaten vorladen
        bewertung_stats = db.session.query(
            Bewertung.praxis_id,
            sql_func.avg(Bewertung.sterne).label('avg_sterne'),
            sql_func.count(Bewertung.id).label('anzahl')
        ).filter(Bewertung.bestaetigt == True).group_by(Bewertung.praxis_id).all()
        chatbot_bewertung_map = {b.praxis_id: {'avg': round(float(b.avg_sterne), 1), 'anzahl': int(b.anzahl)} for b in bewertung_stats}
        
        # 1. DATENBANK-PRAXEN durchsuchen
        query = Praxis.query
        
        # Filter anwenden
        if filters.get('angstpatienten'):
            query = query.filter(Praxis.angstpatientenfreundlich == True)
        if filters.get('kinder'):
            query = query.filter(Praxis.kinderfreundlich == True)
        if filters.get('barrierefrei'):
            query = query.filter(Praxis.barrierefrei == True)
        if filters.get('abendsprechstunde'):
            query = query.filter(Praxis.abendsprechstunde == True)
        if filters.get('samstag'):
            query = query.filter(Praxis.samstagssprechstunde == True)
        
        db_praxen_mit_distanz = []
        
        # Wenn wir Koordinaten haben, nutze Geo-Filter für DB-Praxen
        if user_lat and user_lng:
            alle_db_praxen = query.filter(
                Praxis.latitude.isnot(None),
                Praxis.longitude.isnot(None)
            ).all()
            
            for p in alle_db_praxen:
                distanz = haversine_distance(user_lat, user_lng, p.latitude, p.longitude)
                if distanz <= max_radius_km:
                    bew = chatbot_bewertung_map.get(p.id, {'avg': 0, 'anzahl': 0})
                    db_praxen_mit_distanz.append({
                        'name': p.name,
                        'strasse': p.strasse,
                        'plz': p.plz,
                        'stadt': p.stadt,
                        'telefon': p.telefon,
                        'paket': p.paket or 'basic',
                        'leistungsschwerpunkte': p.leistungsschwerpunkte,
                        'angstpatientenfreundlich': p.angstpatientenfreundlich,
                        'kinderfreundlich': p.kinderfreundlich,
                        'barrierefrei': p.barrierefrei,
                        'abendsprechstunde': p.abendsprechstunde,
                        'samstagssprechstunde': p.samstagssprechstunde,
                        'sprachen': p.sprachen,
                        'slug': p.slug,
                        'ist_verifiziert': p.ist_verifiziert,
                        'distanz': distanz,
                        'quelle': 'db',
                        'bewertung_avg': bew['avg'],
                        'bewertung_anzahl': bew['anzahl'],
                        'google_rating': p.google_rating,
                        'google_review_count': p.google_review_count or 0
                    })
        else:
            # Fallback: Stadtname-basierte Suche
            db_praxen = query.filter(Praxis.stadt.ilike(f'%{location}%')).all()
            for p in db_praxen:
                bew = chatbot_bewertung_map.get(p.id, {'avg': 0, 'anzahl': 0})
                db_praxen_mit_distanz.append({
                    'name': p.name,
                    'strasse': p.strasse,
                    'plz': p.plz,
                    'stadt': p.stadt,
                    'telefon': p.telefon,
                    'paket': p.paket or 'basic',
                    'leistungsschwerpunkte': p.leistungsschwerpunkte,
                    'angstpatientenfreundlich': p.angstpatientenfreundlich,
                    'kinderfreundlich': p.kinderfreundlich,
                    'barrierefrei': p.barrierefrei,
                    'abendsprechstunde': p.abendsprechstunde,
                    'samstagssprechstunde': p.samstagssprechstunde,
                    'sprachen': p.sprachen,
                    'slug': p.slug,
                    'ist_verifiziert': p.ist_verifiziert,
                    'distanz': 0,
                    'quelle': 'db',
                    'bewertung_avg': bew['avg'],
                    'bewertung_anzahl': bew['anzahl'],
                    'google_rating': p.google_rating,
                    'google_review_count': p.google_review_count or 0
                })
        
        # 2. CSV-PRAXEN durchsuchen (zahnaerzte.csv)
        csv_praxen_mit_distanz = []
        try:
            csv_praxen = lade_praxen("zahnaerzte.csv")
            location_lower = location.lower()
            
            for p in csv_praxen:
                csv_lat = p.get('lat')
                csv_lng = p.get('lng')
                csv_stadt = (p.get('stadt') or '').lower()
                
                # Geo-basierte Filterung wenn möglich
                if user_lat and user_lng and csv_lat and csv_lng:
                    try:
                        distanz = haversine_distance(user_lat, user_lng, float(csv_lat), float(csv_lng))
                        if distanz <= max_radius_km:
                            csv_praxen_mit_distanz.append({
                                'name': p.get('name', ''),
                                'strasse': p.get('straße', ''),
                                'plz': p.get('plz', ''),
                                'stadt': p.get('stadt', ''),
                                'telefon': p.get('telefon', ''),
                                'paket': 'basis',
                                'leistungsschwerpunkte': p.get('leistungsschwerpunkte', ''),
                                'angstpatientenfreundlich': False,
                                'kinderfreundlich': False,
                                'barrierefrei': False,
                                'abendsprechstunde': False,
                                'samstagssprechstunde': False,
                                'sprachen': '',
                                'slug': None,
                                'ist_verifiziert': False,
                                'distanz': distanz,
                                'quelle': 'csv',
                                'csv_id': p.get('csv_id')
                            })
                    except (ValueError, TypeError):
                        pass
                # Fallback: Stadtname-Match (nur wenn Stadt vorhanden)
                elif csv_stadt and (location_lower in csv_stadt or csv_stadt in location_lower):
                    csv_praxen_mit_distanz.append({
                        'name': p.get('name', ''),
                        'strasse': p.get('straße', ''),
                        'plz': p.get('plz', ''),
                        'stadt': p.get('stadt', ''),
                        'telefon': p.get('telefon', ''),
                        'paket': 'basis',
                        'leistungsschwerpunkte': p.get('leistungsschwerpunkte', ''),
                        'angstpatientenfreundlich': False,
                        'kinderfreundlich': False,
                        'barrierefrei': False,
                        'abendsprechstunde': False,
                        'samstagssprechstunde': False,
                        'sprachen': '',
                        'slug': None,
                        'ist_verifiziert': False,
                        'distanz': 0,
                        'quelle': 'csv',
                        'csv_id': p.get('csv_id')
                    })
        except Exception as e:
            logging.warning(f"CSV-Praxen laden fehlgeschlagen: {e}")
        
        # 3. Ergebnisse kombinieren und sortieren
        alle_ergebnisse = db_praxen_mit_distanz + csv_praxen_mit_distanz
        
        def sort_key(item):
            paket_prio = {'premiumplus': 1, 'premium': 2, 'basis': 3, 'basic': 3}.get((item.get('paket') or 'basis').lower(), 4)
            verifiziert = -1 if item.get('ist_verifiziert') else 0
            distanz = item.get('distanz', 999)
            return (paket_prio, verifiziert, distanz)
        
        alle_ergebnisse.sort(key=sort_key)
        
        # Top 10 Ergebnisse für KI vorbereiten
        for item in alle_ergebnisse[:10]:
            praxen_data.append({
                'name': item.get('name'),
                'strasse': item.get('strasse'),
                'plz': item.get('plz'),
                'stadt': item.get('stadt'),
                'telefon': item.get('telefon'),
                'paket': item.get('paket'),
                'leistungsschwerpunkte': item.get('leistungsschwerpunkte'),
                'angstpatientenfreundlich': item.get('angstpatientenfreundlich'),
                'kinderfreundlich': item.get('kinderfreundlich'),
                'barrierefrei': item.get('barrierefrei'),
                'abendsprechstunde': item.get('abendsprechstunde'),
                'samstagssprechstunde': item.get('samstagssprechstunde'),
                'sprachen': item.get('sprachen'),
                'slug': item.get('slug'),
                'quelle': item.get('quelle', 'db'),
                'bewertung_avg': item.get('bewertung_avg', 0),
                'bewertung_anzahl': item.get('bewertung_anzahl', 0),
                'google_rating': item.get('google_rating'),
                'google_review_count': item.get('google_review_count', 0)
            })
    
    # Premium-Praxen für Frontend-Karten extrahieren
    premium_praxen = []
    for p in praxen_data:
        if (p.get('paket') or '').lower() in ['premiumplus', 'premium']:
            premium_praxen.append({
                'name': p.get('name'),
                'strasse': p.get('strasse'),
                'plz': p.get('plz'),
                'stadt': p.get('stadt'),
                'telefon': p.get('telefon'),
                'paket': p.get('paket'),
                'slug': p.get('slug'),
                'angstpatientenfreundlich': p.get('angstpatientenfreundlich'),
                'kinderfreundlich': p.get('kinderfreundlich'),
                'barrierefrei': p.get('barrierefrei'),
                'bewertung_avg': p.get('bewertung_avg', 0),
                'bewertung_anzahl': p.get('bewertung_anzahl', 0),
                'google_rating': p.get('google_rating'),
                'google_review_count': p.get('google_review_count', 0)
            })
    
    try:
        response = get_dental_match_response(user_message, praxen_data, conversation_history)
        return jsonify({
            'response': response,
            'praxen_count': len(praxen_data),
            'location_detected': location if location else None,
            'premium_praxen': premium_praxen[:3]  # Max 3 Premium-Karten
        })
    except Exception as e:
        logging.error(f"Dental Match Chat Fehler: {e}")
        return jsonify({
            'response': 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.',
            'error': str(e)
        }), 500


@csrf.exempt
@app.route("/api/ai/generate-text", methods=["POST"])
@login_required
def ai_generate_text():
    """API-Endpoint für KI-Textgenerierung im Dashboard"""
    from services.ai_service import generate_praxis_text
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return jsonify({'error': 'Keine Praxis zugeordnet'}), 403
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        return jsonify({'error': 'Praxis nicht gefunden'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Keine Daten empfangen'}), 400
    
    text_type = data.get('type', '')
    additional_info = data.get('info', '')
    
    if text_type not in ['ueber_uns', 'team_mitglied', 'bewertung_antwort', 'hero']:
        return jsonify({'error': 'Ungültiger Texttyp'}), 400
    
    praxis_data = {
        'name': praxis.name,
        'stadt': praxis.stadt,
        'leistungsschwerpunkte': praxis.leistungsschwerpunkte
    }
    
    try:
        generated_text = generate_praxis_text(text_type, praxis_data, additional_info)
        return jsonify({
            'text': generated_text,
            'type': text_type
        })
    except Exception as e:
        logging.error(f"KI-Textgenerierung Fehler: {e}")
        return jsonify({'error': 'Textgenerierung fehlgeschlagen'}), 500


@app.route("/api/ai/generate-job-text", methods=["POST"])
@csrf.exempt
@login_required
def ai_generate_job_text():
    """API-Endpoint für KI-Textgenerierung bei Stellenangeboten"""
    from services.ai_service import generate_stellenangebot_text
    
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return jsonify({'error': 'Keine Praxis zugeordnet'}), 403
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        return jsonify({'error': 'Praxis nicht gefunden'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Keine Daten empfangen'}), 400
    
    field_type = data.get('field', '')
    position = data.get('position', '')
    anstellungsart = data.get('anstellungsart', 'vollzeit')
    
    if field_type not in ['ueber_uns', 'aufgaben', 'anforderungen', 'wir_bieten', 'tags']:
        return jsonify({'error': 'Ungültiger Feldtyp'}), 400
    
    if not position:
        return jsonify({'error': 'Bitte wählen Sie zuerst eine Position aus'}), 400
    
    praxis_data = {
        'name': praxis.name,
        'stadt': praxis.stadt,
        'beschreibung': praxis.beschreibung or '',
        'leistungsschwerpunkte': praxis.leistungsschwerpunkte or ''
    }
    
    existing_fields = data.get('existing_fields', {})
    
    try:
        generated_text = generate_stellenangebot_text(field_type, position, anstellungsart, praxis_data, existing_fields)
        return jsonify({
            'text': generated_text,
            'field': field_type
        })
    except Exception as e:
        logging.error(f"KI-Stellenangebot-Generierung Fehler: {e}")
        return jsonify({'error': 'Textgenerierung fehlgeschlagen'}), 500


@app.route("/api/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe Webhook Endpoint für Subscription-Events"""
    from stripe_subscription import handle_webhook_event
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    result = handle_webhook_event(payload, sig_header)
    
    if 'error' in result:
        return {'error': result['error']}, 400
    
    return {'received': True}, 200

@app.route("/zahnarzt-dashboard/abrechnung-success")
@login_required
def subscription_success():
    """Callback nach erfolgreicher Subscription-Zahlung"""
    from stripe_subscription import handle_subscription_success
    
    session_id = request.args.get('session_id')
    
    if session_id:
        result = handle_subscription_success(session_id)
        if 'error' in result:
            flash(f'Fehler bei der Verarbeitung: {result["error"]}', 'danger')
        else:
            flash('Vielen Dank! Ihr Paket wurde erfolgreich aktiviert.', 'success')
    
    return redirect(url_for('zahnarzt_dashboard') + '?page=abrechnung')

@app.route("/terminanfrage/<int:praxis_id>", methods=["POST"])
def terminanfrage_senden(praxis_id):
    """Empfängt eine Terminanfrage über das Kontaktformular und speichert sie in der Datenbank"""
    praxis = Praxis.query.get_or_404(praxis_id)
    
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    telefon = request.form.get('telefon', '').strip()
    wunschtermin = request.form.get('wunschtermin', '').strip()
    grund = request.form.get('grund', '').strip()
    nachricht = request.form.get('nachricht', '').strip()
    
    if not name or not email:
        flash('Bitte geben Sie mindestens Ihren Namen und Ihre E-Mail-Adresse an.', 'danger')
        return redirect(url_for('praxis_landingpage', slug=praxis.slug) + '#termin')
    
    try:
        anfrage = Terminanfrage(
            name=name,
            email=email,
            telefon=telefon,
            wunschtermin=wunschtermin,
            grund=grund,
            nachricht=nachricht,
            praxis_id=praxis.id,
            status='neu'
        )
        db.session.add(anfrage)
        db.session.commit()
        
        praxis_email = praxis.email
        if praxis_email:
            try:
                from services.email_service import send_kontaktformular_weiterleitung
                send_kontaktformular_weiterleitung(
                    praxis_email=praxis_email,
                    praxis_name=praxis.name,
                    name=name,
                    email=email,
                    telefon=telefon,
                    wunschtermin=wunschtermin,
                    grund=grund,
                    nachricht=nachricht
                )
            except Exception as mail_err:
                logging.error(f"E-Mail-Weiterleitung fehlgeschlagen: {mail_err}")
        
        flash('Vielen Dank für Ihre Terminanfrage! Wir melden uns schnellstmöglich bei Ihnen.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.', 'danger')
    
    return redirect(url_for('praxis_landingpage', slug=praxis.slug) + '#termin')

@app.route("/termin-buchen/<int:praxis_id>")
def termin_buchen(praxis_id):
    """Terminbuchungsseite für eine Praxis (Dentalax Dashboard Integration)"""
    from datetime import datetime, timedelta, time as dt_time
    praxis = Praxis.query.get_or_404(praxis_id)
    
    oeffnungszeiten = Oeffnungszeit.query.filter_by(praxis_id=praxis.id).all()
    verfuegbarkeiten = Verfuegbarkeit.query.filter_by(praxis_id=praxis.id, aktiv=True).all()
    verfuegbarkeiten_vorhanden = len(verfuegbarkeiten) > 0
    
    kalender_tage = []
    freie_slots = []
    ausgewaehltes_datum = None
    behandlungsarten = Behandlungsart.query.filter_by(praxis_id=praxis.id).all()
    
    if verfuegbarkeiten_vorhanden:
        datum_str = request.args.get('datum')
        heute = datetime.now().date()
        vorlaufzeit = praxis.vorlaufzeit or 0
        fruehestes_datum = heute + timedelta(days=vorlaufzeit)
        
        if datum_str:
            try:
                ausgewaehltes_datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
                if ausgewaehltes_datum < fruehestes_datum:
                    ausgewaehltes_datum = fruehestes_datum
            except ValueError:
                ausgewaehltes_datum = fruehestes_datum
        else:
            ausgewaehltes_datum = fruehestes_datum
        
        ausnahmen = Ausnahme.query.filter_by(praxis_id=praxis.id).filter(
            Ausnahme.datum >= heute,
            Ausnahme.datum <= heute + timedelta(days=14)
        ).all()
        ausnahme_daten = {a.datum: a for a in ausnahmen}
        
        verf_nach_tag = {}
        for v in verfuegbarkeiten:
            if v.wochentag not in verf_nach_tag:
                verf_nach_tag[v.wochentag] = []
            verf_nach_tag[v.wochentag].append(v)
        
        wochentag_kurz = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
        monat_kurz = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
        
        for i in range(14):
            tag_datum = heute + timedelta(days=i)
            wochentag = tag_datum.weekday()
            hat_slots = wochentag in verf_nach_tag and tag_datum not in ausnahme_daten and tag_datum >= fruehestes_datum
            
            kalender_tage.append({
                'datum_str': tag_datum.strftime('%Y-%m-%d'),
                'wochentag': wochentag_kurz[wochentag],
                'tag': tag_datum.day,
                'monat': monat_kurz[tag_datum.month - 1],
                'ist_ausgewaehlt': tag_datum == ausgewaehltes_datum,
                'slots_verfuegbar': hat_slots
            })
        
        if ausgewaehltes_datum and ausgewaehltes_datum not in ausnahme_daten:
            wochentag = ausgewaehltes_datum.weekday()
            if wochentag in verf_nach_tag:
                bestehende_termine = Termin.query.filter_by(
                    praxis_id=praxis.id,
                    datum=ausgewaehltes_datum
                ).filter(Termin.status != 'abgesagt').all()
                belegte_zeiten = set()
                for t in bestehende_termine:
                    if t.uhrzeit:
                        belegte_zeiten.add(t.uhrzeit.strftime('%H:%M'))
                
                for v in verf_nach_tag[wochentag]:
                    current = datetime.combine(ausgewaehltes_datum, v.start_zeit)
                    ende = datetime.combine(ausgewaehltes_datum, v.end_zeit)
                    slot_dauer = v.slot_dauer or 30
                    pause = v.pause_nach_termin or 0
                    
                    while current + timedelta(minutes=slot_dauer) <= ende:
                        zeit_str = current.strftime('%H:%M')
                        if zeit_str not in belegte_zeiten:
                            if ausgewaehltes_datum > heute or (ausgewaehltes_datum == heute and current.time() > datetime.now().time()):
                                freie_slots.append({'zeit_str': zeit_str})
                        current += timedelta(minutes=slot_dauer + pause)
    
    return render_template("termin_buchen.html",
                          praxis=praxis,
                          oeffnungszeiten=oeffnungszeiten,
                          verfuegbarkeiten_vorhanden=verfuegbarkeiten_vorhanden,
                          kalender_tage=kalender_tage,
                          freie_slots=freie_slots,
                          ausgewaehltes_datum=ausgewaehltes_datum,
                          behandlungsarten=behandlungsarten,
                          meta_title=f"Termin buchen bei {praxis.name} | Dentalax",
                          meta_description=f"Buchen Sie jetzt online einen Termin bei {praxis.name} in {praxis.stadt}. Schnell, einfach und sicher.")


@app.route("/termin-buchen/<int:praxis_id>/submit", methods=["POST"])
def termin_buchen_kalender_submit(praxis_id):
    """Terminbuchung absenden"""
    from datetime import datetime
    praxis = Praxis.query.get_or_404(praxis_id)
    
    datum_str = request.form.get('datum')
    uhrzeit_str = request.form.get('uhrzeit')
    name = request.form.get('name')
    email = request.form.get('email')
    telefon = request.form.get('telefon', '')
    grund = request.form.get('grund', '')
    behandlungsart_id = request.form.get('behandlungsart_id')
    
    if not all([datum_str, uhrzeit_str, name, email]):
        flash('Bitte füllen Sie alle Pflichtfelder aus.', 'danger')
        return redirect(url_for('termin_buchen', praxis_id=praxis_id))
    
    try:
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        uhrzeit = datetime.strptime(uhrzeit_str, '%H:%M').time()
    except ValueError:
        flash('Ungültiges Datum oder Uhrzeit.', 'danger')
        return redirect(url_for('termin_buchen', praxis_id=praxis_id))
    
    neuer_termin = Termin(
        praxis_id=praxis.id,
        datum=datum,
        uhrzeit=uhrzeit,
        gast_name=name,
        gast_email=email,
        gast_telefon=telefon,
        grund=grund,
        ist_gast=True,
        status='ausstehend'
    )
    
    if behandlungsart_id:
        try:
            neuer_termin.behandlungsart_id = int(behandlungsart_id)
        except (ValueError, TypeError):
            pass
    
    db.session.add(neuer_termin)
    db.session.commit()
    
    flash(f'Ihr Terminwunsch für den {datum.strftime("%d.%m.%Y")} um {uhrzeit.strftime("%H:%M")} Uhr wurde erfolgreich übermittelt. Sie erhalten eine Bestätigung per E-Mail.', 'success')
    return redirect(url_for('termin_buchen', praxis_id=praxis_id))


# ========================================
# DASHBOARD SPEICHER-ROUTEN
# ========================================

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads/praxis')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from image_utils import optimize_and_save

@app.route("/dashboard/praxisdaten", methods=["POST"])
@login_required
def dashboard_praxisdaten_speichern():
    """Speichert die Praxis-Stammdaten aus dem Dashboard"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    # Alte Adresse speichern für Vergleich
    alte_adresse = f"{praxis.strasse}, {praxis.plz} {praxis.stadt}"
    
    praxis.name = request.form.get('name', praxis.name)
    praxis.strasse = request.form.get('strasse', praxis.strasse)
    praxis.plz = request.form.get('plz', praxis.plz)
    praxis.stadt = request.form.get('stadt', praxis.stadt)
    praxis.telefon = request.form.get('telefon', praxis.telefon)
    praxis.email = request.form.get('email', praxis.email)
    webseite_input = request.form.get('website', praxis.webseite)
    if webseite_input and not webseite_input.startswith(("http://", "https://")):
        webseite_input = "https://" + webseite_input
    praxis.webseite = webseite_input
    praxis.beschreibung = request.form.get('beschreibung', praxis.beschreibung)
    praxis.ueber_uns_text = request.form.get('ueber_uns', praxis.ueber_uns_text)
    
    # Hinweis: Leistungsschwerpunkte, Dental Match und Öffnungszeiten werden jetzt
    # im Landingpage-Bereich verwaltet (separate Routen)
    
    # Neue Adresse prüfen und Geokodierung durchführen wenn geändert
    neue_adresse = f"{praxis.strasse}, {praxis.plz} {praxis.stadt}"
    if neue_adresse != alte_adresse:
        try:
            lat, lng = get_coordinates_from_address(neue_adresse)
            if lat and lng:
                praxis.latitude = lat
                praxis.longitude = lng
                logging.info(f"Geokodierung aktualisiert für {praxis.name}: {lat}, {lng}")
        except Exception as e:
            logging.warning(f"Geokodierung fehlgeschlagen für {neue_adresse}: {e}")
    
    db.session.commit()
    flash('Praxisdaten erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))


@app.route("/dashboard/passwort", methods=["POST"])
@login_required
def dashboard_passwort_aendern():
    """Ändert das Passwort des eingeloggten Benutzers"""
    from werkzeug.security import check_password_hash, generate_password_hash
    
    aktuelles_passwort = request.form.get('aktuelles_passwort', '')
    neues_passwort = request.form.get('neues_passwort', '')
    neues_passwort_bestaetigen = request.form.get('neues_passwort_bestaetigen', '')
    
    if not aktuelles_passwort or not neues_passwort or not neues_passwort_bestaetigen:
        flash('Bitte füllen Sie alle Felder aus.', 'warning')
        return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))
    
    if not check_password_hash(current_user.password_hash, aktuelles_passwort):
        flash('Das aktuelle Passwort ist nicht korrekt.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))
    
    if neues_passwort != neues_passwort_bestaetigen:
        flash('Die neuen Passwörter stimmen nicht überein.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))
    
    if len(neues_passwort) < 8:
        flash('Das neue Passwort muss mindestens 8 Zeichen lang sein.', 'warning')
        return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))
    
    current_user.password_hash = generate_password_hash(neues_passwort)
    db.session.commit()
    
    flash('Ihr Passwort wurde erfolgreich geändert.', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='praxisdaten'))


@app.route("/dashboard/hero", methods=["POST"])
@login_required
def dashboard_hero_speichern():
    """Speichert das Hero-Bild und die Hero-Texte"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis.hero_titel = request.form.get('hero_titel', praxis.hero_titel)
    praxis.hero_untertitel = request.form.get('hero_untertitel', praxis.hero_untertitel)
    
    if 'titelbild' in request.files:
        file = request.files['titelbild']
        pfad = optimize_and_save(file, 'hero', praxis.id)
        if pfad:
            existing = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='titelbild').first()
            if existing:
                existing.pfad = pfad
            else:
                db.session.add(PraxisBild(praxis_id=praxis.id, typ='titelbild', pfad=pfad))
        elif file and file.filename:
            flash('Bild konnte nicht verarbeitet werden. Max. 10MB, erlaubte Formate: PNG, JPG, WebP.', 'warning')
    
    db.session.commit()
    flash('Hero-Bereich erfolgreich aktualisiert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseHeader'))


@app.route("/dashboard/portrait", methods=["POST"])
@login_required
def dashboard_portrait_speichern():
    """Speichert das Portrait-Bild des Praxisinhabers"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    if 'portrait_bild' in request.files:
        file = request.files['portrait_bild']
        pfad = optimize_and_save(file, 'portrait', praxis.id)
        if pfad:
            existing = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
            if existing:
                existing.pfad = pfad
            else:
                db.session.add(PraxisBild(praxis_id=praxis.id, typ='portrait', pfad=pfad))
        elif file and file.filename:
            flash('Bild konnte nicht verarbeitet werden. Max. 10MB, erlaubte Formate: PNG, JPG, WebP.', 'warning')
    
    db.session.commit()
    flash('Portrait erfolgreich aktualisiert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseAbout'))


@app.route("/dashboard/logo", methods=["POST"])
@login_required
def dashboard_logo_speichern():
    """Speichert das Praxis-Logo"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    if 'logo_bild' in request.files:
        file = request.files['logo_bild']
        pfad = optimize_and_save(file, 'logo', praxis.id)
        if pfad:
            existing = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='logo').first()
            if existing:
                existing.pfad = pfad
            else:
                db.session.add(PraxisBild(praxis_id=praxis.id, typ='logo', pfad=pfad))
        elif file and file.filename:
            flash('Bild konnte nicht verarbeitet werden. Max. 10MB, erlaubte Formate: PNG, JPG, WebP.', 'warning')
    
    db.session.commit()
    flash('Logo erfolgreich aktualisiert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseHeader'))


@app.route("/dashboard/ueber-uns-bild", methods=["POST"])
@login_required
def dashboard_ueber_uns_bild_speichern():
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    if 'ueber_uns_bild' in request.files:
        file = request.files['ueber_uns_bild']
        pfad = optimize_and_save(file, 'team', praxis.id)
        if pfad:
            existing = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='team_foto').first()
            if existing:
                existing.pfad = pfad
            else:
                db.session.add(PraxisBild(praxis_id=praxis.id, typ='team_foto', pfad=pfad))
        elif file and file.filename:
            flash('Bild konnte nicht verarbeitet werden. Max. 10MB, erlaubte Formate: PNG, JPG, WebP.', 'warning')
    
    db.session.commit()
    flash('Praxisbild erfolgreich aktualisiert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseAbout'))


@app.route("/dashboard/oeffnungszeiten", methods=["POST"])
@login_required
def dashboard_oeffnungszeiten_speichern():
    """Speichert die Öffnungszeiten"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    Oeffnungszeit.query.filter_by(praxis_id=praxis.id).delete()
    
    tage = ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']
    for i, tag in enumerate(tage):
        # HTML Checkbox sendet 'on' wenn angekreuzt, sonst wird der Key nicht gesendet
        geschlossen = f'oz_{tag}_geschlossen' in request.form
        
        if geschlossen:
            # Tag ist geschlossen
            neue_zeit = Oeffnungszeit(
                praxis_id=praxis.id,
                tag=tag.capitalize(),
                von=None,
                bis=None,
                geschlossen=True
            )
            db.session.add(neue_zeit)
        else:
            # Tag ist geöffnet - parse Zeiten
            von_str = request.form.get(f'oz_{tag}_von', '')
            bis_str = request.form.get(f'oz_{tag}_bis', '')
            von_time = None
            bis_time = None
            if von_str:
                try:
                    von_time = datetime.strptime(von_str, '%H:%M').time()
                except ValueError:
                    pass
            if bis_str:
                try:
                    bis_time = datetime.strptime(bis_str, '%H:%M').time()
                except ValueError:
                    pass
            
            neue_zeit = Oeffnungszeit(
                praxis_id=praxis.id,
                tag=tag.capitalize(),
                von=von_time,
                bis=bis_time,
                geschlossen=False
            )
            db.session.add(neue_zeit)
    
    db.session.commit()
    flash('Öffnungszeiten erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseHours'))


@app.route("/dashboard/dental-match", methods=["POST"])
@login_required
def dashboard_dental_match_speichern():
    """Speichert die Dental Match / Patientensuche Einstellungen"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis.angstpatientenfreundlich = request.form.get('angstpatientenfreundlich') == '1'
    praxis.kinderfreundlich = request.form.get('kinderfreundlich') == '1'
    praxis.barrierefrei = request.form.get('barrierefrei') == '1'
    praxis.abendsprechstunde = request.form.get('abendsprechstunde') == '1'
    praxis.samstagssprechstunde = request.form.get('samstagssprechstunde') == '1'
    praxis.sprachen = request.form.get('sprachen', 'Deutsch').strip()
    
    db.session.commit()
    flash('Dental Match Einstellungen erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseDentalMatch'))


@app.route("/dashboard/leistung", methods=["POST"])
@login_required
def dashboard_leistung_speichern():
    """Speichert eine einzelne Leistung (Legacy-Route)"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    leistung_id = request.form.get('leistung_id')
    titel = request.form.get('titel', '').strip()
    beschreibung = request.form.get('beschreibung', '').strip()
    icon = request.form.get('icon', 'fas fa-tooth')
    
    if not titel:
        flash('Bitte geben Sie einen Titel für die Leistung ein.', 'warning')
        return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseServices'))
    
    if leistung_id:
        leistung = Leistung.query.get(leistung_id)
        if leistung and leistung.praxis_id == praxis.id:
            leistung.titel = titel
            leistung.beschreibung = beschreibung
            leistung.icon = icon
    else:
        neue_leistung = Leistung(
            praxis_id=praxis.id,
            titel=titel,
            beschreibung=beschreibung,
            icon=icon
        )
        db.session.add(neue_leistung)
    
    db.session.commit()
    flash('Leistung erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseServices'))


@app.route("/dashboard/leistungen-kacheln", methods=["POST"])
@login_required
def dashboard_leistungen_kacheln_speichern():
    """Speichert die Leistungsschwerpunkte über Kachel-Auswahl"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    VORDEFINIERTE_LEISTUNGEN = {
        'implantologie': {'titel': 'Implantologie', 'icon': 'fas fa-teeth'},
        'kieferorthopaedie': {'titel': 'Kieferorthopädie', 'icon': 'fas fa-teeth-open'},
        'prophylaxe': {'titel': 'Prophylaxe', 'icon': 'fas fa-shield-alt'},
        'aesthetische-zahnheilkunde': {'titel': 'Ästhetische Zahnheilkunde', 'icon': 'fas fa-smile'},
        'kinderzahnheilkunde': {'titel': 'Kinderzahnheilkunde', 'icon': 'fas fa-baby'},
        'parodontologie': {'titel': 'Parodontologie', 'icon': 'fas fa-tooth'},
        'endodontie': {'titel': 'Endodontie', 'icon': 'fas fa-syringe'},
        'oralchirurgie': {'titel': 'Oralchirurgie', 'icon': 'fas fa-user-md'},
        'prothetik': {'titel': 'Prothetik', 'icon': 'fas fa-teeth'},
        'angstpatienten': {'titel': 'Angstpatienten', 'icon': 'fas fa-heart'}
    }
    
    selected_leistungen = request.form.get('selected_leistungen', '')
    
    praxis.leistungsschwerpunkte = selected_leistungen
    
    Leistung.query.filter_by(praxis_id=praxis.id).delete()
    
    if selected_leistungen:
        for slug in selected_leistungen.split(','):
            slug = slug.strip()
            if slug in VORDEFINIERTE_LEISTUNGEN:
                leistung_data = VORDEFINIERTE_LEISTUNGEN[slug]
                neue_leistung = Leistung(
                    praxis_id=praxis.id,
                    titel=leistung_data['titel'],
                    beschreibung='',
                    icon=leistung_data['icon']
                )
                db.session.add(neue_leistung)
    
    db.session.commit()
    flash('Leistungsschwerpunkte erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseServices'))


@app.route("/dashboard/leistung/loeschen/<int:leistung_id>", methods=["POST"])
@login_required
def dashboard_leistung_loeschen(leistung_id):
    """Löscht eine Leistung"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    leistung = Leistung.query.get(leistung_id)
    if leistung and leistung.praxis_id == current_user.praxis_id:
        db.session.delete(leistung)
        db.session.commit()
        flash('Leistung erfolgreich gelöscht.', 'success')
    else:
        flash('Leistung nicht gefunden.', 'danger')
    
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseServices'))


@app.route("/dashboard/teammitglied", methods=["POST"])
@login_required
def dashboard_teammitglied_speichern():
    """Speichert ein Teammitglied"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    mitglied_id = request.form.get('mitglied_id')
    name = request.form.get('name', '').strip()
    position = request.form.get('position', '').strip()
    beschreibung = request.form.get('beschreibung', '').strip()
    qualifikationen = request.form.get('qualifikationen', '').strip()
    schwerpunkte = request.form.get('schwerpunkte', '').strip()
    sprachen = request.form.get('sprachen', '').strip()
    
    if not name:
        flash('Bitte geben Sie einen Namen ein.', 'warning')
        return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseTeam'))
    
    bild_pfad = None
    if 'bild' in request.files:
        file = request.files['bild']
        bild_pfad = optimize_and_save(file, 'teammitglied', praxis.id)
        if not bild_pfad and file and file.filename:
            flash('Bild konnte nicht verarbeitet werden. Max. 10MB, erlaubte Formate: PNG, JPG, WebP.', 'warning')
    
    if mitglied_id:
        mitglied = TeamMitglied.query.get(mitglied_id)
        if mitglied and mitglied.praxis_id == praxis.id:
            mitglied.name = name
            mitglied.position = position
            mitglied.beschreibung = beschreibung
            mitglied.qualifikationen = qualifikationen
            mitglied.schwerpunkte = schwerpunkte
            mitglied.sprachen = sprachen
            if bild_pfad:
                mitglied.bild_pfad = bild_pfad
    else:
        neues_mitglied = TeamMitglied(
            praxis_id=praxis.id,
            name=name,
            position=position,
            beschreibung=beschreibung,
            qualifikationen=qualifikationen,
            schwerpunkte=schwerpunkte,
            sprachen=sprachen,
            bild_pfad=bild_pfad
        )
        db.session.add(neues_mitglied)
    
    db.session.commit()
    flash('Teammitglied erfolgreich gespeichert!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseTeam'))


@app.route("/dashboard/teammitglied/loeschen/<int:mitglied_id>", methods=["POST"])
@login_required
def dashboard_teammitglied_loeschen(mitglied_id):
    """Löscht ein Teammitglied"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    mitglied = TeamMitglied.query.get(mitglied_id)
    if mitglied and mitglied.praxis_id == current_user.praxis_id:
        db.session.delete(mitglied)
        db.session.commit()
        flash('Teammitglied erfolgreich gelöscht.', 'success')
    else:
        flash('Teammitglied nicht gefunden.', 'danger')
    
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseTeam'))


@app.route("/dashboard/terminbuchung", methods=["POST"])
@login_required
def dashboard_terminbuchung_speichern():
    """Speichert die Terminbuchungs-Einstellungen"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    terminbuchung_modus = request.form.get('terminbuchung_modus', 'dashboard')
    praxis.terminbuchung_modus = terminbuchung_modus
    
    # Für "fallback" ist terminbuchung_aktiv False, sonst True
    praxis.terminbuchung_aktiv = terminbuchung_modus != 'fallback'
    
    if terminbuchung_modus == 'redirect':
        url = request.form.get('terminbuchung_url', '').strip()
        if not url:
            flash('Bitte geben Sie eine gültige URL für die externe Buchung ein.', 'warning')
            return redirect(url_for('zahnarzt_dashboard') + '?page=termine')
        praxis.terminbuchung_url = url
    else:
        praxis.terminbuchung_url = None
    
    db.session.commit()
    
    modus_namen = {
        'dashboard': 'Dentalax Kalender',
        'formular': 'Kontaktformular',
        'redirect': 'Externer Link',
        'fallback': 'Nur Kontaktdaten'
    }
    flash(f'Terminbuchung auf "{modus_namen.get(terminbuchung_modus, terminbuchung_modus)}" eingestellt.', 'success')
    return redirect(url_for('zahnarzt_dashboard') + '?page=termine')


@app.route("/dashboard/veroeffentlichen", methods=["POST"])
@login_required
def dashboard_veroeffentlichen():
    """Veröffentlicht oder deaktiviert die Landingpage (Toggle)"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    if not praxis.slug:
        praxis.slug = slugify(f"{praxis.name}-{praxis.stadt}")
    
    aktion = request.form.get('aktion', 'toggle')
    if aktion == 'deaktivieren':
        praxis.landingpage_aktiv = False
        db.session.commit()
        flash('Ihre Landingpage wurde offline genommen.', 'info')
    else:
        paket_lower = (praxis.paket or '').lower()
        if paket_lower not in ['premium', 'premiumplus', 'praxispro', 'praxisplus']:
            flash('Um Ihre Landingpage zu veröffentlichen, benötigen Sie ein Premium- oder PremiumPlus-Paket.', 'warning')
            return redirect(url_for('zahnarzt_dashboard', page='landingpage'))
        from models import Verfuegbarkeit
        if praxis.terminbuchung_modus == 'kalender':
            verfuegbarkeiten = Verfuegbarkeit.query.filter_by(praxis_id=praxis.id, aktiv=True).count()
            if verfuegbarkeiten == 0:
                skip = request.form.get('skip_warning')
                if not skip:
                    return redirect(url_for('zahnarzt_dashboard', page='landingpage', show_publish_warning='1'))
        praxis.landingpage_aktiv = True
        db.session.commit()
        flash(f'Ihre Landingpage ist jetzt live unter: /zahnarzt/{praxis.slug}', 'success')
    
    return redirect(url_for('zahnarzt_dashboard', page='landingpage'))



@app.route("/dashboard/farbschema", methods=["POST"])
@login_required
def dashboard_farbschema_speichern():
    """Speichert das gewählte Farbschema"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    farbschema = request.form.get('farbschema', 'blau')
    if farbschema in ['blau', 'gruen', 'violett', 'teal']:
        praxis.farbschema = farbschema
        db.session.commit()
        flash('Farbschema erfolgreich gespeichert!', 'success')
    else:
        flash('Ungültiges Farbschema.', 'danger')
    
    return redirect(url_for('zahnarzt_dashboard', page='landingpage', section='collapseHeader'))


@app.route("/zahnarzt/vorschau/<slug>")
@login_required
def praxis_landingpage_vorschau(slug):
    """Vorschau der Landingpage (auch vor Veröffentlichung)"""
    from flask import abort
    
    praxis = Praxis.query.filter_by(slug=slug).first()
    
    if not praxis:
        abort(404)
    
    # Nur Inhaber dürfen die Vorschau sehen
    if not hasattr(current_user, 'praxis_id') or current_user.praxis_id != praxis.id:
        abort(403)
    
    # Bilder laden
    hero_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='titelbild').first()
    logo_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='logo').first()
    ueber_uns_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='team_foto').first()
    portrait_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
    
    # Öffnungszeiten sortiert laden
    tage_reihenfolge = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    oeffnungszeiten_dict = {oz.tag: oz for oz in praxis.oeffnungszeiten}
    oeffnungszeiten = [oeffnungszeiten_dict.get(tag) for tag in tage_reihenfolge if oeffnungszeiten_dict.get(tag)]
    
    bewertungen = Bewertung.query.filter_by(praxis_id=praxis.id, status='freigegeben').order_by(Bewertung.datum.desc()).all()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    import pytz
    berlin_tz = pytz.timezone('Europe/Berlin')
    jetzt = datetime.now(berlin_tz)
    wochentag_index = jetzt.weekday()
    aktueller_tag = tage_reihenfolge[wochentag_index]
    aktuelle_zeit = jetzt.time()
    
    ist_geoeffnet = False
    schliesst_um = None
    oeffnet_naechstes = None
    
    if aktueller_tag in oeffnungszeiten_dict:
        oz_heute = oeffnungszeiten_dict[aktueller_tag]
        if not oz_heute.geschlossen and oz_heute.von and oz_heute.bis:
            if oz_heute.von <= aktuelle_zeit <= oz_heute.bis:
                ist_geoeffnet = True
                schliesst_um = oz_heute.bis.strftime('%H:%M')
            elif aktuelle_zeit < oz_heute.von:
                oeffnet_naechstes = oz_heute.von.strftime('%H:%M')
    
    if not ist_geoeffnet and not oeffnet_naechstes:
        for i in range(1, 8):
            naechster_index = (wochentag_index + i) % 7
            naechster_tag = tage_reihenfolge[naechster_index]
            if naechster_tag in oeffnungszeiten_dict:
                oz_naechster = oeffnungszeiten_dict[naechster_tag]
                if not oz_naechster.geschlossen and oz_naechster.von:
                    oeffnet_naechstes = f"{naechster_tag} {oz_naechster.von.strftime('%H:%M')}"
                    break
    
    return render_template(
        'praxis_landingpage.html',
        praxis=praxis,
        leistungen=praxis.leistungen,
        team_mitglieder=praxis.team_mitglieder,
        oeffnungszeiten=oeffnungszeiten,
        hero_bild=hero_bild,
        logo_bild=logo_bild,
        ueber_uns_bild=ueber_uns_bild,
        portrait_bild=portrait_bild,
        bewertungen=bewertungen,
        ist_geoeffnet=ist_geoeffnet,
        schliesst_um=schliesst_um,
        oeffnet_naechstes=oeffnet_naechstes,
        today=today,
        vorschau_modus=True
    )


@app.route("/dashboard/stellenangebot/erstellen", methods=["POST"])
@login_required
def dashboard_stellenangebot_erstellen():
    """Erstellt ein neues Stellenangebot"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    if praxis.paket.lower() != 'premiumplus':
        flash('Stellenangebote sind nur mit PremiumPlus verfügbar.', 'warning')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    titel = request.form.get('titel', '').strip()
    position = request.form.get('position', 'zfa')
    anstellungsart = request.form.get('anstellungsart', 'vollzeit')
    
    if not titel:
        flash('Bitte geben Sie einen Jobtitel an.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    base_slug = slugify(f"{position}-{request.form.get('standort_stadt', praxis.stadt)}-{praxis.name}")
    slug = base_slug
    counter = 1
    while Stellenangebot.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    try:
        erfahrung_jahre = int(request.form.get('erfahrung_jahre', 0) or 0)
    except (ValueError, TypeError):
        erfahrung_jahre = 0
    
    neues_stellenangebot = Stellenangebot(
        slug=slug,
        titel=titel,
        position=position,
        anstellungsart=anstellungsart,
        ueber_uns=request.form.get('ueber_uns', ''),
        aufgaben=request.form.get('aufgaben', ''),
        anforderungen=request.form.get('anforderungen', ''),
        wir_bieten=request.form.get('wir_bieten', ''),
        erfahrung_jahre=erfahrung_jahre,
        arbeitsbeginn=request.form.get('arbeitsbeginn', 'Ab sofort'),
        tags=request.form.get('tags', ''),
        standort_plz=request.form.get('standort_plz', praxis.plz),
        standort_stadt=request.form.get('standort_stadt', praxis.stadt),
        standort_strasse=praxis.strasse,
        ist_aktiv=True,
        veroeffentlicht_am=datetime.now(),
        praxis_id=praxis.id
    )
    
    db.session.add(neues_stellenangebot)
    db.session.commit()
    
    try:
        notify_matching_job_alerts(neues_stellenangebot)
    except Exception as e:
        logging.error(f"Fehler beim Job-Alert Versand: {e}")
    
    flash('Stellenangebot erfolgreich erstellt!', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))


@app.route("/dashboard/stellenangebot/<int:job_id>/toggle", methods=["POST"])
@login_required
def dashboard_stellenangebot_toggle(job_id):
    """Aktiviert/Deaktiviert ein Stellenangebot"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    job = Stellenangebot.query.get(job_id)
    if not job or job.praxis_id != current_user.praxis_id:
        flash('Stellenangebot nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    job.ist_aktiv = not job.ist_aktiv
    db.session.commit()
    
    status = 'aktiviert' if job.ist_aktiv else 'deaktiviert'
    flash(f'Stellenangebot {status}.', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))


@app.route("/dashboard/stellenangebot/<int:job_id>/loeschen", methods=["POST"])
@login_required
def dashboard_stellenangebot_loeschen(job_id):
    """Löscht ein Stellenangebot"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    job = Stellenangebot.query.get(job_id)
    if not job or job.praxis_id != current_user.praxis_id:
        flash('Stellenangebot nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    db.session.delete(job)
    db.session.commit()
    
    flash('Stellenangebot gelöscht.', 'success')
    return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))


@app.route("/dashboard/bewerbung/<int:bewerbung_id>")
@login_required
def dashboard_bewerbung_detail(bewerbung_id):
    """Zeigt Details einer Bewerbung"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    bewerbung = Bewerbung.query.get(bewerbung_id)
    if not bewerbung or bewerbung.stellenangebot.praxis_id != current_user.praxis_id:
        flash('Bewerbung nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    if bewerbung.status == 'neu':
        bewerbung.status = 'gesehen'
        bewerbung.gelesen_am = datetime.now()
        db.session.commit()
    
    return render_template('bewerbung_detail.html',
                          bewerbung=bewerbung,
                          active_page='fuer-zahnaerzte',
                          meta_title=f"Bewerbung von {bewerbung.vorname} {bewerbung.nachname} | Dentalax")


@app.route("/dashboard/bewerbung/<int:bewerbung_id>/status", methods=["POST"])
@login_required
def dashboard_bewerbung_status(bewerbung_id):
    """Aktualisiert den Status einer Bewerbung"""
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Keine Praxis zugeordnet.'}), 403
        flash('Keine Praxis zugeordnet.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    bewerbung = Bewerbung.query.get(bewerbung_id)
    if not bewerbung or bewerbung.stellenangebot.praxis_id != current_user.praxis_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Bewerbung nicht gefunden.'}), 404
        flash('Bewerbung nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    
    neuer_status = request.form.get('status', 'gesehen')
    if neuer_status in ['neu', 'gesehen', 'kontaktiert', 'abgelehnt', 'eingestellt']:
        bewerbung.status = neuer_status
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'status': neuer_status,
                'status_display': bewerbung.status_display,
                'status_farbe': bewerbung.status_farbe
            })
        flash('Status erfolgreich aktualisiert.', 'success')
    
    redirect_to = request.form.get('redirect_to', '')
    if redirect_to == 'overview':
        return redirect(url_for('zahnarzt_dashboard', page='stellenangebote'))
    return redirect(url_for('dashboard_bewerbung_detail', bewerbung_id=bewerbung_id))


@app.route("/dashboard/google-bewertungen/sync", methods=["POST"])
@login_required
def dashboard_google_sync():
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return jsonify({'success': False, 'error': 'Keine Praxis zugeordnet.'}), 403
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        return jsonify({'success': False, 'error': 'Praxis nicht gefunden.'}), 404
    
    from services.google_reviews_service import sync_praxis_google_reviews
    result = sync_praxis_google_reviews(praxis)
    
    if result.get('success'):
        return jsonify({
            'success': True,
            'rating': result.get('rating'),
            'review_count': result.get('review_count'),
            'maps_url': result.get('maps_url'),
            'sync_datum': praxis.google_sync_datum.strftime('%d.%m.%Y %H:%M') if praxis.google_sync_datum else ''
        })
    
    return jsonify({'success': False, 'error': result.get('error', 'Unbekannter Fehler')}), 400


@app.route("/dashboard/google-bewertungen/place-id", methods=["POST"])
@login_required
def dashboard_google_place_id():
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return jsonify({'success': False, 'error': 'Keine Praxis zugeordnet.'}), 403
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        return jsonify({'success': False, 'error': 'Praxis nicht gefunden.'}), 404
    
    place_id = request.form.get('google_place_id', '').strip()
    praxis.google_place_id = place_id if place_id else None
    
    if not place_id:
        praxis.google_rating = None
        praxis.google_review_count = None
        praxis.google_maps_url = None
        praxis.google_sync_datum = None
        db.session.commit()
        flash('Google Place ID entfernt.', 'info')
        return redirect(url_for('zahnarzt_dashboard', page='bewertungen'))
    
    db.session.commit()
    
    from services.google_reviews_service import sync_praxis_google_reviews
    result = sync_praxis_google_reviews(praxis)
    
    if result.get('success'):
        flash(f'Google-Bewertungen erfolgreich synchronisiert: {praxis.google_rating} Sterne ({praxis.google_review_count} Bewertungen)', 'success')
    else:
        flash(f'Google Place ID gespeichert, aber Synchronisierung fehlgeschlagen: {result.get("error", "")}', 'warning')
    
    return redirect(url_for('zahnarzt_dashboard', page='bewertungen'))


@app.route("/dashboard/google-bewertungen/suche", methods=["POST"])
@login_required
def dashboard_google_suche():
    if not hasattr(current_user, 'praxis_id') or not current_user.praxis_id:
        return jsonify({'success': False, 'error': 'Keine Praxis zugeordnet.'}), 403
    
    praxis = Praxis.query.get(current_user.praxis_id)
    if not praxis:
        return jsonify({'success': False, 'error': 'Praxis nicht gefunden.'}), 404
    
    query = request.form.get('query', '').strip()
    if not query:
        query = f"{praxis.name} Zahnarzt {praxis.stadt}"
    
    from services.google_reviews_service import search_google_place
    location = None
    if praxis.latitude and praxis.longitude:
        location = {'lat': praxis.latitude, 'lng': praxis.longitude}
    
    results = search_google_place(query, location)
    return jsonify({'success': True, 'results': results or []})
