"""
Génération automatique de correctifs DAX — extension du Module B.

Pour un écart de réconciliation (KPI Qlik vs mesure Power BI divergente),
interroge le LLM local (même client Ollama/Mistral que mapping.py) pour :
  1. diagnostiquer la cause probable de l'écart,
  2. proposer une expression DAX corrigée reproduisant fidèlement la logique
     de l'expression Qlik d'origine,
  3. expliquer brièvement la correction.

Réutilise volontairement `llm.client.ask_claude` (déjà connecté à Ollama /
mistral ailleurs dans le projet) plutôt que de dupliquer une connexion LLM
séparée.
"""
import sys
from pathlib import Path
from typing import Dict, Optional
import re

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from llm.client import ask_claude
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False

    def ask_claude(prompt, timeout: int = 90, num_predict: int = 300):
        return "LLM non disponible."


def validate_dax_syntax(dax_code: str) -> Dict:
    """Garde-fou heuristique — PAS un vrai parseur DAX complet, juste des
    vérifications simples qui attrapent les erreurs les plus fréquentes des
    petits LLM locaux (ex. FILTER() juxtaposé sans CALCULATE(), parenthèses
    déséquilibrées). Objectif : signaler un doute, pas garantir la validité.

    Retourne {'valide': bool, 'avertissements': [str, ...]}.
    """
    warnings: list = []
    code = (dax_code or "").strip()

    if not code:
        return {"valide": False, "avertissements": ["Code vide."]}

    # 1. Parenthèses équilibrées.
    if code.count("(") != code.count(")"):
        warnings.append(
            f"Parenthèses déséquilibrées ({code.count('(')} ouvrantes, {code.count(')')} fermantes)."
        )

    # 2. Crochets de colonnes équilibrés (Table[Colonne]).
    if code.count("[") != code.count("]"):
        warnings.append("Crochets de référence de colonne déséquilibrés ([...]).")

    # 3. Deux appels de fonction juxtaposés sans opérateur/virgule entre eux —
    #    exactement le pattern fautif vu en pratique : "SUM(...) FILTER(...)".
    juxtaposition = re.search(r"\)\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", code)
    if juxtaposition:
        snippet = code[max(0, juxtaposition.start() - 15):juxtaposition.end() + 5]
        warnings.append(
            f"Deux appels de fonction semblent juxtaposés sans opérateur ni virgule "
            f"entre eux (near « ...{snippet}... »)  — probable erreur de syntaxe."
        )

    # 4. FILTER( utilisé sans fonction englobante connue qui l'accepte comme argument.
    if re.search(r"\bFILTER\s*\(", code, re.IGNORECASE):
        englobantes = ("CALCULATE", "CALCULATETABLE", "SUMX", "COUNTX", "AVERAGEX", "MAXX", "MINX", "FILTER")
        if not any(re.search(rf"\b{fn}\s*\(", code, re.IGNORECASE) for fn in englobantes if fn != "FILTER"):
            warnings.append(
                "FILTER(...) est présent sans CALCULATE / CALCULATETABLE / SUMX (etc.) "
                "englobant détecté — FILTER seul n'est pas une syntaxe DAX valide en dehors "
                "d'un argument de table."
            )

    return {"valide": len(warnings) == 0, "avertissements": warnings}


def _build_prompt(
    kpi_qlik: Optional[str],
    kpi_pbi: Optional[str],
    expr_qlik: Optional[str],
    expr_pbi: Optional[str],
    valeur_qlik,
    valeur_pbi,
    statut: str,
) -> str:
    return f"""Tu es un expert DAX et Qlik Sense, migration Qlik → Power BI.

## ÉCART DÉTECTÉ
KPI Qlik "{kpi_qlik or '—'}" : {expr_qlik or '(expression non disponible)'} → valeur {valeur_qlik}
Mesure PBI "{kpi_pbi or '—'}" : {expr_pbi or '(expression non disponible)'} → valeur {valeur_pbi}
Statut : {statut}

## TÂCHE
Diagnostique la cause probable de l'écart, propose une expression DAX corrigée
courte et prête à l'emploi, explique brièvement.

## FORMAT DE RÉPONSE OBLIGATOIRE (concis, pas de texte hors de ces 3 sections) :
CAUSE: [1 phrase]
DAX_CORRIGE:
```
[expression DAX corrigée]
```
EXPLICATION: [1-2 phrases]
"""


