"""Test the new populator against the actual user template."""
import sys
sys.path.insert(0, '.')

from populator import populate_template

# Minimal test data to verify rendering works
test_data = {
    "name": "Test Kandidat",
    "job_role": "Schweißer",
    "job_type": "Sudor",
    "employment_history": [
        {
            "employer": "ACME GmbH, Deutschland",
            "position": "Schweißer",
            "duties": ["MAG Schweißen 135", "Stahlkonstruktionen", "Rohrleitungsbau"],
            "start_date": "01/2020",
            "end_date": "present",
        }
    ],
    "education": {
        "higher_education": [
            {"years": "2010-2014", "institution": "Technische Schule Timisoara", "field": "Metallbearbeitung"}
        ],
        "further_training": [
            {"years": "2019", "institution": "TÜV Nord", "field": "Schweißkurs 135/136"}
        ],
    },
    "language_skills": [
        {"language": "Deutsch", "level": "B1"},
        {"language": "Rumänisch", "level": "Muttersprache"},
    ],
    "starttermin": "01.04.2026",
}

template_path = r'C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster\Vorlage_Lebenslauf_Schweißer Python.docx'
output_path = r'C:\tmp\test_populated.docx'

try:
    result = populate_template(template_path, output_path, test_data)
    print(f"SUCCESS! Output saved to: {result}")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
