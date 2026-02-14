from database import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Zahnarzt(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    vorname = db.Column(db.String(50))
    nachname = db.Column(db.String(50))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Zahnarzt {self.email}>'

class Patient(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    vorname = db.Column(db.String(50), nullable=False)
    nachname = db.Column(db.String(50), nullable=False)
    telefon = db.Column(db.String(20))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Beziehungen
    termine = db.relationship('Termin', backref='patient', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Patient {self.vorname} {self.nachname}>'

class Praxis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    strasse = db.Column(db.String(100), nullable=False)
    plz = db.Column(db.String(10), nullable=False)
    stadt = db.Column(db.String(50), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    webseite = db.Column(db.String(255))
    beschreibung = db.Column(db.Text)
    
    # Geodaten
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Paketinformationen
    paket = db.Column(db.String(50), default='basic')  # basic, premium, premiumplus
    paket_aktiv_bis = db.Column(db.DateTime)
    zahlungsart = db.Column(db.String(50))  # monatlich, jaehrlich
    
    # Stripe Subscription Felder
    stripe_customer_id = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))
    stripe_subscription_status = db.Column(db.String(50))  # active, canceled, past_due, etc.
    
    # Terminbuchung
    terminbuchung_aktiv = db.Column(db.Boolean, default=True)
    terminbuchung_modus = db.Column(db.String(20), default='dashboard')  # dashboard, api, redirect, formular
    terminbuchung_url = db.Column(db.String(255))  # Für Redirect-Modus
    api_key = db.Column(db.String(50))  # API-Schlüssel für API-Integration
    
    # Erweiterte Terminbuchungsoptionen
    extern_anbieter = db.Column(db.String(50))  # doctolib, jameda, etc.
    api_anbieter = db.Column(db.String(50))  # medatixx, cgm, etc.
    formular_email = db.Column(db.String(120))  # E-Mail für Formular-Terminanfragen
    formular_text = db.Column(db.Text)  # Zusätzlicher Text für Terminformular
    termin_dauer = db.Column(db.Integer, default=30)  # Standard-Termindauer in Minuten
    vorlaufzeit = db.Column(db.Integer, default=2)  # Vorlaufzeit für Buchungen in Tagen
    buchungshorizont = db.Column(db.Integer, default=4)  # Buchungshorizont in Wochen (1-12)
    termine_auto_bestaetigen = db.Column(db.Boolean, default=False)
    
    # Metadaten
    erstelldatum = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ist_verifiziert = db.Column(db.Boolean, default=False)
    
    # Landing Page Felder
    landingpage_aktiv = db.Column(db.Boolean, default=False)
    hero_titel = db.Column(db.String(255))
    hero_untertitel = db.Column(db.String(500))
    hero_button_text = db.Column(db.String(100), default='Termin vereinbaren')
    ueber_uns_titel = db.Column(db.String(255), default='Willkommen in unserer Praxis')
    ueber_uns_text = db.Column(db.Text)
    farbschema = db.Column(db.String(20), default='blau')
    
    # SEO Felder
    seo_titel = db.Column(db.String(100))
    seo_beschreibung = db.Column(db.String(200))
    seo_keywords = db.Column(db.String(255))
    
    # Leistungsschwerpunkte (kommagetrennte Slugs: implantologie,kieferorthopaedie,prophylaxe)
    leistungsschwerpunkte = db.Column(db.String(500))
    
    # Google Bewertungen
    google_place_id = db.Column(db.String(255))
    google_rating = db.Column(db.Float)
    google_review_count = db.Column(db.Integer)
    google_maps_url = db.Column(db.String(500))
    google_sync_datum = db.Column(db.DateTime)
    
    # Matching-Felder für Dental Match Chatbot
    angstpatientenfreundlich = db.Column(db.Boolean, default=False)
    kinderfreundlich = db.Column(db.Boolean, default=False)
    barrierefrei = db.Column(db.Boolean, default=False)
    sprachen = db.Column(db.String(255))  # Kommagetrennt: Deutsch,Englisch,Türkisch
    abendsprechstunde = db.Column(db.Boolean, default=False)
    samstagssprechstunde = db.Column(db.Boolean, default=False)
    
    # Beziehungen
    zahnarzt_id = db.Column(db.Integer, db.ForeignKey('zahnarzt.id'))
    oeffnungszeiten = db.relationship('Oeffnungszeit', backref='praxis', lazy=True, cascade="all, delete-orphan")
    leistungen = db.relationship('Leistung', backref='praxis', lazy=True, cascade="all, delete-orphan")
    team_mitglieder = db.relationship('TeamMitglied', backref='praxis', lazy=True, cascade="all, delete-orphan")
    termine = db.relationship('Termin', backref='praxis', lazy=True, cascade="all, delete-orphan")
    bilder = db.relationship('PraxisBild', backref='praxis', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Praxis {self.name}>'

class Oeffnungszeit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(20), nullable=False)  # Montag, Dienstag, etc.
    von = db.Column(db.Time)
    bis = db.Column(db.Time)
    geschlossen = db.Column(db.Boolean, default=False)
    
    # Fremdschlüssel
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)

class Leistung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text)
    icon = db.Column(db.String(50))  # CSS-Klassenname, z.B. "fas fa-tooth"
    
    # Fremdschlüssel
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)

