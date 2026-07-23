import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
from module_a.comparison import compare_exports, SEUIL_TOLERANCE


def test_ecart_detecte_au_dela_du_seuil():
    """Un écart supérieur au seuil de tolérance doit être classé ECART_DETECTE."""
    qlik_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})
    pbi_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [200.0]})

    result = compare_exports(qlik_df, pbi_df, key_cols=["__key__"], value_col="__value__")

    assert result.iloc[0]["statut"] == "ECART_DETECTE"


def test_valeurs_identiques_donnent_ok():
    """Des valeurs strictement identiques doivent être classées OK."""
    qlik_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})
    pbi_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})

    result = compare_exports(qlik_df, pbi_df, key_cols=["__key__"], value_col="__value__")

    assert result.iloc[0]["statut"] == "OK"


def test_ecart_sous_le_seuil_donne_ok():
    """Un écart en dessous du seuil de tolérance ne doit PAS être signalé."""
    qlik_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})
    pbi_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0 * (1 + SEUIL_TOLERANCE / 2)]})

    result = compare_exports(qlik_df, pbi_df, key_cols=["__key__"], value_col="__value__")

    assert result.iloc[0]["statut"] == "OK"


def test_ligne_manquante_dans_pbi():
    """Une clé présente uniquement côté Qlik doit être signalée MANQUANT_DANS_PBI."""
    qlik_df = pd.DataFrame({"__key__": ["Laptop", "Monitor"], "__value__": [100.0, 200.0]})
    pbi_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})

    result = compare_exports(qlik_df, pbi_df, key_cols=["__key__"], value_col="__value__")

    monitor_row = result[result["__key__"] == "Monitor"]
    assert monitor_row.iloc[0]["statut"] == "MANQUANT_DANS_PBI"


def test_ligne_manquante_dans_qlik():
    """Une clé présente uniquement côté Power BI doit être signalée MANQUANT_DANS_QLIK."""
    qlik_df = pd.DataFrame({"__key__": ["Laptop"], "__value__": [100.0]})
    pbi_df = pd.DataFrame({"__key__": ["Laptop", "Mouse"], "__value__": [100.0, 50.0]})

    result = compare_exports(qlik_df, pbi_df, key_cols=["__key__"], value_col="__value__")

    mouse_row = result[result["__key__"] == "Mouse"]
    assert mouse_row.iloc[0]["statut"] == "MANQUANT_DANS_QLIK"