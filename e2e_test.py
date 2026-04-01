"""
End-to-end test: verify that populator.py correctly fills the education block
using the REAL template and realistic AI data.
"""
import sys, os, zipfile, re, json
sys.path.insert(0, os.path.dirname(__file__))
from populator import populate_template
import tempfile

# The user's REAL template
TPL = os.path.join(os.path.dirname(__file__), "templates", "Vorlage_Lebenslauf_Schweißer_Python.docx")

# Realistic AI data (what OpenAI returns)
data = {
    "vorname": "Florian",
    "nachname": "Voicu",
    "geburtsdatum": "31.07.1968",
    "geburtsort": "Iława, Polen",
    "staatsangehoerigkeit": "Polnisch",
    "job_role": "Schweißer",
    "zusammenfassung": "Herr Voicu verfügt über mehr als 30 Jahre Berufserfahrung...",
    "berufserfahrung": [
        {
            "von": "02/2020",
            "bis": "present",
            "arbeitgeber": "PRIVATE COMPANY, Polen",
            "position": "Schweißer",
            "taetigkeiten": "Schweißen mit 111, 135, 136 und 141 an Kohlenstoffstahl und Edelstahl"
        }
    ],
    "bildung": [
        {
            "jahre": "1983-1988",
            "einrichtung": "Zespół Szkół Zawodowych w Iławie, Polen",
            "abschluss": "Berufsausbildung Metallbearbeitung / Schweißtechnik"
        }
    ],
    "weiterbildung": [
        {
            "jahre": "2015",
            "anbieter": "TÜV Süd",
            "kurs": "ISO 9606-1 Schweißerprüfung 135, 141"
        }
    ],
    "sprachen": [
        {"sprache": "Polnisch", "niveau": "Muttersprache"},
        {"sprache": "Deutsch", "niveau": "B1-B2"}
    ],
    "faehigkeiten": [],
    "zertifikate": []
}

out = os.path.join(tempfile.gettempdir(), "E2E_TEST_Lebenslauf.docx")
print(f"Template: {TPL}")
print(f"Output:   {out}")
print(f"bildung in data: {data['bildung']}")
print()

try:
    result = populate_template(TPL, out, data)
    print(f"SUCCESS! Generated: {result}")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Now read the debug file
dbg = os.path.join(tempfile.gettempdir(), "cvextractor_last_data.json")
if os.path.exists(dbg):
    with open(dbg) as f:
        print(f"\nDEBUG DATA:\n{f.read()}")

# Now verify the output document contains education data
print("\n=== DOCUMENT CONTENT VERIFICATION ===")
with zipfile.ZipFile(out) as z:
    xml = z.read("word/document.xml").decode("utf-8")
text = re.sub(r"<[^>]+>", "|", xml)
text = re.sub(r"\|+", " | ", text)

# Check for education data in the rendered document
checks = [
    ("Bildung / Schule", "1983"),
    ("Bildung / Schule", "Iław"),  
    ("Bildung / Schule", "Metallbearbeitung"),
    ("Weiterbildung", "TÜV"),
    ("Weiterbildung", "9606"),
    ("Berufserfahrung", "PRIVATE COMPANY"),
    ("Sprachen", "Polnisch"),
]

all_passed = True
for section, keyword in checks:
    found = keyword.lower() in text.lower()
    status = "✅" if found else "❌"
    print(f"  {status} {section}: '{keyword}' {'found' if found else 'NOT FOUND'}")
    if not found:
        all_passed = False

if all_passed:
    print("\n🎉 ALL CHECKS PASSED! Education block is correctly filled!")
else:
    print("\n⚠️ SOME CHECKS FAILED - education may still be missing")
    # Dump 300 chars around "Beruferfahrung" to see what's nearby
    idx = text.find("Beruferfahrung")
    if idx > 0:
        print(f"\n--- Context around 'Beruferfahrung' ---")
        print(text[max(0,idx-300):idx])
