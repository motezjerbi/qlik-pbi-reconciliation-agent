# src/module_b/semantic_analyzer_dynamic.py
"""
Analyseur sémantique dynamique avec apprentissage et règles configurables
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd


@dataclass
class SemanticContext:
    """Contexte sémantique d'un pattern."""
    pattern_type: str
    expression: str
    tables: Set[str] = field(default_factory=set)
    columns: Set[str] = field(default_factory=set)
    variables: Set[str] = field(default_factory=set)
    functions: Set[str] = field(default_factory=set)
    filters: Dict[str, str] = field(default_factory=dict)
    aggregations: Set[str] = field(default_factory=set)
    joins: Set[str] = field(default_factory=set)
    complexity_score: float = 1.0
    pattern_complexity: str = "FAIBLE"
    confidence: float = 0.8
    suggestions: List[str] = field(default_factory=list)


class DynamicSemanticAnalyzer:
    """Analyseur sémantique dynamique avec règles configurables et apprentissage."""
    
    def __init__(self, rules_path: str = "data/rules/mapping_rules.json"):
        self.rules_path = Path(rules_path)
        self.learning_path = Path("data/learning/feedback_history.json")
        self.rules = self._load_rules()
        self.feedback_history = self._load_feedback_history()
        self.learning_data = []
        
    def _load_rules(self) -> Dict:
        """Charge les règles de mapping depuis un fichier JSON."""
        default_rules = {
            "set_analysis": {
                "dax_patterns": {
                    "year_month": "CALCULATE with KEEPFILTERS for Year and Month",
                    "year_only": "CALCULATE with Year filter",
                    "year_dynamic": "CALCULATE with VAR and FILTER for dynamic year",
                    "complex": "CALCULATE with multiple filters",
                    "custom": ""
                },
                "examples": {
                    "year_month": "CALCULATE([Total Sales], KEEPFILTERS(Sales[Year] = _LatestYear), KEEPFILTERS(Sales[Month] = _LatestMonth))",
                    "year_only": "CALCULATE([Total Sales], Sales[Year] = 2025)",
                    "year_dynamic": "VAR CurrentYear = YEAR(TODAY()) RETURN CALCULATE([Total Sales], Sales[Year] = CurrentYear)",
                    "complex": "CALCULATE([Total Sales], FILTER(ALL(Sales), ...))"
                },
                "complexity_weights": {
                    "tables": 0.5,
                    "columns": 0.3,
                    "variables": 0.4,
                    "functions": 0.6,
                    "filters": 0.5,
                    "aggregations": 0.7,
                    "joins": 0.8
                },
                "detection_rules": {
                    "dynamic_year": ["vCurrentYear", "Year(Today())", "Year(Now())"],
                    "static_year": ["vMaxYear", "2025", "2024"],
                    "with_month": ["Month", "vMaxMonth"]
                }
            },
            "resident_group_by": {
                "dax_patterns": {
                    "default": "SUMMARIZE or GROUPBY",
                    "simple": "SUMMARIZE with single column",
                    "complex": "GROUPBY with multiple columns",
                    "custom": ""
                },
                "examples": {
                    "default": "SUMMARIZE(Sales, Sales[CustomerID], 'Total Sales', SUM(Sales[SalesAmount]))",
                    "simple": "SUMMARIZE(Sales, Sales[CustomerID], 'Sales', SUM(Sales[SalesAmount]))",
                    "complex": "GROUPBY(Sales, Sales[CustomerID], Sales[ProductID], 'Total Sales', SUMX(CURRENTGROUP(), Sales[SalesAmount]))"
                },
                "complexity_weights": {
                    "tables": 0.8,
                    "columns": 0.5,
                    "aggregations": 0.9
                },
                "detection_rules": {
                    "group_by_columns": ["CustomerID", "ProductID", "Region", "ChannelID"]
                }
            },
            "mapping_applymap": {
                "dax_patterns": {
                    "default": "LOOKUPVALUE",
                    "with_default": "LOOKUPVALUE with default value",
                    "custom": ""
                },
                "examples": {
                    "default": "LOOKUPVALUE(MappingTable[TargetColumn], MappingTable[KeyColumn], Sales[KeyColumn])",
                    "with_default": "COALESCE(LOOKUPVALUE(MappingTable[TargetColumn], MappingTable[KeyColumn], Sales[KeyColumn]), 'N/A')"
                },
                "complexity_weights": {
                    "tables": 0.7,
                    "columns": 0.6
                },
                "detection_rules": {
                    "mapping_tables": ["MAP_PRODUCT_GROUP_MAP"],
                    "target_fields": ["ProductGroupe"]
                }
            },
            "left_join": {
                "dax_patterns": {
                    "default": "NATURALLEFTOUTERJOIN or Power Query",
                    "power_query": "Merge tables in Power Query",
                    "custom": ""
                },
                "examples": {
                    "default": "NATURALLEFTOUTERJOIN(Table1, Table2)",
                    "power_query": "Table.NestedJoin(Table1, 'Key', Table2, 'Key', 'NewColumn')"
                },
                "complexity_weights": {
                    "tables": 0.8,
                    "joins": 1.0
                },
                "detection_rules": {
                    "join_tables": ["Customers", "Sales", "Products"]
                }
            },
            "subroutine": {
                "dax_patterns": {
                    "default": "DAX Function or Power Query",
                    "simple": "Calculated Column",
                    "complex": "Custom DAX Function",
                    "custom": ""
                },
                "examples": {
                    "default": "CREATE FUNCTION ...",
                    "simple": "Column = [Table[Column1]] + [Table[Column2]]",
                    "complex": "DEFINE VAR FunctionName = ... RETURN ..."
                },
                "complexity_weights": {
                    "variables": 0.9,
                    "functions": 1.0
                },
                "detection_rules": {
                    "subroutine_names": ["LoadFile"]
                }
            },
            "mapping_load": {
                "dax_patterns": {
                    "default": "Calculated Table",
                    "inline": "DATATABLE",
                    "custom": ""
                },
                "examples": {
                    "default": "MappingTable = SUMMARIZE(SourceTable, SourceTable[Key], 'Value', MAX(SourceTable[Value]))",
                    "inline": "DATATABLE('ProductID', STRING, 'ProductGroupe', STRING, {{'P1', 'Hard'}, {'P2', 'ACC'}})"
                },
                "complexity_weights": {
                    "tables": 0.7,
                    "columns": 0.6
                },
                "detection_rules": {
                    "inline_data": ["INLINE", "[", "]"]
                }
            },
            "variable_dollar_expansion": {
                "dax_patterns": {
                    "default": "VAR",
                    "simple": "VAR with simple value",
                    "complex": "VAR with expression",
                    "custom": ""
                },
                "examples": {
                    "default": "VAR VariableName = VALUE",
                    "simple": "VAR TableName = 'Table'",
                    "complex": "VAR CurrentYear = YEAR(TODAY())"
                },
                "complexity_weights": {
                    "variables": 0.3,
                    "functions": 0.2
                },
                "detection_rules": {
                    "simple_vars": ["vTableName", "vFileName"],
                    "complex_vars": ["vCurrentYear", "vMaxYear", "vMaxMonth"]
                }
            },
            "variable_declaration": {
                "dax_patterns": {
                    "default": "VAR",
                    "custom": ""
                },
                "examples": {
                    "default": "VAR VariableName = VALUE"
                },
                "complexity_weights": {
                    "variables": 0.2
                }
            }
        }
        
        if self.rules_path.exists():
            try:
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_rules
        else:
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                json.dump(default_rules, f, indent=2, ensure_ascii=False)
            return default_rules
    
    def _load_feedback_history(self) -> List[Dict]:
        """Charge l'historique des feedbacks."""
        if self.learning_path.exists():
            try:
                with open(self.learning_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        else:
            self.learning_path.parent.mkdir(parents=True, exist_ok=True)
            return []
    
    def _save_feedback(self) -> None:
        """Sauvegarde l'historique des feedbacks."""
        with open(self.learning_path, 'w', encoding='utf-8') as f:
            json.dump(self.feedback_history, f, indent=2, ensure_ascii=False)
    
    def update_rules(self, pattern_type: str, new_rule: Dict) -> None:
        """Met à jour les règles dynamiquement."""
        if pattern_type not in self.rules:
            self.rules[pattern_type] = {}
        
        for key, value in new_rule.items():
            if key in self.rules[pattern_type]:
                if isinstance(self.rules[pattern_type][key], dict):
                    self.rules[pattern_type][key].update(value)
                else:
                    self.rules[pattern_type][key] = value
            else:
                self.rules[pattern_type][key] = value
        
        with open(self.rules_path, 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, indent=2, ensure_ascii=False)
    
    def analyze(self, pattern_type: str, expression: str, 
                user_context: Dict = None) -> SemanticContext:
        """Analyse sémantique avec contexte utilisateur."""
        context = self._basic_analysis(pattern_type, expression)
        
        if user_context:
            context = self._apply_user_context(context, user_context)
        
        context.pattern_complexity = self._determine_complexity(context)
        context.confidence = self._calculate_confidence_advanced(context)
        context.suggestions = self._generate_suggestions(context)
        
        return context
    
    def _basic_analysis(self, pattern_type: str, expression: str) -> SemanticContext:
        """Analyse de base du pattern."""
        context = SemanticContext(
            pattern_type=pattern_type,
            expression=expression
        )
        
        context.tables = self._extract_tables(expression)
        context.columns = self._extract_columns(expression)
        context.variables = self._extract_variables(expression)
        context.functions = self._extract_functions(expression)
        context.filters = self._extract_filters(pattern_type, expression)
        context.aggregations = self._extract_aggregations(expression)
        context.joins = self._extract_joins(expression)
        context.complexity_score = self._calculate_complexity_score(context)
        
        return context
    
    def _extract_tables(self, expression: str) -> Set[str]:
        """Extrait les noms de tables."""
        tables = set()
        patterns = [
            r"(?:FROM|RESIDENT|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"Table\s*=\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)",
            r"Sales\s+\[(\w+)\]"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            tables.update(matches)
        return tables
    
    def _extract_columns(self, expression: str) -> Set[str]:
        """Extrait les noms de colonnes."""
        columns = set()
        patterns = [
            r"\[([A-Za-z_][A-Za-z0-9_]*)\]",
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*",
            r"(?:SUM|COUNT|AVG|MAX|MIN)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            columns.update(matches)
        return columns
    
    def _extract_variables(self, expression: str) -> Set[str]:
        """Extrait les variables Qlik."""
        variables = set()
        patterns = [
            r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)",
            r"(?:SET|LET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            r"v[A-Za-z_][A-Za-z0-9_]*"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            variables.update(matches)
        return variables
    
    def _extract_functions(self, expression: str) -> Set[str]:
        """Extrait les fonctions Qlik."""
        functions = set()
        qlik_functions = [
            "SUM", "COUNT", "AVG", "MAX", "MIN", "AGGR", "APPLYMAP",
            "PEEK", "PREVIOUS", "ABOVE", "BELOW", "RANGESUM",
            "IF", "PICK", "MATCH", "WILDMATCH", "TEXTBETWEEN",
            "DATE", "YEAR", "MONTH", "TODAY", "NOW"
        ]
        for func in qlik_functions:
            if func in expression.upper():
                functions.add(func)
        return functions
    
    def _extract_filters(self, pattern_type: str, expression: str) -> Dict[str, str]:
        """Extrait les filtres."""
        filters = {}
        if pattern_type == "set_analysis":
            filter_pattern = r"(\w+)\s*=\s*([^,}]+)"
            matches = re.findall(filter_pattern, expression)
            for key, value in matches:
                filters[key.strip()] = value.strip()
        return filters
    
    def _extract_aggregations(self, expression: str) -> Set[str]:
        """Extrait les agrégations."""
        aggregations = set()
        patterns = [
            r"SUM\s*\(([^)]*)\)",
            r"COUNT\s*\(([^)]*)\)",
            r"AVG\s*\(([^)]*)\)",
            r"MAX\s*\(([^)]*)\)",
            r"MIN\s*\(([^)]*)\)",
            r"AGGR\s*\(([^)]*)\)"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            for match in matches:
                if match.strip():
                    func_name = pattern.split('\\(')[0].strip().upper()
                    aggregations.add(f"{func_name}({match.strip()})")
        return aggregations
    
    def _extract_joins(self, expression: str) -> Set[str]:
        """Extrait les jointures."""
        joins = set()
        patterns = [
            r"(LEFT|RIGHT|INNER)\s+JOIN",
            r"JOIN\s+ON\s+(.+?)(?:\n|$)"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    joins.add(f"{match[0]} JOIN")
                else:
                    joins.add(match.strip())
        return joins
    
    def _calculate_complexity_score(self, context: SemanticContext) -> float:
        """Calcule le score de complexité en utilisant les règles."""
        weights = self.rules.get(context.pattern_type, {}).get("complexity_weights", {})
        
        score = 1.0
        score += len(context.tables) * weights.get("tables", 0.5)
        score += len(context.columns) * weights.get("columns", 0.3)
        score += len(context.variables) * weights.get("variables", 0.4)
        score += len(context.functions) * weights.get("functions", 0.6)
        score += len(context.filters) * weights.get("filters", 0.5)
        score += len(context.aggregations) * weights.get("aggregations", 0.7)
        score += len(context.joins) * weights.get("joins", 0.8)
        
        return min(score, 10.0)
    
    def _apply_user_context(self, context: SemanticContext, user_context: Dict) -> SemanticContext:
        """Applique le contexte utilisateur."""
        if "priorite" in user_context:
            if user_context["priorite"] == "HAUTE":
                context.complexity_score += 2.0
                context.confidence -= 0.1
            elif user_context["priorite"] == "BASSE":
                context.complexity_score -= 1.0
        
        if "tags" in user_context:
            context.filters["tags"] = user_context["tags"]
        
        if "note" in user_context:
            context.suggestions.append(f"Note utilisateur: {user_context['note']}")
        
        return context
    
    def _determine_complexity(self, context: SemanticContext) -> str:
        """Détermine la complexité de manière dynamique."""
        score = context.complexity_score
        
        if score > 7.0 or len(context.tables) > 3 or len(context.joins) > 2:
            return "ELEVEE"
        elif score > 4.0 or len(context.tables) > 1 or len(context.functions) > 5:
            return "MOYENNE"
        else:
            return "FAIBLE"
    
    def _calculate_confidence_advanced(self, context: SemanticContext) -> float:
        """Calcule la confiance de manière plus précise."""
        confidence = 0.8
        
        # Facteurs qui augmentent la confiance
        if len(context.tables) > 0:
            confidence += 0.05
        if len(context.columns) > 0:
            confidence += 0.05
        if len(context.functions) > 0:
            confidence += 0.05
        
        # Facteurs qui diminuent la confiance
        if len(context.variables) > 3:
            confidence -= 0.1
        if len(context.joins) > 1:
            confidence -= 0.1
        if "unknown" in context.expression.lower():
            confidence -= 0.1
        
        # Vérifier l'historique des feedbacks
        feedbacks = [f for f in self.feedback_history 
                    if f.get("pattern_type") == context.pattern_type]
        if feedbacks:
            avg_accuracy = sum(f.get("accuracy", 0.5) for f in feedbacks) / len(feedbacks)
            confidence = (confidence + avg_accuracy) / 2
        
        return max(0.3, min(0.95, confidence))
    
    def _detect_set_analysis_type(self, context: SemanticContext) -> str:
        """Détecte le type de Set Analysis."""
        if "Year" in context.filters and "Month" in context.filters:
            return "year_month"
        elif "Year" in context.filters:
            for var in context.variables:
                if "Current" in var or "Today" in var:
                    return "year_dynamic"
            return "year_only"
        else:
            return "complex"

    def _detect_resident_group_by_type(self, context: SemanticContext) -> str:
        """Détecte le type de Resident Group By."""
        if len(context.columns) <= 2:
            return "simple"
        else:
            return "complex"

    def _detect_mapping_type(self, context: SemanticContext) -> str:
        """Détecte le type de mapping."""
        if "INLINE" in context.expression.upper():
            return "inline"
        else:
            return "default"

    def _detect_subroutine_type(self, context: SemanticContext) -> str:
        """Détecte le type de subroutine."""
        if len(context.variables) <= 2:
            return "simple"
        else:
            return "complex"
    
    def _detect_variable_type(self, context: SemanticContext) -> str:
        """Détecte le type de variable."""
        if "vTableName" in context.expression or "vFileName" in context.expression:
            return "simple"
        else:
            return "complex"
    
    def _generate_detailed_suggestions(self, context: SemanticContext) -> List[str]:
        """Génère des suggestions détaillées pour chaque type de pattern."""
        suggestions = []
        
        if context.pattern_type == "set_analysis":
            set_type = self._detect_set_analysis_type(context)
            
            if set_type == "year_dynamic":
                suggestions.append("🔹 Utiliser VAR avec TODAY() pour l'année dynamique")
                suggestions.append("🔹 Exemple: VAR CurrentYear = YEAR(TODAY())")
                suggestions.append("🔹 Puis: CALCULATE([Total Sales], Sales[Year] = CurrentYear)")
            elif set_type == "year_month":
                suggestions.append("🔹 Utiliser KEEPFILTERS pour Year et Month")
                suggestions.append("🔹 Créer des variables pour LatestYear et LatestMonth")
            else:
                suggestions.append("🔹 Utiliser CALCULATE avec des filtres appropriés")
        
        elif context.pattern_type == "resident_group_by":
            suggestions.append("🔹 Utiliser SUMMARIZE() pour créer une table agrégée")
            suggestions.append("🔹 Spécifier les colonnes de groupement et les agrégations")
            suggestions.append("🔹 Vérifier les performances sur de grands volumes")
        
        elif context.pattern_type == "mapping_applymap":
            suggestions.append("🔹 Créer une table de mapping en DAX ou Power Query")
            suggestions.append("🔹 Utiliser LOOKUPVALUE() pour récupérer les valeurs")
            suggestions.append("🔹 Ajouter une valeur par défaut avec COALESCE()")
        
        elif context.pattern_type == "left_join":
            suggestions.append("🔹 Migrer en Power Query avec Table.NestedJoin()")
            suggestions.append("🔹 Ou utiliser NATURALLEFTOUTERJOIN() en DAX")
            suggestions.append("🔹 Vérifier les clés de jointure")
        
        elif context.pattern_type == "mapping_load":
            suggestions.append("🔹 Créer une table calculée en DAX")
            suggestions.append("🔹 Utiliser DATATABLE() pour les données inline")
            suggestions.append("🔹 Ou importer en Power Query")
        
        elif context.pattern_type == "variable_dollar_expansion":
            var_type = self._detect_variable_type(context)
            if var_type == "simple":
                suggestions.append("🔹 Variable simple - utiliser VAR en DAX")
                suggestions.append("🔹 Exemple: VAR TableName = 'Table'")
            else:
                suggestions.append("🔹 Variable complexe - utiliser VAR avec expression")
                suggestions.append("🔹 Exemple: VAR CurrentYear = YEAR(TODAY())")
        
        elif context.pattern_type == "variable_declaration":
            suggestions.append("🔹 Déclaration de variable - utiliser VAR en DAX")
            suggestions.append("🔹 Exemple: VAR VariableName = VALUE")
        
        elif context.pattern_type in ["subroutine_definition", "subroutine_call", "subroutine"]:
            sub_type = self._detect_subroutine_type(context)
            if sub_type == "simple":
                suggestions.append("🔹 Convertir en colonne calculée DAX")
            else:
                suggestions.append("🔹 Créer une fonction DAX personnalisée")
            suggestions.append("🔹 Ou migrer en Power Query M")
        
        return suggestions
    
    def _generate_suggestions(self, context: SemanticContext) -> List[str]:
        """Génère des suggestions basées sur l'analyse."""
        suggestions = []
        
        detailed_suggestions = self._generate_detailed_suggestions(context)
        suggestions.extend(detailed_suggestions)
        
        if context.pattern_complexity == "ELEVEE":
            suggestions.append("⚠️ Pattern complexe - tester avec des données de référence")
            suggestions.append("Documenter la logique pour l'équipe")
        elif context.pattern_complexity == "MOYENNE":
            suggestions.append("ℹ️ Vérifier les performances en production")
        
        return suggestions
    
    def learn_from_feedback(self, pattern_type: str, expression: str, 
                           feedback: Dict) -> None:
        """Apprend des retours humains."""
        feedback_entry = {
            "pattern_type": pattern_type,
            "expression": expression[:100],
            "feedback": feedback,
            "timestamp": datetime.now().isoformat(),
            "accuracy": feedback.get("accuracy", 0.5)
        }
        self.feedback_history.append(feedback_entry)
        self._save_feedback()
        
        if feedback.get("statut") == "NON_COUVERT" and feedback.get("correction_dax"):
            self.update_rules(pattern_type, {
                "dax_patterns": {
                    "custom": feedback["correction_dax"]
                }
            })
        
        if feedback.get("new_pattern"):
            self.update_rules(pattern_type, {
                "dax_patterns": {
                    "custom_pattern": feedback["new_pattern"]
                }
            })
    
    def suggest_dax(self, context: SemanticContext) -> Dict:
        """Suggère un équivalent DAX avec contexte amélioré."""
        suggestion = {
            "pattern_type": context.pattern_type,
            "complexity": context.complexity_score,
            "complexity_level": context.pattern_complexity,
            "confidence": context.confidence,
            "tables": list(context.tables),
            "columns": list(context.columns),
            "variables": list(context.variables),
            "functions": list(context.functions),
            "filters": context.filters,
            "suggestions": context.suggestions
        }
        
        pattern_rules = self.rules.get(context.pattern_type, {})
        dax_patterns = pattern_rules.get("dax_patterns", {})
        examples = pattern_rules.get("examples", {})
        
        if context.pattern_type == "set_analysis":
            set_type = self._detect_set_analysis_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(set_type, "CALCULATE with filters")
            suggestion["example"] = examples.get(set_type, "")
        elif context.pattern_type == "resident_group_by":
            res_type = self._detect_resident_group_by_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(res_type, dax_patterns.get("default", "SUMMARIZE"))
            suggestion["example"] = examples.get(res_type, examples.get("default", ""))
        elif context.pattern_type == "mapping_applymap":
            map_type = self._detect_mapping_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(map_type, dax_patterns.get("default", "LOOKUPVALUE"))
            suggestion["example"] = examples.get(map_type, examples.get("default", ""))
        elif context.pattern_type == "mapping_load":
            map_type = self._detect_mapping_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(map_type, dax_patterns.get("default", "Calculated Table"))
            suggestion["example"] = examples.get(map_type, examples.get("default", ""))
        elif context.pattern_type == "variable_dollar_expansion":
            var_type = self._detect_variable_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(var_type, dax_patterns.get("default", "VAR"))
            suggestion["example"] = examples.get(var_type, examples.get("default", ""))
        elif context.pattern_type == "variable_declaration":
            suggestion["dax_pattern"] = dax_patterns.get("default", "VAR")
            suggestion["example"] = examples.get("default", "")
        elif context.pattern_type in ["subroutine_definition", "subroutine_call", "subroutine"]:
            sub_type = self._detect_subroutine_type(context)
            suggestion["dax_pattern"] = dax_patterns.get(sub_type, dax_patterns.get("default", "DAX Function"))
            suggestion["example"] = examples.get(sub_type, examples.get("default", ""))
        else:
            suggestion["dax_pattern"] = dax_patterns.get("default", "À définir")
            suggestion["example"] = examples.get("default", "")
        
        if context.pattern_complexity == "ELEVEE":
            suggestion["warning"] = "⚠️ Pattern complexe - nécessite une attention particulière"
            suggestion["steps"] = [
                "1. Tester la mesure DAX avec des données de référence",
                "2. Vérifier les performances en production",
                "3. Documenter la logique pour l'équipe"
            ]
        elif context.pattern_complexity == "MOYENNE":
            suggestion["warning"] = "ℹ️ Pattern de complexité moyenne"
            suggestion["steps"] = ["1. Valider avec l'équipe métier"]
        else:
            suggestion["warning"] = "✅ Pattern simple - migration directe possible"
            suggestion["steps"] = ["1. Appliquer la mesure DAX existante"]
        
        return suggestion
    
    def get_statistics(self) -> Dict:
        """Retourne des statistiques sur l'analyse."""
        total_patterns = len(self.feedback_history)
        if total_patterns == 0:
            return {
                "total": 0,
                "average_accuracy": 0,
                "patterns_by_type": {},
                "most_complex": []
            }
        
        avg_accuracy = sum(f.get("accuracy", 0.5) for f in self.feedback_history) / total_patterns
        
        types = {}
        for f in self.feedback_history:
            t = f.get("pattern_type", "unknown")
            types[t] = types.get(t, 0) + 1
        
        return {
            "total": total_patterns,
            "average_accuracy": round(avg_accuracy, 2),
            "patterns_by_type": types,
            "most_recent": self.feedback_history[-3:] if len(self.feedback_history) >= 3 else self.feedback_history
        }
    
    def export_analysis(self, context: SemanticContext) -> Dict:
        """Exporte l'analyse complète."""
        suggestion = self.suggest_dax(context)
        
        return {
            "context": {
                "pattern_type": context.pattern_type,
                "expression": context.expression,
                "tables": list(context.tables),
                "columns": list(context.columns),
                "variables": list(context.variables),
                "functions": list(context.functions),
                "filters": context.filters,
                "aggregations": list(context.aggregations),
                "joins": list(context.joins)
            },
            "analysis": {
                "complexity_score": context.complexity_score,
                "complexity_level": context.pattern_complexity,
                "confidence": context.confidence,
                "suggestions": context.suggestions
            },
            "dax": {
                "pattern": suggestion.get("dax_pattern", ""),
                "example": suggestion.get("example", ""),
                "warning": suggestion.get("warning", ""),
                "steps": suggestion.get("steps", [])
            },
            "timestamp": datetime.now().isoformat()
        }