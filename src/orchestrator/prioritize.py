def prioritize_finding(finding: dict) -> str:
    """
    Attribue une criticité (BLOQUANT / MAJEUR / MINEUR) à un finding,
    selon des règles simples basées sur son type et son contenu.
    """
    type_ = finding["type"]
    libelle = finding["libelle"].lower()

    # Règles spécifiques à la sécurité et à l'intégrité des données -> toujours bloquant
    if "section_access" in libelle or "security" in libelle:
        return "BLOQUANT"

    # Écarts de données : criticité selon l'ampleur de l'écart
    if type_ == "ECART_DONNEES":
        detail = finding.get("detail", "")
        try:
            ecart_str = detail.split("écart ")[1].split("%")[0]
            ecart_val = float(ecart_str)
        except (IndexError, ValueError):
            ecart_val = 0

        if ecart_val > 50:
            return "BLOQUANT"
        elif ecart_val > 5:
            return "MAJEUR"
        else:
            return "MINEUR"

    # Lacunes fonctionnelles non couvertes -> majeur par défaut (risque de perte de logique métier)
    if type_ == "LACUNE_NON_COUVERT":
        return "MAJEUR"

    # Partiellement couvert -> mineur, sauf si aucune mesure correspondante trouvée
    if type_ == "LACUNE_PARTIELLEMENT_COUVERT":
        if "aucune trouvée" in finding.get("detail", "").lower():
            return "MAJEUR"
        return "MINEUR"

    return "MINEUR"


def prioritize_all(findings: list[dict]) -> list[dict]:
    """Applique la priorisation à tous les findings et les trie du plus critique au moins critique."""
    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}

    for f in findings:
        f["criticite"] = prioritize_finding(f)

    findings.sort(key=lambda f: ordre.get(f["criticite"], 3))
    return findings


if __name__ == "__main__":
    from merge import merge_findings

    fake_ecarts = [
        {"produit": "Laptop", "valeur_qlik": 116.67, "valeur_pbi": 11666.67, "ecart_relatif": 99.0, "diagnostic": "Format d'affichage incorrect (%) probable."}
    ]
    fake_mapping = [
        {"pattern": "left_join", "expression_source": "left join(", "statut": "PARTIELLEMENT_COUVERT", "mesure_dax_correspondante": None, "justification": "Aucune relation DAX équivalente identifiée clairement."}
    ]

    findings = merge_findings(fake_ecarts, fake_mapping)
    prioritized = prioritize_all(findings)

    for f in prioritized:
        print(f"[{f['criticite']}] {f['source_module']} — {f['libelle']}")
        print(f"   {f['detail']}\n")