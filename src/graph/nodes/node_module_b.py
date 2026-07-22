from src.graph.state import AgentState


def node_module_b(state: AgentState) -> AgentState:
    """
    Nœud Module B : consolide les résultats du mapping déjà produits en amont
    (onglet Functional Coverage) dans l'état partagé, sans les recalculer.
    """
    # Les résultats sont déjà présents dans l'état initial (mapping_results),
    # ce nœud sert de point de passage explicite dans le graphe.
    if "mapping_results" not in state:
        state["mapping_results"] = []

    return state