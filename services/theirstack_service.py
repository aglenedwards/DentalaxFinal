import os
import requests
import logging
from datetime import datetime, timedelta
from models import ExternesInserat
from database import db

logger = logging.getLogger(__name__)

THEIRSTACK_API_URL = "https://api.theirstack.com/v1/jobs/search"

DENTAL_KEYWORDS = [
    "Zahnarzt",
    "Zahnärztin",
    "ZFA",
    "Zahnmedizinische Fachangestellte",
    "ZMF",
    "Zahnmedizinische Fachassistentin",
    "ZMV",
    "Zahnmedizinische Verwaltungsassistentin",
    "ZMP",
    "Zahnmedizinische Prophylaxeassistentin",
    "Dentalhygieniker",
    "Dentalhygienikerin",
    "DH Dentalhygiene",
    "Dental",
    "Zahntechniker",
    "Zahntechnikerin",
    "Dentallabor",
    "Kieferorthopäde",
    "Kieferorthopädin",
    "Kieferorthopädie",
    "KFO",
    "Oralchirurg",
    "Oralchirurgie",
    "Mund-Kiefer-Gesichtschirurg",
    "MKG",
    "Implantologe",
    "Implantologie",
    "Endodontie",
    "Endodontologe",
    "Parodontologe",
    "Parodontologie",
    "Praxismanager",
    "Praxismanagerin",
    "Praxisleitung",
    "Prophylaxe",
    "Prophylaxeassistent",
    "Rezeption Zahnarztpraxis",
    "Empfang Zahnarztpraxis",
    "Abrechnungsmanager",
    "Abrechnung Zahnarzt",
    "Dentist",
    "Dental Assistant",
    "Dental Hygienist",
    "Zahnarzthelferin"
]


def kategorisiere_position(job_title):
    """Ordnet Jobtitel einer Kategorie zu"""
    title_lower = job_title.lower() if job_title else ""
    
    if any(x in title_lower for x in ["zahnarzt", "zahnärztin", "dentist", "oralchirurg", "mkg", "implantolog", "endodont", "parodont"]):
        return "zahnarzt"
    elif any(x in title_lower for x in ["kieferorthopäd", "kfo"]):
        return "kfo"
    elif any(x in title_lower for x in ["zfa", "zahnmedizinische fachangestellte", "dental assistant", "zahnarzthelferin"]):
        return "zfa"
    elif any(x in title_lower for x in ["zmf", "fachassistent"]):
        return "zmf"
    elif any(x in title_lower for x in ["zmv", "verwaltungsassistent", "abrechnung", "abrechnungsmanager"]):
        return "zmv"
    elif any(x in title_lower for x in ["zmp", "prophylaxeassistent", "prophylaxe"]):
        return "zmp"
    elif any(x in title_lower for x in ["dentalhygien", "dental hygien", "dh "]):
        return "dh"
    elif any(x in title_lower for x in ["zahntechnik", "dentallabor"]):
        return "zahntechniker"
    elif any(x in title_lower for x in ["praxismanager", "praxisleitung"]):
        return "praxismanager"
    elif any(x in title_lower for x in ["rezeption", "empfang"]):
        return "rezeption"
    elif any(x in title_lower for x in ["auszubilden", "ausbildung", "azubi"]):
        return "azubi"
    else:
        return "dental"


def parse_anstellungsart(job_data):
    """Ermittelt Anstellungsart aus Job-Daten"""
    title = (job_data.get("job_title") or "").lower()
    description = (job_data.get("description") or "").lower()
    
    if "teilzeit" in title or "teilzeit" in description or "part-time" in title:
        return "teilzeit"
    elif "ausbildung" in title or "azubi" in title or "trainee" in title:
        return "ausbildung"
    elif "minijob" in title or "450" in title or "520" in title:
        return "minijob"
    elif "praktik" in title:
        return "praktikum"
    else:
        return "vollzeit"


def extract_stadt_from_location(location):
    """Extrahiert Stadt aus Location-String"""
    if not location:
        return None
    
    parts = [p.strip() for p in location.split(",")]
    for part in parts:
        if part and not any(char.isdigit() for char in part) and "Germany" not in part and "Deutschland" not in part:
            return part
    return parts[0] if parts else None


