"""
Module B - Audit de couverture fonctionnelle
Analyseur de couverture fonctionnelle générique.
Repère les fonctionnalités Qlik sans équivalent dans Power BI.

Conçu pour fonctionner sur N'IMPORTE QUEL couple Qlik/Power BI (pas seulement
le cas d'exemple) : le matching se fait par mots-clés DAX génériques recherchés
dans les VRAIES expressions des mesures, jamais par une liste de noms codés en dur.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class PatternCoverage:
    """Résultat de couverture pour un pattern."""
    pattern: str
    expression: str
    statut: str  # COUVERT, PARTIELLEMENT_COUVERT, NON_COUVERT
    mesure_dax: Optional[str] = None
    mesure_dax_expr: Optional[str] = None
    justification: str = ""
    recommandation: str = ""
    criticite: str = "MINEUR"
    confiance: float = 0.0


@dataclass
class CoverageReport:
    """Rapport complet de couverture fonctionnelle."""
    patterns: List[PatternCoverage]
    score_global: float
    niveau: str
    statistiques: Dict
    recommandations_globales: List[str]
    findings: List[Dict] = field(default_factory=list)


# ============================================================
# MOTS-CLÉS DAX PAR TYPE DE PATTERN (générique, pas de nom de mesure)
# ============================================================
# Si un des mots-clés apparaît dans l'expression DAX RÉELLE d'une mesure,
# on considère qu'elle est un candidat plausible d'équivalent migré.
# Vide = pas détectable au niveau de la mesure (ex. Section Access = sécurité,
# LOAD INLINE / LOAD FROM FILE = source de données, pas une mesure).
DAX_KEYWORD_MAP: Dict[str, List[str]] = {
    "set_analysis": ["CALCULATE", "FILTER", "ALL(", "ALLEXCEPT"],
    "variable_dollar_expansion": ["VAR "],
    "variable_declaration": ["VAR "],
    "mapping_applymap": ["LOOKUPVALUE"],
    "mapping_load": ["LOOKUPVALUE", "RELATED("],
    "subroutine_definition": [],
    "subroutine_call": [],
    "resident_group_by": ["SUMMARIZE", "GROUPBY"],
    "left_join": ["NATURALLEFTOUTERJOIN", "RELATED(", "RELATEDTABLE"],
    "load_inline": [],
    "load_from_file": [],
    "aggr": ["SUMMARIZE", "GROUPBY", "SUMMARIZECOLUMNS"],
    "nested_aggr": ["SUMMARIZECOLUMNS"],
    "if_condition": ["IF(", "SWITCH("],
    "peek_previous": ["EARLIER(", "OFFSET("],
    "range_sum": ["RUNNINGSUM", "CALCULATE"],
    "section_access": [],  # RLS : se vérifie dans les rôles de sécurité PBI, pas dans une mesure
}


class FunctionalCoverageAnalyzer:
    """
    Analyseur de couverture fonctionnelle générique.
    Repère les fonctionnalités Qlik non migrées vers Power BI, sur n'importe quel cas.
    """

    def __init__(self):
        self.patterns = self._load_taxonomy()
        self.dax_measures: List[Dict[str, str]] = []
        self.qlik_variables = {}

    def _load_taxonomy(self) -> Dict:
        """Charge la taxonomie des patterns Qlik avec leurs configurations."""
        base_taxonomy = {
            "set_analysis": {
                "regex": r"(?i)\{<([^>]+)>}",
                "criticite": "MAJEUR",
                "poids": 10,
                "dax_pattern": "CALCULATE avec FILTER",
                "description": "Set Analysis Qlik",
            },
            "variable_dollar_expansion": {
                "regex": r"\$\(([^)]+)\)",
                "criticite": "MINEUR",
                "poids": 3,
                "dax_pattern": "VAR",
                "description": "Expansion de variable Qlik",
            },
            "variable_declaration": {
                "regex": r"(?i)^\s*SET\s+([A-Za-z_]\w*)\s*=",
                "criticite": "MINEUR",
                "poids": 2,
                "dax_pattern": "VAR",
                "description": "Déclaration de variable Qlik",
            },
            "mapping_applymap": {
                "regex": r"(?i)ApplyMap\s*\(",
                "criticite": "MAJEUR",
                "poids": 7,
                "dax_pattern": "LOOKUPVALUE",
                "description": "ApplyMap Qlik",
            },
            "mapping_load": {
                "regex": r"(?i)Mapping\s+LOAD",
                "criticite": "MAJEUR",
                "poids": 7,
                "dax_pattern": "Table de correspondance",
                "description": "Mapping LOAD Qlik",
            },
            "subroutine_definition": {
                "regex": r"(?i)^\s*SUB\s+([A-Za-z_]\w*)\s*\(",
                "criticite": "MINEUR",
                "poids": 4,
                "dax_pattern": "Fonction DAX / Power Query M",
                "description": "Subroutine Qlik",
            },
            "subroutine_call": {
                "regex": r"(?i)^\s*CALL\s+([A-Za-z_]\w*)\s*\(",
                "criticite": "MINEUR",
                "poids": 3,
                "dax_pattern": "Appel de fonction",
                "description": "Appel de subroutine Qlik",
            },
            "resident_group_by": {
                "regex": r"(?i)Resident\s+([A-Za-z_]\w*)\s+Group By",
                "criticite": "MAJEUR",
                "poids": 6,
                "dax_pattern": "SUMMARIZE / GROUPBY",
                "description": "Resident Group By Qlik",
            },
            "left_join": {
                "regex": r"(?i)^\s*left join\s*",
                "criticite": "MAJEUR",
                "poids": 6,
                "dax_pattern": "NATURALLEFTOUTERJOIN",
                "description": "Left Join Qlik",
            },
            "load_inline": {
                "regex": r"(?i)LOAD\s+\*\s+INLINE\s*\[",
                "criticite": "MINEUR",
                "poids": 2,
                "dax_pattern": "DATATABLE",
                "description": "LOAD INLINE Qlik",
            },
            "load_from_file": {
                "regex": r"(?i)LOAD\s+.*?\s+FROM\s+['\"]",
                "criticite": "MINEUR",
                "poids": 2,
                "dax_pattern": "Power Query Source",
                "description": "LOAD FROM FILE Qlik",
            },
            "aggr": {
                "regex": r"(?i)Aggr\s*\(",
                "criticite": "MAJEUR",
                "poids": 8,
                "dax_pattern": "SUMMARIZE / GROUPBY",
                "description": "AGGR Qlik",
            },
        }

        advanced_patterns = {
            "nested_aggr": {
                "regex": r"Aggr\s*\(\s*Aggr\s*\(",
                "criticite": "BLOQUANT",
                "poids": 9,
                "dax_pattern": "SUMMARIZECOLUMNS",
                "description": "AGGR imbriqué Qlik",
            },
            "if_condition": {
                "regex": r"If\s*\(\s*[^,]+,\s*[^,]+,\s*[^)]+\s*\)",
                "criticite": "MINEUR",
                "poids": 3,
                "dax_pattern": "IF / SWITCH",
                "description": "Condition IF Qlik",
            },
            "peek_previous": {
                "regex": r"Peek\s*\(\s*['\"][^'\"]+['\"]\s*,\s*-1\s*\)",
                "criticite": "MAJEUR",
                "poids": 8,
                "dax_pattern": "EARLIER / OFFSET",
                "description": "PEEK Qlik",
            },
            "range_sum": {
                "regex": r"RangeSum\s*\(\s*Above\s*\(",
                "criticite": "MAJEUR",
                "poids": 7,
                "dax_pattern": "RUNNINGSUM",
                "description": "RangeSum Qlik",
            },
            "section_access": {
                "regex": r"(?i)Section\s+Access",
                "criticite": "BLOQUANT",
                "poids": 10,
                "dax_pattern": "RLS (Row Level Security)",
                "description": "Section Access Qlik",
            },
        }

        full_config = {}
        full_config.update(base_taxonomy)
        full_config.update(advanced_patterns)
        return full_config

    def detect_patterns(self, script_content: str, expressions_content: str) -> List[Dict]:
        """Détecte tous les patterns dans le script et les expressions."""
        combined = (script_content or "") + "\n\n" + (expressions_content or "")
        findings = []

        for pattern_name, config in self.patterns.items():
            matches = re.finditer(config["regex"], combined, re.IGNORECASE)
            for match in matches:
                findings.append({
                    "pattern": pattern_name,
                    "expression_source": match.group(0).strip(),
                    "position": match.start(),
                    "criticite": config["criticite"],
                    "poids": config["poids"],
                    "description": config.get("description", ""),
                    "dax_pattern": config.get("dax_pattern", ""),
                })

        return findings

    def extract_variables(self, content: str) -> Dict:
        """Extrait et analyse les variables Qlik."""
        variables = {}

        for match in re.finditer(r'(?:SET|LET)\s+(\w+)\s*=\s*([^;\n]+)', content, re.IGNORECASE):
            var_name = match.group(1)
            var_expr = match.group(2).strip()
            var_type = self._infer_variable_type(var_expr)

            variables[var_name] = {
                "expression": var_expr,
                "type": var_type,
                "utilisations": [],
            }

        for match in re.finditer(r'\$\((\w+)\)', content):
            var_name = match.group(1)
            if var_name in variables:
                variables[var_name]["utilisations"].append(match.group(0))

        return variables

    def _infer_variable_type(self, expression: str) -> str:
        expr_lower = expression.lower()
        if "year(today())" in expr_lower or "year(now())" in expr_lower:
            return "DATE_DYNAMIQUE"
        elif "month(max(" in expr_lower or "max(month" in expr_lower:
            return "DATE_AGREGEE"
        elif any(op in expr_lower for op in ["sum(", "count(", "avg("]):
            return "AGREGATION"
        elif any(op in expr_lower for op in ["'", '"']):
            return "TEXTE"
        else:
            return "NOMBRE"

    # ============================================================
    # POINT D'ENTRÉE PRINCIPAL (générique, sur mesures déjà structurées)
    # ============================================================

    def analyze_coverage(
        self,
        qlik_script: str,
        qlik_expressions: str,
        dax_measures: List[Dict[str, str]],
    ) -> CoverageReport:
        """
        Analyse complète de la couverture fonctionnelle.

        qlik_script / qlik_expressions : texte brut (script de chargement Qlik,
            expressions des visuels/mesures master).
        dax_measures : liste de dicts avec au moins {"name": ..., "dax": ...}
            (ou "expression" à la place de "dax", les deux sont acceptés) —
            c'est exactement le format déjà produit par pbi_extractor.py /
            qlik_extractor.py, pas besoin d'un fichier séparé à format spécial.
        """
        self.dax_measures = self._normalize_measures(dax_measures)

        patterns = self.detect_patterns(qlik_script, qlik_expressions)
        self.qlik_variables = self.extract_variables(
            (qlik_script or "") + "\n" + (qlik_expressions or "")
        )
        results = self._map_to_dax(patterns, self.dax_measures)

        total_weight = sum(self.patterns.get(p.pattern, {}).get("poids", 5) for p in results)
        achieved_weight = sum(
            p.confiance * self.patterns.get(p.pattern, {}).get("poids", 5) for p in results
        )
        score_global = (achieved_weight / total_weight * 100) if total_weight > 0 else 0

        if score_global >= 90:
            niveau = "EXCELLENT"
        elif score_global >= 70:
            niveau = "BON"
        elif score_global >= 50:
            niveau = "MOYEN"
        else:
            niveau = "CRITIQUE"

        stats = {
            "total": len(results),
            "couvert": sum(1 for p in results if p.statut == "COUVERT"),
            "partiel": sum(1 for p in results if p.statut == "PARTIELLEMENT_COUVERT"),
            "non_couvert": sum(1 for p in results if p.statut == "NON_COUVERT"),
            "critique": sum(1 for p in results if p.criticite == "BLOQUANT"),
            "majeur": sum(1 for p in results if p.criticite == "MAJEUR"),
            "mineur": sum(1 for p in results if p.criticite == "MINEUR"),
        }

        findings = self._generate_findings(results)

        recommandations = []
        if stats["non_couvert"] > 0:
            recommandations.append(f"🔴 {stats['non_couvert']} pattern(s) non couvert(s) - migration manuelle requise")
        if stats["partiel"] > 0:
            recommandations.append(f"🟠 {stats['partiel']} pattern(s) partiellement couvert(s) - vérifier la cohérence")
        if stats["critique"] > 0:
            recommandations.append("🚨 Présence de patterns BLOQUANTS - intervention humaine urgente")
        if stats["couvert"] > 0:
            recommandations.append(f"🟢 {stats['couvert']} pattern(s) correctement couverts")

        return CoverageReport(
            patterns=results,
            score_global=score_global,
            niveau=niveau,
            statistiques=stats,
            recommandations_globales=recommandations,
            findings=findings,
        )

    def _normalize_measures(self, dax_measures: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Uniformise les mesures reçues : garantit les clés 'name' et 'dax'."""
        out = []
        for m in dax_measures or []:
            name = (m.get("name") or "").strip()
            expr = (m.get("dax") or m.get("expression") or "").strip()
            if name:
                out.append({"name": name, "dax": expr})
        return out

    def _map_to_dax(self, patterns: List[Dict], dax_measures: List[Dict[str, str]]) -> List[PatternCoverage]:
        """Map les patterns Qlik vers DAX avec scoring, matching générique par mots-clés."""
        results = []

        mapping_rules = {
            "variable_declaration": {
                "statut": "COUVERT", "justification": "Variables Qlik migrées en VAR DAX",
                "recommandation": "Utiliser VAR dans DAX", "criticite": "MINEUR", "confiance": 0.9,
            },
            "variable_dollar_expansion": {
                "statut": "COUVERT", "justification": "Expansion de variables migrée en VAR DAX",
                "recommandation": "Utiliser VAR dans DAX", "criticite": "MINEUR", "confiance": 0.9,
            },
            "set_analysis": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "Set Analysis équivaut à CALCULATE avec filtres",
                "recommandation": "Utiliser CALCULATE avec FILTER", "criticite": "MAJEUR", "confiance": 0.7,
            },
            "mapping_applymap": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "ApplyMap équivaut à LOOKUPVALUE",
                "recommandation": "Utiliser LOOKUPVALUE", "criticite": "MAJEUR", "confiance": 0.7,
            },
            "resident_group_by": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "Resident Group By équivaut à SUMMARIZE",
                "recommandation": "Utiliser SUMMARIZE en DAX", "criticite": "MAJEUR", "confiance": 0.7,
            },
            "subroutine_definition": {
                "statut": "NON_COUVERT", "justification": "Subroutine Qlik - pas d'équivalent direct en DAX",
                "recommandation": "Migrer en Power Query M ou fonction DAX personnalisée",
                "criticite": "BLOQUANT", "confiance": 0.4,
            },
            "subroutine_call": {
                "statut": "NON_COUVERT", "justification": "Appel de subroutine - pas d'équivalent direct",
                "recommandation": "Migrer manuellement", "criticite": "MAJEUR", "confiance": 0.4,
            },
            "left_join": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "Left Join équivaut à NATURALLEFTOUTERJOIN",
                "recommandation": "Utiliser NATURALLEFTOUTERJOIN ou Power Query", "criticite": "MAJEUR", "confiance": 0.7,
            },
            "load_inline": {
                "statut": "COUVERT", "justification": "LOAD INLINE équivaut à DATATABLE",
                "recommandation": "Utiliser DATATABLE en DAX", "criticite": "MINEUR", "confiance": 0.9,
            },
            "load_from_file": {
                "statut": "COUVERT", "justification": "LOAD FROM FILE migré vers Power Query",
                "recommandation": "Utiliser Power Query comme source", "criticite": "MINEUR", "confiance": 0.8,
            },
            "mapping_load": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "Mapping LOAD migré en table de correspondance",
                "recommandation": "Créer une table de correspondance DAX", "criticite": "MAJEUR", "confiance": 0.6,
            },
            "aggr": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "AGGR équivaut à SUMMARIZE",
                "recommandation": "Utiliser SUMMARIZE en DAX", "criticite": "MAJEUR", "confiance": 0.7,
            },
            "nested_aggr": {
                "statut": "NON_COUVERT", "justification": "AGGR imbriqué - complexe à migrer",
                "recommandation": "Utiliser SUMMARIZECOLUMNS avec plusieurs niveaux", "criticite": "BLOQUANT", "confiance": 0.3,
            },
            "section_access": {
                "statut": "NON_COUVERT", "justification": "Section Access - sécurité au niveau des lignes",
                "recommandation": "Implémenter RLS (rôles de sécurité) dans Power BI", "criticite": "BLOQUANT", "confiance": 0.3,
            },
            "if_condition": {
                "statut": "COUVERT", "justification": "IF Qlik équivaut à IF DAX",
                "recommandation": "Utiliser IF ou SWITCH en DAX", "criticite": "MINEUR", "confiance": 0.9,
            },
            "peek_previous": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "PEEK équivaut à EARLIER ou OFFSET",
                "recommandation": "Utiliser EARLIER ou variables DAX", "criticite": "MAJEUR", "confiance": 0.5,
            },
            "range_sum": {
                "statut": "PARTIELLEMENT_COUVERT", "justification": "RangeSum équivaut à RUNNINGSUM",
                "recommandation": "Créer une mesure avec CALCULATE et FILTER", "criticite": "MAJEUR", "confiance": 0.5,
            },
        }

        for pattern in patterns:
            pattern_type = pattern["pattern"]
            rule = mapping_rules.get(pattern_type, {
                "statut": "NON_COUVERT", "justification": "Pattern non reconnu",
                "recommandation": "Analyse manuelle requise", "criticite": "MAJEUR", "confiance": 0.3,
            })

            matching_measure = self._find_matching_measure(pattern_type, dax_measures)

            statut = rule["statut"]
            confiance = rule["confiance"]

            if matching_measure and rule["statut"] == "PARTIELLEMENT_COUVERT":
                # Une vraie mesure DAX correspondante existe : on peut monter en confiance
                statut = "COUVERT"
                confiance = max(rule["confiance"], 0.8)
            elif matching_measure and rule["statut"] == "NON_COUVERT":
                # Rare mais possible : une mesure candidate existe malgré tout
                statut = "PARTIELLEMENT_COUVERT"
                confiance = max(rule["confiance"], 0.5)
            elif not matching_measure and rule["statut"] == "COUVERT" and DAX_KEYWORD_MAP.get(pattern_type):
                # Le pattern DEVRAIT être vérifiable via mot-clé DAX mais aucune mesure ne matche :
                # on baisse la confiance plutôt que d'affirmer à tort que c'est couvert.
                statut = "PARTIELLEMENT_COUVERT"
                confiance = min(rule["confiance"], 0.5)

            results.append(PatternCoverage(
                pattern=pattern_type,
                expression=pattern["expression_source"],
                statut=statut,
                mesure_dax=matching_measure.get("name") if matching_measure else None,
                mesure_dax_expr=matching_measure.get("dax") if matching_measure else None,
                justification=rule["justification"],
                recommandation=rule["recommandation"],
                criticite=rule["criticite"],
                confiance=confiance,
            ))

        return results

    def _find_matching_measure(
        self, pattern_type: str, dax_measures: List[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        """
        Cherche une mesure DAX candidate par MOTS-CLÉS génériques dans l'expression
        réelle (pas par nom de mesure) — fonctionne sur n'importe quel rapport.
        Retourne la mesure avec le plus de mots-clés trouvés, ou None.
        """
        keywords = DAX_KEYWORD_MAP.get(pattern_type, [])
        if not keywords or not dax_measures:
            return None

        best_measure, best_hits = None, 0
        for m in dax_measures:
            expr_upper = (m.get("dax") or "").upper()
            if not expr_upper:
                continue
            hits = sum(1 for kw in keywords if kw.upper() in expr_upper)
            if hits > best_hits:
                best_hits, best_measure = hits, m

        return best_measure

    def _generate_findings(self, results: List[PatternCoverage]) -> List[Dict]:
        findings = []
        for r in results:
            # Tout ce qui n'est pas pleinement COUVERT va dans le rapport consolidé,
            # pas seulement NON_COUVERT ou les partiels critiques : un pattern
            # PARTIELLEMENT_COUVERT en MAJEUR (ex. ApplyMap sans mesure DAX trouvée)
            # est exactement le genre de lacune que le consultant doit voir.
            if r.statut in ("NON_COUVERT", "PARTIELLEMENT_COUVERT"):
                findings.append({
                    "source_module": "Module B - Functional Coverage",
                    "libelle": f"[{r.statut}] {r.pattern}",
                    "detail": f"Expression: {r.expression[:100]}...",
                    "criticite": r.criticite,
                    "diagnostic": r.justification,
                    "recommandation": r.recommandation,
                    "statut": r.statut,
                    "confiance": r.confiance,
                })
        return findings


# ============================================================
# FONCTIONS D'ENTRÉE POUR L'INTERFACE (app.py)
# ============================================================

def analyze_coverage_quick(
    qlik_script: str,
    qlik_expressions: str,
    dax_measures: List[Dict[str, str]],
) -> Dict:
    """
    Analyse rapide de la couverture fonctionnelle, utilisée par l'interface Streamlit.

    dax_measures : liste de dicts {"name":..., "dax":...} — le format déjà produit
    par pbi_extractor.py (result["dax_measures"]) ou qlik_extractor.py (result["measures"]).
    Aucun fichier texte à format spécial n'est nécessaire.
    """
    try:
        analyzer = FunctionalCoverageAnalyzer()
        report = analyzer.analyze_coverage(qlik_script, qlik_expressions, dax_measures)

        return {
            "total_patterns": report.statistiques["total"],
            "covered": report.statistiques["couvert"],
            "partially_covered": report.statistiques["partiel"],
            "not_covered": report.statistiques["non_couvert"],
            "coverage_rate": report.score_global,
            "level": report.niveau,
            "details": [
                {
                    "pattern": p.pattern,
                    "statut": p.statut,
                    "mesure_dax": p.mesure_dax,
                    "mesure_dax_expr": p.mesure_dax_expr,
                    "justification": p.justification,
                    "criticite": p.criticite,
                    "confiance": p.confiance,
                }
                for p in report.patterns
            ],
            "findings": report.findings,
            "recommandations": report.recommandations_globales,
        }
    except Exception as e:
        return {"error": str(e)}


def parse_dax_measures_text(dax_content: str) -> List[Dict[str, str]]:
    """
    Repli pour compatibilité : parse un fichier texte au format
    '# Mesure : NomDeLaMesure' + expression, pour les cas où l'utilisateur
    uploade un fichier de mesures au lieu de partir d'une extraction live.
    Format attendu, un bloc par mesure :
        # Mesure : Total Sales
        SUM(Sales[SalesAmount])
    """
    measures = []
    blocks = re.split(r'(?=# Mesure\s*:)', dax_content)
    for block in blocks:
        m = re.match(r'#\s*Mesure\s*:\s*(.+)', block.strip())
        if not m:
            continue
        name = m.group(1).strip()
        rest = block[m.end():].strip()
        measures.append({"name": name, "dax": rest})
    return measures