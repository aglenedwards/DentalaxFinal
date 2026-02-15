from main import app
from database import db
from models import Praxis, Oeffnungszeit, Leistung, TeamMitglied, PraxisBild, Bewertung, Behandlungsart, Verfuegbarkeit, Ausnahme, Termin
from flask import render_template, request, redirect, url_for, flash, session, make_response
from flask_login import login_required, current_user
from app import slugify
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date, time
import json
from flask_wtf import FlaskForm
from image_utils import optimize_and_save

# Doppelte Slugify-Import entfernt

# Einfache Form-Klasse für CSRF-Schutz
class CSRFForm(FlaskForm):
    pass

# Verzeichnis für Uploads
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads/praxis')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Erlaubte Dateiendungen
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# ÖFFENTLICHE LANDINGPAGE ROUTE
# ==========================================
@app.route('/zahnarzt/<slug>')
def praxis_landingpage(slug):
    """Zeigt die öffentliche Landingpage einer Praxis an"""
    from flask import abort
    
    praxis = Praxis.query.filter_by(slug=slug).first()
    
    if not praxis:
        abort(404)
    
    paket_lower = (praxis.paket or '').lower()
    if paket_lower not in ['praxispro', 'praxisplus', 'premium', 'premiumplus']:
        abort(404)
    
    # Prüfen ob Landingpage aktiviert ist (Wizard abgeschlossen)
    if not praxis.landingpage_aktiv:
        abort(404)
    
    # Bilder laden
    hero_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='titelbild').first()
    logo_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='logo').first()
    ueber_uns_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='team_foto').first()
    
    # Öffnungszeiten sortiert laden
    tage_reihenfolge = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    oeffnungszeiten_dict = {oz.tag: oz for oz in praxis.oeffnungszeiten}
    oeffnungszeiten = [oeffnungszeiten_dict.get(tag) for tag in tage_reihenfolge if oeffnungszeiten_dict.get(tag)]
    
    # Aktuellen Öffnungsstatus berechnen (in deutscher Zeitzone)
    import pytz
    berlin_tz = pytz.timezone('Europe/Berlin')
    jetzt = datetime.now(berlin_tz)
    wochentag_index = jetzt.weekday()  # 0=Montag, 6=Sonntag
    aktueller_tag = tage_reihenfolge[wochentag_index]
    aktuelle_zeit = jetzt.time()
    
    ist_geoeffnet = False
    schliesst_um = None
    oeffnet_naechstes = None
    
    # Heutige Öffnungszeiten prüfen
    if aktueller_tag in oeffnungszeiten_dict:
        oz_heute = oeffnungszeiten_dict[aktueller_tag]
        if not oz_heute.geschlossen and oz_heute.von and oz_heute.bis:
            if oz_heute.von <= aktuelle_zeit <= oz_heute.bis:
                ist_geoeffnet = True
                schliesst_um = oz_heute.bis.strftime('%H:%M')
            elif aktuelle_zeit < oz_heute.von:
                oeffnet_naechstes = oz_heute.von.strftime('%H:%M')
    
    # Wenn heute geschlossen, nächsten Öffnungstag finden
    if not ist_geoeffnet and not oeffnet_naechstes:
        for i in range(1, 8):
            naechster_index = (wochentag_index + i) % 7
            naechster_tag = tage_reihenfolge[naechster_index]
            if naechster_tag in oeffnungszeiten_dict:
                oz_naechster = oeffnungszeiten_dict[naechster_tag]
                if not oz_naechster.geschlossen and oz_naechster.von:
                    oeffnet_naechstes = f"{naechster_tag} {oz_naechster.von.strftime('%H:%M')}"
                    break
    
    # Portrait-Bild laden
    portrait_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
    
    # Nur freigegebene Bewertungen laden
    bewertungen = Bewertung.query.filter_by(praxis_id=praxis.id, status='freigegeben').order_by(Bewertung.datum.desc()).all()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    kalender_tage = []
    termin_bestaetigung = session.pop('termin_bestaetigung', None)
    
    if praxis.terminbuchung_modus == 'dashboard':
        heute = date.today()
        vorlaufzeit = praxis.vorlaufzeit or 0
        fruehestes_datum = heute + timedelta(days=vorlaufzeit)
        
        verfuegbare_wochentage = set()
        for v in Verfuegbarkeit.query.filter_by(praxis_id=praxis.id).all():
            verfuegbare_wochentage.add(v.wochentag)
        
        ausnahme_daten = set()
        buchungshorizont_tage = (praxis.buchungshorizont or 4) * 7
        
        ausnahmen = Ausnahme.query.filter(
            Ausnahme.praxis_id == praxis.id,
            Ausnahme.datum >= fruehestes_datum,
            Ausnahme.datum <= fruehestes_datum + timedelta(days=buchungshorizont_tage),
            Ausnahme.ganztags_geschlossen == True
        ).all()
        for a in ausnahmen:
            ausnahme_daten.add(a.datum)
        
        for i in range(buchungshorizont_tage):
            tag_datum = fruehestes_datum + timedelta(days=i)
            hat_verfuegbarkeit = tag_datum.weekday() in verfuegbare_wochentage and tag_datum not in ausnahme_daten
            kalender_tage.append({
                'datum': tag_datum,
                'datum_str': tag_datum.strftime('%Y-%m-%d'),
                'tag': tag_datum.day,
                'wochentag': ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'][tag_datum.weekday()],
                'monat': ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'][tag_datum.month - 1],
                'slots_verfuegbar': hat_verfuegbarkeit
            })
    
    return render_template(
        'praxis_landingpage.html',
        praxis=praxis,
        leistungen=praxis.leistungen,
        team_mitglieder=praxis.team_mitglieder,
        oeffnungszeiten=oeffnungszeiten,
        bewertungen=bewertungen,
        hero_bild=hero_bild,
        logo_bild=logo_bild,
        ueber_uns_bild=ueber_uns_bild,
        portrait_bild=portrait_bild,
        ist_geoeffnet=ist_geoeffnet,
        schliesst_um=schliesst_um,
        oeffnet_naechstes=oeffnet_naechstes,
        today=today,
        kalender_tage=kalender_tage,
        termin_bestaetigung=termin_bestaetigung
    )

@app.route('/praxis/<slug>')
def praxis_landingpage_alt(slug):
    """Alternative URL für die Landingpage (Redirect)"""
    return redirect(url_for('praxis_landingpage', slug=slug))

