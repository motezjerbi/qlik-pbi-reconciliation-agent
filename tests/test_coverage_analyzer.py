# tests/test_coverage_analyzer.py
"""
Tests de non-regression pour coverage_analyzer.py (Module B, moteur par regles).
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
        patterns = analyzer.detect_patterns("ApplyMap(''MAP'', ProductID, ''N/A'')", "")
        assert any(p["pattern"] == "mapping_applymap" for p in patterns)

    def test_ignore_texte_sans_pattern(self):
        analyzer = FunctionalCoverageAnalyzer()
        patterns = analyzer.detect_patterns("SELECT * FROM nulle_part", "")
        assert patterns == []


class TestMatchingGeneriqueParMotsCles:
    def test_matche_une_mesure_inconnue_par_mot_cle_calculate(self):
        analyzer = FunctionalCoverageAnalyzer()
        mesures = [{"name": "Mesure Totalement Inedite XYZ", "dax": "CALCULATE(SUM(T[C]), FILTER(T, T[Y]=2025))"}]
        candidate = analyzer._find_matching_measure("set_analysis", mesures)
        assert candidate is not None
        assert candidate["name"] == "Mesure Totalement Inedite XYZ"

    def test_ne_matche_rien_si_aucun_mot_cle_present(self):
        analyzer = FunctionalCoverageAnalyzer()
        mesures = [{"name": "Mesure Sans Rapport", "dax": "SUM(T[Colonne])"}]
        candidate = analyzer._find_matching_measure("mapping_applymap", mesures)
        assert candidate is None

    def test_pattern_sans_mot_cle_dax_ne_matche_jamais(self):
        analyzer = FunctionalCoverageAnalyzer()
        mesures = [{"name": "N''importe Quoi", "dax": "CALCULATE(SUM(T[C]))"}]
        candidate = analyzer._find_matching_measure("load_inline", mesures)
        assert candidate is None


class TestAnalyzeCoverageQuick:
    def test_pipeline_complet_sans_erreur(self):
        script = "SET vCurrentYear = Year(Today());\nApplyMap(''MAP'', ProductID, ''N/A'')"
        expressions = "Sum({<Year={$(vCurrentYear)}>} SalesAmount)"
        mesures = [{"name": "Total Sales", "dax": "SUM(Sales[Amount])"}]
        result = analyze_coverage_quick(script, expressions, mesures)
        assert "error" not in result
        assert result["total_patterns"] > 0

    def test_liste_vide_mesures_ne_plante_pas(self):
        result = analyze_coverage_quick("ApplyMap(''X'', Y, ''Z'')", "", [])
        assert "error" not in result
