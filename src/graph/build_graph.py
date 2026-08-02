# graph/build_graph.py

from typing import TypedDict, List, Dict, Any
from orchestrator.merge_advanced import FindingsMerger
from orchestrator.prioritize import prioritize_all


class State(TypedDict):
    all_comparisons: Dict
    missing_pbi: List
    comparison_failures: List
    qlik_patterns: List
    mapping_results: List
    dax_measures_path: str
    module_a_findings: List
    findings: List


class ReconciliationGraph:
    """
    Graphe de réconciliation pour l'audit de migration.
    """
    
    def __init__(self):
        self.merger = FindingsMerger()
    
    def invoke(self, state: State) -> State:
        """
        Exécute le graphe sur l'état donné.
        """
        # Étape 1: Fusionner les findings
        state = self._merge_findings(state)
        
        # Étape 2: Prioriser les findings
        state = self._prioritize(state)
        
        return state
    
    def _merge_findings(self, state: State) -> State:
        """Fusionne les findings des modules A et B."""
        # Récupérer les findings du Module A
        module_a_findings = state.get("module_a_findings", [])
        
        # Récupérer les findings du Module B depuis mapping_results
        module_b_findings = []
        for result in state.get("mapping_results", []):
            # Déterminer la criticité en fonction du statut
            statut = result.get("statut", "NON_COUVERT")
            criticite = self._get_criticite_from_statut(statut)
            
            module_b_findings.append({
                "source_module": "Module B - Functional Coverage",
                "pattern": result.get("pattern", ""),
                "expression": result.get("expression_source", ""),
                "statut": statut,
                "criticite": criticite,
                "justification": result.get("justification", ""),
                "recommandation": self._get_recommendation_for_pattern(
                    result.get("pattern", ""), 
                    statut
                )
            })
        
        # Ajouter les visuels manquants
        missing_visuals = state.get("missing_pbi", [])
        for visual in missing_visuals:
            module_a_findings.append({
                "source_module": "Module A - Data Reconciliation",
                "libelle": f"Visuel manquant : {visual}",
                "detail": f"Le visuel '{visual}' est présent dans Qlik mais absent dans Power BI",
                "criticite": "MAJEUR",
                "diagnostic": "Fonctionnalité non migrée",
                "recommandation": "Vérifier si le visuel a été supprimé intentionnellement ou s'il doit être migré"
            })
        
        # Ajouter les échecs de comparaison
        comparison_failures = state.get("comparison_failures", [])
        for failure in comparison_failures:
            module_a_findings.append({
                "source_module": "Module A - Data Reconciliation",
                "libelle": f"Échec de comparaison : {failure.get('visuel', 'Inconnu')}",
                "detail": failure.get("raison", "Erreur inconnue"),
                "criticite": "MAJEUR",
                "diagnostic": "Structure de données incompatible",
                "recommandation": "Vérifier manuellement la structure des données"
            })
        
        # Fusionner tous les findings
        all_findings = self.merger.merge_findings(module_a_findings, module_b_findings)
        state["findings"] = all_findings
        
        return state
    
    def _prioritize(self, state: State) -> State:
        """Priorise les findings."""
        state["findings"] = prioritize_all(state.get("findings", []))
        return state
    
    def _get_criticite_from_statut(self, statut: str) -> str:
        """Détermine la criticité en fonction du statut de mapping."""
        mapping = {
            "COUVERT": "MINEUR",
            "PARTIELLEMENT_COUVERT": "MAJEUR",
            "NON_COUVERT": "MAJEUR",
            "ERREUR_PARSING": "MINEUR"
        }
        return mapping.get(statut, "MINEUR")
    
    def _get_recommendation_for_pattern(self, pattern: str, statut: str) -> str:
        """Génère une recommandation pour un pattern donné."""
        if statut == "COUVERT":
            return "Migration OK - pattern équivalent en DAX"
        elif statut == "PARTIELLEMENT_COUVERT":
            recommendations = {
                "set_analysis": "Vérifier la logique des filtres avec CALCULATE()",
                "variable_dollar_expansion": "Utiliser VAR en DAX pour les variables",
                "variable_declaration": "Définir les variables en DAX avec VAR",
                "mapping_applymap": "Utiliser LOOKUPVALUE() ou RELATED()",
                "subroutine_definition": "Convertir en fonction DAX paramétrée",
                "subroutine_call": "Appeler la fonction DAX créée",
                "left_join": "Fusionner les tables en Power Query",
            }
            return recommendations.get(pattern, "Adapter manuellement en DAX")
        else:
            return "Migration manuelle requise - vérifier avec l'équipe technique"


def build_reconciliation_graph() -> ReconciliationGraph:
    """
    Construit le graphe de réconciliation.
    Retourne un objet ReconciliationGraph avec une méthode invoke().
    """
    return ReconciliationGraph()