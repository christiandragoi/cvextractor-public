"""
populator.py
Renders a DOCX template using docxtpl (Jinja2 engine for Word).

Handles:
  1. Smart-quote normalisation (" " → " ")
  2. Nested {% for %} inside {%tr %} blocks (flattened to |join)
  3. Missing {% endif %} auto-injection
  4. Orphaned {% endfor %} removal
"""

import re
from docxtpl import DocxTemplate


# ── Post-patch XML fixer ─────────────────────────────────────────────────────

def _fix_jinja_xml(xml: str) -> str:
    """
    PRE-PROCESSOR: Runs BEFORE docxtpl's patch_xml().
    Removes Word 'shrapnel' tags so docxtpl can read Jinja tags cleanly.
    """
    # Remove self-closing noise elements that Word inserts between text runs.
    xml = re.sub(r'<w:proofErr[^/]*/>', '', xml)
    xml = re.sub(r'<w:noProof/>', '', xml)
    # Fix smart quotes
    xml = xml.replace('\u201c', '"').replace('\u201d', '"').replace('\u201e', '"')
    xml = xml.replace('\u2018', "'").replace('\u2019', "'").replace('\u201a', "'")
    return xml


def _balance_endfor(xml: str) -> str:
    """
    POST-PROCESSOR: Runs AFTER docxtpl's patch_xml().
    
    Finds and removes orphaned {% endfor %} tags — ones that appear before
    any for loop is open, which would crash Jinja with 'unknown tag endfor'.
    Also balances endif tags.
    """
    # We need to find the FIRST orphaned endfor, not just count them.
    # An orphaned endfor is one where the nesting depth goes below 0.
    
    # Extract all Jinja tags WITH their positions in the XML
    tag_positions = []
    text_only = re.sub(r'<[^>]+>', '', xml)
    
    # Simulate Jinja parsing to find the orphan
    depth = 0
    orphan_tags = []  # tags to remove from the text_only representation
    
    for m in re.finditer(r'\{%-?\s*(?:for|endfor|if|endif|else)[^%]*%\}', text_only):
        tag = m.group(0)
        if re.search(r'\{%-?\s*(?:for)\s', tag):
            depth += 1
        elif re.search(r'\{%-?\s*endfor', tag):
            if depth <= 0:
                # This is an orphaned endfor — record it for removal
                orphan_tags.append(tag)
            else:
                depth -= 1
    
    # Remove each orphaned endfor from the actual XML (first occurrence of each)
    for tag in orphan_tags:
        idx = xml.find(tag)
        if idx != -1:
            xml = xml[:idx] + xml[idx + len(tag):]

    # Balance {% if %} vs {% endif %}
    text_only = re.sub(r'<[^>]+>', '', xml)
    if_count    = len(re.findall(r'\{%-?\s*if\s', text_only))
    endif_count = len(re.findall(r'\{%-?\s*endif\s*-?%\}', text_only))
    if if_count > endif_count:
        for _ in range(if_count - endif_count):
            xml = xml.replace('</w:body>', '{% endif %}</w:body>')
    
    # Also handle missing endfor (if for > endfor after removing orphans)
    text_only = re.sub(r'<[^>]+>', '', xml)
    for_count    = len(re.findall(r'\{%-?\s*for\s', text_only))
    endfor_count = len(re.findall(r'\{%-?\s*endfor\s*-?%\}', text_only))
    if for_count > endfor_count:
        for _ in range(for_count - endfor_count):
            xml = xml.replace('</w:body>', '{% endfor %}</w:body>')
    
    return xml



# ── Job-type mapping ──────────────────────────────────────────────────────────

