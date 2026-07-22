from src.graph.state import AgentState


def node_module_a(state: AgentState) -> AgentState:
    """
    Nœud Module A : ne recalcule rien, consolide simplement les résultats
    de comparaison déjà produits en amont (upload + comparison.py) dans l'état partagé.
    """
    # Les comparaisons sont déjà faites en amont (interface Streamlit) ;
    # ce nœud sert de point de passage explicite dans le graphe,
    # et pourra plus tard exécuter directement comparison.py si on branche
    # le graphe sur des fichiers plutôt que sur des résultats déjà calculés.
    return state