"""
Tests de l'assistant Q&A (src/orchestrator/qa_assistant.py).

Le LLM est mocké partout — ces tests valident la logique déterministe
(filtrage par criticité, comptage par module, retrieval lexical, fallback
anti-timeout), qui est justement la partie du système censée être fiable
indépendamment du LLM.
"""
import orchestrator.qa_assistant as qa


def _findings():
    return [
        {"criticite": "BLOQUANT", "libelle": "Current Year Sales — ECART_VALEUR",
         "source_module": "Réconciliation de données", "detail": "Qlik=0 | PBI=4100",
         "diagnostic": "Filtre d'année différent.", "recommandation": "Aligner Max(Year)."},
        {"criticite": "BLOQUANT", "libelle": "Total Sales — ECART_VALEUR",
         "source_module": "Réconciliation de données", "detail": "Qlik=2900 | PBI=5850",
         "diagnostic": "Exclusion région différente.", "recommandation": "Vérifier les filtres."},
        {"criticite": "MAJEUR", "libelle": "Colonne malformée",
         "source_module": "Module A - Structural Gaps", "detail": "ChannelID;ChannelName",
         "diagnostic": "Erreur Power Query.", "recommandation": "Corriger le délimiteur."},
        {"criticite": "MINEUR", "libelle": "Table isolée",
         "source_module": "Module A - Structural Gaps", "detail": "SalesChannels",
         "diagnostic": "Pas de relation.", "recommandation": "Vérifier si voulu."},
    ]


# ============================================================
# Détection de filtre par criticité (déterministe)
# ============================================================
class TestCriticiteFilter:
    def test_detects_bloquant(self):
        assert qa._detect_criticite_filter("Quels sont les points bloquants ?") == "BLOQUANT"

    def test_detects_majeur(self):
        assert qa._detect_criticite_filter("Liste les constats majeurs") == "MAJEUR"

    def test_no_match_returns_none(self):
        assert qa._detect_criticite_filter("Résume l'audit") is None

    def test_select_relevant_findings_filters_exactly(self):
        selected, forced = qa._select_relevant_findings("Quels sont les points bloquants ?", _findings())
        assert forced == "BLOQUANT"
        assert len(selected) == 2
        assert all(f["criticite"] == "BLOQUANT" for f in selected)


# ============================================================
# Comptage/comparaison par module (déterministe, sans LLM)
# ============================================================
class TestModuleComparison:
    def test_detects_comparison_question(self):
        q = "Compare le nombre de problèmes venant du Module A structurel vs de la réconciliation"
        assert qa._detect_module_comparison_question(q) is True

    def test_does_not_trigger_on_unrelated_question(self):
        assert qa._detect_module_comparison_question("Pourquoi Total Sales est en écart ?") is False

    def test_deterministic_answer_has_correct_counts(self):
        answer = qa._answer_module_stats_deterministic(_findings())
        assert "Réconciliation de données" in answer
        assert "2 bloquant" in answer
        assert "Module A - Structural Gaps" in answer
        assert "0 bloquant" in answer
        assert "sans passer par le LLM" in answer

    def test_answer_question_routes_to_deterministic_path(self, monkeypatch):
        # Le LLM ne doit JAMAIS être appelé pour ce type de question.
        called = {"n": 0}
        monkeypatch.setattr(qa, "ask_claude", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or "")
        answer = qa.answer_question(
            "Compare le nombre de problèmes du Module A vs la réconciliation — lequel a le plus de bloquants ?",
            _findings(),
        )
        assert called["n"] == 0
        assert "Réconciliation de données" in answer


# ============================================================
# Retrieval lexical (fallback quand pas de filtre déterministe)
# ============================================================
class TestLexicalRetrieval:
    def test_relevant_finding_ranked_first(self):
        selected, forced = qa._select_relevant_findings(
            "Pourquoi Current Year Sales est-il en écart ?", _findings()
        )
        assert forced is None
        assert selected[0]["libelle"] == "Current Year Sales — ECART_VALEUR"

    def test_general_question_falls_back_to_severity_order(self):
        selected, forced = qa._select_relevant_findings("Résumé ?", _findings())
        assert forced is None
        # Sans recoupement lexical utile, l'ordre doit être par criticité.
        criticites = [f["criticite"] for f in selected]
        assert criticites == sorted(criticites, key=lambda c: {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}[c])


# ============================================================
# answer_question — comportements généraux et fallback anti-timeout
# ============================================================
class TestAnswerQuestion:
    def test_no_findings(self):
        answer = qa.answer_question("Une question", [])
        assert "Aucun constat" in answer

    def test_empty_question(self):
        answer = qa.answer_question("   ", _findings())
        assert "Pose une question" in answer

    def test_successful_llm_response_is_returned_as_is(self, monkeypatch):
        monkeypatch.setattr(qa, "ask_claude", lambda *a, **k: "Voici une réponse claire et utile.")
        answer = qa.answer_question("Pourquoi Total Sales est en écart ?", _findings())
        assert answer == "Voici une réponse claire et utile."

    def test_timeout_triggers_deterministic_fallback_not_empty_error(self, monkeypatch):
        monkeypatch.setattr(
            qa, "ask_claude",
            lambda *a, **k: "STATUT: ERREUR_PARSING\nMESURE: AUCUNE\nJUSTIFICATION: Timeout Ollama (>90s)",
        )
        answer = qa.answer_question("Pourquoi Current Year Sales est-il en écart ?", _findings())
        # Le fallback doit contenir des données concrètes, pas juste "réessaie".
        assert "Current Year Sales" in answer
        assert "n'a pas pu répondre à temps" in answer

    def test_llm_exception_also_triggers_fallback(self, monkeypatch):
        def _raise(*a, **k):
            raise RuntimeError("connexion perdue")
        monkeypatch.setattr(qa, "ask_claude", _raise)
        answer = qa.answer_question("Pourquoi Total Sales est en écart ?", _findings())
        assert "Total Sales" in answer  # toujours une réponse exploitable


# ============================================================
# Tokenisation (utilitaire de base du retrieval)
# ============================================================
class TestTokenize:
    def test_removes_stopwords_and_short_words(self):
        tokens = qa._tokenize("Quels sont les points bloquants de cet audit ?")
        assert "bloquants" in tokens
        assert "les" not in tokens
        assert "de" not in tokens