def _parse_response(response: str) -> Dict[str, str]:
    result = {"cause": "", "dax_corrige": "", "explication": "", "brut": response}
    text = (response or "").strip()
    if not text:
        return result

    # Marqueurs tolérants : casse variable, gras markdown optionnel (**CAUSE:**),
    # espace optionnel avant les deux-points.
    def _extract(label: str, stop_labels: list) -> str:
        pattern = rf"\*{{0,2}}{label}\*{{0,2}}\s*:\s*"
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return ""
        start = m.end()
        end = len(text)
        for stop in stop_labels:
            stop_pattern = rf"\*{{0,2}}{stop}\*{{0,2}}\s*:"
            sm = re.search(stop_pattern, text[start:], re.IGNORECASE)
            if sm:
                end = min(end, start + sm.start())
        return text[start:end].strip().lstrip("*").strip()

    result["cause"] = _extract("CAUSE", ["DAX_CORRIGE", "EXPLICATION"])
    result["explication"] = _extract("EXPLICATION", [])

    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            code = parts[1]
            code_lines = code.splitlines()
            if code_lines and code_lines[0].strip().lower() in ("dax", "sql", ""):
                code_lines = code_lines[1:]
            result["dax_corrige"] = "\n".join(code_lines).strip()
    else:
        # Pas de bloc ``` : tenter quand même d'isoler la section DAX_CORRIGE.
        dax_section = _extract("DAX_CORRIGE", ["EXPLICATION"])
        if dax_section:
            result["dax_corrige"] = dax_section

    return result


def generate_dax_fix(
    kpi_qlik: Optional[str] = None,
    kpi_pbi: Optional[str] = None,
    expr_qlik: Optional[str] = None,
    expr_pbi: Optional[str] = None,
    valeur_qlik=None,
    valeur_pbi=None,
    statut: str = "",
    timeout: int = 180,
    num_predict: int = 400,
) -> Dict[str, str]:
    """Retourne {'cause', 'dax_corrige', 'explication', 'brut', 'validation'}."""
    if not LLM_DISPONIBLE:
        return {
            "cause": "LLM non disponible.",
            "dax_corrige": "",
            "explication": "Vérifie qu'Ollama tourne avec le modèle configuré (voir logs au démarrage de l'app).",
            "brut": "",
            "validation": {"valide": False, "avertissements": []},
        }

    if not expr_qlik and not expr_pbi:
        return {
            "cause": "Expressions non disponibles pour ce constat.",
            "dax_corrige": "",
            "explication": "La génération automatique nécessite au moins l'expression Qlik ou l'expression DAX.",
            "brut": "",
            "validation": {"valide": False, "avertissements": []},
        }

    prompt = _build_prompt(kpi_qlik, kpi_pbi, expr_qlik, expr_pbi, valeur_qlik, valeur_pbi, statut)
    try:
        # Génération plus longue que le format 3-lignes de mapping.py (cause +
        # code DAX + explication) : timeout et budget de tokens élargis par défaut.
        # Paramétrables pour les runs multiples (vérification de confiance), où
        # on réduit volontairement pour limiter le temps total.
        response = ask_claude(prompt, timeout=timeout, num_predict=num_predict)
    except Exception as e:
        return {
            "cause": f"Erreur LLM : {e}",
            "dax_corrige": "",
            "explication": "",
            "brut": "",
            "validation": {"valide": False, "avertissements": []},
        }

    # ask_claude() renvoie un message d'erreur générique (format STATUT/MESURE/
    # JUSTIFICATION hérité de mapping.py) en cas de timeout ou d'échec Ollama —
    # à distinguer d'une vraie réponse hors format, pour donner un message clair.
    lowered = (response or "").lower()
    if "timeout" in lowered or response.strip().upper().startswith("STATUT: ERREUR_PARSING"):
        return {
            "cause": "Le modèle local (Ollama) a mis trop de temps à répondre (timeout).",
            "dax_corrige": "",
            "explication": (
                "Réessaie dans quelques secondes. Si ça persiste, évite de faire tourner "
                "Qlik Sense Desktop et Power BI Desktop en même temps que la génération — "
                "ça sature le CPU/RAM et ralentit fortement Ollama en local."
            ),
            "brut": response,
            "validation": {"valide": False, "avertissements": []},
        }

    result = _parse_response(response)
    if result.get("dax_corrige"):
        result["validation"] = validate_dax_syntax(result["dax_corrige"])
    else:
        result["validation"] = {"valide": False, "avertissements": []}
    return result


