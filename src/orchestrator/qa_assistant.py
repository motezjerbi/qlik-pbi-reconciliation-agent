"""
Assistant Q&A — répond en langage naturel à des questions sur l'audit en
cours (constats, score de santé, écarts...).

Au lieu d'envoyer l'intégralité des constats à chaque question (coûteux en
tokens, donc lent sur un LLM local en CPU), une sélection lexicale simple
retient uniquement les constats pertinents pour la question posée — un
mini-retrieval, pas une vraie base vectorielle, mais suffisant pour le volume
de constats d'un audit de migration (dizaines, pas milliers).

Réutilise le même client LLM (Ollama/Mistral) que le reste du projet.
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from llm.client import ask_claude
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False

    def ask_claude(prompt, timeout: int = 90, num_predict: int = 300):
        return "LLM non disponible."


# Nombre max de constats effectivement envoyés au LLM par question, et longueur
# max par champ texte — les deux leviers qui gardent le prompt court, donc rapide,
# même sur un modèle local en CPU chargé en parallèle de Qlik/PBI Desktop.
TOP_K_FINDINGS = 6
MAX_FIELD_CHARS = 110
MAX_HISTORY_TURNS = 2

_STOPWORDS_FR = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "est", "sont", "dans", "sur",
    "pour", "avec", "qui", "que", "quoi", "quel", "quels", "quelle", "quelles", "ce", "cette",
    "ces", "il", "elle", "ils", "elles", "tu", "vous", "nous", "je", "au", "aux", "en", "par",
    "se", "sa", "son", "ses", "leur", "leurs", "y", "a", "à", "pas", "plus", "moins",
    "comment", "pourquoi", "audit", "constat", "constats",
}

# Mots-clés qui indiquent que la question porte explicitement sur un niveau de
# criticité donné. Dans ce cas, le filtrage est fait par le CODE (exact, fiable),
# pas laissé au LLM — qui a tendance à mélanger les niveaux de criticité même
# quand le contexte les indique clairement (constaté en test).
_CRITICITE_KEYWORDS = {
    "BLOQUANT": ["bloquant", "bloquants", "critique", "critiques", "urgent", "urgents", "urgence"],
    "MAJEUR": ["majeur", "majeurs"],
    "MINEUR": ["mineur", "mineurs"],
}


def _detect_criticite_filter(question: str) -> Optional[str]:
    q_lower = (question or "").lower()
    for criticite, keywords in _CRITICITE_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return criticite
    return None


def _truncate(text: str, max_chars: int = MAX_FIELD_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zàâäéèêëïîôöùûüç0-9]+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS_FR and len(w) > 2}


def _select_relevant_findings(question: str, findings: List[Dict], top_k: int = TOP_K_FINDINGS):
    """Sélectionne les constats à envoyer au LLM pour cette question.

    Retourne (constats_sélectionnés, filtre_criticite_appliqué). Si la question
    porte explicitement sur un niveau de criticité (ex. "points bloquants"), le
    filtrage est déterministe (fait ici, par le code) plutôt que laissé au LLM.
    Sinon, retrieval lexical classique comme fallback."""
    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}

    forced_criticite = _detect_criticite_filter(question)
    if forced_criticite is not None:
        matching = [f for f in findings if f.get("criticite") == forced_criticite]
        return matching[:30], forced_criticite

    q_tokens = _tokenize(question)

    def _score(f: Dict) -> int:
        f_tokens = _tokenize(f"{f.get('libelle', '')} {f.get('detail', '')} {f.get('diagnostic', '')}")
        return len(q_tokens & f_tokens)

    scored = [(_score(f), f) for f in findings]

    if q_tokens and any(s > 0 for s, _ in scored):
        scored.sort(key=lambda sf: (-sf[0], ordre.get(sf[1].get("criticite"), 3)))
    else:
        scored.sort(key=lambda sf: ordre.get(sf[1].get("criticite"), 3))

    return [f for _, f in scored[:top_k]], None


def _build_context(
    question: str,
    findings: List[Dict],
    health_score: Optional[int] = None,
    health_niveau: Optional[str] = None,
    coverage_rate: Optional[float] = None,
):
    bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
    majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
    mineur = sum(1 for f in findings if f.get("criticite") == "MINEUR")

    lines = [
        f"Total constats : {len(findings)} ({bloquant} bloquants, {majeur} majeurs, {mineur} mineurs).",
    ]
    if health_score is not None:
        lines.append(f"Score de santé global : {health_score}/100 ({health_niveau or '—'}).")
    if coverage_rate is not None:
        lines.append(f"Taux de couverture fonctionnelle (Module B) : {coverage_rate:.0f}%.")

    # Répartition exacte par module d'origine, calculée par le code (pas par le
    # LLM) — pour les questions de comptage/comparaison entre modules, l'agent
    # doit utiliser ces chiffres directement plutôt que recompter lui-même sur
    # une liste de constats potentiellement tronquée par la sélection ci-dessous.
    by_module: Dict[str, Dict[str, int]] = {}
    for f in findings:
        mod = f.get("source_module", "Inconnu") or "Inconnu"
        crit = f.get("criticite", "MINEUR")
        by_module.setdefault(mod, {"BLOQUANT": 0, "MAJEUR": 0, "MINEUR": 0})
        if crit in by_module[mod]:
            by_module[mod][crit] += 1
    if by_module:
        lines.append("")
        lines.append("Répartition exacte par module d'origine (chiffres officiels, ne pas recompter) :")
        for mod, counts in by_module.items():
            total_mod = sum(counts.values())
            lines.append(
                f"- {mod} : {total_mod} constat(s) au total "
                f"({counts['BLOQUANT']} bloquant(s), {counts['MAJEUR']} majeur(s), {counts['MINEUR']} mineur(s))"
            )

    selected, forced_criticite = _select_relevant_findings(question, findings)

    lines.append("")
    if forced_criticite is not None:
        lines.append(
            f"⚠️ Liste déjà filtrée par le système : UNIQUEMENT les constats de "
            f"criticité {forced_criticite} ({len(selected)} au total). Ne mentionne "
            f"aucun autre constat, n'ajoute aucun élément d'un autre niveau de criticité."
        )
    else:
        lines.append(
            f"Constats les plus pertinents pour cette question "
            f"({len(selected)} sur {len(findings)} au total) :"
        )

    for i, f in enumerate(selected, 1):
        lines.append(
            f"{i}. [{f.get('criticite', 'MINEUR')}] {_truncate(f.get('libelle', ''), 80)} "
            f"(origine: {f.get('source_module', '')})\n"
            f"   Détail: {_truncate(f.get('detail', ''))}\n"
            f"   Diagnostic: {_truncate(f.get('diagnostic', ''))}\n"
            f"   Recommandation: {_truncate(f.get('recommandation', ''))}"
        )
    if not selected:
        lines.append("(Aucun constat ne correspond à ce filtre.)")

    return "\n".join(lines), forced_criticite, selected


def _format_findings_fallback(selected: List[Dict], forced_criticite: Optional[str]) -> str:
    """Réponse de secours 100% calculée (aucun LLM) — utilisée quand le modèle
    local ne répond pas à temps, pour que l'utilisateur ait toujours quelque
    chose d'exploitable plutôt qu'un simple message d'erreur."""
    if not selected:
        return "Aucun constat pertinent identifié pour cette question."

    lines = []
    if forced_criticite is not None:
        lines.append(f"Constats de criticité {forced_criticite} ({len(selected)}) :")
    else:
        lines.append(f"Constats les plus pertinents trouvés pour cette question ({len(selected)}) :")

    for f in selected:
        lines.append(
            f"- [{f.get('criticite', 'MINEUR')}] {f.get('libelle', '')} "
            f"— {_truncate(f.get('detail', ''), 150)}"
        )
        if f.get("recommandation"):
            lines.append(f"  Recommandation : {_truncate(f.get('recommandation', ''), 150)}")

    return "\n".join(lines)


