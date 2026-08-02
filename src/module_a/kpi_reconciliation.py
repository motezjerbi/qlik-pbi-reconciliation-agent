# src/module_a/kpi_reconciliation.py
"""Réconciliation KPIs Qlik vs Power BI — Module A."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
import pandas as pd

SEUIL_TOLERANCE = 0.01  # 1 %

# Seuil de similarité (0-1) en dessous duquel on considère qu'il n'y a pas de match.
# Qlik et PBI utilisent rarement les mêmes noms exacts (ex. "YTD" vs "Year To Date Sales") :
# ce seuil permet de les rapprocher quand même, tout en gardant une trace du niveau de confiance.
FUZZY_THRESHOLD = 0.5

# Abréviations courantes vues côté Qlik/PBI -> forme longue, pour aider le matching
# approximatif sur des noms courts (ex. "YTD" ne ressemble pas assez, en caractères,
# à "Year To Date Sales" pour passer le seuil sans cette expansion).
ALIASES = {
    "ytd": "year to date",
    "avg": "average",
    "yoy": "year over year",
    "qty": "quantity",
    "cust": "customer",
    "curr": "current",
}

# Mots qui désignent un "sélecteur temporel/statistique" précis. Deux noms qui contiennent
# CHACUN un mot de cette liste, mais des mots DIFFÉRENTS, désignent presque toujours des
# KPIs différents (ex. "Max Year Sales" vs "Latest Year Sales") même si le reste du texte
# se ressemble beaucoup lettre à lettre. On bloque ces faux positifs explicitement.
SELECTOR_WORDS = {
    "max", "min", "latest", "current", "previous", "selected",
    "average", "total", "distinct", "excluding",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _singularize(w: str) -> str:
    """Singularisation grossière : évite que 'customers' vs 'customer' soit vu comme
    deux mots différents lors du calcul de chevauchement (Jaccard).
    Exclut les mots en 'us'/'is'/'ss' (ex. 'previous', 'ss') qui ne sont pas des pluriels."""
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _tokens(s: str) -> set:
    """Mots normalisés, singularisés, avec expansion des abréviations connues (ALIASES)."""
    words = re.findall(r"[a-z0-9]+", (s or "").lower())
    out = set()
    for w in words:
        expansion = ALIASES.get(w, w)
        out.update(_singularize(x) for x in expansion.split(" "))
    return out


def _selector_conflict(tokens_a: set, tokens_b: set) -> bool:
    """True si les deux noms pointent vers des sélecteurs différents (ex. max vs latest)."""
    sel_a = tokens_a & SELECTOR_WORDS
    sel_b = tokens_b & SELECTOR_WORDS
    return bool(sel_a) and bool(sel_b) and not (sel_a & sel_b)


def _similarity(a: str, b: str) -> float:
    """Score de similarité 0-1 entre deux noms normalisés (difflib, stdlib)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _to_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(",", ".")
    s = re.sub(r"[^\d.\-eE]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _diagnose(name: str, v_qlik: Optional[float], v_pbi: Optional[float],
              expr_qlik: str, expr_pbi: str, pbi_error: str = "") -> tuple[str, str]:
    """Cause probable + correction consultant."""
    n = (name or "").lower()
    eq = expr_qlik or ""
    ep = expr_pbi or ""

    # Mesure PBI en erreur de calcul (ex. CALCULATE mal utilisé dans un filtre booléen)
    if pbi_error:
        return (
            f"La mesure Power BI est en erreur de calcul côté moteur DAX : {pbi_error}",
            "Corriger l'expression DAX de la mesure côté Power BI (revoir la logique "
            "CALCULATE/filtre) avant toute comparaison de valeur.",
        )

    if v_qlik is None and v_pbi is None:
        return (
            "Présence structurelle uniquement (pas de valeur numérique des deux côtés).",
            "Exporter les valeurs KPI depuis PBI (CSV) ou vérifier les cards dans Desktop.",
        )

    if v_qlik is not None and v_pbi is None:
        return (
            "KPI présent côté Qlik avec valeur ; valeur PBI absente de l'export/.pbix.",
            "Contrôler la card PBI et fournir un export des totaux PBI pour comparer le chiffre.",
        )

    if v_pbi is not None and v_qlik is None:
        return (
            "KPI présent côté PBI sans équivalent valorisé Qlik.",
            "Vérifier si le KPI Qlik existe sous un autre nom ou une autre feuille.",
        )

    # les deux valeurs présentes
    if abs(v_qlik) < 1e-12 and abs(v_pbi) > 1e-6:
        if any(k in n for k in ("ytd", "current", "year")):
            return (
                "Qlik = 0 alors que PBI > 0 : filtre d'année / période probablement différent "
                "(ex. année courante absente des données Qlik, ou filtre Date non aligné).",
                "Aligner le filtre temporel (Year/YTD) et le calendrier entre Qlik et le modèle PBI ; "
                "vérifier la présence de données pour l'année en cours.",
            )
        return (
            "Qlik à 0 et PBI non nul : filtre, set analysis ou périmètre de données divergent.",
            "Comparer les filtres actifs et les conditions dans l'expression Qlik vs DAX.",
        )

    if abs(v_pbi) < 1e-12 and abs(v_qlik) > 1e-6:
        return (
            "PBI = 0 alors que Qlik > 0 : mesure DAX ou filtre PBI trop restrictif.",
            "Revoir la mesure DAX, les relations du modèle et les filtres de page/rapport.",
        )

    rel = abs(v_qlik - v_pbi) / max(abs(v_qlik), abs(v_pbi), 1e-9)
    if rel <= SEUIL_TOLERANCE:
        return ("Écart dans la tolérance.", "Aucune action.")

    if "previous" in n or "y-1" in n or "yoy" in n:
        return (
            "Écart sur indicateur N-1 / évolution : période de référence ou "
            "SAMEPERIODLASTYEAR / set analysis non équivalents.",
            "Recaler la période de comparaison (année N-1) et la logique YoY des deux côtés.",
        )

    if "avg" in n or "average" in n:
        return (
            "Écart sur moyenne : dénominateur différent (clients, lignes, filtres).",
            "Vérifier AVERAGE vs SUM/COUNT et le grain (client, commande, produit).",
        )

    if "total" in n or "sales" in n:
        return (
            "Écart sur total ventes : exclusion de région/canal, devise, ou double comptage.",
            "Comparer le script de charge / la table Sales et d'éventuels filtres "
            "(ex. exclusion North Region côté PBI).",
        )

    return (
        f"Écart relatif ~{rel:.1%} entre Qlik ({v_qlik}) et PBI ({v_pbi}). "
        "Expression ou périmètre probablement non alignés.",
        "Comparer expression Qlik et DAX ; contrôler filtres, relations et grain d'agrégation.",
    )


