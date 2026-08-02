"""
Parsers spécialisés pour les expressions Qlik Sense
Chaque type de pattern a son propre parser
"""

import re
from typing import List, Dict, Any, Optional
try:
    from .taxonomy import TAXONOMY_PATTERNS
except ImportError:
    from taxonomy import TAXONOMY_PATTERNS

class QlikParser:
    """Parseur principal pour les scripts Qlik"""
    
    def __init__(self):
        self.patterns = TAXONOMY_PATTERNS
    
    def parse_script(self, content: str) -> List[Dict[str, Any]]:
        """Parse un script Qlik complet et retourne tous les patterns détectés."""
        results = []
        
        # Parser chaque type de pattern
        results.extend(self.parse_variable_declarations(content))
        results.extend(self.parse_set_analysis(content))
        results.extend(self.parse_variable_expansions(content))
        results.extend(self.parse_applymap(content))
        results.extend(self.parse_mapping_load(content))
        results.extend(self.parse_subroutines(content))
        results.extend(self.parse_subroutine_calls(content))
        results.extend(self.parse_resident_group_by(content))
        results.extend(self.parse_left_join(content))
        results.extend(self.parse_load_inline(content))
        results.extend(self.parse_load_from_file(content))
        
        # Dédupliquer les résultats
        return self._deduplicate_results(results)
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Déduplique les résultats en gardant les plus détaillés."""
        seen = set()
        unique = []
        
        for r in results:
            key = f"{r['pattern']}_{r['expression_source'][:50]}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return unique
    
    # ============================================
    # PARSER: Variables
    # ============================================
    
    def parse_variable_declarations(self, content: str) -> List[Dict]:
        """Parse les déclarations de variables (SET vName = value)"""
        pattern = r"(?i)^\s*SET\s+([A-Za-z_]\w*)\s*=\s*(.+?)(?=;|\n\s*SET|\n\s*$)"
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        
        results = []
        for match in matches:
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            # Nettoyer la valeur
            value = re.sub(r'\s+', ' ', value)
            
            results.append({
                "pattern": "variable_declaration",
                "expression_source": match.group(0).strip(),
                "name": name,
                "value": value,
                "line": content[:match.start()].count('\n') + 1,
                "category": "VARIABLE",
                "complexity": 1
            })
        
        return results
    
    # ============================================
    # PARSER: Set Analysis
    # ============================================
    
    def parse_set_analysis(self, content: str) -> List[Dict]:
        """Parse les set analysis {<...>}"""
        pattern = r"(?i)\{<([^>]+)>}"
        matches = re.finditer(pattern, content)
        
        results = []
        for match in matches:
            set_content = match.group(1)
            filters = self._parse_set_filters(set_content)
            
            results.append({
                "pattern": "set_analysis",
                "expression_source": match.group(0),
                "filters": filters,
                "variables": self._extract_variables(set_content),
                "line": content[:match.start()].count('\n') + 1,
                "category": "ANALYSIS",
                "complexity": 3
            })
        
        return results
    
    def _parse_set_filters(self, content: str) -> List[Dict]:
        """Parse les filtres dans un set analysis."""
        filters = []
        parts = content.split(',')
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                filters.append({
                    "dimension": key.strip(),
                    "value": value.strip(),
                    "is_variable": '$(' in value
                })
        
        return filters
    
    # ============================================
    # PARSER: Variable Expansions
    # ============================================
    
    def parse_variable_expansions(self, content: str) -> List[Dict]:
        """Parse les expansions de variables $(...)"""
        pattern = r"\$\(([^)]+)\)"
        matches = re.finditer(pattern, content)
        
        results = []
        for match in matches:
            var_content = match.group(1).strip()
            is_nested = '=' in var_content or '$(' in var_content
            
            results.append({
                "pattern": "variable_dollar_expansion",
                "expression_source": match.group(0),
                "variable": var_content,
                "is_nested": is_nested,
                "line": content[:match.start()].count('\n') + 1,
                "category": "VARIABLE",
                "complexity": 2 if is_nested else 1
            })
        
        return results
    
    # ============================================
    # PARSER: ApplyMap
    # ============================================
    
    def parse_applymap(self, content: str) -> List[Dict]:
        """Parse les ApplyMap(...)"""
        pattern = r"(?i)ApplyMap\s*\(([^)]+)\)"
        matches = re.finditer(pattern, content)
        
        results = []
        for match in matches:
            args = self._split_applymap_args(match.group(1))
            
            results.append({
                "pattern": "mapping_applymap",
                "expression_source": match.group(0),
                "map_name": args[0] if len(args) > 0 else None,
                "key_field": args[1] if len(args) > 1 else None,
                "default_value": args[2] if len(args) > 2 else None,
                "line": content[:match.start()].count('\n') + 1,
                "category": "MAPPING",
                "complexity": 3
            })
        
        return results
    
    def _split_applymap_args(self, args_str: str) -> List[str]:
        """Sépare les arguments de ApplyMap."""
        # Gérer les cas avec guillemets
        args = []
        current = ""
        in_quotes = False
        quote_char = ""
        
        for char in args_str:
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = ""
                current += char
            elif char == ',' and not in_quotes:
                args.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            args.append(current.strip())
        
        return [a.strip() for a in args if a.strip()]
    
    # ============================================
    # PARSER: Mapping LOAD
    # ============================================
    
    def parse_mapping_load(self, content: str) -> List[Dict]:
        """Parse les Mapping LOAD"""
        pattern = r"(?i)Mapping\s+LOAD\s+\[?([^\],]+)\]?\s*,\s*\[?([^\],]+)\]?\s*(?:FROM|INLINE|RESIDENT)"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        results = []
        for match in matches:
            results.append({
                "pattern": "mapping_load",
                "expression_source": match.group(0).strip(),
                "key_field": match.group(1).strip(),
                "value_field": match.group(2).strip(),
                "line": content[:match.start()].count('\n') + 1,
                "category": "MAPPING",
                "complexity": 3
            })
        
        return results
    
    # ============================================
    # PARSER: Subroutines
    # ============================================
    
    def parse_subroutines(self, content: str) -> List[Dict]:
        """Parse les définitions de subroutines"""
        pattern = r"(?i)^\s*SUB\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*([\s\S]*?)(?=END SUB|$)"
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        results = []
        for match in matches:
            name = match.group(1).strip()
            params = [p.strip() for p in match.group(2).split(',') if p.strip()]
            body = match.group(3).strip()
            
            results.append({
                "pattern": "subroutine_definition",
                "expression_source": match.group(0).strip(),
                "name": name,
                "parameters": params,
                "body_length": len(body),
                "line": content[:match.start()].count('\n') + 1,
                "category": "SUBROUTINE",
                "complexity": 4
            })
        
        return results
    
    # ============================================
    # PARSER: Subroutine Calls
    # ============================================
    
    def parse_subroutine_calls(self, content: str) -> List[Dict]:
        """Parse les appels de subroutines"""
        pattern = r"(?i)^\s*CALL\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        results = []
        for match in matches:
            name = match.group(1).strip()
            args = [a.strip() for a in match.group(2).split(',') if a.strip()]
            
            results.append({
                "pattern": "subroutine_call",
                "expression_source": match.group(0).strip(),
                "name": name,
                "arguments": args,
                "line": content[:match.start()].count('\n') + 1,
                "category": "SUBROUTINE",
                "complexity": 2
            })
        
        return results
    
    # ============================================
    # PARSER: Resident Group By
    # ============================================
    
    def parse_resident_group_by(self, content: str) -> List[Dict]:
        """Parse les Resident ... Group By"""
        pattern = r"(?i)Resident\s+([A-Za-z_]\w*)\s+Group By\s+(.+?)(?=;|$)"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        results = []
        for match in matches:
            table = match.group(1).strip()
            group_fields = [f.strip() for f in match.group(2).split(',') if f.strip()]
            
            results.append({
                "pattern": "resident_group_by",
                "expression_source": match.group(0).strip(),
                "table": table,
                "group_fields": group_fields,
                "line": content[:match.start()].count('\n') + 1,
                "category": "GROUP_BY",
                "complexity": 3
            })
        
        return results
    
    # ============================================
    # PARSER: Left Join
    # ============================================
    
    def parse_left_join(self, content: str) -> List[Dict]:
        """Parse les LEFT JOIN"""
        pattern = r"(?i)^\s*left join\s*\(?\s*([A-Za-z_]\w*)\s*\)?\s*LOAD"
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        results = []
        for match in matches:
            table = match.group(1).strip()
            
            results.append({
                "pattern": "left_join",
                "expression_source": match.group(0).strip(),
                "table": table,
                "line": content[:match.start()].count('\n') + 1,
                "category": "JOIN",
                "complexity": 3
            })
        
        return results
    
    # ============================================
    # PARSER: LOAD INLINE
    # ============================================
    
    def parse_load_inline(self, content: str) -> List[Dict]:
        """Parse les LOAD ... INLINE"""
        pattern = r"(?i)LOAD\s+\*\s+INLINE\s*\[([^\]]*)\]"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        results = []
        for match in matches:
            inline_data = match.group(1).strip()
            lines = [l.strip() for l in inline_data.split('\n') if l.strip()]
            
            results.append({
                "pattern": "load_inline",
                "expression_source": match.group(0).strip(),
                "rows_count": len(lines) - 1 if len(lines) > 1 else 0,
                "headers": lines[0].split(',') if lines else [],
                "line": content[:match.start()].count('\n') + 1,
                "category": "LOAD",
                "complexity": 2
            })
        
        return results
    
    # ============================================
    # PARSER: LOAD FROM FILE
    # ============================================
    
    def parse_load_from_file(self, content: str) -> List[Dict]:
        """Parse les LOAD ... FROM"""
        pattern = r"(?i)LOAD\s+([\s\S]*?)\s+FROM\s+['\"]([^'\"]+)['\"]"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        results = []
        for match in matches:
            fields = [f.strip() for f in match.group(1).split(',') if f.strip()]
            file_path = match.group(2).strip()
            
            results.append({
                "pattern": "load_from_file",
                "expression_source": match.group(0).strip(),
                "fields": fields,
                "file_path": file_path,
                "line": content[:match.start()].count('\n') + 1,
                "category": "LOAD",
                "complexity": 2
            })
        
        return results
    
    def _extract_variables(self, text: str) -> List[str]:
        """Extrait les variables de la forme $(variable)"""
        pattern = r'\$\(([^)]+)\)'
        return re.findall(pattern, text)