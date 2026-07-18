import sys
import re
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))
from module_a.comparison import compare_exports
from module_b.taxonomy import TAXONOMY_PATTERNS
from module_b.qlik_parser import parse_qlik_script
from module_b.mapping import map_all_patterns
from orchestrator.merge import merge_findings
from orchestrator.prioritize import prioritize_all

st.set_page_config(page_title="Agent de réconciliation Qlik → Power BI", layout="wide")
st.title("🔍 Agent de réconciliation Qlik Sense → Power BI")
st.markdown("*Détection automatique des écarts de données et des lacunes fonctionnelles post-migration*")

# ============================================================
# Fonctions utilitaires
# ============================================================

def load_uploaded_file(uploaded_file):
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def clean_numeric_value(val):
    """Nettoie une valeur individuelle ($ , % , virgule décimale) -> float ou None."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    has_pct = "%" in s
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        num = float(s)
    except ValueError:
        return None
    return num / 100 if has_pct else num


def auto_clean_numeric(series: pd.Series) -> pd.Series:
    return series.apply(clean_numeric_value)


def extract_base_name(filename: str) -> str:
    """Extrait le nom de base en retirant l'extension et les suffixes _qlik/_pbi/_1/_2."""
    name = Path(filename).stem.lower()
    name = re.sub(r"_(qlik|pbi)(\d*)$", "", name)
    name = re.sub(r"_(qlik|pbi)_\d+$", "", name)
    return name


def guess_key_value_columns(df: pd.DataFrame):
    """Devine la colonne clé (dimension) et la colonne valeur (mesure numérique) d'un DataFrame."""
    numeric_cols = []
    text_cols = []
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(5)
        cleaned = sample.apply(clean_numeric_value)
        if len(sample) > 0 and cleaned.notna().sum() >= max(1, len(sample) - 1):
            numeric_cols.append(col)
        else:
            text_cols.append(col)

    # Cas normal : une colonne texte (dimension) + une colonne numérique (valeur)
    if text_cols and numeric_cols:
        return text_cols[0], numeric_cols[0]

    # Cas où TOUTES les colonnes sont détectées comme numériques
    # (ex: "Month" = 1,2,4 est numérique mais joue le rôle de dimension)
    if not text_cols and len(numeric_cols) >= 2:
        return numeric_cols[0], numeric_cols[1]

    # Cas où tout est texte
    if text_cols and len(text_cols) >= 2:
        return text_cols[0], text_cols[1]

    key_col = text_cols[0] if text_cols else (numeric_cols[0] if numeric_cols else None)
    value_col = numeric_cols[0] if numeric_cols else (df.columns[-1] if len(df.columns) else None)
    return key_col, value_col


# ============================================================
# Nouvelles fonctions pour la comparaison multi-colonnes
# ============================================================

def guess_key_column(df: pd.DataFrame):
    """Identifie la colonne clé (dimension, non-numérique) la plus probable."""
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(5)
        cleaned = sample.apply(clean_numeric_value)
        if len(sample) > 0 and cleaned.notna().sum() < len(sample):
            return col
    return df.columns[0] if len(df.columns) else None


def get_numeric_columns(df: pd.DataFrame, exclude: str = None) -> list[str]:
    """Retourne toutes les colonnes numériques d'un DataFrame, hors la colonne clé."""
    numeric_cols = []

    for col in df.columns:
        if col == exclude:
            continue

        sample = df[col].dropna().astype(str).head(5)
        cleaned = sample.apply(clean_numeric_value)

        if len(sample) > 0 and cleaned.notna().sum() >= max(1, len(sample) - 1):
            numeric_cols.append(col)

    return numeric_cols


def normalize_col_name(name: str) -> str:
    """Normalise un nom de colonne pour le rapprochement."""
    return re.sub(r"[\s_]+", "", name.lower())


def match_numeric_columns(qlik_cols: list[str], pbi_cols: list[str]) -> list[tuple[str, str]]:
    """
    Associe automatiquement les colonnes numériques Qlik et Power BI.
    Exemple :
        Margin -> AverageMargin
        Sales -> TotalSales
    """
    pairs = []
    used_pbi = set()

    for qcol in qlik_cols:
        qnorm = normalize_col_name(qcol)
        best_match = None

        for pcol in pbi_cols:
            if pcol in used_pbi:
                continue

            pnorm = normalize_col_name(pcol)

            if qnorm == pnorm or qnorm in pnorm or pnorm in qnorm:
                best_match = pcol
                break

        if best_match:
            pairs.append((qcol, best_match))
            used_pbi.add(best_match)

    return pairs


if "all_comparisons" not in st.session_state:
    st.session_state["all_comparisons"] = {}

