import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from module_a.ingestion import load_export
from module_a.comparison import compare_exports

# Chargement des vrais exports
qlik_df = load_export("data/samples/case_encadrante_01/qlik/data_export.xlsx")
pbi_df = load_export("data/samples/case_encadrante_01/powerbi/data_export.csv")

# Harmonisation des noms de colonnes (ProductName vs Product Name)
qlik_df = qlik_df.rename(columns={"ProductName": "Product Name"})

# Harmonisation Average Margin (PBI) -> Margin (Qlik)
pbi_df = pbi_df.rename(columns={"Average Margin": "Margin"})

# Nettoyage de la colonne Margin côté Power BI (format "11666,67%" -> valeur brute 116.6667)
pbi_df["Margin"] = (
    pbi_df["Margin"]
    .astype(str)
    .str.replace("%", "", regex=False)
    .str.replace(",", ".", regex=False)
    .astype(float) / 100
)

# Comparaison sur la marge
result = compare_exports(qlik_df, pbi_df, key_cols=["Product Name"], value_col="Margin")

print(result[["Product Name", "Margin_qlik", "Margin_pbi", "ecart_absolu", "ecart_relatif", "statut"]])

ecarts = result[result["statut"] == "ECART_DETECTE"]
print(f"\n{len(ecarts)} écart(s) détecté(s) au-delà du seuil.")