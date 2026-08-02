# app.py
import sys
import io
import json
import datetime
import traceback
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))

# === MODULE A ===
from module_a.extractors.qlik_extractor import QlikExtractor
from module_a.extractors.pbi_extractor import PBIExtractor
from module_a.kpi_reconciliation import reconcile_kpis, SEUIL_TOLERANCE

# === MODULE B (optionnel) ===
try:
    from module_a.visual_gap_analyzer import detect_structural_gaps
except ImportError:
    detect_structural_gaps = None

try:
    from module_b.coverage_analyzer import analyze_coverage_quick, parse_dax_measures_text
except ImportError:
    analyze_coverage_quick = None
    parse_dax_measures_text = None

try:
    from module_b.mapping import map_pattern_to_dax as map_pattern_to_dax_eval, auto_evaluate_against_rules
except ImportError:
    map_pattern_to_dax_eval = None
    auto_evaluate_against_rules = None

try:
    from orchestrator.merge_advanced import merge_findings as orchestrator_merge_findings
    from orchestrator.report_generator import generate_report as orchestrator_generate_report, generate_executive_summary
except ImportError:
    orchestrator_merge_findings = None
    orchestrator_generate_report = None
    generate_executive_summary = None

st.set_page_config(
    page_title="Migration Audit — Qlik → Power BI",
    page_icon="▪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DESIGN SYSTEM / CSS
# ============================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg:            #F4F5F7;
    --surface:        #FFFFFF;
    --surface-alt:    #FAFAFB;
    --border:         #E3E5EA;
    --border-strong:  #C9CCD4;
    --text-primary:   #12141C;
    --text-secondary: #63677A;
    --text-muted:     #9498A6;
    --accent:         #1E3A8A;
    --accent-bright:  #2D4FC7;
    --accent-soft:    #EEF1FB;
    --success:        #166534;
    --success-soft:   #EAF5EC;
    --warning:        #92400E;
    --warning-soft:   #FCF3E4;
    --critical:       #991B1B;
    --critical-soft:  #FBEAEA;
    --neutral-soft:   #F0F1F4;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --shadow-sm: 0 1px 2px rgba(16,18,26,0.04);
    --shadow-md: 0 2px 10px rgba(16,18,26,0.06);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text-primary);
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    color: var(--text-primary);
}
code, .stCode, [data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    background: var(--neutral-soft) !important;
    color: var(--text-primary) !important;
}
[data-testid="stAppViewContainer"] { background: var(--bg); }
[data-testid="stHeader"] { background: transparent; }

/* ---------- Top bar ---------- */
.topbar {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1.1rem 2rem;
    margin: -1rem -1rem 1.75rem -1rem;
}
.topbar-inner {
    max-width: 1300px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.topbar-left { display: flex; align-items: center; gap: 0.9rem; }
.topbar-mark {
    width: 38px; height: 38px; background: var(--accent); border-radius: var(--radius-sm);
    display: flex; align-items: center; justify-content: center;
    color: #FFFFFF; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.06em;
}
.topbar-title h1 { font-size: 1.25rem !important; margin: 0; line-height: 1.25; }
.topbar-title .sub {
    font-size: 0.74rem; font-weight: 400; color: var(--text-secondary); letter-spacing: 0.02em;
    margin-top: 0.1rem;
}
.topbar-meta { text-align: right; font-size: 0.74rem; color: var(--text-secondary); line-height: 1.55; }
.topbar-meta strong { color: var(--text-primary); font-weight: 600; }
.status-pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.22rem 0.7rem; border-radius: 20px;
    font-weight: 600; font-size: 0.68rem; letter-spacing: 0.03em; text-transform: uppercase;
    background: var(--accent-soft); color: var(--accent);
}
.status-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-bright); }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
.side-brand { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; color: var(--text-muted);
    text-transform: uppercase; margin-bottom: 1rem; padding: 0 0.2rem;}
.side-progress {
    border-top: 1px solid var(--border); margin-top: 1.2rem; padding-top: 1rem;
}
.side-progress-title {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; color: var(--text-muted);
    text-transform: uppercase; margin-bottom: 0.65rem;
}
.side-progress-row {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 0.78rem; color: var(--text-secondary); padding: 0.28rem 0;
}
.side-progress-row .label { display: flex; align-items: center; gap: 0.5rem; }
.chip { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase;
    padding: 0.12rem 0.5rem; border-radius: 20px; }
.chip-done { background: var(--success-soft); color: var(--success); }
.chip-pending { background: var(--neutral-soft); color: var(--text-muted); }

section[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 0.55rem 0.7rem; border-radius: var(--radius-sm); margin-bottom: 0.15rem;
    transition: background 0.12s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: var(--neutral-soft); }

/* ---------- Cards & sections ---------- */
.section-heading {
    display: flex; align-items: baseline; justify-content: space-between;
    margin-bottom: 0.3rem;
}
.section-heading h2 { font-size: 1.35rem !important; margin: 0; }
.section-tag {
    font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--accent);
}
.section-lead {
    font-size: 0.88rem; color: var(--text-secondary); margin: 0.25rem 0 1.5rem 0;
    max-width: 760px; line-height: 1.55;
}
.card {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
    padding: 1.5rem 1.6rem; margin-bottom: 1.25rem; box-shadow: var(--shadow-sm);
}
.card-header {
    font-weight: 600; font-size: 0.76rem; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--text-secondary); margin-bottom: 0.9rem;
    border-bottom: 1px solid var(--border); padding-bottom: 0.65rem;
}
hr.divider { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }

