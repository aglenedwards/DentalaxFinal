import os
import logging
from datetime import datetime
from flask import Flask, flash, redirect, request
from flask_wtf.csrf import CSRFProtect, CSRFError
from database import db

logging.basicConfig(level=logging.DEBUG)

csrf = CSRFProtect()

app = Flask(__name__)

app.secret_key = os.environ.get("SESSION_SECRET")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 86400
app.config["GOOGLE_MAPS_API_KEY"] = os.environ.get("GOOGLE_MAPS_API_KEY", "")

db.init_app(app)
csrf.init_app(app)

app.jinja_env.globals['now'] = datetime.now

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    app.logger.error(f'CSRF Error: {e.description} | URL: {request.url} | Referrer: {request.referrer}')
    flash('Sicherheitsfehler. Bitte laden Sie die Seite neu und versuchen Sie es erneut.', 'danger')
    if request.referrer:
        return redirect(request.referrer)
    return redirect('/')

# Alte Routen importieren (diese werden später ersetzt)
from app import *

# CSRF-Ausnahmen für Routen die in der Iframe-Umgebung problematisch sind
from app import zahnarzt_passwort_vergessen, zahnarzt_passwort_reset
csrf.exempt(zahnarzt_passwort_vergessen)
csrf.exempt(zahnarzt_passwort_reset)

# Datenbank-Models importieren
with app.app_context():
    from models import *
    db.create_all()

    # Schema-Migration: fehlende Spalten hinzufügen (produktionssicher)
    try:
        db.session.execute(db.text('ALTER TABLE praxis ADD COLUMN IF NOT EXISTS ist_demo BOOLEAN DEFAULT FALSE'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Schema-Migration ist_demo übersprungen: {e}")

    # Schema-Migration: E-Mail-Verifizierungs-Token für Zahnarzt
    try:
        db.session.execute(db.text('ALTER TABLE zahnarzt ADD COLUMN IF NOT EXISTS email_verify_token VARCHAR(100)'))
        db.session.execute(db.text('ALTER TABLE zahnarzt ADD COLUMN IF NOT EXISTS email_verify_expires TIMESTAMP'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Schema-Migration email_verify_token übersprungen: {e}")

    # Demo-Praxen als Demo markieren + Slug korrigieren (einmalige Migration)
    try:
        from models import Praxis
        # Testpraxis auf kanonischen Demo-Slug umbenennen
        testpraxis = Praxis.query.filter_by(slug='testpraxis-bodenheim').first()
        if testpraxis:
            testpraxis.slug = 'praxis-mustermann-mainz'
            testpraxis.ist_demo = True
        # Zweite Testpraxis ebenfalls als Demo markieren
        dr_muste = Praxis.query.filter_by(slug='zahnarztpraxis-dr-muste-mainz').first()
        if dr_muste and not dr_muste.ist_demo:
            dr_muste.ist_demo = True
        # Kanonische Demo-Praxis per neuem Slug markieren
        mustermann = Praxis.query.filter_by(slug='praxis-mustermann-mainz').first()
        if mustermann and not mustermann.ist_demo:
            mustermann.ist_demo = True
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Demo-Migration übersprungen: {e}")

    # Einmalige Bereinigung verwaister Zahnarzt-Accounts (praxis_id IS NULL)
    # Läuft beim Start und bereinigt Accounts die nach dem Löschen einer Praxis übrig geblieben sind
    try:
        from models import Zahnarzt, Praxis
        verwaiste = Zahnarzt.query.filter(Zahnarzt.praxis_id == None).all()
        if verwaiste:
            print(f"🧹 Startup-Bereinigung: {len(verwaiste)} verwaiste Zahnarzt-Account(s) werden gelöscht...")
            for za in verwaiste:
                Praxis.query.filter_by(zahnarzt_id=za.id).update({'zahnarzt_id': None})
                db.session.flush()
                db.session.delete(za)
            db.session.commit()
            print(f"✅ {len(verwaiste)} verwaiste(r) Zahnarzt-Account(s) bereinigt.")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Startup-Bereinigung verwaister Accounts übersprungen: {e}")

    # Neue Routen importieren
    try:
        from db_praxis_route import *
        print("✅ Praxis-Routen erfolgreich geladen")
    except Exception as e:
        print(f"❌ Fehler beim Laden der Praxis-Routen: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
