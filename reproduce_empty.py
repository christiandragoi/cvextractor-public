import json
import os
from populator import populate_template

# Mock data as returned by get_lebenslauf_data
data = {
    "anrede": "Herr",
    "vorname": "John",
    "nachname": "Doe",
    "geburtsdatum": "01.01.1990",
    "geburtsort": "Berlin",
    "staatsangehoerigkeit": "Deutsch",
    "job_role": "Schweißer",
    "berufserfahrung": [
        {
            "von": "01/2020",
            "bis": "present",
            "arbeitgeber": "MOCK CORP",
            "ort_land": "Germany",
            "position": "Senior Schweißer",
            "taetigkeiten": "Schweißen von Rohren (141), Testen."
        }
    ],
    "bildung": [
        {
            "jahre": "2006-2010",
            "einrichtung": "Berufsschule Berlin",
            "abschluss": "Metallbauer"
        }
    ],
    "weiterbildung": [
        {
            "jahre": "2012",
            "anbieter": "TÜV",
            "kurs": "Schweißkurs 135"
        }
    ],
    "zertifikate": [
        {
            "bezeichnung": "ISO 9606-1",
            "ausgestellt": "2023",
            "gueltig_bis": "2025"
        }
    ],
    "sprachen": [
        { "sprache": "Deutsch", "niveau": "Muttersprache" }
    ],
    "faehigkeiten": [
        { "name": "MAG", "beschreibung": "Expert" }
    ],
    "zusammenfassung": "John Doe ist ein erfahrener Schweißer..."
}

tpl_path = "templates/Vorlage_Lebenslauf_Kandidatenprofil_V2_Mit_Tags.docx"
out_path = "test_output.docx"

if not os.path.exists(tpl_path):
    # Create the template first if it doesn't exist
    import create_template
    # create_template.py runs on import and saves the file

print(f"Populating template {tpl_path}...")
populate_template(tpl_path, out_path, data)
print(f"Done. Check {out_path}")