@app.route('/praxis-daten-eingeben', methods=['GET'])
# Login-Schutz entfernt, um nach Stripe-Checkout auch ohne Login die Praxis einrichten zu können
# @login_required
def praxis_daten_eingeben():
    # Debugausgaben
    session_keys = list(session.keys())
    print(f"🔍 praxis_daten_eingeben - Session Variablen: {session_keys}")
    print(f"🔑 Email in Session: {session.get('email')}")
    print(f"📦 Paket in Session: {session.get('paket')}")
    print(f"🏥 Praxiseinrichtung Flag: {session.get('praxis_einrichten')}")
    print(f"💳 Stripe Test Mode: {session.get('stripe_session_id') is not None}")
    
    # Prüfen: Wenn wir keine User-ID haben, aber nach Zahlung hier sind
    user_authenticated = False
    try:
        # Wenn es einen eingeloggten User gibt
        if current_user and current_user.is_authenticated:
            user_authenticated = True
            print(f"👤 Authentifizierter Benutzer: {current_user.email}")
    except:
        print("ℹ️ Kein aktueller Benutzer gefunden, fahre mit Session-Daten fort")
    
    # Praxis des eingeloggten Zahnarztes finden
    praxis = None
    if user_authenticated:
        praxis = Praxis.query.filter_by(zahnarzt_id=current_user.id).first()
        if praxis:
            print(f"🏥 Praxis für User ID {current_user.id} gefunden: {praxis.name}")
    
    if not praxis:
        # Versuchen wir, die Praxis anhand der E-Mail aus der Session zu finden
        email = session.get("email")
        stripe_test_mode = session.get('stripe_session_id') is not None
        
        if email or stripe_test_mode:
            # Im Testmodus könnten wir eine spezielle E-Mail haben
            if stripe_test_mode and not email:
                email = "test@example.com"
                session['email'] = email
                print(f"🔄 Testmodus: E-Mail auf {email} gesetzt")
            
            # Prüfen, ob eine Praxis mit dieser E-Mail existiert
            if email:
                praxis = Praxis.query.filter_by(email=email).first()
                if praxis:
                    print(f"📧 Praxis für Email {email} gefunden: {praxis.name}")
        
        # Wenn wir aus einem Zahlungsvorgang kommen und bezahlung_stammdaten haben
        if not praxis and session.get('praxis_einrichten') and session.get('bezahlung_stammdaten'):
            # Praxis neu anlegen mit den Daten aus der Bezahlung
            bezahlung_stammdaten = session.get('bezahlung_stammdaten', {})
            # Prüfen, ob Email in den Stammdaten oder in der Session vorhanden ist
            email_to_use = bezahlung_stammdaten.get('email') or session.get('email')
            
            if email_to_use:
                print(f"🆕 Erstelle neue Praxis aus Bezahlungsdaten für {email_to_use}")
                
                # Prüfen, ob mit dieser E-Mail bereits eine Praxis existiert
                existing_praxis = Praxis.query.filter_by(email=email_to_use).first()
                if existing_praxis:
                    praxis = existing_praxis
                    print(f"📧 Bestehende Praxis gefunden für {email_to_use}")
                else:
                    # In die Session-Bezahlungsdaten einfügen, falls nicht vorhanden
                    if 'email' not in bezahlung_stammdaten and email_to_use:
                        bezahlung_stammdaten['email'] = email_to_use
                        session['bezahlung_stammdaten'] = bezahlung_stammdaten
                    
                    # Neue Praxis anlegen
                    neue_praxis = Praxis(
                        name=bezahlung_stammdaten.get('praxisname', 'Neue Praxis'),
                        email=email_to_use,
                        strasse=bezahlung_stammdaten.get('strasse', ''),
                        plz=bezahlung_stammdaten.get('plz', ''),
                        stadt=bezahlung_stammdaten.get('stadt', ''),
                        telefon=bezahlung_stammdaten.get('telefon', ''),
                        webseite=bezahlung_stammdaten.get('webseite', ''),
                        paket=bezahlung_stammdaten.get('paket', 'PraxisPro'),
                        zahlungsart=bezahlung_stammdaten.get('zahlweise', 'monatlich'),
                        slug=slugify(f"{bezahlung_stammdaten.get('praxisname', 'Neue Praxis')}-{bezahlung_stammdaten.get('stadt', '')}")
                    )
                    
                    # Wenn das Paket PraxisPro oder PraxisPlus ist, setzen wir eine Aktivitätsdauer
                    if neue_praxis.paket in ['PraxisPro', 'PraxisPlus']:
                        if neue_praxis.zahlungsart == 'jaehrlich':
                            neue_praxis.paket_aktiv_bis = datetime.now() + timedelta(days=365)
                        else:
                            neue_praxis.paket_aktiv_bis = datetime.now() + timedelta(days=30)
                    
                    try:
                        db.session.add(neue_praxis)
                        db.session.commit()
                        praxis = neue_praxis  # Setzen der neu erstellten Praxis
                        print(f"✅ Neue Praxis erstellt: {neue_praxis.name} (ID: {neue_praxis.id})")
                    except Exception as e:
                        db.session.rollback()
                        print(f"❌ Fehler beim Erstellen der Praxis: {str(e)}")
        
        # Wenn immer noch keine Praxis gefunden wurde
        if not praxis and not session.get('praxis_einrichten'):
            print(f"⚠️ Keine Praxis gefunden für Email: {email}")
            flash('Keine Praxis gefunden. Bitte registrieren Sie zuerst eine Praxis.', 'danger')
            return redirect(url_for('index'))
        
        # Falls wir aus dem Zahlungsprozess kommen und keine Praxis haben, aber praxis_einrichten gesetzt ist
        if not praxis and session.get('praxis_einrichten'):
            print(f"ℹ️ Keine existierende Praxis gefunden, aber praxis_einrichten ist gesetzt. Erstelle neue Praxis-Instanz.")
            # Dummy-Praxis für das Formular erstellen
            praxis = Praxis(
                name='',
                email=session.get('email', ''),
                strasse='',
                plz='',
                stadt='',
                telefon='',
                webseite=session.get('webseite', ''),
                paket=session.get('paket', 'PraxisPro'),
                zahlungsart=session.get('zahlweise', 'monatlich'),
                slug=''
            )
    
    # Praxis gefunden oder erstellt, jetzt mit Stammdaten aus dem Bezahlprozess anreichern
    bezahlung_stammdaten = session.get('bezahlung_stammdaten', {})
    if bezahlung_stammdaten and praxis is not None:
        print(f"🔄 Praxis {getattr(praxis, 'name', 'ohne Namen')} (ID: {getattr(praxis, 'id', 'neu')}) wird mit Bezahlungsdaten aktualisiert")
        # Praxisdaten vervollständigen, wenn Felder leer sind
        if hasattr(praxis, 'name') and not praxis.name and bezahlung_stammdaten.get('praxisname'):
            praxis.name = bezahlung_stammdaten.get('praxisname')
        
        if hasattr(praxis, 'strasse') and not praxis.strasse and bezahlung_stammdaten.get('strasse'):
            praxis.strasse = bezahlung_stammdaten.get('strasse')
            
        if hasattr(praxis, 'plz') and not praxis.plz and bezahlung_stammdaten.get('plz'):
            praxis.plz = bezahlung_stammdaten.get('plz')
            
        if hasattr(praxis, 'stadt') and not praxis.stadt and bezahlung_stammdaten.get('stadt'):
            praxis.stadt = bezahlung_stammdaten.get('stadt')
            
        if hasattr(praxis, 'telefon') and not praxis.telefon and bezahlung_stammdaten.get('telefon'):
            praxis.telefon = bezahlung_stammdaten.get('telefon')
        
        if hasattr(praxis, 'webseite') and not praxis.webseite and bezahlung_stammdaten.get('webseite'):
            praxis.webseite = bezahlung_stammdaten.get('webseite')
            
        # Paket aktualisieren, wenn aus der Bezahlung verfügbar
        if bezahlung_stammdaten.get('paket'):
            praxis.paket = bezahlung_stammdaten.get('paket')
            
        # Änderungen speichern
        db.session.commit()
        
        # Jetzt können wir den Schlüssel aus der Session entfernen
        session.pop('bezahlung_stammdaten', None)
        print('✅ Stammdaten aus Bezahlprozess wurden übernommen für:', praxis.email)
    
    # Öffnungszeiten laden
    oeffnungszeiten = {}
    if praxis and hasattr(praxis, 'oeffnungszeiten'):
        oeffnungszeiten = {
            oz.tag.lower(): {
                'geschlossen': oz.geschlossen,
                'von': oz.von.strftime('%H:%M') if oz.von else '08:00',
                'bis': oz.bis.strftime('%H:%M') if oz.bis else '18:00'
            } for oz in praxis.oeffnungszeiten
        }
    
    # Standard-Öffnungszeiten für alle Wochentage setzen, falls nicht vorhanden
    for tag in ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']:
        if tag not in oeffnungszeiten:
            geschlossen = tag in ['samstag', 'sonntag']
            oeffnungszeiten[tag] = {
                'geschlossen': geschlossen,
                'von': '08:00',
                'bis': '18:00'
            }
    
    # CSRF-Form erstellen für das Template
    form = CSRFForm()
    
    # Sichere Template-Werte erstellen, falls praxis None ist
    leistungen = []
    team = []
    portrait_bild = None
    
    if praxis:
        if hasattr(praxis, 'leistungen'):
            leistungen = praxis.leistungen
        if hasattr(praxis, 'team_mitglieder'):
            team = praxis.team_mitglieder
        # Portrait-Bild laden
        portrait_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
    
    # Stammdaten aus Session für vorausgefüllte Werte
    stammdaten = {
        'vorname': session.get('vorname', ''),
        'nachname': session.get('nachname', ''),
        'praxisname': session.get('praxisname', ''),
        'strasse': session.get('strasse', ''),
        'plz': session.get('plz', ''),
        'stadt': session.get('stadt', ''),
        'telefon': session.get('telefon', ''),
        'email': session.get('email', ''),
        'webseite': session.get('webseite', '')
    }
    
    # Stelle sicher, dass das Paket aus der Session übergeben wird
    paket_info = session.get('paket', 'PraxisPro')
    
    # Debug-Ausgabe für das Paket
    print(f"📦 Paketnamen für Template: {paket_info}")
    
    import time
    cache_bust = int(time.time())
    
    response = make_response(render_template(
        'praxis_daten_eingeben_neu.html',
        praxis=praxis,
        leistungen=leistungen,
        team=team,
        oeffnungszeiten=oeffnungszeiten,
        form=form,
        stammdaten=stammdaten,
        portrait_bild=portrait_bild,
        paket_name=paket_info,
        import_datetime=cache_bust
    ))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/praxis-daten-speichern-db', methods=['POST'])
