import os
import re
import json
import logging
from typing import Dict, Any

try:
    import httpx
except Exception:
    httpx = None

logger = logging.getLogger(__name__)

class AIClient:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.enabled = bool(self.api_key) and bool(httpx)

    async def extract_json(self, prompt: str, model: str = None, request_id: str = None) -> Dict[str, Any]:
        if not self.enabled:
            logger.info("AI client not configured (no OPENAI_API_KEY). Using demo extraction.")
            return self._demo_extraction(prompt)

        target_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a CV data extraction assistant. "
                        "Extract structured candidate data from the provided CV text. "
                        "Return ONLY valid JSON with this structure:\n"
                        "{\n"
                        '  "full_name": "...",\n'
                        '  "nationality": "...",\n'
                        '  "email": "...",\n'
                        '  "phone": "...",\n'
                        '  "date_of_birth": "...",\n'
                        '  "employment_history": [\n'
                        '    {"job_title": "...", "company": "...", "start_date": "...", "end_date": "..."}\n'
                        "  ],\n"
                        '  "skills": ["..."],\n'
                        '  "languages": ["..."]\n'
                        "}\n"
                        "Use null for missing fields. Do not include markdown formatting."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Clean up markdown fences
                content = content.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
                parsed = json.loads(content)
                return parsed
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}. Falling back to demo extraction.")
            return self._demo_extraction(prompt)

    def _demo_extraction(self, text: str) -> Dict[str, Any]:
        """Extract basic fields using heuristics when no AI key is available."""
        result = {
            "full_name": None,
            "nationality": None,
            "email": None,
            "phone": None,
            "date_of_birth": None,
            "employment_history": [],
            "skills": [],
            "languages": [],
        }
        # Strip prompt prefix if present — only look at actual CV text
        cv_text = text
        if "CV TEXT CONTENT:" in text:
            cv_text = text.split("CV TEXT CONTENT:", 1)[-1]
        lines = [ln.strip() for ln in cv_text.splitlines() if ln.strip()]
        text_lower = cv_text.lower()

        # Name extraction: first line that looks like a proper name
        skip_name_words = ["straße", "strasse", "str.", "tel", "phone", "email", "geboren",
                           "birth", "date of", "nationality", "nationalität", "staatsangehörigkeit",
                           "address", "adresse", "cv", "resume", "lebenslauf", "curriculum",
                           "content", "extract", "text", "instruction", "prompt"]
        for line in lines[:20]:
            words = line.split()
            if 2 <= len(words) <= 5 and all(w[0].isupper() for w in words if w):
                line_lower = line.lower()
                if "@" not in line and not any(sw in line_lower for sw in skip_name_words):
                    # Reject lines that are mostly numbers or special chars
                    alpha_chars = sum(1 for c in line if c.isalpha())
                    if alpha_chars > len(line) * 0.4:
                        result["full_name"] = line
                        break

        # Email
        email_match = re.search(r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}", cv_text)
        if email_match:
            result["email"] = email_match.group(0)

        # Phone
        phone_match = re.search(r"(?:tel\.?|telefon|phone|mobil|mobile)[:\s]*([+\d][\d\s\-\(\)\./]{6,25})", cv_text, re.IGNORECASE)
        if not phone_match:
            phone_match = re.search(r"([+\d][\d\s\-\(\)\./]{6,25})", cv_text)
        if phone_match:
            raw = phone_match.group(1).strip()
            # Basic sanity: must contain at least 7 digits
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 7:
                result["phone"] = raw

        # Date of birth
        dob_match = re.search(
            r"(?:geboren|born|geb\.|date of birth|birthdate|birth date|dob)[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})",
            cv_text, re.IGNORECASE
        )
        if dob_match:
            result["date_of_birth"] = dob_match.group(1)
        else:
            # Fallback: standalone date that looks like a birthdate (dd.mm.yyyy or mm/dd/yyyy with reasonable year)
            fallback_dob = re.search(r"(\d{1,2}[./\-]\d{1,2}[./\-](?:19|20)\d{2})", cv_text)
            if fallback_dob:
                result["date_of_birth"] = fallback_dob.group(1)

        # Nationality
        nat_match = re.search(
            r"(?:nationality|nationalität|staatsangehörigkeit|citizenship)[:\s]*([A-Za-zäöüßÄÖÜ\s]+?)(?=\n|\r|email|tel|phone|date|geboren|address|$)",
            cv_text, re.IGNORECASE
        )
        if nat_match:
            result["nationality"] = nat_match.group(1).strip()

        # Employment history
        emp_entries = []
        for line in lines:
            date_match = re.search(
                r"(\d{1,2}[./]\d{4}|\d{4})\s*[-–]\s*(\d{1,2}[./]\d{4}|\d{4}|heute|present|now|current|today)",
                line, re.IGNORECASE
            )
            if date_match:
                prefix = line[:date_match.start()].strip()
                # Clean common separators
                prefix = re.sub(r"[|•\-–]", " ", prefix).strip()
                emp_entries.append({
                    "start_date": date_match.group(1),
                    "end_date": date_match.group(2),
                    "job_title": prefix or "Position",
                    "company": "",
                })
        result["employment_history"] = emp_entries[:10]

        # Skills
        skill_keywords = [
            "Python", "Java", "JavaScript", "TypeScript", "SQL", "Excel", "Word", "PowerPoint",
            "Project Management", "Leadership", "Communication", "Sales", "Marketing", "Design",
            "Photoshop", "Illustrator", "AutoCAD", "SolidWorks", "CATIA",
            "Schweißen", "MAG", "WIG", "Schweißer", "Schlosser", "Mechatroniker",
            "Elektriker", "Ingenieur", "Manager", "Consultant", "Developer", "Engineer",
            "AWS", "Azure", "Docker", "Kubernetes", "React", "Vue", "Angular", "Node.js",
            "C++", "C#", "Go", "Rust", "PHP", "Ruby", "Swift", "Kotlin",
            "Scrum", "Agile", "Kanban", "ITIL", "PMP",
        ]
        found_skills = []
        for skill in skill_keywords:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        result["skills"] = found_skills[:15]

        # Languages
        lang_keywords = [
            "Deutsch", "German", "Englisch", "English", "Französisch", "French",
            "Spanisch", "Spanish", "Italienisch", "Italian", "Polnisch", "Polish",
            "Russisch", "Russian", "Türkisch", "Turkish", "Arabisch", "Arabic",
            "Chinesisch", "Chinese", "Japanisch", "Japanese", "Holländisch", "Dutch",
            "Portugiesisch", "Portuguese", "Koreanisch", "Korean", "Hindi", "Griechisch", "Greek",
        ]
        found_langs = []
        for lang in lang_keywords:
            if lang.lower() in text_lower:
                found_langs.append(lang)
        result["languages"] = found_langs[:10]

        # Final name fallback
        if not result["full_name"]:
            for line in lines[:10]:
                if line and len(line) > 3 and len(line) < 60 and " " in line:
                    alpha = sum(1 for c in line if c.isalpha())
                    if alpha > len(line) * 0.4 and "@" not in line:
                        result["full_name"] = line
                        break

        return result

ai_client = AIClient()