if "missing_pbi" not in st.session_state:
    st.session_state["missing_pbi"] = []
# ============================================================
# Onglets principaux
# ============================================================

tab_a, tab_b, tab_report = st.tabs([
    "📊 Module A — Réconciliation de données",
    "🔍 Module B — Couverture fonctionnelle",
    "📄 Rapport consolidé"
])

# ============================================================
# TAB A — Module A (upload multi-fichiers, association automatique)
# ============================================================

with tab_a:
    st.header("Import en masse des exports Qlik et Power BI")
    st.caption("Uploadez tous les fichiers d'un coup. L'agent associe automatiquement chaque paire "
               "en se basant sur un nom commun (ex: total_sales_qlik.xlsx ↔ total_sales_pbi.csv).")

    col1, col2 = st.columns(2)
    with col1:
        qlik_files = st.file_uploader(
            "📥 Tous les exports Qlik (sélection multiple)",
            type=["csv", "xlsx"], accept_multiple_files=True, key="qlik_batch"
        )
    with col2:
        pbi_files = st.file_uploader(
            "📥 Tous les exports Power BI (sélection multiple)",
            type=["csv", "xlsx"], accept_multiple_files=True, key="pbi_batch"
        )

    if qlik_files and pbi_files:
        qlik_map = {extract_base_name(f.name): f for f in qlik_files}
        pbi_map = {extract_base_name(f.name): f for f in pbi_files}

        all_base_names = sorted(set(qlik_map.keys()) | set(pbi_map.keys()))

        st.subheader(f"🔗 {len(all_base_names)} groupe(s) détecté(s)")

        if st.button("🚀 Lancer toutes les comparaisons automatiquement", type="primary"):
            st.session_state["all_comparisons"] = {}
            st.session_state["missing_pbi"] = []

            for base_name in all_base_names:
                qlik_f = qlik_map.get(base_name)
                pbi_f = pbi_map.get(base_name)

                with st.expander(f"📄 {base_name}", expanded=True):
                    if qlik_f is None:
                        st.warning(f"⚠️ Fichier Qlik manquant pour '{base_name}' → visuel absent côté Qlik.")
                        continue
                    if pbi_f is None:
                        st.error(f"🔴 Fichier Power BI manquant pour '{base_name}' → visuel non affiché côté Power BI (LACUNE).")
                        st.session_state["missing_pbi"].append(base_name)
                        continue

                    try:
                        qlik_df = load_uploaded_file(qlik_f)
                        pbi_df = load_uploaded_file(pbi_f)

                        is_single_value = len(qlik_df) == 1 and len(pbi_df) == 1

                        if is_single_value:
                            _, value_col_qlik = guess_key_value_columns(qlik_df)
                            _, value_col_pbi = guess_key_value_columns(pbi_df)
                            if value_col_qlik is None or value_col_pbi is None:
                                st.error("❌ Impossible de détecter une colonne de valeur exploitable.")
                                continue

                            qlik_prepared = pd.DataFrame({"__key__": ["Total"], "__value__": [qlik_df[value_col_qlik].iloc[0]]})
                            pbi_prepared = pd.DataFrame({"__key__": ["Total"], "__value__": [pbi_df[value_col_pbi].iloc[0]]})
                            qlik_prepared["__value__"] = auto_clean_numeric(qlik_prepared["__value__"])
                            pbi_prepared["__value__"] = auto_clean_numeric(pbi_prepared["__value__"])

                            result = compare_exports(qlik_prepared, pbi_prepared, key_cols=["__key__"], value_col="__value__")
                            st.session_state["all_comparisons"][base_name] = result
                            st.dataframe(result, use_container_width=True)

                        else:
                            # --- Mode intelligent multi-colonnes ---
                            key_col_qlik = guess_key_column(qlik_df)
                            key_col_pbi = guess_key_column(pbi_df)

                            qlik_numeric_cols = get_numeric_columns(qlik_df, exclude=key_col_qlik)
                            pbi_numeric_cols = get_numeric_columns(pbi_df, exclude=key_col_pbi)

                            matched_pairs = match_numeric_columns(qlik_numeric_cols, pbi_numeric_cols)

                            # Filet de sécurité : si une seule colonne numérique de chaque côté
                            # (mais noms trop différents pour être rapprochés automatiquement),
                            # on les associe quand même par position.
                            if not matched_pairs and len(qlik_numeric_cols) == 1 and len(pbi_numeric_cols) == 1:
                                matched_pairs = [(qlik_numeric_cols[0], pbi_numeric_cols[0])]

                            st.write(f"Colonne clé — Qlik: `{key_col_qlik}` | Power BI: `{key_col_pbi}`")
                            st.write(f"Colonnes de valeur associées automatiquement : "
                                     f"{', '.join(f'{q} ↔ {p}' for q, p in matched_pairs) or 'aucune'}")

                            if not matched_pairs or key_col_qlik is None or key_col_pbi is None:
                                st.warning(f"⚠️ Impossible d'associer des colonnes de valeur pour '{base_name}'. Comparaison ignorée.")
                                continue

                            any_ecart = False
                            for qcol, pcol in matched_pairs:
                                qlik_prepared = qlik_df[[key_col_qlik, qcol]].rename(
                                    columns={key_col_qlik: "__key__", qcol: "__value__"})
                                pbi_prepared = pbi_df[[key_col_pbi, pcol]].rename(
                                    columns={key_col_pbi: "__key__", pcol: "__value__"})

                                qlik_prepared["__value__"] = auto_clean_numeric(qlik_prepared["__value__"])
                                pbi_prepared["__value__"] = auto_clean_numeric(pbi_prepared["__value__"])
                                qlik_prepared["__key__"] = qlik_prepared["__key__"].astype(str).str.strip()
                                pbi_prepared["__key__"] = pbi_prepared["__key__"].astype(str).str.strip()

                                result = compare_exports(qlik_prepared, pbi_prepared, key_cols=["__key__"], value_col="__value__")

                                comparison_name = f"{base_name} [{qcol}]"
                                st.session_state["all_comparisons"][comparison_name] = result

                                st.markdown(f"**Colonne : {qcol} ↔ {pcol}**")
                                st.dataframe(result, use_container_width=True)

                                if len(result[result["statut"] == "ECART_DETECTE"]) > 0:
                                    any_ecart = True

                        ecarts_found = any(
                            len(r[r["statut"] == "ECART_DETECTE"]) > 0
                            for k, r in st.session_state["all_comparisons"].items() if k.startswith(base_name)
                        )
                        if ecarts_found:
                            st.error(f"⚠️ Écart(s) détecté(s) pour '{base_name}'")
                        else:
                            st.success(f"✅ OK pour '{base_name}'")

                    except Exception as e:
                        st.error(f"❌ Erreur lors du traitement de '{base_name}' : {e}")
                        continue

    st.divider()
    st.header(f"Comparaisons enregistrées : {len(st.session_state['all_comparisons'])}")

    if st.session_state["missing_pbi"]:
        st.warning(f"🔴 Visuels sans équivalent Power BI : {', '.join(st.session_state['missing_pbi'])}")

    if st.session_state["all_comparisons"]:
        if st.button("🗑️ Tout effacer"):
            st.session_state["all_comparisons"] = {}
            st.session_state["missing_pbi"] = []
            st.rerun()

        for nom, result in st.session_state["all_comparisons"].items():
            ecarts = result[result["statut"] == "ECART_DETECTE"]
            icone = "🔴" if len(ecarts) > 0 else "🟢"
            with st.expander(f"{icone} {nom} — {len(ecarts)} écart(s)"):
                st.dataframe(result, use_container_width=True)

