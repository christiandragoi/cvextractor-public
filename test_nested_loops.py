import os
from populator import _fix_jinja_xml

# Test 1: Comma-separated (flat) loop
flat_loop = '{%tr for job in employment_history %} Tätigkeiten: {% for d in job.duties %}{{ d }}{% endfor %} {%tr endfor %}'
result_flat = _fix_jinja_xml(flat_loop)
print(f"Flat loop result: {result_flat}")
assert 'join(", ")' in result_flat

# Test 2: Vertical (multiline) loop
vertical_loop = """{%tr for job in employment_history %}
Tätigkeiten: 
{% for d in job.duties %}
{{ d }}
{% endfor %}
{%tr endfor %}"""
result_vert = _fix_jinja_xml(vertical_loop)
print(f"Vertical loop result: {result_vert}")
# In current logic, if it contains a newline, it should join with \n
assert 'join("\\n")' in result_vert

# Test 3: Curly quote fix
curly_tag = '{% if job_type == "Sudor“ %}'
result_curly = _fix_jinja_xml(curly_tag)
print(f"Curly quote fix: {result_curly}")
assert '“' not in result_curly

print("\n--- ALL TESTS PASSED ---")