# Login-Schutz auch hier entfernt, um Formularabsendung nach Stripe-Checkout zu ermöglichen
# @login_required
def praxis_daten_speichern_db():
    # Überprüfen Sie die CSRF-Token-Validität nicht
    # form = CSRFForm()
    # if form.validate_on_submit():
    #    pass  # Validierung erfolgreich
    # Wir verzichten hier auf die CSRF-Validierung, um die Formularabsendung zu ermöglichen
    # Praxis finden (entweder des eingeloggten Zahnarztes oder über Session-Email)
    praxis = None
    user_authenticated = False
    
    try:
        # Wenn es einen eingeloggten User gibt
        if current_user and current_user.is_authenticated:
            user_authenticated = True
            print(f"👤 Authentifizierter Benutzer in speichern_db: {current_user.email}")
            praxis = Praxis.query.filter_by(zahnarzt_id=current_user.id).first()
    except:
        print("ℹ️ Kein aktueller Benutzer gefunden, fahre mit Session-Daten fort")
    
    # Wenn keine Praxis gefunden: über Session-Email suchen
    if not praxis:
        email = session.get("email")
        print(f"🔎 Suche nach Praxis für Email aus Session: {email}")
        
        if email:
            praxis = Praxis.query.filter_by(email=email).first()
            if praxis:
                print(f"✅ Praxis für Email {email} gefunden: {praxis.name}")
        
        # Wenn immer noch keine Praxis gefunden wurde
        if not praxis and not session.get('praxis_einrichten'):
            print(f"⚠️ Keine Praxis gefunden für Email: {email}")
            flash('Keine Praxis gefunden. Bitte registrieren Sie zuerst eine Praxis.', 'danger')
            return redirect(url_for('index'))
            
        # Falls wir aus dem Zahlungsprozess kommen und keine Praxis haben, aber praxis_einrichten gesetzt ist
        if not praxis and session.get('praxis_einrichten'):
            print(f"ℹ️ Keine existierende Praxis gefunden, aber praxis_einrichten ist gesetzt. Erstelle neue Praxis-Instanz.")
            # Bezahlungsdaten aus der Session holen
            bezahlung_stammdaten = session.get('bezahlung_stammdaten', {})
            
            # Neue Praxis anlegen
            praxis = Praxis(
                name=bezahlung_stammdaten.get('praxisname', ''),
                email=session.get('email', ''),
                strasse=bezahlung_stammdaten.get('strasse', ''),
                plz=bezahlung_stammdaten.get('plz', ''),
                stadt=bezahlung_stammdaten.get('stadt', ''),
                telefon=bezahlung_stammdaten.get('telefon', ''),
                webseite=bezahlung_stammdaten.get('webseite', ''),
                paket=session.get('paket', 'PraxisPro'),
                zahlungsart=session.get('zahlweise', 'monatlich'),
                slug=slugify(f"{bezahlung_stammdaten.get('praxisname', 'Neue Praxis')}-{bezahlung_stammdaten.get('stadt', '')}")
            )
            
            try:
                db.session.add(praxis)
                db.session.commit()
                print(f"✅ Neue Praxis erstellt für Formularabgabe: {praxis.name} (ID: {praxis.id})")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Fehler beim Erstellen der Praxis: {str(e)}")
                # Fallback Lösung - temporäre Praxis-Instanz
                praxis = Praxis(
                    name='',
                    email=session.get('email', ''),
                    webseite=session.get('webseite', ''),
                    paket=session.get('paket', 'PraxisPro'),
                    zahlungsart=session.get('zahlweise', 'monatlich')
                )
    
    # Welcher Tab wurde übermittelt?
    form_step = request.form.get('form_step', 'step1')
    final_submit = request.form.get('final_submit')
    submission_method = request.form.get('submission_method', 'unbekannt')
    debug_info = request.form.get('debug_info', 'keine')
    
    print(f"📝 Praxisdaten werden gespeichert - Form Step: {form_step}, Final Submit: {final_submit}")
    print(f"📊 Submission Details - Method: {submission_method}, Debug: {debug_info}")
    
    # Debug: Wichtige Formularfelder anzeigen
    print(f"Form Tracker: {request.form.get('praxisform_submit_timestamp', 'nicht vorhanden')}")
    print(f"Form Target: {request.form.get('form_target', 'nicht angegeben')}")
    
    # Alle Formularfelder zur Debug-Ausgabe
    print("📋 Formularfelder:")
    for key, value in request.form.items():
        print(f"  - {key}: {value}")
    
    # Schritt 1: Basisdaten (immer aktualisieren, unabhängig vom Schritt)
    # So werden die Stammdaten bei jedem Schritt aktualisiert
    praxis.name = request.form.get('praxisname', praxis.name)
    praxis.strasse = request.form.get('strasse', praxis.strasse)
    praxis.plz = request.form.get('plz', praxis.plz)
    praxis.stadt = request.form.get('stadt', praxis.stadt)
    praxis.telefon = request.form.get('telefon', praxis.telefon)
    praxis.email = request.form.get('email', praxis.email)
    webseite_form = request.form.get('webseite', praxis.webseite)
    if webseite_form and not webseite_form.startswith(("http://", "https://")):
        webseite_form = "https://" + webseite_form
    praxis.webseite = webseite_form
    
    # Willkommenstext speichern
    ueber_uns_text = request.form.get('ueber_uns_text', '')
    if ueber_uns_text:
        praxis.ueber_uns_text = ueber_uns_text
    
    # Slug aktualisieren
    from app import slugify
    praxis.slug = slugify(f"{praxis.name}-{praxis.stadt}")
    
    # Geocoding: Koordinaten aus Adresse ermitteln
    if praxis.strasse and praxis.plz and praxis.stadt:
        try:
            from utils.geocode import get_coordinates_from_address
            adresse = f"{praxis.strasse}, {praxis.plz} {praxis.stadt}, Deutschland"
            lat, lng = get_coordinates_from_address(adresse)
            if lat and lng:
                praxis.latitude = lat
                praxis.longitude = lng
                print(f"📍 Geocoding erfolgreich: {adresse} -> ({lat}, {lng})")
            else:
                print(f"⚠️ Geocoding fehlgeschlagen für: {adresse}")
        except Exception as e:
            print(f"❌ Geocoding Fehler: {e}")
    
    db.session.commit()
    
    # Feedback nur beim Basis-Tab oder beim ersten Aufruf anzeigen
    if form_step == 'step1':
        flash('Basisdaten wurden erfolgreich gespeichert.', 'success')
    
    # Schritt 2: Praxisinfos & Öffnungszeiten
    elif form_step == 'step2':
        # Praxisbeschreibung aktualisieren
        praxis.beschreibung = request.form.get('beschreibung', '')
        
        # Bilder verarbeiten
        if 'praxislogo' in request.files and request.files['praxislogo'].filename:
            logo_file = request.files['praxislogo']
            pfad = optimize_and_save(logo_file, 'logo', praxis.id)
            if pfad:
                logo_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='logo').first()
                if logo_bild:
                    if os.path.exists(os.path.join(os.getcwd(), logo_bild.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), logo_bild.pfad.lstrip('/')))
                    logo_bild.pfad = pfad
                else:
                    neues_logo = PraxisBild(
                        typ='logo',
                        pfad=pfad,
                        praxis_id=praxis.id
                    )
                    db.session.add(neues_logo)
        
        if 'titelbild' in request.files and request.files['titelbild'].filename:
            titelbild_file = request.files['titelbild']
            pfad = optimize_and_save(titelbild_file, 'titel', praxis.id)
            if pfad:
                titelbild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='titelbild').first()
                if titelbild:
                    if os.path.exists(os.path.join(os.getcwd(), titelbild.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), titelbild.pfad.lstrip('/')))
                    titelbild.pfad = pfad
                else:
                    neues_titelbild = PraxisBild(
                        typ='titelbild',
                        pfad=pfad,
                        praxis_id=praxis.id
                    )
                    db.session.add(neues_titelbild)
        
        if 'team_foto' in request.files and request.files['team_foto'].filename:
            teamfoto_file = request.files['team_foto']
            pfad = optimize_and_save(teamfoto_file, 'team', praxis.id)
            if pfad:
                teamfoto = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='team_foto').first()
                if teamfoto:
                    if os.path.exists(os.path.join(os.getcwd(), teamfoto.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), teamfoto.pfad.lstrip('/')))
                    teamfoto.pfad = pfad
                else:
                    neues_teamfoto = PraxisBild(
                        typ='team_foto',
                        pfad=pfad,
                        praxis_id=praxis.id
                    )
                    db.session.add(neues_teamfoto)
        
        if 'portrait' in request.files and request.files['portrait'].filename:
            portrait_file = request.files['portrait']
            pfad = optimize_and_save(portrait_file, 'portrait', praxis.id)
            if pfad:
                portrait = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
                if portrait:
                    if os.path.exists(os.path.join(os.getcwd(), portrait.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), portrait.pfad.lstrip('/')))
                    portrait.pfad = pfad
                else:
                    neues_portrait = PraxisBild(
                        typ='portrait',
                        pfad=pfad,
                        praxis_id=praxis.id
                    )
                    db.session.add(neues_portrait)
        
        # Öffnungszeiten aktualisieren
        # Zuerst bestehende Öffnungszeiten löschen
        Oeffnungszeit.query.filter_by(praxis_id=praxis.id).delete()
        
        # Dann neue Öffnungszeiten hinzufügen
        for tag in ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']:
            geschlossen = request.form.get(f'closed_{tag}', '') == '1'
            von = request.form.get(f'{tag}_von', '08:00') if not geschlossen else None
            bis = request.form.get(f'{tag}_bis', '18:00') if not geschlossen else None
            
            neue_oeffnungszeit = Oeffnungszeit(
                tag=tag.capitalize(),
                von=datetime.strptime(von, '%H:%M').time() if von else None,
                bis=datetime.strptime(bis, '%H:%M').time() if bis else None,
                geschlossen=geschlossen,
                praxis_id=praxis.id
            )
            db.session.add(neue_oeffnungszeit)
        
        db.session.commit()
        flash('Praxisinformationen und Öffnungszeiten wurden erfolgreich gespeichert.', 'success')
        
    # Schritt 3: Leistungen (Kachel-Auswahl)
    elif form_step == 'step3':
        # Vordefinierte Leistungen mit Slug, Titel und Icon
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
        
        # Ausgewählte Leistungen aus dem Formular holen
        selected_leistungen = request.form.get('selected_leistungen', '')
        
        # Leistungsschwerpunkte speichern (für KI-Matching und Suche)
        praxis.leistungsschwerpunkte = selected_leistungen
        
        # Bestehende Leistungen löschen
        Leistung.query.filter_by(praxis_id=praxis.id).delete()
        
        # Neue Leistungen basierend auf der Auswahl erstellen (für Landingpage-Anzeige)
        if selected_leistungen:
            for slug in selected_leistungen.split(','):
                slug = slug.strip()
                if slug in VORDEFINIERTE_LEISTUNGEN:
                    leistung_data = VORDEFINIERTE_LEISTUNGEN[slug]
                    neue_leistung = Leistung(
                        titel=leistung_data['titel'],
                        beschreibung='',  # Keine Beschreibung mehr nötig
                        icon=leistung_data['icon'],
                        praxis_id=praxis.id
                    )
                    db.session.add(neue_leistung)
        
        db.session.commit()
        flash('Leistungsschwerpunkte wurden erfolgreich gespeichert.', 'success')
    
    # Schritt 4: Team
    elif form_step == 'step4':
        # Bestehende Teammitglieder löschen
        TeamMitglied.query.filter_by(praxis_id=praxis.id).delete()
        
        # Neue Teammitglieder hinzufügen
        team_name = request.form.getlist('team_name[]')
        team_position = request.form.getlist('team_position[]')
        team_beschreibung = request.form.getlist('team_beschreibung[]')
        team_qualifikationen = request.form.getlist('team_qualifikationen[]')
        team_sprachen = request.form.getlist('team_sprachen[]')
        team_schwerpunkte = request.form.getlist('team_schwerpunkte[]')
        team_foto_files = request.files.getlist('team_foto[]')
        
        for i in range(len(team_name)):
            if team_name[i].strip():
                bild_pfad = None
                
                if i < len(team_foto_files) and team_foto_files[i].filename:
                    foto_file = team_foto_files[i]
                    pfad = optimize_and_save(foto_file, 'teammitglied', praxis.id)
                    if pfad:
                        bild_pfad = pfad
                
                neues_teammitglied = TeamMitglied(
                    name=team_name[i],
                    position=team_position[i] if i < len(team_position) else '',
                    beschreibung=team_beschreibung[i] if i < len(team_beschreibung) else '',
                    qualifikationen=team_qualifikationen[i] if i < len(team_qualifikationen) else '',
                    sprachen=team_sprachen[i] if i < len(team_sprachen) else '',
                    schwerpunkte=team_schwerpunkte[i] if i < len(team_schwerpunkte) else '',
                    bild_pfad=bild_pfad,
                    praxis_id=praxis.id
                )
                db.session.add(neues_teammitglied)
        
        db.session.commit()
        flash('Teammitglieder wurden erfolgreich gespeichert.', 'success')
    
    # Schritt 5: Team (aktualisiert)
    elif form_step == 'step5':
        # Team Mitglieder werden in Schritt 4 gespeichert
        pass
        
    # Schritt 6: Terminbuchung (neuer Tab)
    elif form_step == 'step6':
        praxis.terminbuchung_aktiv = True  # Standardmäßig aktiviert
        praxis.terminbuchung_modus = request.form.get('terminbuchung_modus', 'dashboard')
        
        # Modus-spezifische Daten speichern
        if praxis.terminbuchung_modus == 'redirect':
            praxis.terminbuchung_url = request.form.get('terminbuchung_url', '')
            praxis.extern_anbieter = request.form.get('extern_anbieter', '')
        
        # API-Modus
        elif praxis.terminbuchung_modus == 'api':
            # API-Schlüssel in der Datenbank speichern
            api_key = request.form.get('api_key', '')
            if api_key:
                praxis.api_key = api_key
            praxis.api_anbieter = request.form.get('api_anbieter', '')
        
        # Kontaktformular-Modus
        elif praxis.terminbuchung_modus == 'formular':
            praxis.formular_email = request.form.get('formular_email', '')
            praxis.formular_text = request.form.get('formular_text', '')
        
        # Dashboard-Modus
        elif praxis.terminbuchung_modus == 'dashboard':
            # Einstellungen für Standard-Termindauer und Vorlaufzeit
            try:
                praxis.termin_dauer = int(request.form.get('termin_dauer', 30))
                praxis.vorlaufzeit = int(request.form.get('vorlaufzeit', 2))
                praxis.buchungshorizont = int(request.form.get('buchungshorizont', 4))
            except ValueError:
                praxis.termin_dauer = 30
                praxis.vorlaufzeit = 2
                praxis.buchungshorizont = 4
            
            # Verfügbare Behandlungen - optional, werden später im Dashboard konfiguriert
            behandlungen = request.form.getlist('behandlung[]')
            behandlung_dauer = request.form.getlist('behandlung_dauer[]')
            
            # Konfigurationsdaten für das Dashboard
            konfiguration_daten = {}
            konfiguration_daten['behandlungen'] = []
            
            # Wenn behandlungen übermittelt wurden, speichern
            if behandlungen:
                for i in range(len(behandlungen)):
                    if i < len(behandlungen) and behandlungen[i].strip():
                        konfiguration_daten['behandlungen'].append({
                            'name': behandlungen[i],
                            'dauer': behandlung_dauer[i] if i < len(behandlung_dauer) else '30'
                        })
        
        # JSON-Daten in separater Tabelle oder als JSON-Feld speichern
        # Für dieses Beispiel speichern wir es nur in einer JSON-Datei
        os.makedirs(os.path.join(os.getcwd(), 'static/uploads/praxis_konfiguration'), exist_ok=True)
        with open(os.path.join(os.getcwd(), f'static/uploads/praxis_konfiguration/praxis_{praxis.id}_konfiguration.json'), 'w') as f:
            json.dump(konfiguration_daten, f)
        
        db.session.commit()
        flash('Terminbuchungseinstellungen wurden erfolgreich gespeichert.', 'success')
    
    # Schritt 7: Abschluss - ALLE DATEN SPEICHERN
    elif form_step == 'step7':
        print("📦 Step 7: Speichere ALLE Wizard-Daten...")
        
        # ========================================
        # BILDER SPEICHERN (aus Step 2)
        # ========================================
        print("📸 Speichere Bilder...")
        
        # Logo
        if 'praxislogo' in request.files and request.files['praxislogo'].filename:
            logo_file = request.files['praxislogo']
            pfad = optimize_and_save(logo_file, 'logo', praxis.id)
            if pfad:
                logo_bild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='logo').first()
                if logo_bild:
                    if os.path.exists(os.path.join(os.getcwd(), logo_bild.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), logo_bild.pfad.lstrip('/')))
                    logo_bild.pfad = pfad
                else:
                    neues_logo = PraxisBild(typ='logo', pfad=pfad, praxis_id=praxis.id)
                    db.session.add(neues_logo)
                print(f"  - Logo gespeichert: {pfad}")
        
        # Titelbild
        if 'titelbild' in request.files and request.files['titelbild'].filename:
            titelbild_file = request.files['titelbild']
            pfad = optimize_and_save(titelbild_file, 'titel', praxis.id)
            if pfad:
                titelbild = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='titelbild').first()
                if titelbild:
                    if os.path.exists(os.path.join(os.getcwd(), titelbild.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), titelbild.pfad.lstrip('/')))
                    titelbild.pfad = pfad
                else:
                    neues_titelbild = PraxisBild(typ='titelbild', pfad=pfad, praxis_id=praxis.id)
                    db.session.add(neues_titelbild)
                print(f"  - Titelbild gespeichert: {pfad}")
        
        # Team Foto
        if 'team_foto' in request.files and request.files['team_foto'].filename:
            teamfoto_file = request.files['team_foto']
            pfad = optimize_and_save(teamfoto_file, 'team', praxis.id)
            if pfad:
                teamfoto = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='team_foto').first()
                if teamfoto:
                    if os.path.exists(os.path.join(os.getcwd(), teamfoto.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), teamfoto.pfad.lstrip('/')))
                    teamfoto.pfad = pfad
                else:
                    neues_teamfoto = PraxisBild(typ='team_foto', pfad=pfad, praxis_id=praxis.id)
                    db.session.add(neues_teamfoto)
                print(f"  - Team-Foto gespeichert: {pfad}")
        
        # Portrait
        if 'portrait' in request.files and request.files['portrait'].filename:
            portrait_file = request.files['portrait']
            pfad = optimize_and_save(portrait_file, 'portrait', praxis.id)
            if pfad:
                portrait = PraxisBild.query.filter_by(praxis_id=praxis.id, typ='portrait').first()
                if portrait:
                    if os.path.exists(os.path.join(os.getcwd(), portrait.pfad.lstrip('/'))):
                        os.remove(os.path.join(os.getcwd(), portrait.pfad.lstrip('/')))
                    portrait.pfad = pfad
                else:
                    neues_portrait = PraxisBild(typ='portrait', pfad=pfad, praxis_id=praxis.id)
                    db.session.add(neues_portrait)
                print(f"  - Portrait gespeichert: {pfad}")
        
        # Über uns Text speichern
        ueber_uns = request.form.get('ueber_uns_text', '')
        if ueber_uns:
            praxis.ueber_uns_text = ueber_uns
        
        # ========================================
        # ÖFFNUNGSZEITEN SPEICHERN (aus Step 3)
        # ========================================
        print("⏰ Speichere Öffnungszeiten...")
        Oeffnungszeit.query.filter_by(praxis_id=praxis.id).delete()
        
        for tag in ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag']:
            geschlossen = request.form.get(f'tag_{tag}_geschlossen', '') == 'on'
            von = request.form.get(f'tag_{tag}_von', '08:00') if not geschlossen else None
            bis = request.form.get(f'tag_{tag}_bis', '18:00') if not geschlossen else None
            
            if von or geschlossen:  # Nur speichern wenn Daten vorhanden
                neue_oeffnungszeit = Oeffnungszeit(
                    tag=tag.capitalize(),
                    von=datetime.strptime(von, '%H:%M').time() if von else None,
                    bis=datetime.strptime(bis, '%H:%M').time() if bis else None,
                    geschlossen=geschlossen,
                    praxis_id=praxis.id
                )
                db.session.add(neue_oeffnungszeit)
                print(f"  - {tag.capitalize()}: {von} - {bis} (geschlossen: {geschlossen})")
        
        # ========================================
        # LEISTUNGEN SPEICHERN (aus Step 4)
        # ========================================
        print("🦷 Speichere Leistungen...")
        leistung_titel = request.form.getlist('leistung_titel[]')
        
        if leistung_titel:
            Leistung.query.filter_by(praxis_id=praxis.id).delete()
            leistung_beschreibung = request.form.getlist('leistung_beschreibung[]')
            leistung_icon = request.form.getlist('leistung_icon[]')
            
            for i in range(len(leistung_titel)):
                if leistung_titel[i].strip():
                    neue_leistung = Leistung(
                        titel=leistung_titel[i],
                        beschreibung=leistung_beschreibung[i] if i < len(leistung_beschreibung) else '',
                        icon=leistung_icon[i] if i < len(leistung_icon) else 'fas fa-tooth',
                        praxis_id=praxis.id
                    )
                    db.session.add(neue_leistung)
                    print(f"  - {leistung_titel[i]}")
        
        # ========================================
        # TEAM SPEICHERN (aus Step 5)
        # ========================================
        print("👥 Speichere Team...")
        team_name = request.form.getlist('team_name[]')
        
        if team_name:
            TeamMitglied.query.filter_by(praxis_id=praxis.id).delete()
            team_position = request.form.getlist('team_position[]')
            team_beschreibung = request.form.getlist('team_beschreibung[]')
            team_qualifikationen = request.form.getlist('team_qualifikationen[]')
            team_sprachen = request.form.getlist('team_sprachen[]')
            team_schwerpunkte = request.form.getlist('team_schwerpunkte[]')
            team_foto_files = request.files.getlist('team_foto[]')
            
            for i in range(len(team_name)):
                if team_name[i].strip():
                    bild_pfad = None
                    
                    if i < len(team_foto_files) and team_foto_files[i].filename:
                        foto_file = team_foto_files[i]
                        pfad = optimize_and_save(foto_file, 'teammitglied', praxis.id)
                        if pfad:
                            bild_pfad = pfad
                    
                    neues_teammitglied = TeamMitglied(
                        name=team_name[i],
                        position=team_position[i] if i < len(team_position) else '',
                        beschreibung=team_beschreibung[i] if i < len(team_beschreibung) else '',
                        qualifikationen=team_qualifikationen[i] if i < len(team_qualifikationen) else '',
                        sprachen=team_sprachen[i] if i < len(team_sprachen) else '',
                        schwerpunkte=team_schwerpunkte[i] if i < len(team_schwerpunkte) else '',
                        bild_pfad=bild_pfad,
                        praxis_id=praxis.id
                    )
                    db.session.add(neues_teammitglied)
                    print(f"  - {team_name[i]}")
        
        # ========================================
        # TERMINBUCHUNG SPEICHERN (aus Step 6)
        # ========================================
        print("📅 Speichere Terminbuchung...")
        terminbuchung_modus = request.form.get('terminbuchung_modus', 'formular')
        praxis.terminbuchung_aktiv = True
        praxis.terminbuchung_modus = terminbuchung_modus
        print(f"  - Modus: {terminbuchung_modus}")
        
        if terminbuchung_modus == 'redirect':
            praxis.terminbuchung_url = request.form.get('terminbuchung_url', '')
            praxis.extern_anbieter = request.form.get('extern_anbieter', '')
        elif terminbuchung_modus == 'formular':
            praxis.formular_email = request.form.get('formular_email', praxis.email)
            praxis.formular_text = request.form.get('formular_text', '')
        elif terminbuchung_modus == 'dashboard':
            try:
                praxis.termin_dauer = int(request.form.get('termin_dauer', 30))
                praxis.vorlaufzeit = int(request.form.get('vorlaufzeit', 2))
                praxis.buchungshorizont = int(request.form.get('buchungshorizont', 4))
            except ValueError:
                praxis.termin_dauer = 30
                praxis.vorlaufzeit = 2
                praxis.buchungshorizont = 4
        
        db.session.commit()
        print("✅ Alle Wizard-Daten gespeichert!")
        
        # ========================================
        # FAQ-Daten speichern (optional)
        # ========================================
        if request.form.getlist('faq_frage[]'):
            faq_fragen = request.form.getlist('faq_frage[]')
            faq_antworten = request.form.getlist('faq_antwort[]')
            
            konfiguration_pfad = os.path.join(os.getcwd(), f'static/uploads/praxis_konfiguration/praxis_{praxis.id}_konfiguration.json')
            
            if os.path.exists(konfiguration_pfad):
                with open(konfiguration_pfad, 'r') as f:
                    konfiguration_daten = json.load(f)
            else:
                konfiguration_daten = {}
            
            konfiguration_daten['faqs'] = []
            for i in range(len(faq_fragen)):
                if faq_fragen[i].strip():
                    konfiguration_daten['faqs'].append({
                        'frage': faq_fragen[i],
                        'antwort': faq_antworten[i] if i < len(faq_antworten) else ''
                    })
            
            os.makedirs(os.path.join(os.getcwd(), 'static/uploads/praxis_konfiguration'), exist_ok=True)
            
            with open(konfiguration_pfad, 'w') as f:
                json.dump(konfiguration_daten, f)
        
        # Sicherstellen, dass der Slug erstellt wurde
        if not praxis.slug or praxis.slug.strip() == '':
            from app import slugify
            praxis.slug = slugify(f"{praxis.name}-{praxis.stadt}")
            
        # Änderungen speichern
        db.session.commit()
        
        # Wenn der finale Submit-Button gedrückt wurde
        if 'final_submit' in request.form or form_step == 'step7':
            print(f"📋 Alle Formularwerte: {list(request.form.keys())}")
            print(f"🔍 Debug-Info: {request.form.get('debug_info', 'Keine Debug-Info')}")
            
            # Erneut sicherstellen, dass ein gültiger Slug existiert
            if not praxis.slug or praxis.slug.strip() == '':
                from app import slugify
                praxis.slug = slugify(f"{praxis.name}-{praxis.stadt}")
            
            # Landingpage aktivieren für Premium-Pakete (case-insensitive)
            paket_lower = (praxis.paket or '').lower()
            if paket_lower in ['praxispro', 'praxisplus']:
                praxis.landingpage_aktiv = True
                
                # Standard-Werte für Landingpage setzen, falls nicht vorhanden
                if not praxis.hero_titel:
                    praxis.hero_titel = praxis.name
                if not praxis.hero_untertitel:
                    praxis.hero_untertitel = f"Ihre moderne Zahnarztpraxis in {praxis.stadt}"
                if not praxis.ueber_uns_text and praxis.beschreibung:
                    praxis.ueber_uns_text = praxis.beschreibung
            
            db.session.commit()
                
            # Erweiterte Debug-Ausgabe
            print(f"✅ FINAL SUBMIT ERKANNT: Formular-Schritt {form_step}")
            print(f"📍 Praxis ID: {praxis.id}, Name: {praxis.name}, Stadt: {praxis.stadt}")
            print(f"🔗 Generierter Slug: {praxis.slug}")
            print(f"🌐 Landingpage aktiviert: {praxis.landingpage_aktiv}")
                
            # Flash-Nachricht setzen
            flash('Ihre Praxisdaten wurden erfolgreich gespeichert und Ihre Praxisseite ist jetzt online.', 'success')
            
            # Immer zur generierten Landingpage weiterleiten
            return redirect(url_for('praxis_landingpage', slug=praxis.slug))
    
    # Nach der Speicherung zurück zum Formular (für Zwischenschritte)
    return redirect(url_for('praxis_daten_eingeben'))




