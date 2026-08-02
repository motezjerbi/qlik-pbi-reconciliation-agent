# orchestrator/prioritize.py

from typing import List
from .merge_advanced import Finding

def prioritize_all(findings: List) -> List:
    """
    Priorise les findings par criticité.
    Peut accepter soit des dictionnaires, soit des objets Finding.
    """
    prioritized = []
    
    for f in findings:
        if isinstance(f, dict):
            # Convertir les dictionnaires en objets Finding
            prioritized.append(Finding(
                source_module=f.get("source_module", "Inconnu"),
                libelle=f.get("libelle", f.get("metrique", "Non spécifié")),
                detail=f.get("detail", ""),
                criticite=f.get("criticite", "MINEUR"),
                diagnostic=f.get("diagnostic", "À analyser"),
                recommandation=f.get("recommandation", ""),
                statut=f.get("statut", "")
            ))
        else:
            # Déjà un objet Finding
            prioritized.append(f)
    
    # Trier par criticité (BLOQUANT > MAJEUR > MINEUR)
    criticite_order = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
    prioritized.sort(key=lambda x: criticite_order.get(x.criticite, 3))
    
    return prioritized