import json
from populator import populate_template
import os

# Simulated data from get_lebenslauf_data
data = {
    "vorname": "John",
    "nachname": "Doe",
    "geburtsdatum": "1990-01-01",
    "geburtsort": "Berlin",
    "staatsangehoerigkeit": "Deutsch",
    "nationality": "German",
    "first_name": "John",
    "last_name": "Doe",
    "job_role": "Schweißer",
    "employment_history": [
        {
            "employer": "Tech Corp",
            "position": "Welder",
            "duties": ["Welding", "Brazing", "Testing"],
            "start_date": "2020-01",
            "end_date": "Present"
        }
    ],
    "education": {
        "higher_education": [
            {"years": "2010-2014", "institution": "TUM", "field": "Engineering"}
        ],
        "further_training": []
    }
}

# The user's specific template tags
# {%tr for he in education.higher_education %}
# {{ he.years }}
# {{ he.institution }} – {{ he.field }}

tpl_path = "templates/Vorlage_Lebenslauf_Kandidatenprofil_V2_Mit_Tags.docx"
out_path = "debug_reformat_output.docx"

print("Testing populator with user-style tags...")
try:
    populate_template(tpl_path, out_path, data)
    print(f"Success! Generated {out_path}")
except Exception as e:
    print(f"FAILED: {e}")
