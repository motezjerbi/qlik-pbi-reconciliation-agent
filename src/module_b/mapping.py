import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm.client import ask_claude


def map_pattern_to_dax(pattern: dict, dax_measures_text: str) -> dict:
    """
    Demande au LLM si un pattern Qlik détecté a un équivalent
    parmi les mesures DAX disponibles (format ligne par ligne,
    plus fiable qu'un JSON pour un petit modèle local comme Mistral).
    """
    prompt = f"""Tu es un expert en migration Qlik Sense vers Power BI. Sois strict et critique, ne dis pas "couvert" par défaut.

PATTERN QLIK DÉTECTÉ :
Type : {pattern['pattern']}
Expression : {pattern['expression_source']}

MESURES DAX DISPONIBLES CÔTÉ POWER BI :
{dax_measures_text}

Choisis UNE SEULE mesure DAX, la plus proche en intention (ou AUCUNE si rien ne correspond vraiment).
IMPORTANT : ne donne jamais plusieurs noms de mesures, un seul nom exact ou AUCUNE.

Réponds EXACTEMENT sur 3 lignes, sans rien d'autre, sans JSON, sans markdown :

STATUT: COUVERT ou PARTIELLEMENT_COUVERT ou NON_COUVERT
MESURE: un seul nom exact de la mesure choisie, ou AUCUNE
JUSTIFICATION: une seule phrase courte"""

    response = ask_claude(prompt)

    result = {
        "statut": "ERREUR_PARSING",
        "mesure_dax_correspondante": None,
        "justification": response.strip()
    }

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("STATUT:"):
            result["statut"] = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("MESURE:"):
            mesure = line.split(":", 1)[1].strip()
            # Garde-fou : si le modèle liste quand même plusieurs mesures (virgule détectée),
            # on ne garde que la première et on force PARTIELLEMENT_COUVERT
            # (signal que le modèle n'était pas sûr d'un choix unique)
            if "," in mesure:
                mesure = mesure.split(",")[0].strip()
                result["statut"] = "PARTIELLEMENT_COUVERT"
            result["mesure_dax_correspondante"] = None if mesure.upper() == "AUCUNE" else mesure
        elif line.upper().startswith("JUSTIFICATION:"):
            result["justification"] = line.split(":", 1)[1].strip()

    return {
        "pattern": pattern["pattern"],
        "expression_source": pattern["expression_source"],
        **result
    }


def map_all_patterns(patterns: list[dict], dax_measures_path: str) -> list[dict]:
    """Applique le mapping sur tous les patterns Qlik détectés."""
    dax_text = Path(dax_measures_path).read_text(encoding="utf-8")
    results = []

    for pattern in patterns:
        print(f"Analyse : {pattern['pattern']}...")
        result = map_pattern_to_dax(pattern, dax_text)
        results.append(result)

    return results


if __name__ == "__main__":
    from qlik_parser import parse_qlik_script

    patterns = parse_qlik_script("data/samples/case_encadrante_01/qlik/load_script.qvs")
    results = map_all_patterns(patterns, "data/samples/case_encadrante_01/powerbi/measures_dax.txt")

    print(f"\n{'='*60}")
    print(f"RÉSULTATS DU MAPPING ({len(results)} patterns analysés)")
    print(f"{'='*60}\n")

    for r in results:
        print(f"[{r['statut']}] {r['pattern']} → {r['expression_source']}")
        print(f"   Mesure DAX : {r.get('mesure_dax_correspondante')}")
        print(f"   Justification : {r.get('justification')}\n")