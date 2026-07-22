from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.nodes.node_module_a import node_module_a
from src.graph.nodes.node_module_b import node_module_b
from src.graph.nodes.node_orchestrator import node_orchestrator


def build_reconciliation_graph():
    graph = StateGraph(AgentState)

    graph.add_node("module_a", node_module_a)
    graph.add_node("module_b", node_module_b)
    graph.add_node("orchestrator", node_orchestrator)

    graph.set_entry_point("module_a")
    graph.add_edge("module_a", "module_b")
    graph.add_edge("module_b", "orchestrator")
    graph.add_edge("orchestrator", END)

    return graph.compile()