# src/llm/client.py
"""
Client LLM (Ollama / Mistral en local) pour le mapping sémantique Module B.

Important : en cas d'échec de connexion à Ollama, on renvoie une erreur
EXPLICITE (statut ERREUR_PARSING), jamais une réponse "intelligente" simulée.
Une évaluation d'agent (onglet Agent Evaluation) qui mesurerait en réalité
des règles codées en dur plutôt qu'un vrai LLM n'aurait aucune valeur.
"""

import requests
import time
from typing import Optional


class LLMClient:
    def __init__(self, model: str = "mistral", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._connected = False
        self._connection_error: Optional[str] = None
        self._model_available = False
        self._check_connection()

    def _check_connection(self) -> bool:
        """Vérifie qu'Ollama tourne ET que le modèle demandé est bien installé."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code != 200:
                self._connected = False
                self._connection_error = f"Ollama a répondu avec le code {response.status_code}"
                return False

            self._connected = True
            self._connection_error = None

            models = [m.get("name", "") for m in response.json().get("models", [])]
            # Le tag Ollama peut être "mistral:latest" ; on tolère les deux formes.
            self._model_available = any(
                m == self.model or m.startswith(f"{self.model}:") for m in models
            )
            if not self._model_available:
                self._connection_error = (
                    f"Modèle '{self.model}' non installé dans Ollama. "
                    f"Modèles disponibles : {models or 'aucun'}. "
                    f"Lance : ollama pull {self.model}"
                )
            else:
                print(f"✅ Ollama connecté, modèle '{self.model}' disponible")
            return self._model_available

        except requests.exceptions.RequestException as e:
            self._connected = False
            self._connection_error = f"Ollama non accessible sur {self.base_url} ({e})"
            return False

    def _ensure_connection(self) -> bool:
        if self._connected and self._model_available:
            return True
        return self._check_connection()

    def ask(self, prompt: str, timeout: int = 90, num_predict: int = 300) -> str:
        """Envoie une requête à Ollama. Retourne une erreur explicite si ça échoue,
        jamais une réponse simulée.

        `timeout` et `num_predict` sont réglables par appel : le mapping Module B
        (réponses courtes à 3 lignes) reste sur les valeurs par défaut historiques,
        mais un appelant qui demande une génération plus longue (ex. génération de
        correctif DAX) peut passer un timeout plus élevé sans changer le comportement
        des autres appels.
        """
        if not self._ensure_connection():
            return self._error_response(self._connection_error or "Ollama indisponible")

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": num_predict,
                        "temperature": 0.2,
                        "top_p": 0.9,
                    },
                },
                timeout=timeout,  # l'inférence locale peut être lente selon le CPU/GPU
            )

            if response.status_code != 200:
                return self._error_response(
                    f"Ollama a répondu avec le code {response.status_code}"
                )

            result = response.json().get("response", "").strip()
            if len(result) < 5:
                return self._error_response("Réponse vide ou trop courte du modèle")

            return result

        except requests.exceptions.Timeout:
            return self._error_response(f"Timeout Ollama (>{timeout}s) - le modèle est peut-être surchargé")
        except requests.exceptions.RequestException as e:
            return self._error_response(f"Erreur de connexion Ollama : {e}")

    def _error_response(self, reason: str) -> str:
        """Format compatible avec le parsing STATUT/MESURE/JUSTIFICATION de mapping.py —
        l'échec remonte comme ERREUR_PARSING, pas comme un faux résultat plausible."""
        return f"STATUT: ERREUR_PARSING\nMESURE: AUCUNE\nJUSTIFICATION: {reason}"


# Instance globale (réutilisée entre les appels pour éviter de reconnecter à chaque fois)
llm_client = LLMClient()


def ask_claude(prompt: str, timeout: int = 90, num_predict: int = 300) -> str:
    """Interface compatible avec le code existant (module_b/mapping.py).
    Le nom est historique ; le backend réel est Ollama/Mistral en local.

    timeout / num_predict : optionnels, valeurs par défaut identiques au
    comportement historique. Un appelant peut les augmenter pour une tâche
    de génération plus longue (ex. dax_fix_generator.py)."""
    return llm_client.ask(prompt, timeout=timeout, num_predict=num_predict)


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Test du client LLM (Ollama / Mistral)")
    print("=" * 60)

    # Prompt au format réellement utilisé par module_b/mapping.py (3 lignes attendues)
    test_prompt = """Tu es un expert en migration Qlik Sense vers Power BI.

Pattern Qlik : set_analysis
Expression : {<Year={$(vCurrentYear)}>}

Mesures DAX disponibles :
- Current Year Sales
- Total Sales

Réponds EXACTEMENT sur 3 lignes :
STATUT: [COUVERT / PARTIELLEMENT_COUVERT / NON_COUVERT]
MESURE: [nom exact ou AUCUNE]
JUSTIFICATION: [explication courte]
"""

    print("\n--- Réponse du modèle ---")
    print(ask_claude(test_prompt))