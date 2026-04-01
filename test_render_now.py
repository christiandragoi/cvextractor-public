"""
Direct test: render the Vorlage template with dummy data to confirm if the fix works locally.
"""
import os, sys, json, tempfile
sys.path.insert(0, os.getcwd())

from populator import populate_template

TPL = r"C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster\Vorlage_Lebenslauf_Schweißer Python.docx"

dummy = {
    "name": "Max Mustermann",
    "vorname": "Max",
    "nachname": "Mustermann",
    "geburtsdatum": "01.01.1990",
    "geburtsort": "Berlin",
    "staatsangehoerigkeit": "Deutsch",
    "job_role": "Schweißer",
    "zusammenfassung": "Erfahrener Schweißer.",
    "starttermin": "01.05.2026",
    "berufserfahrung": [
        {
            "von": "01/2020",
            "bis": "heute",
            "arbeitgeber": "MUSTER GmbH",
            "position": "Schweißer",
            "taetigkeiten": "MAG Schweißen",
        }
    ],
    "bildung": [
        {"jahre": "2005-2009", "einrichtung": "Berufsschule Berlin", "abschluss": "Metallbauer"}
    ],
    "weiterbildung": [
        {"jahre": "2015", "anbieter": "TÜV", "kurs": "ISO 9606-1"}
    ],
    "sprachen": [
        {"sprache": "Deutsch", "niveau": "Muttersprache"},
        {"sprache": "Englisch", "niveau": "B2"},
    ],
    "faehigkeiten": [
        {"name": "MAG Schweißen", "beschreibung": "Expert"}
    ],
    "zertifikate": [],
}

out = tempfile.mktemp(suffix=".docx")
print(f"Output path: {out}")
try:
    result = populate_template(TPL, out, dummy)
    print(f"SUCCESS! Generated: {result}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"\nFAILED: {e}")
