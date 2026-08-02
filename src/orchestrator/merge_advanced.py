# orchestrator/merge_advanced.py
"""
Fusion avancée des findings des modules A et B.

Les deux modules (kpi_reconciliation.py côté A, coverage_analyzer.py côté B)
produisent déjà des dicts findings avec le MÊME schéma :
    source_module, libelle, detail, criticite, diagnostic, recommandation, statut
La fusion ne doit donc PAS recalculer une criticité ou reconstruire un libellé
à partir de champs propres à un module (ex. "ecart_relatif", "pattern",
"expression") qui n'existent pas dans ce schéma réel — ça écraserait
silencieusement la criticité déjà correctement calculée en amont (y compris
les cas ERREUR_PBI -> BLOQUANT).
"""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Finding:
    source_module: str
    libelle: str
    detail: str
    criticite: str  # BLOQUANT, MAJEUR, MINEUR
    diagnostic: str
    recommandation: str = ""
    statut: str = ""


class FindingsMerger:
    """Fusionne et priorise les findings des modules A et B."""

    def __init__(self):
        self.criticite_weights = {
            "BLOQUANT": 100,
            "MAJEUR": 50,
            "MINEUR": 10,
        }

    def _to_finding(self, f: Dict[str, Any]) -> Finding:
        """Convertit un dict finding (n'importe quel module) en Finding,
        en respectant le schéma déjà produit en amont — pas de recalcul."""
        return Finding(
            source_module=f.get("source_module", "Module inconnu"),
            libelle=f.get("libelle", "Finding"),
            detail=f.get("detail", ""),
            criticite=f.get("criticite", "MINEUR"),
            diagnostic=f.get("diagnostic", ""),
            recommandation=f.get("recommandation", ""),
            statut=f.get("statut", ""),
        )

    def merge_findings(
        self, module_a_findings: List[Dict], module_b_findings: List[Dict]
    ) -> List[Finding]:
        """Fusionne les findings des deux modules, triés par criticité décroissante."""
        all_raw = list(module_a_findings or []) + list(module_b_findings or [])
        findings = [self._to_finding(f) for f in all_raw]
        findings.sort(
            key=lambda x: self.criticite_weights.get(x.criticite, 0), reverse=True
        )
        return findings


def merge_findings(module_a_findings: List[Dict], module_b_findings: List[Dict]) -> List[Finding]:
    """Fonction de compatibilité pour l'ancienne interface."""
    return FindingsMerger().merge_findings(module_a_findings, module_b_findings)