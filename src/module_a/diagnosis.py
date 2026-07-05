import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # pour importer src/llm
from llm.client import ask_claude

def diagnose_ecart(region: str, produit: str, valeur_qlik: float, valeur_pbi: float, ecart_relatif: float) -> str:
    """Demande au LLM une hypothèse de cause probable pour un écart détecté."""
    prompt = f"""Un écart de données a été détecté après migration Qlik Sense -> Power BI.

Dimension : Region={region}, Produit={produit}
Valeur Qlik : {valeur_qlik}
Valeur Power BI : {valeur_pbi}
Écart relatif : {ecart_relatif:.2%}

Propose en 2-3 phrases une hypothèse de cause probable (ex: filtre de contexte mal traduit,
agrégation différente, gestion des NULL) et une suggestion de vérification pour le consultant."""

    return ask_claude(prompt)

if __name__ == "__main__":
    diagnostic = diagnose_ecart(
        region="Sud",
        produit="ProduitA",
        valeur_qlik=12300,
        valeur_pbi=11800,
        ecart_relatif=0.04065
    )
    print(diagnostic)