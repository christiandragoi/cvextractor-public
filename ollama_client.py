import aiohttp
import json
from typing import AsyncGenerator, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL  # http://localhost:11434
        self.model = settings.OLLAMA_MODEL        # qwen2.5:14b or llama3.1:8b
        
    async def extract_cv_data(
        self, 
        text_content: str,
        progress_callback: Optional[callable] = None
    ) -> dict:
        """
        Extract structured CV data with confidence scores.
        Returns JSON with data and confidence levels.
        """
        
        system_prompt = """Du bist ein präziser CV-Parser für deutsche Personalagenturen. 
Extrahiere Informationen aus dem Lebenslauf und gib sie als JSON aus.
WICHTIG: Für jedes Feld gib auch einen Konfidenz-Score (0.0-1.0) an, wie sicher du bist.
Bei Unsicherheit (z.B. unklare Berufsbezeichnung oder handschriftliche Notizen), nutze niedrige Scores.

Ausgabeformat:
{
  "data": {
    "full_name": "Max Mustermann",
    "email": "max@example.com",
    ...
  },
  "confidence": {
    "full_name": 0.95,
    "email": 0.88,
    ...
  },
  "warnings": ["Berufsbezeichnung mehrdeutig: 'Entwickler' vs 'Programmierer'"]
}"""

        user_prompt = f"""Analysiere diesen Lebenslauf-Text und extrahiere strukturierte Daten:

{text_content[:8000]}  # Truncate very long CVs

Gib NUR das JSON zurück, keine Erklärungen."""

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "format": "json",  # Force JSON mode if Ollama supports it
                    "options": {
                        "temperature": 0.1,  # Low temp for deterministic extraction
                        "num_ctx": 8192
                    }
                }
                
                if progress_callback:
                    await progress_callback("contacting_ollama")
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # 2 min timeout
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Ollama error: {response.status}")
                    
                    result = await response.json()
                    response_text = result.get("response", "{}")
                    
                    if progress_callback:
                        await progress_callback("parsing_response")
                    
                    # Parse the JSON response
                    parsed = json.loads(response_text)
                    
                    return {
                        "data": parsed.get("data", {}),
                        "confidence": parsed.get("confidence", {}),
                        "warnings": parsed.get("warnings", []),
                        "raw_response": response_text
                    }
                    
        except Exception as e:
            logger.error(f"Ollama extraction failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Verify Ollama is running and model is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return self.model in models
                    return False
        except:
            return False

    def calculate_overall_confidence(self, confidence_dict: dict) -> float:
        """Calculate average confidence across all fields"""
        if not confidence_dict:
            return 0.0
        scores = [v for v in confidence_dict.values() if isinstance(v, (int, float))]
        return sum(scores) / len(scores) if scores else 0.0
