"""
Module B - Functional Coverage
Audit de couverture fonctionnelle entre Qlik et Power BI.

Ce fichier n'importe QUE ce qui est réellement utilisé et testé par app.py :
- coverage_analyzer.py : détection de patterns par règles (généralisée,
  matching par mots-clés DAX, pas de nom de mesure codé en dur)
- mapping.py : mapping 100% LLM (Mistral via Ollama) + auto-évaluation
  sans fichier (accord vs le moteur par règles)

D'autres fichiers existent encore dans ce dossier (module_b_integration.py,
pbi_parser.py, semantic_analyzer.py, semantic_analyzer_dynamic.py,
taxonomy.py, qlik_parser.py) mais ne sont plus importés ici : ce sont
d'anciennes tentatives ou des utilitaires non branchés au pipeline actif.
Les garder hors de ce __init__.py évite qu'un problème dans l'un d'eux ne
fasse planter le chargement de tout le module au démarrage.
"""

from .coverage_analyzer import FunctionalCoverageAnalyzer, analyze_coverage_quick, parse_dax_measures_text
from .mapping import map_pattern_to_dax, map_all_patterns, generate_coverage_report, LLMMapper, auto_evaluate_against_rules

__all__ = [
    "FunctionalCoverageAnalyzer",
    "analyze_coverage_quick",
    "parse_dax_measures_text",
    "map_pattern_to_dax",
    "map_all_patterns",
    "generate_coverage_report",
    "LLMMapper",
    "auto_evaluate_against_rules",
]