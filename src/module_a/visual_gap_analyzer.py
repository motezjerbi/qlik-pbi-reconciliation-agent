# src/module_a/visual_gap_analyzer.py
"""
Détection des écarts STRUCTURELS entre Qlik et Power BI :
- dimensions Qlik sans colonne équivalente trouvée côté Power BI
- pages/feuilles où le nombre de visuels diffère fortement

Complète le Module A (écarts de valeurs) et le Module B (patterns de script) :
ni l'un ni l'autre ne détecte qu'un visuel a disparu ou qu'une dimension n'a
pas été migrée, même quand aucun nombre n'est "faux" à proprement parler.

Findings produits au même schéma que kpi_reconciliation.py / coverage_analyzer.py
(source_module, libelle, detail, criticite, diagnostic, recommandation, statut)
pour s'intégrer directement à orchestrator.merge_findings.
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _pbi_column_names(pbi_result: Dict) -> List[str]:
    """Gère les deux formats possibles : liste de dicts {table,name} (extraction
    live) ou liste de chaînes (repli ZIP)."""
    names = []
    for c in pbi_result.get("columns", []) or []:
        if isinstance(c, dict):
            names.append(c.get("name", ""))
        else:
            names.append(str(c))
    return [n for n in names if n]


def _collect_qlik_dimension_fields(qlik_result: Dict) -> List[Dict]:
    """Rassemble les champs de dimension Qlik à vérifier : les dimensions
    MASTER (réutilisables, déclarées explicitement) + les dimensions utilisées
    directement dans un visuel sans être une dimension master (ex. 'Channel'
    utilisé dans un graphique sans jamais être promu en dimension nommée —
    cas fréquent, et justement le genre de champ qui se perd facilement à la
    migration puisqu'il n'a pas de fiche dédiée à vérifier)."""
    seen = set()
    out = []

    for dim in qlik_result.get("dimensions", []) or []:
        field = (dim.get("field") or dim.get("name") or "").strip()
        if field and _norm(field) not in seen:
            seen.add(_norm(field))
            out.append({"name": dim.get("name") or field, "field": field, "source": "master"})

    for visual in qlik_result.get("visuals", []) or []:
        for field in visual.get("dimensions", []) or []:
            field = (field or "").strip()
            if field and _norm(field) not in seen:
                seen.add(_norm(field))
                out.append({
                    "name": field,
                    "field": field,
                    "source": f"visuel '{visual.get('name', '')}' (feuille {visual.get('sheet', '')})",
                })

    return out


def detect_dimension_gaps(qlik_result: Dict, pbi_result: Dict, threshold: float = 0.6) -> List[Dict]:
    """Repère les dimensions Qlik (master OU utilisées dans un visuel) dont le
    champ source ne semble correspondre à AUCUNE colonne du modèle Power BI
    (piste : dimension non migrée)."""
    findings = []
    pbi_columns = _pbi_column_names(pbi_result)
    pbi_columns_norm = [_norm(c) for c in pbi_columns]

    for dim in _collect_qlik_dimension_fields(qlik_result):
        field = dim["field"]
        field_norm = _norm(field)
        best_score = max(
            (_similarity(field_norm, c) for c in pbi_columns_norm), default=0.0
        )
        if best_score < threshold:
            findings.append({
                "source_module": "Module A - Structural Gaps",
                "libelle": f"Dimension possiblement non migrée : {dim['name']}",
                "detail": (
                    f"Champ Qlik source : '{field}' (repéré via {dim['source']}). "
                    f"Aucune colonne Power BI suffisamment proche trouvée "
                    f"(meilleur score : {best_score:.2f})."
                ),
                "criticite": "MAJEUR",
                "diagnostic": (
                    "Cette dimension existe côté Qlik mais aucune colonne du modèle "
                    "Power BI ne lui correspond clairement — elle n'a peut-être pas "
                    "été migrée, ou a été renommée au point d'être introuvable "
                    "automatiquement."
                ),
                "recommandation": (
                    "Vérifier manuellement dans le modèle Power BI si cette "
                    "dimension existe sous un autre nom, ou si son absence est "
                    "une régression fonctionnelle réelle (analyse impossible par "
                    "cette dimension dans le rapport migré)."
                ),
                "statut": "DIMENSION_MANQUANTE",
            })

    return findings


def detect_visual_count_gaps(qlik_result: Dict, pbi_result: Dict, threshold: float = 0.5) -> List[Dict]:
    """Compare le nombre de visuels par feuille Qlik / page Power BI (rapprochées
    par similarité de nom), et signale les écarts significatifs."""
    findings = []

    qlik_visuals_by_sheet: Dict[str, int] = {}
    for v in qlik_result.get("visuals", []) or []:
        sheet = v.get("sheet", "Sans nom")
        qlik_visuals_by_sheet[sheet] = qlik_visuals_by_sheet.get(sheet, 0) + 1

    pbi_visuals_by_page: Dict[str, int] = {}
    for v in pbi_result.get("visuals", []) or []:
        page = v.get("page", "Sans nom")
        pbi_visuals_by_page[page] = pbi_visuals_by_page.get(page, 0) + 1

    used_pbi_pages = set()

    for sheet_name, n_qlik in qlik_visuals_by_sheet.items():
        # Rapprochement par nom le plus proche (même logique légère que le
        # matching KPI, mais appliquée aux noms de page/feuille)
        best_page, best_score = None, 0.0
        for page_name in pbi_visuals_by_page:
            if page_name in used_pbi_pages:
                continue
            score = _similarity(_norm(sheet_name), _norm(page_name))
            if score > best_score:
                best_score, best_page = score, page_name

        if best_page is None or best_score < threshold:
            findings.append({
                "source_module": "Module A - Structural Gaps",
                "libelle": f"Page Power BI introuvable pour la feuille Qlik '{sheet_name}'",
                "detail": f"La feuille Qlik '{sheet_name}' contient {n_qlik} visuel(s), "
                          "aucune page Power BI correspondante identifiée.",
                "criticite": "MAJEUR",
                "diagnostic": "Aucune page Power BI ne porte un nom suffisamment "
                              "proche de cette feuille Qlik.",
                "recommandation": "Vérifier si cette feuille a été migrée sous un "
                                  "nom de page différent, ou si elle a été omise.",
                "statut": "PAGE_MANQUANTE",
            })
            continue

        used_pbi_pages.add(best_page)
        n_pbi = pbi_visuals_by_page[best_page]
        if n_qlik > n_pbi:
            ecart = n_qlik - n_pbi
            findings.append({
                "source_module": "Module A - Structural Gaps",
                "libelle": f"Visuels manquants sur '{sheet_name}' → '{best_page}'",
                "detail": f"Qlik : {n_qlik} visuel(s) | Power BI : {n_pbi} visuel(s) "
                          f"(écart de {ecart}).",
                "criticite": "MAJEUR" if ecart >= 2 else "MINEUR",
                "diagnostic": "Le nombre de visuels sur la page migrée est "
                              "inférieur à celui de la feuille Qlik source — au "
                              "moins un visuel n'a probablement pas été migré.",
                "recommandation": "Comparer visuellement les deux pages pour "
                                  "identifier le(s) visuel(s) manquant(s).",
                "statut": "VISUELS_MANQUANTS",
            })

    return findings


def detect_malformed_columns(pbi_result: Dict) -> List[Dict]:
    """Repère les colonnes Power BI au nom malformé (ex. deux noms de colonnes
    collés par un séparateur comme ';' ou '|') — signe fréquent d'une fusion
    Power Query ratée. Ce n'est jamais un nom de colonne normal, quel que soit
    le projet, donc pas besoin de connaître le domaine métier pour le détecter."""
    findings = []
    for c in pbi_result.get("columns", []) or []:
        name = c.get("name", "") if isinstance(c, dict) else str(c)
        table = c.get("table", "") if isinstance(c, dict) else ""
        if any(sep in name for sep in (";", "|", "\t")) and "RowNumber" not in name:
            findings.append({
                "source_module": "Module A - Structural Gaps",
                "libelle": f"Colonne au nom malformé : '{name}'",
                "detail": f"Table '{table}', colonne '{name}' — ressemble à "
                          "plusieurs noms de colonnes collés (fusion Power Query "
                          "ratée, ou colonne mal nommée à la source).",
                "criticite": "MAJEUR",
                "diagnostic": (
                    "Une colonne dont le nom contient un séparateur comme ';' "
                    "n'est jamais un nom voulu — c'est le signe qu'une étape de "
                    "transformation (fusion/pivot Power Query) n'a pas correctement "
                    "isolé les colonnes attendues. Les visuels qui devraient "
                    "utiliser cette colonne comme dimension d'affichage risquent "
                    "de ne pas fonctionner (regroupement impossible, valeur "
                    "unique agrégée au lieu d'un détail par catégorie)."
                ),
                "recommandation": (
                    "Revoir l'étape Power Query qui a produit cette colonne : "
                    "séparer correctement les champs concernés en colonnes "
                    "distinctes avant de les utiliser dans un visuel."
                ),
                "statut": "COLONNE_MALFORMEE",
            })
    return findings


def detect_structural_gaps(qlik_result: Dict, pbi_result: Dict) -> List[Dict]:
    """Point d'entrée unique : combine les trois détections ci-dessus."""
    return (
        detect_dimension_gaps(qlik_result, pbi_result)
        + detect_visual_count_gaps(qlik_result, pbi_result)
        + detect_malformed_columns(pbi_result)
    )