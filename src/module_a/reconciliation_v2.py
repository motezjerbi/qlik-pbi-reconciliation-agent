"""
Module A - Réconciliation de données
Détecte les écarts numériques entre Qlik et Power BI
"""

import re
import pandas as pd
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# ============================================================
# EXTRACTION QLIK
# ============================================================

def extract_qlik_inline_table(qvs_path: str, table_name: str = "Sales") -> pd.DataFrame:
    """
    Extrait une table INLINE du script Qlik (.qvs).
    """
    content = Path(qvs_path).read_text(encoding="utf-8")
    
    table_pattern = rf"{table_name}\s*:\s*LOAD.*?INLINE\s*\[(.*?)\]\s*;"
    match = re.search(table_pattern, content, re.IGNORECASE | re.DOTALL)
    
    if not match:
        raise ValueError(f"Table INLINE '{table_name}' introuvable dans {qvs_path}")
    
    raw_csv = match.group(1).strip()
    df = pd.read_csv(StringIO(raw_csv))
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # Transformations
    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df["OrderDate"] = dates
        df["Year"] = dates.dt.year
        df["Month"] = dates.dt.month
        df = df.drop(columns=["Date"])
    elif "Order Date" in df.columns:
        dates = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
        df["OrderDate"] = dates
        df["Year"] = dates.dt.year
        df["Month"] = dates.dt.month
        df = df.drop(columns=["Order Date"])
    
    return df

# ============================================================
# NORMALISATION
# ============================================================

