import re
import pandas as pd
from io import StringIO
from pathlib import Path

# ============================================
# PARTIE 1 : Extraction Qlik (parse direct)
# ============================================

def extract_qlik_inline_table(qvs_path: str, table_name: str = "Sales") -> pd.DataFrame:
    """
    Extrait une table INLINE du script Qlik (.qvs).
    """
    content = Path(qvs_path).read_text(encoding="utf-8")
    
    # Pattern pour trouver : Sales: LOAD ... INLINE [ ... ] ;
    table_pattern = rf"{table_name}\s*:\s*LOAD.*?INLINE\s*\[(.*?)\]\s*;"
    match = re.search(table_pattern, content, re.IGNORECASE | re.DOTALL)
    
    if not match:
        raise ValueError(f"Table INLINE '{table_name}' introuvable dans {qvs_path}")
    
    raw_csv = match.group(1).strip()
    df = pd.read_csv(StringIO(raw_csv))
    
    # Nettoyer les noms de colonnes
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # Transformations du script Qlik (Year, Month)
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


# ============================================
# PARTIE 2 : Chargement Power BI (CORRIGÉ)
# ============================================

def load_pbi_table(csv_path: str) -> pd.DataFrame:
    """Charge la table exportée depuis Power BI (DAX Studio) avec le bon séparateur."""
    # Power BI exporte souvent avec ; comme séparateur (format européen)
    df = pd.read_csv(csv_path, sep=';')
    
    # Nettoyer les noms de colonnes
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # Si "Order Date" existe, créer "OrderDate"
    if "Order Date" in df.columns:
        dates = pd.to_datetime(df["Order Date"], errors="coerce")
        df["OrderDate"] = dates
        df["Year"] = dates.dt.year
        df["Month"] = dates.dt.month
    
    return df


# ============================================
# PARTIE 3 : Normalisation
# ============================================

def normalize_for_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les données pour comparaison avec des noms de colonnes standardisés."""
    df = df.copy()
    
    # Dictionnaire de mapping : nom original → nom standard
    column_mapping = {
        # Power BI (avec espaces) → Standard
        "Order ID": "OrderID",
        "Order Date": "OrderDate",
        "Customer ID": "CustomerID",
        "Product ID": "ProductID",
        "Channel ID": "ChannelID",
        "Sales Amount": "SalesAmount",
        
        # Qlik (sans espaces) → Standard (déjà bon)
        "OrderID": "OrderID",
        "OrderDate": "OrderDate",
        "CustomerID": "CustomerID",
        "ProductID": "ProductID",
        "ChannelID": "ChannelID",
        "SalesAmount": "SalesAmount",
    }
    
    # Renommer les colonnes existantes
    df = df.rename(columns=column_mapping)
    
    # Colonnes standard attendues
    expected_cols = ["OrderID", "OrderDate", "Year", "Month", "CustomerID", 
                     "ProductID", "ChannelID", "Region", "SalesAmount", 
                     "Quantity", "Margin"]
    
    # Ne garder que les colonnes qui existent
    existing_cols = [col for col in expected_cols if col in df.columns]
    df = df[existing_cols]
    
    return df


# ============================================
# PARTIE 4 : Comparaison
# ============================================

def compare_tables(qlik_df: pd.DataFrame, pbi_df: pd.DataFrame) -> dict:
    """Compare deux tables ligne par ligne."""
    
    # Normaliser les deux tables
    qlik_norm = normalize_for_comparison(qlik_df)
    pbi_norm = normalize_for_comparison(pbi_df)
    
    print(f"   🔍 Colonnes Qlik normalisées : {', '.join(qlik_norm.columns)}")
    print(f"   🔍 Colonnes PBI normalisées : {', '.join(pbi_norm.columns)}")
    
    # Vérifier la clé commune
    if "OrderID" not in qlik_norm.columns:
        raise ValueError("La colonne 'OrderID' est introuvable dans Qlik")
    if "OrderID" not in pbi_norm.columns:
        raise ValueError("La colonne 'OrderID' est introuvable dans Power BI")
    
    # Fusion
    merged = qlik_norm.merge(
        pbi_norm,
        on="OrderID",
        how="outer",
        suffixes=("_qlik", "_pbi"),
        indicator=True
    )
    
    # Statistiques
    aligned = merged[merged["_merge"] == "both"]
    missing_in_pbi = merged[merged["_merge"] == "left_only"]
    extra_in_pbi = merged[merged["_merge"] == "right_only"]
    
    # Détection des écarts
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
                            "Différence": float(q_val) - float(p_val)
                        })
                except (ValueError, TypeError):
                    if str(q_val).strip() != str(p_val).strip():
                        discrepancies.append({
                            "OrderID": order_id,
                            "Colonne": col,
                            "Valeur Qlik": q_val,
                            "Valeur PBI": p_val,
                            "Différence": "N/A"
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
        "merge_summary": merged
    }


# ============================================
# PARTIE 5 : Génération du rapport
# ============================================

def generate_report(results: dict, output_path: str):
    """Génère un rapport Excel."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        
        # Résumé
        summary = pd.DataFrame([
            {"Métrique": "Total lignes Qlik", "Valeur": results["total_qlik"]},
            {"Métrique": "Total lignes Power BI", "Valeur": results["total_pbi"]},
            {"Métrique": "✅ Lignes alignées", "Valeur": results["aligned"]},
            {"Métrique": "❌ Manquantes dans PBI", "Valeur": results["missing_in_pbi"]},
            {"Métrique": "➕ Extra dans PBI", "Valeur": results["extra_in_pbi"]},
            {"Métrique": "⚠️ Écarts de valeurs", "Valeur": len(results["discrepancies"])},
            {"Métrique": "🎯 Taux d'alignement", "Valeur": f"{results['aligned']/max(results['total_qlik'],1)*100:.1f}%"}
        ])
        summary.to_excel(writer, sheet_name="📊 Résumé", index=False)
        
        # Écarts
        if not results["discrepancies"].empty:
            results["discrepancies"].to_excel(writer, sheet_name="⚠️ Écarts", index=False)
        else:
            pd.DataFrame([{"Message": "✅ Aucun écart détecté"}]).to_excel(
                writer, sheet_name="⚠️ Écarts", index=False
            )
        
        # Détails
        results["aligned_data"].to_excel(writer, sheet_name="✅ Alignées", index=False)
        
        if not results["missing_data"].empty:
            results["missing_data"].to_excel(writer, sheet_name="❌ Manquantes PBI", index=False)
        
        if not results["extra_data"].empty:
            results["extra_data"].to_excel(writer, sheet_name="➕ Extra PBI", index=False)
    
    print(f"✅ Rapport généré : {output_path}")