/* ---------- KPI grid ---------- */
.kpi-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem; margin: 0.5rem 0 1.5rem 0;
}
.kpi-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md);
    padding: 1rem 1.2rem;
}
.kpi-value { font-size: 1.55rem; font-weight: 700; color: var(--text-primary); line-height: 1.2; }
.kpi-label {
    font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--text-muted); margin-top: 0.25rem;
}
.kpi-critical .kpi-value { color: var(--critical); }
.kpi-warning .kpi-value { color: var(--warning); }
.kpi-success .kpi-value { color: var(--success); }
.kpi-neutral .kpi-value { color: var(--text-secondary); }

/* ---------- Badges ---------- */
.match-badge {
    display: inline-block; padding: 0.12rem 0.55rem; border-radius: 20px;
    font-size: 0.66rem; font-weight: 600; letter-spacing: 0.02em;
}
.match-exact  { background: var(--success-soft); color: var(--success); }
.match-approx { background: var(--warning-soft); color: var(--warning); }
.match-none   { background: var(--critical-soft); color: var(--critical); }

.crit-badge {
    display: inline-block; padding: 0.14rem 0.6rem; border-radius: 20px;
    font-size: 0.66rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
}
.crit-BLOQUANT { background: var(--critical-soft); color: var(--critical); }
.crit-MAJEUR   { background: var(--warning-soft); color: var(--warning); }
.crit-MINEUR   { background: var(--neutral-soft); color: var(--text-secondary); }
.crit-OK       { background: var(--success-soft); color: var(--success); }

/* ---------- Callout ---------- */
.callout {
    background: var(--surface-alt); border: 1px solid var(--border); border-left: 3px solid var(--accent);
    border-radius: var(--radius-md); padding: 0.85rem 1.1rem; margin-bottom: 1.5rem;
    font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;
}

/* ---------- Buttons ---------- */
.stButton button[kind="primary"] {
    background: var(--accent) !important; color: #FFFFFF !important; border: none !important;
    border-radius: var(--radius-sm) !important; font-weight: 600 !important; letter-spacing: 0.01em;
}
.stButton button[kind="primary"]:hover { background: var(--accent-bright) !important; }
.stDownloadButton button {
    border-radius: var(--radius-sm) !important; font-weight: 500 !important;
    border-color: var(--border-strong) !important;
}

/* ---------- Misc ---------- */
[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.7rem; letter-spacing: 0.03em; text-transform: uppercase; color: var(--text-secondary); }
.streamlit-expanderHeader { font-size: 0.86rem !important; font-weight: 500 !important; }

.footer {
    margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border);
    font-size: 0.7rem; color: var(--text-muted); text-align: center;
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# TOP BAR
# ============================================================

today = datetime.date.today().strftime("%d %B %Y")
ref = f"QA-{datetime.date.today().strftime('%Y%m%d')}"

