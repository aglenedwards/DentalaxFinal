import os
import logging
from openai import AzureOpenAI

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

client = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "https://dentalax.openai.azure.com/"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
)

def get_dental_match_response(user_message: str, praxen_data: list, conversation_history: list = None) -> str:
    """
    Generiert eine KI-Antwort für den Dental Match Chatbot.
    
    Args:
        user_message: Die Nachricht des Nutzers
        praxen_data: Liste von Praxis-Dictionaries mit relevanten Informationen
        conversation_history: Bisherige Konversation als Liste von {"role": "user/assistant", "content": "..."}
    
    Returns:
        Die Antwort des Chatbots als String
    """
    
    system_prompt = """Du bist der Dentalberater von Dentalax, ein freundlicher und kompetenter KI-Zahnarztberater.
Deine Aufgabe ist es, Patienten bei zahnmedizinischen Fragen zu helfen und sie mit passenden Zahnarztpraxen zu verbinden.

DEINE FÄHIGKEITEN:
1. Symptom-Einschätzung: Wenn ein Patient Symptome beschreibt (z.B. Zahnfleischbluten, Zahnschmerzen), 
   erkläre mögliche Ursachen in einfacher Sprache und empfehle den passenden Spezialisten.
2. Behandlungsberatung: Erkläre Behandlungen wie Implantate, Zahnreinigung, Wurzelbehandlung etc. 
   verständlich mit ungefähren Kostenrahmen.
3. Praxisempfehlung: Verbinde Patienten mit passenden Zahnarztpraxen basierend auf ihren Bedürfnissen.

WICHTIGE REGELN:
1. Antworte immer auf Deutsch, freundlich und in einfacher Sprache (duzen)
2. Stelle KEINE Diagnosen - sage statt "Sie haben Parodontitis" lieber "Das klingt so, als könnte ein Zahnarzt mit Schwerpunkt Parodontologie dir weiterhelfen"
3. Frage nach dem Standort, wenn der Patient noch keinen genannt hat und du Praxen empfehlen möchtest
4. Frage bei Symptomen gezielt nach: Seit wann? Wo genau? Wie stark?
5. Empfehle den passenden Leistungsschwerpunkt basierend auf dem Anliegen
6. Bei Kostenfragen: Gib nur allgemeine Richtwerte an und weise darauf hin, dass die genauen Kosten von der Praxis abhängen
7. Priorisiere Premium-Praxen (PraxisPlus und PraxisPro) - diese werden dir zuerst übergeben
8. Wenn Google-Bewertungen vorhanden sind, erwähne diese bei der Praxisempfehlung

SYMPTOM-MATCHING:
- Zahnfleischbluten/Zahnfleischentzündung → Parodontologie
- Zahnschmerzen/Karies → Allgemeine Zahnheilkunde
- Schiefe Zähne/Fehlstellung → Kieferorthopädie
- Zahnlücke/fehlender Zahn → Implantologie
- Zahnaufhellung/Schönheit → Ästhetische Zahnheilkunde
- Angst vor dem Zahnarzt → Angstpatienten-freundliche Praxen
- Kinder-Behandlung → Kinderzahnheilkunde
- Weisheitszahn-Probleme → Oralchirurgie
- Zahnreinigung/Vorsorge → Prophylaxe

KRITISCH - ERFINDE NIEMALS PRAXEN:
- Du darfst NUR Praxen nennen, die dir explizit in der aktuellen Nachricht als "Verfügbare Praxen in der Nähe:" übergeben wurden
- Nenne NIEMALS Adressen, Telefonnummern, Webseiten oder Bewertungen aus deinem eigenen Wissen oder aus früheren Nachrichten im Gespräch
- Wenn in der aktuellen Nachricht KEINE Praxen-Daten enthalten sind, sage dem Patienten: "Leider konnte ich gerade keine passenden Praxen für dich finden. Nenne mir bitte deinen Standort, damit ich erneut suchen kann."
- Erfundene oder aus dem Gedächtnis rekonstruierte Praxis-Informationen (Adressen, Telefonnummern, Webseiten) sind ABSOLUT VERBOTEN - auch wenn du glaubst, sie aus einer früheren Nachricht zu kennen
- Im Zweifel: Lieber KEINE Praxis nennen als eine mit möglicherweise falschen Details

PRAXIS-INFORMATIONEN:
Die dir übergebenen Praxen sind bereits nach Relevanz und Premium-Status sortiert.
Bei Praxen mit paket="premiumplus" oder paket="praxispro" handelt es sich um Premium-Partner.
Hebe diese besonders hervor. Wenn Google-Bewertungen (google_rating, google_review_count) vorhanden sind, erwähne diese.
Wenn interne Bewertungsdaten vorhanden sind (bewertung_avg, bewertung_anzahl), erwähne auch diese.
Verwende NUR die Daten, die dir in der aktuellen Nachricht übergeben werden - niemals eigene Informationen ergänzen."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if conversation_history:
        messages.extend(conversation_history)
    
    praxen_info = ""
    if praxen_data:
        praxen_info = "\n\nVerfügbare Praxen in der Nähe:\n"
        for i, p in enumerate(praxen_data[:5], 1):
            praxen_info += f"\n{i}. {p.get('name', 'Unbekannt')}"
            praxen_info += f"\n   Adresse: {p.get('strasse', '')}, {p.get('plz', '')} {p.get('stadt', '')}"
            praxen_info += f"\n   Paket: {p.get('paket', 'basic')}"
            if p.get('telefon'):
                praxen_info += f"\n   Telefon: {p.get('telefon')}"
            if p.get('leistungsschwerpunkte'):
                praxen_info += f"\n   Schwerpunkte: {p.get('leistungsschwerpunkte')}"
            if p.get('angstpatientenfreundlich'):
                praxen_info += "\n   ✓ Spezialisiert auf Angstpatienten"
            if p.get('kinderfreundlich'):
                praxen_info += "\n   ✓ Kinderfreundlich"
            if p.get('barrierefrei'):
                praxen_info += "\n   ✓ Barrierefrei"
            if p.get('sprachen'):
                praxen_info += f"\n   Sprachen: {p.get('sprachen')}"
            if p.get('bewertung_anzahl') and p.get('bewertung_anzahl') > 0:
                praxen_info += f"\n   ⭐ Bewertung: {p.get('bewertung_avg')}/5 ({p.get('bewertung_anzahl')} Bewertungen)"
            if p.get('google_rating') and p.get('google_rating') > 0:
                praxen_info += f"\n   ⭐ Google Bewertung: {p.get('google_rating')}/5 ({p.get('google_review_count', 0)} Google-Bewertungen)"
            praxen_info += "\n"
    
    user_content = user_message
    if praxen_info:
        user_content += praxen_info
    else:
        user_content += "\n\n[SYSTEM-HINWEIS: Es wurden KEINE Praxen für diese Anfrage gefunden. Nenne dem Patienten KEINE Praxis-Details. Erfinde KEINE Adressen, Telefonnummern oder Webseiten.]"
    
    messages.append({"role": "user", "content": user_content})
    
    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=messages,
            max_tokens=800,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Azure OpenAI API Fehler: {e}")
        return "Entschuldigung, ich habe gerade technische Schwierigkeiten. Bitte versuchen Sie es in einem Moment erneut oder nutzen Sie unsere Suchfunktion auf der Startseite."


def generate_praxis_text(text_type: str, praxis_data: dict, additional_info: str = "") -> str:
    """
    Generiert Texte für die Praxis-Landingpage (Über uns, Team-Beschreibungen, etc.)
    
    Args:
        text_type: Art des Textes - "ueber_uns", "team_mitglied", "bewertung_antwort", "hero"
        praxis_data: Dictionary mit Praxis-Informationen
        additional_info: Zusätzliche Informationen (z.B. Mitarbeitername, Bewertungstext)
    
    Returns:
        Der generierte Text
    """
    
    prompts = {
        "ueber_uns": f"""Schreibe einen professionellen, einladenden Willkommenstext für eine Zahnarztpraxis.

