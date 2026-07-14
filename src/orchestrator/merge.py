def merge_findings(ecarts_module_a: list[dict], mapping_module_b: list[dict]) -> list[dict]:
    """
    Fusionne les résultats du Module A (écarts de données) et du Module B (couverture fonctionnelle)
    en une liste unique de findings structurés, prête pour la priorisation et le rapport final.
    """
    findings = []

    for e in ecarts_module_a:
        findings.append({
            "source_module": "Module A - Réconciliation de données",
            "type": "ECART_DONNEES",
            "libelle": f"{e.get('produit', e.get('region', 'N/A'))}",
            "detail": f"Valeur Qlik: {e.get('valeur_qlik')} vs Power BI: {e.get('valeur_pbi')} (écart {e.get('ecart_relatif', 0):.2%})",
            "diagnostic": e.get("diagnostic", ""),
            "criticite": None  # à définir dans prioritize.py
        })

    for m in mapping_module_b:
        if m["statut"] != "COUVERT":
            findings.append({
                "source_module": "Module B - Audit de couverture fonctionnelle",
                "type": f"LACUNE_{m['statut']}",
                "libelle": f"{m['pattern']} ({m['expression_source']})",
                "detail": f"Mesure DAX correspondante : {m.get('mesure_dax_correspondante') or 'aucune trouvée'}",
                "diagnostic": m.get("justification", ""),
                "criticite": None
            })

    return findings


if __name__ == "__main__":
    # Test avec des exemples représentatifs
    fake_ecarts = [
        {"produit": "Laptop", "valeur_qlik": 116.67, "valeur_pbi": 11666.67, "ecart_relatif": 99.0, "diagnostic": "Format d'affichage incorrect (%) probable."}
    ]
    fake_mapping = [
        {"pattern": "left_join", "expression_source": "left join(", "statut": "PARTIELLEMENT_COUVERT", "mesure_dax_correspondante": None, "justification": "Aucune relation DAX équivalente identifiée clairement."}
    ]

    result = merge_findings(fake_ecarts, fake_mapping)
    for f in result:
        print(f)