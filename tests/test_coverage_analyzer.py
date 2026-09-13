# tests/test_coverage_analyzer.py
"""
Tests de non-régression pour coverage_analyzer.py (Module B, moteur par règles).

Objectif principal : garantir que le matching reste GÉNÉRIQUE (mots-clés DAX
dans les vraies expressions) et ne redevienne jamais une liste de noms de
mesures codés en dur pour sales_demo — c'est le bug qu'on a corrigé au début
du travail sur le Module B.

Lancer : pytest tests/test_coverage_analyzer.py -v
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from module_b.coverage_analyzer import FunctionalCoverageAnalyzer, analyze_coverage_quick


class TestDetectionPatterns:
    def test_detecte_set_analysis(self):
        analyzer = FunctionalCoverageAnalyzer()
        patterns = analyzer.detect_patterns("Sum({<Year={2025}>} Sales)", "")
        assert any(p["pattern"] == "set_analysis" for p in patterns)

    def test_detecte_applymap(self):
        analyzer = FunctionalCoverageAnalyzer()
        patterns = analyzer.detect_patterns("ApplyMap('MAP', ProductID, 'N/A')", "")
        assert any(p["pattern"] == "mapping_applymap" for p in patterns)

    def test_ignore_texte_sans_pattern(self):
        analyzer = FunctionalCoverageAnalyzer()
        patterns = analyzer.detect_patterns("SELECT * FROM nulle_part", "")
        assert patterns == []


class TestMatchingGeneriqueParMotsCles:
    """C'est LE test qui doit échouer si quelqu'un réintroduit un jour une
    liste de noms de mesures codés en dur dans _find_matching_measure."""

    def test_matche_une_mesure_inconnue_par_mot_cle_calculate(self):
        analyzer = FunctionalCoverageAnalyzer()
        # Nom de mesure volontairement absent de tout projet connu (pas
        # "Total Sales", pas "Current Year Sales"...) pour prouver que le
        # matching ne dépend pas d'un nom précis, juste du contenu DAX.
        mesures = [{"name": "Mesure Totalement Inedite XYZ", "dax": "CALCULATE(SUM(T[C]), FILTER(T, T[Y]=2025))"}]
        candidate = analyzer._find_matching_measure("set_analysis", mesures)
        assert candidate is not None
        assert candidate["name"] == "Mesure Totalement Inedite XYZ"

    def test_ne_matche_rien_si_aucun_mot_cle_present(self):
        analyzer = FunctionalCoverageAnalyzer()
        mesures = [{"name": "Mesure Sans Rapport", "dax": "SUM(T[Colonne])"}]
        candidate = analyzer._find_matching_measure("mapping_applymap", mesures)  # attend LOOKUPVALUE
        assert candidate is None

    def test_pattern_sans_mot_cle_dax_ne_matche_jamais(self):
        """load_inline n'a pas de mot-clé DAX associé (concept de source de
        données, pas de mesure) : ne doit jamais renvoyer de mesure."""
        analyzer = FunctionalCoverageAnalyzer()
        mesures = [{"name": "N'importe Quoi", "dax": "CALCULATE(SUM(T[C]))"}]
        candidate = analyzer._find_matching_measure("load_inline", mesures)
        assert candidate is None


class TestMatchingPowerQuery:
    """Certains patterns Qlik (chargement/jointure) doivent se vérifier côté
    Power Query (M), pas côté DAX — ajout suite au constat que le Module B
    ignorait totalement Power Query alors que la mission le demande."""

    def test_resident_group_by_matche_via_table_group_m(self):
        analyzer = FunctionalCoverageAnalyzer()
        pq = [{"table": "Sales", "m_code": "Table.Group(Source, {\"CustomerID\"}, {{\"Total\", each 1}})"}]
        candidate = analyzer._find_matching_measure("resident_group_by", [], pq)
        assert candidate is not None
        assert candidate["source"] == "Power Query"

    def test_left_join_matche_via_table_nestedjoin_m(self):
        analyzer = FunctionalCoverageAnalyzer()
        pq = [{"table": "Sales", "m_code": "Table.NestedJoin(Sales, {\"ID\"}, Customers, {\"ID\"}, \"C\", JoinKind.LeftOuter)"}]
        candidate = analyzer._find_matching_measure("left_join", [], pq)
        assert candidate is not None
        assert candidate["source"] == "Power Query"

    def test_aucun_power_query_ne_matche_rien(self):
        analyzer = FunctionalCoverageAnalyzer()
        candidate = analyzer._find_matching_measure("resident_group_by", [], [])
        assert candidate is None

    def test_analyze_coverage_accepte_power_query_optionnel(self):
        script = "Resident Sales Group By CustomerID"
        pq = [{"table": "Sales", "m_code": "Table.Group(Source, {\"CustomerID\"}, {})"}]
        result = analyze_coverage_quick(script, "", [], pq)
        assert "error" not in result
        detail = next(d for d in result["details"] if d["pattern"] == "resident_group_by")
        assert detail["source_equivalent"] == "Power Query"


class TestSectionAccessRLS:
    """Section Access ne doit plus être un statut figé — il doit refléter
    la vraie présence (ou absence) de rôles RLS côté Power BI."""

    def test_sans_aucun_role_est_non_couvert_bloquant(self):
        result = analyze_coverage_quick("Section Access\nLOAD * INLINE [A];", "", [], [], [])
        d = next(x for x in result["details"] if x["pattern"] == "section_access")
        assert d["statut"] == "NON_COUVERT"
        assert d["criticite"] == "BLOQUANT"

    def test_role_sans_filtre_reste_bloquant(self):
        roles = [{"role": "Manager", "table": "", "filter_expression": ""}]
        result = analyze_coverage_quick("Section Access\nLOAD * INLINE [A];", "", [], [], roles)
        d = next(x for x in result["details"] if x["pattern"] == "section_access")
        assert d["criticite"] == "BLOQUANT"

    def test_role_avec_filtre_devient_partiellement_couvert(self):
        roles = [{"role": "Manager", "table": "Sales", "filter_expression": "[Region] = 'East'"}]
        result = analyze_coverage_quick("Section Access\nLOAD * INLINE [A];", "", [], [], roles)
        d = next(x for x in result["details"] if x["pattern"] == "section_access")
        assert d["statut"] == "PARTIELLEMENT_COUVERT"
        assert d["source_equivalent"] == "RLS"


class TestAnalyzeCoverageQuick:
    def test_pipeline_complet_sans_erreur(self):
        script = "SET vCurrentYear = Year(Today());\nApplyMap('MAP', ProductID, 'N/A')"
        expressions = "Sum({<Year={$(vCurrentYear)}>} SalesAmount)"
        mesures = [{"name": "Total Sales", "dax": "SUM(Sales[Amount])"}]
        result = analyze_coverage_quick(script, expressions, mesures)
        assert "error" not in result
        assert result["total_patterns"] > 0

    def test_liste_vide_mesures_ne_plante_pas(self):
        result = analyze_coverage_quick("ApplyMap('X', Y, 'Z')", "", [])
        assert "error" not in result