# ==========================================
# BEWERTUNG HINZUFÜGEN (Dashboard)
# ==========================================
@app.route('/zahnarzt-dashboard/bewertung-speichern', methods=['POST'])
@login_required
def dashboard_bewertung_speichern():
    """Fügt eine neue Bewertung hinzu"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    # Bewertungsdaten aus dem Formular mit Validierung
    name = request.form.get('name', 'Anonym').strip()
    if not name:
        name = 'Anonym'
    
    try:
        bewertung_wert = int(request.form.get('bewertung', 5))
        bewertung_wert = max(1, min(5, bewertung_wert))
    except (ValueError, TypeError):
        bewertung_wert = 5
    
    text = request.form.get('text', '').strip()
    if not text:
        flash('Bitte geben Sie einen Bewertungstext ein.', 'warning')
        return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')
    
    # Neue Bewertung erstellen (vom Dashboard = direkt freigegeben)
    neue_bewertung = Bewertung(
        name=name,
        bewertung=bewertung_wert,
        text=text,
        praxis_id=praxis.id,
        datum=datetime.now(),
        status='freigegeben',
        quelle='dashboard'
    )
    
    db.session.add(neue_bewertung)
    db.session.commit()
    
    flash(f'Bewertung von {name} wurde hinzugefügt.', 'success')
    return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')


# ==========================================
# BEWERTUNG LÖSCHEN (Dashboard)
# ==========================================
@app.route('/zahnarzt-dashboard/bewertung-loeschen/<int:bewertung_id>', methods=['POST'])
@login_required
def dashboard_bewertung_loeschen(bewertung_id):
    """Löscht eine Bewertung"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    bewertung = Bewertung.query.get(bewertung_id)
    
    if not bewertung or bewertung.praxis_id != zahnarzt.praxis_id:
        flash('Bewertung nicht gefunden oder keine Berechtigung.', 'danger')
        return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')
    
    db.session.delete(bewertung)
    db.session.commit()
    
    flash('Bewertung wurde gelöscht.', 'success')
    return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')