Praxis-Informationen:
- Name: {praxis_data.get('name', 'Zahnarztpraxis')}
- Stadt: {praxis_data.get('stadt', '')}
- Leistungen: {praxis_data.get('leistungsschwerpunkte', 'Allgemeine Zahnheilkunde')}

Zusätzliche Infos vom Zahnarzt: {additional_info if additional_info else 'Keine weiteren Angaben'}

WICHTIG - Der Text soll:
- KEINE Überschrift enthalten (kein "Über uns", kein "Willkommen", keine Markdown-Formatierung wie ** oder ##)
- Direkt mit dem Fließtext beginnen
- Maximal 80-100 Wörter lang sein (STRIKT einhalten!)
- 1-2 kurze Absätze
- Vertrauen aufbauen und einladend wirken
- Die Philosophie einer modernen, patientenorientierten Praxis vermitteln
- Keine falschen Behauptungen über Auszeichnungen oder spezifische Erfahrungsjahre machen
- Professionell aber warmherzig formuliert sein
- Nur reinen Fließtext liefern, ohne jegliche Formatierung""",

        "team_mitglied": f"""Schreibe eine kurze, sympathische Beschreibung für ein Teammitglied einer Zahnarztpraxis.

Name: {additional_info if additional_info else 'Teammitglied'}
Praxis: {praxis_data.get('name', 'Zahnarztpraxis')}

Die Beschreibung soll:
- 2-3 Sätze lang sein (ca. 40-60 Wörter)
- Freundlich und professionell sein
- Allgemein gehalten sein (keine erfundenen Qualifikationen)
- Das Engagement für Patienten betonen""",

        "bewertung_antwort": f"""Schreibe eine professionelle Antwort auf eine Patientenbewertung.

Praxis: {praxis_data.get('name', 'Zahnarztpraxis')}
Bewertungstext: {additional_info}

Die Antwort soll:
- Höflich und dankbar sein
- 2-3 Sätze lang sein
- Bei positiver Bewertung: Danken und Freude ausdrücken
- Bei kritischer Bewertung: Verständnis zeigen, sich entschuldigen und Besserung versprechen
- Mit "Ihr Praxisteam" enden""",

        "hero": f"""Schreibe einen kurzen, einprägsamen Untertitel für die Startseite einer Zahnarztpraxis.

Praxis: {praxis_data.get('name', 'Zahnarztpraxis')}
Stadt: {praxis_data.get('stadt', '')}

Der Text soll:
- Maximal 15 Wörter
- Einladend und vertrauensbildend sein
- Die Patientenorientierung betonen"""
    }
    
    prompt = prompts.get(text_type)
    if not prompt:
        return "Unbekannter Texttyp"
    
    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "Du bist ein professioneller Texter für Zahnarztpraxen in Deutschland. Schreibe authentische, einladende Texte ohne Übertreibungen."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Azure OpenAI API Fehler bei Textgenerierung: {e}")
        return "Textgenerierung fehlgeschlagen. Bitte versuchen Sie es erneut."


def generate_stellenangebot_text(field_type: str, position: str, anstellungsart: str, praxis_data: dict, existing_fields: dict = None) -> str:
    """
    Generiert Texte für Stellenangebote basierend auf Position und Praxisdaten.
    
    Args:
        field_type: "ueber_uns", "aufgaben", "anforderungen", "wir_bieten", "tags"
        position: Position (z.B. "zfa", "zahnarzt", "zmp")
        anstellungsart: Anstellungsart (z.B. "vollzeit", "teilzeit")
        praxis_data: Dictionary mit Praxis-Informationen (name, stadt, beschreibung, leistungsschwerpunkte)
        existing_fields: Bereits ausgefüllte Felder als Dictionary
    
    Returns:
        Der generierte Text
    """
    if existing_fields is None:
        existing_fields = {}
    
    position_namen = {
        'zfa': 'Zahnmedizinische/r Fachangestellte/r (ZFA)',
        'zmf': 'Zahnmedizinische Fachassistentin (ZMF)',
        'zmv': 'Zahnmedizinische Verwaltungsassistentin (ZMV)',
        'zmp': 'Zahnmedizinische Prophylaxeassistentin (ZMP)',
        'dh': 'Dentalhygieniker/in (DH)',
        'prophylaxe': 'Prophylaxe-Assistent/in',
        'zahnarzt': 'Zahnarzt/Zahnärztin',
        'kfo': 'Kieferorthopäde/in',
        'oralchirurg': 'Oralchirurg/in / MKG-Chirurg/in',
        'implantologe': 'Implantologe/in',
        'endodontologe': 'Endodontologe/in',
        'parodontologe': 'Parodontologe/in',
        'zahntechniker': 'Zahntechniker/in',
        'praxismanager': 'Praxismanager/in',
        'rezeption': 'Rezeption / Empfang',
        'abrechnung': 'Abrechnungskraft',
        'verwaltung': 'Verwaltungskraft',
        'azubi': 'Auszubildende/r zur ZFA',
        'sonstige': 'Mitarbeiter/in'
    }
    
    position_display = position_namen.get(position, position)
    
    praxis_name = praxis_data.get('name', 'Zahnarztpraxis')
    praxis_stadt = praxis_data.get('stadt', '')
    praxis_beschreibung = praxis_data.get('beschreibung', '')
    praxis_leistungen = praxis_data.get('leistungsschwerpunkte', '')
    
    context = f"""Position: {position_display}
Anstellungsart: {anstellungsart}
Praxis: {praxis_name}
Stadt: {praxis_stadt}
Leistungsschwerpunkte: {praxis_leistungen}"""
    
    if praxis_beschreibung:
        context += f"\nPraxisbeschreibung (von der Landingpage): {praxis_beschreibung}"
    
    already_filled = ""
    for key, val in existing_fields.items():
        if val and val.strip():
            already_filled += f"\n{key}: {val}"
    if already_filled:
        context += f"\n\nBereits ausgefüllte Felder:{already_filled}"
    
    prompts = {
        "ueber_uns": f"""{context}

Schreibe einen kurzen, attraktiven "Über uns"-Text für dieses Stellenangebot.
Basiere dich auf der Praxisbeschreibung von der Landingpage (falls vorhanden) und optimiere den Text für den Jobmarkt.

Der Text soll:
- 3-5 Sätze lang sein (ca. 80-120 Wörter)
- Die Praxis als attraktiven Arbeitgeber darstellen
- Teamgeist, moderne Ausstattung und Arbeitsatmosphäre betonen
- Authentisch und einladend klingen, nicht übertrieben
- Wenn Praxisbeschreibung vorhanden: diese als Grundlage nehmen und für Bewerber optimieren
- NUR den Text ausgeben, keine Überschriften oder Labels""",

        "aufgaben": f"""{context}

Erstelle eine Bulletpoint-Liste typischer Aufgaben für die Position {position_display}.

Die Liste soll:
- 5-8 konkrete Aufgabenpunkte enthalten
- Jeder Punkt MUSS mit einem "• " (Bullet-Zeichen + Leerzeichen) beginnen
- Jeder Punkt in einer neuen Zeile
- Spezifisch für die Position sein, nicht generisch
- Realistische, tägliche Aufgaben widerspiegeln
- Falls Leistungsschwerpunkte der Praxis bekannt sind, diese einbeziehen
- NUR die Bulletpoint-Liste ausgeben, keine Überschriften

Beispielformat:
• Professionelle Zahnreinigung durchführen
• Patienten über Mundhygiene beraten""",

        "anforderungen": f"""{context}

Erstelle eine Bulletpoint-Liste von Anforderungen/Qualifikationen für die Position {position_display}.

Die Liste soll:
- 5-7 Anforderungspunkte enthalten
- Jeder Punkt MUSS mit einem "• " (Bullet-Zeichen + Leerzeichen) beginnen
- Jeder Punkt in einer neuen Zeile
- Pflichtanforderungen und Wünsche mischen (z.B. "• Abgeschlossene Ausbildung als..." vs "• Idealerweise Erfahrung in...")
- Soft Skills einbeziehen (Teamfähigkeit, Patientenorientierung etc.)
- Realistisch sein, nicht zu viele Anforderungen
- NUR die Bulletpoint-Liste ausgeben, keine Überschriften

Beispielformat:
• Abgeschlossene Ausbildung als ZFA
• Freundliches und einfühlsames Auftreten""",

        "wir_bieten": f"""{context}

Erstelle eine Bulletpoint-Liste von Benefits/Vorteilen, die die Praxis Bewerbern bietet.

Die Liste soll:
- 5-8 attraktive Benefits enthalten
- Jeder Punkt MUSS mit einem "• " (Bullet-Zeichen + Leerzeichen) beginnen
- Jeder Punkt in einer neuen Zeile
- Typische Benefits für Zahnarztpraxen einbeziehen (Fortbildungen, modernes Equipment, Team-Events etc.)
- Sich vom Standard abheben und attraktiv klingen
- Falls Praxisinfos bekannt, diese einbeziehen (z.B. Schwerpunkte = Fortbildungsmöglichkeiten in dem Bereich)
- NUR die Bulletpoint-Liste ausgeben, keine Überschriften

Beispielformat:
• Überdurchschnittliche Vergütung
• Regelmäßige Fort- und Weiterbildungen""",

        "tags": f"""{context}

Erstelle 5-8 relevante Tags/Schlagwörter für dieses Stellenangebot, kommasepariert.

Die Tags sollen:
- Relevant für die Position und Praxis sein
- Suchbegriffe abdecken, die Bewerber nutzen würden
- Leistungsschwerpunkte der Praxis einbeziehen
- Mix aus Position, Fachgebiet, Benefits und Arbeitsmodell
- Kommasepariert in einer Zeile, OHNE # oder sonstige Zeichen
- Beispiel: Prophylaxe, Moderne Praxis, Fortbildung, Teamarbeit, Work-Life-Balance"""
    }
    
    prompt = prompts.get(field_type)
    if not prompt:
        return "Unbekannter Feldtyp"
    
    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "Du bist ein erfahrener HR-Texter für Zahnarztpraxen in Deutschland. Schreibe professionelle, attraktive Stellenangebote, die qualifizierte Bewerber ansprechen. Formuliere jeden Text individuell und einzigartig - nicht generisch. Antworte NUR mit dem angefragten Text, ohne Überschriften, Labels oder Erklärungen."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.8
        )
        result = response.choices[0].message.content.strip()
        lines = result.split('\n')
        cleaned_lines = []
        
        bullet_fields = ('aufgaben', 'anforderungen', 'wir_bieten')
        
        for line in lines:
            line = line.strip()
            if line:
                if field_type in bullet_fields:
                    line = line.lstrip('-–—*►▸▹✓✔☑ ')
                    if line and not line.startswith('•'):
                        line = '• ' + line
                    cleaned_lines.append(line)
                else:
                    while line and line[0] in '-•·–—*►▸▹✓✔☑':
                        line = line[1:].strip()
                    if line:
                        cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    except Exception as e:
        logger.error(f"Azure OpenAI API Fehler bei Stellenangebot-Generierung ({field_type}): {e}")
        return "Textgenerierung fehlgeschlagen. Bitte versuchen Sie es erneut."


def generate_city_seo_texts(stadt_name: str) -> dict:
    """
    Generiert SEO-Texte für eine Stadtseite.
    
    Args:
        stadt_name: Name der Stadt (z.B. "München")
    
    Returns:
        Dictionary mit allen SEO-Feldern inkl. FAQ und Meta-Tags
    """
    
    system_prompt = """Du bist ein SEO-Experte für Zahnarzt-Verzeichnisse in Deutschland.
Deine Aufgabe ist es, einzigartige, informative SEO-Texte für Stadtseiten zu erstellen.

WICHTIGE REGELN:
1. Schreibe auf Deutsch in professionellem, aber zugänglichem Stil
2. Die H1 muss mit "Zahnarzt [Stadt]:" beginnen (KEIN "in" nach Zahnarzt!) - z.B. "Zahnarzt Berlin: ..."
3. Der Teaser sollte kurz sein (1-2 Sätze, maximal 40 Wörter)
4. Jeder SEO-Text (seo_text_1, seo_text_2) sollte 150-200 Wörter haben - ausführlich und informativ!
5. Die Texte müssen einzigartig sein und dürfen nicht generisch klingen
6. Baue lokale Bezüge zur Stadt ein wenn möglich (Stadtteile, Besonderheiten, regionale Aspekte)
7. Vermeide übertriebene Werbesprache
8. Fokussiere auf Nutzen für Patienten
9. Meta-Title: max 60 Zeichen, Meta-Description: 150-160 Zeichen
10. FAQ: 4 relevante Fragen mit hilfreichen Antworten (je 2-3 Sätze)

Du antwortest NUR im folgenden JSON-Format, ohne Markdown-Formatierung:
{
  "meta_title": "Zahnarzt [Stadt] | Top Zahnärzte finden - Dentalax",
  "meta_description": "Finden Sie Ihren Zahnarzt in [Stadt]. Vergleichen Sie Bewertungen...",
  "h1_titel": "Zahnarzt [Stadt]: [einzigartiger Zusatz]",
  "teaser_text": "Kurzer Teaser-Text (1-2 Sätze)...",
  "h2_titel_1": "Überschrift 1 mit Keyword",
  "seo_text_1": "Ausführlicher SEO-Text mit 150-200 Wörtern...",
  "h2_titel_2": "Überschrift 2 mit sekundärem Keyword",
  "seo_text_2": "Ausführlicher SEO-Text mit 150-200 Wörtern...",
  "faq": [
    {"frage": "Wie finde ich einen guten Zahnarzt in [Stadt]?", "antwort": "Antwort..."},
    {"frage": "Was kostet eine Zahnreinigung in [Stadt]?", "antwort": "Antwort..."},
    {"frage": "Welche Zahnärzte in [Stadt] behandeln Angstpatienten?", "antwort": "Antwort..."},
    {"frage": "Gibt es Notdienst-Zahnärzte in [Stadt]?", "antwort": "Antwort..."}
  ]
}"""

    user_prompt = f"""Erstelle SEO-Texte für die Stadtseite "Zahnarzt {stadt_name}".

Die Seite zeigt Zahnärzte in {stadt_name} und Umgebung.

Erstelle:
1. Meta-Title (max 60 Zeichen) und Meta-Description (150-160 Zeichen)
2. Eine einzigartige H1 im Format "Zahnarzt {stadt_name}: [kreativer Zusatz]" (OHNE "in")
3. Einen kurzen Teaser-Text (1-2 Sätze, max 40 Wörter)
4. H2 + ausführlicher Text (150-200 Wörter) über die Zahnarztsuche in {stadt_name}
5. H2 + ausführlicher Text (150-200 Wörter) mit Tipps zur Wahl einer Zahnarztpraxis
6. FAQ mit 4 relevanten Fragen und hilfreichen Antworten

Antworte NUR mit dem JSON-Objekt, ohne Markdown-Backticks."""

    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
            temperature=0.8
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Azure OpenAI API Fehler bei SEO-Generierung für {stadt_name}: {e}")
        return {
            "meta_title": f"Zahnarzt {stadt_name} | Top Zahnärzte finden - Dentalax",
            "meta_description": f"Finden Sie Ihren Zahnarzt in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und Öffnungszeiten der besten Zahnarztpraxen.",
            "h1_titel": f"Zahnarzt {stadt_name}: Finden Sie Ihre ideale Praxis",
            "teaser_text": f"Entdecken Sie qualifizierte Zahnärzte in {stadt_name} und Umgebung. Vergleichen Sie Praxen und vereinbaren Sie Ihren Termin.",
            "h2_titel_1": f"Zahnärzte {stadt_name} – Ihre Praxis in der Nähe",
            "seo_text_1": f"Finden Sie qualifizierte Zahnärzte in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und Öffnungszeiten, um die passende Zahnarztpraxis für Ihre Bedürfnisse zu finden. Unser Verzeichnis bietet Ihnen einen umfassenden Überblick über alle Zahnarztpraxen in {stadt_name} und der näheren Umgebung. Ob Sie eine Routineuntersuchung, professionelle Zahnreinigung oder spezielle Behandlungen wie Implantologie oder Kieferorthopädie benötigen – hier finden Sie den passenden Spezialisten. Nutzen Sie die Filterfunktionen, um nach Leistungsschwerpunkten, Öffnungszeiten oder besonderen Angeboten wie Behandlung von Angstpatienten zu suchen.",
            "h2_titel_2": f"Zahnarztpraxis {stadt_name} – Worauf Sie achten sollten",
            "seo_text_2": f"Bei der Wahl Ihrer Zahnarztpraxis in {stadt_name} sollten Sie auf verschiedene Faktoren achten. Die Erreichbarkeit spielt eine wichtige Rolle – liegt die Praxis günstig zu Ihrem Wohnort oder Arbeitsplatz? Prüfen Sie auch die angebotenen Leistungen und ob die Praxis auf Ihre speziellen Bedürfnisse eingehen kann. Patientenbewertungen geben wertvolle Einblicke in die Behandlungsqualität und das Praxisklima. Achten Sie zudem auf die technische Ausstattung und ob moderne Behandlungsmethoden angeboten werden. Ein persönliches Erstgespräch hilft Ihnen, einen Eindruck vom Behandlungsstil zu bekommen.",
            "faq": [
                {"frage": f"Wie finde ich einen guten Zahnarzt in {stadt_name}?", "antwort": f"Nutzen Sie unsere Suchfunktion und filtern Sie nach Ihren Bedürfnissen. Achten Sie auf Bewertungen anderer Patienten und prüfen Sie, ob die Praxis Ihre gewünschten Leistungen anbietet."},
                {"frage": f"Was kostet eine Zahnreinigung in {stadt_name}?", "antwort": "Die Kosten für eine professionelle Zahnreinigung liegen meist zwischen 80 und 150 Euro. Der genaue Preis hängt vom Aufwand und der Praxis ab."},
                {"frage": f"Welche Zahnärzte in {stadt_name} behandeln Angstpatienten?", "antwort": "Viele Praxen bieten spezielle Behandlungen für Angstpatienten an. Nutzen Sie unseren Filter, um Praxen mit diesem Schwerpunkt zu finden."},
                {"frage": f"Gibt es Notdienst-Zahnärzte in {stadt_name}?", "antwort": f"Ja, in {stadt_name} gibt es einen zahnärztlichen Notdienst. Bei akuten Beschwerden außerhalb der Sprechzeiten können Sie den Notdienst kontaktieren."}
            ]
        }


def generate_leistung_stadt_seo_texts(leistung_name: str, leistung_slug: str, stadt_name: str) -> dict:
    """
    Generiert SEO-Texte für eine Leistung+Stadt-Kombinationsseite.
    
    Args:
        leistung_name: Name der Leistung (z.B. "Implantologie")
        leistung_slug: Slug der Leistung (z.B. "implantologie")
        stadt_name: Name der Stadt (z.B. "München")
    
    Returns:
        Dictionary mit allen SEO-Feldern inkl. FAQ und Meta-Tags
    """
    
    leistung_beschreibungen = {
        'implantologie': 'Zahnimplantate und Implantologie-Behandlungen',
        'kieferorthopaedie': 'Kieferorthopädie, Zahnspangen und Aligner',
        'prophylaxe': 'Professionelle Zahnreinigung und Prophylaxe',
        'parodontologie': 'Parodontologie und Zahnfleischbehandlungen',
        'wurzelbehandlung': 'Wurzelbehandlung und Endodontie',
        'zahnersatz': 'Zahnersatz, Kronen, Brücken und Prothesen',
        'aesthetik': 'Ästhetische Zahnheilkunde, Bleaching und Veneers',
        'kinderzahnheilkunde': 'Kinderzahnheilkunde und Behandlung für Kinder',
        'oralchirurgie': 'Oralchirurgie und zahnchirurgische Eingriffe',
        'angstpatienten': 'Zahnbehandlung für Angstpatienten'
    }
    
    leistung_details = leistung_beschreibungen.get(leistung_slug, leistung_name)
    
    import random
    h1_patterns = [
        f'{leistung_name} {{Stadt}}: [kreativer Zusatz, z.B. "Kompetente Spezialisten für Ihre Behandlung"]',
        f'{leistung_name} {{Stadt}} – [kreativer Zusatz mit Bindestrich, z.B. "Erfahrene Praxen im Überblick"]',
        f'{leistung_name}-Spezialisten {{Stadt}}: [Zusatz, z.B. "Qualifizierte Zahnärzte finden"]',
        f'{leistung_name} {{Stadt}} | [kreativer Zusatz, z.B. "Top-Praxen auf einen Blick"]',
    ]
    chosen_pattern = random.choice(h1_patterns)

    system_prompt = f"""Du bist ein SEO-Experte für Zahnarzt-Verzeichnisse in Deutschland.
Deine Aufgabe ist es, einzigartige, informative SEO-Texte für Leistungs-Stadtseiten zu erstellen.

WICHTIGE REGELN:
1. Schreibe auf Deutsch in professionellem, aber zugänglichem Stil
2. SEHR WICHTIG - H1-Überschrift: Das primäre Keyword "{leistung_name}" MUSS am Anfang der H1 stehen. Nutze folgendes Format als Inspiration (aber variiere kreativ!): {chosen_pattern}
   Wechsle zwischen Trennzeichen (Doppelpunkt, Bindestrich, Pipe) und formuliere den Zusatz jedes Mal komplett anders. Vermeide generische Phrasen wie "Finden Sie Ihren Spezialisten" - stattdessen konkrete, einzigartige Aussagen.
3. Der Teaser sollte kurz sein (1-2 Sätze, maximal 40 Wörter)
4. Jeder SEO-Text (seo_text_1, seo_text_2) sollte 150-200 Wörter haben - ausführlich und informativ!
5. Die Texte müssen einzigartig sein und dürfen nicht generisch klingen
6. Baue spezifische Informationen zur Leistung "{leistung_name}" ein
7. Vermeide übertriebene Werbesprache
8. Fokussiere auf Nutzen für Patienten
9. Meta-Title: max 60 Zeichen, Meta-Description: 150-160 Zeichen
10. FAQ: 4 relevante Fragen zur Leistung in der Stadt mit hilfreichen Antworten
11. H2-Überschriften: Verwende abwechslungsreiche Formulierungen. Nutze Synonyme und verschiedene Satzstrukturen. Vermeide es, immer dasselbe Muster zu verwenden.

Du antwortest NUR im folgenden JSON-Format, ohne Markdown-Formatierung:
{{
  "meta_title": "{leistung_name} {{Stadt}} | [variierender Zusatz] - Dentalax",
  "meta_description": "[Einzigartige Beschreibung, 150-160 Zeichen]",
  "h1_titel": "[Siehe H1-Regel oben - kreativ und einzigartig!]",
  "teaser_text": "Kurzer Teaser-Text (1-2 Sätze)...",
  "h2_titel_1": "[Kreative Überschrift mit Keyword zur Leistung]",
  "seo_text_1": "Ausführlicher SEO-Text mit 150-200 Wörtern...",
  "h2_titel_2": "[Kreative Überschrift mit sekundärem Keyword]",
  "seo_text_2": "Ausführlicher SEO-Text mit 150-200 Wörtern...",
  "faq": [
    {{"frage": "Frage zu {leistung_name} in {{Stadt}}?", "antwort": "Antwort..."}},
    {{"frage": "Was kostet {leistung_name} in {{Stadt}}?", "antwort": "Antwort..."}},
    {{"frage": "Frage 3", "antwort": "Antwort..."}},
    {{"frage": "Frage 4", "antwort": "Antwort..."}}
  ]
}}"""

    user_prompt = f"""Erstelle SEO-Texte für die Seite "{leistung_name} {stadt_name}".

Die Seite zeigt Zahnarztpraxen in {stadt_name}, die sich auf {leistung_details} spezialisieren.

Erstelle:
1. Meta-Title (max 60 Zeichen) und Meta-Description (150-160 Zeichen) - BEIDE einzigartig formuliert
2. Eine einzigartige H1 mit dem Keyword "{leistung_name}" am Anfang. Nutze dieses Muster als Inspiration: {chosen_pattern} - aber formuliere den Zusatz komplett einzigartig für {stadt_name}. KEIN "in" vor dem Stadtnamen.
3. Einen kurzen Teaser-Text (1-2 Sätze, max 40 Wörter) - einzigartig, nicht generisch
4. H2 + ausführlicher Text (150-200 Wörter) über {leistung_name} in {stadt_name} - kreative H2-Überschrift
5. H2 + ausführlicher Text (150-200 Wörter) mit Tipps zur Wahl eines {leistung_name}-Spezialisten - andere H2-Struktur als H2_1
6. FAQ mit 4 relevanten Fragen zu {leistung_name} in {stadt_name}

Antworte NUR mit dem JSON-Objekt, ohne Markdown-Backticks."""

    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
            temperature=0.8
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Azure OpenAI API Fehler bei Leistung-SEO-Generierung für {leistung_name} {stadt_name}: {e}")
        return {
            "meta_title": f"{leistung_name} {stadt_name} | Spezialisten finden - Dentalax",
            "meta_description": f"Finden Sie Spezialisten für {leistung_name} in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und Öffnungszeiten.",
            "h1_titel": f"{leistung_name} {stadt_name}: Finden Sie Ihren Spezialisten",
            "teaser_text": f"Entdecken Sie qualifizierte {leistung_name}-Spezialisten in {stadt_name}. Vergleichen Sie Praxen und vereinbaren Sie Ihren Termin.",
            "h2_titel_1": f"{leistung_name} in {stadt_name} – Ihre Praxis in der Nähe",
            "seo_text_1": f"Finden Sie qualifizierte Zahnarztpraxen für {leistung_name} in {stadt_name}. Vergleichen Sie Bewertungen, Leistungen und Öffnungszeiten, um die passende Praxis für Ihre Behandlung zu finden. Unser Verzeichnis bietet Ihnen einen umfassenden Überblick über alle Praxen mit Schwerpunkt {leistung_name} in {stadt_name} und der näheren Umgebung. Nutzen Sie die Filterfunktionen, um nach weiteren Leistungsschwerpunkten, Öffnungszeiten oder besonderen Angeboten zu suchen. Die gelisteten Praxen verfügen über Erfahrung und moderne Ausstattung für Ihre Behandlung.",
            "h2_titel_2": f"{leistung_name}-Spezialist {stadt_name} – Worauf Sie achten sollten",
            "seo_text_2": f"Bei der Wahl Ihres {leistung_name}-Spezialisten in {stadt_name} sollten Sie auf verschiedene Faktoren achten. Die Erfahrung und Qualifikation des Zahnarztes spielt eine wichtige Rolle. Prüfen Sie auch, ob die Praxis über moderne Technik und Ausstattung verfügt. Patientenbewertungen geben wertvolle Einblicke in die Behandlungsqualität. Achten Sie zudem auf die Beratungsqualität – ein gutes Erstgespräch ist wichtig für Ihre Entscheidung. Die Erreichbarkeit und Terminverfügbarkeit sind weitere praktische Faktoren bei Ihrer Wahl.",
            "faq": [
                {"frage": f"Was ist {leistung_name}?", "antwort": f"{leistung_name} ist ein spezialisierter Bereich der Zahnmedizin. In {stadt_name} finden Sie qualifizierte Praxen für diese Behandlung."},
                {"frage": f"Was kostet {leistung_name} in {stadt_name}?", "antwort": f"Die Kosten für {leistung_name} variieren je nach Umfang und Praxis. Lassen Sie sich einen individuellen Kostenvoranschlag erstellen."},
                {"frage": f"Wie finde ich einen guten {leistung_name}-Spezialisten in {stadt_name}?", "antwort": f"Nutzen Sie unsere Suchfunktion und achten Sie auf Bewertungen. Praxen mit Schwerpunkt {leistung_name} werden prominent angezeigt."},
                {"frage": f"Übernimmt die Krankenkasse {leistung_name}?", "antwort": f"Die Kostenübernahme hängt von Ihrer Versicherung und der konkreten Behandlung ab. Klären Sie dies vorab mit Ihrer Krankenkasse."}
            ]
        }
