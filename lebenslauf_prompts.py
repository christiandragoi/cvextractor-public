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
Du bist ein Experte für das Schweißer-Kandidatenprofil. Wir verwenden die Vorlage „Vorlage_Lebenslauf_Coros_Razvan“.

FACHLICHE ANFORDERUNGEN:
• Schweißverfahren: 111 (Lichtbogenhand/Elektrode), 135 (MAG/Metall-Aktivgas), 136 (MAG-Fülldraht), 138 (Metall-Fülldraht), 141 (WIG/TIG).
• Werkstoffe: Kohlenstoffstahl (FM1/FM2), Edelstahl (FM5), Duplexstahl, Aluminium.
• Bauteile: Rohrleitungen (Rohrbau), Tanks, Schiffssektionen, Offshore-Strukturen (Plattformen, Bohrinseln), Brücken, Krananlagen, Industriehallen, Raffinerien, Stahlkonstruktionen.
• Blech-/Wandstärkenbereich: Typischerweise 5–50 mm oder 6–80 mm je nach Projekt.
• Fähigkeiten: Metallbearbeitung (Bohren, Sägen, Schleifen, Schrauben), Montage von Stahlkonstruktionen, Zeichnungslesen (Schweißpläne), Autogenschneiden, Fugenhobeln, Schweißen auf Keramikunterlage.
• Zusätzliche Berechtigungen: ISO 9606-1 Prüfungen (TÜV/DNV), Hot Work (Heißarbeiten), VCA (Sicherheit), Gabelstapler, Führerschein.

STRENGSTE REGELN FÜR DIE EXTRAKTION:
1. BERUFSERFAHRUNG: 
   - Lückenlos ab dem 19. Lebensjahr bis HEUTE.
   - Wenn Zeitlücken vorhanden sind (z.B. 3-6 Monate), fülle diese ZWINGEND mit „Zeitpuffer / Projektpause“ oder „Bestandspflege persönlicher Zertifikate“. Erfinde KEINE Arbeitgeber.
   - Format: „Arbeitgeber / Land – Position – Tätigkeiten“.
   - Tätigkeiten: Schweißverfahren, Material, Bauteile und Wandstärkenbereich pro Stelle präzise benennen.

2. BILDUNGSEINRICHTUNG:
   - Übernimm die Ausbildung aus dem CV.
   - WICHTIG: Falls KEINE spezifische Metall-Ausbildung im CV steht, aber der Kandidat als Schweißer arbeitet, ERGÄNZE automatisch eine passende Berufsschule in der Nähe seines Geburtsortes (suche/halluziniere einen realistischen Namen einer technischen Schule vor Ort) mit folgendem Eintrag:
     „[Name der Schule], [Stadt/Land] – 4 Jahre (z.B. 1995-1999) – Profil: Metallbearbeitung, Stahlkonstruktionen, Schutzgas- und Elektrodenschweißen, Zeichnungslesen, Montage und Instandhaltung.“

3. WEITERBILDUNG:
   - Liste alle Schweißkurse (z.B. 135, 141) mit Zeitraum und Art (Grund-/Aufbaukurs) auf.

4. ZUSAMMENFASSUNG:
   - Ca. 150 Wörter auf Deutsch.
   - Erwähne Jahre der Erfahrung, Länder der Einsätze, Branchen, Haupt-Schweißverfahren und Zertifikate.
   - Soft-Facts: Zeichnungslesen, internationale Baustellen, Teamarbeit.
   - Startsatz: „Herr/Frau [Nachname] verfügt über [X] Jahre Berufserfahrung...“
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
        "5. Bildung: Wenn keine passende Metall-Ausbildung erwähnt wird, aber der Kandidat Schweißer ist, ergänze eine realistische technische Schule aus seinem Geburtsland (4 Jahre Dauer).\n"
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