class TeamMitglied(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    beschreibung = db.Column(db.Text)
    bild_pfad = db.Column(db.String(255))
    qualifikationen = db.Column(db.Text)
    sprachen = db.Column(db.String(255))
    schwerpunkte = db.Column(db.String(255))
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)

class Bestandspatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vorname = db.Column(db.String(50), nullable=False)
    nachname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120))
    telefon = db.Column(db.String(30))
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    letzter_besuch = db.Column(db.Date)
    naechster_recall = db.Column(db.Date)
    recall_aktiv = db.Column(db.Boolean, default=True)
    recall_gesendet = db.Column(db.Boolean, default=False)
    recall_intervall_monate = db.Column(db.Integer, default=6)
    
    notizen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    praxis = db.relationship('Praxis', backref=db.backref('bestandspatienten', lazy=True))
    termine = db.relationship('Termin', backref='bestandspatient', lazy=True)
    
    @property
    def voller_name(self):
        return f"{self.vorname} {self.nachname}"
    
    @property
    def termine_count(self):
        return len(self.termine)
    
    def __repr__(self):
        return f'<Bestandspatient {self.vorname} {self.nachname}>'


class Termin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Date, nullable=False)
    uhrzeit = db.Column(db.Time, nullable=False)
    end_zeit = db.Column(db.Time)
    dauer_minuten = db.Column(db.Integer, default=30)
    grund = db.Column(db.String(255))
    notizen = db.Column(db.Text)
    status = db.Column(db.String(20), default='ausstehend')
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    behandlungsart_id = db.Column(db.Integer, db.ForeignKey('behandlungsart.id'))
    bestandspatient_id = db.Column(db.Integer, db.ForeignKey('bestandspatient.id'), nullable=True)
    
    gast_name = db.Column(db.String(100))
    gast_email = db.Column(db.String(120))
    gast_telefon = db.Column(db.String(30))
    ist_gast = db.Column(db.Boolean, default=False)
    
    bestaetigung_token = db.Column(db.String(100))
    bestaetigung_gesendet = db.Column(db.Boolean, default=False)
    
    erinnerung_gesendet = db.Column(db.Boolean, default=False)
    
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    behandlungsart = db.relationship('Behandlungsart', backref='termine')
    
    @property
    def patient_name(self):
        if self.bestandspatient:
            return self.bestandspatient.voller_name
        if self.ist_gast and self.gast_name:
            return self.gast_name
        elif self.patient:
            return f"{self.patient.vorname} {self.patient.nachname}"
        return "Unbekannt"
    
    @property
    def kontakt_email(self):
        if self.bestandspatient and self.bestandspatient.email:
            return self.bestandspatient.email
        if self.ist_gast:
            return self.gast_email
        elif self.patient:
            return self.patient.email
        return None
    
    @property
    def kontakt_telefon(self):
        if self.bestandspatient and self.bestandspatient.telefon:
            return self.bestandspatient.telefon
        if self.ist_gast:
            return self.gast_telefon
        elif self.patient:
            return self.patient.telefon
        return None
    
    @property
    def ist_bestandspatient(self):
        return self.bestandspatient_id is not None

