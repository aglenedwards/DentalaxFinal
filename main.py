import os
import logging
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
    
    # Neue Routen importieren
    try:
        from db_praxis_route import *
        print("✅ Praxis-Routen erfolgreich geladen")
    except Exception as e:
        print(f"❌ Fehler beim Laden der Praxis-Routen: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