def reconcile_kpis(
    qlik_result: Dict[str, Any],
    pbi_result: Dict[str, Any],
    pbi_values: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    pbi_values : dict optionnel {nom_normalisé ou id -> float} depuis CSV export PBI.
    Utile en repli si pbi_extractor n'a pas pu récupérer de vraie valeur (Power BI Desktop fermé).
    """
    pbi_values = pbi_values or {}

    # Index Qlik
    qlik_by_id = {}
    qlik_by_name = {}
    for k in qlik_result.get("kpis", []):
        kid = (k.get("id") or "").strip()
        name = (k.get("name") or "").strip()
        if kid:
            qlik_by_id[kid] = k
        if name:
            qlik_by_name[_norm(name)] = k

    # Index PBI (cards + kpis/mesures)
    pbi_items = list(pbi_result.get("kpis", []))
    pbi_by_id = {}
    pbi_by_name = {}
    for k in pbi_items:
        kid = (k.get("id") or k.get("name") or "").strip()
        name = (k.get("name") or "").strip()
        if kid:
            pbi_by_id[kid] = k
        if name:
            pbi_by_name[_norm(name)] = k

    rows: List[Dict] = []
    used_pbi_ids = set()

    def pbi_val_for(k: dict) -> Optional[float]:
        # 1) déjà dans l'objet (vraie valeur remontée par pbi_engine_client)
        v = _to_float(k.get("value"))
        if v is not None:
            return v
        # 2) export CSV manuel (repli)
        for key in (k.get("id"), k.get("name"), _norm(k.get("name") or "")):
            if key and key in pbi_values:
                return pbi_values[key]
            if key and _norm(str(key)) in pbi_values:
                return pbi_values[_norm(str(key))]
        return None

    def find_pbi_match(kid: str, qname: str) -> tuple[Optional[dict], str, float]:
        """
        Cherche le KPI PBI correspondant, dans l'ordre :
        1) id exact  2) nom normalisé identique  3) nom approchant (fuzzy)
        Retourne (kpi_pbi_ou_None, type_match, score).
        """
        if kid and kid in pbi_by_id:
            return pbi_by_id[kid], "EXACT_ID", 1.0

        qn = _norm(qname)
        if qn in pbi_by_name:
            return pbi_by_name[qn], "EXACT_NOM", 1.0

        # Repli : correspondance approximative, seulement parmi les KPIs PBI pas déjà pris.
        # Score = moyenne de la similarité caractère-à-caractère et du chevauchement de mots
        # (avec expansion des abréviations) ; rejeté si conflit de mot-sélecteur (max/latest/...).
        q_tok = _tokens(qname)
        best_score, best_pk = 0.0, None
        for pname_norm, cand in pbi_by_name.items():
            cand_id = (cand.get("id") or cand.get("name") or "").strip()
            if cand_id in used_pbi_ids:
                continue

            p_tok = _tokens(cand.get("name") or "")
            if _selector_conflict(q_tok, p_tok):
                continue  # ex. "Max Year Sales" vs "Latest Year Sales" -> rejeté

            char_score = _similarity(qn, pname_norm)
            union = q_tok | p_tok
            word_score = len(q_tok & p_tok) / len(union) if union else 0.0
            # Le chevauchement de mots (avec alias) est plus fiable que la similarité
            # caractère-à-caractère pour les abréviations (YTD, Avg...), d'où le poids 0.65.
            score = 0.35 * char_score + 0.65 * word_score

            if score > best_score:
                best_score, best_pk = score, cand

        if best_pk is not None and best_score >= FUZZY_THRESHOLD:
            return best_pk, "APPROX", round(best_score, 2)

        return None, "AUCUN", 0.0

    # Parcourir tous les KPIs Qlik
    for qk in qlik_result.get("kpis", []):
        kid = (qk.get("id") or "").strip()
        qname = (qk.get("name") or "").strip()

        pk, match_type, match_score = find_pbi_match(kid, qname)

        if pk:
            used_pbi_ids.add((pk.get("id") or pk.get("name") or "").strip())

        vq = _to_float(qk.get("value"))
        vp = pbi_val_for(pk) if pk else None
        if vp is None and qname:
            vp = pbi_values.get(_norm(qname)) or pbi_values.get(qname)

        pbi_error = (pk or {}).get("error") or ""

        if not pk:
            statut = "MANQUANT_PBI"
            criticite = "MAJEUR"
        elif pbi_error:
            statut = "ERREUR_PBI"
            criticite = "BLOQUANT"
        elif vq is not None and vp is not None:
            if abs(vq - vp) <= max(SEUIL_TOLERANCE * max(abs(vq), abs(vp), 1.0), 1e-6):
                statut = "MATCH_VALUE"
                criticite = "OK"
            else:
                statut = "ECART_VALEUR"
                rel = abs(vq - vp) / max(abs(vq), abs(vp), 1e-9)
                criticite = "BLOQUANT" if rel > 0.10 else ("MAJEUR" if rel > 0.05 else "MINEUR")
        else:
            statut = "MATCH_STRUCTURE"
            criticite = "MINEUR"

        cause, fix = _diagnose(
            qname,
            vq,
            vp,
            qk.get("expression") or "",
            (pk or {}).get("expression") or "",
            pbi_error,
        )

        rows.append({
            "kpi": qname or kid,
            "kpi_pbi": (pk or {}).get("name", ""),
            "id": kid,
            "sheet_qlik": qk.get("sheet", ""),
            "page_pbi": (pk or {}).get("page", ""),
            "valeur_qlik": vq,
            "valeur_pbi": vp,
            "expr_qlik": qk.get("expression", ""),
            "expr_pbi": (pk or {}).get("expression", ""),
            "statut": statut,
            "criticite": criticite,
            "match_type": match_type,
            "match_score": match_score,
            "cause_probable": cause,
            "correction": fix,
        })

    # KPIs PBI sans match Qlik
    for pk in pbi_items:
        pid = (pk.get("id") or pk.get("name") or "").strip()
        if pid in used_pbi_ids:
            continue
        pname = (pk.get("name") or pid).strip()
        if _norm(pname) in qlik_by_name or (pid in qlik_by_id):
            continue
        vp = pbi_val_for(pk)
        pbi_error = pk.get("error") or ""
        cause, fix = _diagnose(pname, None, vp, "", pk.get("expression") or "", pbi_error)
        rows.append({
            "kpi": "",
            "kpi_pbi": pname,
            "id": pid,
            "sheet_qlik": "",
            "page_pbi": pk.get("page", ""),
            "valeur_qlik": None,
            "valeur_pbi": vp,
            "expr_qlik": "",
            "expr_pbi": pk.get("expression", ""),
            "statut": "ERREUR_PBI" if pbi_error else "MANQUANT_QLIK",
            "criticite": "BLOQUANT" if pbi_error else "MINEUR",
            "match_type": "AUCUN",
            "match_score": 0.0,
            "cause_probable": cause,
            "correction": fix,
        })

    return pd.DataFrame(rows)


def load_pbi_values_csv(uploaded_file) -> Dict[str, float]:
    """CSV avec colonnes name|kpi et value|valeur (repli si extraction live indisponible)."""
    df = pd.read_csv(uploaded_file)
    cols = {c.lower().strip(): c for c in df.columns}
    name_col = cols.get("name") or cols.get("kpi") or cols.get("nom") or list(df.columns)[0]
    val_col = cols.get("value") or cols.get("valeur") or cols.get("val") or list(df.columns)[1]
    out = {}
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        val = _to_float(row[val_col])
        if name and val is not None:
            out[name] = val
            out[_norm(name)] = val
    return out