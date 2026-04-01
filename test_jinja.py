import os
from docx import Document
from docxtpl import DocxTemplate

doc = Document()
text = """
{% if education.higher_education %}
{% tr for he in education.higher_education %}
{{ he.years }}
{{ he.institution }}
{% tr endfor %}
{% endif %}

{% tr for job in employment_history %}
Arbeitgeber: {{ job.employer }}
Tätigkeit: {% for d in job.duties %}
{{ d }}{% endfor %}
{% tr endfor %}

{% if job_type == "Sudor" %}
Fähigkeiten
{% tr for l in language_skills %}	
{{ l.language }}:	{{ l.level }}
{% tr endfor %}	
"""

# Let's save this as a docx
doc.add_paragraph(text)
doc.save("/tmp/test_template.docx")

tpl = DocxTemplate("/tmp/test_template.docx")
context = {
    "education": {"higher_education": [{"years": "2020", "institution": "Uni"}]},
    "employment_history": [{"employer": "ACME", "duties": ["a", "b"]}],
    "job_type": "Sudor",
    "language_skills": [{"language": "ENG", "level": "C1"}],
}
try:
    tpl.render(context)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {type(e).__name__} - {e}")