def generate_dax_fix_with_confidence(
    kpi_qlik: Optional[str] = None,
    kpi_pbi: Optional[str] = None,
    expr_qlik: Optional[str] = None,
    expr_pbi: Optional[str] = None,
    valeur_qlik=None,
    valeur_pbi=None,
    statut: str = "",
    n_runs: int = 3,
) -> Dict:
    """Génère le correctif DAX `n_runs` fois et mesure un indicateur de confiance :
    - taux_validite : proportion des générations syntaxiquement valides.
    - taux_stabilite : similarité moyenne du code DAX généré entre les runs
      (même principe que la mesure de stabilité de la page 05, appliqué ici au
      texte du code plutôt qu'à un statut catégoriel).
    - confiance : moyenne des deux, comme score global à afficher.

    Plus lent qu'un seul appel (n_runs appels LLM séquentiels) — à utiliser à la
    demande, pas systématiquement.
    """
    import difflib

    runs = []
    for _ in range(max(1, n_runs)):
        r = generate_dax_fix(
            kpi_qlik=kpi_qlik, kpi_pbi=kpi_pbi, expr_qlik=expr_qlik, expr_pbi=expr_pbi,
            valeur_qlik=valeur_qlik, valeur_pbi=valeur_pbi, statut=statut,
            timeout=100, num_predict=300,  # plus court par run pour limiter le temps total
        )
        runs.append(r)

    dax_versions = [r["dax_corrige"] for r in runs if r.get("dax_corrige")]
    valid_count = sum(1 for r in runs if r.get("dax_corrige") and r.get("validation", {}).get("valide"))
    taux_validite = round(valid_count / len(runs) * 100, 1) if runs else 0.0

    if len(dax_versions) >= 2:
        pairs = [
            difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()
            for i, a in enumerate(dax_versions) for b in dax_versions[i + 1:]
        ]
        taux_stabilite = round((sum(pairs) / len(pairs)) * 100, 1) if pairs else 0.0
    elif len(dax_versions) == 1:
        taux_stabilite = 100.0
    else:
        taux_stabilite = 0.0

    confiance = round((taux_validite + taux_stabilite) / 2, 1)

    # Proposition retenue : la première génération valide ; sinon la première
    # génération non vide ; sinon la dernière (message d'erreur/timeout).
    retenue = next(
        (r for r in runs if r.get("dax_corrige") and r.get("validation", {}).get("valide")),
        next((r for r in runs if r.get("dax_corrige")), runs[-1] if runs else {}),
    )

    return {
        "proposition": retenue,
        "runs": runs,
        "taux_validite": taux_validite,
        "taux_stabilite": taux_stabilite,
        "confiance": confiance,
        "n_runs": len(runs),
    }