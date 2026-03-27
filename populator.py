"""
populator.py
Renders a DOCX template using docxtpl (Jinja2 engine for Word).

Problem fix: Word randomly splits {{ tag }} tokens across XML runs like:
  <r>{{</r><r>name</r><r>}}</r>
docxtpl has a built-in fix via DocxTemplate which handles this,
but we additionally pre-process the XML to merge fragmented tags.
"""

import re
from docxtpl import DocxTemplate
from lxml import etree


# ── Quote Normalizer ──────────────────────────────────────────────────────────

def _normalize_template_quotes(doc: DocxTemplate) -> None:
    """
    Replace curly quotes (“ ” ‘ ’) with straight quotes (" ') in every 
    paragraph and table cell. This ensures that Jinja2 tags like 
    {% if x == "val" %} work even if Word autocorrected the quotes.
    """
    if doc.docx is None:
        return

    # Helper to replace in a string
    def _sub(text):
        if not text: return text
        t = text.replace('“', '"').replace('”', '"').replace('„', '"')
        t = t.replace('‘', "'").replace('’', "'").replace('‚', "'")
        return t

    # 1. Body paragraphs
    for p in doc.docx.paragraphs:
        for r in p.runs:
            if r.text:
                r.text = _sub(r.text)
    
    # 2. Tables
    for table in doc.docx.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        if r.text:
                            r.text = _sub(r.text)


# ── Word XML run-fixer ────────────────────────────────────────────────────────

def _fix_xml_runs(doc: DocxTemplate) -> None:
    """
    Merge fragmented Jinja2 tags split across multiple Word XML runs.
    Word often breaks {{ variable }} into separate <w:r> elements which
    prevents docxtpl from recognising the tags.
    This walks every paragraph and table cell, concatenates adjacent run
    texts, then writes the merged text back into a single run.

    Gracefully skips if the internal Document object is not available.
    """
    try:
        # Guard: doc.docx may be None if init_docx() hasn't been called
        # or if the template couldn't be parsed as a python-docx Document.
        if doc.docx is None:
            try:
                doc.init_docx()
            except Exception:
                return  # Cannot initialise — skip fixing runs
        if doc.docx is None:
            return

        body = getattr(doc.docx, 'element', None)
        if body is None:
            return
        body = getattr(body, 'body', None)
        if body is None:
            return

        NSMAP = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        W = f"{{{NSMAP}}}"

        def _merge_paragraph_runs(para_elem):
            runs = para_elem.findall(f"{W}r")
            if not runs:
                return
            # Collect all text in order
            full_text = ""
            for r in runs:
                t = r.find(f"{W}t")
                if t is not None and t.text:
                    full_text += t.text

            # Only touch paragraphs that contain Jinja2 syntax
            if "{{" not in full_text and "{%" not in full_text:
                return

            # Remove all existing runs
            for r in runs:
                para_elem.remove(r)

            # Re-insert a single run carrying the full merged text
            new_r = etree.SubElement(para_elem, f"{W}r")
            new_t = etree.SubElement(new_r, f"{W}t")
            new_t.text = full_text
            if full_text.startswith(" ") or full_text.endswith(" "):
                new_t.set(
                    "{http://www.w3.org/XML/1998/namespace}space", "preserve"
                )

        # Paragraphs at body level
        for para in body.iter(f"{W}p"):
            _merge_paragraph_runs(para)

    except Exception:
        # If anything goes wrong in run-fixing, skip silently.
        # docxtpl can still render without this pre-processing step.
        pass


# ── Job-type mapping ──────────────────────────────────────────────────────────

JOB_TYPE_MAP = {
    "Schweißer":               "Schweißer",
    "Schlosser":               "Schweißer",
    "Mechaniker":              "Schweißer",
    "Lackierer":               "Schweißer",
    "Klempner":                "Schweißer",
    "Maurer":                  "Schweißer",
    "Zimmermann":              "Schweißer",
    "Tischler":                "Schweißer",
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
            "years":       _safe(e.get("years"), ""),
            "institution": _safe(e.get("institution"), ""),
            "field":       _safe(e.get("field"), ""),
        }
        for e in (lst or [])
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def populate_template(template_path: str, output_path: str, data: dict) -> str:
    """
    Render template_path with data dict and save to output_path.
    Supports both Jinja2-style docxtpl templates and plain search-replace fallback.
    """
    doc = DocxTemplate(template_path)

    # Initialize the docx.Document object so doc.docx is populated
    doc.init_docx()

    # Normalize curly quotes in the template XML to straight quotes.
    _normalize_template_quotes(doc)

    # Fix Word's run-fragmentation BEFORE rendering
    _fix_xml_runs(doc)

    job_role = _safe(data.get("job_role"), "Schweißer")
    job_type = JOB_TYPE_MAP.get(job_role, job_role)

    # Employment history
    raw_jobs = data.get("employment_history", [])
    employment_history = []
    for j in raw_jobs:
        duties = j.get("duties", [])
        if isinstance(duties, str):
            duties = [d.strip() for d in duties.split(",") if d.strip()]
        employment_history.append({
            "employer":   _safe(j.get("employer"),   "N/A"),
            "position":   _safe(j.get("position"),   job_role),
            "duties":     duties,
            "start_date": _safe(j.get("start_date"), ""),
            "end_date":   _safe(j.get("end_date"),   ""),
        })

    # Education
    edu_raw = data.get("education", {})
    if isinstance(edu_raw, str):
        edu_raw = {}
    education = {
        "higher_education": _fmt_edu(edu_raw.get("higher_education", [])),
        "further_training": _fmt_edu(edu_raw.get("further_training",  [])),
    }

    # Language skills
    language_skills = [
        {
            "language": _safe(l.get("language"), ""),
            "level":    _safe(l.get("level"),    ""),
        }
        for l in data.get("language_skills", [])
    ]

    context = {
        "name":                    _safe(data.get("name"),                   ""),
        "birth_date":              _safe(data.get("birth_date"),              ""),
        "nationality":             _safe(data.get("nationality"),             ""),
        "id_expiry":               _safe(data.get("id_expiry"),               ""),
        "residence_permit_expiry": _safe(data.get("residence_permit_expiry"), ""),
        "job_role":                job_role,
        "job_type":                job_type,
        "employment_history":      employment_history,
        "education":               education,
        "language_skills":         language_skills,
        "profile_summary":         _safe(data.get("profile_summary"),         ""),
    }

    doc.render(context)
    doc.save(output_path)
    return output_path
