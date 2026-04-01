"""
lebenslauf_prompts.py
=====================
Builds job-role-aware master prompts for the Lebenslauf Generator.
Each prompt instructs the AI to extract and restructure CV / ID data
into a fixed JSON schema that mirrors the "Vorlage Lebenslauf" layout.
"""

# ---------------------------------------------------------------------------
# Skill-block definitions per trade
# ---------------------------------------------------------------------------

_SKILL_BLOCKS = {
    "Schweißer": """
Du erhältst einen Lebenslauf (PDF/DOC) und ggf. Ausweis eines Schweißers.

Block „Beruferfahrung“ (wie in der Vorlage, mit Zeitspanne links und Textblock rechts), im Format:
MM.JJJJ -- MM.JJJJ Arbeitgeber / Land – Position – Tätigkeiten
Sortierung: ab dem 19. Lebensjahr des Kandidaten, lückenlos bis heute.
Keine Datums-Lücken: Zwischenräume mit neutralen Einträgen wie „Zeitpuffer/Projektpause“ oder „Weiterbildung“ füllen, aber nicht erfinden, dass der Kandidat woanders angestellt war.
Für jede Position:
Arbeitgeber, Ort/Land
Position (z.B. Schweißer, Schlosser/Schweißer, Schweißerhelfer)
Genaue Tätigkeit in einem Satz: Schweißverfahren (111, 135, 136, 138, 141), Material (Kohlenstoffstahl, Edelstahl), typische Bauteile (Schiff, Brücke, Tank, Kran, Halle, Rohrleitungen, Module) und Blech-/Wandstärkenbereich (z.B. 6–50 mm), angelehnt an Branchenstandard.

Block „Bildungseinrichtung“:
Schul-/Berufsausbildung aus dem CV übernehmen.
Wenn im Lebenslauf die Berufsschule oder schulische Ausbildung fehlt, recherchiere online eine passende Schule in der Nähe des Geburtsortes oder in derselben Region des Kandidaten. Trage eine realistische Ausbildungs- oder Schulstation für den Zeitraum vom 15. bis 18. Lebensjahr ein, bevorzugt mit Bezug zu Metallbearbeitung, Stahlkonstruktionen, Schutzgas- und Elektrodenschweißen, Zeichnungslesen, Montage und Instandhaltung; falls keine solche Schule auffindbar ist, verwende eine allgemeine regionale Schule und formuliere den Eintrag neutral und plausibel.

Block „WEITERBILDUNG“:
Alle Schweißkurse und relevanten Weiterbildungen aus dem CV, z.B.:
Kurse 111, 135, 136, 138, 141 (mit Zeitraum und Art: Grund-/Aufbaukurs).

Block „Sprachkenntnisse“ in Tabellenform wie in der Vorlage:
Jede Sprache mit Niveau (z.B. C2, B1, A2 oder „kommunikativ“) aus dem CV ableiten; wenn nur „communicative“ steht, als B1–B2 interpretieren.

BEWERTUNG DER TECHNISCHEN FÄHIGKEITEN (WICHTIG)
Bei allen Angaben im Abschnitt „Sonstige Techniken / Schweißfähigkeiten“ (diese sollen ins feld `faehigkeiten` überführt werden) muss das Niveau realistisch aus der Berufserfahrung des Kandidaten abgeleitet werden und darf nicht pauschal auf „Advanced“ gesetzt werden.
Das Modell soll folgende Logik verwenden:
Expert = über viele Jahre (ca. 8–10+ Jahre) regelmäßig angewendet, auch in anspruchsvollen Projekten oder internationalen Einsätzen, selbstständiges Arbeiten nach Zeichnung, komplexe Bauteile oder hohe Wandstärken.
Advanced = solide praktische Erfahrung (ca. 3–8 Jahre), regelmäßig angewendet, selbstständiges Arbeiten möglich, aber nicht zwingend auf höchstem Spezialniveau.
Intermediate = grundlegende bis mittlere Erfahrung (ca. 1–3 Jahre), unter Anleitung oder in einfacheren Projekten eingesetzt.
Basic = nur Grundkenntnisse, kurze Einsätze oder nur unterstützende Tätigkeiten.

ANWENDUNG AUF DIE LISTE (Ins Feld `faehigkeiten` abspeichern):
Format beibehalten (Schlüssel, Beschreibung / Level):
Handwerkliches Geschick
Installation
Demontage
Blechbearbeitung
Montieren von Stahlkonstruktionen
Sägen / Schleifen / Schrauben
Bohren
Schweißarbeiten frei Hand
Schweißarbeiten mit Schweißroboter
MAG Schweißen
WIG Schweißen

Für jede dieser Fähigkeiten muss das Niveau individuell bestimmt werden — basierend auf:
Berufsjahren, Häufigkeit der Anwendung, Projektart (z. B. Schwerstahlbau = höheres Niveau), Schweißverfahren im CV.
WICHTIG:
Wenn der Kandidat z. B. 15+ Jahre MAG schweißt -> „Expert“, nicht „Advanced“.
Wenn WIG nur selten erwähnt wird -> maximal „Intermediate“.
Wenn Schweißroboter nicht klar erwähnt wird -> „Basic“ oder leer lassen.

ZUSAMMENFASSUNG:
Ca. 150 Wörter auf Deutsch. Erwähnung von Erfahrung, Branchen, Haupt-Schweißverfahren, Zertifikate.
Startsatz: „Herr/Frau [Nachname] verfügt über [X] Jahre Berufserfahrung...“
""",

    "Schlosser": """
Kernaufgaben: Metall-/Stahlkonstruktionen montieren, Baugruppen zusammenbauen, Maschinenwartung,
  Rohrleitungsmontage, Hydraulik und Pneumatik
Werkstoffe: Baustahl, Edelstahl, Aluminium
Fertigkeiten: Bohren, Sägen, Schleifen, Fräsen, Drehen (Grundkenntnisse), MIG/MAG-Schweißen,
  Elektrodenschweißen, Brennschneiden, Lesen von technischen Zeichnungen
Berechtigungen: Gabelstapler, Führerschein Klasse B, ggf. Kranführerschein
""",

    "Mechaniker": """
Kernaufgaben: Wartung und Instandhaltung von Maschinen und Fahrzeugen, Fehlerdiagnose,
  Fehlersuche (elektrisch/mechanisch), Reparatur, Einheit montieren/demontieren
Fachgebiet: KFZ-Mechanik, Industriemechanik, Landmaschinenmechanik, Nutzfahrzeuge
Fertigkeiten: Hydraulik, Pneumatik, Werkzeugkunde, CNC-Grundkenntnisse, 
  Lesen technischer Zeichnungen, Schweißen (MIG/MAG, Grundkenntnisse)
Berechtigungen: Führerschein Klasse B/C/CE, Gabelstapler, ggf. ADR
""",

    "Elektriker": """
Kernaufgaben: Installation elektrischer Anlagen (Nieder-/Mittelspannung), Verdrahtung, 
  Schalttafelbau, Fehlersuche, Inbetriebnahme, SPS-Grundkenntnisse
Normen: EN 50110, VDE-Vorschriften, ATEX (Explosionsschutz) falls zutreffend
Fertigkeiten: Schaltplan lesen, Kabel verlegen, Klemmen und Stecker konfektionieren,
  Messtechnik (Multimeter, Isolationsmessung), Photovoltaik-Grundkenntnisse
Berechtigungen: Führerschein Klasse B, ggf. Befähigungsnachweis nach EN 50110
""",

    "Lackierer": """
Kernaufgaben: Korrosionsschutz- und Oberflächenbeschichtung, Lackierarbeiten (Industrie/Bau),
  Strahlarbeiten (Sandstrahlen, Kugelstrahlen), Untergrundvorbereitung, Schichtdickenmessung
Materialien: Epoxid, Polyurethan, Zinkstaub, Farbsysteme nach Spezifikation (ISO 12944)
Equipment: Airless-Spritzgeräte, Konventionelle Pistolen, ESD-Ausrüstung
Berechtigungen: Führerschein Klasse B, ggf. Befähigungsnachweis Arbeitssicherheit,
  Höhenarbeitserlaubnis (Gerüst/Arbeitsbühne)
""",

    "Klempner": """
Kernaufgaben: Heizungs- und Sanitärinstallation, Rohrverbindungen (löten, pressen, 
  schweißen), Lüftungskanäle, Inbetriebnahme und Wartung von Heizanlagen
Materialien: Kupfer, Edelstahl, Kunststoffrohre (PE, PVC, PP), Verbundrohre
Normen: DVGW, VOB, DIN-Vorschriften
Berechtigungen: Führerschein Klasse B, ggf. Gas-Wasser-Installateurschein
""",

    "Maurer": """
Kernaufgaben: Mauerwerk, Beton- und Stahlbetonbau, Schalungsarbeiten, Putzarbeiten,
  Fundamentarbeiten, Abbruch- und Demontagearbeiten
Materialien: Beton, Ziegel, Kalksandstein, Porenbeton, Stahlbeton
Fertigkeiten: Vermessung (Wasserwaage, Deodolit-Grundkenntnisse), 
  Zeichnungslesen, Gerüstbau (Grundkenntnisse)
Berechtigungen: Führerschein Klasse B, ggf. Baggerführerschein
""",

    "Zimmermann": """
Kernaufgaben: Dachstuhlkonstruktion, Holzrahmenbau, Balkenkonstruktionen,
  Holzverbindungen, Instandhaltung von Holzkonstruktionen, Ausbauarbeiten
Materialien: Konstruktionsvollholz, Brettschichtholz, OSB-Platten, Dämmstoffe
Fertigkeiten: Zeichnungslesen, Abbund, Zimmerer-Handwerkzeug, Zimmereimaschinen,
  Dachabdichtung, Holzschutzbehandlung
Berechtigungen: Führerschein Klasse B
""",

    "Tischler": """
Kernaufgaben: Möbelherstellung und -montage, Fenster- und Türmontage, Innenausbau,
  Renovierungsarbeiten, Beschlagtechnik, Lackier-/Beizarbeiten an Holz
Materialien: Massivholz, Spanplatten, MDF, Furniere, Leimholz
Fertigkeiten: CNC-Holzbearbeitung (Grundkenntnisse), Handwerkszeug, 
  Maßnehmen, Zeichnungslesen, Oberflächenbehandlung
Berechtigungen: Führerschein Klasse B
""",
}

