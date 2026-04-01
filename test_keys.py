import json
import sys
from pathlib import Path

# Add current dir to sys.path to import extractor
sys.path.append(str(Path(__file__).parent))

from extractor import validate_key

def test_all_keys():
    settings_path = Path(__file__).parent / ".settings.json"
    if not settings_path.exists():
        print("❌ .settings.json not found")
        return

    with open(settings_path, "r") as f:
        settings = json.load(f)

    providers = [
        "OpenAI", "Gemini", "Anthropic", "DeepSeek", "Grok (xAI)", 
        "Kimi K2", "Perplexity", "TogetherAI", "Groq", "OpenRouter", "Xiaomi MiMo"
    ]
    
    key_map = {
        "OpenAI": "openai_api_key",
        "Gemini": "gemini_api_key",
        "Anthropic": "anthropic_api_key",
        "DeepSeek": "deepseek_api_key",
        "Grok (xAI)": "grok_api_key",
        "Kimi K2": "kimi_api_key",
        "Perplexity": "perplexity_api_key",
        "TogetherAI": "togetherai_api_key",
        "Groq": "groq_api_key",
        "OpenRouter": "openrouter_api_key",
        "Xiaomi MiMo": "xiaomi_api_key"
    }

    print("\n=== AI Key Health Report ===\n")
    for p in providers:
        key_name = key_map.get(p)
        key = settings.get(key_name)
        if not key:
            print(f"{p:12}: ⚪ Missing")
            continue
        
        # Simple mask for printing
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "****"
        print(f"{p:12}: Testing {masked} ... ", end="", flush=True)
        
        success, msg = validate_key(p, key)
        if success:
            print(msg)
        else:
            print(msg)

if __name__ == "__main__":
    test_all_keys()