def fetch_dental_jobs_from_theirstack(limit=25):
    """Ruft Dental-Jobs von TheirStack API ab"""
    api_key = os.environ.get("THEIRSTACK_API_KEY")
    
    if not api_key:
        logger.error("THEIRSTACK_API_KEY nicht konfiguriert")
        return []
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "order_by": [
            {"desc": True, "field": "date_posted"},
            {"desc": True, "field": "discovered_at"}
        ],
        "page": 0,
        "limit": limit,
        "job_title_or": DENTAL_KEYWORDS,
        "job_country_code_or": ["DE"],
        "posted_at_max_age_days": 30
    }
    
    try:
        logger.info(f"Rufe TheirStack API ab mit {limit} Jobs...")
        response = requests.post(
            THEIRSTACK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        jobs = data.get("data", [])
        logger.info(f"TheirStack API: {len(jobs)} Dental-Jobs gefunden")
        return jobs
        
    except requests.exceptions.RequestException as e:
        logger.error(f"TheirStack API Fehler: {e}")
        return []


def cleanup_old_external_jobs(max_age_days=45, synced_ids=None):
    """
    Löscht externe Jobs die älter als max_age_days sind.
    Wenn synced_ids angegeben ist, werden nur Jobs gelöscht die:
    - älter als max_age_days sind UND
    - nicht in der aktuellen Sync-Liste sind
    """
    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    query = ExternesInserat.query.filter(
        ExternesInserat.abgerufen_am < cutoff_date
    )
    
    if synced_ids:
        query = query.filter(~ExternesInserat.external_id.in_(synced_ids))
    
    old_jobs = query.all()
    deleted_count = len(old_jobs)
    
    for job in old_jobs:
        db.session.delete(job)
    
    try:
        db.session.commit()
        if deleted_count > 0:
            logger.info(f"Bereinigung: {deleted_count} alte externe Jobs gelöscht (älter als {max_age_days} Tage)")
        return deleted_count
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fehler bei der Bereinigung: {e}")
        return 0


def sync_external_jobs(limit=25):
    """Synchronisiert externe Jobs in die Datenbank"""
    
    jobs = fetch_dental_jobs_from_theirstack(limit)
    
    # Sammle IDs der aktuell abgerufenen Jobs
    synced_ids = [str(job.get("id")) for job in jobs if job.get("id")]
    
    # Bereinige alte Jobs (älter als 45 Tage und nicht in aktueller Sync-Liste)
    cleanup_old_external_jobs(max_age_days=45, synced_ids=synced_ids)
    
    new_count = 0
    updated_count = 0
    
    for job in jobs:
        external_id = str(job.get("id"))
        
        existing = ExternesInserat.query.filter_by(external_id=external_id).first()
        
        date_posted = None
        if job.get("date_posted"):
            try:
                date_posted = datetime.strptime(job["date_posted"], "%Y-%m-%d")
            except:
                pass
        
        company_name = job.get("company", {}).get("name") if isinstance(job.get("company"), dict) else job.get("company", "Unbekannt")
        
        job_data = {
            "titel": job.get("job_title", "Dental-Position"),
            "unternehmen": company_name,
            "standort": job.get("location", ""),
            "standort_stadt": extract_stadt_from_location(job.get("location")),
            "beschreibung": job.get("description", ""),
            "position_kategorie": kategorisiere_position(job.get("job_title")),
            "anstellungsart": parse_anstellungsart(job),
            "gehalt_min": job.get("min_annual_salary"),
            "gehalt_max": job.get("max_annual_salary"),
            "externe_url": job.get("final_url") or job.get("url", ""),
            "quelle": extract_source_from_url(job.get("url", "")),
            "veroeffentlicht_am": date_posted,
            "abgerufen_am": datetime.utcnow(),
            "ist_aktiv": True
        }
        
        if existing:
            for key, value in job_data.items():
                setattr(existing, key, value)
            updated_count += 1
        else:
            new_job = ExternesInserat(external_id=external_id, **job_data)
            db.session.add(new_job)
            new_count += 1
    
    try:
        db.session.commit()
        logger.info(f"TheirStack Sync: {new_count} neue, {updated_count} aktualisierte Jobs")
        return {"new": new_count, "updated": updated_count}
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fehler beim Speichern: {e}")
        return {"error": str(e)}


def extract_source_from_url(url):
    """Ermittelt die Quelle aus der URL"""
    if not url:
        return "Unbekannt"
    
    url_lower = url.lower()
    if "linkedin" in url_lower:
        return "LinkedIn"
    elif "indeed" in url_lower:
        return "Indeed"
    elif "stepstone" in url_lower:
        return "StepStone"
    elif "glassdoor" in url_lower:
        return "Glassdoor"
    elif "xing" in url_lower:
        return "XING"
    elif "monster" in url_lower:
        return "Monster"
    elif "jobware" in url_lower:
        return "Jobware"
    else:
        return "Jobbörse"


def should_refresh_jobs():
    """Prüft ob Jobs aktualisiert werden sollten (alle 24h)"""
    latest = ExternesInserat.query.order_by(ExternesInserat.abgerufen_am.desc()).first()
    
    if not latest:
        return True
    
    age = datetime.utcnow() - latest.abgerufen_am
    return age > timedelta(hours=24)


def get_external_jobs(stadt=None, position=None, limit=20):
    """Holt externe Jobs aus der Datenbank mit optionalen Filtern"""
    query = ExternesInserat.query.filter_by(ist_aktiv=True)
    
    if stadt:
        query = query.filter(ExternesInserat.standort_stadt.ilike(f"%{stadt}%"))
    
    if position:
        query = query.filter(ExternesInserat.position_kategorie == position)
    
    return query.order_by(ExternesInserat.veroeffentlicht_am.desc()).limit(limit).all()


def get_cities_with_jobs():
    """Gibt Liste aller Städte mit externen Jobs zurück (nur Stadtname, ohne PLZ)"""
    import re
    
    results = db.session.query(
        ExternesInserat.standort_stadt,
        db.func.count(ExternesInserat.id).label('count')
    ).filter(
        ExternesInserat.ist_aktiv == True,
        ExternesInserat.standort_stadt.isnot(None)
    ).group_by(
        ExternesInserat.standort_stadt
    ).order_by(
        db.desc('count')
    ).all()
    
    city_counts = {}
    for city, count in results:
        if city:
            clean_city = re.sub(r'^\d{5}\s*', '', city).strip()
            if clean_city:
                if clean_city in city_counts:
                    city_counts[clean_city] += count
                else:
                    city_counts[clean_city] = count
    
    sorted_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_cities