class PraxisBild(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(20), nullable=False)  # logo, titelbild, team_foto, galerie
    pfad = db.Column(db.String(255), nullable=False)
    
    # Fremdschlüssel
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)

class PaketBuchung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paket = db.Column(db.String(50), nullable=False)  # premium, premiumplus
    zahlweise = db.Column(db.String(20), nullable=False)  # monatlich, jaehrlich
    preis = db.Column(db.Float, nullable=False)
    zahlungsmethode = db.Column(db.String(50), nullable=False)  # stripe
    zahlungsstatus = db.Column(db.String(20), nullable=False)  # ausstehend, bezahlt, fehlgeschlagen
    
    # Stripe-Metadaten
    stripe_session_id = db.Column(db.String(255))
    
    # Fremdschlüssel (nur praxis_id, da Buchungen von Zahnärzten gemacht werden)
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    # Metadaten
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    bezahlt_am = db.Column(db.DateTime)

class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    praxis_name = db.Column(db.String(100), nullable=False)
    plz = db.Column(db.String(10), nullable=False)
    strasse = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, verifying, approved, rejected
    
    # Fremdschlüssel zu Zahnarzt und Praxis
    zahnarzt_id = db.Column(db.Integer, db.ForeignKey('zahnarzt.id'))
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'))
    
    # Verifizierung
    verification_token = db.Column(db.String(100))
    token_expires_at = db.Column(db.DateTime)
    verification_method = db.Column(db.String(20), default='email')  # email, phone, document
    verification_attempts = db.Column(db.Integer, default=0)
    verified_at = db.Column(db.DateTime)
    
    # Paketauswahl
    gewaehltes_paket = db.Column(db.String(50))  # basic, premium, premiumplus
    
    # Metadaten
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    bearbeitet_am = db.Column(db.DateTime)
    notizen = db.Column(db.Text)
    
    # Beziehungen
    praxis = db.relationship('Praxis', backref=db.backref('claims', lazy=True))

class Bewertung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    bewertung = db.Column(db.Integer, nullable=False)
    sterne = db.Column(db.Integer)
    text = db.Column(db.Text)
    datum = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='ausstehend')  # ausstehend, bestaetigt, freigegeben, abgelehnt
    quelle = db.Column(db.String(20), default='patient')  # patient, dashboard, google
    bestaetigungs_token = db.Column(db.String(100))
    bestaetigt = db.Column(db.Boolean, default=False)
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('bewertungen', lazy=True))

class Terminanfrage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefon = db.Column(db.String(30))
    wunschtermin = db.Column(db.String(100))
    grund = db.Column(db.String(50))
    nachricht = db.Column(db.Text)
    status = db.Column(db.String(20), default='neu')
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    bearbeitet_am = db.Column(db.DateTime)
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('terminanfragen', lazy=True))


class Behandlungsart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    beschreibung = db.Column(db.Text)
    dauer_minuten = db.Column(db.Integer, default=30)
    farbe = db.Column(db.String(20), default='#4ECDC4')
    icon = db.Column(db.String(50), default='fa-tooth')
    aktiv = db.Column(db.Boolean, default=True)
    reihenfolge = db.Column(db.Integer, default=0)
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('behandlungsarten', lazy=True, cascade="all, delete-orphan"))
    
    def __repr__(self):
        return f'<Behandlungsart {self.name}>'


class Verfuegbarkeit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wochentag = db.Column(db.Integer, nullable=False)  # 0=Montag, 6=Sonntag
    start_zeit = db.Column(db.Time, nullable=False)
    end_zeit = db.Column(db.Time, nullable=False)
    slot_dauer = db.Column(db.Integer, default=30)  # Minuten pro Slot
    pause_nach_termin = db.Column(db.Integer, default=0)  # Puffer zwischen Terminen
    aktiv = db.Column(db.Boolean, default=True)
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('verfuegbarkeiten', lazy=True, cascade="all, delete-orphan"))
    
    @property
    def wochentag_name(self):
        tage = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        return tage[self.wochentag] if 0 <= self.wochentag <= 6 else 'Unbekannt'
    
    def __repr__(self):
        return f'<Verfuegbarkeit {self.wochentag_name} {self.start_zeit}-{self.end_zeit}>'


