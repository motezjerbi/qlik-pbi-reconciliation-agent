"""
Module A - Reconciliation avancée
Comparaison avancée entre Qlik et Power BI avec détection automatique des colonnes
"""

import pandas as pd
import re
from typing import Dict, List, Tuple, Optional

# Import depuis reconciliation_v2 au lieu de model_reconciliation
try:
    from module_a.reconciliation_v2 import normalize_for_comparison as normalize_columns
except ImportError:
    def normalize_columns(df):
        if df is None:
            return df
        df = df.copy()
        df.columns = df.columns.str.strip().str.replace('"', '')
        return df

# Fonctions factices pour compatibilité
def load_raw_table(*args, **kwargs):
    """Compatibilité - utilisez compare_qlik_pbi_files à la place."""
    raise NotImplementedError(
        "load_raw_table est déprécié. Utilisez compare_qlik_pbi_files à la place."
    )

def get_column_name(df, col):
    """Récupère une colonne par nom."""
    if col in df.columns:
        return col
    for c in df.columns:
        if c.lower().strip() == col.lower().strip():
            return c
    return None

def get_column_safe(df, col, default=None):
    """Récupère une colonne en toute sécurité."""
    name = get_column_name(df, col)
    if name:
        return df[name]
    return default

def clean_amount_column(df, col):
    """Nettoie une colonne de montants."""
    if col not in df.columns:
        return df
    df = df.copy()
    df[col] = df[col].astype(str).str.replace(r'[^\d.,-]', '', regex=True)
    df[col] = df[col].str.replace(',', '.')
    df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

METRICS_SCALAIRES = {
    "SUM": "SUM",
    "AVG": "AVERAGE",
    "COUNT": "COUNT",
    "MIN": "MIN",
    "MAX": "MAX"
}

SEUIL_TOLERANCE = 0.01


def compare_exports_advanced(qlik_df: pd.DataFrame, pbi_df: pd.DataFrame, 
                             qlik_name: str = "Qlik", pbi_name: str = "PBI") -> Dict:
    """
    Compare deux dataframes de manière avancée avec détection automatique.
    
    Args:
        qlik_df: DataFrame Qlik
        pbi_df: DataFrame Power BI
        qlik_name: Nom de la source Qlik
        pbi_name: Nom de la source Power BI
        
    Returns:
        Dict avec les résultats de la comparaison
    """
    if qlik_df is None or pbi_df is None:
        return {
            "dataframe": pd.DataFrame(),
            "nb_ok": 0,
            "nb_ecarts": 0,
            "nb_erreurs": 1,
            "erreurs": ["DataFrame vide ou None"]
        }
    
    # Normaliser les colonnes
    qlik_df = normalize_columns(qlik_df)
    pbi_df = normalize_columns(pbi_df)
    
    # Trouver une colonne clé commune
    qlik_cols = set(qlik_df.columns)
    pbi_cols = set(pbi_df.columns)
    common_cols = qlik_cols & pbi_cols
    
    if not common_cols:
        return {
            "dataframe": pd.DataFrame(),
            "nb_ok": 0,
            "nb_ecarts": 0,
            "nb_erreurs": 1,
            "erreurs": ["Aucune colonne commune trouvée"]
        }
    
    # Utiliser la première colonne commune comme clé
    key_col = list(common_cols)[0]
    
    # Trouver les colonnes numériques communes
    numeric_cols = []
    for col in common_cols:
        if col != key_col:
            # Vérifier si la colonne est numérique
            try:
                if pd.to_numeric(qlik_df[col], errors='coerce').notna().sum() > 0:
                    numeric_cols.append(col)
            except:
                pass
    
    # Comparer
    results = []
    nb_ok = 0
    nb_ecarts = 0
    
    # Fusion
    merged = qlik_df.merge(
        pbi_df,
        on=key_col,
        how='outer',
        suffixes=(f'_{qlik_name}', f'_{pbi_name}'),
        indicator=True
    )
    
    for _, row in merged.iterrows():
        merge_status = row['_merge']
        
        if merge_status == 'both':
            # Comparer les valeurs
            has_ecart = False
            row_result = {key_col: row[key_col]}
            
            for col in numeric_cols:
                q_val = row.get(f'{col}_{qlik_name}')
                p_val = row.get(f'{col}_{pbi_name}')
                
                if pd.notna(q_val) and pd.notna(p_val):
                    try:
                        if float(q_val) != float(p_val):
                            has_ecart = True
                            row_result[f'{col}_qlik'] = q_val
                            row_result[f'{col}_pbi'] = p_val
                            row_result[f'{col}_ecart'] = float(q_val) - float(p_val)
                    except (ValueError, TypeError):
                        if str(q_val) != str(p_val):
                            has_ecart = True
                            row_result[f'{col}_qlik'] = q_val
                            row_result[f'{col}_pbi'] = p_val
                            row_result[f'{col}_ecart'] = 'N/A'
            
            if has_ecart:
                row_result['statut'] = 'ECART_DETECTE'
                nb_ecarts += 1
            else:
                row_result['statut'] = 'OK'
                nb_ok += 1
            
            results.append(row_result)
            
        elif merge_status == 'left_only':
            row_result = {key_col: row[key_col], 'statut': f'MANQUANT_{pbi_name.upper()}'}
            results.append(row_result)
        else:  # right_only
            row_result = {key_col: row[key_col], 'statut': f'EXTRA_{pbi_name.upper()}'}
            results.append(row_result)
    
    return {
        "dataframe": pd.DataFrame(results),
        "nb_ok": nb_ok,
        "nb_ecarts": nb_ecarts,
        "nb_erreurs": 0,
        "erreurs": []
    }


def detect_key_columns(df1: pd.DataFrame, df2: pd.DataFrame) -> List[str]:
    """Détecte automatiquement les colonnes clés communes."""
    common_cols = set(df1.columns) & set(df2.columns)
    key_candidates = []
    
    for col in common_cols:
        # Vérifier si la colonne est un bon candidat (peu de valeurs uniques)
        unique_count = min(df1[col].nunique(), df2[col].nunique())
        if unique_count > 1:
            key_candidates.append(col)
    
    return key_candidates


def detect_numeric_columns(df: pd.DataFrame) -> List[str]:
    """Détecte les colonnes numériques dans un DataFrame."""
    numeric_cols = []
    for col in df.columns:
        try:
            if pd.to_numeric(df[col], errors='coerce').notna().sum() > 0:
                numeric_cols.append(col)
        except:
            pass
    return numeric_cols