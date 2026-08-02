# src/module_b/semantic_analyzer.py
"""
Analyseur sémantique avancé pour les patterns Qlik
"""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
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


class SemanticAnalyzer:
    """Analyse sémantique des patterns Qlik pour un mapping plus précis."""
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.context_cache = {}
    
    def _load_patterns(self) -> Dict:
        """Charge les patterns sémantiques."""
        return {
            "set_analysis": {
                "regex": r"\{<.*?>\}",
                "extractors": {
                    "filters": r"(\w+)\s*=\s*([^,}]+)",
                    "variables": r"\$\((\w+)\)",
                    "functions": r"(\w+)\s*\("
                }
            },
            "aggr": {
                "regex": r"Aggr\s*\(.*?\)",
                "extractors": {
                    "columns": r"\[(\w+)\]",
                    "dimensions": r"Aggr\s*\(.*?,\s*(.+?)\)",
                    "functions": r"(\w+)\s*\("
                }
            },
            "mapping": {
                "regex": r"Mapping\s+LOAD.*?RESIDENT",
                "extractors": {
                    "source_table": r"RESIDENT\s+(\w+)",
                    "target_fields": r"LOAD\s+([^,\n]+)",
                    "mapping_fields": r"INLINE\s*\[(.*?)\]"
                }
            },
            "join": {
                "regex": r"(?:Left|Right|Inner)\s+Join\s*\(",
                "extractors": {
                    "left_table": r"Left\s+Join\s*\(([^)]+)\)",
                    "right_table": r"Right\s+Join\s*\(([^)]+)\)",
                    "on_condition": r"ON\s+(.+?)(?=\n|$)"
                }
            },
            "subroutine": {
                "regex": r"SUB\s+(\w+)\s*\((.*?)\)",
                "extractors": {
                    "name": r"SUB\s+(\w+)",
                    "parameters": r"SUB\s+\w+\s*\((.*?)\)",
                    "body": r"SUB\s+\w+\s*\(.*?\)\s*(.*?)\s*END\s+SUB"
                }
            },
            "resident_group_by": {
                "regex": r"RESIDENT\s+(\w+)\s+GROUP\s+BY",
                "extractors": {
                    "table": r"RESIDENT\s+(\w+)",
                    "group_by": r"GROUP\s+BY\s+(.*?)(?:\n|$)",
                    "aggregations": r"(\w+)\s*\([^)]*\)\s+as"
                }
            }
        }
    
    def analyze(self, pattern_type: str, expression: str) -> SemanticContext:
        """Analyse sémantique d'un pattern."""
        context = SemanticContext(
            pattern_type=pattern_type,
            expression=expression
        )
        
        # Extraire les éléments sémantiques
        context.tables = self._extract_tables(pattern_type, expression)
        context.columns = self._extract_columns(pattern_type, expression)
        context.variables = self._extract_variables(expression)
        context.functions = self._extract_functions(expression)
        context.filters = self._extract_filters(pattern_type, expression)
        context.aggregations = self._extract_aggregations(expression)
        context.joins = self._extract_joins(expression)
        context.complexity_score = self._calculate_complexity(context)
        
        return context
    
    def _extract_tables(self, pattern_type: str, expression: str) -> Set[str]:
        """Extrait les noms de tables."""
        tables = set()
        
        # Patterns pour les tables
        table_patterns = [
            r"(?:FROM|RESIDENT|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"Table\s*=\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)",
            r"Sales\s+\[(\w+)\]"
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            tables.update(matches)
        
        return tables
    
    def _extract_columns(self, pattern_type: str, expression: str) -> Set[str]:
        """Extrait les noms de colonnes."""
        columns = set()
        
        # Patterns pour les colonnes
        column_patterns = [
            r"\[([A-Za-z_][A-Za-z0-9_]*)\]",
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*",
            r"(?:SUM|COUNT|AVG|MAX|MIN)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
        ]
        
        for pattern in column_patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            columns.update(matches)
        
        return columns
    
    def _extract_variables(self, expression: str) -> Set[str]:
        """Extrait les variables Qlik."""
        variables = set()
        
        # Patterns pour les variables
        var_patterns = [
            r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)",
            r"(?:SET|LET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            r"v[A-Za-z_][A-Za-z0-9_]*"
        ]
        
        for pattern in var_patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            variables.update(matches)
        
        return variables
    
    def _extract_functions(self, expression: str) -> Set[str]:
        """Extrait les fonctions Qlik."""
        functions = set()
        
        # Liste des fonctions Qlik courantes
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
        """Extrait les filtres (Set Analysis)."""
        filters = {}
        
        if pattern_type == "set_analysis":
            # Extraire les filtres de la Set Analysis
            filter_pattern = r"(\w+)\s*=\s*([^,}]+)"
            matches = re.findall(filter_pattern, expression)
            for key, value in matches:
                filters[key.strip()] = value.strip()
        
        return filters
    
    def _extract_aggregations(self, expression: str) -> Set[str]:
        """Extrait les agrégations."""
        aggregations = set()
        
        agg_patterns = [
            r"SUM\s*\(([^)]*)\)",
            r"COUNT\s*\(([^)]*)\)",
            r"AVG\s*\(([^)]*)\)",
            r"MAX\s*\(([^)]*)\)",
            r"MIN\s*\(([^)]*)\)",
            r"AGGR\s*\(([^)]*)\)"
        ]
        
        for pattern in agg_patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            for match in matches:
                if match.strip():
                    # Correction : extraire le nom de la fonction sans backslash
                    func_name = pattern.split('\\(')[0].strip().upper()
                    aggregations.add(f"{func_name}({match.strip()})")
        
        return aggregations
    
    def _extract_joins(self, expression: str) -> Set[str]:
        """Extrait les jointures."""
        joins = set()
        
        join_patterns = [
            r"(LEFT|RIGHT|INNER)\s+JOIN",
            r"JOIN\s+ON\s+(.+?)(?:\n|$)"
        ]
        
        for pattern in join_patterns:
            matches = re.findall(pattern, expression, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    joins.add(f"{match[0]} JOIN")
                else:
                    joins.add(match.strip())
        
        return joins
    
    def _calculate_complexity(self, context: SemanticContext) -> float:
        """Calcule un score de complexité pour le pattern."""
        score = 1.0
        
        # Nombre de tables
        score += len(context.tables) * 0.5
        
        # Nombre de colonnes
        score += len(context.columns) * 0.3
        
        # Nombre de variables
        score += len(context.variables) * 0.4
        
        # Nombre de fonctions
        score += len(context.functions) * 0.6
        
        # Nombre de filtres
        score += len(context.filters) * 0.5
        
        # Nombre d'agrégations
        score += len(context.aggregations) * 0.7
        
        # Nombre de jointures
        score += len(context.joins) * 0.8
        
        return min(score, 10.0)  # Max 10
    
    def suggest_dax_equivalent(self, context: SemanticContext) -> Dict:
        """Suggère un équivalent DAX basé sur l'analyse sémantique."""
        
        suggestions = {
            "pattern_type": context.pattern_type,
            "complexity": context.complexity_score,
            "tables": list(context.tables),
            "columns": list(context.columns),
            "variables": list(context.variables),
            "functions": list(context.functions)
        }
        
        # Détection du type de pattern pour suggestions spécifiques
        if context.pattern_type == "set_analysis":
            if "Year" in context.filters and "Month" in context.filters:
                suggestions["dax_pattern"] = "CALCULATE with KEEPFILTERS for Year and Month"
                suggestions["example"] = """
CALCULATE(
    [Total Sales],
    KEEPFILTERS(Sales[Year] = _LatestYear),
    KEEPFILTERS(Sales[Month] = _LatestMonth)
)"""
            elif "Year" in context.filters:
                suggestions["dax_pattern"] = "CALCULATE with Year filter"
                suggestions["example"] = "CALCULATE([Total Sales], Sales[Year] = 2025)"
            else:
                suggestions["dax_pattern"] = "CALCULATE with multiple filters"
                suggestions["example"] = "CALCULATE([Total Sales], FILTER(ALL(Sales), ...))"
        
        elif context.pattern_type == "resident_group_by":
            suggestions["dax_pattern"] = "SUMMARIZE or GROUPBY"
            suggestions["example"] = """
SUMMARIZE(
    Sales,
    Sales[CustomerID],
    "Total Sales", SUM(Sales[SalesAmount])
)"""
        
        elif context.pattern_type == "left_join":
            suggestions["dax_pattern"] = "NATURALLEFTOUTERJOIN or Power Query"
            suggestions["example"] = "NATURALLEFTOUTERJOIN(Table1, Table2)"
        
        elif context.pattern_type == "subroutine":
            suggestions["dax_pattern"] = "DAX Function or Power Query"
            suggestions["example"] = "CREATE FUNCTION ..."
        
        elif context.pattern_type == "mapping":
            suggestions["dax_pattern"] = "LOOKUPVALUE or RELATED"
            suggestions["example"] = "LOOKUPVALUE(Table[Column], Table[Key], Value)"
        
        return suggestions
    
    def analyze_all_patterns(self, patterns: List[Dict], dax_measures: List[str]) -> List[Dict]:
        """Analyse tous les patterns et propose des mappings DAX."""
        results = []
        
        for pattern in patterns:
            context = self.analyze(
                pattern.get("pattern", ""),
                pattern.get("expression_source", "")
            )
            
            suggestions = self.suggest_dax_equivalent(context)
            
            # Vérifier si une mesure DAX correspondante existe
            matching_measure = self._find_matching_measure(context, dax_measures)
            
            results.append({
                **pattern,
                "semantic_context": {
                    "tables": list(context.tables),
                    "columns": list(context.columns),
                    "variables": list(context.variables),
                    "functions": list(context.functions),
                    "filters": context.filters,
                    "aggregations": list(context.aggregations),
                    "complexity": context.complexity_score
                },
                "dax_suggestion": suggestions,
                "matching_measure": matching_measure
            })
        
        return results
    
    def _find_matching_measure(self, context: SemanticContext, dax_measures: List[str]) -> Optional[str]:
        """Trouve une mesure DAX correspondante."""
        for measure in dax_measures:
            measure_lower = measure.lower()
            
            # Vérifier si les colonnes correspondent
            for col in context.columns:
                if col.lower() in measure_lower:
                    return measure
            
            # Vérifier si les tables correspondent
            for table in context.tables:
                if table.lower() in measure_lower:
                    return measure
            
            # Vérifier si les agrégations correspondent
            for agg in context.aggregations:
                if agg.lower() in measure_lower:
                    return measure
        
        return None