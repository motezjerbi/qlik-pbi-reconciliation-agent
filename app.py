import sys
import re
from pathlib import Path
import pandas as pd
import streamlit as st
import json
import datetime

sys.path.append(str(Path(__file__).resolve().parent / "src"))
from module_a.comparison import compare_exports
from module_b.taxonomy import TAXONOMY_PATTERNS
from module_b.qlik_parser import parse_qlik_script
from module_b.mapping import map_all_patterns
from module_b.mapping import map_pattern_to_dax as map_pattern_to_dax_eval
from orchestrator.merge import merge_findings
from orchestrator.prioritize import prioritize_all
from llm.client import ask_claude

st.set_page_config(
    page_title="Migration Audit — Qlik → Power BI",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS Professionnel - Style "Cabinet de Conseil"
# ============================================================

st.markdown("""
<style>
/* ===== IMPORTS POLICES ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ===== BASE ===== */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #F8F7F4;
}

/* ===== TYPOGRAPHIE ===== */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
h1 { font-size: 2.2rem !important; }
h2 { font-size: 1.6rem !important; }
h3 { font-size: 1.2rem !important; }

code, .stCode, [data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* ===== HEADER ===== */
.header-container {
    background: #FFFFFF;
    border-bottom: 3px solid #1A1F2B;
    padding: 1.2rem 2rem;
    margin: -1rem -1rem 1.5rem -1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.header-content {
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
}
.header-logo {
    width: 40px;
    height: 40px;
    background: #1A1F2B;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 0.9rem;
    letter-spacing: 0.1em;
}
.header-title h1 {
    font-size: 1.4rem !important;
    margin: 0;
    line-height: 1.2;
}
.header-title .sub {
    font-size: 0.75rem;
    font-weight: 400;
    color: #6B6F78;
    letter-spacing: 0.05em;
}
.header-meta {
    text-align: right;
    font-size: 0.75rem;
    color: #6B6F78;
    line-height: 1.6;
}
.header-meta strong { color: #1A1F2B; font-weight: 600; }
.header-meta .badge-status {
    display: inline-block;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-draft { background: #F0EDE6; color: #6B6F78; }
.badge-active { background: #E8F0E8; color: #2E7D5B; }

/* ===== CARTES ===== */
.card {
    background: #FFFFFF;
    border: 1px solid #E8E5DE;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    transition: box-shadow 0.2s ease;
}
.card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.card-header {
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B6F78;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid #F0EDE6;
    padding-bottom: 0.6rem;
}

/* ===== STATS / KPI ===== */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 0.75rem;
    margin: 1rem 0 1.5rem 0;
}
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E8E5DE;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1A1F2B;
    line-height: 1.2;
}
.kpi-label {
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B6F78;
    margin-top: 0.2rem;
}
.kpi-critical .kpi-value { color: #C0392B; }
.kpi-warning .kpi-value { color: #E67E22; }
.kpi-success .kpi-value { color: #2E7D5B; }
.kpi-neutral .kpi-value { color: #6B6F78; }

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    border-bottom: 2px solid #E8E5DE;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    color: #6B6F78;
    padding: 0.6rem 1.2rem;
    border-radius: 8px 8px 0 0;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #1A1F2B;
    background: #F5F3EE;
}
.stTabs [aria-selected="true"] {
    color: #1A1F2B !important;
    background: #FFFFFF !important;
    border-bottom: 2px solid #1A1F2B !important;
}

/* ===== BOUTONS ===== */
.stButton button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
}
.stButton button[kind="primary"] {
    background: #1A1F2B !important;
    color: #FFFFFF !important;
}
.stButton button[kind="primary"]:hover {
    background: #2E7D5B !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(46,125,91,0.25);
}
.stButton button:not([kind="primary"]) {
    background: #F0EDE6 !important;
    color: #1A1F2B !important;
}
.stButton button:not([kind="primary"]):hover {
    background: #E8E5DE !important;
}

/* ===== EXPANDERS ===== */
[data-testid="stExpander"] {
    border: 1px solid #E8E5DE !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}
[data-testid="stExpander"]:hover {
    border-color: #D0CCC2 !important;
}
[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    font-size: 0.9rem !important;
}

/* ===== METRICS ===== */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8E5DE;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B6F78 !important;
}
[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    color: #1A1F2B !important;
}

/* ===== BADGES ===== */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
.badge-critical { background: #FDE8E8; color: #C0392B; }
.badge-major { background: #FEF3E7; color: #E67E22; }
.badge-minor { background: #F0EDE6; color: #6B6F78; }
.badge-success { background: #E8F0E8; color: #2E7D5B; }
.badge-qlik { background: #E8F0E8; color: #2E7D5B; }
.badge-pbi { background: #FEF3E7; color: #D68910; }

/* ===== ALERTS ===== */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
}
[data-testid="stAlert"] .stAlert {
    border-radius: 10px !important;
}

/* ===== FOOTER ===== */
.footer {
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid #E8E5DE;
    font-size: 0.7rem;
    color: #8A8F98;
    text-align: center;
    letter-spacing: 0.03em;
}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
    .header-content { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
    .header-meta { text-align: left; width: 100%; }
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER PROFESSIONNEL
# ============================================================

today = datetime.date.today().strftime("%d %B %Y")
ref = f"QA-{datetime.date.today().strftime('%Y%m%d')}"

st.markdown(f"""
<div class="header-container">
    <div class="header-content">
        <div class="header-left">
            <div class="header-logo">QA</div>
            <div class="header-title">
                <h1>Migration Quality Audit</h1>
                <div class="sub">Qlik Sense → Power BI · Automated Reconciliation</div>
            </div>
        </div>
        <div class="header-meta">
            <div><strong>Référence</strong> {ref}</div>
            <div><strong>Date</strong> {today}</div>
            <div style="margin-top: 0.3rem;">
                <span class="badge-status badge-active">● En cours</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def load_uploaded_file(uploaded_file):
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def clean_numeric_value(val):
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
    name = Path(filename).stem.lower()
    name = re.sub(r"_(qlik|pbi)(\d*)$", "", name)
    name = re.sub(r"_(qlik|pbi)_\d+$", "", name)
    return name


def guess_key_value_columns(df: pd.DataFrame):
    numeric_cols = []
    text_cols = []
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(5)
        cleaned = sample.apply(clean_numeric_value)
        if len(sample) > 0 and cleaned.notna().sum() >= max(1, len(sample) - 1):
            numeric_cols.append(col)
        else:
            text_cols.append(col)

    if text_cols and numeric_cols:
        return text_cols[0], numeric_cols[0]
    if not text_cols and len(numeric_cols) >= 2:
        return numeric_cols[0], numeric_cols[1]
    if text_cols and len(text_cols) >= 2:
        return text_cols[0], text_cols[1]
    key_col = text_cols[0] if text_cols else (numeric_cols[0] if numeric_cols else None)
    value_col = numeric_cols[0] if numeric_cols else (df.columns[-1] if len(df.columns) else None)
    return key_col, value_col


def guess_key_column(df: pd.DataFrame):
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(5)
        cleaned = sample.apply(clean_numeric_value)
        if len(sample) > 0 and cleaned.notna().sum() < len(sample):
            return col
    return df.columns[0] if len(df.columns) else None


def get_numeric_columns(df: pd.DataFrame, exclude: str = None) -> list[str]:
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
    return re.sub(r"[\s_]+", "", name.lower())


def match_numeric_columns(qlik_cols: list[str], pbi_cols: list[str]) -> list[tuple[str, str]]:
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


def generate_executive_summary(findings: list) -> str:
    if not findings:
        return "Aucun problème détecté sur les éléments testés. La migration est conforme."

    nb_bloquant = sum(1 for f in findings if f["criticite"] == "BLOQUANT")
    nb_majeur = sum(1 for f in findings if f["criticite"] == "MAJEUR")
    nb_mineur = sum(1 for f in findings if f["criticite"] == "MINEUR")

    resume_findings = "\n".join(
        f"- [{f['criticite']}] {f['source_module']} : {f['libelle']} — {f['detail']}"
        for f in findings
    )

    prompt = f"""Tu es un consultant senior en migration Qlik Sense vers Power BI.
Rédige un résumé exécutif court (5-6 phrases maximum) pour un rapport de réconciliation post-migration,
à destination d'un consultant qui doit valider et corriger les problèmes.

Statistiques : {nb_bloquant} problème(s) bloquant(s), {nb_majeur} majeur(s), {nb_mineur} mineur(s).

Détail des findings :
{resume_findings}

Le résumé doit être factuel, professionnel, et donner une vue d'ensemble du niveau de risque de cette migration."""

    return ask_claude(prompt)


def render_badge(criticite: str) -> str:
    css_map = {
        "BLOQUANT": "badge-critical",
        "MAJEUR": "badge-major",
        "MINEUR": "badge-minor"
    }
    return f'<span class="badge {css_map.get(criticite, "badge-minor")}">{criticite}</span>'


def style_comparison_df(df: pd.DataFrame):
    def highlight_cols(col):
        if "_qlik" in col.name or "__value___qlik" in col.name:
            return ['background-color: rgba(46,125,91,0.06)'] * len(col)
        if "_pbi" in col.name or "__value___pbi" in col.name:
            return ['background-color: rgba(214,137,16,0.07)'] * len(col)
        return [''] * len(col)
    return df.style.apply(highlight_cols, axis=0)


def render_kpi_grid(stats: dict):
    items = [
        ("BLOQUANT", stats.get("bloquant", 0), "critical"),
        ("MAJEUR", stats.get("majeur", 0), "warning"),
        ("MINEUR", stats.get("mineur", 0), "neutral"),
        ("COUVERT", stats.get("couvert", 0), "success"),
    ]
    cards_html = "".join(
        f'<div class="kpi-card kpi-{type_class}"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>'
        for label, value, type_class in items
    )
    return f'<div class="kpi-grid">{cards_html}</div>'


if "all_comparisons" not in st.session_state:
    st.session_state["all_comparisons"] = {}

if "missing_pbi" not in st.session_state:
    st.session_state["missing_pbi"] = []

if "comparison_failures" not in st.session_state:
    st.session_state["comparison_failures"] = []

# ============================================================
# ONGLETS
# ============================================================

tab_a, tab_b, tab_report, tab_eval = st.tabs([
    "📊 Data Reconciliation",
    "🔍 Functional Coverage",
    "📄 Audit Report",
    "🎯 Agent Evaluation"
])

# ============================================================
# TAB A — DATA RECONCILIATION
# ============================================================

with tab_a:
    st.markdown('<div class="card"><div class="card-header">📥 Import des exports</div>', unsafe_allow_html=True)
    st.caption("Upload des fichiers Qlik et Power BI. L'agent associe automatiquement les paires par nom commun.")

    col1, col2 = st.columns(2)
    with col1:
        qlik_files = st.file_uploader(
            "Exports Qlik Sense",
            type=["csv", "xlsx"], accept_multiple_files=True, key="qlik_batch"
        )
    with col2:
        pbi_files = st.file_uploader(
            "Exports Power BI",
            type=["csv", "xlsx"], accept_multiple_files=True, key="pbi_batch"
        )

    if qlik_files and pbi_files:
        qlik_map = {extract_base_name(f.name): f for f in qlik_files}
        pbi_map = {extract_base_name(f.name): f for f in pbi_files}
        all_base_names = sorted(set(qlik_map.keys()) | set(pbi_map.keys()))

        st.markdown(f"**{len(all_base_names)} paire(s) détectée(s)**")

        if st.button("🚀 Lancer les comparaisons", type="primary"):
            st.session_state["all_comparisons"] = {}
            st.session_state["missing_pbi"] = []
            st.session_state["comparison_failures"] = []

            for base_name in all_base_names:
                qlik_f = qlik_map.get(base_name)
                pbi_f = pbi_map.get(base_name)

                with st.expander(f"📄 {base_name}", expanded=True):
                    if qlik_f is None:
                        st.warning(f"⚠️ Fichier Qlik manquant pour '{base_name}'")
                        continue
                    if pbi_f is None:
                        st.error(f"🔴 Fichier Power BI manquant pour '{base_name}'")
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
                                st.error("❌ Impossible de détecter une colonne de valeur.")
                                continue

                            qlik_prepared = pd.DataFrame({"__key__": ["Total"], "__value__": [qlik_df[value_col_qlik].iloc[0]]})
                            pbi_prepared = pd.DataFrame({"__key__": ["Total"], "__value__": [pbi_df[value_col_pbi].iloc[0]]})
                            qlik_prepared["__value__"] = auto_clean_numeric(qlik_prepared["__value__"])
                            pbi_prepared["__value__"] = auto_clean_numeric(pbi_prepared["__value__"])

                            result = compare_exports(qlik_prepared, pbi_prepared, key_cols=["__key__"], value_col="__value__")
                            st.session_state["all_comparisons"][base_name] = result
                            st.dataframe(style_comparison_df(result), use_container_width=True)

                        else:
                            key_col_qlik = guess_key_column(qlik_df)
                            key_col_pbi = guess_key_column(pbi_df)

                            qlik_numeric_cols = get_numeric_columns(qlik_df, exclude=key_col_qlik)
                            pbi_numeric_cols = get_numeric_columns(pbi_df, exclude=key_col_pbi)

                            matched_pairs = match_numeric_columns(qlik_numeric_cols, pbi_numeric_cols)

                            if not matched_pairs and len(qlik_numeric_cols) == 1 and len(pbi_numeric_cols) == 1:
                                matched_pairs = [(qlik_numeric_cols[0], pbi_numeric_cols[0])]

                            st.write(f"Clé: `{key_col_qlik}` ↔ `{key_col_pbi}`")
                            st.write(f"Mesures: {', '.join(f'{q} ↔ {p}' for q, p in matched_pairs) or 'aucune'}")

                            if not matched_pairs or key_col_qlik is None or key_col_pbi is None:
                                st.warning("⚠️ Impossible d'associer les colonnes.")
                                st.session_state["comparison_failures"].append({
                                    "visuel": base_name,
                                    "raison": f"Structure incompatible — colonnes Qlik: {list(qlik_df.columns)}, "
                                              f"colonnes Power BI: {list(pbi_df.columns)}. "
                                              f"Aucune correspondance de dimension/mesure fiable détectée automatiquement."
                                })
                                continue

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

                                st.markdown(f"**{qcol} ↔ {pcol}**")
                                st.dataframe(style_comparison_df(result), use_container_width=True)

                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
                        continue

    st.markdown('</div>', unsafe_allow_html=True)

    # Résumé des comparaisons
    if st.session_state["all_comparisons"]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{len(st.session_state['all_comparisons'])} comparaison(s) enregistrée(s)**")
        
        if st.session_state["missing_pbi"]:
            st.warning(f"🔴 Visuels sans équivalent PBI: {', '.join(st.session_state['missing_pbi'])}")

        if st.session_state["comparison_failures"]:
            st.error(f"⚠️ {len(st.session_state['comparison_failures'])} comparaison(s) échouée(s) — nécessite une vérification manuelle")
            for cf in st.session_state["comparison_failures"]:
                with st.expander(f"❌ {cf['visuel']}"):
                    st.write(cf["raison"])

        if st.button("🗑️ Effacer tout"):
            st.session_state["all_comparisons"] = {}
            st.session_state["missing_pbi"] = []
            st.session_state["comparison_failures"] = []
            st.rerun()

        for nom, result in st.session_state["all_comparisons"].items():
            ecarts = result[result["statut"] == "ECART_DETECTE"]
            icone = "🔴" if len(ecarts) > 0 else "✅"
            with st.expander(f"{icone} {nom} — {len(ecarts)} écart(s)"):
                st.dataframe(style_comparison_df(result), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TAB B — FUNCTIONAL COVERAGE
# ============================================================

with tab_b:
    st.markdown('<div class="card"><div class="card-header">🔍 Analyse fonctionnelle</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        qlik_script_file = st.file_uploader("Script Qlik (.qvs)", type=["qvs", "txt"], key="qlik_script")
    with col2:
        qlik_expr_file = st.file_uploader("Expressions visuels (.txt)", type=["txt"], key="qlik_expr")

    if qlik_script_file:
        script_content = qlik_script_file.read().decode("utf-8")
        expr_content = qlik_expr_file.read().decode("utf-8") if qlik_expr_file else ""

        combined_content = script_content + "\n\n" + expr_content

        temp_path = Path("data/samples/_temp_uploaded_script.qvs")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(combined_content, encoding="utf-8")

        patterns = parse_qlik_script(str(temp_path))

        st.markdown(f"**{len(patterns)} pattern(s) détecté(s)**")
        for p in patterns:
            st.markdown(f"- **{p['pattern']}** → `{p['expression_source']}`")

        dax_path = Path("data/samples/case_encadrante_01/powerbi/measures_dax.txt")
        if dax_path.exists():
            st.markdown("---")
            st.markdown("**Mesures DAX disponibles**")
            st.text_area("", dax_path.read_text(encoding="utf-8"), height=150)

            if st.button("🧠 Lancer le mapping sémantique", type="primary"):
                with st.spinner("Analyse en cours..."):
                    mapping_results = map_all_patterns(patterns, str(dax_path))
                st.session_state["module_b_mapping"] = mapping_results

            if "module_b_mapping" in st.session_state:
                st.markdown("---")
                st.markdown("**Résultats du mapping**")
                couleur_statut = {
                    "COUVERT": "🟢", "PARTIELLEMENT_COUVERT": "🟠",
                    "NON_COUVERT": "🔴", "ERREUR_PARSING": "⚪"
                }
                for r in st.session_state["module_b_mapping"]:
                    icone = couleur_statut.get(r["statut"], "⚪")
                    expr_display = r["expression_source"].replace("\n", " ").strip()
                    if len(expr_display) > 50:
                        expr_display = expr_display[:50] + "..."
                    with st.expander(f"{icone} [{r['statut']}] {r['pattern']}"):
                        st.write(f"**Expression:** `{r['expression_source']}`")
                        st.write(f"**Mesure DAX:** {r.get('mesure_dax_correspondante') or 'Aucune'}")
                        st.write(f"**Justification:** {r.get('justification')}")
        else:
            st.warning("Fichier measures_dax.txt introuvable.")
    else:
        st.info("Importez le script Qlik pour commencer l'analyse.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TAB C — AUDIT REPORT
# ============================================================

with tab_report:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    nb_comparisons = len(st.session_state["all_comparisons"])
    nb_missing = len(st.session_state["missing_pbi"])
    has_b = "module_b_mapping" in st.session_state

    col1, col2, col3 = st.columns(3)
    col1.metric("Comparaisons", nb_comparisons)
    col2.metric("Visuels manquants", nb_missing)
    col3.metric("Module B", "✅ Activé" if has_b else "⏳ En attente")

    if st.button("📄 Générer le rapport d'audit", type="primary",
                 disabled=(nb_comparisons == 0 and nb_missing == 0 and not has_b)):
        ecarts_a = []

        for nom, result in st.session_state["all_comparisons"].items():
            for _, row in result[result["statut"] == "ECART_DETECTE"].iterrows():
                ecarts_a.append({
                    "produit": f"{nom} — {row['__key__']}",
                    "valeur_qlik": row["__value___qlik"],
                    "valeur_pbi": row["__value___pbi"],
                    "ecart_relatif": row["ecart_relatif"] * 100,
                    "diagnostic": f"Écart sur '{nom}'"
                })

        for nom in st.session_state["missing_pbi"]:
            ecarts_a.append({
                "produit": nom,
                "valeur_qlik": "présent",
                "valeur_pbi": "absent",
                "ecart_relatif": 100.0,
                "diagnostic": f"Visuel '{nom}' absent dans PBI"
            })

        for cf in st.session_state["comparison_failures"]:
            ecarts_a.append({
                "produit": cf["visuel"],
                "valeur_qlik": "structure incompatible",
                "valeur_pbi": "structure incompatible",
                "ecart_relatif": 50.0,
                "diagnostic": f"Comparaison automatique échouée — {cf['raison']} Vérification manuelle requise."
            })

        mapping_b = st.session_state.get("module_b_mapping", [])
        findings = merge_findings(ecarts_a, mapping_b)
        prioritized = prioritize_all(findings)
        st.session_state["findings"] = prioritized

    if "findings" in st.session_state:
        prioritized = st.session_state["findings"]

        # Résumé exécutif
        if "executive_summary" not in st.session_state or st.button("🔄 Régénérer"):
            with st.spinner("Rédaction du résumé..."):
                st.session_state["executive_summary"] = generate_executive_summary(prioritized)

        st.markdown("### 📝 Résumé exécutif")
        st.info(st.session_state["executive_summary"])

        # KPI Grid
        stats = {
            "bloquant": sum(1 for f in prioritized if f["criticite"] == "BLOQUANT"),
            "majeur": sum(1 for f in prioritized if f["criticite"] == "MAJEUR"),
            "mineur": sum(1 for f in prioritized if f["criticite"] == "MINEUR"),
            "couvert": sum(1 for f in prioritized if f.get("statut") == "COUVERT")
        }
        st.markdown(render_kpi_grid(stats), unsafe_allow_html=True)

        # Findings détaillés
        if prioritized:
            st.markdown("### 🔍 Détail des findings")
            for f in prioritized:
                st.markdown(render_badge(f['criticite']) + f" **{f['libelle']}**", unsafe_allow_html=True)
                with st.expander("Voir le détail"):
                    st.write(f"**Module:** {f['source_module']}")
                    st.write(f"**Détail:** {f['detail']}")
                    st.write(f"**Diagnostic:** {f['diagnostic']}")

            # Export
            rapport_texte = "\n\n".join(
                f"## [{f['criticite']}] {f['libelle']}\n"
                f"- **Module:** {f['source_module']}\n"
                f"- **Détail:** {f['detail']}\n"
                f"- **Diagnostic:** {f['diagnostic']}"
                for f in prioritized
            )
            st.download_button(
                "⬇️ Télécharger le rapport",
                data=f"# Audit Report — Qlik → Power BI\n\n{rapport_texte}",
                file_name=f"audit_report_{datetime.date.today().isoformat()}.md",
                mime="text/markdown"
            )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TAB D — AGENT EVALUATION
# ============================================================

with tab_eval:
    st.markdown('<div class="card"><div class="card-header">🎯 Évaluation de l\'agent</div>', unsafe_allow_html=True)
    st.caption("Validation du mapping sémantique sur des cas labellisés")

    labeled_cases_path = Path("eval/labeled_cases.json")

    if not labeled_cases_path.exists():
        st.warning("Fichier eval/labeled_cases.json introuvable.")
    else:
        labeled_cases = json.loads(labeled_cases_path.read_text(encoding="utf-8"))
        st.markdown(f"**{len(labeled_cases)} cas labellisés** disponibles")

        with st.expander("👁️ Voir les cas de test"):
            for case in labeled_cases:
                st.markdown(f"**{case['pattern']}** → `{case['expression_source']}`")
                st.write(f"Vérité terrain: **{case['verite_terrain']}**")
                st.caption(case["justification_humaine"])
                st.divider()

        n_runs = st.slider("Exécutions par cas", 1, 5, 3)

        dax_path = Path("data/samples/case_encadrante_01/powerbi/measures_dax.txt")

        if not dax_path.exists():
            st.warning("Fichier measures_dax.txt introuvable.")
        elif st.button("🎯 Lancer l'évaluation", type="primary"):
            dax_text = dax_path.read_text(encoding="utf-8")

            progress = st.progress(0)
            status_text = st.empty()
            results = []

            total_calls = len(labeled_cases) * n_runs
            call_count = 0

            for case in labeled_cases:
                pattern = {"pattern": case["pattern"], "expression_source": case["expression_source"]}
                predictions = []

                for run_idx in range(n_runs):
                    status_text.text(f"Analyse: {case['pattern']} ({run_idx + 1}/{n_runs})...")
                    agent_result = map_pattern_to_dax_eval(pattern, dax_text)
                    predictions.append(agent_result["statut"])
                    call_count += 1
                    progress.progress(call_count / total_calls)

                most_common = max(set(predictions), key=predictions.count)
                is_correct = most_common == case["verite_terrain"]
                is_stable = len(set(predictions)) == 1

                results.append({
                    "pattern": case["pattern"],
                    "expression": case["expression_source"],
                    "verite_terrain": case["verite_terrain"],
                    "predictions": predictions,
                    "verdict_majoritaire": most_common,
                    "correct": is_correct,
                    "stable": is_stable
                })

            status_text.empty()
            progress.empty()

            accuracy = sum(1 for r in results if r["correct"]) / len(results)
            stability = sum(1 for r in results if r["stable"]) / len(results)

            st.session_state["eval_results"] = {"accuracy": accuracy, "stability": stability, "details": results}

        if "eval_results" in st.session_state:
            report = st.session_state["eval_results"]

            st.markdown(render_kpi_grid({
                "bloquant": int((1 - report["accuracy"]) * 100),
                "majeur": int((1 - report["stability"]) * 100),
                "mineur": 0,
                "couvert": int(report["accuracy"] * 100)
            }), unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            col1.metric("🎯 Précision", f"{report['accuracy']:.0%}")
            col2.metric("🔄 Stabilité", f"{report['stability']:.0%}")

            st.markdown("---")
            st.markdown("**Détail par cas**")

            for r in report["details"]:
                status_icon = "✅" if r["correct"] else "❌"
                stable_icon = "🟢" if r["stable"] else "🔴"
                with st.expander(f"{status_icon} {r['pattern']} — {stable_icon}"):
                    st.write(f"**Expression:** `{r['expression']}`")
                    st.write(f"**Attendu:** {r['verite_terrain']}")
                    st.write(f"**Verdict:** {r['verdict_majoritaire']}")
                    st.write(f"**Exécutions:** {r['predictions']}")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.markdown(f"""
<div class="footer">
    Migration Quality Audit · Qlik Sense → Power BI · {datetime.date.today().year}
    <br>Document confidentiel — Usage interne
</div>
""", unsafe_allow_html=True)