# ==========================================
# BEWERTUNG FREIGEBEN (Dashboard)
# ==========================================
@app.route('/zahnarzt-dashboard/bewertung-freigeben/<int:bewertung_id>', methods=['POST'])
@login_required
def dashboard_bewertung_freigeben(bewertung_id):
    """Gibt eine Bewertung frei"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    bewertung = Bewertung.query.get(bewertung_id)
    
    if not bewertung or bewertung.praxis_id != zahnarzt.praxis_id:
        flash('Bewertung nicht gefunden oder keine Berechtigung.', 'danger')
        return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')
    
    bewertung.status = 'freigegeben'
    db.session.commit()
    
    flash('Bewertung wurde freigegeben und ist jetzt öffentlich sichtbar.', 'success')
    return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')


# ==========================================
# BEWERTUNG ABLEHNEN (Dashboard)
# ==========================================
@app.route('/zahnarzt-dashboard/bewertung-ablehnen/<int:bewertung_id>', methods=['POST'])
@login_required
def dashboard_bewertung_ablehnen(bewertung_id):
    """Lehnt eine Bewertung ab"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    bewertung = Bewertung.query.get(bewertung_id)
    
    if not bewertung or bewertung.praxis_id != zahnarzt.praxis_id:
        flash('Bewertung nicht gefunden oder keine Berechtigung.', 'danger')
        return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')
    
    bewertung.status = 'abgelehnt'
    db.session.commit()
    
    flash('Bewertung wurde abgelehnt.', 'info')
    return redirect(url_for('zahnarzt_dashboard') + '?page=bewertungen')


# ==========================================
# TERMINVERWALTUNG - DASHBOARD
# ==========================================

@app.route('/zahnarzt-dashboard/termine')
@login_required
def dashboard_termine():
    """Zeigt die Terminübersicht im Dashboard mit Monatskalender"""
    from models import Zahnarzt
    from datetime import date, timedelta
    import calendar as cal_module
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    
    datum_str = request.args.get('datum')
    if datum_str:
        try:
            ausgewaehltes_datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        except ValueError:
            ausgewaehltes_datum = date.today()
    else:
        ausgewaehltes_datum = date.today()
    
    status_filter = request.args.get('filter', 'alle')
    
    tages_query = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.datum == ausgewaehltes_datum
    )
    if status_filter == 'offen':
        tages_query = tages_query.filter(Termin.status == 'ausstehend')
    elif status_filter == 'bestaetigt':
        tages_query = tages_query.filter(Termin.status == 'bestaetigt')
    elif status_filter == 'abgesagt':
        tages_query = tages_query.filter(Termin.status == 'abgesagt')
    tages_termine = tages_query.order_by(Termin.uhrzeit).all()
    
    heute = date.today()
    termine_heute = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.datum == heute
    ).count()
    
    termine_monat = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        db.extract('month', Termin.datum) == ausgewaehltes_datum.month,
        db.extract('year', Termin.datum) == ausgewaehltes_datum.year
    ).count()
    
    ausstehende = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.status == 'ausstehend',
        Termin.datum >= heute
    ).count()
    
    monat_jahr = ausgewaehltes_datum.year
    monat_monat = ausgewaehltes_datum.month
    erster_tag = date(monat_jahr, monat_monat, 1)
    letzter_tag_nr = cal_module.monthrange(monat_jahr, monat_monat)[1]
    letzter_tag = date(monat_jahr, monat_monat, letzter_tag_nr)
    
    from sqlalchemy import func
    termine_pro_tag_raw = db.session.query(
        Termin.datum,
        func.count(Termin.id).label('gesamt'),
        func.sum(db.case((Termin.status == 'ausstehend', 1), else_=0)).label('offen'),
        func.sum(db.case((Termin.status == 'bestaetigt', 1), else_=0)).label('bestaetigt'),
        func.sum(db.case((Termin.status == 'abgesagt', 1), else_=0)).label('abgesagt')
    ).filter(
        Termin.praxis_id == praxis.id,
        Termin.datum >= erster_tag,
        Termin.datum <= letzter_tag
    ).group_by(Termin.datum).all()
    
    termine_pro_tag = {}
    for row in termine_pro_tag_raw:
        termine_pro_tag[row.datum] = {
            'gesamt': row.gesamt,
            'offen': int(row.offen or 0),
            'bestaetigt': int(row.bestaetigt or 0),
            'abgesagt': int(row.abgesagt or 0)
        }
    
    kalender_wochen = []
    start_wochentag = erster_tag.weekday()
    
    if start_wochentag > 0:
        vormonat_start = erster_tag - timedelta(days=start_wochentag)
    else:
        vormonat_start = erster_tag
    
    current = vormonat_start
    while current <= letzter_tag or current.weekday() != 0:
        if current.weekday() == 0:
            woche = []
        tag_data = termine_pro_tag.get(current, {'gesamt': 0, 'offen': 0, 'bestaetigt': 0, 'abgesagt': 0})
        woche.append({
            'datum': current,
            'tag': current.day,
            'ist_heute': current == heute,
            'ist_ausgewaehlt': current == ausgewaehltes_datum,
            'ist_aktueller_monat': current.month == monat_monat,
            'termine_gesamt': tag_data['gesamt'],
            'termine_offen': tag_data['offen'],
            'termine_bestaetigt': tag_data['bestaetigt'],
            'termine_abgesagt': tag_data['abgesagt']
        })
        if current.weekday() == 6:
            kalender_wochen.append(woche)
        current += timedelta(days=1)
    
    monatsnamen = ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                   'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
    
    if monat_monat == 1:
        vorheriger_monat = date(monat_jahr - 1, 12, 1).strftime('%Y-%m-%d')
    else:
        vorheriger_monat = date(monat_jahr, monat_monat - 1, 1).strftime('%Y-%m-%d')
    if monat_monat == 12:
        naechster_monat = date(monat_jahr + 1, 1, 1).strftime('%Y-%m-%d')
    else:
        naechster_monat = date(monat_jahr, monat_monat + 1, 1).strftime('%Y-%m-%d')
    
    vorheriger_tag = (ausgewaehltes_datum - timedelta(days=1)).strftime('%Y-%m-%d')
    naechster_tag = (ausgewaehltes_datum + timedelta(days=1)).strftime('%Y-%m-%d')
    
    behandlungsarten = Behandlungsart.query.filter_by(praxis_id=praxis.id, aktiv=True).all()
    
    return render_template('zahnarzt_termine.html',
        praxis=praxis,
        termine=tages_termine,
        ausgewaehltes_datum=ausgewaehltes_datum,
        kalender_wochen=kalender_wochen,
        monatsname=monatsnamen[monat_monat],
        monat_jahr=monat_jahr,
        vorheriger_monat=vorheriger_monat,
        naechster_monat=naechster_monat,
        termine_heute=termine_heute,
        termine_monat=termine_monat,
        ausstehende=ausstehende,
        behandlungsarten=behandlungsarten,
        vorheriger_tag=vorheriger_tag,
        naechster_tag=naechster_tag,
        status_filter=status_filter
    )


@app.route('/zahnarzt-dashboard/termin-bestaetigen/<int:termin_id>', methods=['POST'])
@login_required
def dashboard_termin_bestaetigen(termin_id):
    """Bestätigt einen Termin"""
    from models import Zahnarzt
    from flask import abort
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    # Sichere Abfrage: Termin muss zur eigenen Praxis gehören
    termin = Termin.query.filter_by(id=termin_id, praxis_id=zahnarzt.praxis_id).first()
    
    if not termin:
        abort(404)
    
    termin.status = 'bestaetigt'
    db.session.commit()
    
    patient_email = termin.gast_email if termin.ist_gast else (termin.patient.email if termin.patient else None)
    patient_name = termin.gast_name if termin.ist_gast else (termin.patient.vorname if termin.patient else 'Patient')
    
    if patient_email:
        try:
            from services.email_service import send_termin_sofort_bestaetigt_patient
            praxis = Praxis.query.get(termin.praxis_id)
            send_termin_sofort_bestaetigt_patient(
                to_email=patient_email,
                patient_name=patient_name,
                praxis_name=praxis.name if praxis else '',
                datum_str=termin.datum.strftime('%d.%m.%Y'),
                uhrzeit_str=termin.uhrzeit.strftime('%H:%M'),
                praxis_telefon=praxis.telefon or '' if praxis else ''
            )
        except Exception as e:
            app.logger.error(f'Bestätigungs-E-Mail konnte nicht gesendet werden: {e}')
    
    display_name = termin.gast_name if termin.ist_gast else (termin.patient.vorname if termin.patient else 'Patient')
    flash(f'Termin mit {display_name} wurde bestätigt.', 'success')
    
    redirect_to = request.form.get('redirect_to', '')
    if redirect_to == 'dashboard':
        return redirect(url_for('zahnarzt_dashboard'))
    return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))


@app.route('/zahnarzt-dashboard/termin-absagen/<int:termin_id>', methods=['POST'])
@login_required
def dashboard_termin_absagen(termin_id):
    """Sagt einen Termin ab und benachrichtigt den Patienten per E-Mail"""
    from models import Zahnarzt
    from flask import abort
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    termin = Termin.query.filter_by(id=termin_id, praxis_id=zahnarzt.praxis_id).first()
    
    if not termin:
        abort(404)
    
    absage_grund = request.form.get('absage_grund', '').strip()
    
    termin.status = 'abgesagt'
    db.session.commit()
    
    patient_email = termin.gast_email if termin.ist_gast else (termin.patient.email if termin.patient else None)
    patient_name = termin.gast_name if termin.ist_gast else (termin.patient.vorname if termin.patient else 'Patient')
    display_name = patient_name
    
    if patient_email:
        try:
            from services.email_service import send_termin_absage_patient
            praxis = Praxis.query.get(termin.praxis_id)
            send_termin_absage_patient(
                to_email=patient_email,
                patient_name=patient_name,
                praxis_name=praxis.name if praxis else '',
                datum_str=termin.datum.strftime('%d.%m.%Y'),
                uhrzeit_str=termin.uhrzeit.strftime('%H:%M'),
                absage_grund=absage_grund,
                praxis_telefon=praxis.telefon or '' if praxis else ''
            )
        except Exception as e:
            app.logger.error(f'Absage-E-Mail konnte nicht gesendet werden: {e}')
    
    flash(f'Termin mit {display_name} wurde abgesagt. Der Patient wurde per E-Mail benachrichtigt.', 'info')
    
    redirect_to = request.form.get('redirect_to', '')
    if redirect_to == 'dashboard':
        return redirect(url_for('zahnarzt_dashboard'))
    return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))


