from typing import TypedDict, Optional
import pandas as pd


class AgentState(TypedDict, total=False):
    """État partagé qui circule entre les nœuds du graphe de réconciliation."""
    # Entrées
    all_comparisons: dict          # nom_visuel -> DataFrame résultat de comparison.py
    missing_pbi: list              # visuels Qlik sans équivalent Power BI
    comparison_failures: list      # comparaisons impossibles (structure incompatible)
    qlik_patterns: list            # patterns détectés par qlik_parser.py
    dax_measures_path: str         # chemin vers measures_dax.txt

    # Résultats intermédiaires
    mapping_results: list          # résultats de mapping.py (Module B)
    findings: list                 # findings fusionnés et priorisés

    # Sortie finale
    executive_summary: str
    report_markdown: str