class Ausnahme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Date, nullable=False)
    ganztags_geschlossen = db.Column(db.Boolean, default=True)
    start_zeit = db.Column(db.Time)  # Falls nur teilweise geschlossen
    end_zeit = db.Column(db.Time)
    grund = db.Column(db.String(100))  # z.B. "Urlaub", "Fortbildung"
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('ausnahmen', lazy=True, cascade="all, delete-orphan"))
    
    def __repr__(self):
        return f'<Ausnahme {self.datum} - {self.grund}>'


class Stellenangebot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    
    titel = db.Column(db.String(150), nullable=False)
    position = db.Column(db.String(50), nullable=False)  # zfa, zmf, zahnarzt, etc.
    anstellungsart = db.Column(db.String(50), nullable=False)  # vollzeit, teilzeit, ausbildung
    
    ueber_uns = db.Column(db.Text)
    aufgaben = db.Column(db.Text)
    anforderungen = db.Column(db.Text)
    wir_bieten = db.Column(db.Text)
    
    gehalt_von = db.Column(db.Integer)
    gehalt_bis = db.Column(db.Integer)
    gehalt_anzeigen = db.Column(db.Boolean, default=False)
    
    erfahrung_jahre = db.Column(db.Integer, default=0)
    arbeitsbeginn = db.Column(db.String(100))  # z.B. "Ab sofort", "01.05.2025"
    
    tags = db.Column(db.Text)  # Kommasepariert: "Prophylaxe,Digitale Praxis,Flexible Arbeitszeiten"
    
    standort_plz = db.Column(db.String(10))
    standort_stadt = db.Column(db.String(100))
    standort_strasse = db.Column(db.String(150))
    
    ist_aktiv = db.Column(db.Boolean, default=True)
    ist_premium = db.Column(db.Boolean, default=False)
    
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    veroeffentlicht_am = db.Column(db.DateTime)
    ablaufdatum = db.Column(db.DateTime)
    
    praxis_id = db.Column(db.Integer, db.ForeignKey('praxis.id'), nullable=False)
    
    praxis = db.relationship('Praxis', backref=db.backref('stellenangebote', lazy=True, cascade="all, delete-orphan"))
    
    @property
    def tags_liste(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []
    
    @property
    def position_display(self):
        positionen = {
            'zfa': 'Zahnmedizinische/r Fachangestellte/r (ZFA)',
            'zmf': 'Zahnmedizinische/r Fachassistent/in (ZMF)',
            'zmv': 'Zahnmedizinische/r Verwaltungsassistent/in (ZMV)',
            'zmp': 'Zahnmedizinische/r Prophylaxeassistent/in (ZMP)',
            'dh': 'Dentalhygieniker/in (DH)',
            'prophylaxe': 'Prophylaxe-Assistent/in',
            'zahnarzt': 'Zahnarzt/Zahnärztin',
            'kfo': 'Kieferorthopäde/in',
            'oralchirurg': 'Oralchirurg/in / MKG',
            'implantologe': 'Implantologe/in',
            'endodontologe': 'Endodontologe/in',
            'parodontologe': 'Parodontologe/in',
            'zahntechniker': 'Zahntechniker/in',
            'praxismanager': 'Praxismanager/in',
            'rezeption': 'Rezeption / Empfang',
            'abrechnung': 'Abrechnung',
            'verwaltung': 'Verwaltungsangestellte/r',
            'azubi': 'Auszubildende/r zur ZFA',
            'sonstige': 'Sonstige Position'
        }
        return positionen.get(self.position, self.position)
    
    @property
    def anstellungsart_display(self):
        arten = {
            'vollzeit': 'Vollzeit',
            'teilzeit': 'Teilzeit',
            'ausbildung': 'Ausbildung',
            'minijob': 'Minijob',
            'praktikum': 'Praktikum'
        }
        return arten.get(self.anstellungsart, self.anstellungsart)
    
    def __repr__(self):
        return f'<Stellenangebot {self.titel}>'


class Bewerbung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    vorname = db.Column(db.String(50), nullable=False)
    nachname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefon = db.Column(db.String(30))
    
    anschreiben = db.Column(db.Text)
    lebenslauf_pfad = db.Column(db.String(255))
    weitere_dokumente_pfad = db.Column(db.String(255))
    
    anschreiben_pfad = db.Column(db.String(255))
    zeugnisse_pfad = db.Column(db.String(255))
    
    adresse = db.Column(db.String(200))
    plz = db.Column(db.String(10))
    ort = db.Column(db.String(100))
    
    berufserfahrung = db.Column(db.String(20))
    fruehester_eintritt = db.Column(db.String(30))
    gehaltsvorstellung = db.Column(db.String(50))
    nachricht = db.Column(db.Text)
    
    status = db.Column(db.String(30), default='neu')  # neu, gesehen, kontaktiert, abgelehnt, eingestellt
    notizen = db.Column(db.Text)
    
    eingegangen_am = db.Column(db.DateTime, default=datetime.utcnow)
    gelesen_am = db.Column(db.DateTime)
    
    stellenangebot_id = db.Column(db.Integer, db.ForeignKey('stellenangebot.id'), nullable=False)
    
    stellenangebot = db.relationship('Stellenangebot', backref=db.backref('bewerbungen', lazy=True, cascade="all, delete-orphan"))
    
    @property
    def status_display(self):
        status_labels = {
            'neu': 'Neu',
            'gesehen': 'Gesehen',
            'kontaktiert': 'Kontaktiert',
            'abgelehnt': 'Abgelehnt',
            'eingestellt': 'Eingestellt'
        }
        return status_labels.get(self.status, self.status)
    
    @property
    def status_farbe(self):
        farben = {
            'neu': 'primary',
            'gesehen': 'info',
            'kontaktiert': 'warning',
            'abgelehnt': 'danger',
            'eingestellt': 'success'
        }
        return farben.get(self.status, 'secondary')
    
    def __repr__(self):
        return f'<Bewerbung {self.vorname} {self.nachname}>'


class JobAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(50))
    ort = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    umkreis_km = db.Column(db.Integer, default=50)
    ist_aktiv = db.Column(db.Boolean, default=False)
    bestaetigt_am = db.Column(db.DateTime)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    bestaetigungs_token = db.Column(db.String(100), unique=True)
    
    def __repr__(self):
        return f'<JobAlert {self.email} - {self.position}>'


