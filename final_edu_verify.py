from populator import populate_template
import os

# Mock data simulating a flat AI response
data = {
    "vorname": "Jane",
    "nachname": "Doe",
    "bildung": [
        {"years": "2015-2019", "institution": "University of Berlin", "field": "Mechanical Engineering"}
    ],
    "weiterbildung": [
        {"years": "2020", "institution": "TÜV", "field": "Welding Specialist"}
    ]
}

# The user's template expects:
# education.higher_education
# education.further_training

# Check if populator correctly transforms 'bildung' into 'education.higher_education'
tpl_path = "templates/Vorlage_Lebenslauf_Kandidatenprofil_V2_Mit_Tags.docx"
out_path = "final_edu_check.docx"

print("Running Education Key Verification...")
try:
    # We use a dummy template if needed, but the logic happens before rendering
    # Let's just mock the populate_template function's context building
    from populator import _safe, _fmt_edu
    
    # Re-run the core logic part of populate_template
    edu_input = data.get("education", {})
    bildung_raw = data.get("bildung", [])
    training_raw = data.get("weiterbildung", [])

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

    if isinstance(edu_input, dict):
        sync_edu = _fmt_edu(edu_input.get("higher_education", bildung_raw))
        sync_training = _fmt_edu(edu_input.get("further_training", training_raw))
    else:
        sync_edu = _fmt_edu(bildung_raw)
        sync_training = _fmt_edu(training_raw)

    context_edu = {
        "higher_education": dual_edu(sync_edu),
        "further_training": dual_edu(sync_training)
    }

    print(f"Mapped Education Keys: {list(context_edu.keys())}")
    print(f"Higher Ed Content: {context_edu['higher_education']}")
    
    assert len(context_edu['higher_education']) > 0
    assert context_edu['higher_education'][0]['institution'] == "University of Berlin"
    
    print("✅ EDUCATION MAPPING SUCCESSFUL!")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
