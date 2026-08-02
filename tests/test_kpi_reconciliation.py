# tests/test_kpi_reconciliation.py
"""
Tests de non-regression pour kpi_reconciliation.py.
Lancer : pytest tests/test_kpi_reconciliation.py -v
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from module_a.kpi_reconciliation import reconcile_kpis


def _qlik_kpi(name, value, kpi_id="", sheet="Sheet1", expression=""):
    return {"id": kpi_id, "name": name, "value": value, "sheet": sheet, "expression": expression}


def _pbi_kpi(name, value, error=None, expression=""):
    return {"id": "", "name": name, "value": value, "page": "", "expression": expression, "error": error}


def _statut_for(rec_df, kpi_name):
    row = rec_df[rec_df["kpi"] == kpi_name]
    assert not row.empty, f"KPI '{kpi_name}' absent du resultat"
    return row.iloc[0]


class TestMatchingExact:
    def test_id_exact_prioritaire(self):
        qlik = {"kpis": [{"id": "K1", "name": "Total", "value": 100, "sheet": "S1", "expression": ""}]}
        pbi = {"kpis": [{"id": "K1", "name": "Nom Different", "value": 100, "page": "", "expression": "", "error": None}]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Total")
        assert row["match_type"] == "EXACT_ID"
        assert row["match_score"] == 1.0

    def test_nom_exact_si_pas_id(self):
        qlik = {"kpis": [_qlik_kpi("Total Sales", 5850)]}
        pbi = {"kpis": [_pbi_kpi("Total Sales", 5850)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Total Sales")
        assert row["match_type"] == "EXACT_NOM"
        assert row["statut"] == "MATCH_VALUE"


class TestMatchingApproximatif:
    def test_ytd_matche_year_to_date_sales(self):
        qlik = {"kpis": [_qlik_kpi("YTD", 0)]}
        pbi = {"kpis": [_pbi_kpi("Year To Date Sales", 4100)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "YTD")
        assert row["match_type"] == "APPROX"
        assert row["kpi_pbi"] == "Year To Date Sales"

    def test_avg_sales_matche_average_sales_per_customer(self):
        qlik = {"kpis": [_qlik_kpi("Avg Sales", 1462.5)]}
        pbi = {"kpis": [_pbi_kpi("Average Sales Per Customer", 1462.5)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Avg Sales")
        assert row["match_type"] == "APPROX"
        assert row["statut"] == "MATCH_VALUE"

    def test_distinct_customers_matche_distinct_customer_count(self):
        qlik = {"kpis": [_qlik_kpi("Distinct Customers", 4)]}
        pbi = {"kpis": [_pbi_kpi("Distinct Customer Count", 4)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Distinct Customers")
        assert row["match_type"] == "APPROX"
        assert row["statut"] == "MATCH_VALUE"


class TestGardeFouSelecteur:
    def test_max_year_sales_ne_matche_pas_latest_year_sales(self):
        qlik = {"kpis": [_qlik_kpi("Max Year Sales", 4100)]}
        pbi = {"kpis": [_pbi_kpi("Latest Year Sales", None)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Max Year Sales")
        assert row["match_type"] == "AUCUN"

    def test_max_year_sales_ne_matche_pas_previous_year_sales(self):
        qlik = {"kpis": [_qlik_kpi("Max Year Sales", 4100)]}
        pbi = {"kpis": [_pbi_kpi("Previous Year Sales", 1400)]}
        rec = reconcile_kpis(qlik, pbi)
        row = _statut_for(rec, "Max Year Sales")
        assert row["match_type"] == "AUCUN"


class TestErreurPbi:
    def test_mesure_en_erreur_dax_devient_bloquant(self):
        qlik = {"kpis": [_qlik_kpi("Latest Year", 4100)]}
        pbi = {"kpis": [_pbi_kpi(
            "Latest Year Sales", None,
            error="CALCULATE utilise dans un filtre booleen invalide",
        )]}
        rec = reconcile_kpis(qlik, pbi)
        assert (rec["statut"] == "ERREUR_PBI").any()
        row = rec[rec["statut"] == "ERREUR_PBI"].iloc[0]
        assert row["criticite"] == "BLOQUANT"


class TestDoublonsMemeNom:
    def test_deux_total_sales_restent_deux_lignes(self):
        qlik = {"kpis": [
            _qlik_kpi("Total Sales", 5850, sheet="Executive Overview"),
            _qlik_kpi("Total Sales", 2900, sheet="Advanced Metrics"),
        ]}
        pbi = {"kpis": [_pbi_kpi("Total Sales", 5850)]}
        rec = reconcile_kpis(qlik, pbi)
        assert len(rec[rec["kpi"] == "Total Sales"]) == 2
