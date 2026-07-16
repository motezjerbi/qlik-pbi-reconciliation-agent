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
    s = re.sub(r"[^0-9,.\-]", "", s)  # ne garde que chiffres, virgule, point, moins
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


# ============================================================
# Onglets principaux
# ============================================================

tab_a, tab_b, tab_report = st.tabs([
    "📊 Module A — Réconciliation de données",
    "🔍 Module B — Couverture fonctionnelle",
    "📄 Rapport consolidé"
])

# ============================================================
# TAB A — Module A
# ============================================================

with tab_a:
    st.header("Import des fichiers")
    col1, col2 = st.columns(2)
    with col1:
        qlik_file = st.file_uploader("📥 Export Qlik (CSV ou XLSX)", type=["csv", "xlsx"], key="qlik_a")
    with col2:
        pbi_file = st.file_uploader("📥 Export Power BI (CSV ou XLSX)", type=["csv", "xlsx"], key="pbi_a")

    if qlik_file and pbi_file:
        qlik_df = load_uploaded_file(qlik_file)
        pbi_df = load_uploaded_file(pbi_file)

        with st.expander("👁️ Aperçu brut des données importées"):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Qlik")
                st.dataframe(qlik_df, use_container_width=True)
            with col2:
                st.subheader("Power BI")
                st.dataframe(pbi_df, use_container_width=True)

        st.header("Configuration de la comparaison")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Côté Qlik**")
            key_col_qlik = st.selectbox("Colonne clé", qlik_df.columns, key="key_qlik")
            value_col_qlik = st.selectbox("Colonne valeur", qlik_df.columns, key="val_qlik")
        with col2:
            st.markdown("**Côté Power BI**")
            key_col_pbi = st.selectbox("Colonne clé", pbi_df.columns, key="key_pbi")
            value_col_pbi = st.selectbox("Colonne valeur", pbi_df.columns, key="val_pbi")

        seuil = st.slider("Seuil de tolérance (%)", 0.1, 20.0, 1.0, 0.1)

        if st.button("🚀 Lancer la comparaison", type="primary"):
            qlik_prepared = qlik_df[[key_col_qlik, value_col_qlik]].rename(
                columns={key_col_qlik: "__key__", value_col_qlik: "__value__"})
            pbi_prepared = pbi_df[[key_col_pbi, value_col_pbi]].rename(
                columns={key_col_pbi: "__key__", value_col_pbi: "__value__"})

            with st.expander("🐛 Debug — valeurs avant nettoyage"):
                st.write("Qlik brut :", qlik_prepared["__value__"].tolist())
                st.write("Power BI brut :", pbi_prepared["__value__"].tolist())

            qlik_prepared["__value__"] = auto_clean_numeric(qlik_prepared["__value__"])
            pbi_prepared["__value__"] = auto_clean_numeric(pbi_prepared["__value__"])

            with st.expander("🐛 Debug — après nettoyage"):
                st.write("Qlik nettoyé :", qlik_prepared["__value__"].tolist())
                st.write("Power BI nettoyé :", pbi_prepared["__value__"].tolist())

            result = compare_exports(qlik_prepared, pbi_prepared, key_cols=["__key__"], value_col="__value__")
            st.session_state["module_a_result"] = result

            st.header("Résultats")
            st.dataframe(result, use_container_width=True)

            ecarts = result[result["statut"] == "ECART_DETECTE"]
            if len(ecarts) > 0:
                st.error(f"⚠️ {len(ecarts)} écart(s) détecté(s) au-delà du seuil de {seuil}%")
            else:
                st.success("✅ Aucun écart détecté au-delà du seuil.")
    else:
        st.info("Importez les deux fichiers pour continuer.")

# ============================================================
# TAB B — Module B
# ============================================================

