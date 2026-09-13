"""
Tests du générateur de correctifs DAX (src/module_b/dax_fix_generator.py).

Le LLM (ask_claude) est systématiquement mocké — ces tests valident la logique
du module (parsing, garde-fou syntaxique, agrégation de confiance), pas la
qualité des réponses de Mistral lui-même.
"""
import module_b.dax_fix_generator as dfg


# ============================================================
# validate_dax_syntax — garde-fou heuristique
# ============================================================
class TestValidateDaxSyntax:
    def test_valid_simple_calculate(self):
        code = "CALCULATE(SUM('Sales'[Amount]), 'Sales'[Year] = MAX('Sales'[Year]))"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is True
        assert result["avertissements"] == []

    def test_valid_filter_inside_calculate(self):
        code = "CALCULATE(SUM('Sales'[Amount]), FILTER(ALL('Sales'), 'Sales'[Year] = YEAR(TODAY())))"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is True

    def test_invalid_juxtaposed_calls(self):
        # Cas réellement observé : SUM(...) suivi de FILTER(...) sans CALCULATE englobant.
        code = "SUM('Sales'[Sales Amount]) FILTER ('Sales', 'Sales'[Date] <= TODAY())"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is False
        assert len(result["avertissements"]) >= 1

    def test_invalid_unbalanced_parentheses(self):
        code = "CALCULATE(SUM('Sales'[Amount])"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is False
        assert any("parenthèses" in w.lower() for w in result["avertissements"])

    def test_invalid_unbalanced_brackets(self):
        code = "CALCULATE(SUM('Sales'[Amount))"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is False

    def test_empty_code_is_invalid(self):
        result = dfg.validate_dax_syntax("")
        assert result["valide"] is False

    def test_filter_without_enclosing_function(self):
        code = "FILTER('Sales', 'Sales'[Year] = 2026)"
        result = dfg.validate_dax_syntax(code)
        assert result["valide"] is False


# ============================================================
# _parse_response — parsing de la réponse LLM
# ============================================================
class TestParseResponse:
    def test_standard_format(self):
        response = (
            "CAUSE: Filtre différent.\n"
            "DAX_CORRIGE:\n```\nCALCULATE([Total Sales], 'Sales'[Year]=MAX('Sales'[Year]))\n```\n"
            "EXPLICATION: Ca corrige le filtre."
        )
        result = dfg._parse_response(response)
        assert result["cause"] == "Filtre différent."
        assert "CALCULATE" in result["dax_corrige"]
        assert result["explication"] == "Ca corrige le filtre."

    def test_markdown_bold_markers_are_stripped(self):
        response = (
            "**CAUSE:** Filtre différent.\n"
            "**DAX_CORRIGE:**\n```dax\nSUM(Sales[Amount])\n```\n"
            "**EXPLICATION:** Voilà."
        )
        result = dfg._parse_response(response)
        assert not result["cause"].startswith("*")
        assert not result["explication"].startswith("*")

    def test_response_without_expected_format_returns_empty_fields(self):
        response = "Je ne peux pas déterminer la cause exacte sans plus de contexte."
        result = dfg._parse_response(response)
        assert result["cause"] == ""
        assert result["dax_corrige"] == ""
        assert result["brut"] == response


