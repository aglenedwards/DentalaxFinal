import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

BREVO_SMTP_SERVER = "smtp-relay.brevo.com"
BREVO_SMTP_PORT = 587

def send_email(to_email, subject, html_body, text_body=None):
    smtp_login = os.environ.get("BREVO_SMTP_LOGIN")
    smtp_password = os.environ.get("BREVO_SMTP_PASSWORD")
    mail_sender = os.environ.get("MAIL_SENDER")

    if not all([smtp_login, smtp_password, mail_sender]):
        logger.error("E-Mail-Konfiguration unvollständig. BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD oder MAIL_SENDER fehlt.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Dentalax <{mail_sender}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(BREVO_SMTP_SERVER, BREVO_SMTP_PORT) as server:
            server.starttls()
            server.login(smtp_login, smtp_password)
            server.sendmail(mail_sender, to_email, msg.as_string())
        logger.info(f"E-Mail erfolgreich gesendet an {to_email}")
        return True
    except Exception as e:
        logger.error(f"Fehler beim E-Mail-Versand an {to_email}: {e}")
        return False


def send_bewertung_bestaetigung(to_email, praxis_name, bestaetigungs_url):
    subject = f"Bitte bestätigen Sie Ihre Bewertung für {praxis_name} - Dentalax"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Bewertung bestätigen</h2>

    <p>Vielen Dank für Ihre Bewertung der Praxis <strong>{praxis_name}</strong>!</p>

    <p>Bitte klicken Sie auf den folgenden Button, um Ihre Bewertung zu bestätigen und zu veröffentlichen:</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{bestaetigungs_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Bewertung bestätigen
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{bestaetigungs_url}" style="color: #17a2b8; word-break: break-all;">{bestaetigungs_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <div style="font-size: 12px; color: #999; padding: 15px; background-color: #f8f9fa; border-radius: 6px;">
        <p style="margin: 0 0 8px 0;"><strong>Hinweis zum Datenschutz:</strong></p>
        <p style="margin: 0 0 5px 0;">Diese E-Mail wurde im Rahmen der Verifizierung Ihrer Bewertung auf Dentalax versendet. Ihre E-Mail-Adresse wird ausschließlich zur Bestätigung dieser Bewertung verwendet und nicht an Dritte weitergegeben.</p>
        <p style="margin: 0 0 5px 0;">Nach erfolgreicher Bestätigung wird Ihre E-Mail-Adresse nicht für Werbezwecke oder weitere Kontaktaufnahmen genutzt.</p>
        <p style="margin: 0;">Falls Sie diese Bewertung nicht abgegeben haben, können Sie diese E-Mail ignorieren. In diesem Fall werden Ihre Daten nicht weiterverarbeitet.</p>
    </div>

    <p style="font-size: 12px; color: #999; text-align: center; margin-top: 15px;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Bewertung bestätigen - Dentalax

Vielen Dank für Ihre Bewertung der Praxis {praxis_name}!

Bitte klicken Sie auf den folgenden Link, um Ihre Bewertung zu bestätigen:
{bestaetigungs_url}

Hinweis zum Datenschutz:
Diese E-Mail wurde im Rahmen der Verifizierung Ihrer Bewertung auf Dentalax versendet. Ihre E-Mail-Adresse wird ausschließlich zur Bestätigung dieser Bewertung verwendet und nicht an Dritte weitergegeben. Nach erfolgreicher Bestätigung wird Ihre E-Mail-Adresse nicht für Werbezwecke oder weitere Kontaktaufnahmen genutzt.

Falls Sie diese Bewertung nicht abgegeben haben, können Sie diese E-Mail ignorieren. In diesem Fall werden Ihre Daten nicht weiterverarbeitet.

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_zahnarzt_bestaetigung(to_email, praxis_name, bestaetigungs_url):
    subject = f"Bestätigen Sie Ihre Registrierung bei Dentalax"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Registrierung bestätigen</h2>

    <p>Vielen Dank für Ihre Registrierung der Praxis <strong>{praxis_name}</strong> bei Dentalax!</p>

    <p>Bitte klicken Sie auf den folgenden Button, um Ihre E-Mail-Adresse zu bestätigen:</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{bestaetigungs_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Registrierung bestätigen
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{bestaetigungs_url}" style="color: #17a2b8; word-break: break-all;">{bestaetigungs_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        Falls Sie sich nicht bei Dentalax registriert haben, können Sie diese E-Mail ignorieren.<br>
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Registrierung bestätigen - Dentalax

Vielen Dank für Ihre Registrierung der Praxis {praxis_name} bei Dentalax!

Bitte klicken Sie auf den folgenden Link, um Ihre E-Mail-Adresse zu bestätigen:
{bestaetigungs_url}

Falls Sie sich nicht bei Dentalax registriert haben, können Sie diese E-Mail ignorieren.

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_praxis_verifizierung(to_email, praxis_name, bestaetigungs_url):
    subject = f"Bestätigen Sie die Übernahme Ihrer Praxis - Dentalax"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Praxis-Übernahme bestätigen</h2>

    <p>Sie möchten die Praxis <strong>{praxis_name}</strong> bei Dentalax übernehmen.</p>

    <p>Bitte klicken Sie auf den folgenden Button, um die Übernahme zu bestätigen:</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{bestaetigungs_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Übernahme bestätigen
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{bestaetigungs_url}" style="color: #17a2b8; word-break: break-all;">{bestaetigungs_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        Falls Sie diese Übernahme nicht beantragt haben, können Sie diese E-Mail ignorieren.<br>
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Praxis-Übernahme bestätigen - Dentalax

Sie möchten die Praxis {praxis_name} bei Dentalax übernehmen.

Bitte klicken Sie auf den folgenden Link, um die Übernahme zu bestätigen:
{bestaetigungs_url}

Falls Sie diese Übernahme nicht beantragt haben, können Sie diese E-Mail ignorieren.

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_bestaetigung_patient(to_email, patient_name, praxis_name, datum_str, uhrzeit_str, praxis_telefon):
    subject = f"Terminanfrage erhalten - {praxis_name}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Ihre Terminanfrage wurde empfangen</h2>

    <p>Hallo <strong>{patient_name}</strong>,</p>

    <p>Ihre Terminanfrage bei <strong>{praxis_name}</strong> wurde erfolgreich übermittelt.</p>

    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>Datum:</strong> {datum_str}</p>
        <p style="margin: 5px 0;"><strong>Uhrzeit:</strong> {uhrzeit_str} Uhr</p>
        <p style="margin: 5px 0;"><strong>Praxis:</strong> {praxis_name}</p>
    </div>

    <p>Die Praxis wird Ihren Termin prüfen und bestätigen oder sich bei Ihnen melden.</p>

    {f'<p>Bei Fragen erreichen Sie die Praxis telefonisch unter: <strong>{praxis_telefon}</strong></p>' if praxis_telefon else ''}

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Terminanfrage erhalten - {praxis_name}

Hallo {patient_name},

Ihre Terminanfrage bei {praxis_name} wurde erfolgreich übermittelt.

Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
Praxis: {praxis_name}

Die Praxis wird Ihren Termin prüfen und bestätigen oder sich bei Ihnen melden.

{f'Bei Fragen erreichen Sie die Praxis telefonisch unter: {praxis_telefon}' if praxis_telefon else ''}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_benachrichtigung_zahnarzt(to_email, patient_name, patient_email, patient_telefon, datum_str, uhrzeit_str, behandlung, grund, dashboard_url):
    subject = f"Neue Terminanfrage - {datum_str} um {uhrzeit_str}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Neue Terminanfrage eingegangen</h2>

    <p>Es ist eine neue Terminanfrage über Ihre Landingpage eingegangen:</p>

    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>Patient:</strong> {patient_name}</p>
        <p style="margin: 5px 0;"><strong>E-Mail:</strong> {patient_email}</p>
        <p style="margin: 5px 0;"><strong>Telefon:</strong> {patient_telefon or 'Nicht angegeben'}</p>
        <p style="margin: 5px 0;"><strong>Datum:</strong> {datum_str}</p>
        <p style="margin: 5px 0;"><strong>Uhrzeit:</strong> {uhrzeit_str} Uhr</p>
        {f'<p style="margin: 5px 0;"><strong>Behandlung:</strong> {behandlung}</p>' if behandlung else ''}
        {f'<p style="margin: 5px 0;"><strong>Grund:</strong> {grund}</p>' if grund else ''}
    </div>

    <p>Bitte bestätigen oder lehnen Sie den Termin in Ihrem Dashboard ab.</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Termin im Dashboard verwalten
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{dashboard_url}" style="color: #17a2b8; word-break: break-all;">{dashboard_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Neue Terminanfrage - {datum_str} um {uhrzeit_str}

Es ist eine neue Terminanfrage über Ihre Landingpage eingegangen:

Patient: {patient_name}
E-Mail: {patient_email}
Telefon: {patient_telefon or 'Nicht angegeben'}
Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
{f'Behandlung: {behandlung}' if behandlung else ''}
{f'Grund: {grund}' if grund else ''}

Bitte bestätigen oder lehnen Sie den Termin in Ihrem Dashboard ab:
{dashboard_url}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_sofort_bestaetigt_patient(to_email, patient_name, praxis_name, datum_str, uhrzeit_str, praxis_telefon):
    subject = f"Terminbestätigung - {praxis_name}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #28a745;">Ihr Termin ist bestätigt!</h2>

    <p>Hallo <strong>{patient_name}</strong>,</p>

    <p>Ihr Termin bei <strong>{praxis_name}</strong> wurde bestätigt.</p>

    <div style="background-color: #d4edda; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #28a745;">
        <p style="margin: 5px 0;"><strong>Datum:</strong> {datum_str}</p>
        <p style="margin: 5px 0;"><strong>Uhrzeit:</strong> {uhrzeit_str} Uhr</p>
        <p style="margin: 5px 0;"><strong>Praxis:</strong> {praxis_name}</p>
    </div>

    <p>Bitte erscheinen Sie pünktlich zum Termin. Falls Sie den Termin absagen möchten, kontaktieren Sie die Praxis bitte rechtzeitig.</p>

    {f'<p>Bei Fragen erreichen Sie die Praxis telefonisch unter: <strong>{praxis_telefon}</strong></p>' if praxis_telefon else ''}

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Terminbestätigung - {praxis_name}

Hallo {patient_name},

Ihr Termin bei {praxis_name} wurde bestätigt.

Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
Praxis: {praxis_name}

Bitte erscheinen Sie pünktlich zum Termin. Falls Sie den Termin absagen möchten, kontaktieren Sie die Praxis bitte rechtzeitig.

{f'Bei Fragen erreichen Sie die Praxis telefonisch unter: {praxis_telefon}' if praxis_telefon else ''}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_auto_bestaetigt_zahnarzt(to_email, patient_name, patient_email, patient_telefon, datum_str, uhrzeit_str, behandlung, grund, dashboard_url):
    subject = f"Neuer Termin automatisch bestätigt - {datum_str} um {uhrzeit_str}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #28a745;">Neuer Termin automatisch bestätigt</h2>

    <p>Ein neuer Termin wurde über Ihre Landingpage gebucht und <strong>automatisch bestätigt</strong>:</p>

    <div style="background-color: #d4edda; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #28a745;">
        <p style="margin: 5px 0;"><strong>Patient:</strong> {patient_name}</p>
        <p style="margin: 5px 0;"><strong>E-Mail:</strong> {patient_email}</p>
        <p style="margin: 5px 0;"><strong>Telefon:</strong> {patient_telefon or 'Nicht angegeben'}</p>
        <p style="margin: 5px 0;"><strong>Datum:</strong> {datum_str}</p>
        <p style="margin: 5px 0;"><strong>Uhrzeit:</strong> {uhrzeit_str} Uhr</p>
        {f'<p style="margin: 5px 0;"><strong>Behandlung:</strong> {behandlung}</p>' if behandlung else ''}
        {f'<p style="margin: 5px 0;"><strong>Grund:</strong> {grund}</p>' if grund else ''}
    </div>

    <p>Der Patient wurde bereits per E-Mail über die Bestätigung informiert.</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Termin im Dashboard ansehen
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{dashboard_url}" style="color: #17a2b8; word-break: break-all;">{dashboard_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Neuer Termin automatisch bestätigt - {datum_str} um {uhrzeit_str}

Ein neuer Termin wurde über Ihre Landingpage gebucht und automatisch bestätigt:

Patient: {patient_name}
E-Mail: {patient_email}
Telefon: {patient_telefon or 'Nicht angegeben'}
Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
{f'Behandlung: {behandlung}' if behandlung else ''}
{f'Grund: {grund}' if grund else ''}

Der Patient wurde bereits per E-Mail über die Bestätigung informiert.

Termin im Dashboard ansehen: {dashboard_url}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_absage_patient(to_email, patient_name, praxis_name, datum_str, uhrzeit_str, absage_grund='', praxis_telefon=''):
    subject = f"Terminabsage - {praxis_name}"

    grund_html = f'<p><strong>Begründung:</strong> {absage_grund}</p>' if absage_grund else ''
    grund_text = f'\nBegründung: {absage_grund}' if absage_grund else ''

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #dc3545;">Ihr Termin wurde abgesagt</h2>

    <p>Hallo <strong>{patient_name}</strong>,</p>

    <p>leider wurde Ihr Termin bei <strong>{praxis_name}</strong> abgesagt.</p>

    <div style="background-color: #f8d7da; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #dc3545;">
        <p style="margin: 5px 0;"><strong>Datum:</strong> {datum_str}</p>
        <p style="margin: 5px 0;"><strong>Uhrzeit:</strong> {uhrzeit_str} Uhr</p>
        <p style="margin: 5px 0;"><strong>Praxis:</strong> {praxis_name}</p>
    </div>

    {grund_html}

    <p>Bitte vereinbaren Sie bei Bedarf einen neuen Termin über unsere Plattform oder kontaktieren Sie die Praxis direkt.</p>

    {f'<p>Bei Fragen erreichen Sie die Praxis telefonisch unter: <strong>{praxis_telefon}</strong></p>' if praxis_telefon else ''}

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Terminabsage - {praxis_name}

Hallo {patient_name},

leider wurde Ihr Termin bei {praxis_name} abgesagt.

Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
Praxis: {praxis_name}
{grund_text}

Bitte vereinbaren Sie bei Bedarf einen neuen Termin über unsere Plattform oder kontaktieren Sie die Praxis direkt.

{f'Bei Fragen erreichen Sie die Praxis telefonisch unter: {praxis_telefon}' if praxis_telefon else ''}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_recall_erinnerung(to_email, patient_name, praxis_name, praxis_telefon='', buchungs_url=''):
    subject = f"Erinnerung: Zeit für Ihre Vorsorgeuntersuchung - {praxis_name}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #17a2b8;">Zeit für Ihre Vorsorgeuntersuchung!</h2>

    <p>Hallo <strong>{patient_name}</strong>,</p>

    <p>Ihr letzter Besuch bei <strong>{praxis_name}</strong> liegt nun etwa 6 Monate zurück. 
    Wir möchten Sie daran erinnern, dass regelmäßige Vorsorgeuntersuchungen wichtig für Ihre Zahngesundheit sind.</p>

    <div style="background-color: #e8f4fd; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #17a2b8;">
        <p style="margin: 0; font-size: 16px;">
            <strong>Die Krankenkassen empfehlen halbjährliche Kontrolluntersuchungen.</strong><br>
            Regelmäßige Besuche helfen, Probleme frühzeitig zu erkennen und Ihr Bonusheft aktuell zu halten.
        </p>
    </div>

    {f'<div style="text-align: center; margin: 30px 0;"><a href="{buchungs_url}" style="background-color: #17a2b8; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Jetzt Termin vereinbaren</a></div>' if buchungs_url else ''}

    {f'<p>Sie können auch direkt in der Praxis anrufen: <strong>{praxis_telefon}</strong></p>' if praxis_telefon else ''}

    <p style="color: #666; font-size: 14px;">Wir freuen uns auf Ihren Besuch!</p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal<br>
        <em>Sie erhalten diese E-Mail, weil Sie Patient bei {praxis_name} sind. 
        Falls Sie keine weiteren Erinnerungen wünschen, teilen Sie dies bitte der Praxis mit.</em>
    </p>
</body>
</html>"""

    text_body = f"""Erinnerung: Zeit für Ihre Vorsorgeuntersuchung

Hallo {patient_name},

Ihr letzter Besuch bei {praxis_name} liegt nun etwa 6 Monate zurück.
Wir möchten Sie daran erinnern, dass regelmäßige Vorsorgeuntersuchungen wichtig für Ihre Zahngesundheit sind.

Die Krankenkassen empfehlen halbjährliche Kontrolluntersuchungen.
Regelmäßige Besuche helfen, Probleme frühzeitig zu erkennen und Ihr Bonusheft aktuell zu halten.

{f'Jetzt Termin vereinbaren: {buchungs_url}' if buchungs_url else ''}
{f'Oder rufen Sie direkt an: {praxis_telefon}' if praxis_telefon else ''}

Wir freuen uns auf Ihren Besuch!

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_termin_erinnerung_24h(to_email, patient_name, praxis_name, datum_str, uhrzeit_str, praxis_telefon='', praxis_adresse=''):
    subject = f"Erinnerung: Ihr Termin morgen bei {praxis_name}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #17a2b8;">Terminerinnerung</h2>

    <p>Hallo <strong>{patient_name}</strong>,</p>

    <p>wir möchten Sie an Ihren Termin bei <strong>{praxis_name}</strong> erinnern:</p>

    <div style="background-color: #e8f4fd; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #17a2b8;">
        <p style="margin: 0; font-size: 16px;">
            <strong>📅 Datum:</strong> {datum_str}<br>
            <strong>🕐 Uhrzeit:</strong> {uhrzeit_str} Uhr
        </p>
        {f'<p style="margin: 10px 0 0 0;"><strong>📍 Adresse:</strong> {praxis_adresse}</p>' if praxis_adresse else ''}
    </div>

    <p>Bitte kommen Sie pünktlich zu Ihrem Termin. Falls Sie den Termin nicht wahrnehmen können, 
    sagen Sie bitte rechtzeitig ab.</p>

    {f'<p>Sie erreichen uns telefonisch unter: <strong>{praxis_telefon}</strong></p>' if praxis_telefon else ''}

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal<br>
        <em>Sie erhalten diese E-Mail als automatische Terminerinnerung von {praxis_name}.</em>
    </p>
</body>
</html>"""

    text_body = f"""Terminerinnerung

Hallo {patient_name},

wir möchten Sie an Ihren Termin bei {praxis_name} erinnern:

Datum: {datum_str}
Uhrzeit: {uhrzeit_str} Uhr
{f'Adresse: {praxis_adresse}' if praxis_adresse else ''}

Bitte kommen Sie pünktlich. Falls Sie den Termin nicht wahrnehmen können, sagen Sie bitte rechtzeitig ab.

{f'Telefon: {praxis_telefon}' if praxis_telefon else ''}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_passwort_reset_email(to_email, vorname, reset_url):
    subject = "Passwort zurücksetzen - Dentalax"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Passwort zurücksetzen</h2>

    <p>Hallo {vorname},</p>

    <p>Sie haben angefordert, Ihr Passwort zurückzusetzen. Klicken Sie auf den folgenden Button, um ein neues Passwort festzulegen:</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{reset_url}" style="display: inline-block; padding: 14px 30px; background-color: #17a2b8; color: white; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px;">Neues Passwort festlegen</a>
    </div>

    <p style="color: #666; font-size: 14px;">Dieser Link ist <strong>1 Stunde</strong> gültig. Falls Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.</p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="color: #999; font-size: 12px; text-align: center;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{reset_url}" style="color: #17a2b8; word-break: break-all;">{reset_url}</a>
    </p>

    <p style="color: #999; font-size: 12px; text-align: center;">Dentalax - Ihr Zahnarzt-Portal</p>
</body>
</html>"""

    text_body = f"""Passwort zurücksetzen - Dentalax

Hallo {vorname},

Sie haben angefordert, Ihr Passwort zurückzusetzen.

Klicken Sie auf den folgenden Link, um ein neues Passwort festzulegen:
{reset_url}

Dieser Link ist 1 Stunde gültig. Falls Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_kontaktformular_weiterleitung(praxis_email, praxis_name, name, email, telefon, wunschtermin, grund, nachricht):
    subject = f"Neue Terminanfrage über Dentalax - {name}"

    grund_text = grund if grund else "Nicht angegeben"
    telefon_text = telefon if telefon else "Nicht angegeben"
    wunschtermin_text = wunschtermin if wunschtermin else "Nicht angegeben"
    nachricht_text = nachricht if nachricht else "Keine Nachricht"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h2 style="color: #17a2b8; margin-bottom: 5px;">Neue Terminanfrage</h2>
        <p style="color: #6c757d; font-size: 14px;">über Ihr Dentalax-Kontaktformular</p>
    </div>

    <div style="background: #f8f9fa; border-radius: 12px; padding: 24px; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: #333; font-size: 16px;">Kontaktdaten</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; color: #6c757d; width: 140px;"><strong>Name:</strong></td>
                <td style="padding: 8px 0;">{name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6c757d;"><strong>E-Mail:</strong></td>
                <td style="padding: 8px 0;"><a href="mailto:{email}" style="color: #17a2b8;">{email}</a></td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6c757d;"><strong>Telefon:</strong></td>
                <td style="padding: 8px 0;">{telefon_text}</td>
            </tr>
        </table>
    </div>

    <div style="background: #f8f9fa; border-radius: 12px; padding: 24px; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: #333; font-size: 16px;">Terminwunsch</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; color: #6c757d; width: 140px;"><strong>Wunschtermin:</strong></td>
                <td style="padding: 8px 0;">{wunschtermin_text}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6c757d;"><strong>Termingrund:</strong></td>
                <td style="padding: 8px 0;">{grund_text}</td>
            </tr>
        </table>
    </div>

    <div style="background: #f8f9fa; border-radius: 12px; padding: 24px; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: #333; font-size: 16px;">Nachricht</h3>
        <p style="margin: 0; line-height: 1.6;">{nachricht_text}</p>
    </div>

    <div style="text-align: center; padding: 20px 0; color: #6c757d; font-size: 12px; border-top: 1px solid #e9ecef;">
        <p>Diese Anfrage wurde über das Kontaktformular auf Ihrer Dentalax-Praxisseite gesendet.</p>
        <p style="margin-top: 5px;">© Dentalax - Ihr Zahnarzt-Portal</p>
    </div>
</body>
</html>"""

    text_body = f"""Neue Terminanfrage über Dentalax

Name: {name}
E-Mail: {email}
Telefon: {telefon_text}
Wunschtermin: {wunschtermin_text}
Termingrund: {grund_text}

Nachricht:
{nachricht_text}

---
Diese Anfrage wurde über Ihr Dentalax-Kontaktformular gesendet."""

    return send_email(praxis_email, subject, html_body, text_body)


def send_bewerbung_bestaetigung_bewerber(to_email, vorname, job_titel, praxis_name):
    subject = f"Bewerbungsbestätigung - {job_titel} bei {praxis_name}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Bewerbung erfolgreich eingegangen</h2>

    <p>Hallo <strong>{vorname}</strong>,</p>

    <p>vielen Dank für Ihre Bewerbung auf die Stelle <strong>{job_titel}</strong> bei <strong>{praxis_name}</strong>.</p>

    <div style="background-color: #d4edda; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #28a745;">
        <p style="margin: 5px 0;"><strong>Stelle:</strong> {job_titel}</p>
        <p style="margin: 5px 0;"><strong>Praxis:</strong> {praxis_name}</p>
    </div>

    <p>Ihre Bewerbungsunterlagen wurden erfolgreich übermittelt und werden von der Praxis geprüft. Sie werden sich bei Ihnen melden.</p>

    <p>Wir wünschen Ihnen viel Erfolg!</p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Bewerbungsbestätigung - {job_titel} bei {praxis_name}

Hallo {vorname},

vielen Dank für Ihre Bewerbung auf die Stelle {job_titel} bei {praxis_name}.

Ihre Bewerbungsunterlagen wurden erfolgreich übermittelt und werden von der Praxis geprüft. Sie werden sich bei Ihnen melden.

Wir wünschen Ihnen viel Erfolg!

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_bewerbung_benachrichtigung_zahnarzt(to_email, bewerber_vorname, bewerber_nachname, job_titel, praxis_name, dashboard_url):
    subject = f"Neue Bewerbung eingegangen - {job_titel}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Neue Bewerbung eingegangen</h2>

    <p>Für Ihre Praxis <strong>{praxis_name}</strong> ist eine neue Bewerbung eingegangen:</p>

    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>Bewerber/in:</strong> {bewerber_vorname} {bewerber_nachname}</p>
        <p style="margin: 5px 0;"><strong>Stelle:</strong> {job_titel}</p>
    </div>

    <p>Bitte prüfen Sie die Bewerbung in Ihrem Dashboard und nehmen Sie Kontakt mit dem/der Bewerber/in auf.</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Bewerbung im Dashboard ansehen
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{dashboard_url}" style="color: #17a2b8; word-break: break-all;">{dashboard_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Neue Bewerbung eingegangen - {job_titel}

Für Ihre Praxis {praxis_name} ist eine neue Bewerbung eingegangen:

Bewerber/in: {bewerber_vorname} {bewerber_nachname}
Stelle: {job_titel}

Bitte prüfen Sie die Bewerbung in Ihrem Dashboard:
{dashboard_url}

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_job_alert_bestaetigung(to_email, position, ort, confirm_url):
    position_display = position.upper() if position else 'Alle Positionen'
    subject = f"Job-Alert bestätigen - {position_display} in {ort}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Job-Alert bestätigen</h2>

    <p>Sie möchten einen Job-Alert für folgende Kriterien einrichten:</p>

    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>Position:</strong> {position_display}</p>
        <p style="margin: 5px 0;"><strong>Ort:</strong> {ort}</p>
    </div>

    <p>Bitte klicken Sie auf den folgenden Button, um Ihren Job-Alert zu aktivieren:</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{confirm_url}"
           style="background-color: #17a2b8; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
            Job-Alert aktivieren
        </a>
    </div>

    <p style="font-size: 13px; color: #666;">
        Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
        <a href="{confirm_url}" style="color: #17a2b8; word-break: break-all;">{confirm_url}</a>
    </p>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <div style="font-size: 12px; color: #999; padding: 15px; background-color: #f8f9fa; border-radius: 6px;">
        <p style="margin: 0 0 8px 0;"><strong>Hinweis zum Datenschutz:</strong></p>
        <p style="margin: 0;">Diese E-Mail wurde im Rahmen der Einrichtung eines Job-Alerts auf Dentalax versendet. Ihre E-Mail-Adresse wird ausschließlich für den Versand passender Stellenangebote verwendet. Sie können den Job-Alert jederzeit abbestellen. Falls Sie diesen Job-Alert nicht angefordert haben, können Sie diese E-Mail ignorieren.</p>
    </div>

    <p style="font-size: 12px; color: #999; text-align: center; margin-top: 15px;">
        &copy; Dentalax - Ihr Zahnarzt-Portal
    </p>
</body>
</html>"""

    text_body = f"""Job-Alert bestätigen - Dentalax

Sie möchten einen Job-Alert für folgende Kriterien einrichten:

Position: {position_display}
Ort: {ort}

Bitte klicken Sie auf den folgenden Link, um Ihren Job-Alert zu aktivieren:
{confirm_url}

Hinweis zum Datenschutz:
Diese E-Mail wurde im Rahmen der Einrichtung eines Job-Alerts auf Dentalax versendet. Ihre E-Mail-Adresse wird ausschließlich für den Versand passender Stellenangebote verwendet. Sie können den Job-Alert jederzeit abbestellen. Falls Sie diesen Job-Alert nicht angefordert haben, können Sie diese E-Mail ignorieren.

Dentalax - Ihr Zahnarzt-Portal"""

    return send_email(to_email, subject, html_body, text_body)


def send_job_alert_benachrichtigung(to_email, job_titel, position_display, praxis_name, standort, job_url, abmelde_url):
    subject = f"Neues Stellenangebot: {position_display} in {standort} | Dentalax"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #17a2b8; margin: 0;">Dentalax</h1>
        <p style="color: #666; margin-top: 5px;">Ihr Zahnarzt-Portal</p>
    </div>

    <h2 style="color: #333;">Neues Stellenangebot passend zu Ihrem Job-Alert</h2>

    <div style="background-color: #f8f9fa; border-left: 4px solid #17a2b8; padding: 20px; margin: 20px 0; border-radius: 4px;">
        <h3 style="color: #17a2b8; margin-top: 0;">{job_titel}</h3>
        <p style="margin: 5px 0;"><strong>Praxis:</strong> {praxis_name}</p>
        <p style="margin: 5px 0;"><strong>Standort:</strong> {standort}</p>
        <p style="margin: 5px 0;"><strong>Position:</strong> {position_display}</p>
    </div>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{job_url}" style="display: inline-block; padding: 14px 30px; background-color: #17a2b8; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: bold;">Stellenangebot ansehen</a>
    </div>

    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

    <p style="font-size: 12px; color: #999; text-align: center;">
        Sie erhalten diese E-Mail, weil Sie einen Job-Alert auf Dentalax eingerichtet haben.<br>
        <a href="{abmelde_url}" style="color: #17a2b8;">Job-Alert abbestellen</a>
    </p>
</body>
</html>"""

    text_body = f"""Neues Stellenangebot passend zu Ihrem Job-Alert

{job_titel}
Praxis: {praxis_name}
Standort: {standort}
Position: {position_display}

Stellenangebot ansehen: {job_url}

---
Job-Alert abbestellen: {abmelde_url}"""

    return send_email(to_email, subject, html_body, text_body)
