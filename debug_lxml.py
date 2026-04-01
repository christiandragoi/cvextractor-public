"""
Targeted XML repair using lxml - the definitive fix.
Find and repair fragmented Jinja tags in Word document XML.
"""
import re
import sys
sys.path.insert(0, '.')

from lxml import etree
import zipfile

TPL = r"C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster\Vorlage_Lebenslauf_Schweißer Python.docx"

# Load the raw XML
with zipfile.ZipFile(TPL) as z:
    raw = z.read('word/document.xml').decode('utf-8')

# Strip proofErr and noProof
raw_clean = re.sub(r'<w:proofErr[^/]*/>', '', raw)
raw_clean = re.sub(r'<w:noProof/>', '', raw_clean)

# Find all text run sequences and look for split Jinja tags across run boundaries
# by examining the text-only content of the document
text_only = re.sub(r'<[^>]+>', '', raw_clean)

# Find the broken tags
print("=== Text around 'endfor' in cleaned text ===")
for m in re.finditer(r'endfor', text_only):
    ctx = text_only[max(0, m.start()-80):m.end()+80]
    print(f"  ...{ctx}...")

print("\n=== All {%tr tags in cleaned text ===")
for m in re.finditer(r'\{%tr\s+\S+', text_only):
    ctx = text_only[m.start():min(len(text_only), m.end()+30)]
    print(f"  {ctx}")
