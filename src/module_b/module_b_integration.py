"""
Module B - Intégration complète
Assemble tous les composants du Module B pour une analyse fonctionnelle complète
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd

# Import des composants
from .qlik_parser import QlikParser
from .pbi_parser import extract_dax_measures, save_measures_as_text
from .mapping import map_all_patterns, generate_coverage_report, LLMMapper
from .coverage_analyzer import FunctionalCoverageAnalyzer
from .taxonomy import TAXONOMY_PATTERNS


@dataclass
class ModuleBResult:
    """Résultat complet du Module B."""
    # Statistiques générales
    total_patterns: int = 0
    total_measures: int = 0
    
    # Couverture
    covered: int = 0
    partially_covered: int = 0
    not_covered: int = 0
    errors: int = 0
    
    # Taux
    coverage_rate: float = 0.0
    effective_coverage: float = 0.0
    
    # Détails
    patterns: List[Dict] = field(default_factory=list)
    measures: List[Dict] = field(default_factory=list)
    variables: Dict = field(default_factory=dict)
    
    # Rapports
    mapping_results: List[Dict] = field(default_factory=list)
    coverage_report: Optional[Any] = None
    
    # Synthèse
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour l'affichage."""
        return {
            "total_patterns": self.total_patterns,
            "total_measures": self.total_measures,
            "covered": self.covered,
            "partially_covered": self.partially_covered,
            "not_covered": self.not_covered,
            "errors": self.errors,
            "coverage_rate": self.coverage_rate,
            "effective_coverage": self.effective_coverage,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "critical_issues": self.critical_issues
        }
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convertit les résultats en DataFrame pour affichage."""
        rows = []
        for r in self.mapping_results:
            rows.append({
                "Pattern": r.get("pattern", "unknown"),
                "Expression": r.get("expression_source", "")[:100] + "...",
                "Statut": r.get("statut", "ERREUR_PARSING"),
                "Mesure DAX": r.get("mesure_dax_correspondante") or "Aucune",
                "Confiance": f"{r.get('confiance', 0):.0%}",
                "Justification": r.get("justification", "")[:100] + "..."
            })
        return pd.DataFrame(rows)


class ModuleBIntegration:
    """
    Intégration complète du Module B.
    Orchestre tous les composants pour une analyse fonctionnelle.
    """
    
    def __init__(self):
        self.qlik_parser = QlikParser()
        self.mapper = LLMMapper()  # Utilisation de LLMMapper
        self.coverage_analyzer = FunctionalCoverageAnalyzer()
        self.qlik_variables = {}
    
    def analyze(self, 
                qlik_script_content: str,
                qlik_expressions_content: str = "",
                dax_measures_text: str = "",
                dax_measures_path: Optional[str] = None) -> ModuleBResult:
        """
        Analyse complète du Module B.
        
        Args:
            qlik_script_content: Contenu du script Qlik (.qvs)
            qlik_expressions_content: Contenu des expressions visuelles (.txt)
            dax_measures_text: Texte des mesures DAX
            dax_measures_path: Chemin vers le fichier des mesures DAX (optionnel)
            
        Returns:
            ModuleBResult avec tous les résultats
        """
        
        result = ModuleBResult()
        
        # === 1. Charger les mesures DAX ===
        if dax_measures_path and Path(dax_measures_path).exists():
            dax_content = Path(dax_measures_path).read_text(encoding="utf-8")
            result.measures = self._parse_dax_measures(dax_content)
            result.total_measures = len(result.measures)
        elif dax_measures_text:
            result.measures = self._parse_dax_measures(dax_measures_text)
            result.total_measures = len(result.measures)
        
        # === 2. Parser le script Qlik ===
        combined_content = qlik_script_content
        if qlik_expressions_content:
            combined_content += "\n\n" + qlik_expressions_content
        
        patterns = self.qlik_parser.parse_script(combined_content)
        result.total_patterns = len(patterns)
        result.patterns = patterns
        
        # === 3. Extraire les variables ===
        self.qlik_variables = self.qlik_parser.parse_variable_declarations(combined_content)
        result.variables = {v.get("name"): v for v in self.qlik_variables}
        
        # === 4. Mapping avec LLM ===
        dax_text = "\n".join([m.get("formule_dax", m.get("nom", "")) for m in result.measures])
        if not dax_text and dax_measures_text:
            dax_text = dax_measures_text
        
        mapping_results = []
        for pattern in patterns:
            mapped = self.mapper.map_pattern(pattern, dax_text)
            mapping_results.append(mapped)
        
        result.mapping_results = mapping_results
        
        # === 5. Statistiques ===
        stats = self._compute_stats(mapping_results)
        result.covered = stats["covered"]
        result.partially_covered = stats["partially"]
        result.not_covered = stats["not_covered"]
        result.errors = stats["errors"]
        result.coverage_rate = stats["coverage_rate"]
        result.effective_coverage = stats["effective_coverage"]
        
        # === 6. Générer la synthèse ===
        result.summary = self._generate_summary(result)
        result.recommendations = self._generate_recommendations(result)
        result.critical_issues = self._find_critical_issues(result)
        
        return result
    
    def _parse_dax_measures(self, text: str) -> List[Dict]:
        """Parse un texte DAX pour extraire les mesures."""
        measures = []
        lines = text.splitlines()
        
        current_measure = {}
        for line in lines:
            line = line.strip()
            if line.startswith("# Mesure :"):
                if current_measure:
                    measures.append(current_measure)
                current_measure = {"nom": line.replace("# Mesure :", "").strip()}
            elif line.startswith("# Table source :"):
                parts = line.replace("# Table source :", "").strip().split("|")
                if len(parts) >= 1:
                    current_measure["table_source"] = parts[0].strip()
                if len(parts) >= 2:
                    current_measure["colonne_source"] = parts[1].strip()
            elif line and not line.startswith("#"):
                if "formule_dax" not in current_measure:
                    current_measure["formule_dax"] = ""
                current_measure["formule_dax"] += line + "\n"
            elif not line and current_measure:
                if "formule_dax" not in current_measure:
                    current_measure["formule_dax"] = ""
                if current_measure.get("nom"):
                    measures.append(current_measure)
                current_measure = {}
        
        if current_measure and current_measure.get("nom"):
            measures.append(current_measure)
        
        return measures
    
    def _compute_stats(self, mapping_results: List[Dict]) -> Dict:
        """Calcule les statistiques à partir des résultats de mapping."""
        total = len(mapping_results) if mapping_results else 1
        
        covered = sum(1 for r in mapping_results if r.get("statut") == "COUVERT")
        partially = sum(1 for r in mapping_results if r.get("statut") == "PARTIELLEMENT_COUVERT")
        not_covered = sum(1 for r in mapping_results if r.get("statut") == "NON_COUVERT")
        errors = sum(1 for r in mapping_results if r.get("statut") == "ERREUR_PARSING")
        
        return {
            "covered": covered,
            "partially": partially,
            "not_covered": not_covered,
            "errors": errors,
            "coverage_rate": covered / total * 100 if total > 0 else 0,
            "effective_coverage": (covered + partially * 0.5) / total * 100 if total > 0 else 0
        }
    
    def _generate_summary(self, result: ModuleBResult) -> str:
        """Génère un résumé textuel des résultats."""
        return f"""