# Default / generic block for unknown trades
_SKILL_BLOCKS["Other"] = """
Kernaufgaben und relevante Tätigkeiten aus dem CV übernehmen.
Fertigkeiten und Berechtigungen: aus dem CV extrahieren.
"""

# Make sure every JOB_PROFILES entry has a block (fallback to "Other")
def _get_skill_block(job_role: str) -> str:
    return _SKILL_BLOCKS.get(job_role, _SKILL_BLOCKS["Other"])


# ---------------------------------------------------------------------------
# JSON schema comment (embedded in prompt)
# ---------------------------------------------------------------------------

_JSON_SCHEMA = """{
  "anrede": "Herr oder Frau",
  "vorname": "Vorname",
  "nachname": "Nachname",
  "geburtsdatum": "TT.MM.JJJJ",
  "geburtsort": "Stadt, Land oder nur Land",
  "staatsangehoerigkeit": "Staatsangehörigkeit",

  "berufserfahrung": [
    {
      "von": "MM/JJJJ",
      "bis": "MM/JJJJ oder present",
      "arbeitgeber": "FIRMENNAME IN GROSSBUCHSTABEN, Ort",
      "ort_land": "Land",
      "position": "Stellenbezeichnung",
      "taetigkeiten": "Kurze Beschreibung der Haupttätigkeit, dann weitere Details"
    }
  ],

  "bildung": [
    {
      "jahre": "JJJJ-JJJJ",
      "einrichtung": "Name der Schule / Hochschule, Land",
      "abschluss": "Fachrichtung oder Abschluss"
    }
  ],

  "weiterbildung": [
    {
      "jahre": "JJJJ",
      "anbieter": "Kursanbieter",
      "kurs": "Kursbezeichnung"
    }
  ],

  "zertifikate": [
    {
      "bezeichnung": "z.B. ISO 9606-1 / VCA / Hot Work / Gabelstapler",
      "ausgestellt": "JJJJ oder MM.JJJJ",
      "gueltig_bis": "JJJJ oder null"
    }
  ],

  "sprachen": [
    { "sprache": "Sprache", "niveau": "z.B. C2 / B2 / B1 / A2 / Muttersprache" }
  ],

  "faehigkeiten": [
    { "name": "Fähigkeitsbereich", "beschreibung": "Detaillierte Beschreibung der Fähigkeit" }
  ],

  "zusammenfassung": "~150 Wörter auf Deutsch: Erfahrung, Einsatzländer, Branchen, Verfahren, Zertifikate, Soft-Facts. Beginne mit Herr/Frau [Nachname] verfügt über..."
}"""