# ============================================================
# generate_dax_fix — orchestration complète (LLM mocké)
# ============================================================
class TestGenerateDaxFix:
    def test_missing_expressions_short_circuits_without_llm_call(self, monkeypatch):
        called = {"n": 0}
        monkeypatch.setattr(dfg, "ask_claude", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or "")
        result = dfg.generate_dax_fix(kpi_qlik="X", expr_qlik=None, expr_pbi=None)
        assert called["n"] == 0
        assert "non disponibles" in result["cause"]

    def test_successful_generation_includes_validation(self, monkeypatch):
        fake_response = (
            "CAUSE: ok\nDAX_CORRIGE:\n```\nCALCULATE(SUM(Sales[Amount]), ALL(Sales))\n```\nEXPLICATION: ok"
        )
        monkeypatch.setattr(dfg, "ask_claude", lambda *a, **k: fake_response)
        result = dfg.generate_dax_fix(expr_qlik="Total Sales", expr_pbi="SUM(Sales[Amount])")
        assert result["validation"]["valide"] is True
        assert "CALCULATE" in result["dax_corrige"]

    def test_invalid_generated_dax_is_flagged(self, monkeypatch):
        fake_response = (
            "CAUSE: ok\nDAX_CORRIGE:\n```\nSUM(Sales[Amount]) FILTER(Sales, Sales[Year]=2026)\n```\nEXPLICATION: ok"
        )
        monkeypatch.setattr(dfg, "ask_claude", lambda *a, **k: fake_response)
        result = dfg.generate_dax_fix(expr_qlik="X", expr_pbi="Y")
        assert result["validation"]["valide"] is False

    def test_timeout_response_is_detected(self, monkeypatch):
        monkeypatch.setattr(
            dfg, "ask_claude",
            lambda *a, **k: "STATUT: ERREUR_PARSING\nMESURE: AUCUNE\nJUSTIFICATION: Timeout Ollama (>90s)",
        )
        result = dfg.generate_dax_fix(expr_qlik="X", expr_pbi="Y")
        assert "temps de répondre" in result["cause"] or "timeout" in result["cause"].lower()
        assert result["dax_corrige"] == ""


# ============================================================
# generate_dax_fix_with_confidence — agrégation sur n runs
# ============================================================
class TestConfidenceGeneration:
    def test_all_runs_valid_and_identical_gives_high_confidence(self, monkeypatch):
        fake_response = (
            "CAUSE: ok\nDAX_CORRIGE:\n```\nCALCULATE(SUM(Sales[Amount]), ALL(Sales))\n```\nEXPLICATION: ok"
        )
        monkeypatch.setattr(dfg, "ask_claude", lambda *a, **k: fake_response)
        result = dfg.generate_dax_fix_with_confidence(expr_qlik="X", expr_pbi="Y", n_runs=3)
        assert result["taux_validite"] == 100.0
        assert result["taux_stabilite"] == 100.0
        assert result["confiance"] == 100.0
        assert result["proposition"]["validation"]["valide"] is True

    def test_mixed_validity_lowers_confidence_but_keeps_valid_proposal(self, monkeypatch):
        responses = [
            "CAUSE: ok\nDAX_CORRIGE:\n```\nCALCULATE(SUM(Sales[Amount]), ALL(Sales))\n```\nEXPLICATION: ok",
            "CAUSE: ok\nDAX_CORRIGE:\n```\nSUM(Sales[Amount]) FILTER(Sales, Sales[Year]=2026)\n```\nEXPLICATION: ok",
        ]
        call_count = {"n": 0}

        def fake_ask(*a, **k):
            r = responses[call_count["n"] % len(responses)]
            call_count["n"] += 1
            return r

        monkeypatch.setattr(dfg, "ask_claude", fake_ask)
        result = dfg.generate_dax_fix_with_confidence(expr_qlik="X", expr_pbi="Y", n_runs=2)
        assert 0 < result["taux_validite"] < 100
        assert result["proposition"]["validation"]["valide"] is True  # doit privilégier la version valide

    def test_confidence_runs_count_matches_n_runs(self, monkeypatch):
        monkeypatch.setattr(dfg, "ask_claude", lambda *a, **k: "CAUSE: x\nDAX_CORRIGE:\n```\nSUM(Sales[Amount])\n```\nEXPLICATION: x")
        result = dfg.generate_dax_fix_with_confidence(expr_qlik="X", expr_pbi="Y", n_runs=4)
        assert result["n_runs"] == 4
        assert len(result["runs"]) == 4