def normalize_for_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise les colonnes pour la comparaison.
    """
    df = df.copy()
    
    column_mapping = {
        "Order ID": "OrderID",
        "Order Date": "OrderDate",
        "Customer ID": "CustomerID",
        "Product ID": "ProductID",
        "Channel ID": "ChannelID",
        "Sales Amount": "SalesAmount",
        "OrderID": "OrderID",
        "OrderDate": "OrderDate",
        "CustomerID": "CustomerID",
        "ProductID": "ProductID",
        "ChannelID": "ChannelID",
        "SalesAmount": "SalesAmount",
    }
    
    df = df.rename(columns=column_mapping)
    
    expected_cols = ["OrderID", "OrderDate", "Year", "Month", "CustomerID", 
                     "ProductID", "ChannelID", "Region", "SalesAmount", 
                     "Quantity", "Margin"]
    
    existing_cols = [col for col in expected_cols if col in df.columns]
    df = df[existing_cols]
    
    return df

# ============================================================
# COMPARAISON DES TABLES
# ============================================================

def compare_tables(qlik_df: pd.DataFrame, pbi_df: pd.DataFrame) -> Dict:
    """
    Compare deux tables ligne par ligne.
    """
    qlik_norm = normalize_for_comparison(qlik_df)
    pbi_norm = normalize_for_comparison(pbi_df)
    
    if "OrderID" not in qlik_norm.columns:
        raise ValueError("Colonne 'OrderID' introuvable dans Qlik")
    if "OrderID" not in pbi_norm.columns:
        raise ValueError("Colonne 'OrderID' introuvable dans Power BI")
    
    merged = qlik_norm.merge(
        pbi_norm,
        on="OrderID",
        how="outer",
        suffixes=("_qlik", "_pbi"),
        indicator=True
    )
    
    aligned = merged[merged["_merge"] == "both"]
    missing_in_pbi = merged[merged["_merge"] == "left_only"]
    extra_in_pbi = merged[merged["_merge"] == "right_only"]
    
    numeric_cols = ["SalesAmount", "Quantity", "Margin", "Year", "Month", "ChannelID"]
    discrepancies = []
    
    for _, row in aligned.iterrows():
        order_id = row["OrderID"]
        for col in numeric_cols:
            q_val = row.get(f"{col}_qlik")
            p_val = row.get(f"{col}_pbi")
            if pd.notna(q_val) and pd.notna(p_val):
                try:
                    if float(q_val) != float(p_val):
                        discrepancies.append({
                            "OrderID": order_id,
                            "Colonne": col,
                            "Valeur Qlik": q_val,
                            "Valeur PBI": p_val,
                            "Différence": float(q_val) - float(p_val),
                            "Écart %": abs(float(q_val) - float(p_val)) / abs(float(q_val)) * 100 if float(q_val) != 0 else 0
                        })
                except (ValueError, TypeError):
                    if str(q_val).strip() != str(p_val).strip():
                        discrepancies.append({
                            "OrderID": order_id,
                            "Colonne": col,
                            "Valeur Qlik": q_val,
                            "Valeur PBI": p_val,
                            "Différence": "N/A",
                            "Écart %": "N/A"
                        })
    
    return {
        "total_qlik": len(qlik_norm),
        "total_pbi": len(pbi_norm),
        "aligned": len(aligned),
        "missing_in_pbi": len(missing_in_pbi),
        "extra_in_pbi": len(extra_in_pbi),
        "discrepancies": pd.DataFrame(discrepancies),
        "aligned_data": aligned,
        "missing_data": missing_in_pbi,
        "extra_data": extra_in_pbi,
        "merge_summary": merged,
        "match_rate": len(aligned) / max(len(qlik_norm), 1) * 100
    }

# ============================================================
# COMPARAISON QLIK VS PBI FILES
# ============================================================

def compare_qlik_pbi_files(qlik_content: bytes, pbi_content: bytes, 
                           qlik_filename: str = "load_script.qvs",
                           pbi_filename: str = "sales_demo.csv") -> Dict:
    """
    Compare un fichier Qlik (.qvs) avec un fichier Power BI (.csv).
    """
    import io
    
    # 1. Extraire la table Qlik depuis le contenu
    qlik_text = qlik_content.decode("utf-8")
    
    # Écrire temporairement pour le parser
    temp_path = Path("data/temp_temp_qvs.qvs")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(qlik_text, encoding="utf-8")
    
    try:
        qlik_df = extract_qlik_inline_table(str(temp_path), "Sales")
    finally:
        if temp_path.exists():
            temp_path.unlink()
    
    # 2. Charger le CSV Power BI (détection du séparateur)
    content_str = pbi_content.decode("utf-8", errors="ignore")
    first_line = content_str.split('\n')[0]
    sep = ";" if first_line.count(";") > first_line.count(",") else ","
    
    pbi_df = pd.read_csv(io.BytesIO(pbi_content), sep=sep)
    pbi_df.columns = pbi_df.columns.str.strip().str.replace('"', '')
    
    if "Order Date" in pbi_df.columns:
        dates = pd.to_datetime(pbi_df["Order Date"], errors="coerce")
        pbi_df["OrderDate"] = dates
        pbi_df["Year"] = dates.dt.year
        pbi_df["Month"] = dates.dt.month
    
    # 3. Comparer
    results = compare_tables(qlik_df, pbi_df)
    
    # 4. Formater pour l'interface
    comparison_rows = []
    
    # Ajouter les lignes alignées
    for _, row in results["aligned_data"].iterrows():
        row_dict = {}
        for col in results["aligned_data"].columns:
            if col.endswith("_qlik"):
                base_col = col[:-5]
                row_dict[f"{base_col}"] = row[col]
            elif col.endswith("_pbi"):
                base_col = col[:-4]
                if base_col not in row_dict:
                    row_dict[f"{base_col}"] = row[col]
            elif col not in ["_merge"]:
                if col not in row_dict:
                    row_dict[col] = row[col]
        row_dict["statut"] = "✅ OK"
        comparison_rows.append(row_dict)
    
    # Ajouter les manquantes dans PBI
    for _, row in results["missing_data"].iterrows():
        row_dict = {"statut": "❌ Manquant dans PBI"}
        for col in results["missing_data"].columns:
            if not col.endswith(("_qlik", "_pbi", "_merge")):
                row_dict[col] = row[col]
        comparison_rows.append(row_dict)
    
    # Ajouter les extras dans PBI
    for _, row in results["extra_data"].iterrows():
        row_dict = {"statut": "➕ Extra dans PBI"}
        for col in results["extra_data"].columns:
            if not col.endswith(("_qlik", "_pbi", "_merge")):
                row_dict[col] = row[col]
        comparison_rows.append(row_dict)
    
    return {
        "summary": {
            "total_qlik": results["total_qlik"],
            "total_pbi": results["total_pbi"],
            "aligned": results["aligned"],
            "missing_in_pbi": results["missing_in_pbi"],
            "extra_in_pbi": results["extra_in_pbi"],
            "discrepancies": len(results["discrepancies"]),
            "match_rate": results["match_rate"]
        },
        "dataframe": pd.DataFrame(comparison_rows),
        "discrepancies": results["discrepancies"]
    }

# ============================================================
# CHARGEMENT PBI
# ============================================================

def load_pbi_table_from_csv(csv_content: bytes, sep: str = ';') -> pd.DataFrame:
    """Charge une table Power BI depuis un CSV exporté par DAX Studio."""
    import io
    df = pd.read_csv(io.BytesIO(csv_content), sep=sep)
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    if "Order Date" in df.columns:
        dates = pd.to_datetime(df["Order Date"], errors="coerce")
        df["OrderDate"] = dates
        df["Year"] = dates.dt.year
        df["Month"] = dates.dt.month
    
    return df

# ============================================================
# ANALYSE COMPLÈTE MODULE A
# ============================================================

def analyze_module_a(qlik_content: bytes, pbi_content: bytes) -> Dict:
    """
    Analyse complète du Module A.
    """
    import io
    
    # 1. Charger les données Qlik
    qlik_text = qlik_content.decode("utf-8")
    temp_path = Path("data/temp_temp_qvs.qvs")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(qlik_text, encoding="utf-8")
    
    try:
        qlik_df = extract_qlik_inline_table(str(temp_path), "Sales")
        qlik_df = normalize_for_comparison(qlik_df)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    
    # 2. Charger les données PBI
    content_str = pbi_content.decode("utf-8", errors="ignore")
    first_line = content_str.split('\n')[0]
    sep = ";" if first_line.count(";") > first_line.count(",") else ","
    pbi_df = pd.read_csv(io.BytesIO(pbi_content), sep=sep)
    pbi_df = normalize_for_comparison(pbi_df)
    
    # 3. Comparer les colonnes
    qlik_cols = set(qlik_df.columns)
    pbi_cols = set(pbi_df.columns)
    
    col_results = {
        "qlik_columns": list(qlik_cols),
        "pbi_columns": list(pbi_cols),
        "common": list(qlik_cols & pbi_cols),
        "missing_in_pbi": list(qlik_cols - pbi_cols),
        "extra_in_pbi": list(pbi_cols - qlik_cols)
    }
    
    # 4. Comparer les agrégations
    numeric_cols = ["SalesAmount", "Quantity", "Margin"]
    agg_results = []
    ecarts_detectes = []
    
    for col in numeric_cols:
        if col not in qlik_df.columns or col not in pbi_df.columns:
            continue
            
        qlik_sum = qlik_df[col].sum()
        pbi_sum = pbi_df[col].sum()
        qlik_avg = qlik_df[col].mean()
        pbi_avg = pbi_df[col].mean()
        qlik_count = qlik_df[col].count()
        pbi_count = pbi_df[col].count()
        qlik_min = qlik_df[col].min()
        pbi_min = pbi_df[col].min()
        qlik_max = qlik_df[col].max()
        pbi_max = pbi_df[col].max()
        
        agg_results.append({
            "Colonne": col,
            "Qlik_Sum": qlik_sum,
            "PBI_Sum": pbi_sum,
            "Diff_Sum": pbi_sum - qlik_sum,
            "Qlik_Avg": qlik_avg,
            "PBI_Avg": pbi_avg,
            "Diff_Avg": pbi_avg - qlik_avg,
            "Qlik_Count": qlik_count,
            "PBI_Count": pbi_count,
            "Diff_Count": pbi_count - qlik_count,
            "Qlik_Min": qlik_min,
            "PBI_Min": pbi_min,
            "Qlik_Max": qlik_max,
            "PBI_Max": pbi_max
        })
        
        if qlik_sum != 0:
            diff_pct = abs((pbi_sum - qlik_sum) / qlik_sum * 100)
            if diff_pct > 0.01:
                ecarts_detectes.append({
                    "Colonne": col,
                    "Qlik": qlik_sum,
                    "PBI": pbi_sum,
                    "Différence": pbi_sum - qlik_sum,
                    "Écart %": diff_pct,
                    "Criticité": "ÉLEVÉE" if diff_pct > 5 else "MOYENNE" if diff_pct > 1 else "FAIBLE"
                })
    
    # 5. Comparaison ligne par ligne
    table_results = compare_tables(qlik_df, pbi_df)
    
    # 6. Synthèse
    summary = {
        "total_qlik_rows": len(qlik_df),
        "total_pbi_rows": len(pbi_df),
        "common_columns": len(col_results["common"]),
        "missing_columns": len(col_results["missing_in_pbi"]),
        "extra_columns": len(col_results["extra_in_pbi"]),
        "aligned_rows": table_results["aligned"],
        "missing_rows": table_results["missing_in_pbi"],
        "extra_rows": table_results["extra_in_pbi"],
        "discrepancies_count": len(table_results["discrepancies"]),
        "aggregation_ecarts": len(ecarts_detectes),
        "match_rate": table_results["match_rate"]
    }
    
    return {
        "summary": summary,
        "columns": col_results,
        "aggregations": {
            "aggregations": pd.DataFrame(agg_results),
            "ecarts": pd.DataFrame(ecarts_detectes),
            "nb_ecarts": len(ecarts_detectes)
        },
        "table_comparison": table_results,
        "qlik_df": qlik_df,
        "pbi_df": pbi_df
    }

# ============================================================
# EXPORT RAPPORT
# ============================================================

def export_module_a_report(results: Dict, output_path: str):
    """
    Exporte le rapport du Module A en Excel.
    """
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Résumé
        summary_df = pd.DataFrame([
            {"Métrique": "Total Qlik", "Valeur": results["summary"]["total_qlik_rows"]},
            {"Métrique": "Total Power BI", "Valeur": results["summary"]["total_pbi_rows"]},
            {"Métrique": "Colonnes communes", "Valeur": results["summary"]["common_columns"]},
            {"Métrique": "Colonnes manquantes PBI", "Valeur": results["summary"]["missing_columns"]},
            {"Métrique": "Colonnes extra PBI", "Valeur": results["summary"]["extra_columns"]},
            {"Métrique": "Lignes alignées", "Valeur": results["summary"]["aligned_rows"]},
            {"Métrique": "Lignes manquantes PBI", "Valeur": results["summary"]["missing_rows"]},
            {"Métrique": "Lignes extra PBI", "Valeur": results["summary"]["extra_rows"]},
            {"Métrique": "Écarts numériques", "Valeur": results["summary"]["discrepancies_count"]},
            {"Métrique": "Taux d'alignement", "Valeur": f"{results['summary']['match_rate']:.1f}%"}
        ])
        summary_df.to_excel(writer, sheet_name="Résumé", index=False)
        
        # Colonnes
        pd.DataFrame({
            "Type": ["Communes", "Manquantes PBI", "Extra PBI"],
            "Colonnes": [
                ", ".join(results["columns"]["common"]),
                ", ".join(results["columns"]["missing_in_pbi"]),
                ", ".join(results["columns"]["extra_in_pbi"])
            ]
        }).to_excel(writer, sheet_name="Colonnes", index=False)
        
        # Agrégations
        if not results["aggregations"]["aggregations"].empty:
            results["aggregations"]["aggregations"].to_excel(writer, sheet_name="Agrégations", index=False)
        
        # Écarts
        if not results["aggregations"]["ecarts"].empty:
            results["aggregations"]["ecarts"].to_excel(writer, sheet_name="Écarts_agrégats", index=False)
        
        # Comparaison détaillée
        if not results["table_comparison"]["discrepancies"].empty:
            results["table_comparison"]["discrepancies"].to_excel(writer, sheet_name="Écarts_détaillés", index=False)
        
        # Données alignées
        results["table_comparison"]["aligned_data"].to_excel(writer, sheet_name="Données_alignées", index=False)

# ============================================================
# SUGGESTIONS DE CORRECTION
# ============================================================

def generate_correction_suggestions_llm(results: Dict) -> str:
    """
    Génère des suggestions de correction via LLM.
    """
    try:
        from llm.client import ask_claude
    except ImportError:
        return "LLM non disponible"
    
    prompt = f"""
Analyse les écarts détectés dans la migration Qlik → Power BI :

## Résumé
- Taux d'alignement: {results['summary']['match_rate']:.1f}%
- Écarts numériques: {results['summary']['discrepancies_count']}
- Lignes manquantes: {results['summary']['missing_rows']}
- Colonnes manquantes: {results['summary']['missing_columns']}

## Écarts d'agrégations
{results['aggregations']['ecarts'].to_string() if not results['aggregations']['ecarts'].empty else 'Aucun'}

## Écarts ligne par ligne
{results['table_comparison']['discrepancies'].to_string() if not results['table_comparison']['discrepancies'].empty else 'Aucun'}

Pour chaque écart, identifie:
1. La cause probable
2. Une action corrective concrète
"""
    
    return ask_claude(prompt)