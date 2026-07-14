import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm.client import ask_claude


def generate_executive_summary(findings: list[dict]) -> str:
    """Demande au LLM de rédiger un résumé exécutif à partir des findings structurés."""
    nb_bloquant = sum(1 for f in findings if f["criticite"] == "BLOQUANT")
    nb_majeur = sum(1 for f in findings if f["criticite"] == "MAJEUR")
    nb_mineur = sum(1 for f in findings if f["criticite"] == "MINEUR")

    resume_findings = "\n".join(
        f"- [{f['criticite']}] {f['source_module']} : {f['libelle']} — {f['detail']}"
        for f in findings
    )

    prompt = f"""Tu es un consultant senior en migration Qlik Sense vers Power BI.
Rédige un résumé exécutif court (5-6 phrases maximum) pour un rapport de réconciliation post-migration,
à destination d'un consultant qui doit valider et corriger les problèmes.

Statistiques : {nb_bloquant} problème(s) bloquant(s), {nb_majeur} majeur(s), {nb_mineur} mineur(s).

Détail des findings :
{resume_findings}

Le résumé doit être factuel, professionnel, et donner une vue d'ensemble du niveau de risque de cette migration."""

    return ask_claude(prompt)


def generate_report(findings: list[dict], case_name: str) -> str:
    """Assemble le rapport consolidé final au format Markdown."""
    summary = generate_executive_summary(findings)

    lines = [
        f"# Rapport de réconciliation post-migration — {case_name}",
        f"\n*Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}*",
        "\n## Résumé exécutif\n",
        summary,
        "\n## Détail des findings\n"
    ]

    for f in findings:
        lines.append(f"### [{f['criticite']}] {f['libelle']}")
        lines.append(f"- **Module source :** {f['source_module']}")
        lines.append(f"- **Détail :** {f['detail']}")
        lines.append(f"- **Diagnostic :** {f['diagnostic']}")
        lines.append("- **Statut :** ⬜ à valider par le consultant\n")

    return "\n".join(lines)


if __name__ == "__main__":
    from merge import merge_findings
    from prioritize import prioritize_all

    fake_ecarts = [
        {"produit": "Laptop", "valeur_qlik": 116.67, "valeur_pbi": 11666.67, "ecart_relatif": 99.0, "diagnostic": "Format d'affichage incorrect (%) probable."}
    ]
    fake_mapping = [
        {"pattern": "left_join", "expression_source": "left join(", "statut": "PARTIELLEMENT_COUVERT", "mesure_dax_correspondante": None, "justification": "Aucune relation DAX équivalente identifiée clairement."}
    ]

    findings = merge_findings(fake_ecarts, fake_mapping)
    prioritized = prioritize_all(findings)

    report = generate_report(prioritized, case_name="sales_demo")

    output_path = Path("reports/rapport_sales_demo.md")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Rapport généré : {output_path}")
    print("\n--- Aperçu ---\n")
    print(report[:800])