import re
import os
import sys
from docxtpl import DocxTemplate

# Add current path to sys.path to import populator
sys.path.append(os.getcwd())
import populator

template_path = r"C:\Users\Cris\Desktop\AP Workers\AP Mitarbeiter 2026\Vorlage_Lebenslauf Muster\Vorlage_Lebenslauf_Schweißer Python.docx"

try:
    doc = DocxTemplate(template_path)
    xml = doc.get_xml()
    
    print("\n--- RAW XML AROUND ENDFOR ---")
    for m in re.finditer(r'\{%\s*.*?(?:endfor).*?%\}', xml, re.DOTALL):
        print(f"MATCH: {xml[m.start():m.end()]}")
    
    # 1. docxtpl patch
    patched_xml = doc.patch_xml(xml)
    
    # 2. our fix
    fixed_xml = populator._fix_jinja_xml(patched_xml)
    
    print("\n--- FIXED XML AROUND ENDFOR ---")
    # Let's find tags that have 'endfor' in them
    for m in re.finditer(r'\{%\s*.*?(?:endfor).*?%\}', fixed_xml, re.DOTALL):
        print(f"MATCH: {fixed_xml[m.start():m.end()]}")
        
except Exception as e:
    print(f"Error: {e}")
