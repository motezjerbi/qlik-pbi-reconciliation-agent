import pandas as pd

# Seuil de tolérance : au-delà de 1% d'écart relatif, on considère que c'est une anomalie
SEUIL_TOLERANCE = 0.01

def compare_exports(qlik_df: pd.DataFrame, pbi_df: pd.DataFrame, key_cols: list[str], value_col: str) -> pd.DataFrame:
    """
    Compare deux DataFrames sur une colonne de valeur, alignés sur des colonnes clés (dimensions).
    Retourne un DataFrame des écarts détectés.
    """
    merged = qlik_df.merge(
        pbi_df,
        on=key_cols,
        suffixes=("_qlik", "_pbi"),
        how="outer",
        indicator=True
    )

    val_qlik = f"{value_col}_qlik"
    val_pbi = f"{value_col}_pbi"

    merged["ecart_absolu"] = merged[val_qlik] - merged[val_pbi]
    merged["ecart_relatif"] = (merged["ecart_absolu"] / merged[val_qlik]).abs()

    merged["statut"] = merged.apply(_classify_row, axis=1)

    return merged

def _classify_row(row) -> str:
    if row["_merge"] == "left_only":
        return "MANQUANT_DANS_PBI"
    if row["_merge"] == "right_only":
        return "MANQUANT_DANS_QLIK"
    if pd.isna(row["ecart_relatif"]):
        return "ERREUR_CALCUL"
    if row["ecart_relatif"] > SEUIL_TOLERANCE:
        return "ECART_DETECTE"
    return "OK"

if __name__ == "__main__":
    from ingestion import load_export

    qlik_df = load_export("data/samples/case_01_test/qlik/data_export.csv")
    pbi_df = load_export("data/samples/case_01_test/powerbi/data_export.csv")

    result = compare_exports(qlik_df, pbi_df, key_cols=["Region", "Produit"], value_col="Ventes")

    print(result[["Region", "Produit", "Ventes_qlik", "Ventes_pbi", "ecart_absolu", "ecart_relatif", "statut"]])

    ecarts = result[result["statut"] == "ECART_DETECTE"]
    print(f"\n{len(ecarts)} écart(s) détecté(s) au-delà du seuil de {SEUIL_TOLERANCE*100}%.")