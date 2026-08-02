"""
Module A - Data Reconciliation
Comparaison des données entre Qlik et Power BI.

Ce fichier n'importe QUE ce qui est réellement utilisé et testé par app.py :
extraction live (Qlik Engine API, Power BI ADOMD.NET) + réconciliation KPI.

D'anciens fichiers (auto_comparator.py, model_reconciliation.py,
reconciliation_v2.py, reconciliation_advanced.py, pbi_visual_extractor.py,
pdf_extractor.py, test_engine.py, test_real_case.py...) existent encore dans
ce dossier mais ne sont plus importés ici : ce sont d'anciennes tentatives,
souvent codées en dur pour le cas d'exemple sales_demo (IDs de visuels,
montants, chemins de fichiers en dur). Les garder hors de ce __init__.py
évite qu'un problème dans l'un d'eux ne fasse planter le chargement de tout
le module au démarrage.
"""

from .extractors.qlik_extractor import QlikExtractor
from .extractors.pbi_extractor import PBIExtractor
from .kpi_reconciliation import reconcile_kpis, SEUIL_TOLERANCE

__all__ = [
    "QlikExtractor",
    "PBIExtractor",
    "reconcile_kpis",
    "SEUIL_TOLERANCE",
]