📊 **Résumé du Module B - Audit de couverture fonctionnelle**

**📈 Statistiques générales**
- **Total patterns détectés :** {result.total_patterns}
- **Mesures DAX disponibles :** {result.total_measures}
- **Variables Qlik :** {len(result.variables)}

**🎯 Couverture fonctionnelle**
- **🟢 Couverts :** {result.covered} ({result.coverage_rate:.1f}%)
- **🟠 Partiellement couverts :** {result.partially_covered} 
- **🔴 Non couverts :** {result.not_covered}
- **⚪ Erreurs de parsing :** {result.errors}

**📊 Taux de couverture**
- **Taux nominal :** {result.coverage_rate:.1f}%
- **Taux effectif :** {result.effective_coverage:.1f}% (avec partiels à 50%)

**🏷️ Niveau de couverture :** {self._get_coverage_level(result.effective_coverage)}
"""
    
    def _get_coverage_level(self, rate: float) -> str:
        """Détermine le niveau de couverture."""
        if rate >= 90:
            return "🟢 EXCELLENT"
        elif rate >= 70:
            return "🟡 BON"
        elif rate >= 50:
            return "🟠 MOYEN"
        else:
            return "🔴 CRITIQUE"
    
    def _generate_recommendations(self, result: ModuleBResult) -> List[str]:
        """Génère des recommandations d'action."""
        recommendations = []
        
        if result.not_covered > 0:
            recommendations.append(
                f"🔴 **{result.not_covered}** patterns non couverts - "
                f"migration manuelle requise pour ces fonctionnalités"
            )
        
        if result.partially_covered > 0:
            recommendations.append(
                f"🟠 **{result.partially_covered}** patterns partiellement couverts - "
                f"vérifier la cohérence des données"
            )
        
        if result.errors > 0:
            recommendations.append(
                f"⚪ **{result.errors}** erreurs de parsing - "
                f"expressions Qlik trop complexes ou syntaxe non reconnue"
            )
        
        if result.effective_coverage < 70:
            recommendations.append(
                "⚠️ **Taux de couverture faible** - "
                "une attention particulière est requise sur la migration"
            )
        
        if not recommendations:
            recommendations.append("✅ Tous les patterns sont correctement couverts !")
        
        return recommendations
    
    def _find_critical_issues(self, result: ModuleBResult) -> List[str]:
        """Identifie les problèmes critiques."""
        issues = []
        
        # Identifier les patterns critiques non couverts
        critical_patterns = ["section_access", "subroutine_definition", "nested_aggr"]
        
        for r in result.mapping_results:
            pattern = r.get("pattern", "")
            statut = r.get("statut", "")
            if pattern in critical_patterns and statut != "COUVERT":
                issues.append(
                    f"🔴 Pattern critique non couvert : **{pattern}** - "
                    f"{r.get('justification', 'Migration manuelle requise')}"
                )
        
        return issues


