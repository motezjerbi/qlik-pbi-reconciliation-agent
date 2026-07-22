import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3] / "src"))
from orchestrator.merge import merge_findings
from orchestrator.prioritize import prioritize_all
from src.graph.state import AgentState


def node_orchestrator(state: AgentState) -> AgentState:
    """Nœud Orchestrateur : fusionne les résultats des deux modules et priorise."""
    ecarts_a = []

    for nom, result in state.get("all_comparisons", {}).items():
        for _, row in result[result["statut"] == "ECART_DETECTE"].iterrows():
            ecarts_a.append({
                "produit": f"{nom} — {row['__key__']}",
                "valeur_qlik": row["__value___qlik"],
                "valeur_pbi": row["__value___pbi"],
                "ecart_relatif": row["ecart_relatif"] * 100,
                "diagnostic": f"Écart détecté sur '{nom}'."
            })

    for nom in state.get("missing_pbi", []):
        ecarts_a.append({
            "produit": nom,
            "valeur_qlik": "présent",
            "valeur_pbi": "absent",
            "ecart_relatif": 100.0,
            "diagnostic": f"Visuel '{nom}' absent côté Power BI."
        })

    for cf in state.get("comparison_failures", []):
        ecarts_a.append({
            "produit": cf["visuel"],
            "valeur_qlik": "structure incompatible",
            "valeur_pbi": "structure incompatible",
            "ecart_relatif": 50.0,
            "diagnostic": f"Comparaison échouée — {cf['raison']}"
        })

    mapping_b = state.get("mapping_results", [])
    findings = merge_findings(ecarts_a, mapping_b)
    state["findings"] = prioritize_all(findings)

    return state