# ============================================================
# TAB B — Module B (script + expressions fusionnés)
# ============================================================

with tab_b:
    st.header("Import des sources Qlik (script + expressions des visuels)")

    col1, col2 = st.columns(2)
    with col1:
        qlik_script_file = st.file_uploader("📥 Script de chargement (.qvs)", type=["qvs", "txt"], key="qlik_script")
    with col2:
        qlik_expr_file = st.file_uploader("📥 Expressions des visuels (optionnel, .txt)", type=["txt"], key="qlik_expr")

    if qlik_script_file:
        script_content = qlik_script_file.read().decode("utf-8")
        expr_content = qlik_expr_file.read().decode("utf-8") if qlik_expr_file else ""

        combined_content = script_content + "\n\n" + expr_content

        temp_path = Path("data/samples/_temp_uploaded_script.qvs")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(combined_content, encoding="utf-8")

        patterns = parse_qlik_script(str(temp_path))

        st.header(f"Patterns détectés : {len(patterns)}")
        for p in patterns:
            st.markdown(f"- **{p['pattern']}** → `{p['expression_source']}`")

        st.header("Mesures DAX disponibles")
        dax_path = Path("data/samples/case_encadrante_01/powerbi/measures_dax.txt")
        if dax_path.exists():
            st.text_area("Mesures DAX chargées", dax_path.read_text(encoding="utf-8"), height=200)

            if st.button("🧠 Lancer le mapping sémantique (LLM local)", type="primary"):
                with st.spinner("Analyse en cours via Ollama/Mistral — peut prendre plusieurs minutes..."):
                    mapping_results = map_all_patterns(patterns, str(dax_path))
                st.session_state["module_b_mapping"] = mapping_results

            if "module_b_mapping" in st.session_state:
                st.header("Résultats du mapping")
                couleur_statut = {
                    "COUVERT": "🟢", "PARTIELLEMENT_COUVERT": "🟠",
                    "NON_COUVERT": "🔴", "ERREUR_PARSING": "⚪"
                }
                for r in st.session_state["module_b_mapping"]:
                    icone = couleur_statut.get(r["statut"], "⚪")
                    with st.expander(f"{icone} [{r['statut']}] {r['pattern']} → {r['expression_source'][:40]}"):
                        st.write(f"**Mesure DAX correspondante :** {r.get('mesure_dax_correspondante') or 'Aucune'}")
                        st.write(f"**Justification :** {r.get('justification')}")
        else:
            st.warning("Aucun fichier measures_dax.txt trouvé. Lancez d'abord pbi_parser.py.")
    else:
        st.info("Importez au moins le script de chargement pour lancer la détection.")