class ExternesInserat(db.Model):
    """Externe Stellenangebote von TheirStack API (für SEO und Content)"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True, nullable=False)  # TheirStack Job ID
    
    titel = db.Column(db.String(255), nullable=False)
    unternehmen = db.Column(db.String(200), nullable=False)
    standort = db.Column(db.String(200))
    standort_stadt = db.Column(db.String(100))
    standort_plz = db.Column(db.String(10))
    
    beschreibung = db.Column(db.Text)
    position_kategorie = db.Column(db.String(50))  # zfa, zahnarzt, etc.
    anstellungsart = db.Column(db.String(50))  # vollzeit, teilzeit
    
    gehalt_min = db.Column(db.Integer)
    gehalt_max = db.Column(db.Integer)
    
    externe_url = db.Column(db.Text, nullable=False)  # Link zur Originalquelle
    quelle = db.Column(db.String(100))  # z.B. "stepstone", "indeed", etc.
    
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    veroeffentlicht_am = db.Column(db.DateTime)
    abgerufen_am = db.Column(db.DateTime, default=datetime.utcnow)
    ist_aktiv = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<ExternesInserat {self.titel} bei {self.unternehmen}>'
    
    @property
    def position_display(self):
        positionen = {
            'zfa': 'Zahnmedizinische/r Fachangestellte/r (ZFA)',
            'zmf': 'Zahnmedizinische/r Fachassistent/in (ZMF)',
            'zmv': 'Zahnmedizinische/r Verwaltungsassistent/in (ZMV)',
            'zmp': 'Zahnmedizinische/r Prophylaxeassistent/in (ZMP)',
            'dh': 'Dentalhygieniker/in (DH)',
            'prophylaxe': 'Prophylaxe-Assistent/in',
            'zahnarzt': 'Zahnarzt/Zahnärztin',
            'kfo': 'Kieferorthopäde/in',
            'oralchirurg': 'Oralchirurg/in / MKG',
            'implantologe': 'Implantologe/in',
            'endodontologe': 'Endodontologe/in',
            'parodontologe': 'Parodontologe/in',
            'zahntechniker': 'Zahntechniker/in',
            'praxismanager': 'Praxismanager/in',
            'rezeption': 'Rezeption / Empfang',
            'abrechnung': 'Abrechnung',
            'verwaltung': 'Verwaltungsangestellte/r',
            'azubi': 'Auszubildende/r zur ZFA',
            'dental': 'Dental-Fachkraft',
            'sonstige': 'Sonstige Position'
        }
        return positionen.get(self.position_kategorie, self.position_kategorie or 'Dental-Fachkraft')
    
    @property
    def anstellungsart_display(self):
        arten = {
            'vollzeit': 'Vollzeit',
            'teilzeit': 'Teilzeit',
            'ausbildung': 'Ausbildung',
            'minijob': 'Minijob',
            'praktikum': 'Praktikum'
        }
        return arten.get(self.anstellungsart, self.anstellungsart or 'Vollzeit')


class StadtSEO(db.Model):
    """SEO-Texte für Stadtseiten"""
    id = db.Column(db.Integer, primary_key=True)
    stadt_slug = db.Column(db.String(100), unique=True, nullable=False)  # z.B. "muenchen"
    stadt_name = db.Column(db.String(100), nullable=False)  # z.B. "München"
    
    # SEO Meta
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    
    # H1 und Teaser
    h1_titel = db.Column(db.String(200))
    teaser_text = db.Column(db.Text)
    
    # Erster SEO-Block
    h2_titel_1 = db.Column(db.String(200))
    seo_text_1 = db.Column(db.Text)
    
    # Zweiter SEO-Block
    h2_titel_2 = db.Column(db.String(200))
    seo_text_2 = db.Column(db.Text)
    
    # FAQ als JSON (Liste von {frage, antwort} Objekten)
    faq_json = db.Column(db.Text)  # JSON-String mit FAQ-Einträgen
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<StadtSEO {self.stadt_name}>'


class LeistungStadtSEO(db.Model):
    """SEO-Texte für Leistung+Stadt-Kombinationsseiten (z.B. Implantologie München)"""
    id = db.Column(db.Integer, primary_key=True)
    leistung_slug = db.Column(db.String(100), nullable=False)  # z.B. "implantologie"
    stadt_slug = db.Column(db.String(100), nullable=False)  # z.B. "muenchen"
    stadt_name = db.Column(db.String(100), nullable=False)  # z.B. "München"
    leistung_name = db.Column(db.String(100), nullable=False)  # z.B. "Implantologie"
    
    # SEO Meta
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    
    # H1 und Teaser
    h1_titel = db.Column(db.String(200))
    teaser_text = db.Column(db.Text)
    
    # Erster SEO-Block
    h2_titel_1 = db.Column(db.String(200))
    seo_text_1 = db.Column(db.Text)
    
    # Zweiter SEO-Block
    h2_titel_2 = db.Column(db.String(200))
    seo_text_2 = db.Column(db.Text)
    
    # FAQ als JSON (Liste von {frage, antwort} Objekten)
    faq_json = db.Column(db.Text)  # JSON-String mit FAQ-Einträgen
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint für Leistung+Stadt Kombination
    __table_args__ = (
        db.UniqueConstraint('leistung_slug', 'stadt_slug', name='unique_leistung_stadt'),
    )
    
    def __repr__(self):
        return f'<LeistungStadtSEO {self.leistung_name} {self.stadt_name}>'


class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
    
    @staticmethod
    def get(key, default=''):
        setting = SiteSettings.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @staticmethod
    def set(key, value):
        setting = SiteSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = SiteSettings(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
    
    def __repr__(self):
        return f'<SiteSettings {self.key}={self.value}>'