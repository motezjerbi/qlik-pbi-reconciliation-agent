from langchain_ollama import ChatOllama

# Remplacez "mistral" par le nom exact du modèle que vous avez téléchargé (ollama list)
llm = ChatOllama(model="mistral", temperature=0)

def ask_claude(prompt: str) -> str:
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print(f"[ERREUR OLLAMA] {e}")
        return "[Erreur : impossible de contacter Ollama — vérifiez qu'il tourne bien en arrière-plan]"

if __name__ == "__main__":
    print(ask_claude("Réponds juste 'OK' si tu me reçois."))