# ---------------------------------------------------------------------------
# Main prompt builder
# ---------------------------------------------------------------------------

def build_lebenslauf_prompt(text: str, job_role: str = "Schweißer") -> str:
    skill_block = _get_skill_block(job_role)
    return (
        "Du bist ein auf Personaldienstleistung spezialisierter HR-Assistent.\n"
        "Dir werden der extrahierte Text eines Lebenslaufs und ggf. eines Ausweisdokuments\n"
        "eines Kandidaten übergeben.\n\n"
        "Erstelle daraus ein strukturiertes Kandidatenprofil exakt im Stil der\n"
        f"Vorlage Lebenslauf für die Position: **{job_role}**\n\n"
        "════════════════════════════════════════\n"
        "REGELN\n"
        "════════════════════════════════════════\n"
        "1. Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Objekt (kein Markdown, keine Code-Fences,\n"
        "   keine Erklärungen).\n"
        "2. Entferne alle privaten Kontaktdaten des Kandidaten (Telefon, E-Mail, genaue\n"
        "   Privatadresse) — diese dürfen NICHT im JSON erscheinen.\n"
        "3. Formuliere alles auf Deutsch.\n"
        "4. Berufserfahrung:\n"
        "   - Beginne ab dem 19. Lebensjahr des Kandidaten.\n"
        "   - Sortiere neueste Einträge zuerst (absteigend).\n"
        "   - Lückenlos: Fülle Zeiträume ohne Anstellung mit „Zeitpuffer/Projektpause“ oder „Selbststudium/Weiterbildung“.\n"
        "   - Format für Tätigkeiten: Benenne Schweißverfahren (z.B. 135, 141), Material (Stahl/Edelstahl), Bauteile und Blechdicken (z.B. 5-50mm).\n"
        "5. Bildung: PFLICHT — gib IMMER mindestens einen Eintrag in 'bildung' an. "
        "   Wenn keine Schule im CV erwähnt wird, leite eine realistische Berufsschule aus "
        "   Geburtsort und Beruf ab (z.B. technische Schule für Metallverarbeitung, 4 Jahre Dauer). "
        "   Das 'bildung'-Array darf NIEMALS leer sein.\n"
        "6. Sprachniveaus: „communicative“ = B1-B2.\n"
        "7. Zusammenfassung: ca. 150 Wörter. Beginne mit „Herr/Frau [Nachname] verfügt über [X] Jahre Erfahrung...“\n\n"
        "════════════════════════════════════════\n"
        f"FACHLICHE REFERENZ FÜR POSITION: {job_role}\n"
        "════════════════════════════════════════\n"
        f"{skill_block}\n\n"
        "════════════════════════════════════════\n"
        "AUSGABE-JSON-SCHEMA\n"
        "════════════════════════════════════════\n"
        f"{_JSON_SCHEMA}\n\n"
        "════════════════════════════════════════\n"
        "DOKUMENT-TEXT (CV + ggf. Ausweisdaten)\n"
        "════════════════════════════════════════\n"
        f"{text}\n"
    )


# ---------------------------------------------------------------------------
# Convenience: system message
# ---------------------------------------------------------------------------

LEBENSLAUF_SYSTEM_MSG = (
    "Du bist ein professioneller HR-Assistent für Personaldienstleistung. "
    "Antworte immer mit validem JSON ohne Markdown-Fences und ohne Erklärungen. "
    "CRITICAL: Wenn das Dokument KEINE identifizierbaren Namen oder Daten enthält (z. B. leere oder unsinnige Texte), "
    "setze das 'nachname' Feld auf 'N/A'. Halluziniere NIEMALS Beispielnamen wie 'Max Mustermann' oder 'Hans Müller'."
)