# ============================================================
# TAB RAPPORT — Fusion de TOUTES les comparaisons + mapping
# ============================================================

with tab_report:
    st.header("Génération du rapport consolidé")

    nb_comparisons = len(st.session_state["all_comparisons"])
    nb_missing = len(st.session_state["missing_pbi"])
    has_b = "module_b_mapping" in st.session_state

    st.write(f"Module A : {nb_comparisons} comparaison(s) + {nb_missing} visuel(s) manquant(s) côté PBI")
    st.write(f"Module B : {'✅ mapping effectué' if has_b else '❌ pas encore lancé'}")

    if st.button("📄 Générer le rapport complet", type="primary",
                 disabled=(nb_comparisons == 0 and nb_missing == 0 and not has_b)):
        ecarts_a = []

        for nom, result in st.session_state["all_comparisons"].items():
            for _, row in result[result["statut"] == "ECART_DETECTE"].iterrows():
                ecarts_a.append({
                    "produit": f"{nom} — {row['__key__']}",
                    "valeur_qlik": row["__value___qlik"],
                    "valeur_pbi": row["__value___pbi"],
                    "ecart_relatif": row["ecart_relatif"] * 100,
                    "diagnostic": f"Écart détecté sur le visuel '{nom}'."
                })

        for nom in st.session_state["missing_pbi"]:
            ecarts_a.append({
                "produit": nom,
                "valeur_qlik": "présent",
                "valeur_pbi": "absent",
                "ecart_relatif": 100.0,
                "diagnostic": f"Le visuel '{nom}' existe côté Qlik mais n'a aucun équivalent exporté/affiché côté Power BI."
            })

        mapping_b = st.session_state.get("module_b_mapping", [])

        findings = merge_findings(ecarts_a, mapping_b)
        prioritized = prioritize_all(findings)
        st.session_state["findings"] = prioritized

    if "findings" in st.session_state:
        prioritized = st.session_state["findings"]

        nb_bloquant = sum(1 for f in prioritized if f["criticite"] == "BLOQUANT")
        nb_majeur = sum(1 for f in prioritized if f["criticite"] == "MAJEUR")
        nb_mineur = sum(1 for f in prioritized if f["criticite"] == "MINEUR")

        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 Bloquants", nb_bloquant)
        col2.metric("🟠 Majeurs", nb_majeur)
        col3.metric("🟡 Mineurs", nb_mineur)

        st.divider()

        if not prioritized:
            st.info("Aucun finding à afficher.")
        else:
            couleur = {"BLOQUANT": "🔴", "MAJEUR": "🟠", "MINEUR": "🟡"}
            for f in prioritized:
                with st.expander(f"{couleur.get(f['criticite'], '⚪')} [{f['criticite']}] {f['libelle']}"):
                    st.write(f"**Module source :** {f['source_module']}")
                    st.write(f"**Détail :** {f['detail']}")
                    st.write(f"**Diagnostic :** {f['diagnostic']}")

            st.divider()
            rapport_texte = "\n\n".join(
                f"## [{f['criticite']}] {f['libelle']}\n"
                f"- **Module :** {f['source_module']}\n"
                f"- **Détail :** {f['detail']}\n"
                f"- **Diagnostic :** {f['diagnostic']}"
                for f in prioritized
            )
            st.download_button(
                "⬇️ Télécharger le rapport complet (Markdown)",
                data=f"# Rapport de réconciliation — sales_demo\n\n{rapport_texte}",
                file_name="rapport_reconciliation_complet.md",
                mime="text/markdown"
            )