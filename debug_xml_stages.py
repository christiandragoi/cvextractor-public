"""
Minimal direct test to confirm our monkey-patch actually fires and to see the
exact XML state AFTER patching, right before rendering.
"""
import re, sys, os, tempfile
sys.path.insert(0, os.getcwd())

import populator
from docxtpl import DocxTemplate

TPL = r"C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster\Vorlage_Lebenslauf_Schweißer Python.docx"

doc = DocxTemplate(TPL)
doc.init_docx()

# Raw xml
raw_xml = doc.get_xml()
print(f"Raw XML length: {len(raw_xml)}")

# Check what the raw XML endfor tags look like
text_only = re.sub(r'<[^>]+>', '', raw_xml)
for_count    = len(re.findall(r'\{%-?\s*(?:tr\s+|tc\s+|p\s+)?for\s', text_only))
endfor_count = len(re.findall(r'\{%-?\s*endfor\s*-?%\}', text_only))
if_count    = len(re.findall(r'\{%-?\s*if\s', text_only))
endif_count = len(re.findall(r'\{%-?\s*endif\s*-?%\}', text_only))

print(f"\n=== RAW XML TAG COUNTS ===")
print(f"  for: {for_count}, endfor: {endfor_count}")
print(f"  if: {if_count}, endif: {endif_count}")

# After patch_xml
patched = doc.patch_xml(raw_xml)
text_only_p = re.sub(r'<[^>]+>', '', patched)
for_count_p    = len(re.findall(r'\{%-?\s*(?:tr\s+|tc\s+|p\s+)?for\s', text_only_p))
endfor_count_p = len(re.findall(r'\{%-?\s*endfor\s*-?%\}', text_only_p))

print(f"\n=== AFTER patch_xml TAG COUNTS ===")
print(f"  for: {for_count_p}, endfor: {endfor_count_p}")

# Find what endfor looks like in raw text
print("\n=== endfor occurrences in patched text ===")
for m in re.finditer(r'\{%-?\s*endfor\s*-?%\}', text_only_p):
    start = max(0, m.start() - 60)
    end = min(len(text_only_p), m.end() + 60)
    print(f"  [{start}:{end}]: ...{text_only_p[start:end]}...")

# After our fix
fixed = populator._fix_jinja_xml(patched)
text_only_f = re.sub(r'<[^>]+>', '', fixed)
for_count_f    = len(re.findall(r'\{%-?\s*(?:tr\s+|tc\s+|p\s+)?for\s', text_only_f))
endfor_count_f = len(re.findall(r'\{%-?\s*endfor\s*-?%\}', text_only_f))

print(f"\n=== AFTER _fix_jinja_xml TAG COUNTS ===")
print(f"  for: {for_count_f}, endfor: {endfor_count_f}")
