import zipfile, re

path = r"C:\Users\Cris\AppData\Local\Temp\Lebenslauf_Voicu_Schweißer.docx"
with zipfile.ZipFile(path) as z:
    xml = z.read("word/document.xml").decode("utf-8")
text = re.sub(r"<[^>]+>", "|", xml)
text = re.sub(r"\|+", " | ", text)

# Find education-related sections
for keyword in ["Bildung", "education", "Berufsschule", "higher_education", "Metall", "Ausbildung", "Schule"]:
    idx = text.lower().find(keyword.lower())
    if idx >= 0:
        print(f'--- Found "{keyword}" at pos {idx} ---')
        print(text[max(0,idx-100):idx+200])
        print()

if "Beruferfahrung" in text:
    idx = text.find("Beruferfahrung")
    # Show what's BEFORE Beruferfahrung (should be education)
    print("--- 300 chars BEFORE Beruferfahrung ---")
    print(text[max(0,idx-400):idx])
