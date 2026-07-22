from src.graph.build_graph import build_reconciliation_graph

app = build_reconciliation_graph()

initial_state = {
    "all_comparisons": {},
    "missing_pbi": [],
    "comparison_failures": [],
    "qlik_patterns": [],
    "dax_measures_path": "data/samples/case_encadrante_01/powerbi/measures_dax.txt",
}

result = app.invoke(initial_state)
print("Graphe exécuté avec succès.")
print(f"Findings produits : {len(result['findings'])}")