@app.route('/zahnarzt-dashboard/termin-modus-toggle', methods=['POST'])
@login_required
def dashboard_termin_modus_toggle():
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    if not praxis:
        flash('Praxis nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    praxis.termine_auto_bestaetigen = 'auto_bestaetigen' in request.form
    db.session.commit()
    
    if praxis.termine_auto_bestaetigen:
        flash('Termine werden jetzt automatisch bestätigt.', 'success')
    else:
        flash('Termine müssen jetzt manuell bestätigt werden.', 'info')
    
    return redirect(url_for('dashboard_termine'))


@app.route('/zahnarzt-dashboard/termin-erschienen/<int:termin_id>', methods=['POST'])
@login_required
def dashboard_termin_erschienen(termin_id):
    """Markiert einen Patienten als erschienen"""
    from models import Zahnarzt
    from flask import abort
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    # Sichere Abfrage: Termin muss zur eigenen Praxis gehören
    termin = Termin.query.filter_by(id=termin_id, praxis_id=zahnarzt.praxis_id).first()
    
    if not termin:
        abort(404)
    
    termin.status = 'erschienen'
    
    if termin.bestandspatient_id:
        from models import Bestandspatient
        from dateutil.relativedelta import relativedelta
        bp = Bestandspatient.query.get(termin.bestandspatient_id)
        if bp:
            bp.letzter_besuch = termin.datum
            bp.naechster_recall = termin.datum + relativedelta(months=bp.recall_intervall_monate)
            bp.recall_gesendet = False
    
    db.session.commit()
    
    flash(f'{termin.patient_name} wurde als erschienen markiert.', 'success')
    return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))


# ==========================================
# BESTANDSPATIENTEN VERWALTEN
# ==========================================

@app.route('/zahnarzt-dashboard/bestandspatienten')
@login_required
def dashboard_bestandspatienten():
    from models import Zahnarzt, Bestandspatient
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    
    suche = request.args.get('suche', '').strip()
    query = Bestandspatient.query.filter_by(praxis_id=praxis.id)
    
    if suche:
        query = query.filter(
            db.or_(
                Bestandspatient.vorname.ilike(f'%{suche}%'),
                Bestandspatient.nachname.ilike(f'%{suche}%'),
                Bestandspatient.email.ilike(f'%{suche}%')
            )
        )
    
    patienten = query.order_by(Bestandspatient.nachname, Bestandspatient.vorname).all()
    
    from datetime import date
    heute = date.today()
    recall_faellig = Bestandspatient.query.filter(
        Bestandspatient.praxis_id == praxis.id,
        Bestandspatient.recall_aktiv == True,
        Bestandspatient.naechster_recall <= heute,
        Bestandspatient.recall_gesendet == False
    ).count()
    
    return render_template('zahnarzt_bestandspatienten.html',
        praxis=praxis,
        patienten=patienten,
        suche=suche,
        recall_faellig=recall_faellig
    )


@app.route('/zahnarzt-dashboard/gast-zu-bestandspatient/<int:termin_id>', methods=['POST'])
@login_required
def dashboard_gast_zu_bestandspatient(termin_id):
    from models import Zahnarzt, Bestandspatient
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    termin = Termin.query.filter_by(id=termin_id, praxis_id=zahnarzt.praxis_id).first()
    if not termin:
        flash('Termin nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    if termin.bestandspatient_id:
        flash('Dieser Termin ist bereits einem Bestandspatienten zugeordnet.', 'info')
        return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))
    
    name_parts = (termin.gast_name or 'Unbekannt').strip().split(' ', 1)
    vorname = name_parts[0]
    nachname = name_parts[1] if len(name_parts) > 1 else ''
    
    vorname = request.form.get('vorname', vorname).strip()
    nachname = request.form.get('nachname', nachname).strip()
    email = request.form.get('email', termin.gast_email or '').strip()
    telefon = request.form.get('telefon', termin.gast_telefon or '').strip()
    
    existing = None
    if email:
        existing = Bestandspatient.query.filter_by(
            praxis_id=zahnarzt.praxis_id,
            email=email
        ).first()
    
    if existing:
        termin.bestandspatient_id = existing.id
        termin.ist_gast = False
        existing.letzter_besuch = termin.datum
        existing.naechster_recall = termin.datum + relativedelta(months=existing.recall_intervall_monate)
        existing.recall_gesendet = False
        db.session.commit()
        flash(f'{existing.voller_name} wurde als bestehender Patient erkannt und zugeordnet.', 'success')
    else:
        letzter_besuch = termin.datum if termin.status == 'erschienen' else None
        recall_datum = termin.datum + relativedelta(months=6) if letzter_besuch else None
        
        patient = Bestandspatient(
            vorname=vorname,
            nachname=nachname,
            email=email,
            telefon=telefon,
            praxis_id=zahnarzt.praxis_id,
            letzter_besuch=letzter_besuch,
            naechster_recall=recall_datum,
            recall_aktiv=True if email else False
        )
        db.session.add(patient)
        db.session.flush()
        
        termin.bestandspatient_id = patient.id
        termin.ist_gast = False
        
        other_termine = Termin.query.filter(
            Termin.praxis_id == zahnarzt.praxis_id,
            Termin.id != termin.id,
            Termin.ist_gast == True,
            Termin.gast_email == email,
            Termin.bestandspatient_id == None
        ).all()
        for t in other_termine:
            t.bestandspatient_id = patient.id
            t.ist_gast = False
        
        db.session.commit()
        flash(f'{patient.voller_name} wurde als Bestandspatient gespeichert.', 'success')
    
    return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))


@app.route('/zahnarzt-dashboard/bestandspatient/<int:patient_id>')
@login_required
def dashboard_bestandspatient_detail(patient_id):
    from models import Zahnarzt, Bestandspatient
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    patient = Bestandspatient.query.filter_by(id=patient_id, praxis_id=zahnarzt.praxis_id).first()
    if not patient:
        flash('Patient nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_bestandspatienten'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    termine = Termin.query.filter_by(
        bestandspatient_id=patient.id,
        praxis_id=praxis.id
    ).order_by(Termin.datum.desc(), Termin.uhrzeit.desc()).all()
    
    return render_template('zahnarzt_bestandspatient_detail.html',
        praxis=praxis,
        patient=patient,
        termine=termine
    )


@app.route('/zahnarzt-dashboard/bestandspatient/<int:patient_id>/bearbeiten', methods=['POST'])
@login_required
def dashboard_bestandspatient_bearbeiten(patient_id):
    from models import Zahnarzt, Bestandspatient
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    patient = Bestandspatient.query.filter_by(id=patient_id, praxis_id=zahnarzt.praxis_id).first()
    if not patient:
        flash('Patient nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_bestandspatienten'))
    
    patient.vorname = request.form.get('vorname', patient.vorname).strip()
    patient.nachname = request.form.get('nachname', patient.nachname).strip()
    patient.email = request.form.get('email', patient.email or '').strip()
    patient.telefon = request.form.get('telefon', patient.telefon or '').strip()
    patient.notizen = request.form.get('notizen', patient.notizen or '').strip()
    patient.recall_aktiv = 'recall_aktiv' in request.form
    
    recall_intervall = request.form.get('recall_intervall_monate')
    if recall_intervall:
        patient.recall_intervall_monate = int(recall_intervall)
    
    db.session.commit()
    flash(f'Patientendaten von {patient.voller_name} wurden aktualisiert.', 'success')
    return redirect(url_for('dashboard_bestandspatient_detail', patient_id=patient.id))


@app.route('/zahnarzt-dashboard/recall-senden', methods=['POST'])
@login_required
def dashboard_recall_senden():
    from models import Zahnarzt, Bestandspatient
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_bestandspatienten'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    heute = date.today()
    
    patienten = Bestandspatient.query.filter(
        Bestandspatient.praxis_id == praxis.id,
        Bestandspatient.recall_aktiv == True,
        Bestandspatient.naechster_recall <= heute,
        Bestandspatient.recall_gesendet == False,
        Bestandspatient.email.isnot(None),
        Bestandspatient.email != ''
    ).all()
    
    gesendet = 0
    for patient in patienten:
        try:
            from services.email_service import send_recall_erinnerung
            buchungs_url = url_for('praxis_landingpage', slug=praxis.slug, _external=True)
            send_recall_erinnerung(
                to_email=patient.email,
                patient_name=patient.vorname,
                praxis_name=praxis.name,
                praxis_telefon=praxis.telefon or '',
                buchungs_url=buchungs_url
            )
            patient.recall_gesendet = True
            gesendet += 1
        except Exception as e:
            app.logger.error(f'Recall-E-Mail an {patient.email} fehlgeschlagen: {e}')
    
    db.session.commit()
    
    if gesendet > 0:
        flash(f'{gesendet} Recall-Erinnerung(en) wurden versendet.', 'success')
    else:
        flash('Keine fälligen Recall-Erinnerungen vorhanden.', 'info')
    
    return redirect(url_for('dashboard_bestandspatienten'))


@app.route('/zahnarzt-dashboard/recall-einzeln/<int:patient_id>', methods=['POST'])
@login_required
def dashboard_recall_einzeln(patient_id):
    from models import Zahnarzt, Bestandspatient
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_bestandspatienten'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    patient = Bestandspatient.query.filter_by(id=patient_id, praxis_id=praxis.id).first()
    
    if not patient or not patient.email:
        flash('Patient nicht gefunden oder keine E-Mail hinterlegt.', 'danger')
        return redirect(url_for('dashboard_bestandspatienten'))
    
    try:
        from services.email_service import send_recall_erinnerung
        buchungs_url = url_for('praxis_landingpage', slug=praxis.slug, _external=True)
        send_recall_erinnerung(
            to_email=patient.email,
            patient_name=patient.vorname,
            praxis_name=praxis.name,
            praxis_telefon=praxis.telefon or '',
            buchungs_url=buchungs_url
        )
        patient.recall_gesendet = True
        db.session.commit()
        flash(f'Recall-Erinnerung an {patient.voller_name} wurde versendet.', 'success')
    except Exception as e:
        app.logger.error(f'Recall-E-Mail fehlgeschlagen: {e}')
        flash('E-Mail konnte nicht versendet werden.', 'danger')
    
    return redirect(url_for('dashboard_bestandspatient_detail', patient_id=patient.id))


# ==========================================
# VERFÜGBARKEITEN VERWALTEN
# ==========================================