def _detect_module_comparison_question(question: str) -> bool:
    """Détecte une question de comptage/comparaison ENTRE modules — traitée en
    dur par le code (voir _answer_module_stats_deterministic), pas envoyée au
    LLM. Constaté en test : même avec les chiffres exacts fournis dans son
    contexte, le petit modèle local se trompe encore en recomptant lui-même."""
    q = (question or "").lower()
    has_module_kw = "module" in q
    has_compare_or_count_kw = any(
        kw in q for kw in ["combien", "compare", "comparer", "lequel", "laquelle", "nombre de", "plus de"]
    )
    return has_module_kw and has_compare_or_count_kw


def _answer_module_stats_deterministic(findings: List[Dict]) -> str:
    """Réponse 100% calculée par le code — aucun appel LLM, donc aucune place
    à l'erreur de comptage ni au timeout."""
    by_module: Dict[str, Dict[str, int]] = {}
    for f in findings:
        mod = f.get("source_module", "Inconnu") or "Inconnu"
        crit = f.get("criticite", "MINEUR")
        by_module.setdefault(mod, {"BLOQUANT": 0, "MAJEUR": 0, "MINEUR": 0})
        if crit in by_module[mod]:
            by_module[mod][crit] += 1

    if not by_module:
        return "Aucun constat disponible pour établir une répartition par module."

    lines = ["Répartition exacte des constats par module d'origine :"]
    for mod, counts in sorted(by_module.items(), key=lambda kv: -kv[1]["BLOQUANT"]):
        total_mod = sum(counts.values())
        lines.append(
            f"- **{mod}** : {total_mod} constat(s) — {counts['BLOQUANT']} bloquant(s), "
            f"{counts['MAJEUR']} majeur(s), {counts['MINEUR']} mineur(s)"
        )

    max_bloquant = max(counts["BLOQUANT"] for counts in by_module.values())
    if max_bloquant > 0:
        leaders = [mod for mod, counts in by_module.items() if counts["BLOQUANT"] == max_bloquant]
        if len(leaders) == 1:
            lines.append(f"\nLe module avec le plus de constats bloquants est **{leaders[0]}** ({max_bloquant}).")
        else:
            lines.append(f"\nÉgalité entre {' et '.join(leaders)}, {max_bloquant} bloquant(s) chacun.")
    else:
        lines.append("\nAucun module n'a de constat bloquant.")

    lines.append("\n*(Réponse calculée directement, sans passer par le LLM — garantie exacte.)*")
    return "\n".join(lines)


