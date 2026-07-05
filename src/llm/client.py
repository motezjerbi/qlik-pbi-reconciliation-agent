import os
from dotenv import load_dotenv

load_dotenv()

FORCE_MOCK = os.getenv("FORCE_MOCK", "false").lower() == "true"
HAS_KEY = os.getenv("ANTHROPIC_API_KEY") is not None
USE_MOCK = FORCE_MOCK or not HAS_KEY

if not USE_MOCK:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def ask_claude(prompt: str, max_tokens: int = 500) -> str:
    if USE_MOCK:
        print("[MOCK] Mode simulation actif — réponse simulée.")
        return "[Réponse simulée : ici viendra le diagnostic réel de Claude]"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"[ERREUR API] {e}\n→ Basculement automatique en mode simulé.")
        return "[Réponse simulée suite à une erreur API : ici viendra le diagnostic réel de Claude]"

if __name__ == "__main__":
    print(ask_claude("Réponds juste 'OK' si tu me reçois."))