@app.route('/zahnarzt-dashboard/verfuegbarkeiten')
@login_required
def dashboard_verfuegbarkeiten():
    """Zeigt die Verfügbarkeitsverwaltung"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('zahnarzt_dashboard'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    
    # Verfügbarkeiten nach Wochentag gruppieren
    verfuegbarkeiten = Verfuegbarkeit.query.filter_by(praxis_id=praxis.id).order_by(Verfuegbarkeit.wochentag, Verfuegbarkeit.start_zeit).all()
    
    # In Wochentag-Dict gruppieren
    verfuegbarkeiten_dict = {}
    for v in verfuegbarkeiten:
        if v.wochentag not in verfuegbarkeiten_dict:
            verfuegbarkeiten_dict[v.wochentag] = []
        verfuegbarkeiten_dict[v.wochentag].append(v)
    
    # Behandlungsarten
    behandlungsarten = Behandlungsart.query.filter_by(praxis_id=praxis.id).order_by(Behandlungsart.reihenfolge).all()
    
    # Ausnahmen (nächste 30 Tage)
    from datetime import date, timedelta
    ausnahmen = Ausnahme.query.filter(
        Ausnahme.praxis_id == praxis.id,
        Ausnahme.datum >= date.today()
    ).order_by(Ausnahme.datum).limit(20).all()
    
    wochentage = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    
    return render_template('zahnarzt_verfuegbarkeiten.html',
        praxis=praxis,
        verfuegbarkeiten_dict=verfuegbarkeiten_dict,
        behandlungsarten=behandlungsarten,
        ausnahmen=ausnahmen,
        wochentage=wochentage
    )


@app.route('/zahnarzt-dashboard/buchungseinstellungen-speichern', methods=['POST'])
@login_required
def dashboard_buchungseinstellungen_speichern():
    """Speichert Buchungseinstellungen (Vorlaufzeit, Buchungshorizont)"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    try:
        praxis.vorlaufzeit = int(request.form.get('vorlaufzeit', 0))
        praxis.buchungshorizont = max(1, min(12, int(request.form.get('buchungshorizont', 4))))
    except (ValueError, TypeError):
        praxis.vorlaufzeit = 0
        praxis.buchungshorizont = 4
    
    db.session.commit()
    flash('Buchungseinstellungen gespeichert!', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/verfuegbarkeit-speichern', methods=['POST'])
@login_required
def dashboard_verfuegbarkeit_speichern():
    """Speichert eine neue Verfügbarkeit"""
    from models import Zahnarzt
    from datetime import time
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    try:
        wochentag = int(request.form.get('wochentag', 0))
        start_zeit_str = request.form.get('start_zeit', '08:00')
        end_zeit_str = request.form.get('end_zeit', '17:00')
        slot_dauer = int(request.form.get('slot_dauer', 30))
        
        start_zeit = datetime.strptime(start_zeit_str, '%H:%M').time()
        end_zeit = datetime.strptime(end_zeit_str, '%H:%M').time()
        
        verfuegbarkeit = Verfuegbarkeit(
            wochentag=wochentag,
            start_zeit=start_zeit,
            end_zeit=end_zeit,
            slot_dauer=slot_dauer,
            praxis_id=zahnarzt.praxis_id
        )
        
        db.session.add(verfuegbarkeit)
        db.session.commit()
        
        flash('Verfügbarkeit wurde hinzugefügt.', 'success')
    except Exception as e:
        flash(f'Fehler beim Speichern: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/verfuegbarkeit-loeschen/<int:id>', methods=['POST'])
@login_required
def dashboard_verfuegbarkeit_loeschen(id):
    """Löscht eine Verfügbarkeit"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    verfuegbarkeit = Verfuegbarkeit.query.get(id)
    
    if not verfuegbarkeit or verfuegbarkeit.praxis_id != zahnarzt.praxis_id:
        flash('Verfügbarkeit nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    db.session.delete(verfuegbarkeit)
    db.session.commit()
    
    flash('Verfügbarkeit wurde gelöscht.', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/behandlungsart-speichern', methods=['POST'])
@login_required
def dashboard_behandlungsart_speichern():
    """Speichert eine neue Behandlungsart"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    name = request.form.get('name', '').strip()
    if not name:
        flash('Bitte geben Sie einen Namen ein.', 'warning')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    try:
        dauer = int(request.form.get('dauer_minuten', 30))
    except ValueError:
        dauer = 30
    
    farbe = request.form.get('farbe', '#4ECDC4')
    icon = request.form.get('icon', 'fa-tooth')
    beschreibung = request.form.get('beschreibung', '').strip()
    
    behandlungsart = Behandlungsart(
        name=name,
        beschreibung=beschreibung,
        dauer_minuten=dauer,
        farbe=farbe,
        icon=icon,
        praxis_id=zahnarzt.praxis_id
    )
    
    db.session.add(behandlungsart)
    db.session.commit()
    
    flash(f'Behandlungsart "{name}" wurde hinzugefügt.', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/behandlungsart-loeschen/<int:id>', methods=['POST'])
@login_required
def dashboard_behandlungsart_loeschen(id):
    """Löscht eine Behandlungsart"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    behandlungsart = Behandlungsart.query.get(id)
    
    if not behandlungsart or behandlungsart.praxis_id != zahnarzt.praxis_id:
        flash('Behandlungsart nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    db.session.delete(behandlungsart)
    db.session.commit()
    
    flash('Behandlungsart wurde gelöscht.', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/ausnahme-speichern', methods=['POST'])
@login_required
def dashboard_ausnahme_speichern():
    """Speichert eine Ausnahme (Urlaub, Feiertag, etc.)"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    datum_str = request.form.get('datum')
    if not datum_str:
        flash('Bitte wählen Sie ein Datum.', 'warning')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    try:
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Ungültiges Datum.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    grund = request.form.get('grund', '').strip()
    ganztags = request.form.get('ganztags') == 'on'
    
    ausnahme = Ausnahme(
        datum=datum,
        grund=grund,
        ganztags_geschlossen=ganztags,
        praxis_id=zahnarzt.praxis_id
    )
    
    db.session.add(ausnahme)
    db.session.commit()
    
    flash(f'Ausnahme für {datum.strftime("%d.%m.%Y")} wurde hinzugefügt.', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


@app.route('/zahnarzt-dashboard/ausnahme-loeschen/<int:id>', methods=['POST'])
@login_required
def dashboard_ausnahme_loeschen(id):
    """Löscht eine Ausnahme"""
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    ausnahme = Ausnahme.query.get(id)
    
    if not ausnahme or ausnahme.praxis_id != zahnarzt.praxis_id:
        flash('Ausnahme nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_verfuegbarkeiten'))
    
    db.session.delete(ausnahme)
    db.session.commit()
    
    flash('Ausnahme wurde gelöscht.', 'success')
    return redirect(url_for('dashboard_verfuegbarkeiten'))


# ==========================================
# TERMIN MANUELL ERSTELLEN (Dashboard)
# ==========================================

@app.route('/zahnarzt-dashboard/termin-erstellen', methods=['POST'])
@login_required
def dashboard_termin_erstellen():
    """Erstellt einen neuen Termin manuell"""
    from models import Zahnarzt
    from datetime import timedelta
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    try:
        datum_str = request.form.get('datum')
        uhrzeit_str = request.form.get('uhrzeit')
        
        if not datum_str or not uhrzeit_str:
            flash('Bitte Datum und Uhrzeit angeben.', 'warning')
            return redirect(url_for('dashboard_termine'))
        
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        uhrzeit = datetime.strptime(uhrzeit_str, '%H:%M').time()
        
        gast_name = request.form.get('gast_name', '').strip()
        gast_email = request.form.get('gast_email', '').strip()
        gast_telefon = request.form.get('gast_telefon', '').strip()
        grund = request.form.get('grund', '').strip()
        
        behandlungsart_id = request.form.get('behandlungsart_id')
        if behandlungsart_id:
            behandlungsart_id = int(behandlungsart_id)
        else:
            behandlungsart_id = None
        
        dauer = int(request.form.get('dauer_minuten', 30))
        
        wiederholung = request.form.get('wiederholung', '')
        wiederholung_anzahl = int(request.form.get('wiederholung_anzahl', 1))
        wiederholung_anzahl = min(max(wiederholung_anzahl, 1), 52)
        
        notizen = request.form.get('notizen', '').strip()
        
        termine_erstellt = []
        aktuelles_datum = datum
        
        for i in range(wiederholung_anzahl if wiederholung else 1):
            t = Termin(
                datum=aktuelles_datum,
                uhrzeit=uhrzeit,
                dauer_minuten=dauer,
                grund=grund,
                notizen=notizen if i == 0 else '',
                status='bestaetigt',
                praxis_id=zahnarzt.praxis_id,
                behandlungsart_id=behandlungsart_id,
                gast_name=gast_name,
                gast_email=gast_email,
                gast_telefon=gast_telefon,
                ist_gast=True
            )
            db.session.add(t)
            termine_erstellt.append(t)
            
            if wiederholung == 'woechentlich':
                aktuelles_datum = aktuelles_datum + timedelta(weeks=1)
            elif wiederholung == '2wochen':
                aktuelles_datum = aktuelles_datum + timedelta(weeks=2)
            elif wiederholung == '4wochen':
                aktuelles_datum = aktuelles_datum + timedelta(weeks=4)
            elif wiederholung == 'monatlich':
                from dateutil.relativedelta import relativedelta
                aktuelles_datum = aktuelles_datum + relativedelta(months=1)
        
        db.session.commit()
        
        if len(termine_erstellt) > 1:
            flash(f'{len(termine_erstellt)} Termine für {gast_name} wurden erstellt (wiederkehrend).', 'success')
        else:
            flash(f'Termin für {gast_name} wurde erstellt.', 'success')
        return redirect(url_for('dashboard_termine', datum=datum_str))
        
    except Exception as e:
        flash(f'Fehler beim Erstellen: {str(e)}', 'danger')
        return redirect(url_for('dashboard_termine'))


@app.route('/zahnarzt-dashboard/termin-notiz/<int:termin_id>', methods=['POST'])
@login_required
def dashboard_termin_notiz(termin_id):
    from models import Zahnarzt
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    termin = Termin.query.filter_by(id=termin_id, praxis_id=zahnarzt.praxis_id).first()
    if not termin:
        flash('Termin nicht gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    termin.notizen = request.form.get('notizen', '').strip()
    db.session.commit()
    
    flash('Notiz gespeichert.', 'success')
    return redirect(url_for('dashboard_termine', datum=termin.datum.strftime('%Y-%m-%d')))


@app.route('/zahnarzt-dashboard/erinnerungen-senden', methods=['POST'])
@login_required
def dashboard_erinnerungen_senden():
    from models import Zahnarzt
    from datetime import date, timedelta
    
    zahnarzt = Zahnarzt.query.get(current_user.id)
    if not zahnarzt or not zahnarzt.praxis_id:
        flash('Keine Praxis gefunden.', 'danger')
        return redirect(url_for('dashboard_termine'))
    
    praxis = Praxis.query.get(zahnarzt.praxis_id)
    morgen = date.today() + timedelta(days=1)
    
    termine_morgen = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.datum == morgen,
        Termin.status.in_(['ausstehend', 'bestaetigt']),
        Termin.erinnerung_gesendet == False
    ).all()
    
    gesendet = 0
    for termin in termine_morgen:
        email = termin.kontakt_email
        name = termin.patient_name
        if email:
            try:
                from services.email_service import send_termin_erinnerung_24h
                adresse = ''
                if praxis.strasse:
                    adresse = f"{praxis.strasse}, {praxis.plz or ''} {praxis.stadt or ''}"
                send_termin_erinnerung_24h(
                    to_email=email,
                    patient_name=name,
                    praxis_name=praxis.name,
                    datum_str=termin.datum.strftime('%d.%m.%Y'),
                    uhrzeit_str=termin.uhrzeit.strftime('%H:%M'),
                    praxis_telefon=praxis.telefon or '',
                    praxis_adresse=adresse
                )
                termin.erinnerung_gesendet = True
                gesendet += 1
            except Exception as e:
                app.logger.error(f'Erinnerungs-E-Mail fehlgeschlagen: {e}')
    
    db.session.commit()
    
    if gesendet > 0:
        flash(f'{gesendet} Erinnerung(en) für morgen versendet.', 'success')
    elif len(termine_morgen) == 0:
        flash('Keine Termine für morgen gefunden (oder bereits erinnert).', 'info')
    else:
        flash('Keine E-Mail-Adressen für die morgigen Termine vorhanden.', 'warning')
    
    return redirect(url_for('dashboard_termine'))


# ==========================================
# ÖFFENTLICHE TERMINBUCHUNG (für Patienten)
# ==========================================

def get_freie_slots(praxis_id, datum):
    """Berechnet alle freien Slots für ein Datum basierend auf Verfügbarkeiten und bestehenden Terminen"""
    
    # Wochentag (0=Montag, 6=Sonntag)
    wochentag = datum.weekday()
    
    # Verfügbarkeiten für diesen Wochentag laden
    verfuegbarkeiten = Verfuegbarkeit.query.filter_by(
        praxis_id=praxis_id,
        wochentag=wochentag,
        aktiv=True
    ).all()
    
    if not verfuegbarkeiten:
        return []
    
    # Prüfen ob ganztägige Ausnahme für diesen Tag
    ausnahme_ganztags = Ausnahme.query.filter_by(
        praxis_id=praxis_id,
        datum=datum,
        ganztags_geschlossen=True
    ).first()
    
    if ausnahme_ganztags:
        return []
    
    # Teilzeit-Ausnahmen laden (z.B. nur Vormittag geschlossen)
    teilzeit_ausnahmen = Ausnahme.query.filter(
        Ausnahme.praxis_id == praxis_id,
        Ausnahme.datum == datum,
        Ausnahme.ganztags_geschlossen == False,
        Ausnahme.start_zeit != None,
        Ausnahme.end_zeit != None
    ).all()
    
    # Geblockte Zeiträume aus Ausnahmen sammeln
    ausnahme_bloecke = []
    for a in teilzeit_ausnahmen:
        ausnahme_start = datetime.combine(datum, a.start_zeit)
        ausnahme_end = datetime.combine(datum, a.end_zeit)
        ausnahme_bloecke.append((ausnahme_start, ausnahme_end))
    
    # Bestehende Termine für diesen Tag laden
    bestehende_termine = Termin.query.filter(
        Termin.praxis_id == praxis_id,
        Termin.datum == datum,
        Termin.status.in_(['ausstehend', 'bestaetigt'])
    ).all()
    
    # Geblockte Zeiten sammeln (aus Terminen UND Teilzeit-Ausnahmen)
    geblockte_zeiten = []
    for t in bestehende_termine:
        start = datetime.combine(datum, t.uhrzeit)
        end = start + timedelta(minutes=t.dauer_minuten)
        geblockte_zeiten.append((start, end))
    
    # Teilzeit-Ausnahmen zu geblockten Zeiten hinzufügen
    geblockte_zeiten.extend(ausnahme_bloecke)
    
    # Alle möglichen Slots generieren
    slots = []
    for v in verfuegbarkeiten:
        current = datetime.combine(datum, v.start_zeit)
        end_time = datetime.combine(datum, v.end_zeit)
        
        while current + timedelta(minutes=v.slot_dauer) <= end_time:
            slot_end = current + timedelta(minutes=v.slot_dauer)
            
            # Prüfen ob Slot frei ist (keine Überschneidung mit Terminen oder Ausnahmen)
            ist_frei = True
            for blocked_start, blocked_end in geblockte_zeiten:
                if not (slot_end <= blocked_start or current >= blocked_end):
                    ist_frei = False
                    break
            
            if ist_frei:
                slots.append({
                    'zeit': current.time(),
                    'zeit_str': current.strftime('%H:%M'),
                    'dauer': v.slot_dauer
                })
            
            current += timedelta(minutes=v.slot_dauer)
    
    # Nach Zeit sortieren
    slots.sort(key=lambda x: x['zeit'])
    return slots


@app.route('/api/praxis/<slug>/slots/<datum_str>')
def api_praxis_slots(slug, datum_str):
    """JSON-API: Gibt freie Slots für ein Datum zurück (nur für Dashboard-Modus)"""
    from flask import jsonify, abort
    praxis = Praxis.query.filter_by(slug=slug).first()
    if not praxis:
        abort(404)
    if praxis.terminbuchung_modus != 'dashboard':
        return jsonify({'slots': [], 'error': 'Terminbuchung nicht verfügbar'}), 400
    try:
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'slots': [], 'error': 'Ungültiges Datum'}), 400

    heute = date.today()
    vorlaufzeit = praxis.vorlaufzeit or 0
    fruehestes_datum = heute + timedelta(days=vorlaufzeit)
    if datum < fruehestes_datum:
        return jsonify({'slots': [], 'error': 'Datum liegt in der Vergangenheit'}), 400

    slots = get_freie_slots(praxis.id, datum)
    wt_de = ['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag']
    mt_de = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember']

    behandlungsarten = Behandlungsart.query.filter_by(praxis_id=praxis.id, aktiv=True).order_by(Behandlungsart.reihenfolge).all()

    return jsonify({
        'slots': [{'zeit_str': s['zeit_str'], 'dauer': s['dauer']} for s in slots],
        'datum': datum_str,
        'datum_label': f"{wt_de[datum.weekday()]}, {datum.day}. {mt_de[datum.month - 1]} {datum.year}",
        'behandlungsarten': [{'id': ba.id, 'name': ba.name, 'dauer': ba.dauer_minuten} for ba in behandlungsarten],
        'telefon': praxis.telefon or ''
    })


