import os
import csv
from datetime import datetime
from main import app
from database import db
import models
from werkzeug.security import generate_password_hash

def lade_csv_daten(datei_pfad):
    daten = []
    if os.path.exists(datei_pfad):
        with open(datei_pfad, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                daten.append(row)
    return daten

def migriere_praxen():
    print("Migriere Zahnarztpraxen...")
    zahnaerzte_csv = lade_csv_daten("zahnaerzte.csv")
    
    # Zähler für die Protokollierung
    count_total = len(zahnaerzte_csv)
    count_imported = 0
    count_skipped = 0
    
    for praxis_data in zahnaerzte_csv:
        # Überprüfen, ob die Praxis bereits in der Datenbank existiert
        existierende_praxis = models.Praxis.query.filter_by(
            plz=praxis_data.get('plz', ''),
            strasse=praxis_data.get('straße', '')
        ).first()
        
        if existierende_praxis:
            count_skipped += 1
            print(f"Praxis wird übersprungen (existiert bereits): {praxis_data.get('name', '')}")
            continue
        
        # Slug generieren
        from app import slugify
        praxis_name = praxis_data.get('name', 'Zahnarztpraxis')
        stadt = praxis_data.get('stadt', '')
        base_slug = slugify(f"{praxis_name}-{stadt}")
        
        # Eindeutigen Slug erstellen, falls nötig
        slug = base_slug
        counter = 1
        while models.Praxis.query.filter_by(slug=slug).first() is not None:
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Latitude und Longitude umwandeln
        try:
            raw_lat = praxis_data.get('lat', '0').replace(',', '').replace('.', '')
            raw_lng = praxis_data.get('lng', '0').replace(',', '').replace('.', '')
            lat = int(raw_lat) / 1e7 if raw_lat else None
            lng = int(raw_lng) / 1e7 if raw_lng else None
        except Exception as e:
            print(f"Fehler bei Koordinaten-Konvertierung: {e}")
            lat = None
            lng = None
        
        # Neue Praxis erstellen
        neue_praxis = models.Praxis(
            name=praxis_data.get('name', 'Zahnarztpraxis'),
            slug=slug,
            strasse=praxis_data.get('straße', ''),
            plz=praxis_data.get('plz', ''),
            stadt=praxis_data.get('stadt', ''),
            telefon=praxis_data.get('telefon', ''),
            email=praxis_data.get('email', ''),
            webseite=praxis_data.get('webseite', ''),
            beschreibung='',
            latitude=lat,
            longitude=lng,
            paket='basic',
            terminbuchung_aktiv=True,
            terminbuchung_modus='dashboard',
            ist_verifiziert=(praxis_data.get('beansprucht', 'nein').lower() == 'ja')
        )
        
        # Zur Datenbank hinzufügen
        db.session.add(neue_praxis)
        count_imported += 1
    
    # Nach dem Durchlauf speichern
    db.session.commit()
    print(f"Migration abgeschlossen: {count_imported} Praxen importiert, {count_skipped} übersprungen (von {count_total} gesamt)")

def migriere_zahnaerzte():
    print("Migriere Zahnarzt-Konten...")
    neue_praxen_csv = lade_csv_daten("neue_praxen.csv")
    
    count_imported = 0
    
    for zahnarzt_data in neue_praxen_csv:
        email = zahnarzt_data.get('email', '')
        if not email:
            continue
            
        # Überprüfen, ob der Zahnarzt bereits existiert
        existierender_zahnarzt = models.Zahnarzt.query.filter_by(email=email).first()
        if existierender_zahnarzt:
            print(f"Zahnarzt wird übersprungen (existiert bereits): {email}")
            continue
        
        # Neuen Zahnarzt erstellen
        neuer_zahnarzt = models.Zahnarzt(
            email=email,
            password_hash=zahnarzt_data.get('passwort_hash', generate_password_hash('defaultpassword')),
            is_active=(zahnarzt_data.get('bestätigt', 'nein').lower() == 'ja')
        )
        
        db.session.add(neuer_zahnarzt)
        count_imported += 1
        
        # Verknüpfe seine Praxis, falls vorhanden
        praxis_name = zahnarzt_data.get('name', '')
        if praxis_name:
            praxis = models.Praxis.query.filter_by(
                plz=zahnarzt_data.get('plz', ''),
                strasse=zahnarzt_data.get('straße', '')
            ).first()
            
            if praxis:
                praxis.zahnarzt_id = neuer_zahnarzt.id
                praxis.paket = zahnarzt_data.get('paket', 'basic').lower()
    
    db.session.commit()
    print(f"Migration abgeschlossen: {count_imported} Zahnärzte importiert.")

def migriere_claims():
    print("Migriere Praxis-Claims...")
    claims_csv = lade_csv_daten("claims.csv")
    pending_claims_csv = lade_csv_daten("pending_claims.csv")
    
    # Zusammenführen der beiden Claim-Quellen
    alle_claims = claims_csv + pending_claims_csv
    count_imported = 0
    
    for claim_data in alle_claims:
        email = claim_data.get('email', '')
        plz = claim_data.get('plz', '')
        strasse = claim_data.get('strasse', '')
        
        if not email or not plz or not strasse:
            continue
            
        # Überprüfen, ob der Claim bereits existiert
        existierender_claim = models.Claim.query.filter_by(
            email=email,
            plz=plz,
            strasse=strasse
        ).first()
        
        if existierender_claim:
            print(f"Claim wird übersprungen (existiert bereits): {email} für {plz}")
            continue
        
        # Status bestimmen
        status = claim_data.get('status', 'pending').lower()
        if status not in ['pending', 'approved', 'rejected']:
            status = 'pending'
        
        # Finde Zahnarzt und Praxis
        zahnarzt = models.Zahnarzt.query.filter_by(email=email).first()
        zahnarzt_id = zahnarzt.id if zahnarzt else None
        
        praxis = models.Praxis.query.filter_by(plz=plz, strasse=strasse).first()
        praxis_id = praxis.id if praxis else None
        
        # Neuen Claim erstellen
        neuer_claim = models.Claim(
            email=email,
            praxis_name=claim_data.get('praxisname', ''),
            plz=plz,
            strasse=strasse,
            status=status,
            zahnarzt_id=zahnarzt_id,
            praxis_id=praxis_id,
            erstellt_am=datetime.now()
        )
        
        db.session.add(neuer_claim)
        count_imported += 1
    
    db.session.commit()
    print(f"Migration abgeschlossen: {count_imported} Claims importiert.")

def migriere_paket_buchungen():
    print("Migriere Paket-Buchungen...")
    buchungen_csv = lade_csv_daten("paket_buchungen.csv")
    
    count_imported = 0
    
    for buchung_data in buchungen_csv:
        email = buchung_data.get('email', '')
        paket = buchung_data.get('paket', '')
        
        if not email or not paket:
            continue
        
        # Finde zugehörige Praxis
        zahnarzt = models.Zahnarzt.query.filter_by(email=email).first()
        if not zahnarzt or not zahnarzt.praxen:
            print(f"Keine Praxis gefunden für Zahnarzt: {email}")
            continue
            
        praxis = zahnarzt.praxen[0]  # Erste Praxis des Zahnarztes
        
        # Überprüfen, ob die Buchung bereits existiert
        existierende_buchung = models.PaketBuchung.query.filter_by(
            praxis_id=praxis.id,
            stripe_session_id=buchung_data.get('stripe_session_id', '')
        ).first()
        
        if existierende_buchung:
            print(f"Buchung wird übersprungen (existiert bereits): {email} für {paket}")
            continue
        
        # Zahlungsstatus bestimmen
        zahlungsstatus = buchung_data.get('status', 'ausstehend').lower()
        if zahlungsstatus not in ['ausstehend', 'bezahlt', 'fehlgeschlagen']:
            zahlungsstatus = 'ausstehend'
        
        # Neue Buchung erstellen
        neue_buchung = models.PaketBuchung(
            paket=paket.lower(),
            zahlweise=buchung_data.get('zahlweise', 'monatlich'),
            preis=float(buchung_data.get('preis', 0)),
            zahlungsmethode='stripe',
            zahlungsstatus=zahlungsstatus,
            stripe_session_id=buchung_data.get('stripe_session_id', ''),
            praxis_id=praxis.id,
            erstellt_am=datetime.now()
        )
        
        # Bezahlt-Datum setzen, falls vorhanden
        if zahlungsstatus == 'bezahlt':
            neue_buchung.bezahlt_am = datetime.now()
            
            # Auch das Paket der Praxis aktualisieren
            praxis.paket = paket.lower()
            
            # Aktualisiere paket_aktiv_bis Datum (1 Monat oder 1 Jahr)
            from datetime import timedelta
            if buchung_data.get('zahlweise', '') == 'jährlich':
                praxis.paket_aktiv_bis = datetime.now() + timedelta(days=365)
            else:
                praxis.paket_aktiv_bis = datetime.now() + timedelta(days=30)
        
        db.session.add(neue_buchung)
        count_imported += 1
    
    db.session.commit()
    print(f"Migration abgeschlossen: {count_imported} Paket-Buchungen importiert.")

def migriere_patienten():
    print("Migriere Patienten-Konten...")
    patienten_csv = lade_csv_daten("patienten.csv")
    
    count_imported = 0
    
    for patient_data in patienten_csv:
        email = patient_data.get('email', '')
        if not email:
            continue
            
        # Überprüfen, ob der Patient bereits existiert
        existierender_patient = models.Patient.query.filter_by(email=email).first()
        if existierender_patient:
            print(f"Patient wird übersprungen (existiert bereits): {email}")
            continue
        
        # Neuen Patienten erstellen
        neuer_patient = models.Patient(
            email=email,
            password_hash=patient_data.get('passwort_hash', generate_password_hash('defaultpassword')),
            vorname=patient_data.get('vorname', ''),
            nachname=patient_data.get('nachname', ''),
            telefon=patient_data.get('telefon', ''),
            is_active=True
        )
        
        db.session.add(neuer_patient)
        count_imported += 1
    
    db.session.commit()
    print(f"Migration abgeschlossen: {count_imported} Patienten importiert.")

if __name__ == "__main__":
    print("Starte Datenmigration...")
    
    with app.app_context():
        # Alle Tabellen erstellen
        db.create_all()
        
        # Daten migrieren
        migriere_praxen()
        migriere_zahnaerzte()
        migriere_claims()
        migriere_paket_buchungen()
        migriere_patienten()
        
        print("Datenmigration abgeschlossen!")