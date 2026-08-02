"""
Extraction des visuels, KPIs et métriques depuis un script Qlik
Version améliorée avec détection avancée des KPIs et expressions
"""

import re
from typing import Dict, List, Any
from collections import defaultdict


class QlikVisualExtractor:
    """
    Extrait tous les visuels, KPIs, mesures et pages d'un script Qlik.
    Version améliorée avec détection avancée.
    """
    
    def __init__(self):
        self.results = {
            "pages": [],
            "kpis": [],
            "charts": [],
            "tables": [],
            "filters": [],
            "measures": [],
            "dimensions": [],
            "variables": [],
            "subroutines": [],
            "set_analysis": [],
            "mappings": []
        }
    
    def extract_all(self, content: str) -> Dict[str, Any]:
        """Extrait tous les éléments du script Qlik."""
        
        # 1. Extraire les pages (sheets)
        self.results["pages"] = self._extract_pages(content)
        
        # 2. Extraire les KPIs (amélioré)
        self.results["kpis"] = self._extract_kpis_advanced(content)
        
        # 3. Extraire les graphiques
        self.results["charts"] = self._extract_charts(content)
        
        # 4. Extraire les tableaux
        self.results["tables"] = self._extract_tables(content)
        
        # 5. Extraire les filtres
        self.results["filters"] = self._extract_filters(content)
        
        # 6. Extraire les mesures (amélioré)
        self.results["measures"] = self._extract_measures_advanced(content)
        
        # 7. Extraire les dimensions
        self.results["dimensions"] = self._extract_dimensions(content)
        
        # 8. Extraire les variables
        self.results["variables"] = self._extract_variables(content)
        
        # 9. Extraire les subroutines
        self.results["subroutines"] = self._extract_subroutines(content)
        
        # 10. Extraire les Set Analysis
        self.results["set_analysis"] = self._extract_set_analysis(content)
        
        # 11. Extraire les mappings
        self.results["mappings"] = self._extract_mappings(content)
        
        return self.results
    
    def _extract_pages(self, content: str) -> List[Dict]:
        """Extrait les pages (sheets) du script."""
        pages = []
        
        patterns = [
            r'(?i)(?:Sheet|Feuille)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Page|Page)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Tab|Onglet)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name not in [p["name"] for p in pages]:
                    pages.append({
                        "name": name,
                        "type": "page",
                        "expression": match.group(0).strip()
                    })
        
        # Si aucune page trouvée, chercher dans les commentaires ou titres
        if not pages:
            title_pattern = r'(?i)(?:Title|Titre|Dashboard)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)'
            matches = re.finditer(title_pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name not in [p["name"] for p in pages]:
                    pages.append({
                        "name": name,
                        "type": "page",
                        "expression": match.group(0).strip()
                    })
        
        # Si toujours aucune page, ajouter une page par défaut
        if not pages:
            pages.append({
                "name": "Main",
                "type": "page",
                "expression": "Sheet: Main"
            })
        
        return pages
    
    def _extract_kpis_advanced(self, content: str) -> List[Dict]:
        """Extrait les KPIs de manière avancée."""
        kpis = []
        kpi_names = set()
        
        # 1. Pattern KPI explicite
        kpi_patterns = [
            r'(?i)(?:KPI|kpi)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*=\s*([^;\n]+)',
            r'(?i)(?:KPI|kpi)\s+([A-Za-z_][A-Za-z0-9_\- ]*)\s*=\s*([^;\n]+)',
            r'(?i)(?:Measure|Mesure)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*=\s*([^;\n]+)',
            r'(?i)(?:Expression|Expression)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*=\s*([^;\n]+)'
        ]
        
        for pattern in kpi_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                expression = match.group(2).strip()
                
                if name not in kpi_names:
                    kpi_names.add(name)
                    kpis.append({
                        "name": name,
                        "expression": expression,
                        "type": "kpi",
                        "source": "explicit",
                        "aggregation": self._detect_aggregation(expression),
                        "raw": match.group(0).strip()
                    })
        
        # 2. Variables qui ressemblent à des KPIs (vCurrentYear, vMaxYear, etc.)
        var_pattern = r'(?i)^\s*SET\s+(v[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)(?=;|\n\s*SET|\n\s*$)'
        matches = re.finditer(var_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            # Vérifier si c'est un KPI (contient des fonctions de date/agrégation)
            kpi_keywords = ['year', 'today', 'now', 'max', 'min', 'sum', 'count', 'avg', 'month', 'date']
            if any(keyword in value.lower() for keyword in kpi_keywords):
                if name not in kpi_names:
                    kpi_names.add(name)
                    kpis.append({
                        "name": name,
                        "expression": value,
                        "type": "kpi",
                        "source": "variable",
                        "aggregation": self._detect_aggregation(value),
                        "raw": match.group(0).strip()
                    })
        
        # 3. Expressions avec des fonctions d'agrégation qui pourraient être des KPIs
        agg_pattern = r'(?i)(SUM|COUNT|AVG|MAX|MIN|AGGR)\s*\([^)]*\)\s*(?:AS\s+([A-Za-z_][A-Za-z0-9_\- ]*))?'
        matches = re.finditer(agg_pattern, content)
        
        for match in matches:
            agg_func = match.group(1).upper()
            name = match.group(2) if match.group(2) else f"{agg_func}_Measure"
            
            if name not in kpi_names:
                kpi_names.add(name)
                kpis.append({
                    "name": name,
                    "expression": match.group(0).strip(),
                    "type": "kpi",
                    "source": "aggregation",
                    "aggregation": agg_func.lower(),
                    "raw": match.group(0).strip()
                })
        
        # 4. Expressions de set analysis
        set_pattern = r'(?i)\{<([^>]+)>\}\s*(SUM|COUNT|AVG|MAX|MIN)\s*\(([^)]*)\)\s*(?:AS\s+([A-Za-z_][A-Za-z0-9_\- ]*))?'
        matches = re.finditer(set_pattern, content)
        
        for match in matches:
            set_analysis = match.group(1)
            agg_func = match.group(2).upper()
            field = match.group(3)
            name = match.group(4) if match.group(4) else f"Set_{agg_func}"
            
            if name not in kpi_names:
                kpi_names.add(name)
                kpis.append({
                    "name": name,
                    "expression": match.group(0).strip(),
                    "type": "kpi",
                    "source": "set_analysis",
                    "set_analysis": set_analysis,
                    "aggregation": agg_func.lower(),
                    "raw": match.group(0).strip()
                })
        
        return kpis
    
    def _extract_charts(self, content: str) -> List[Dict]:
        """Extrait les graphiques du script."""
        charts = []
        chart_names = set()
        
        patterns = [
            r'(?i)(?:Chart|Graph|BarChart|LineChart|PieChart|ComboChart|ScatterChart)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Object|Objet)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*,\s*Type\s*=\s*(?:Chart|Graph|Bar|Line|Pie)',
            r'(?i)(?:Visualization|Visualisation)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name not in chart_names:
                    chart_names.add(name)
                    charts.append({
                        "name": name,
                        "type": "chart",
                        "raw": match.group(0).strip()
                    })
        
        # Chercher aussi les graphiques par leur nom dans les expressions
        chart_ref_pattern = r'(?i)(?:Chart|Graph)\s+([A-Za-z_][A-Za-z0-9_\- ]*)'
        matches = re.finditer(chart_ref_pattern, content)
        for match in matches:
            name = match.group(1).strip()
            if name not in chart_names:
                chart_names.add(name)
                charts.append({
                    "name": name,
                    "type": "chart_reference",
                    "raw": match.group(0).strip()
                })
        
        return charts
    
    def _extract_tables(self, content: str) -> List[Dict]:
        """Extrait les tableaux du script."""
        tables = []
        table_names = set()
        
        patterns = [
            r'(?i)(?:Table|Tableau|StraightTable|PivotTable)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Object|Objet)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*,\s*Type\s*=\s*Table',
            r'(?i)(?:Grid|Grille)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name not in table_names:
                    table_names.add(name)
                    tables.append({
                        "name": name,
                        "type": "table",
                        "raw": match.group(0).strip()
                    })
        
        return tables
    
    def _extract_filters(self, content: str) -> List[Dict]:
        """Extrait les filtres du script."""
        filters = []
        filter_names = set()
        
        patterns = [
            r'(?i)(?:Filter|Filtre|ListBox|Dropdown)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Dimension)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*,\s*Type\s*=\s*Filter',
            r'(?i)(?:Selection|Sélection)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name not in filter_names:
                    filter_names.add(name)
                    filters.append({
                        "name": name,
                        "type": "filter",
                        "raw": match.group(0).strip()
                    })
        
        # Chercher les filtres dans les Set Analysis
        set_filter_pattern = r'(?i)\{<([^>]+)>\}'
        matches = re.finditer(set_filter_pattern, content)
        for match in matches:
            filter_content = match.group(1)
            # Extraire les dimensions filtrées
            dim_matches = re.findall(r'(\w+)\s*=\s*[^,}]+', filter_content)
            for dim in dim_matches:
                if dim not in filter_names:
                    filter_names.add(dim)
                    filters.append({
                        "name": dim,
                        "type": "set_analysis_filter",
                        "raw": match.group(0).strip()
                    })
        
        return filters
    
    def _extract_measures_advanced(self, content: str) -> List[Dict]:
        """Extrait les mesures de manière avancée."""
        measures = []
        measure_names = set()
        
        # Expressions avec AS
        pattern = r'(?i)(?:SUM|COUNT|AVG|MAX|MIN|CALCULATE|DIVIDE)\s*\([^)]*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_\- ]*)'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            name = match.group(1).strip()
            if name not in measure_names:
                measure_names.add(name)
                measures.append({
                    "name": name,
                    "expression": match.group(0).strip(),
                    "type": "measure",
                    "raw": match.group(0).strip()
                })
        
        # Expressions sans AS
        expr_pattern = r'(?i)(SUM|COUNT|AVG|MAX|MIN)\s*\(([^)]*)\)'
        matches = re.finditer(expr_pattern, content)
        for match in matches:
            func = match.group(1).upper()
            field = match.group(2).strip()
            # Essayer de trouver un nom dans le contexte
            name = f"{func}_{field.replace('[', '').replace(']', '').strip()}"
            if name not in measure_names and len(field) > 0:
                measure_names.add(name)
                measures.append({
                    "name": name,
                    "expression": match.group(0).strip(),
                    "type": "measure",
                    "raw": match.group(0).strip()
                })
        
        return measures
    
    def _extract_dimensions(self, content: str) -> List[Dict]:
        """Extrait les dimensions du script."""
        dimensions = []
        dim_names = set()
        
        patterns = [
            r'(?i)(?:Dimension|Dim)\s*:\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*=\s*([^;]+)',
            r'(?i)Group\s+By\s+([A-Za-z_][A-Za-z0-9_\- ]*)',
            r'(?i)(?:Dimension)\s+([A-Za-z_][A-Za-z0-9_\- ]*)\s+AS\s+([A-Za-z_][A-Za-z0-9_\- ]*)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                if len(match.groups()) == 2:
                    if pattern.endswith(r'AS\s+([A-Za-z_][A-Za-z0-9_\- ]*)'):
                        name = match.group(2).strip()
                        expression = match.group(1).strip()
                    else:
                        name = match.group(1).strip()
                        expression = match.group(2).strip()
                else:
                    name = match.group(1).strip()
                    expression = match.group(0).strip()
                
                if name not in dim_names:
                    dim_names.add(name)
                    dimensions.append({
                        "name": name,
                        "expression": expression,
                        "type": "dimension",
                        "raw": match.group(0).strip()
                    })
        
        return dimensions
    
    def _extract_variables(self, content: str) -> List[Dict]:
        """Extrait les variables du script."""
        variables = []
        var_names = set()
        
        pattern = r'(?i)^\s*SET\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)(?=;|\n\s*SET|\n\s*$)'
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            if name not in var_names:
                var_names.add(name)
                variables.append({
                    "name": name,
                    "value": value,
                    "type": "variable",
                    "raw": match.group(0).strip()
                })
        
        # Chercher les LET variables
        let_pattern = r'(?i)^\s*LET\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)(?=;|\n\s*LET|\n\s*$)'
        matches = re.finditer(let_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            if name not in var_names:
                var_names.add(name)
                variables.append({
                    "name": name,
                    "value": value,
                    "type": "variable",
                    "raw": match.group(0).strip()
                })
        
        return variables
    
    def _extract_subroutines(self, content: str) -> List[Dict]:
        """Extrait les subroutines du script."""
        subroutines = []
        sub_names = set()
        
        pattern = r'(?i)^\s*SUB\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*([\s\S]*?)(?=END SUB|$)'
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        for match in matches:
            name = match.group(1).strip()
            if name not in sub_names:
                sub_names.add(name)
                params = [p.strip() for p in match.group(2).split(',') if p.strip()]
                body = match.group(3).strip()
                
                subroutines.append({
                    "name": name,
                    "parameters": params,
                    "body_length": len(body),
                    "body": body[:200] + "..." if len(body) > 200 else body,
                    "type": "subroutine",
                    "raw": match.group(0).strip()[:200] + "..."
                })
        
        return subroutines
    
    def _extract_set_analysis(self, content: str) -> List[Dict]:
        """Extrait les Set Analysis du script."""
        set_analysis = []
        set_ids = set()
        
        pattern = r'(?i)\{<([^>]+)>\}'
        matches = re.finditer(pattern, content)
        
        for match in matches:
            set_content = match.group(1)
            if set_content not in set_ids:
                set_ids.add(set_content)
                # Extraire les filtres
                filters = []
                for part in set_content.split(','):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        filters.append({
                            "dimension": key.strip(),
                            "value": value.strip(),
                            "is_variable": '$(' in value
                        })
                
                set_analysis.append({
                    "expression": match.group(0).strip(),
                    "filters": filters,
                    "raw": match.group(0).strip()
                })
        
        return set_analysis
    
    def _extract_mappings(self, content: str) -> List[Dict]:
        """Extrait les mappings du script."""
        mappings = []
        map_names = set()
        
        pattern = r'(?i)Mapping\s+LOAD\s+\[?([^\],]+)\]?\s*,\s*\[?([^\],]+)\]?\s*(?:FROM|INLINE|RESIDENT)'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            key_field = match.group(1).strip()
            value_field = match.group(2).strip()
            map_id = f"{key_field}_{value_field}"
            
            if map_id not in map_names:
                map_names.add(map_id)
                mappings.append({
                    "key_field": key_field,
                    "value_field": value_field,
                    "type": "mapping_load",
                    "raw": match.group(0).strip()
                })
        
        # ApplyMap
        apply_pattern = r'(?i)ApplyMap\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*(?:,\s*([^)]+))?\s*\)'
        matches = re.finditer(apply_pattern, content)
        
        for match in matches:
            map_name = match.group(1).strip()
            key_field = match.group(2).strip()
            default_value = match.group(3).strip() if match.group(3) else None
            
            mappings.append({
                "map_name": map_name,
                "key_field": key_field,
                "default_value": default_value,
                "type": "applymap",
                "raw": match.group(0).strip()
            })
        
        return mappings
    
    def _detect_aggregation(self, expression: str) -> str:
        """Détecte le type d'agrégation dans une expression."""
        expr_lower = expression.lower()
        if "sum(" in expr_lower:
            return "sum"
        elif "count(" in expr_lower:
            return "count"
        elif "avg(" in expr_lower:
            return "avg"
        elif "max(" in expr_lower:
            return "max"
        elif "min(" in expr_lower:
            return "min"
        elif "aggr(" in expr_lower:
            return "aggr"
        else:
            return "unknown"
    
    def get_summary(self, content: str) -> Dict:
        """Retourne un résumé des éléments extraits."""
        results = self.extract_all(content)
        
        return {
            "pages_count": len(results["pages"]),
            "kpis_count": len(results["kpis"]),
            "charts_count": len(results["charts"]),
            "tables_count": len(results["tables"]),
            "filters_count": len(results["filters"]),
            "measures_count": len(results["measures"]),
            "dimensions_count": len(results["dimensions"]),
            "variables_count": len(results["variables"]),
            "subroutines_count": len(results["subroutines"]),
            "set_analysis_count": len(results["set_analysis"]),
            "mappings_count": len(results["mappings"]),
            "pages": [p["name"] for p in results["pages"]],
            "kpis": [k["name"] for k in results["kpis"]],
            "kpis_detail": results["kpis"],
            "charts": [c["name"] for c in results["charts"]],
            "tables": [t["name"] for t in results["tables"]],
            "filters": [f["name"] for f in results["filters"]],
            "measures": [m["name"] for m in results["measures"]],
            "dimensions": [d["name"] for d in results["dimensions"]],
            "variables": [v["name"] for v in results["variables"]],
            "subroutines": [s["name"] for s in results["subroutines"]],
            "set_analysis": results["set_analysis"],
            "mappings": results["mappings"]
        }


def extract_qlik_visuals(content: str) -> Dict:
    """
    Fonction rapide pour extraire les visuels d'un script Qlik.
    """
    extractor = QlikVisualExtractor()
    return extractor.get_summary(content)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = extract_qlik_visuals(content)
        
        print("=" * 60)
        print("📊 EXTRACTION DES VISUELS QLIK")
        print("=" * 60)
        
        print(f"\n📈 Statistiques:")
        print(f"   Pages: {result.get('pages_count', 0)}")
        print(f"   KPIs: {result.get('kpis_count', 0)}")
        print(f"   Graphiques: {result.get('charts_count', 0)}")
        print(f"   Tableaux: {result.get('tables_count', 0)}")
        print(f"   Filtres: {result.get('filters_count', 0)}")
        print(f"   Mesures: {result.get('measures_count', 0)}")
        print(f"   Dimensions: {result.get('dimensions_count', 0)}")
        print(f"   Variables: {result.get('variables_count', 0)}")
        print(f"   Subroutines: {result.get('subroutines_count', 0)}")
        print(f"   Set Analysis: {result.get('set_analysis_count', 0)}")
        print(f"   Mappings: {result.get('mappings_count', 0)}")
        
        if result.get('pages'):
            print(f"\n📋 Pages: {', '.join(result['pages'])}")
        if result.get('kpis'):
            print(f"\n📈 KPIs: {', '.join(result['kpis'])}")
            print(f"\n📊 Détail des KPIs:")
            for k in result.get('kpis_detail', [])[:10]:
                print(f"   - {k.get('name')} ({k.get('source', 'unknown')}) : {k.get('expression')[:60]}...")
        if result.get('charts'):
            print(f"\n🖼️ Graphiques: {', '.join(result['charts'])}")
        if result.get('tables'):
            print(f"\n📊 Tableaux: {', '.join(result['tables'])}")
        if result.get('filters'):
            print(f"\n🔍 Filtres: {', '.join(result['filters'])}")
        if result.get('measures'):
            print(f"\n📐 Mesures: {', '.join(result['measures'][:10])}{'...' if len(result['measures']) > 10 else ''}")
        if result.get('dimensions'):
            print(f"\n📏 Dimensions: {', '.join(result['dimensions'])}")
        if result.get('variables'):
            print(f"\n📋 Variables: {', '.join(result['variables'][:10])}{'...' if len(result['variables']) > 10 else ''}")
    else:
        print("Usage: python qlik_visual_extractor.py <chemin_fichier.qvs>")