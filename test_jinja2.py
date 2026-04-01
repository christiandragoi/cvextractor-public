import os
from docx import Document
from docxtpl import DocxTemplate

doc = Document()
text = """Titel des Job Postings		angefragt	falls abweichend
Einkaufskurzprofil (EKP)	X|YYY|XXX|Z	X|YYY|XXX|Z
Stundenverrechnungssatz (SVS)	€	€
Möglicher Starttermin (verfügbar ab / Kündigungsfrist)	{{ starttermin }}

{% if education.higher_education %}
{%p for he in education.higher_education %}
{{ he.years }}
{{ he.institution }} – {{ he.field }}
{%p endfor %}
{% endif %}

Beruferfahrung	
{%p for job in employment_history %}
Arbeitgeber: {{ job.employer }}
Position: {{ job.position }}
Tätigkeit: {% for d in job.duties %}
{{ d }}{% endfor %}
{{ job.start_date }} – {{ job.end_date }}
{%p endfor %}	
	
{% if education.higher_education %}
Bildungseinrichtung:  
{%p for he in education.higher_education %}	
{{ he.years }}:
	{{ he.institution }} – {{ he.field }}
{%p endfor %}	
{% endif %}

{% if education.further_training %}
WEITERBILDUNG:
{%p for ft in education.further_training %}	
{{ ft.years }}:
	{{ ft.institution }} – {{ ft.field }}
{%p endfor %}	
{% endif %}

{% if job_type == "Sudor" %}
Fähigkeiten
Schweißer (MIG/MAG 135)
Handwerkliches Geschick: Sicherer Umgang mit Schweißgeräten, Brennern und Handwerkzeugen
Installation: Montage und Heften von Schweißbaugruppen nach Zeichnung und Schweißplan
Demontage: Trennen von Metallverbindungen mittels Brennschneider, Trennschleifer und Bohrmaschine
Blechbearbeitung: Zuschneiden, Anfasen, Richten und Vorbereiten von Blechen und Profilen
Montieren von Stahlkonstruktionen: Zusammensetzen, Ausrichten und Fixieren von Schweißteilen und Trägern
MIG-MAG 135, 136,138: 
Arbeit mit Robotern: Bedienung, Programmierung und Überwachung von Schweißrobotern (MIG/MAG-Automation)	
{% endif %}

Sprachkenntnisse:
{%p for l in language_skills %}	
{{ l.language }}:	{{ l.level }}
{%p endfor %}	
"""

for line in text.strip().split('\n'):
    doc.add_paragraph(line)
    
doc.save("/tmp/test_template2.docx")

tpl = DocxTemplate("/tmp/test_template2.docx")
context = {
    "education": {"higher_education": [{"years": "2020", "institution": "Uni", "field": "CS"}],
                  "further_training": [{"years": "2021", "institution": "Coursera", "field": "AI"}]},
    "employment_history": [{"employer": "ACME", "position": "Dev", "duties": ["a", "b"], "start_date": "2020", "end_date": "2021"}],
    "job_type": "Sudor",
    "language_skills": [{"language": "ENG", "level": "C1"}],
    "starttermin": "ASAP"
}
try:
    tpl.render(context)
    print("SUCCESS")
    tpl.save("/tmp/test_template2_rendered.docx")
except Exception as e:
    print(f"ERROR: {type(e).__name__} - {e}")