st.markdown(
    f"""
<div class="topbar">
  <div class="topbar-inner">
    <div class="topbar-left">
      <div class="topbar-mark">QA</div>
      <div class="topbar-title">
        <h1>Migration Quality Audit</h1>
        <div class="sub">Qlik Sense → Power BI · Réconciliation automatisée</div>
      </div>
    </div>
    <div class="topbar-meta">
      <div><strong>Référence</strong> {ref}</div>
      <div><strong>Date</strong> {today}</div>
      <div style="margin-top:0.35rem;">
        <span class="status-pill"><span class="dot"></span>En cours</span>
      </div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================


def render_kpi_grid(stats: dict) -> str:
    items = [
        ("BLOQUANT", stats.get("bloquant", 0), "critical"),
        ("MAJEUR", stats.get("majeur", 0), "warning"),
        ("MINEUR", stats.get("mineur", 0), "neutral"),
        ("OK / MATCH", stats.get("ok", 0), "success"),
    ]
    cards = "".join(
        f'<div class="kpi-card kpi-{t}"><div class="kpi-value">{v}</div>'
        f'<div class="kpi-label">{lab}</div></div>'
        for lab, v, t in items
    )
    return f'<div class="kpi-grid">{cards}</div>'


def match_badge(match_type: str) -> str:
    cls = {
        "EXACT_ID": "match-exact",
        "EXACT_NOM": "match-exact",
        "APPROX": "match-approx",
        "AUCUN": "match-none",
    }.get(match_type, "match-none")
    return f'<span class="match-badge {cls}">{match_type}</span>'


def crit_badge(criticite: str) -> str:
    c = criticite if criticite in ("BLOQUANT", "MAJEUR", "MINEUR", "OK") else "MINEUR"
    return f'<span class="crit-badge crit-{c}">{c}</span>'


def findings_from_reconciliation(rec_df: pd.DataFrame) -> list:
    findings = []
    if rec_df is None or rec_df.empty:
        return findings
    for _, row in rec_df.iterrows():
        statut = row.get("statut", "")
        criticite = row.get("criticite", "MINEUR")
        if statut == "MATCH_VALUE" or criticite == "OK":
            continue
        findings.append(
            {
                "source_module": "Module A - Data Reconciliation",
                "libelle": f"{row.get('kpi') or row.get('kpi_pbi', '')} [{statut}]",
                "detail": (
                    f"Qlik={row.get('valeur_qlik')} | PBI={row.get('valeur_pbi')} | "
                    f"feuille Qlik={row.get('sheet_qlik')} | page PBI={row.get('page_pbi')} | "
                    f"correspondance={row.get('match_type')} (score {row.get('match_score')})"
                ),
                "criticite": criticite if criticite != "OK" else "MINEUR",
                "diagnostic": row.get("cause_probable", ""),
                "recommandation": row.get("correction", ""),
                "statut": statut,
            }
        )
    return findings


def show_ecarts_expanders(rec_df: pd.DataFrame) -> None:
    action = rec_df[
        rec_df["statut"].isin(
            ["ECART_VALEUR", "MANQUANT_PBI", "MANQUANT_QLIK", "ERREUR_PBI"]
        )
    ]
    if action.empty:
        st.success("Aucun écart numérique hors tolérance à traiter.")
        return
    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
    action = action.assign(_ordre=action["criticite"].map(ordre).fillna(3))
    action = action.sort_values("_ordre")

    for _, row in action.iterrows():
        with st.expander(
            f"{row.get('criticite')} — {row.get('kpi') or row.get('kpi_pbi')} — {row.get('statut')}"
        ):
            st.markdown(
                f"**Rapprochement :** {match_badge(row.get('match_type', 'AUCUN'))} "
                f"(score {row.get('match_score', 0):.2f})",
                unsafe_allow_html=True,
            )
            st.write(
                f"**Localisation Qlik :** feuille=`{row.get('sheet_qlik', '')}` | "
                f"id=`{row.get('id', '')}`"
            )
            st.write(f"**Localisation PBI :** page=`{row.get('page_pbi', '')}`")
            st.write(
                f"**KPI Qlik :** `{row.get('kpi') or '—'}` · "
                f"**KPI PBI :** `{row.get('kpi_pbi') or '—'}`"
            )
            st.write(
                f"**Valeur Qlik :** `{row.get('valeur_qlik')}` · "
                f"**Valeur PBI :** `{row.get('valeur_pbi')}`"
            )
            if row.get("expr_qlik"):
                st.write(f"**Expr. Qlik :** `{row.get('expr_qlik')}`")
            if row.get("expr_pbi"):
                st.write(f"**Expr. PBI :** `{row.get('expr_pbi')}`")
            st.write(f"**Cause probable :** {row.get('cause_probable')}")
            st.write(f"**Correction suggérée :** {row.get('correction')}")


def build_qlik_expressions_text(qlik_result: dict) -> str:
    """Rassemble toutes les expressions Qlik déjà extraites (mesures master,
    KPIs, visuels) en un seul texte, pour la détection de patterns du Module B —
    évite d'avoir à uploader un fichier d'expressions séparé."""
    lines = []
    for m in qlik_result.get("measures", []) or []:
        if m.get("expression"):
            lines.append(str(m["expression"]))
    for k in qlik_result.get("kpis", []) or []:
        if k.get("expression"):
            lines.append(str(k["expression"]))
    for v in qlik_result.get("visuals", []) or []:
        if v.get("expression"):
            lines.append(str(v["expression"]))
    return "\n".join(lines)


def export_module_a_excel(
    rec_df: pd.DataFrame, qlik_result: dict, pbi_result: dict
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if rec_df is not None and not rec_df.empty:
            rec_df.to_excel(writer, sheet_name="Reconciliation_KPIs", index=False)
        pd.DataFrame(qlik_result.get("kpis", [])).to_excel(
            writer, sheet_name="Qlik_KPIs", index=False
        )
        pd.DataFrame(pbi_result.get("kpis", [])).to_excel(
            writer, sheet_name="PBI_KPIs", index=False
        )
    return buf.getvalue()


def section_heading(tag: str, title: str, lead: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <h2>{title}</h2>
            <span class="section-tag">{tag}</span>
        </div>
        {f'<div class="section-lead">{lead}</div>' if lead else ''}
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================

for key, default in [
    ("all_comparisons", {}),
    ("findings", []),
    ("module_b_coverage", None),
    ("qlik_extraction", None),
    ("pbi_extraction", None),
    ("module_a_reconciliation", None),
    ("active_section", "Réconciliation de données"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

sections = [
    "Réconciliation de données",
    "Couverture fonctionnelle",
    "Rapport d'audit",
    "Évaluation de l'agent",
]

with st.sidebar:
    st.markdown('<div class="side-brand">Navigation</div>', unsafe_allow_html=True)
    active_section = st.radio(
        "Navigation",
        sections,
        index=sections.index(st.session_state["active_section"]),
        label_visibility="collapsed",
    )
    st.session_state["active_section"] = active_section

    rec_df_side = st.session_state.get("module_a_reconciliation")
    has_a_side = isinstance(rec_df_side, pd.DataFrame) and not rec_df_side.empty
    has_b_side = bool(st.session_state.get("module_b_coverage"))
    findings_side = st.session_state.get("findings") or []

    st.markdown(
        f"""
        <div class="side-progress">
            <div class="side-progress-title">État de l'audit</div>
            <div class="side-progress-row">
                <span class="label">Réconciliation</span>
                <span class="chip {'chip-done' if has_a_side else 'chip-pending'}">
                    {'Fait' if has_a_side else 'En attente'}
                </span>
            </div>
            <div class="side-progress-row">
                <span class="label">Couverture</span>
                <span class="chip {'chip-done' if has_b_side else 'chip-pending'}">
                    {'Fait' if has_b_side else 'En attente'}
                </span>
            </div>
            <div class="side-progress-row">
                <span class="label">Findings</span>
                <span class="chip {'chip-done' if findings_side else 'chip-pending'}">
                    {len(findings_side)}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION — RÉCONCILIATION DE DONNÉES (MODULE A)
# ============================================================

def render_module_a() -> None:
    section_heading(
        "Module A",
        "Réconciliation de données",
        "À partir des exports du rapport Qlik et de son équivalent Power BI, détecte les écarts "
        "numériques (totaux, KPIs, dimensions), les localise, et suggère une cause probable et "
        "une correction au consultant.",
    )

    st.markdown(
        '<div class="card"><div class="card-header">Import des fichiers</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        qlik_file = st.file_uploader(
            "Rapport Qlik (.qvf)",
            type=["qvf"],
            key="qlik_main",
            help="Qlik Sense Desktop doit être ouvert avec ce fichier chargé (Engine API).",
        )
    with col2:
        pbi_file = st.file_uploader(
            "Rapport Power BI (.pbix)",
            type=["pbix", "pbit"],
            key="pbi_main",
            help="Power BI Desktop doit être ouvert avec ce fichier chargé (extraction live ADOMD.NET).",
        )

    st.caption(
        f"Tolérance relative : {SEUIL_TOLERANCE:.0%}. Matching automatique par id, nom exact, "
        "puis nom approchant (score affiché). Les valeurs sont lues directement dans les "
        "moteurs Qlik / Power BI — aucune saisie manuelle requise."
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if qlik_file and pbi_file:
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        if st.button("Extraire et réconcilier", type="primary"):
            with st.spinner("Extraction Qlik + Power BI en cours..."):
                try:
                    # ----- QLIK -----
                    st.markdown('<div class="card"><div class="card-header">Qlik Sense</div>', unsafe_allow_html=True)
                    qlik_path = temp_dir / qlik_file.name
                    qlik_path.write_bytes(qlik_file.getvalue())

                    qlik_extractor = QlikExtractor()
                    qlik_result = qlik_extractor.extract_from_file(str(qlik_path.resolve()))
                    st.session_state["qlik_extraction"] = qlik_result

                    q1, q2, q3, q4, q5 = st.columns(5)
                    q1.metric("Sheets", len(qlik_result.get("sheets", [])))
                    q2.metric("KPIs", len(qlik_result.get("kpis", [])))
                    q3.metric("Visuels", len(qlik_result.get("visuals", [])))
                    q4.metric("Mesures", len(qlik_result.get("measures", [])))
                    q5.metric("Dimensions", len(qlik_result.get("dimensions", [])))

                    with st.expander("Détail KPIs Qlik"):
                        for k in qlik_result.get("kpis", []):
                            st.write(
                                f"- **[{k.get('sheet', '')}] {k.get('name', '')}** "
                                f"= `{k.get('value')}` · id=`{k.get('id', '')}`"
                            )
                    st.markdown("</div>", unsafe_allow_html=True)

                    # ----- PBI -----
                    st.markdown('<div class="card"><div class="card-header">Power BI</div>', unsafe_allow_html=True)
                    pbi_path = temp_dir / pbi_file.name
                    pbi_path.write_bytes(pbi_file.getvalue())

                    pbi_extractor = PBIExtractor()
                    pbi_result = pbi_extractor.extract_from_file(str(pbi_path.resolve()))
                    st.session_state["pbi_extraction"] = pbi_result

                    live = (pbi_result.get("metadata", {}) or {}).get("source", "")
                    if "live" in live:
                        st.success("Extraction live réussie (valeurs réelles des mesures DAX).")
                    else:
                        st.warning(
                            "Power BI Desktop n'a pas pu être atteint — structure extraite du "
                            "fichier, sans valeurs réelles. Ouvrez le .pbix dans Power BI Desktop "
                            "et relancez pour des valeurs exactes."
                        )

                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Pages", len(pbi_result.get("pages", [])))
                    p2.metric("Visuels", len(pbi_result.get("visuals", [])))
                    p3.metric("KPIs / Mesures", len(pbi_result.get("kpis", [])))
                    p4.metric("Mesures DAX", len(pbi_result.get("dax_measures", [])))

                    with st.expander("Détail structure PBI"):
                        if pbi_result.get("pages"):
                            st.write(
                                "**Pages :** "
                                + ", ".join(str(p.get("name", "")) for p in pbi_result["pages"])
                            )
                        for k in pbi_result.get("kpis") or []:
                            err = k.get("error")
                            tag = " — ERREUR DAX" if err else ""
                            st.markdown(f"- **{k.get('name')}** = `{k.get('value')}`{tag}")
                            if err:
                                st.caption(err)
                    st.markdown("</div>", unsafe_allow_html=True)

                    # ----- RÉCONCILIATION -----
                    st.markdown('<div class="card"><div class="card-header">Réconciliation</div>', unsafe_allow_html=True)
                    rec_df = reconcile_kpis(qlik_result, pbi_result)
                    st.session_state["module_a_reconciliation"] = rec_df
                    st.session_state["all_comparisons"]["kpis"] = rec_df
                    st.session_state["findings"] = findings_from_reconciliation(rec_df)

                    if rec_df is not None and not rec_df.empty:
                        n_match = int((rec_df["statut"] == "MATCH_VALUE").sum())
                        n_ecart = int((rec_df["statut"] == "ECART_VALEUR").sum())
                        n_err = int((rec_df["statut"] == "ERREUR_PBI").sum())
                        n_miss_p = int((rec_df["statut"] == "MANQUANT_PBI").sum())
                        n_miss_q = int((rec_df["statut"] == "MANQUANT_QLIK").sum())
                    else:
                        n_match = n_ecart = n_err = n_miss_p = n_miss_q = 0

                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Match valeur", n_match)
                    m2.metric("Écarts valeur", n_ecart)
                    m3.metric("Mesures en erreur", n_err)
                    m4.metric("Manquants PBI", n_miss_p)
                    m5.metric("Manquants Qlik", n_miss_q)

                    cols_show = [
                        c
                        for c in [
                            "kpi", "kpi_pbi", "valeur_qlik", "valeur_pbi",
                            "statut", "criticite", "match_type", "match_score",
                        ]
                        if rec_df is not None and c in rec_df.columns
                    ]
                    if rec_df is not None:
                        st.dataframe(rec_df[cols_show], width="stretch")
                    st.markdown("</div>", unsafe_allow_html=True)

                    # ----- ÉCARTS STRUCTURELS -----
                    if detect_structural_gaps is not None:
                        structural_findings = detect_structural_gaps(qlik_result, pbi_result)
                        st.session_state["structural_findings"] = structural_findings
                        st.session_state["findings"] = st.session_state["findings"] + structural_findings
                        if structural_findings:
                            st.markdown(
                                '<div class="card"><div class="card-header">Écarts structurels — visuels & dimensions</div>',
                                unsafe_allow_html=True,
                            )
                            st.caption(
                                "Détection complémentaire : dimensions Qlik sans colonne Power BI "
                                "correspondante, pages avec moins de visuels que leur feuille Qlik source."
                            )
                            for f in structural_findings:
                                with st.expander(f"{f['criticite']} — {f['libelle']}"):
                                    st.write(f"**Détail :** {f['detail']}")
                                    st.write(f"**Diagnostic :** {f['diagnostic']}")
                                    st.write(f"**Recommandation :** {f['recommandation']}")
                            st.markdown("</div>", unsafe_allow_html=True)

                    # ----- ÉCARTS DÉTAILLÉS -----
                    st.markdown(
                        '<div class="card"><div class="card-header">Écarts, causes probables & corrections</div>',
                        unsafe_allow_html=True,
                    )
                    show_ecarts_expanders(rec_df)
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.download_button(
                        "Télécharger le rapport Excel — Module A",
                        data=export_module_a_excel(rec_df, qlik_result, pbi_result),
                        file_name=f"module_a_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_module_a",
                    )
                    st.success("Réconciliation Module A terminée.")

                except Exception as e:
                    st.error(f"Erreur d'extraction : {e}")
                    st.code(traceback.format_exc())
    else:
        st.markdown(
            '<div class="callout">Uploadez un fichier <strong>.qvf</strong> et un fichier '
            '<strong>.pbix</strong> pour lancer la réconciliation.</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# SECTION — COUVERTURE FONCTIONNELLE (MODULE B)
# ============================================================

def render_module_b() -> None:
    section_heading(
        "Module B",
        "Couverture fonctionnelle",
        "Script et expressions Qlik comparés aux mesures DAX pour repérer les fonctionnalités "
        "source sans équivalent migré.",
    )

    st.markdown(
        '<div class="card"><div class="card-header">Analyse fonctionnelle</div>',
        unsafe_allow_html=True,
    )

    qlik_live = st.session_state.get("qlik_extraction")
    pbi_live = st.session_state.get("pbi_extraction")
    has_live = bool(qlik_live) and bool(pbi_live)

    source = st.radio(
        "Source des données",
        ["Extraction du Module A (recommandé)", "Uploader des fichiers manuellement"],
        index=0 if has_live else 1,
        horizontal=True,
    )

    qlik_content = expr_content = dax_content = None
    dax_measures_struct = None

    if source.startswith("Extraction"):
        if not has_live:
            st.warning(
                "Aucune extraction Module A en mémoire. Lancez d'abord la section "
                "**Réconciliation de données** (avec Qlik Sense Desktop et Power BI Desktop "
                "ouverts), ou basculez sur l'upload manuel ci-dessus."
            )
        else:
            qlik_content = qlik_live.get("script", "") or ""
            expr_content = build_qlik_expressions_text(qlik_live)
            dax_measures_struct = pbi_live.get("dax_measures", []) or []
            n_script_lines = len(qlik_content.splitlines())
            st.caption(
                f"Script Qlik : {n_script_lines} ligne(s) · "
                f"Expressions Qlik : {expr_content.count(chr(10)) + (1 if expr_content else 0)} · "
                f"Mesures DAX (PBI) : {len(dax_measures_struct)}"
            )
            if not qlik_content.strip():
                st.info(
                    "Le script Qlik récupéré est vide — vérifiez que l'app Qlik contient bien "
                    "un script de chargement, ou uploadez-le manuellement."
                )
    else:
        b1, b2 = st.columns(2)
        with b1:
            qlik_script_file = st.file_uploader("Script Qlik (.qvs)", type=["qvs", "txt"], key="qlik_script")
        with b2:
            qlik_expr_file = st.file_uploader("Expressions visuels (.txt)", type=["txt"], key="qlik_expr")
        dax_measures_file = st.file_uploader(
            "Mesures DAX (.txt / .dax, format '# Mesure : Nom')", type=["txt", "dax"], key="dax_measures"
        )
        if qlik_script_file:
            qlik_content = qlik_script_file.read().decode("utf-8")
        if qlik_expr_file:
            expr_content = qlik_expr_file.read().decode("utf-8")
        if dax_measures_file:
            dax_content = dax_measures_file.read().decode("utf-8")

    if st.button("Lancer l'analyse de couverture", type="primary"):
        if analyze_coverage_quick is None:
            st.error("Module B (coverage_analyzer) non disponible.")
        elif not qlik_content:
            st.warning("Aucun script Qlik disponible (extraction live vide ou fichier non uploadé).")
        elif dax_measures_struct is None and not dax_content:
            st.warning("Aucune mesure DAX disponible (extraction live absente ou fichier non uploadé).")
        else:
            with st.spinner("Analyse de couverture en cours..."):
                try:
                    measures_for_analysis = (
                        dax_measures_struct
                        if dax_measures_struct is not None
                        else parse_dax_measures_text(dax_content)
                    )
                    results = analyze_coverage_quick(qlik_content, expr_content or "", measures_for_analysis)
                    if results.get("error"):
                        st.error(results["error"])
                    else:
                        st.session_state["module_b_coverage"] = results
                        k1, k2, k3, k4, k5 = st.columns(5)
                        k1.metric("Patterns", results.get("total_patterns", 0))
                        k2.metric("Couverts", results.get("covered", 0))
                        k3.metric("Partiels", results.get("partially_covered", 0))
                        k4.metric("Non couverts", results.get("not_covered", 0))
                        k5.metric("Taux", f"{results.get('coverage_rate', 0):.1f}%")
                        if results.get("details"):
                            st.dataframe(pd.DataFrame(results["details"]), width="stretch")
                        if results.get("findings"):
                            existing = st.session_state.get("findings") or []
                            st.session_state["findings"] = existing + results["findings"]
                        if results.get("recommandations"):
                            with st.expander("Recommandations"):
                                for rec in results["recommandations"]:
                                    st.markdown(f"- {rec}")
                        st.success("Analyse Module B terminée.")
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# SECTION — RAPPORT D'AUDIT
# ============================================================

def render_report() -> None:
    section_heading(
        "Synthèse",
        "Rapport d'audit",
        "Fusionne les findings des modules A et B, les trie par criticité, et génère les "
        "exports destinés au consultant et au client.",
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)

    rec_df = st.session_state.get("module_a_reconciliation")
    has_a = isinstance(rec_df, pd.DataFrame) and not rec_df.empty
    has_b = bool(st.session_state.get("module_b_coverage"))
    findings = st.session_state.get("findings") or []

    c1, c2, c3 = st.columns(3)
    c1.metric("Module A", "Fait" if has_a else "En attente")
    c2.metric("Module B", "Fait" if has_b else "En attente")
    c3.metric("Findings", len(findings))

    if st.button(
        "Générer / rafraîchir le rapport",
        type="primary",
        disabled=not (has_a or has_b),
    ):
        findings_a = findings_from_reconciliation(rec_df) if has_a else []
        findings_a = findings_a + (st.session_state.get("structural_findings") or [])
        findings_b = st.session_state["module_b_coverage"].get("findings") or [] if has_b else []
        if orchestrator_merge_findings is not None:
            merged_typed = orchestrator_merge_findings(findings_a, findings_b)
            merged = [
                {
                    "source_module": f.source_module,
                    "libelle": f.libelle,
                    "detail": f.detail,
                    "criticite": f.criticite,
                    "diagnostic": f.diagnostic,
                    "recommandation": f.recommandation,
                    "statut": f.statut,
                }
                for f in merged_typed
            ]
        else:
            merged = findings_a + findings_b
        st.session_state["findings"] = merged
        findings = merged
        st.success(f"Rapport généré : {len(findings)} finding(s).")

    st.markdown("</div>", unsafe_allow_html=True)

    if findings:
        if generate_executive_summary is not None:
            from orchestrator.merge_advanced import Finding as _FindingSummary
            findings_typed_summary = [
                _FindingSummary(
                    source_module=f.get("source_module", ""),
                    libelle=f.get("libelle", ""),
                    detail=f.get("detail", ""),
                    criticite=f.get("criticite", "MINEUR"),
                    diagnostic=f.get("diagnostic", ""),
                    recommandation=f.get("recommandation", ""),
                    statut=f.get("statut", ""),
                )
                for f in findings
            ]
            st.markdown('<div class="card"><div class="card-header">Résumé exécutif</div>', unsafe_allow_html=True)
            st.markdown(generate_executive_summary(findings_typed_summary))
            st.markdown("</div>", unsafe_allow_html=True)

        bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
        majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
        mineur = sum(1 for f in findings if f.get("criticite") == "MINEUR")
        st.markdown(
            render_kpi_grid({"bloquant": bloquant, "majeur": majeur, "mineur": mineur, "ok": 0}),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="card"><div class="card-header">Détail des findings</div>', unsafe_allow_html=True)
        for f in findings:
            with st.expander(f"{f.get('criticite', 'MINEUR')} — {f.get('libelle', '')}"):
                st.write(f"**Module :** {f.get('source_module', '')}")
                st.write(f"**Détail :** {f.get('detail', '')}")
                st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")
                if f.get("recommandation"):
                    st.write(f"**Recommandation :** {f.get('recommandation')}")
        st.markdown("</div>", unsafe_allow_html=True)

        report_data = {
            "date": datetime.datetime.now().isoformat(),
            "reference": ref,
            "total_findings": len(findings),
            "bloquant": bloquant,
            "majeur": majeur,
            "mineur": mineur,
            "findings": findings,
        }

        st.markdown('<div class="card"><div class="card-header">Exports</div>', unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button(
                "Export JSON",
                data=json.dumps(report_data, indent=2, ensure_ascii=False),
                file_name=f"audit_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                key="dl_audit_json",
                width="stretch",
            )

        if orchestrator_generate_report is not None:
            from orchestrator.merge_advanced import Finding as _Finding
            findings_typed = [
                _Finding(
                    source_module=f.get("source_module", ""),
                    libelle=f.get("libelle", ""),
                    detail=f.get("detail", ""),
                    criticite=f.get("criticite", "MINEUR"),
                    diagnostic=f.get("diagnostic", ""),
                    recommandation=f.get("recommandation", ""),
                    statut=f.get("statut", ""),
                )
                for f in findings
            ]
            markdown_report = orchestrator_generate_report(findings_typed)
            with e2:
                st.download_button(
                    "Export Markdown",
                    data=markdown_report,
                    file_name=f"audit_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md",
                    mime="text/markdown",
                    key="dl_audit_md",
                    width="stretch",
                )

        if has_a:
            qlik_result = st.session_state.get("qlik_extraction") or {}
            pbi_result = st.session_state.get("pbi_extraction") or {}
            with e3:
                st.download_button(
                    "Export Excel",
                    data=export_module_a_excel(rec_df, qlik_result, pbi_result),
                    file_name=f"audit_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_audit_xlsx",
                    width="stretch",
                )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="callout">Lancez le Module A et/ou le Module B pour alimenter le rapport.</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# SECTION — ÉVALUATION DE L'AGENT
# ============================================================

def render_eval() -> None:
    section_heading(
        "Qualité",
        "Évaluation de l'agent",
        "Mesure la fiabilité du LLM : accord avec un moteur de règles déterministe, ou "
        "comparaison à une vérité terrain labellisée.",
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)

    eval_mode = st.radio(
        "Mode d'évaluation",
        [
            "Automatique — accord LLM vs moteur par règles (sans fichier)",
            "Manuel — comparaison à une vérité terrain labellisée",
        ],
        index=0,
        horizontal=False,
    )

    if eval_mode.startswith("Automatique"):
        st.caption(
            "Compare les verdicts du LLM à ceux du moteur par règles déterministe "
            "(coverage_analyzer.py) sur les mêmes patterns, plus la stabilité du LLM sur "
            "plusieurs exécutions. Aucun fichier requis — utilise l'extraction déjà faite "
            "dans la section Réconciliation de données."
        )
        qlik_live = st.session_state.get("qlik_extraction")
        pbi_live = st.session_state.get("pbi_extraction")
        if not (qlik_live and pbi_live):
            st.warning(
                "Aucune extraction en mémoire. Lancez d'abord la section Réconciliation de "
                "données (Qlik Sense Desktop + Power BI Desktop ouverts)."
            )
        elif auto_evaluate_against_rules is None:
            st.error("Fonction d'auto-évaluation indisponible (import échoué).")
        else:
            n_runs_auto = st.slider("Exécutions par pattern", 1, 5, 3, key="n_runs_auto")
            if st.button("Lancer l'auto-évaluation", type="primary"):
                with st.spinner("Auto-évaluation en cours (peut prendre plusieurs minutes)..."):
                    script_txt = qlik_live.get("script", "") or ""
                    expr_txt = build_qlik_expressions_text(qlik_live)
                    dax_measures_live = pbi_live.get("dax_measures", []) or []
                    result = auto_evaluate_against_rules(
                        script_txt, expr_txt, dax_measures_live, n_runs=n_runs_auto
                    )
                    if result.get("error"):
                        st.error(result["error"])
                    else:
                        st.session_state["auto_eval_results"] = result

            if "auto_eval_results" in st.session_state:
                r = st.session_state["auto_eval_results"]
                e1, e2, e3 = st.columns(3)
                e1.metric("Taux d'accord (vs règles)", f"{r['taux_accord']:.1f}%")
                e2.metric("Stabilité LLM", f"{r['taux_stabilite']:.1f}%")
                e3.metric("Patterns testés", r["total_patterns"])
                for d in r["details"]:
                    tag = "Accord" if d["accord"] else "Désaccord"
                    stab_tag = "Stable" if d["stable"] else "Instable"
                    with st.expander(f"{tag} · {stab_tag} — {d['pattern']}"):
                        st.write(f"**Expression :** `{d['expression']}`")
                        st.write(f"**Référence (règles) :** {d['reference_regles']}")
                        st.write(f"**Verdict LLM (majoritaire) :** {d['verdict_llm_majoritaire']}")
                        st.write(f"**Prédictions LLM ({r['n_runs']} runs) :** {d['predictions_llm']}")
    else:
        st.caption("Validation du mapping sémantique sur des cas labellisés.")
        st.caption(
            "Ce banc de test compare les réponses du LLM à une vérité terrain déjà validée à "
            "la main. Pour évaluer un autre projet, uploadez son propre fichier de cas "
            "labellisés (même format que eval/labeled_cases.json) — il n'existe pas de vérité "
            "terrain automatique."
        )
        labeled_cases_upload = st.file_uploader(
            "Cas labellisés (.json) — optionnel, sinon eval/labeled_cases.json est utilisé",
            type=["json"], key="labeled_cases_upload",
        )

        labeled_cases_path = Path("eval/labeled_cases.json")
        if labeled_cases_upload is not None:
            labeled_cases = json.loads(labeled_cases_upload.read().decode("utf-8"))
        elif not labeled_cases_path.exists():
            labeled_cases = None
            st.warning("Fichier eval/labeled_cases.json introuvable — uploadez un fichier de cas labellisés.")
        else:
            labeled_cases = json.loads(labeled_cases_path.read_text(encoding="utf-8"))

        if labeled_cases is None:
            pass
        elif map_pattern_to_dax_eval is None:
            st.warning("Fonction map_pattern_to_dax indisponible.")
        else:
            st.markdown(f"**{len(labeled_cases)} cas labellisés**")

            with st.expander("Voir les cas de test"):
                for case in labeled_cases:
                    st.markdown(f"**{case.get('pattern')}** → `{case.get('expression_source')}`")
                    st.write(f"Vérité terrain : **{case.get('verite_terrain')}**")
                    st.caption(case.get("justification_humaine", ""))
                    st.divider()

            n_runs = st.slider("Exécutions par cas", 1, 5, 3)
            dax_path = st.text_input(
                "Chemin fichier mesures DAX",
                value="data/samples/case_encadrante_01/powerbi/measures_dax.txt",
            )

            if st.button("Lancer l'évaluation", type="primary"):
                dax_file = Path(dax_path)
                if not dax_file.exists():
                    st.error(f"Fichier introuvable : {dax_path}")
                else:
                    dax_text = dax_file.read_text(encoding="utf-8")
                    progress = st.progress(0)
                    status = st.empty()
                    results = []
                    total = max(len(labeled_cases) * n_runs, 1)
                    count = 0
                    for case in labeled_cases:
                        pattern = {
                            "pattern": case["pattern"],
                            "expression_source": case["expression_source"],
                        }
                        preds = []
                        for run_idx in range(n_runs):
                            status.text(f"{case['pattern']} ({run_idx + 1}/{n_runs})...")
                            agent_result = map_pattern_to_dax_eval(pattern, dax_text)
                            preds.append(agent_result.get("statut"))
                            count += 1
                            progress.progress(count / total)
                        most = max(set(preds), key=preds.count)
                        results.append(
                            {
                                "pattern": case["pattern"],
                                "expression": case["expression_source"],
                                "verite_terrain": case["verite_terrain"],
                                "predictions": preds,
                                "verdict_majoritaire": most,
                                "correct": most == case["verite_terrain"],
                                "stable": len(set(preds)) == 1,
                            }
                        )
                    status.empty()
                    progress.empty()
                    acc = sum(1 for r in results if r["correct"]) / len(results)
                    stab = sum(1 for r in results if r["stable"]) / len(results)
                    st.session_state["eval_results"] = {
                        "accuracy": acc,
                        "stability": stab,
                        "details": results,
                    }

            if "eval_results" in st.session_state:
                report = st.session_state["eval_results"]
                e1, e2 = st.columns(2)
                e1.metric("Précision", f"{report['accuracy']:.0%}")
                e2.metric("Stabilité", f"{report['stability']:.0%}")
                for r in report["details"]:
                    tag = "Correct" if r["correct"] else "Incorrect"
                    with st.expander(f"{tag} — {r['pattern']}"):
                        st.write(f"**Attendu :** {r['verite_terrain']}")
                        st.write(f"**Verdict :** {r['verdict_majoritaire']}")
                        st.write(f"**Prédictions :** {r['predictions']}")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ROUTAGE — UNE SEULE SECTION AFFICHÉE À LA FOIS
# ============================================================

router = {
    "Réconciliation de données": render_module_a,
    "Couverture fonctionnelle": render_module_b,
    "Rapport d'audit": render_report,
    "Évaluation de l'agent": render_eval,
}
router[st.session_state["active_section"]]()

# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
<div class="footer">
  Migration Quality Audit · Qlik Sense → Power BI · {datetime.date.today().year}
  <br>Document confidentiel — Usage interne
</div>
""",
    unsafe_allow_html=True,
)