# ============================================================
# FONCTION PRINCIPALE D'EXPORT
# ============================================================

def analyze_functional_coverage(
    qlik_script_path: str,
    qlik_expressions_path: Optional[str] = None,
    dax_measures_path: Optional[str] = None
) -> ModuleBResult:
    """
    Analyse complète de la couverture fonctionnelle.
    
    Args:
        qlik_script_path: Chemin vers le script Qlik (.qvs)
        qlik_expressions_path: Chemin vers les expressions visuelles (.txt) (optionnel)
        dax_measures_path: Chemin vers les mesures DAX (optionnel)
        
    Returns:
        ModuleBResult complet
    """
    integrator = ModuleBIntegration()
    
    qlik_content = Path(qlik_script_path).read_text(encoding="utf-8")
    
    expr_content = ""
    if qlik_expressions_path and Path(qlik_expressions_path).exists():
        expr_content = Path(qlik_expressions_path).read_text(encoding="utf-8")
    
    dax_content = ""
    if dax_measures_path and Path(dax_measures_path).exists():
        dax_content = Path(dax_measures_path).read_text(encoding="utf-8")
    
    return integrator.analyze(
        qlik_script_content=qlik_content,
        qlik_expressions_content=expr_content,
        dax_measures_text=dax_content,
        dax_measures_path=dax_measures_path
    )


if __name__ == "__main__":
    # Test
    result = analyze_functional_coverage(
        "data/samples/case_encadrante_01/qlik/load_script.qvs",
        "data/samples/case_encadrante_01/qlik/expressions_completes.txt",
        "data/samples/case_encadrante_01/powerbi/measures_dax.txt"
    )
    
    print(result.summary)
    print("\n📋 Recommandations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
    
    if result.critical_issues:
        print("\n🚨 Problèmes critiques:")
        for issue in result.critical_issues:
            print(f"  - {issue}")
    
    print("\n📊 Détail par pattern:")
    df = result.to_dataframe()
    print(df.to_string(index=False))