# ============================================
# PARTIE 6 : MAIN
# ============================================

if __name__ == "__main__":
    
    # Configuration
    QLIK_QVS_PATH = "data/samples/case_encadrante_01/qlik/load_script.qvs"
    PBI_CSV_PATH = "data/samples/case_encadrante_01/model_level/sales_raw_pbi_final.csv"
    OUTPUT_PATH = "data/samples/case_encadrante_01/reports/reconciliation_report.xlsx"
    
    print("=" * 60)
    print("🔍 MODULE A - RÉCONCILIATION QLIK → POWER BI")
    print("=" * 60)
    
    # 1. Extraction Qlik
    print("\n📂 1. Extraction de la table Qlik...")
    try:
        qlik_df = extract_qlik_inline_table(QLIK_QVS_PATH, "Sales")
        print(f"   ✅ {len(qlik_df)} lignes extraites")
        print(f"   📋 Colonnes Qlik : {', '.join(qlik_df.columns)}")
    except FileNotFoundError:
        print("   ❌ Fichier Qlik introuvable !")
        print(f"   📁 Chemin attendu : {QLIK_QVS_PATH}")
        exit(1)
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        exit(1)
    
    # 2. Chargement Power BI
    print("\n📂 2. Chargement de la table Power BI...")
    try:
        pbi_df = load_pbi_table(PBI_CSV_PATH)
        print(f"   ✅ {len(pbi_df)} lignes chargées")
        print(f"   📋 Colonnes PBI : {', '.join(pbi_df.columns)}")
    except FileNotFoundError:
        print("   ❌ Fichier Power BI introuvable !")
        print(f"   📁 Chemin attendu : {PBI_CSV_PATH}")
        print("   💡 Exportez depuis DAX Studio avec : EVALUATE Sales")
        exit(1)
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        exit(1)
    
    # 3. Comparaison
    print("\n🔄 3. Comparaison des tables...")
    results = compare_tables(qlik_df, pbi_df)
    
    # 4. Résultats
    print("\n📊 RÉSULTATS :")
    print(f"   ✅ Alignées : {results['aligned']}/{results['total_qlik']}")
    print(f"   ❌ Manquantes dans PBI : {results['missing_in_pbi']}")
    print(f"   ➕ Extra dans PBI : {results['extra_in_pbi']}")
    print(f"   ⚠️ Écarts de valeurs : {len(results['discrepancies'])}")
    print(f"   🎯 Taux d'alignement : {results['aligned']/max(results['total_qlik'],1)*100:.1f}%")
    
    # 5. Rapport
    print("\n📄 4. Génération du rapport Excel...")
    generate_report(results, OUTPUT_PATH)
    
    print("\n" + "=" * 60)
    print("✅ Module A terminé avec succès !")
    print("=" * 60)