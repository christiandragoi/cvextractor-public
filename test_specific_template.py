import os
import json
from populator import populate_template

data = {
    "name": "Jane Doe",
    "vorname": "Jane",
    "nachname": "Doe",
    "job_role": "Schweißer",
    "geburtsdatum": "01.01.1990",
    "geburtsort": "Berlin",
    "nationality": "Deutsch",
    "education": {
        "higher_education": [{"years": "2010-2015", "institution": "TUM", "field": "Engineering"}],
        "further_training": [{"years": "2016", "institution": "TÜV", "field": "Welding"}]
    },
    "employment_history": [
        {
            "employer": "Tech Corp",
            "position": "Welder",
            "start_date": "2016-01",
            "end_date": "Present",
            "duties": ["Duty 1", "Duty 2"]
        }
    ],
    "language_skills": [
        {"language": "Deutsch", "level": "Muttersprache"}
    ]
}

source = r"C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster .docx"
out = "test_user_template_output.docx"

try:
    print(f"Testing population on {source}")
    populate_template(source, out, data)
    print("SUCCESS: File generated at", out)
except Exception as e:
    print("ERROR:", e)
    import traceback
    traceback.print_exc()
