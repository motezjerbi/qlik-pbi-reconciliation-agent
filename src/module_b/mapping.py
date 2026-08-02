"""
Module B - Mapping intelligent Qlik → Power BI
100% LLM - Tous les patterns sont analysés par le LLM
"""

import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Import du client LLM
try:
    from llm.client import ask_claude
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False
    def ask_claude(prompt):
        return "STATUT: ERREUR_PARSING\nMESURE: AUCUNE\nJUSTIFICATION: LLM non disponible - impossible d'analyser"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PatternContext:
    """Contexte complet d'un pattern."""
    pattern_type: str
    expression: str
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    filters: Dict[str, str] = field(default_factory=dict)
    aggregations: List[str] = field(default_factory=list)
    joins: List[str] = field(default_factory=list)
    complexity_score: float = 1.0
    confidence: float = 0.0


# ============================================================
# ANALYSEUR DE CONTEXTE
# ============================================================

class ContextAnalyzer:
    """Analyseur de contexte pour extraire les informations."""

    def analyze(self, pattern: dict) -> PatternContext:
        """Analyse le contexte d'un pattern."""
        expr = pattern.get("expression_source", pattern.get("expression", ""))
        pattern_type = pattern.get("pattern", "unknown")

        context = PatternContext(
            pattern_type=pattern_type,
            expression=expr
        )

        context.tables = self._extract_tables(expr)
        context.columns = self._extract_columns(expr)
        context.variables = self._extract_variables(expr)
        context.functions = self._extract_functions(expr)
        context.filters = self._extract_filters(pattern_type, expr)
        context.aggregations = self._extract_aggregations(expr)
        context.joins = self._extract_joins(expr)
        context.complexity_score = self._calculate_complexity(context)
        context.confidence = 0.5

        return context

    def _extract_tables(self, expression: str) -> List[str]:
        tables = []
        patterns = [
            r"(?:FROM|RESIDENT|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"Table\s*=\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)",
            r"Sales\s+\[(\w+)\]",
            r"Customers\s+\[(\w+)\]"
        ]
        for p in patterns:
            matches = re.findall(p, expression, re.IGNORECASE)
            tables.extend(matches)
        return list(set(tables))

    def _extract_columns(self, expression: str) -> List[str]:
        columns = []
        patterns = [
            r"\[([A-Za-z_][A-Za-z0-9_]*)\]",
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*",
            r"(?:SUM|COUNT|AVG|MAX|MIN)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
            r"Group\s+By\s+([A-Za-z_][A-Za-z0-9_]*)"
        ]
        for p in patterns:
            matches = re.findall(p, expression, re.IGNORECASE)
            columns.extend(matches)
        return list(set(columns))

    def _extract_variables(self, expression: str) -> List[str]:
        variables = []
        patterns = [
            r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)",
            r"(?:SET|LET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            r"v[A-Za-z_][A-Za-z0-9_]*"
        ]
        for p in patterns:
            matches = re.findall(p, expression, re.IGNORECASE)
            variables.extend(matches)
        return list(set(variables))

    def _extract_functions(self, expression: str) -> List[str]:
        functions = []
        qlik_functions = [
            "SUM", "COUNT", "AVG", "MAX", "MIN", "AGGR", "APPLYMAP",
            "PEEK", "PREVIOUS", "ABOVE", "BELOW", "RANGESUM",
            "IF", "PICK", "MATCH", "WILDMATCH", "TEXTBETWEEN",
            "DATE", "YEAR", "MONTH", "TODAY", "NOW", "CALL", "SUB"
        ]
        for func in qlik_functions:
            if func in expression.upper():
                functions.append(func)
        return functions

    def _extract_filters(self, pattern_type: str, expression: str) -> Dict[str, str]:
        filters = {}
        if pattern_type == "set_analysis":
            filter_pattern = r"(\w+)\s*=\s*([^,}]+)"
            matches = re.findall(filter_pattern, expression)
            for key, value in matches:
                filters[key.strip()] = value.strip()
        return filters

    def _extract_aggregations(self, expression: str) -> List[str]:
        aggregations = []
        patterns = [
            r"SUM\s*\(([^)]*)\)",
            r"COUNT\s*\(([^)]*)\)",
            r"AVG\s*\(([^)]*)\)",
            r"MAX\s*\(([^)]*)\)",
            r"MIN\s*\(([^)]*)\)",
            r"AGGR\s*\(([^)]*)\)"
        ]
        for p in patterns:
            matches = re.findall(p, expression, re.IGNORECASE)
            for match in matches:
                if match.strip():
                    func_name = p.split('\\(')[0].strip().upper()
                    aggregations.append(f"{func_name}({match.strip()})")
        return aggregations

    def _extract_joins(self, expression: str) -> List[str]:
        joins = []
        patterns = [
            r"(LEFT|RIGHT|INNER)\s+JOIN",
            r"JOIN\s+ON\s+(.+?)(?:\n|$)"
        ]
        for p in patterns:
            matches = re.findall(p, expression, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    joins.append(f"{match[0]} JOIN")
                else:
                    joins.append(match.strip())
        return joins

    def _calculate_complexity(self, context: PatternContext) -> float:
        score = 1.0
        score += len(context.tables) * 0.5
        score += len(context.columns) * 0.3
        score += len(context.variables) * 0.4
        score += len(context.functions) * 0.6
        score += len(context.filters) * 0.5
        score += len(context.aggregations) * 0.7
        score += len(context.joins) * 0.8
        return min(score, 10.0)


# ============================================================
# MAPPEUR 100% LLM
# ============================================================

def _normalize_measures_input(dax_measures) -> str:
    """Uniformise l'entrée mesures DAX vers le format texte '# Mesure : ...'
    attendu par le prompt, que l'appelant fournisse :
    - une chaîne déjà dans ce format (legacy, fichier uploadé), ou
    - une liste de dicts {"name":..., "dax":...} ou {"name":..., "expression":...}
      (format déjà produit par pbi_extractor.py / qlik_extractor.py — pas de
      fichier séparé nécessaire)."""
    if isinstance(dax_measures, str):
        return dax_measures
    lines = []
    for m in dax_measures or []:
        name = (m.get("name") or "").strip()
        expr = (m.get("dax") or m.get("expression") or "").strip()
        if name:
            lines.append(f"# Mesure : {name}\n{expr}")
    return "\n".join(lines)


class LLMMapper:
    """Mapper 100% LLM - Tous les patterns sont analysés par le LLM."""

    def __init__(self):
        self.analyzer = ContextAnalyzer()
        self.mapping_history = []
        self.llm_disponible = LLM_DISPONIBLE

    def map_pattern(self, pattern: dict, dax_measures) -> dict:
        """Mappe un pattern en utilisant UNIQUEMENT le LLM.
        dax_measures : texte '# Mesure : ...' OU liste de dicts {"name","dax"}."""

        dax_measures_text = _normalize_measures_input(dax_measures)

        # 1. Analyser le contexte
        context = self.analyzer.analyze(pattern)

        # Liste des noms de mesures réellement disponibles, pour valider la réponse
        # du LLM ensuite (anti-hallucination).
        known_measure_names = set(re.findall(r'# Mesure : (.+?)(?:\n|$)', dax_measures_text))

        # 2. Si LLM disponible → analyse LLM
        if self.llm_disponible:
            result = self._ask_llm(pattern, dax_measures_text, context, known_measure_names)
        else:
            result = {
                "statut": "ERREUR_PARSING",
                "mesure_dax_correspondante": None,
                "justification": "LLM non disponible - impossible d'analyser",
                "confidence": 0.0
            }

        # 3. Enregistrer l'historique
        self.mapping_history.append({
            "pattern": pattern,
            "context": context,
            "result": result
        })

        # 4. Retourner le résultat
        return {
            "pattern": pattern.get("pattern", "unknown"),
            "expression_source": pattern.get("expression_source", pattern.get("expression", "")),
            "statut": result.get("statut", "ERREUR_PARSING"),
            "mesure_dax_correspondante": result.get("mesure_dax_correspondante"),
            "justification": result.get("justification", "Analyse LLM terminée"),
            "confiance": result.get("confidence", 0.5),
            "_context": {
                "tables": context.tables,
                "columns": context.columns,
                "variables": context.variables,
                "functions": context.functions,
                "filters": context.filters,
                "complexity": context.complexity_score
            }
        }

    def _ask_llm(self, pattern: dict, dax_measures: str, context: PatternContext,
                 known_measure_names: set) -> dict:
        """Interroge le LLM pour le mapping."""
        try:
            prompt = self._build_prompt(pattern, dax_measures, context)
            response = ask_claude(prompt)
            result = self._parse_response(response)

            # --- Validation anti-hallucination ---
            # Les petits modèles locaux (ex. Mistral) suivent parfois mal la consigne
            # et inventent une expression DAX au lieu de recopier un nom de la liste.
            # On rejette tout nom de mesure qui n'existe pas réellement.
            mesure = result.get("mesure_dax_correspondante")
            if mesure and known_measure_names and mesure not in known_measure_names:
                result["justification"] += (
                    f" [ATTENTION : mesure '{mesure}' invalidée — absente de la liste "
                    f"fournie, probable hallucination du modèle]"
                )
                result["mesure_dax_correspondante"] = None
                # Un statut COUVERT reposait sur cette mesure invalide : on redescend
                # en PARTIELLEMENT_COUVERT plutôt que de garder une affirmation fausse.
                if result.get("statut") == "COUVERT":
                    result["statut"] = "PARTIELLEMENT_COUVERT"

            # --- Validation de cohérence STATUT vs JUSTIFICATION ---
            # Les petits modèles locaux annoncent parfois COUVERT tout en expliquant
            # eux-mêmes qu'aucune mesure ne correspond — contradiction interne à corriger,
            # pas juste une hallucination de nom (déjà traitée ci-dessus).
            justification_lower = (result.get("justification") or "").lower()
            nie_toute_correspondance = any(
                phrase in justification_lower
                for phrase in [
                    "aucune mesure", "aucune des mesures", "ne correspond à aucune",
                    "ne correspond pas", "pas d'équivalent", "n'a pas d'équivalent",
                    "aucun équivalent", "ne représente pas", "n'est pas une mesure",
                    "pas une mesure spécifique", "aucune correspondance",
                    "sans équivalent",
                ]
            )
            if (
                result.get("statut") == "COUVERT"
                and not result.get("mesure_dax_correspondante")
                and nie_toute_correspondance
            ):
                result["statut"] = "NON_COUVERT"
                result["justification"] += (
                    " [ATTENTION : statut COUVERT incohérent avec la justification "
                    "du modèle (qui indique l'inverse) — corrigé automatiquement en NON_COUVERT]"
                )

            result["confidence"] = min(0.9, context.confidence + 0.3)
        except Exception as e:
            print(f"⚠️ Erreur LLM pour {pattern.get('pattern', 'unknown')}: {e}")
            result = {
                "statut": "ERREUR_PARSING",
                "mesure_dax_correspondante": None,
                "justification": f"Erreur LLM: {str(e)[:100]}",
                "confidence": 0.0
            }

        return result

    def _build_prompt(self, pattern: dict, dax_measures: str, context: PatternContext) -> str:
        """Construit le prompt pour le LLM."""

        # Extraire les mesures DAX
        measures = re.findall(r'# Mesure : (.+?)(?:\n|$)', dax_measures)
        measures_list = "\n".join([f"- {m}" for m in measures]) if measures else "Aucune mesure DAX trouvée"

        # Détails du contexte
        context_details = f"""
Type: {pattern.get('pattern', 'unknown')}
Expression:

**Contexte extrait :**
- Tables: {', '.join(context.tables) if context.tables else 'Aucune'}
- Colonnes: {', '.join(context.columns) if context.columns else 'Aucune'}
- Variables: {', '.join(context.variables) if context.variables else 'Aucune'}
- Fonctions Qlik: {', '.join(context.functions) if context.functions else 'Aucune'}
- Filtres: {json.dumps(context.filters) if context.filters else 'Aucun'}
- Agrégations: {', '.join(context.aggregations) if context.aggregations else 'Aucune'}
- Complexité: {context.complexity_score:.1f}/10
"""

        prompt = f"""Tu es un expert en migration Qlik Sense vers Power BI.

## TÂCHE : Analyser ce pattern Qlik et déterminer s'il peut être migré vers Power BI.

**Pattern Qlik :**
{context_details}

**Mesures DAX disponibles dans Power BI :**
{measures_list}

## INSTRUCTIONS :
1. Analyse ce pattern Qlik en profondeur
2. Détermine s'il a un équivalent dans les mesures DAX disponibles
3. Si oui, identifie quelle mesure DAX correspond le mieux
4. Si non, explique pourquoi et suggère une approche

## FORMAT DE RÉPONSE OBLIGATOIRE (3 LIGNES EXACTEMENT) :
STATUT: [COUVERT / PARTIELLEMENT_COUVERT / NON_COUVERT]
MESURE: [Nom exact de la mesure DAX trouvée ou AUCUNE]
JUSTIFICATION: [Explication détaillée de ta décision]

RÈGLE STRICTE pour le champ MESURE : recopie EXACTEMENT un des noms listés
ci-dessus dans "Mesures DAX disponibles", caractère pour caractère, ou écris
AUCUNE. N'invente jamais un nouveau nom, une expression DAX, ou une variante
du nom — un nom qui n'apparaît pas mot pour mot dans la liste sera rejeté.

Ne réponds QUE sur ces 3 lignes, pas de texte supplémentaire.
"""

        return prompt

    def _parse_response(self, response: str) -> dict:
        """Parse la réponse du LLM."""
        result = {
            "statut": "ERREUR_PARSING",
            "mesure_dax_correspondante": None,
            "justification": response.strip()[:200]
        }

        for line in response.splitlines():
            line = line.strip()
            if line.upper().startswith("STATUT:"):
                statut = line.split(":", 1)[1].strip().upper()
                if statut in ["COUVERT", "PARTIELLEMENT_COUVERT", "NON_COUVERT"]:
                    result["statut"] = statut
            elif line.upper().startswith("MESURE:"):
                mesure = line.split(":", 1)[1].strip()
                if mesure.upper() != "AUCUNE":
                    result["mesure_dax_correspondante"] = mesure
            elif line.upper().startswith("JUSTIFICATION:"):
                result["justification"] = line.split(":", 1)[1].strip()

        return result


# ============================================================
# FONCTIONS PRINCIPALES
# ============================================================

# Variables que Qlik Sense déclare automatiquement au début de CHAQUE nouveau
# script de chargement (formats régionaux/décimaux/date). Ce n'est jamais du
# contenu métier à migrer, donc pas la peine de solliciter le LLM dessus —
# ça fait gagner du temps et évite un bruit systématique dans le rapport.
QLIK_SYSTEM_VARIABLES = {
    "thousandsep", "decimalsep", "moneythousandsep", "moneydecimalsep",
    "moneyformat", "timeformat", "dateformat", "timestampformat",
    "monthnames", "longmonthnames", "daynames", "longdaynames",
    "firstweekday", "brokenweeks", "referenceday", "firstmonthofyear",
    "collationlocale", "createsearchindexonreload", "numericaldecimalsep",
    "numericalthousandsep",
}


def _filter_system_noise(patterns: list[dict]) -> list[dict]:
    """Retire les déclarations de variables système standards Qlik (pas de valeur
    à faire évaluer par le LLM)."""
    return [
        p for p in patterns
        if not (
            p.get("pattern") == "variable_declaration"
            and (p.get("name") or "").strip().lower() in QLIK_SYSTEM_VARIABLES
        )
    ]


def auto_evaluate_against_rules(
    qlik_script: str,
    qlik_expressions: str,
    dax_measures,
    n_runs: int = 3,
) -> Dict:
    """
    Évaluation professionnelle SANS fichier de vérité terrain : compare le LLM
    (Mistral) au moteur par règles déterministe (coverage_analyzer.py) sur les
    MÊMES patterns, et mesure aussi l'auto-cohérence du LLM sur n_runs exécutions.

    Ce n'est pas une "vérité absolue" (le moteur par règles peut aussi se
    tromper), mais un indicateur professionnel standard : taux d'accord
    inter-méthodes + stabilité. Fonctionne sur n'importe quel projet déjà
    extrait par les Modules A/B, sans upload d'un fichier de cas labellisés.
    """
    try:
        from module_b.coverage_analyzer import FunctionalCoverageAnalyzer
    except ImportError:
        from coverage_analyzer import FunctionalCoverageAnalyzer

    analyzer = FunctionalCoverageAnalyzer()
    patterns = analyzer.detect_patterns(qlik_script, qlik_expressions)
    patterns = _filter_system_noise(patterns)

    if not patterns:
        return {"error": "Aucun pattern détecté (script/expressions vides ou sans pattern reconnu)."}

    if isinstance(dax_measures, str):
        # Format legacy '# Mesure : Nom\n<expression>' -> liste structurée
        measures_list = [
            {"name": n, "dax": e}
            for n, e in re.findall(
                r'# Mesure : (.+?)\n(.*?)(?=\n# Mesure :|\Z)', dax_measures, re.S
            )
        ]
    else:
        measures_list = dax_measures or []
    normalized_measures = analyzer._normalize_measures(measures_list)

    reference_results = analyzer._map_to_dax(patterns, normalized_measures)

    mapper = LLMMapper()
    details = []
    n_agree = 0
    n_stable = 0

    for pattern, ref in zip(patterns, reference_results):
        statuts_llm = []
        for _ in range(max(1, n_runs)):
            res = mapper.map_pattern(pattern, normalized_measures)
            statuts_llm.append(res.get("statut", "ERREUR_PARSING"))

        verdict_majoritaire = max(set(statuts_llm), key=statuts_llm.count)
        stable = len(set(statuts_llm)) == 1
        accord = verdict_majoritaire == ref.statut

        if accord:
            n_agree += 1
        if stable:
            n_stable += 1

        details.append({
            "pattern": pattern.get("pattern", "unknown"),
            "expression": pattern.get("expression_source", "")[:80],
            "reference_regles": ref.statut,
            "predictions_llm": statuts_llm,
            "verdict_llm_majoritaire": verdict_majoritaire,
            "accord": accord,
            "stable": stable,
        })

    total = len(details)
    return {
        "total_patterns": total,
        "taux_accord": round(n_agree / total * 100, 1) if total else 0.0,
        "taux_stabilite": round(n_stable / total * 100, 1) if total else 0.0,
        "n_runs": n_runs,
        "details": details,
    }


def map_pattern_to_dax(pattern: dict, dax_measures_text: str) -> dict:
    """Interface principale pour le mapping 100% LLM."""
    mapper = LLMMapper()
    return mapper.map_pattern(pattern, dax_measures_text)


def map_all_patterns(patterns: list[dict], dax_measures_path: str) -> list[dict]:
    """Applique le mapping 100% LLM sur tous les patterns."""
    dax_text = Path(dax_measures_path).read_text(encoding="utf-8")
    mapper = LLMMapper()
    results = []

    patterns = _filter_system_noise(patterns)
    total = len(patterns)

    if not mapper.llm_disponible:
        print("\n⚠️ LLM NON DISPONIBLE - Aucune analyse possible")
        return [{
            "pattern": p.get("pattern", "unknown"),
            "expression_source": p.get("expression_source", ""),
            "statut": "ERREUR_PARSING",
            "mesure_dax_correspondante": None,
            "justification": "LLM non disponible",
            "confiance": 0.0
        } for p in patterns]

    print(f"\n🧠 LLM ACTIVÉ - Analyse intelligente de {total} patterns...\n")

    for idx, pattern in enumerate(patterns):
        print(f"🔍 Analyse LLM {idx+1}/{total} : {pattern.get('pattern', 'unknown')}...")
        result = mapper.map_pattern(pattern, dax_text)
        results.append(result)

        statut = result.get("statut", "UNKNOWN")
        emoji = "🟢" if statut == "COUVERT" else "🟠" if statut == "PARTIELLEMENT_COUVERT" else "🔴" if statut == "NON_COUVERT" else "⚪"
        print(f"   {emoji} {statut} - {result.get('justification', '')[:60]}...")

    return results


def generate_coverage_report(results: list[dict]) -> dict:
    """Génère un rapport de couverture."""
    total = len(results) if results else 1

    stats = {"COUVERT": 0, "PARTIELLEMENT_COUVERT": 0, "NON_COUVERT": 0, "ERREUR_PARSING": 0}
    details = []

    for r in results:
        statut = r.get("statut", "ERREUR_PARSING")
        stats[statut] = stats.get(statut, 0) + 1
        details.append({
            "pattern": r.get("pattern", "unknown"),
            "statut": statut,
            "mesure": r.get("mesure_dax_correspondante", ""),
            "justification": r.get("justification", ""),
            "confiance": r.get("confiance", 0.0)
        })

    covered = stats["COUVERT"]
    partially = stats["PARTIELLEMENT_COUVERT"]

    return {
        "total": total,
        "covered": covered,
        "partially": partially,
        "not_covered": stats["NON_COUVERT"],
        "errors": stats["ERREUR_PARSING"],
        "coverage_rate": covered / max(total, 1) * 100,
        "effective_coverage": (covered + partially * 0.5) / max(total, 1) * 100,
        "details": details,
        "summary": {
            "total": total,
            "covered": covered,
            "partially": partially,
            "not_covered": stats["NON_COUVERT"],
            "errors": stats["ERREUR_PARSING"],
            "coverage_rate": round(covered / max(total, 1) * 100, 1),
            "effective_coverage": round((covered + partially * 0.5) / max(total, 1) * 100, 1)
        }
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    from qlik_parser import QlikParser

    qlik_script_content = Path(
        "data/samples/case_encadrante_01/qlik/load_script.qvs"
    ).read_text(encoding="utf-8")

    patterns = QlikParser().parse_script(qlik_script_content)
    results = map_all_patterns(patterns, "data/samples/case_encadrante_01/powerbi/measures_dax.txt")

    report = generate_coverage_report(results)

    print(f"\n{'='*70}")
    print(f"📊 RAPPORT DE COUVERTURE (100% LLM)")
    print(f"{'='*70}")
    print(f"📈 Couverture: {report['coverage_rate']:.1f}% ({report['covered']}/{report['total']})")
    print(f"📊 Effective: {report['effective_coverage']:.1f}%")
    print(f"{'='*70}")

    for r in results[:10]:
        print(f"\n[{r.get('statut')}] {r.get('pattern')}")
        print(f"   Justification: {r.get('justification', '')[:80]}...")