def answer_question(
    question: str,
    findings: List[Dict],
    health_score: Optional[int] = None,
    health_niveau: Optional[str] = None,
    coverage_rate: Optional[float] = None,
    history: Optional[List[Dict]] = None,
) -> str:
    """Répond en langage naturel à partir des constats de l'audit courant."""
    if not findings:
        return "Aucun constat d'audit disponible pour l'instant — génère d'abord un rapport consolidé (section 04)."

    if not question or not question.strip():
        return "Pose une question sur l'audit (ex. « Quels sont les points bloquants ? »)."

    # Comptage/comparaison entre modules : réponse déterministe, pas de LLM.
    if _detect_module_comparison_question(question):
        return _answer_module_stats_deterministic(findings)

    if not LLM_DISPONIBLE:
        return "L'assistant Q&A nécessite le client LLM (Ollama/Mistral), actuellement indisponible."

    context, forced_criticite, selected = _build_context(question, findings, health_score, health_niveau, coverage_rate)

    history_block = ""
    if history:
        recent = history[-MAX_HISTORY_TURNS:]
        turns = "\n".join(f"Q: {h['question']}\nR: {h['answer']}" for h in recent)
        history_block = f"\n## HISTORIQUE RÉCENT DE LA CONVERSATION\n{turns}\n"

    filter_instruction = (
        f"La liste ci-dessus est DÉJÀ filtrée sur la criticité {forced_criticite} par le "
        f"système — cite-la intégralement et fidèlement, ne filtre pas toi-même, "
        f"n'omets aucun élément, n'en ajoute aucun d'un autre niveau."
        if forced_criticite is not None
        else "Base-toi UNIQUEMENT sur les données ci-dessus."
    )

    prompt = f"""Tu es un assistant qui aide un consultant à comprendre un audit de migration Qlik Sense vers Power BI.

## DONNÉES DE L'AUDIT (sélection pertinente pour la question)
{context}
{history_block}
## QUESTION DU CONSULTANT
{question}

## INSTRUCTIONS
Réponds en français, de façon concise (3-5 phrases, sauf si la question demande
explicitement une liste — dans ce cas, liste chaque élément). {filter_instruction}

Règles supplémentaires :
- Question de comptage ou de comparaison entre modules ("combien de...", "lequel
  a le plus de...") : utilise EXCLUSIVEMENT la section "Répartition exacte par
  module" ci-dessus, donne le chiffre exact en premier dans ta réponse, ne
  recompte pas toi-même à partir de la liste de constats détaillés.
- Question qui compare plusieurs constats nommément (ex. "X et Y ont-ils la
  même cause ?") : examine le champ Diagnostic de CHAQUE constat séparément et
  dis explicitement s'ils sont identiques ou différents — ne fusionne jamais
  deux diagnostics distincts en une explication moyenne si les causes citées
  dans les données sont différentes.
- Si la question porte sur un constat absent de cette sélection, dis-le
  clairement plutôt que d'inventer une réponse.
"""

    fallback_note = (
        "Le modèle IA local n'a pas pu répondre à temps. Voici, à la place, les "
        "constats les plus pertinents trouvés automatiquement pour ta question "
        "(réponse calculée, sans reformulation par l'IA) :\n\n"
    )

    try:
        response = ask_claude(prompt, timeout=220, num_predict=220)
    except Exception:
        return fallback_note + _format_findings_fallback(selected, forced_criticite)

    lowered = (response or "").lower()
    if response.strip().upper().startswith("STATUT: ERREUR_PARSING") or "timeout" in lowered:
        return fallback_note + _format_findings_fallback(selected, forced_criticite)

    return response.strip()