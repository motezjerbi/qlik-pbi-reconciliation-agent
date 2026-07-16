import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))
from module_a.comparison import compare_exports

st.set_page_config(page_title="Agent de réconciliation Qlik → Power BI", layout="wide")

st.title("🔍 Agent de réconciliation Qlik Sense → Power BI")
st.caption("Détection d'écarts de données post-migration")

st.header("1. Import des fichiers")

col1, col2 = st.columns(2)
with col1:
    qlik_file = st.file_uploader("📥 Export Qlik (CSV ou XLSX)", type=["csv", "xlsx"])
with col2:
    pbi_file = st.file_uploader("📥 Export Power BI (CSV ou XLSX)", type=["csv", "xlsx"])


def load_uploaded_file(uploaded_file):
    """Charge un fichier uploadé (CSV ou Excel) dans un DataFrame."""
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def auto_clean_numeric(series: pd.Series) -> pd.Series:
    """Nettoie automatiquement les formats numériques courants ($, %, virgule décimale)."""
    if series.dtype == object:
        series_str = series.astype(str)
        has_percent = series_str.str.contains("%", regex=False)

        cleaned = (
            series_str
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")

        # Si la valeur d'origine contenait un %, on divise par 100
        # pour ramener à la même échelle que côté Qlik (qui n'est pas en %)
        numeric = numeric.where(~has_percent, numeric / 100)

        return numeric
    return pd.to_numeric(series, errors="coerce")


if qlik_file and pbi_file:
    qlik_df = load_uploaded_file(qlik_file)
    pbi_df = load_uploaded_file(pbi_file)

    st.header("2. Aperçu des données importées")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Qlik")
        st.dataframe(qlik_df, use_container_width=True)
    with col2:
        st.subheader("Power BI")
        st.dataframe(pbi_df, use_container_width=True)

    st.header("3. Configuration de la comparaison")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Côté Qlik**")
        key_col_qlik = st.selectbox("Colonne clé (dimension)", qlik_df.columns, key="key_qlik")
        value_col_qlik = st.selectbox("Colonne valeur à comparer", qlik_df.columns, key="val_qlik")
    with col2:
        st.markdown("**Côté Power BI**")
        key_col_pbi = st.selectbox("Colonne clé (dimension)", pbi_df.columns, key="key_pbi")
        value_col_pbi = st.selectbox("Colonne valeur à comparer", pbi_df.columns, key="val_pbi")

    seuil = st.slider("Seuil de tolérance (%)", 0.1, 20.0, 1.0, 0.1)

    if st.button("🚀 Lancer la comparaison", type="primary"):
        qlik_prepared = qlik_df.rename(columns={key_col_qlik: "__key__", value_col_qlik: "__value__"})
        pbi_prepared = pbi_df.rename(columns={key_col_pbi: "__key__", value_col_pbi: "__value__"})

        qlik_prepared["__value__"] = auto_clean_numeric(qlik_prepared["__value__"])
        pbi_prepared["__value__"] = auto_clean_numeric(pbi_prepared["__value__"])

        result = compare_exports(
            qlik_prepared[["__key__", "__value__"]],
            pbi_prepared[["__key__", "__value__"]],
            key_cols=["__key__"],
            value_col="__value__"
        )

        st.header("4. Résultats")
        st.dataframe(result, use_container_width=True)

        ecarts = result[result["statut"] == "ECART_DETECTE"]
        if len(ecarts) > 0:
            st.error(f"⚠️ {len(ecarts)} écart(s) détecté(s) au-delà du seuil de {seuil}%")
        else:
            st.success("✅ Aucun écart détecté au-delà du seuil.")

else:
    st.info("Importez les deux fichiers pour continuer.")