JOB_TYPE_MAP = {
    "Schweißer":               "Sudor",
    "Schlosser":               "Sudor",
    "Mechaniker":              "Sudor",
    "Lackierer":               "Sudor",
    "Klempner":                "Sudor",
    "Maurer":                  "Sudor",
    "Zimmermann":              "Sudor",
    "Tischler":                "Sudor",
    "Elektriker":              "Elektriker",
    "Sudor":                   "Sudor",
    "Schweißer cu Elektriker": "Schweißer cu Elektriker",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(v, fallback=""):
    return v if v else fallback


def _fmt_edu(lst):
    return [
        {
            "years":       _safe(e.get("years", e.get("jahre")), ""),
            "institution": _safe(e.get("institution", e.get("einrichtung")), ""),
            "field":       _safe(e.get("field", e.get("abschluss", e.get("kurs"))), ""),
        }
        for e in (lst or [])
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def populate_template(template_path: str, output_path: str, data: dict) -> str:
    """
    Render template_path with data dict and save to output_path.
    """
    doc = DocxTemplate(template_path)
    doc.init_docx()

    # Monkey-patch build_xml to inject our pre-fix BEFORE docxtpl's patch_xml
    # This is the correct injection point: we need to clean Word's shrapnel tags
    # so that docxtpl's patch_xml can correctly identify and transform {%tr for %} etc.
    def _patched_build_xml(context, jinja_env=None):
        xml = doc.get_xml()
        # Phase 1: Strip Word noise BEFORE docxtpl's patch_xml
        xml = _fix_jinja_xml(xml)
        # Phase 2: Let docxtpl do its table-row expansion
        xml = doc.patch_xml(xml)
        # Phase 3: Balance any stray endfor tags docxtpl introduced
        xml = _balance_endfor(xml)
        # Phase 4: Render the clean XML
        xml = doc.render_xml_part(xml, doc.docx._part, context, jinja_env)
        return xml

    doc.build_xml = _patched_build_xml

    job_role = _safe(data.get("job_role"), "Schweißer")
    job_type = JOB_TYPE_MAP.get(job_role, job_role)

    # --- SYNCHRONIZATION ---
    # We ensure both German (template-style) and English (AI-style) keys exist
    # to avoid empty documents no matter what tags the user has.

    # 1. Identity & Profile
    name = _safe(data.get("name"), "") or f"{data.get('vorname', '')} {data.get('nachname', '')}".strip()
    first_name = _safe(data.get("first_name", data.get("vorname")), "")
    last_name = _safe(data.get("last_name", data.get("nachname")), "")
    dob = _safe(data.get("date_of_birth", data.get("birth_date", data.get("geburtsdatum"))), "")
    pob = _safe(data.get("place_of_birth", data.get("birth_place", data.get("geburtsort"))), "")
    nat = _safe(data.get("nationality", data.get("staatsangehoerigkeit")), "")
    summary = _safe(data.get("profile_summary", data.get("zusammenfassung")), "")
    start = _safe(data.get("starttermin", data.get("start_date")), "")

    # 2. Employment History Synchronization
    raw_jobs = data.get("employment_history", data.get("berufserfahrung", []))
    sync_jobs = []
    for j in raw_jobs:
        if not isinstance(j, dict): continue
        duties = j.get("duties", j.get("taetigkeiten", []))
        if isinstance(duties, str):
            duties = [d.strip() for d in duties.split(",") if d.strip()]
        duties_str = ", ".join(duties) if isinstance(duties, list) else str(duties)
        
        # Dual-key object for both {{ job.von }} and {{ job.start_date }}
        item = {
            # English keys
            "employer":   _safe(j.get("employer", j.get("arbeitgeber")), "N/A"),
            "position":   _safe(j.get("position"), job_role),
            "duties":     duties,
            "duties_str": duties_str,
            "start_date": _safe(j.get("start_date", j.get("von")), ""),
            "end_date":   _safe(j.get("end_date", j.get("bis")), ""),
            # German keys
            "arbeitgeber": _safe(j.get("arbeitgeber", j.get("employer")), "N/A"),
            "von":         _safe(j.get("von", j.get("start_date")), ""),
            "bis":         _safe(j.get("bis", j.get("end_date")), ""),
            "taetigkeiten": duties_str, # Use string by default for German templates
        }
        sync_jobs.append(item)

    # 3. Education Synchronization
    # AI often returns a list for "bildung" and a list for "weiterbildung".
    # UI buffer returns a dict with "higher_education" and "further_training" keys.
    edu_input = data.get("education", {})
    bildung_raw = data.get("bildung", [])
    training_raw = data.get("weiterbildung", [])

    if isinstance(edu_input, dict):
        sync_edu = _fmt_edu(edu_input.get("higher_education", bildung_raw))
        sync_training = _fmt_edu(edu_input.get("further_training", training_raw))
    else:
        # Fallback if somehow it's not a dict
        sync_edu = _fmt_edu(bildung_raw)
        sync_training = _fmt_edu(training_raw)

    # Dual-language list for loops
    # b.jahre / b.years, b.einrichtung / b.institution, b.abschluss / b.field
    def dual_edu(lst):
        res = []
        for e in lst:
            res.append({
                "years":       _safe(e.get("years"), ""), 
                "jahre":       _safe(e.get("years"), ""),
                "institution": _safe(e.get("institution"), ""), 
                "einrichtung": _safe(e.get("institution"), ""),
                "field":       _safe(e.get("field"), ""), 
                "abschluss":   _safe(e.get("field"), ""), 
                "kurs":        _safe(e.get("field"), "")
            })
        return res

    # 4. Languages
    raw_langs = data.get("language_skills", data.get("sprachen", []))
    sync_langs = [
        {
            "language": _safe(l.get("language", l.get("sprache")), ""),
            "sprache":  _safe(l.get("sprache", l.get("language")), ""),
            "level":    _safe(l.get("level", l.get("niveau")), ""),
            "niveau":   _safe(l.get("niveau", l.get("level")), ""),
        }
        for l in raw_langs
    ]

    # Final Context Construction
    context = {}
    context.update(data) # Start with raw data
    
    # Overwrite/Add synchronized master keys
    context.update({
        "name":                    name,
        "first_name":              first_name,
        "vorname":                 first_name,
        "last_name":               last_name,
        "nachname":                last_name,
        "date_of_birth":           dob,
        "geburtsdatum":            dob,
        "birth_date":              dob,
        "place_of_birth":          pob,
        "geburtsort":              pob,
        "birth_place":             pob,
        "nationality":             nat,
        "staatsangehoerigkeit":    nat,
        "profile_summary":         summary,
        "zusammenfassung":         summary,
        "job_role":                job_role,
        "job_type":                job_type,
        "starttermin":             start,
        "start_date":              start,
        
        # Lists
        "employment_history":      sync_jobs,
        "berufserfahrung":         sync_jobs,
        "education": {
            "higher_education": dual_edu(sync_edu),
            "further_training": dual_edu(sync_training)
        },
        "bildung":                 dual_edu(sync_edu),
        "weiterbildung":           dual_edu(sync_training),
        "language_skills":         sync_langs,
        "sprachen":                sync_langs,
        "zertifikate":             data.get("zertifikate", []),
        "faehigkeiten":            data.get("faehigkeiten", []),
        "technical_skills":        data.get("faehigkeiten", []),
    })

    # Final safety: Ensure no nulls hit docxtpl (can cause crash in some Jinja versions)
    for k, v in context.items():
        if v is None: context[k] = ""

    try:
        doc.render(context)
    except Exception as e:
        raise RuntimeError(
            f"Template Rendering Error: {str(e)}\n\n"
            "TIP: Check that every {% if %} has {% endif %} and "
            "every {% for %} has {% endfor %}. "
            'Use straight quotes (") not curly ones (\u201c\u201d).'
        )
    doc.save(output_path)
    return output_path

def diagnose_template(template_path_or_file) -> dict:
    """
    Safely loads a DOCX template and attempts to parse all Jinja variables.
    Returns: {"tags": [...], "error": str, "count": int}
    """
    try:
        doc = DocxTemplate(template_path_or_file)
        # Attempt to get undeclared variables (this parses the XML)
        tags = doc.get_undeclared_template_variables()
        return {
            "tags": sorted(list(tags)),
            "count": len(tags),
            "error": None
        }
    except Exception as e:
        return {
            "tags": [],
            "count": 0,
            "error": str(e)
        }
