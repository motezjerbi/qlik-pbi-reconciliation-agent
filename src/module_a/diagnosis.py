import sys
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
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


def diagnose_all_ecarts(comparison_result: pd.DataFrame) -> list[dict]:
    """
    Parcourt le résultat de comparison.py et génère un diagnostic
    pour chaque ligne marquée ECART_DETECTE.
    Retourne une liste de dictionnaires structurés (sortie finale du Module A).
    """
    ecarts = comparison_result[comparison_result["statut"] == "ECART_DETECTE"]
    resultats = []

    for _, row in ecarts.iterrows():
        diagnostic = diagnose_ecart(
            region=row["Region"],
            produit=row["Produit"],
            valeur_qlik=row["Ventes_qlik"],
            valeur_pbi=row["Ventes_pbi"],
            ecart_relatif=row["ecart_relatif"]
        )

        resultats.append({
            "region": row["Region"],
            "produit": row["Produit"],
            "valeur_qlik": row["Ventes_qlik"],
            "valeur_pbi": row["Ventes_pbi"],
            "ecart_absolu": row["ecart_absolu"],
            "ecart_relatif": row["ecart_relatif"],
            "diagnostic": diagnostic
        })

    return resultats


if __name__ == "__main__":
    from ingestion import load_export
    from comparison import compare_exports

    qlik_df = load_export("data/samples/case_01_test/qlik/data_export.csv")
    pbi_df = load_export("data/samples/case_01_test/powerbi/data_export.csv")

    result = compare_exports(qlik_df, pbi_df, key_cols=["Region", "Produit"], value_col="Ventes")

    diagnostics = diagnose_all_ecarts(result)

    print(f"{len(diagnostics)} diagnostic(s) généré(s) :\n")
    for d in diagnostics:
        print(f"- {d['region']} / {d['produit']} : écart de {d['ecart_relatif']:.2%}")
        print(f"  → {d['diagnostic']}\n")