with tab_b:
    st.header("Import du script Qlik")
    qlik_script_file = st.file_uploader("📥 Script de chargement Qlik (.qvs, .txt)", type=["qvs", "txt"], key="qlik_script")

    if qlik_script_file:
        script_content = qlik_script_file.read().decode("utf-8")

        # Sauvegarde temporaire pour réutiliser parse_qlik_script tel quel
        temp_path = Path("data/samples/_temp_uploaded_script.qvs")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(script_content, encoding="utf-8")

        patterns = parse_qlik_script(str(temp_path))

        st.header(f"Patterns détectés : {len(patterns)}")
        for p in patterns:
            st.markdown(f"- **{p['pattern']}** → `{p['expression_source']}`")

        st.header("Mesures DAX disponibles")
        dax_path = Path("data/samples/case_encadrante_01/powerbi/measures_dax.txt")
        if dax_path.exists():
            st.text_area("Mesures DAX chargées", dax_path.read_text(encoding="utf-8"), height=200)

            if st.button("🧠 Lancer le mapping sémantique (LLM local)", type="primary"):
                with st.spinner("Analyse en cours via Ollama/Mistral — peut prendre 1 à 2 minutes..."):
                    mapping_results = map_all_patterns(patterns, str(dax_path))
                st.session_state["module_b_mapping"] = mapping_results
                st.session_state["module_b_patterns"] = patterns

            if "module_b_mapping" in st.session_state:
                st.header("Résultats du mapping")
                couleur_statut = {
                    "COUVERT": "🟢",
                    "PARTIELLEMENT_COUVERT": "🟠",
                    "NON_COUVERT": "🔴",
                    "ERREUR_PARSING": "⚪"
                }
                for r in st.session_state["module_b_mapping"]:
                    icone = couleur_statut.get(r["statut"], "⚪")
                    with st.expander(f"{icone} [{r['statut']}] {r['pattern']} → {r['expression_source'][:40]}"):
                        st.write(f"**Mesure DAX correspondante :** {r.get('mesure_dax_correspondante') or 'Aucune'}")
                        st.write(f"**Justification :** {r.get('justification')}")
        else:
            st.warning("Aucun fichier measures_dax.txt trouvé. Lancez d'abord pbi_parser.py.")
    else:
        st.info("Importez un script Qlik pour lancer la détection de patterns.")

# ============================================================
# TAB RAPPORT — Fusion + priorisation
# ============================================================

with tab_report:
    st.header("Génération du rapport consolidé")

    has_a = "module_a_result" in st.session_state
    has_b = "module_b_mapping" in st.session_state

    statut_a = "✅" if has_a else "❌ (lancez une comparaison dans l'onglet Module A)"
    statut_b = "✅" if has_b else "❌ (lancez le mapping dans l'onglet Module B)"
    st.write(f"Module A prêt : {statut_a}")
    st.write(f"Module B prêt : {statut_b}")

    if st.button("📄 Générer le rapport", type="primary", disabled=not (has_a or has_b)):
        ecarts_a = []
        if has_a:
            result = st.session_state["module_a_result"]
            for _, row in result[result["statut"] == "ECART_DETECTE"].iterrows():
                ecarts_a.append({
                    "produit": row["__key__"],
                    "valeur_qlik": row["__value___qlik"],
                    "valeur_pbi": row["__value___pbi"],
                    "ecart_relatif": row["ecart_relatif"] * 100,
                    "diagnostic": "Écart détecté — diagnostic LLM à générer."
                })

        mapping_b = st.session_state.get("module_b_mapping", [])

        findings = merge_findings(ecarts_a, mapping_b)
        prioritized = prioritize_all(findings)

        nb_bloquant = sum(1 for f in prioritized if f["criticite"] == "BLOQUANT")
        nb_majeur = sum(1 for f in prioritized if f["criticite"] == "MAJEUR")
        nb_mineur = sum(1 for f in prioritized if f["criticite"] == "MINEUR")

        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 Bloquants", nb_bloquant)
        col2.metric("🟠 Majeurs", nb_majeur)
        col3.metric("🟡 Mineurs", nb_mineur)

        st.divider()

        if not prioritized:
            st.info("Aucun finding à afficher (aucun écart détecté et/ou aucune lacune non couverte).")
        else:
            couleur = {"BLOQUANT": "🔴", "MAJEUR": "🟠", "MINEUR": "🟡"}
            for f in prioritized:
                with st.expander(f"{couleur.get(f['criticite'], '⚪')} [{f['criticite']}] {f['libelle']}"):
                    st.write(f"**Module source :** {f['source_module']}")
                    st.write(f"**Détail :** {f['detail']}")
                    st.write(f"**Diagnostic :** {f['diagnostic']}")