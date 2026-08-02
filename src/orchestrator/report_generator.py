# orchestrator/report_generator.py
"""
Générateur de rapport d'audit.

Le résumé exécutif est généré par des RÈGLES DÉTERMINISTES, volontairement
pas par un LLM : on a mesuré (voir Agent Evaluation) que Mistral en local
n'est pas stable d'une exécution à l'autre. Un résumé qui varie ou invente un
chiffre à chaque génération serait pire qu'inutile pour un consultant qui
doit s'y fier rapidement — mieux vaut un texte prévisible et toujours exact.
"""

from typing import List, Dict
from datetime import datetime
from collections import Counter
from .merge_advanced import Finding


def generate_executive_summary(findings: List[Finding]) -> str:
    """Résumé exécutif en 3-4 phrases, calculé uniquement à partir des
    findings déjà produits — aucune invention, aucun chiffre halluciné."""
    total = len(findings)
    if total == 0:
        return (
            "**Aucun écart ni lacune détecté.** Le rapport Power BI migré "
            "correspond au rapport Qlik source sur l'ensemble des points "
            "vérifiés par cet audit automatisé."
        )

    bloquant = sum(1 for f in findings if f.criticite == "BLOQUANT")
    majeur = sum(1 for f in findings if f.criticite == "MAJEUR")
    mineur = sum(1 for f in findings if f.criticite == "MINEUR")

    if bloquant > 0:
        niveau = "CRITIQUE"
    elif majeur >= 3:
        niveau = "ÉLEVÉ"
    elif majeur > 0:
        niveau = "MODÉRÉ"
    else:
        niveau = "FAIBLE"

    par_module = Counter(f.source_module for f in findings)
    modules_txt = ", ".join(
        f"{count} via {module}" for module, count in par_module.most_common()
    )

    lines = [f"**Niveau de risque global : {niveau}**", ""]
    lines.append(
        f"L'audit automatisé a identifié **{total} point(s)** à examiner "
        f"({bloquant} bloquant(s), {majeur} majeur(s), {mineur} mineur(s)), "
        f"répartis ainsi : {modules_txt}."
    )

    if bloquant > 0:
        exemples = [f.libelle for f in findings if f.criticite == "BLOQUANT"][:3]
        lines.append(
            "Points bloquants à traiter en priorité, avant toute mise en "
            f"production : {'; '.join(exemples)}"
            + (f" (et {bloquant - len(exemples)} autre(s))." if bloquant > len(exemples) else ".")
        )
        lines.append(
            "**Recommandation :** ces écarts nécessitent une validation "
            "manuelle par un consultant avant de considérer la migration "
            "comme terminée."
        )
    elif majeur > 0:
        lines.append(
            "**Recommandation :** aucun blocage critique, mais les points "
            "majeurs méritent une vérification avant validation finale."
        )
    else:
        lines.append(
            "**Recommandation :** écarts mineurs uniquement — revue "
            "standard suffisante, pas d'urgence particulière."
        )

    return "\n".join(lines)


def generate_report(findings: List[Finding]) -> str:
    """
    Génère un rapport Markdown à partir des findings.
    """
    if not findings:
        return "# Rapport d'Audit\n\nAucun finding à signaler."

    report = "# 📊 Rapport d'Audit de Migration\n\n"
    report += f"**Date :** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

    report += "## 🧭 Résumé exécutif\n\n"
    report += generate_executive_summary(findings) + "\n\n"

    # Statistiques
    total = len(findings)
    bloquant = sum(1 for f in findings if f.criticite == "BLOQUANT")
    majeur = sum(1 for f in findings if f.criticite == "MAJEUR")
    mineur = sum(1 for f in findings if f.criticite == "MINEUR")

    report += f"## 📈 Résumé chiffré\n\n"
    report += f"- **Total des findings :** {total}\n"
    report += f"- **🔴 Bloquants :** {bloquant}\n"
    report += f"- **🟠 Majeurs :** {majeur}\n"
    report += f"- **🟡 Mineurs :** {mineur}\n\n"

    # Détails par criticité
    for criticite, emoji in [("BLOQUANT", "🔴"), ("MAJEUR", "🟠"), ("MINEUR", "🟡")]:
        items = [f for f in findings if f.criticite == criticite]
        if items:
            report += f"## {emoji} {criticite} ({len(items)})\n\n"
            for idx, item in enumerate(items, 1):
                report += f"### {idx}. {item.libelle}\n"
                report += f"- **Module :** {item.source_module}\n"
                report += f"- **Détail :** {item.detail}\n"
                report += f"- **Diagnostic :** {item.diagnostic}\n"
                if item.recommandation:
                    report += f"- **Recommandation :** {item.recommandation}\n"
                report += "\n"

    return report


def export_report(findings: List[Finding], filepath: str) -> None:
    """
    Exporte le rapport vers un fichier.
    """
    report = generate_report(findings)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)