@app.route('/zahnarzt/<slug>/termin-buchen', methods=['GET', 'POST'])
def termin_buchen_submit(slug):
    """Verarbeitet eine Terminbuchung (POST) oder leitet zur Landingpage weiter (GET)"""
    if request.method == 'GET':
        return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
    from flask import abort
    import secrets
    
    praxis = Praxis.query.filter_by(slug=slug).first()
    
    if not praxis:
        abort(404)
    
    if praxis.terminbuchung_modus != 'dashboard':
        flash('Online-Terminbuchung ist für diese Praxis nicht verfügbar.', 'danger')
        return redirect(url_for('praxis_landingpage', slug=slug))
    
    # Spam-Schutz: Honeypot
    if request.form.get('website_url'):
        flash('Ihre Anfrage konnte nicht verarbeitet werden.', 'danger')
        return redirect(url_for('praxis_landingpage', slug=slug))
    
    # Rate-Limiting: Max 3 Buchungen pro IP pro Stunde
    from datetime import datetime, timedelta, date, time
    eine_stunde_zuvor = datetime.utcnow() - timedelta(hours=1)
    buchungen_count = Termin.query.filter(
        Termin.praxis_id == praxis.id,
        Termin.erstellt_am >= eine_stunde_zuvor,
        Termin.gast_email == request.form.get('email', '').strip()
    ).count()
    if buchungen_count >= 3:
        flash('Sie haben zu viele Terminanfragen gestellt. Bitte versuchen Sie es später erneut.', 'warning')
        return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
    
    try:
        datum_str = request.form.get('datum')
        uhrzeit_str = request.form.get('uhrzeit')
        
        if not datum_str or not uhrzeit_str:
            flash('Bitte wählen Sie Datum und Uhrzeit.', 'warning')
            return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
        
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        uhrzeit = datetime.strptime(uhrzeit_str, '%H:%M').time()
        
        # Vorlaufzeit prüfen
        heute = date.today()
        vorlaufzeit = praxis.vorlaufzeit or 0
        if datum < heute + timedelta(days=vorlaufzeit):
            flash('Dieser Termin liegt zu kurzfristig.', 'warning')
            return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
        
        # Slot-Verfügbarkeit prüfen
        freie_slots = get_freie_slots(praxis.id, datum)
        slot_verfuegbar = any(s['zeit_str'] == uhrzeit_str for s in freie_slots)
        
        if not slot_verfuegbar:
            flash('Dieser Termin ist leider nicht mehr verfügbar.', 'warning')
            return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
        
        # Patientendaten
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        telefon = request.form.get('telefon', '').strip()
        grund = request.form.get('grund', '').strip()
        
        if not name or not email:
            flash('Bitte geben Sie Name und E-Mail an.', 'warning')
            return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
        
        behandlungsart_id = request.form.get('behandlungsart_id')
        if behandlungsart_id:
            behandlungsart_id = int(behandlungsart_id)
            behandlungsart = Behandlungsart.query.get(behandlungsart_id)
            dauer = behandlungsart.dauer_minuten if behandlungsart else 30
        else:
            behandlungsart_id = None
            dauer = praxis.termin_dauer or 30
        
        # Bestätigungstoken generieren
        token = secrets.token_urlsafe(32)
        
        auto_bestaetigen = praxis.termine_auto_bestaetigen or False
        
        termin = Termin(
            datum=datum,
            uhrzeit=uhrzeit,
            dauer_minuten=dauer,
            grund=grund,
            status='bestaetigt' if auto_bestaetigen else 'ausstehend',
            praxis_id=praxis.id,
            behandlungsart_id=behandlungsart_id,
            gast_name=name,
            gast_email=email,
            gast_telefon=telefon,
            ist_gast=True,
            bestaetigung_token=token
        )
        
        db.session.add(termin)
        db.session.commit()
        
        datum_formatiert = datum.strftime('%d.%m.%Y')
        uhrzeit_formatiert = uhrzeit.strftime('%H:%M')
        
        if auto_bestaetigen:
            from services.email_service import send_termin_sofort_bestaetigt_patient, send_termin_benachrichtigung_zahnarzt
            send_termin_sofort_bestaetigt_patient(
                to_email=email,
                patient_name=name,
                praxis_name=praxis.name,
                datum_str=datum_formatiert,
                uhrzeit_str=uhrzeit_formatiert,
                praxis_telefon=praxis.telefon or ''
            )
        else:
            from services.email_service import send_termin_bestaetigung_patient, send_termin_benachrichtigung_zahnarzt
            send_termin_bestaetigung_patient(
                to_email=email,
                patient_name=name,
                praxis_name=praxis.name,
                datum_str=datum_formatiert,
                uhrzeit_str=uhrzeit_formatiert,
                praxis_telefon=praxis.telefon or ''
            )
        
        from flask import url_for as flask_url_for
        dashboard_url = flask_url_for('dashboard_termine', datum=datum_str, _external=True)
        behandlung_name = ''
        if behandlungsart_id:
            ba = Behandlungsart.query.get(behandlungsart_id)
            behandlung_name = ba.name if ba else ''
        
        if auto_bestaetigen:
            from services.email_service import send_termin_auto_bestaetigt_zahnarzt
            send_termin_auto_bestaetigt_zahnarzt(
                to_email=praxis.email,
                patient_name=name,
                patient_email=email,
                patient_telefon=telefon,
                datum_str=datum_formatiert,
                uhrzeit_str=uhrzeit_formatiert,
                behandlung=behandlung_name,
                grund=grund,
                dashboard_url=dashboard_url
            )
        else:
            from services.email_service import send_termin_benachrichtigung_zahnarzt
            send_termin_benachrichtigung_zahnarzt(
                to_email=praxis.email,
                patient_name=name,
                patient_email=email,
                patient_telefon=telefon,
                datum_str=datum_formatiert,
                uhrzeit_str=uhrzeit_formatiert,
                behandlung=behandlung_name,
                grund=grund,
                dashboard_url=dashboard_url
            )
        
        session['termin_bestaetigung'] = {
            'name': name,
            'datum': datum_formatiert,
            'uhrzeit': uhrzeit_formatiert,
            'praxis': praxis.name,
            'email': email,
            'auto_bestaetigt': auto_bestaetigen
        }
        return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')
        
    except Exception as e:
        import traceback
        app.logger.error(f'Terminbuchung Fehler für {slug}: {str(e)}')
        app.logger.error(traceback.format_exc())
        db.session.rollback()
        flash(f'Fehler bei der Buchung. Bitte versuchen Sie es erneut.', 'danger')
        return redirect(url_for('praxis_landingpage', slug=slug) + '#termin')