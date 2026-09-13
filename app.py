# app.py
import sys
import io
import json
import time
import datetime
import traceback
import base64
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.append(str(Path(__file__).resolve().parent / "src"))

# === MODULE A ===
from module_a.extractors.qlik_extractor import QlikExtractor
from module_a.extractors.pbi_extractor import PBIExtractor
from module_a.kpi_reconciliation import reconcile_kpis, SEUIL_TOLERANCE

try:
    from module_a.visual_gap_analyzer import detect_structural_gaps
except ImportError:
    detect_structural_gaps = None

# === MODULE B ===
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

# === ORCHESTRATOR ===
try:
    from orchestrator.merge_advanced import merge_findings as orchestrator_merge_findings, Finding
    from orchestrator.report_generator import (
        generate_report as orchestrator_generate_report,
        generate_executive_summary,
        compute_health_score,
    )
except ImportError:
    orchestrator_merge_findings = None
    orchestrator_generate_report = None
    generate_executive_summary = None
    compute_health_score = None
    Finding = None

# === HISTORIQUE (suivi multi-runs) ===
try:
    from orchestrator.history_tracker import (
        save_run as history_save_run,
        load_history_df as history_load_df,
        load_run_findings as history_load_run_findings,
        clear_history as history_clear_all,
        diff_runs as history_diff_runs,
        detect_stalled_findings as history_detect_stalled,
    )
except ImportError:
    history_save_run = None
    history_load_df = None
    history_load_run_findings = None
    history_clear_all = None
    history_diff_runs = None
    history_detect_stalled = None

# === RAPPORT WORD (livrable client) ===
try:
    from orchestrator.word_report_generator import generate_word_report
except ImportError:
    generate_word_report = None

# === GÉNÉRATION DE CORRECTIFS DAX (IA) ===
try:
    from module_b.dax_fix_generator import generate_dax_fix, generate_dax_fix_with_confidence
except ImportError:
    generate_dax_fix = None
    generate_dax_fix_with_confidence = None

# === ASSISTANT Q&A (chat sur les constats) ===
try:
    from orchestrator.qa_assistant import answer_question
except ImportError:
    answer_question = None

# === NOTIFICATIONS EMAIL (compte SMTP dédié) ===
try:
    from orchestrator.notifier import (
        send_email_via_smtp,
        email_new_bloquant,
        email_report_generated,
        email_dette_migration,
    )
except ImportError:
    send_email_via_smtp = None
    email_new_bloquant = None
    email_report_generated = None
    email_dette_migration = None

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="Audit Migration Qlik → Power BI | Talan",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo_talan.png"
LOGO_GOOGLE_PATH = Path(__file__).resolve().parent / "assets" / "logo_google.jpg"

# ============================================================
# DESIGN SYSTEM + ANIMATIONS
# ============================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --ink: #0B1220;
    --ink-soft: #64748B;
    --surface: rgba(255,255,255,0.78);
    --line: rgba(226,232,240,0.85);
    --accent: #1E3A5F;
    --accent-2: #2563EB;
    --brass: #B45309;
    --danger: #DC2626;
    --danger-soft: #FEE2E2;
    --warn: #D97706;
    --warn-soft: #FEF3C7;
    --ok: #059669;
    --ok-soft: #D1FAE5;
    --neutral: #64748B;
    --neutral-soft: #F1F5F9;
}

.stApp {
    background:
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(99,102,241,0.12) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(16,185,129,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(245,158,11,0.06) 0%, transparent 55%),
        linear-gradient(160deg, #F8FAFC 0%, #EEF2FF 40%, #F0FDF4 100%);
    background-attachment: fixed;
    background-size: 140% 140%, 130% 130%, 110% 110%, 100% 100%;
    animation: softDrift 28s ease-in-out infinite;
}
@keyframes softDrift {
    0%, 100% { background-position: 0% 0%, 100% 100%, 50% 50%, 0% 0%; }
    50%      { background-position: 5% 10%, 95% 90%, 45% 55%, 0% 0%; }
}

.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        radial-gradient(1.5px 1.5px at 20% 30%, rgba(37,99,235,0.22), transparent),
        radial-gradient(1.5px 1.5px at 70% 60%, rgba(16,185,129,0.18), transparent),
        radial-gradient(1px 1px at 40% 80%, rgba(245,158,11,0.15), transparent),
        radial-gradient(1.5px 1.5px at 85% 20%, rgba(37,99,235,0.12), transparent);
    animation: floatParticles 40s linear infinite;
    opacity: 0.55;
    z-index: 0;
}
@keyframes floatParticles {
    0%   { transform: translateY(0); }
    100% { transform: translateY(-28px); }
}

[data-testid="stAppViewContainer"] > .main {
    animation: fadeInUp 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--ink);
}
h1, h2, h3 {
    font-family: 'Source Serif 4', Georgia, serif !important;
    font-weight: 600 !important;
    color: var(--ink) !important;
    letter-spacing: -0.025em !important;
}
code, .stCode, [data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #0B1220 0%, #111827 55%, #1E293B 100%) !important;
    border-right: 1px solid rgba(51,65,85,0.6);
    box-shadow: 8px 0 32px rgba(0,0,0,0.18);
}
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #94A3B8 !important; }
[data-testid="stSidebar"] hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, #334155, transparent) !important;
    margin: 1rem 0 !important;
}
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    border-radius: 10px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    color: #CBD5E1 !important;
    font-weight: 500 !important;
    font-size: 0.86rem !important;
    text-align: left !important;
    padding: 0.62rem 0.95rem !important;
    transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
    margin-bottom: 0.18rem;
    position: relative;
    overflow: hidden;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(37,99,235,0.18) !important;
    border-color: rgba(37,99,235,0.35) !important;
    color: #F8FAFC !important;
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1E40AF 0%, #2563EB 100%) !important;
    border-color: transparent !important;
    color: white !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.4);
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8 0%, #3B82F6 100%) !important;
    transform: translateX(0) scale(1.01);
    box-shadow: 0 6px 20px rgba(37,99,235,0.45);
}

.doc-header {
    background: var(--surface);
    backdrop-filter: blur(16px) saturate(180%);
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.75rem;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.06);
}
.header-accent {
    height: 3px;
    width: 100%;
    border-radius: 3px;
    margin-bottom: 1.1rem;
    background: linear-gradient(90deg, #2563EB, #22C55E, #F59E0B, #2563EB);
    background-size: 300% 100%;
    animation: accentFlow 6s ease infinite;
}
@keyframes accentFlow {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.doc-header .kicker {
    font-size: 0.68rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-soft);
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.doc-header h1 {
    font-size: 1.85rem !important;
    margin: 0 !important;
    line-height: 1.15;
}
.doc-header .meta {
    font-size: 0.8rem;
    color: var(--ink-soft);
    display: flex;
    gap: 1.75rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
}
.doc-header .meta strong { color: var(--ink); font-weight: 600; }

.section-heading {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin: 0 0 0.65rem 0;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--line);
}
.section-heading .num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--brass);
    font-weight: 700;
    letter-spacing: 0.05em;
    background: linear-gradient(135deg, #FEF3C7, #FDE68A);
    padding: 0.25rem 0.55rem;
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(180,83,9,0.15);
}
.section-heading h2 { font-size: 1.35rem !important; margin: 0 !important; }
.section-sub {
    font-size: 0.9rem;
    color: var(--ink-soft);
    margin: 0 0 1.4rem 0;
    max-width: 70ch;
    line-height: 1.55;
}

.card {
    background: var(--surface);
    backdrop-filter: blur(12px) saturate(160%);
    -webkit-backdrop-filter: blur(12px) saturate(160%);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 1.5rem 1.6rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.05);
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.9rem;
    margin: 0.9rem 0 1.4rem 0;
}
.stat-card {
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(8px);
    border: 1px solid var(--line);
    border-left: 4px solid transparent;
    border-radius: 12px;
    padding: 1.05rem 1.15rem;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}
.stat-card::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, transparent 40%, rgba(37,99,235,0.05) 100%);
    opacity: 0;
    transition: opacity 0.25s ease;
}
.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(15,23,42,0.1);
}
.stat-card:hover::after { opacity: 1; }
.stat-value {
    font-family: 'Source Serif 4', serif;
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.1;
}
.stat-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--ink-soft);
    margin-top: 0.3rem;
}
.stat-danger { border-left-color: var(--danger); }
.stat-danger .stat-value { color: var(--danger); }
.stat-warn { border-left-color: var(--warn); }
.stat-warn .stat-value { color: var(--warn); }
.stat-neutral { border-left-color: var(--neutral); }
.stat-ok { border-left-color: var(--ok); }
.stat-ok .stat-value { color: var(--ok); }

.tag {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 5px;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.tag-danger { background: var(--danger-soft); color: var(--danger); }
.tag-warn { background: var(--warn-soft); color: var(--warn); }
.tag-neutral { background: var(--neutral-soft); color: var(--neutral); }
.tag-ok { background: var(--ok-soft); color: var(--ok); }
.tag-exact { background: var(--ok-soft); color: var(--ok); }
.tag-approx { background: var(--warn-soft); color: var(--warn); }
.tag-none { background: var(--neutral-soft); color: var(--neutral); }
.finding-ref {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--ink-soft);
}

.stamp-row {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin: 0.5rem 0 1.4rem 0;
    background: var(--surface);
    backdrop-filter: blur(12px);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.3rem 1.5rem;
    box-shadow: 0 4px 18px rgba(15,23,42,0.05);
}
.stamp {
    width: 90px;
    height: 90px;
    border-radius: 50%;
    border: 2.5px dashed var(--brass);
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    transform: rotate(-8deg);
    flex-shrink: 0;
    background: rgba(254,243,199,0.35);
    transition: box-shadow 0.3s ease;
}
.stamp span {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--brass);
    line-height: 1.3;
}
.stamp-critical {
    box-shadow: 0 0 0 4px rgba(220,38,38,0.15), 0 0 24px rgba(220,38,38,0.25);
    animation: criticalPulse 2s ease-in-out infinite;
}
@keyframes criticalPulse {
    0%, 100% { box-shadow: 0 0 0 4px rgba(220,38,38,0.15), 0 0 20px rgba(220,38,38,0.2); }
    50%      { box-shadow: 0 0 0 8px rgba(220,38,38,0.08), 0 0 32px rgba(220,38,38,0.35); }
}

.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%) !important;
    color: white !important;
    border-radius: 10px !important;
    border: none !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.3);
    transition: all 0.2s ease !important;
}
.stButton button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,0.4);
    transform: translateY(-1px);
}
.stButton button[kind="secondary"] { border-radius: 10px !important; }

.sidebar-status {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.78rem;
    margin: 0.3rem 0;
}
.dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
}
.dot-ok {
    background: #22C55E;
    box-shadow: 0 0 0 0 rgba(34,197,94,0.45);
    animation: pulseOk 2.2s ease-in-out infinite;
}
@keyframes pulseOk {
    0%   { box-shadow: 0 0 0 0 rgba(34,197,94,0.45); }
    70%  { box-shadow: 0 0 0 8px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
.dot-wait { background: #475569; }
.dot-warn {
    background: #F59E0B;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.25);
}

.progress-track {
    height: 4px;
    background: #1E293B;
    border-radius: 4px;
    margin: 0.8rem 0 0.4rem 0;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #2563EB, #22C55E, #2563EB);
    background-size: 200% 100%;
    border-radius: 4px;
    animation: progressShine 2.8s linear infinite;
}
@keyframes progressShine {
    0%   { background-position: 100% 0; }
    100% { background-position: -100% 0; }
}

.doc-footer {
    margin-top: 3.5rem;
    padding-top: 1.3rem;
    border-top: 1px solid var(--line);
    font-size: 0.7rem;
    color: var(--ink-soft);
    text-align: center;
}

.impact-hero {
    display: flex;
    align-items: center;
    gap: 2rem;
    background: linear-gradient(135deg, rgba(30,58,95,0.05) 0%, rgba(37,99,235,0.06) 100%);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin: 1rem 0 1.5rem 0;
    flex-wrap: wrap;
}
.impact-hero .impact-figure {
    font-family: 'Source Serif 4', serif;
    font-size: 2.6rem;
    font-weight: 700;
    color: var(--accent-2);
    line-height: 1;
    white-space: nowrap;
}
.impact-hero .impact-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-soft);
    margin-top: 0.35rem;
}
.impact-hero .impact-sub {
    flex: 1;
    min-width: 220px;
    font-size: 0.85rem;
    color: var(--ink-soft);
    line-height: 1.55;
    border-left: 1px solid var(--line);
    padding-left: 1.75rem;
}
.impact-hero .impact-sub strong { color: var(--ink); }

.stepper {
    display: flex;
    align-items: center;
    margin: 0.5rem 0 1.75rem 0;
    flex-wrap: wrap;
    gap: 0;
}
.stepper .step { display: flex; align-items: center; gap: 0.55rem; }
.stepper .step-circle {
    width: 30px; height: 30px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700;
    flex-shrink: 0;
}
.stepper .step-circle.done { background: var(--ok); color: white; }
.stepper .step-circle.current {
    background: var(--accent-2); color: white;
    box-shadow: 0 0 0 4px rgba(37,99,235,0.15);
}
.stepper .step-circle.pending {
    background: var(--neutral-soft); color: var(--ink-soft);
    border: 1px solid var(--line);
}
.stepper .step-label { font-size: 0.8rem; font-weight: 600; color: var(--ink); white-space: nowrap; }
.stepper .step-label.pending { color: var(--ink-soft); font-weight: 500; }
.stepper .step-connector { width: 36px; height: 2px; background: var(--line); margin: 0 0.6rem; }
.stepper .step-connector.done { background: var(--ok); }

#MainMenu, footer { visibility: hidden; }
::selection { background: rgba(37,99,235,0.2); }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================
def section(num: str, title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="section-heading"><span class="num">{num}</span><h2>{title}</h2></div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


def user_greeting() -> str:
    """Bonjour / Bonsoir + prénom (ou email) du compte Google connecté."""
    hour = datetime.datetime.now().hour
    salutation = "Bonsoir" if hour >= 18 or hour < 5 else "Bonjour"
    name = None
    try:
        name = getattr(st.user, "given_name", None) or getattr(st.user, "name", None)
        if not name:
            email = getattr(st.user, "email", None) or ""
            name = email.split("@")[0] if email else None
    except Exception:
        name = None
    if name:
        first = str(name).strip().split()[0]
        return f"{salutation}, {first}"
    return salutation


def stat_grid(items: list) -> str:
    cards = "".join(
        f'<div class="stat-card stat-{style}"><div class="stat-value">{value}</div>'
        f'<div class="stat-label">{label}</div></div>'
        for label, value, style in items
    )
    return f'<div class="stat-grid">{cards}</div>'


def crit_tag(criticite: str) -> str:
    cls = {"BLOQUANT": "tag-danger", "MAJEUR": "tag-warn", "MINEUR": "tag-neutral", "OK": "tag-ok"}.get(
        criticite, "tag-neutral"
    )
    return f'<span class="tag {cls}">{criticite}</span>'


def match_tag(match_type: str) -> str:
    cls = {
        "EXACT_ID": "tag-exact", "EXACT_NOM": "tag-exact",
        "APPROX": "tag-approx", "AUCUN": "tag-none",
    }.get(match_type, "tag-none")
    return f'<span class="tag {cls}">{match_type}</span>'


def confidence_badge(score: float) -> str:
    if score >= 70:
        cls, label = "tag-ok", "CONFIANCE ÉLEVÉE"
    elif score >= 40:
        cls, label = "tag-warn", "CONFIANCE MODÉRÉE"
    else:
        cls, label = "tag-danger", "CONFIANCE FAIBLE"
    return f'<span class="tag {cls}">{label} · {score:.0f}/100</span>'


def risk_level(findings: list) -> str:
    bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
    majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
    if bloquant > 0:
        return "CRITIQUE"
    if majeur >= 3:
        return "ÉLEVÉ"
    if majeur > 0:
        return "MODÉRÉ"
    if findings:
        return "FAIBLE"
    return "AUCUN"


def send_notification(subject: str, html_body: str) -> None:
    """Envoie une notification par email via un compte SMTP dédié à l'app —
    indépendant du compte Google de la personne connectée."""
    if send_email_via_smtp is None:
        raise RuntimeError("Module de notification indisponible (orchestrator/notifier.py introuvable).")
    try:
        sender_email = st.secrets["smtp"]["sender_email"]
        app_password = st.secrets["smtp"]["app_password"]
    except Exception:
        raise RuntimeError(
            "Configuration SMTP manquante — vérifie que [smtp] sender_email "
            "et app_password sont bien définis dans .streamlit/secrets.toml."
        )
    to_email = st.session_state.get("notify_to") or st.user.email
    send_email_via_smtp(
        sender_email=sender_email,
        app_password=app_password,
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )


# ============================================================
# PLAN D'ACTION PRIORISÉ
# ============================================================
_CRITICITE_BASE_SCORE = {"BLOQUANT": 100, "MAJEUR": 60, "MINEUR": 20}
_MODULE_WEIGHT = {
    "Réconciliation de données": 1.15,   # écarts de données = impact direct sur les chiffres du client
    "Module A - Structural Gaps": 1.0,
    "Module B - Functional Coverage": 0.95,
}
_STALLED_BONUS_PER_RUN = 8   # chaque run supplémentaire de dette ajoute un peu d'urgence
_STALLED_BONUS_CAP = 40      # plafond pour ne pas écraser complètement la criticité


def compute_priority_score(finding: dict, stalled_by_libelle: dict) -> dict:
    """Combine criticité, origine, et ancienneté (dette) en un score de priorité
    0-100+, avec le détail du calcul pour que ce soit explicable, pas une boîte noire."""
    base = _CRITICITE_BASE_SCORE.get(finding.get("criticite"), 20)
    weight = _MODULE_WEIGHT.get(finding.get("source_module"), 1.0)

    stalled_info = stalled_by_libelle.get(finding.get("libelle"))
    runs_consecutifs = stalled_info["runs_consecutifs"] if stalled_info else 0
    stalled_bonus = min(_STALLED_BONUS_CAP, runs_consecutifs * _STALLED_BONUS_PER_RUN) if runs_consecutifs >= 2 else 0

    score = round(base * weight + stalled_bonus)

    reasons = [f"criticité {finding.get('criticite', 'MINEUR')}"]
    if weight != 1.0:
        reasons.append("écart de données (impact direct)" if weight > 1.0 else "impact indirect")
    if stalled_bonus:
        reasons.append(f"non résolu depuis {runs_consecutifs} runs consécutifs")

    return {"score": score, "reasons": reasons, "runs_consecutifs": runs_consecutifs}


# ============================================================
# GRAPHIQUES (charte Talan — remplace les graphiques Streamlit par défaut)
# ============================================================
_CHART_INK = "#0B1220"
_CHART_INK_SOFT = "#64748B"
_CHART_GRID = "#E2E8F0"
_CHART_ACCENT = "#2563EB"
_CHART_ACCENT_2 = "#1E3A5F"
_CHART_DANGER = "#DC2626"
_CHART_WARN = "#D97706"
_CHART_NEUTRAL = "#94A3B8"
_CHART_OK = "#059669"

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Inter", "Segoe UI", "Arial", "DejaVu Sans"]


def _style_axes(ax):
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(_CHART_GRID)
    ax.tick_params(colors=_CHART_INK_SOFT, labelsize=9)
    ax.yaxis.grid(True, color=_CHART_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def render_health_score_chart(chart_df: pd.DataFrame):
    """Courbe du score de santé dans le temps, avec zone sous la courbe."""
    fig, ax = plt.subplots(figsize=(9, 3), dpi=160)
    x = chart_df.index
    y = chart_df["health_score"]

    ax.plot(x, y, color=_CHART_ACCENT, linewidth=2.2, marker="o", markersize=5,
            markerfacecolor="white", markeredgecolor=_CHART_ACCENT, markeredgewidth=1.6, zorder=3)
    ax.fill_between(x, y, 0, color=_CHART_ACCENT, alpha=0.08, zorder=1)

    for xi, yi in zip(x, y):
        if pd.notna(yi):
            ax.annotate(f"{yi:.0f}", (xi, yi), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8.5, color=_CHART_INK, fontweight="bold")

    ax.set_ylim(0, 105)
    ax.set_ylabel("")
    _style_axes(ax)
    ax.spines["bottom"].set_visible(True)
    fig.autofmt_xdate(rotation=20, ha="right")
    fig.tight_layout()
    st.pyplot(fig, transparent=True)
    plt.close(fig)


def render_severity_chart(chart_df: pd.DataFrame):
    """Barres empilées : répartition des constats par criticité, par run."""
    fig, ax = plt.subplots(figsize=(9, 3), dpi=160)
    x = range(len(chart_df))
    labels = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in chart_df.index]

    bloquant = chart_df["bloquant"]
    majeur = chart_df["majeur"]
    mineur = chart_df["mineur"]

    ax.bar(x, bloquant, color=_CHART_DANGER, label="Bloquant", width=0.55, zorder=3)
    ax.bar(x, majeur, bottom=bloquant, color=_CHART_WARN, label="Majeur", width=0.55, zorder=3)
    ax.bar(x, mineur, bottom=bloquant + majeur, color=_CHART_NEUTRAL, label="Mineur", width=0.55, zorder=3)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _style_axes(ax)
    ax.spines["bottom"].set_visible(True)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncols=3, bbox_to_anchor=(0, 1.15))
    fig.tight_layout()
    st.pyplot(fig, transparent=True)
    plt.close(fig)


def render_business_impact_chart(temps_manuel_min: float, temps_auto_min: float):
    """Barres horizontales comparant temps manuel estimé vs temps automatisé mesuré."""
    fig, ax = plt.subplots(figsize=(9, 2.6), dpi=160)
    labels = ["Audit manuel (estimé)", "Audit automatisé (mesuré)"]
    values = [temps_manuel_min, temps_auto_min]
    colors = [_CHART_NEUTRAL, _CHART_ACCENT]

    bars = ax.barh(labels, values, color=colors, height=0.5, zorder=3)
    max_v = max(values + [1])
    for bar, v in zip(bars, values):
        label = f"{v:.0f} min" if v < 60 else f"{v / 60:.1f} h"
        ax.text(bar.get_width() + max_v * 0.015, bar.get_y() + bar.get_height() / 2,
                label, va="center", fontsize=9.5, color=_CHART_INK, fontweight="bold")

    ax.invert_yaxis()
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, labelsize=10, colors=_CHART_INK)
    fig.tight_layout()
    st.pyplot(fig, transparent=True)
    plt.close(fig)


def findings_from_reconciliation(rec_df: pd.DataFrame) -> list:
    findings = []
    if rec_df is None or rec_df.empty:
        return findings
    for _, row in rec_df.iterrows():
        statut = row.get("statut", "")
        criticite = row.get("criticite", "MINEUR")
        if statut == "MATCH_VALUE" or criticite == "OK":
            continue
        findings.append({
            "source_module": "Réconciliation de données",
            "libelle": f"{row.get('kpi') or row.get('kpi_pbi', '')} — {statut}",
            "detail": (
                f"Qlik={row.get('valeur_qlik')} | PBI={row.get('valeur_pbi')} | "
                f"feuille Qlik={row.get('sheet_qlik')} | page PBI={row.get('page_pbi')} | "
                f"correspondance={row.get('match_type')} (score {row.get('match_score')})"
            ),
            "criticite": criticite if criticite != "OK" else "MINEUR",
            "diagnostic": row.get("cause_probable", ""),
            "recommandation": row.get("correction", ""),
            "statut": statut,
        })
    return findings


def show_ecarts(rec_df: pd.DataFrame) -> None:
    action = rec_df[rec_df["statut"].isin(["ECART_VALEUR", "MANQUANT_PBI", "MANQUANT_QLIK", "ERREUR_PBI"])]
    if action.empty:
        st.success("Aucun écart hors tolérance à traiter.")
        return
    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
    action = action.assign(_ordre=action["criticite"].map(ordre).fillna(3)).sort_values("_ordre")

    for idx, row in action.iterrows():
        with st.expander(f"{row.get('kpi') or row.get('kpi_pbi')} — {row.get('statut')}"):
            st.markdown(
                f"{crit_tag(row.get('criticite'))} &nbsp; {match_tag(row.get('match_type', 'AUCUN'))} "
                f"<span class='finding-ref'>score {row.get('match_score', 0):.2f}</span>",
                unsafe_allow_html=True,
            )
            st.write(f"**Feuille Qlik :** `{row.get('sheet_qlik', '') or '—'}` · **Page PBI :** `{row.get('page_pbi', '') or '—'}`")
            st.write(f"**KPI Qlik :** `{row.get('kpi') or '—'}` · **KPI PBI :** `{row.get('kpi_pbi') or '—'}`")
            st.write(f"**Valeur Qlik :** `{row.get('valeur_qlik')}` · **Valeur PBI :** `{row.get('valeur_pbi')}`")
            if row.get("expr_qlik"):
                st.write(f"**Expression Qlik :** `{row.get('expr_qlik')}`")
            if row.get("expr_pbi"):
                st.write(f"**Expression PBI :** `{row.get('expr_pbi')}`")
            st.write(f"**Cause probable :** {row.get('cause_probable')}")
            st.write(f"**Correction suggérée :** {row.get('correction')}")

            if generate_dax_fix is not None:
                row_key = (
                    f"daxfix_{idx}_" +
                    "_".join(str(x) for x in [row.get("kpi"), row.get("kpi_pbi"), row.get("statut")])
                )
                if st.button("Générer le correctif DAX (IA)", key=f"btn_{row_key}"):
                    with st.spinner("L'agent analyse l'écart et rédige un correctif DAX…"):
                        st.session_state[row_key] = generate_dax_fix(
                            kpi_qlik=row.get("kpi"),
                            kpi_pbi=row.get("kpi_pbi"),
                            expr_qlik=row.get("expr_qlik"),
                            expr_pbi=row.get("expr_pbi"),
                            valeur_qlik=row.get("valeur_qlik"),
                            valeur_pbi=row.get("valeur_pbi"),
                            statut=row.get("statut"),
                        )

                if row_key in st.session_state:
                    fix = st.session_state[row_key]
                    if fix.get("cause"):
                        st.markdown(f"**Cause identifiée par l'agent :** {fix['cause']}")
                    if fix.get("dax_corrige"):
                        validation = fix.get("validation") or {}
                        if not validation.get("valide", True):
                            st.error(
                                "⚠️ Ce DAX généré par l'IA présente des signes d'erreur de "
                                "syntaxe (vérification automatique, pas un vrai parseur DAX) — "
                                "**à corriger avant utilisation** :"
                            )
                            for w in validation.get("avertissements", []):
                                st.markdown(f"- {w}")
                        st.markdown("**DAX corrigé proposé :**")
                        st.code(fix["dax_corrige"], language="dax")
                        if validation.get("valide"):
                            st.caption("✅ Vérification syntaxique de base passée (pas une garantie de validité DAX complète).")
                    if fix.get("explication"):
                        st.caption(fix["explication"])
                    if not fix.get("dax_corrige") and not fix.get("cause"):
                        st.warning("L'agent n'a pas pu générer de correctif au format attendu.")
                        if fix.get("brut"):
                            with st.expander("Voir la réponse brute du LLM (diagnostic)"):
                                st.text(fix["brut"])

                if generate_dax_fix_with_confidence is not None:
                    conf_key = f"{row_key}_confidence"
                    st.caption(
                        "Vérification approfondie : relance la génération 3 fois et mesure "
                        "la cohérence — **plus lent** (jusqu'à ~5 min selon ta machine)."
                    )
                    if st.button("Vérifier la confiance (3 générations)", key=f"btn_conf_{row_key}"):
                        with st.spinner("Génération x3 en cours pour mesurer la confiance…"):
                            st.session_state[conf_key] = generate_dax_fix_with_confidence(
                                kpi_qlik=row.get("kpi"),
                                kpi_pbi=row.get("kpi_pbi"),
                                expr_qlik=row.get("expr_qlik"),
                                expr_pbi=row.get("expr_pbi"),
                                valeur_qlik=row.get("valeur_qlik"),
                                valeur_pbi=row.get("valeur_pbi"),
                                statut=row.get("statut"),
                                n_runs=3,
                            )

                    if conf_key in st.session_state:
                        conf = st.session_state[conf_key]
                        st.progress(conf["taux_validite"] / 100, text=f"Validité syntaxique : {conf['taux_validite']:.0f}% ({conf['n_runs']} générations)")
                        st.progress(conf["taux_stabilite"] / 100, text=f"Stabilité inter-générations : {conf['taux_stabilite']:.0f}%")
                        st.markdown(confidence_badge(conf["confiance"]), unsafe_allow_html=True)

                        prop = conf["proposition"]
                        if prop.get("dax_corrige"):
                            st.markdown("**Proposition retenue (la plus fiable des 3) :**")
                            st.code(prop["dax_corrige"], language="dax")
                            if not prop.get("validation", {}).get("valide", True):
                                st.caption("⚠️ Même la meilleure proposition sur 3 présente des doutes de syntaxe — à vérifier manuellement.")
                        with st.expander("Voir les 3 générations individuelles"):
                            for i, r in enumerate(conf["runs"], 1):
                                st.markdown(f"**Génération {i} :**")
                                if r.get("dax_corrige"):
                                    st.code(r["dax_corrige"], language="dax")
                                    st.caption("✅ Valide" if r.get("validation", {}).get("valide") else "⚠️ Doute de syntaxe")
                                else:
                                    st.caption(f"Échec : {r.get('cause', 'raison inconnue')}")
            else:
                st.caption(
                    "Module de correctif DAX (IA) indisponible — vérifie que "
                    "`src/module_b/dax_fix_generator.py` existe et s'importe sans erreur."
                )


def build_qlik_expressions_text(qlik_result: dict) -> str:
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


def export_module_a_excel(rec_df: pd.DataFrame, qlik_result: dict, pbi_result: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if rec_df is not None and not rec_df.empty:
            rec_df.to_excel(writer, sheet_name="Reconciliation_KPIs", index=False)
        pd.DataFrame(qlik_result.get("kpis", [])).to_excel(writer, sheet_name="Qlik_KPIs", index=False)
        pd.DataFrame(pbi_result.get("kpis", [])).to_excel(writer, sheet_name="PBI_KPIs", index=False)
    return buf.getvalue()


def to_finding_objects(findings: list):
    return [
        Finding(
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


# ============================================================
# ALERTES DE TENDANCE (en plus des alertes ponctuelles)
# ============================================================
_TREND_SCORE_DROP_THRESHOLD = 10  # points de score de santé


def detect_trend_alerts(current_health_score, current_coverage_rate) -> list:
    """Compare le run courant à l'historique pour détecter des tendances
    négatives dans la durée — en plus des alertes ponctuelles ('nouveau
    bloquant') déjà en place. Deux signaux :
      - chute du score de santé par rapport au run précédent
      - régression du taux de couverture sur 2 runs consécutifs ou plus
    Ne nécessite pas de nouveau run enregistré : peut être appelé avec les
    valeurs "en cours" (avant même de sauvegarder le run) pour prévenir tôt.
    """
    alerts = []
    if history_load_df is None:
        return alerts
    try:
        hist_df = history_load_df()
    except Exception:
        return alerts
    if hist_df is None or hist_df.empty:
        return alerts

    hist_sorted = hist_df.sort_values("timestamp")

    # --- Chute du score de santé vs le run précédent ---
    if current_health_score is not None:
        prev_score = hist_sorted.iloc[-1].get("health_score")
        if pd.notna(prev_score):
            delta = current_health_score - float(prev_score)
            if delta <= -_TREND_SCORE_DROP_THRESHOLD:
                alerts.append({
                    "type": "score_drop",
                    "severity": "danger" if delta <= -20 else "warn",
                    "message": (
                        f"Le score de santé a chuté de {abs(delta):.0f} points depuis le "
                        f"run précédent ({prev_score:.0f} → {current_health_score:.0f})."
                    ),
                })

    # --- Régression du taux de couverture sur 2+ runs consécutifs ---
    if current_coverage_rate is not None and "coverage_rate" in hist_sorted.columns:
        past_coverage = list(hist_sorted["coverage_rate"].dropna().tail(2))
        coverage_series = past_coverage + [float(current_coverage_rate)]
        if len(coverage_series) >= 3 and coverage_series[-1] < coverage_series[-2] < coverage_series[-3]:
            alerts.append({
                "type": "coverage_regression",
                "severity": "warn",
                "message": (
                    "Le taux de couverture fonctionnelle régresse depuis 2 runs consécutifs "
                    f"({coverage_series[-3]:.0f}% → {coverage_series[-2]:.0f}% → {coverage_series[-1]:.0f}%)."
                ),
            })

    return alerts


def render_trend_alerts(alerts: list) -> None:
    for a in alerts:
        if a.get("severity") == "danger":
            st.error(a["message"])
        else:
            st.warning(a["message"])


def email_trend_alert_html(reference: str, alerts: list) -> str:
    """Corps HTML de l'email d'alerte de tendance — construit ici plutôt que
    dans orchestrator/notifier.py pour ne pas dépendre d'un template dédié."""
    items = "".join(f"<li>{a['message']}</li>" for a in alerts)
    return f"""
    <div style="font-family:Arial,sans-serif;color:#0B1220;">
      <h2 style="margin-bottom:0.4rem;">Alerte de tendance — {reference}</h2>
      <p style="color:#475569;">Les tendances suivantes ont été détectées sur ce run, en plus
      des constats ponctuels :</p>
      <ul style="line-height:1.6;">{items}</ul>
      <p style="color:#94A3B8;font-size:0.8rem;margin-top:1rem;">
        Généré automatiquement par l'outil d'audit de migration Qlik → Power BI.
      </p>
    </div>
    """


# ============================================================
# MODE PRÉSENTATION CLIENT (plein écran, sans sidebar)
# ============================================================
def _pres_stat(col, value, label, color) -> None:
    with col:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-family:'Source Serif 4',serif; font-size:2.4rem; font-weight:700; color:{color};">{value}</div>
                <div style="font-size:0.68rem; letter-spacing:0.08em; text-transform:uppercase; color:#94A3B8; margin-top:0.2rem;">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_presentation_mode(reference: str) -> None:
    """Affichage plein écran pensé pour être projeté en réunion client :
    pas de sidebar, pas de jargon technique, juste le score de santé et le
    plan d'action prioritisé, en gros caractères."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        #MainMenu, footer, header[data-testid="stHeader"] { display: none !important; }
        .main .block-container { max-width: 1100px !important; padding: 3rem 2.5rem !important; margin: 0 auto !important; }
        .stApp {
            background: linear-gradient(160deg, #0B1220 0%, #111827 55%, #1E293B 100%) !important;
            background-attachment: fixed !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    findings = st.session_state.get("findings") or []
    mb = st.session_state.get("module_b_coverage")
    cov_rate = mb.get("coverage_rate") if mb else None
    health = (
        compute_health_score(to_finding_objects(findings), cov_rate)
        if compute_health_score is not None and findings else {}
    )
    niveau = risk_level(findings) if findings else "AUCUN"
    score_val = health.get("score")
    score_color = "#22C55E" if (score_val or 0) >= 70 else "#F59E0B" if (score_val or 0) >= 40 else "#EF4444"

    top_l, top_mid, top_r = st.columns([5, 1, 1])
    with top_l:
        st.markdown(
            f'<div style="font-size:0.8rem;letter-spacing:0.14em;text-transform:uppercase;'
            f'color:#94A3B8;margin-top:0.4rem;">Audit de migration · Qlik → Power BI · {reference}</div>',
            unsafe_allow_html=True,
        )
    with top_mid:
        if st.button("Actualiser", key="refresh_presentation"):
            st.rerun()
    with top_r:
        if st.button("Quitter", key="exit_presentation"):
            st.session_state["presentation_mode"] = False
            st.rerun()

    if not findings:
        st.markdown(
            '<div style="font-family:\'Source Serif 4\',serif;font-size:1.8rem;'
            'color:#F8FAFC;margin-top:3rem;text-align:center;">'
            "Aucun audit consolidé pour l'instant.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div style="text-align:center; margin: 2.5rem 0 2.5rem 0;">
            <div style="font-family:'Source Serif 4',serif; font-size:7rem; font-weight:700; line-height:1; color:{score_color};">
                {score_val if score_val is not None else '—'}<span style="font-size:2.3rem; opacity:0.6;">/100</span>
            </div>
            <div style="font-size:1.05rem; letter-spacing:0.08em; text-transform:uppercase; color:#94A3B8; margin-top:0.6rem;">
                Score de santé · {health.get('niveau', '—')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
    majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
    mineur = sum(1 for f in findings if f.get("criticite") == "MINEUR")

    c1, c2, c3, c4 = st.columns(4)
    _pres_stat(c1, bloquant, "Bloquants", "#EF4444")
    _pres_stat(c2, majeur, "Majeurs", "#F59E0B")
    _pres_stat(c3, mineur, "Mineurs", "#94A3B8")
    _pres_stat(c4, niveau, "Risque global", score_color)

    trend_alerts = detect_trend_alerts(score_val, cov_rate)
    if trend_alerts:
        st.markdown('<div style="height:1.5rem;"></div>', unsafe_allow_html=True)
        for a in trend_alerts:
            border = "#EF4444" if a.get("severity") == "danger" else "#F59E0B"
            st.markdown(
                f"""
                <div style="border-left:3px solid {border}; background:rgba(255,255,255,0.05);
                     border-radius:8px; padding:0.7rem 1rem; margin-bottom:0.5rem; color:#E2E8F0; font-size:0.9rem;">
                    {a['message']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div style="height:1px;background:rgba(148,163,184,0.25);margin:2.5rem 0 2rem 0;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-family:\'Source Serif 4\',serif;font-size:1.55rem;font-weight:700;'
        'color:#F8FAFC;margin-bottom:1.2rem;">Plan d\'action prioritaire</div>',
        unsafe_allow_html=True,
    )

    stalled_by_libelle = {}
    if history_detect_stalled is not None:
        try:
            stalled_by_libelle = {f.get("libelle"): f for f in history_detect_stalled(min_runs=2)}
        except Exception:
            stalled_by_libelle = {}

    scored = sorted(
        ({**f, **compute_priority_score(f, stalled_by_libelle)} for f in findings),
        key=lambda x: -x["score"],
    )[:5]

    tag_color = {"BLOQUANT": "#EF4444", "MAJEUR": "#F59E0B", "MINEUR": "#94A3B8"}
    for rank, f in enumerate(scored, 1):
        cl = tag_color.get(f.get("criticite"), "#94A3B8")
        st.markdown(
            f"""
            <div style="display:flex; align-items:flex-start; gap:1.1rem; padding:1rem 0;
                 border-bottom:1px solid rgba(148,163,184,0.15);">
                <div style="font-family:'JetBrains Mono',monospace; font-size:1.4rem; font-weight:700; color:#64748B; width:2.2rem;">
                    {rank}
                </div>
                <div style="flex:1;">
                    <div style="font-size:1.08rem; font-weight:600; color:#F8FAFC;">{f.get('libelle', '')}</div>
                    <div style="font-size:0.85rem; color:#94A3B8; margin-top:0.3rem;">{f.get('recommandation', '') or f.get('diagnostic', '')}</div>
                </div>
                <div style="font-size:0.66rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;
                     color:{cl}; border:1px solid {cl}; border-radius:6px; padding:0.2rem 0.6rem; white-space:nowrap; margin-top:0.15rem;">
                    {f.get('criticite', '')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="text-align:center; margin-top:3rem; font-size:0.72rem; color:#475569;">'
        f"Talan · {datetime.date.today().strftime('%d %B %Y')}</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================
for key, default in [
    ("findings", []),
    ("structural_findings", []),
    ("module_b_coverage", None),
    ("qlik_extraction", None),
    ("pbi_extraction", None),
    ("module_a_reconciliation", None),
    ("current_page", "00"),
    ("qa_history", []),
    ("timing_extraction_sec", None),
    ("timing_coverage_sec", None),
    ("timing_kpis_reconcilies", 0),
    ("notify_to", ""),
    ("alert_settings", {"bloquant": True, "rapport": True, "dette": True, "tendance": True}),
    ("last_bloquant_libelles", set()),
    ("presentation_mode", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ============================================================
# GATE — Connexion Google (landing animée, centrée)
# ============================================================
if not getattr(st.user, "is_logged_in", False):
    _login_logo_html = ""
    if LOGO_PATH.exists():
        _lb64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        _login_logo_html = (
            f'<img src="data:image/png;base64,{_lb64}" '
            f'class="login-logo" alt="Talan">'
        )
    else:
        _login_logo_html = '<div class="login-logo-text">TALAN</div>'

    # Logo Google : même technique que Talan = balise <img> (fiable),
    # priorité assets/logo_google.jpg, sinon SVG officiel 4 couleurs.
    if LOGO_GOOGLE_PATH.exists():
        _g_b64 = base64.b64encode(LOGO_GOOGLE_PATH.read_bytes()).decode()
        _g_src = f"data:image/jpeg;base64,{_g_b64}"
    else:
        _g_src = (
            "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E"
            "%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/%3E"
            "%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/%3E"
            "%3Cpath fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z'/%3E"
            "%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z'/%3E"
            "%3C/svg%3E"
        )
    _g_img_html = (
        f'<img src="{_g_src}" alt="Google" class="gbtn-logo" '
        f'width="22" height="22" draggable="false" />'
    )

    st.markdown(
        f"""
<style>
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
#MainMenu, footer, header[data-testid="stHeader"] {{
  display: none !important;
}}
.stApp {{ background: #070B14 !important; }}
[data-testid="stAppViewContainer"] > .main {{ padding: 0 !important; }}
.main .block-container {{
  max-width: 100% !important;
  padding: 0 !important;
  margin: 0 !important;
}}

/* ---- Keyframes ---- */
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(22px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
  from {{ opacity: 0; }}
  to   {{ opacity: 1; }}
}}
@keyframes scaleIn {{
  from {{ opacity: 0; transform: scale(0.92); }}
  to   {{ opacity: 1; transform: scale(1); }}
}}
@keyframes softFloat {{
  0%, 100% {{ transform: translateY(0); }}
  50%      {{ transform: translateY(-7px); }}
}}
@keyframes shimmerLine {{
  0%   {{ background-position: 0% 50%; }}
  100% {{ background-position: 200% 50%; }}
}}
@keyframes pulseGlow {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(37,99,235,0.28), 0 28px 56px -14px rgba(0,0,0,0.5); }}
  50%      {{ box-shadow: 0 0 0 8px rgba(37,99,235,0.06), 0 28px 56px -14px rgba(0,0,0,0.5); }}
}}
@keyframes bgDrift {{
  0%   {{ transform: scale(1) translate(0, 0); }}
  100% {{ transform: scale(1.08) translate(-1.5%, 1%); }}
}}
@keyframes meshPulse {{
  0%, 100% {{ opacity: 0.55; }}
  50%      {{ opacity: 0.85; }}
}}
@keyframes pillIn {{
  from {{ opacity: 0; transform: translateY(10px) scale(0.94); }}
  to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
@keyframes announceIn {{
  from {{ opacity: 0; transform: translateX(-16px); }}
  to   {{ opacity: 1; transform: translateX(0); }}
}}
@keyframes bannerShine {{
  0%   {{ background-position: -120% 0; }}
  100% {{ background-position: 220% 0; }}
}}
@keyframes orbFloat1 {{
  0%, 100% {{ transform: translate(0, 0) scale(1); }}
  50%      {{ transform: translate(18px, -22px) scale(1.06); }}
}}
@keyframes orbFloat2 {{
  0%, 100% {{ transform: translate(0, 0) scale(1); }}
  50%      {{ transform: translate(-24px, 16px) scale(1.08); }}
}}
@keyframes particleDrift {{
  0%   {{ transform: translateY(0) rotate(0deg); opacity: 0.4; }}
  50%  {{ opacity: 0.7; }}
  100% {{ transform: translateY(-40px) rotate(8deg); opacity: 0.35; }}
}}
@keyframes statusBlink {{
  0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }}
  50%      {{ opacity: 0.75; box-shadow: 0 0 0 6px rgba(34,197,94,0); }}
}}
@keyframes floatCardA {{
  0%, 100% {{ transform: translateY(0) rotate(-1.5deg); }}
  50%      {{ transform: translateY(-14px) rotate(-0.5deg); }}
}}
@keyframes floatCardB {{
  0%, 100% {{ transform: translateY(0) rotate(1.2deg); }}
  50%      {{ transform: translateY(-18px) rotate(2deg); }}
}}
@keyframes floatCardC {{
  0%, 100% {{ transform: translateY(0) rotate(0.8deg); }}
  50%      {{ transform: translateY(-12px) rotate(-0.4deg); }}
}}
@keyframes floatCardD {{
  0%, 100% {{ transform: translateY(0) rotate(-0.6deg); }}
  50%      {{ transform: translateY(-16px) rotate(0.8deg); }}
}}
@keyframes floatIn {{
  from {{ opacity: 0; transform: translateY(24px) scale(0.92); }}
  to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

.login-shell {{
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.25rem 1.25rem 3.25rem 1.25rem;
  box-sizing: border-box;
  overflow: hidden;
}}

/* Fond multi-couches : photo + mesh + orbes */
.login-shell-bg {{
  position: absolute;
  inset: 0;
  background-color: #070B14;
  background-image:
    linear-gradient(165deg, rgba(7,11,20,0.92) 0%, rgba(15,23,42,0.78) 42%, rgba(7,11,20,0.94) 100%),
    url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1920&q=80');
  background-size: cover;
  background-position: center;
  animation: bgDrift 32s ease-in-out infinite alternate;
}}
.login-shell-bg::before {{
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 55% 45% at 15% 20%, rgba(37,99,235,0.28) 0%, transparent 55%),
    radial-gradient(ellipse 45% 40% at 85% 75%, rgba(16,185,129,0.18) 0%, transparent 50%),
    radial-gradient(ellipse 35% 30% at 70% 15%, rgba(245,158,11,0.10) 0%, transparent 45%),
    radial-gradient(ellipse 40% 35% at 30% 85%, rgba(99,102,241,0.12) 0%, transparent 50%);
  animation: meshPulse 12s ease-in-out infinite;
  pointer-events: none;
}}
.login-shell-bg::after {{
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(1.5px 1.5px at 12% 25%, rgba(147,197,253,0.45), transparent),
    radial-gradient(1.5px 1.5px at 78% 18%, rgba(110,231,183,0.35), transparent),
    radial-gradient(1px 1px at 45% 70%, rgba(252,211,77,0.30), transparent),
    radial-gradient(1.5px 1.5px at 88% 55%, rgba(147,197,253,0.28), transparent),
    radial-gradient(1px 1px at 22% 82%, rgba(167,139,250,0.25), transparent),
    radial-gradient(1.5px 1.5px at 60% 40%, rgba(110,231,183,0.22), transparent);
  animation: particleDrift 22s linear infinite;
  pointer-events: none;
  opacity: 0.7;
}}

.login-orb {{
  position: absolute;
  border-radius: 50%;
  filter: blur(48px);
  pointer-events: none;
  z-index: 1;
}}
.login-orb-1 {{
  width: 280px; height: 280px;
  top: 8%; left: -4%;
  background: radial-gradient(circle, rgba(37,99,235,0.35) 0%, transparent 70%);
  animation: orbFloat1 14s ease-in-out infinite;
}}
.login-orb-2 {{
  width: 220px; height: 220px;
  bottom: 12%; right: -2%;
  background: radial-gradient(circle, rgba(16,185,129,0.28) 0%, transparent 70%);
  animation: orbFloat2 16s ease-in-out infinite;
}}

.login-center {{
  position: relative;
  z-index: 3;
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
}}

.login-logo, .login-logo-text {{
  animation: fadeUp 0.75s cubic-bezier(0.22,1,0.36,1) both;
}}
.login-logo {{
  height: 52px;
  width: auto;
  margin-bottom: 1.35rem;
  display: block;
  filter: drop-shadow(0 6px 16px rgba(0,0,0,0.35));
}}
.login-logo-text {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 1.9rem;
  font-weight: 700;
  color: #F8FAFC !important;
  margin-bottom: 1.35rem;
  letter-spacing: -0.02em;
}}

.login-kicker {{
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #94A3B8 !important;
  text-align: center;
  margin-bottom: 0.6rem;
  animation: fadeUp 0.7s 0.08s cubic-bezier(0.22,1,0.36,1) both;
}}
.login-title {{
  font-family: 'Source Serif 4', Georgia, serif !important;
  font-size: clamp(1.6rem, 4.2vw, 2.05rem) !important;
  font-weight: 700 !important;
  line-height: 1.15 !important;
  text-align: center !important;
  color: #F8FAFC !important;
  margin: 0 0 0.6rem 0 !important;
  animation: fadeUp 0.75s 0.14s cubic-bezier(0.22,1,0.36,1) both;
}}
.login-title .grad {{
  background: linear-gradient(90deg, #60A5FA, #34D399, #FBBF24, #60A5FA);
  background-size: 300% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmerLine 6s linear infinite;
}}
.login-sub {{
  text-align: center;
  font-size: 0.9rem !important;
  line-height: 1.55 !important;
  color: #CBD5E1 !important;
  margin: 0 0 1.2rem 0 !important;
  max-width: 38ch;
  animation: fadeUp 0.75s 0.2s cubic-bezier(0.22,1,0.36,1) both;
}}

.login-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: center;
  margin-bottom: 1.25rem;
}}
.login-pill {{
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.32rem 0.72rem;
  border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.32);
  color: #E2E8F0 !important;
  background: rgba(15,23,42,0.55);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  animation: pillIn 0.55s cubic-bezier(0.22,1,0.36,1) both;
  transition: all 0.22s ease;
}}
.login-pill:nth-child(1) {{ animation-delay: 0.26s; }}
.login-pill:nth-child(2) {{ animation-delay: 0.34s; }}
.login-pill:nth-child(3) {{ animation-delay: 0.42s; }}
.login-pill:nth-child(4) {{ animation-delay: 0.50s; }}
.login-pill:hover {{
  border-color: rgba(96,165,250,0.6);
  background: rgba(37,99,235,0.22);
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(37,99,235,0.2);
}}

/* Bannière statique (annonce permanente) — version modernisée */
.login-banner {{
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 1rem 0.7rem 0.7rem;
  margin-bottom: 0.85rem;
  border-radius: 14px;
  background: linear-gradient(110deg, rgba(37,99,235,0.24) 0%, rgba(16,185,129,0.16) 50%, rgba(37,99,235,0.20) 100%);
  background-size: 220% 100%;
  border: 1px solid rgba(96,165,250,0.4);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  animation: fadeUp 0.7s 0.24s cubic-bezier(0.22,1,0.36,1) both,
             bannerShine 7s linear infinite,
             bannerGlow 4s ease-in-out infinite;
  position: relative;
  overflow: hidden;
}}
.login-banner::after {{
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 35%, rgba(255,255,255,0.14) 50%, transparent 65%);
  background-size: 200% 100%;
  animation: bannerShine 3.2s ease-in-out infinite;
  pointer-events: none;
}}
@keyframes bannerGlow {{
  0%, 100% {{ box-shadow: 0 4px 18px rgba(37,99,235,0.10), inset 0 1px 0 rgba(255,255,255,0.08); }}
  50%      {{ box-shadow: 0 4px 26px rgba(37,99,235,0.28), inset 0 1px 0 rgba(255,255,255,0.14); }}
}}
.login-banner .status-badge {{
  position: relative;
  z-index: 1;
  width: 26px; height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(34,197,94,0.16);
  border: 1px solid rgba(34,197,94,0.4);
}}
.login-banner .status-dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #22C55E;
  animation: statusBlink 1.8s ease-in-out infinite;
}}
.login-banner .banner-tx {{
  font-size: 0.77rem;
  line-height: 1.4;
  color: #EEF2FF !important;
  position: relative;
  z-index: 1;
}}
.login-banner .banner-tx strong {{ color: #FFFFFF !important; font-weight: 700; }}

/* Cartes flottantes Qlik / Power BI autour de l'écran */
.float-layer {{
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}}
.float-card {{
  position: absolute;
  max-width: 240px;
  padding: 0.85rem 1rem;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.22);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  box-shadow: 0 12px 40px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.06);
  pointer-events: auto;
  animation: floatIn 0.9s cubic-bezier(0.22,1,0.36,1) both;
}}
.float-card .fc-tag {{
  display: inline-block;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  margin-bottom: 0.45rem;
}}
.float-card .fc-tag.qlik {{
  background: rgba(89, 171, 227, 0.2);
  color: #7DD3FC;
  border: 1px solid rgba(89, 171, 227, 0.35);
}}
.float-card .fc-tag.pbi {{
  background: rgba(242, 201, 76, 0.15);
  color: #FCD34D;
  border: 1px solid rgba(242, 201, 76, 0.35);
}}
.float-card .fc-tag.both {{
  background: rgba(99, 102, 241, 0.18);
  color: #A5B4FC;
  border: 1px solid rgba(129, 140, 248, 0.35);
}}
.float-card .fc-title {{
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 0.92rem;
  font-weight: 600;
  color: #F8FAFC !important;
  margin: 0 0 0.3rem 0;
  line-height: 1.25;
}}
.float-card .fc-body {{
  font-size: 0.72rem;
  line-height: 1.45;
  color: #94A3B8 !important;
  margin: 0;
}}
.float-card:hover {{
  border-color: rgba(96,165,250,0.45);
  box-shadow: 0 16px 48px rgba(0,0,0,0.35), 0 0 0 1px rgba(37,99,235,0.15);
}}

.float-tl {{ top: 6%; left: 3%; animation-delay: 0.15s; animation-name: floatIn, floatCardA; animation-duration: 0.9s, 7s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}
.float-tr {{ top: 8%; right: 3%; animation-delay: 0.28s; animation-name: floatIn, floatCardB; animation-duration: 0.9s, 8.5s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}
.float-ml {{ top: 42%; left: 2%; animation-delay: 0.4s; animation-name: floatIn, floatCardC; animation-duration: 0.9s, 9s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}
.float-mr {{ top: 38%; right: 2.5%; animation-delay: 0.48s; animation-name: floatIn, floatCardD; animation-duration: 0.9s, 7.5s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}
.float-bl {{ bottom: 8%; left: 4%; animation-delay: 0.55s; animation-name: floatIn, floatCardB; animation-duration: 0.9s, 8s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}
.float-br {{ bottom: 10%; right: 4%; animation-delay: 0.62s; animation-name: floatIn, floatCardA; animation-duration: 0.9s, 9.5s; animation-timing-function: cubic-bezier(0.22,1,0.36,1), ease-in-out; animation-iteration-count: 1, infinite; animation-fill-mode: both, none; }}

@media (max-width: 1100px) {{
  .float-ml, .float-mr {{ display: none; }}
  .float-card {{ max-width: 200px; padding: 0.7rem 0.85rem; }}
  .float-card .fc-title {{ font-size: 0.82rem; }}
  .float-card .fc-body {{ font-size: 0.68rem; }}
}}
@media (max-width: 780px) {{
  .float-layer {{ display: none; }}
}}

.login-card {{
  width: 100%;
  background: rgba(255,255,255,0.97);
  border-radius: 22px;
  padding: 1.55rem 1.4rem 1.35rem 1.4rem;
  border: 1px solid rgba(255,255,255,0.6);
  animation: scaleIn 0.75s 0.38s cubic-bezier(0.22,1,0.36,1) both, pulseGlow 5s 1.3s ease-in-out infinite;
}}
.login-card-title {{
  font-family: 'Source Serif 4', Georgia, serif !important;
  font-size: 1.2rem !important;
  font-weight: 700 !important;
  color: #0B1220 !important;
  margin: 0 0 0.3rem 0 !important;
  text-align: center;
}}
.login-card-sub {{
  font-size: 0.8rem !important;
  color: #64748B !important;
  line-height: 1.5 !important;
  text-align: center;
  margin-bottom: 0.95rem !important;
}}
.login-features {{
  list-style: none;
  margin: 0 0 0.95rem 0 !important;
  padding: 0.65rem 0 !important;
  border-top: 1px solid #F1F5F9;
  border-bottom: 1px solid #F1F5F9;
}}
.login-features li {{
  font-size: 0.8rem;
  color: #334155 !important;
  padding: 0.3rem 0;
  display: flex;
  gap: 0.5rem;
  line-height: 1.4;
  animation: fadeUp 0.5s cubic-bezier(0.22,1,0.36,1) both;
}}
.login-features li:nth-child(1) {{ animation-delay: 0.52s; }}
.login-features li:nth-child(2) {{ animation-delay: 0.60s; }}
.login-features li:nth-child(3) {{ animation-delay: 0.68s; }}
.login-features li .check {{
  color: #059669;
  font-weight: 700;
  width: 1.1rem;
  text-align: center;
}}

.login-divider {{
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin: 0 0 0.85rem 0;
  color: #94A3B8 !important;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.login-divider::before, .login-divider::after {{
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, #E2E8F0, transparent);
}}

/* Bouton Google réel (Streamlit) — logo + texte, un seul bouton cliquable */
.google-login-btn-anchor {{
  position: relative;
  z-index: 30;
  margin-top: -6.35rem;
  padding: 0 0.15rem 0.45rem 0.15rem;
  animation: fadeUp 0.65s 0.58s cubic-bezier(0.22,1,0.36,1) both;
}}
.gbtn-wrap {{
  position: relative;
  width: 100%;
}}
.gbtn-wrap .stButton {{
  width: 100% !important;
  margin: 0 !important;
}}
.gbtn-wrap .stButton > button,
.gbtn-wrap .stButton > button[kind="secondary"],
.gbtn-wrap .stButton > button[data-testid="baseButton-secondary"],
.gbtn-wrap .stButton > button[kind="primary"] {{
  width: 100% !important;
  height: 52px !important;
  min-height: 52px !important;
  max-height: 52px !important;
  border-radius: 999px !important;
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  background-image: none !important;
  border: 1.5px solid #DADCE0 !important;
  box-shadow: 0 1px 3px rgba(60,64,67,0.12), 0 1px 2px rgba(60,64,67,0.08) !important;
  color: #3C4043 !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  font-weight: 600 !important;
  font-size: 0.94rem !important;
  letter-spacing: 0.01em !important;
  padding: 0 1.4rem !important;
  margin: 0 !important;
  cursor: pointer !important;
  opacity: 1 !important;
  transition: all 0.2s ease !important;
  position: relative !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.65rem !important;
}}
/* Logo Google injecté dans le vrai bouton (à gauche du texte) */
.gbtn-wrap .stButton > button::before {{
  content: "" !important;
  display: inline-block !important;
  width: 22px !important;
  height: 22px !important;
  flex-shrink: 0 !important;
  background-image: url('{_g_src}') !important;
  background-size: contain !important;
  background-repeat: no-repeat !important;
  background-position: center !important;
  pointer-events: none !important;
  vertical-align: middle !important;
}}
.gbtn-wrap .stButton > button:hover {{
  background: #F8F9FA !important;
  background-color: #F8F9FA !important;
  box-shadow: 0 8px 22px rgba(60,64,67,0.15), 0 0 0 3px rgba(66,133,244,0.12) !important;
  transform: translateY(-1px) !important;
  border-color: #DADCE0 !important;
  color: #3C4043 !important;
}}
.gbtn-wrap .stButton > button:active {{
  transform: translateY(0) !important;
  background: #F1F3F4 !important;
}}
.login-secure {{
  text-align: center;
  font-size: 0.72rem;
  color: #64748B !important;
  margin-top: 0.65rem;
  animation: fadeIn 0.85s 0.72s both;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
}}
.login-secure::before {{
  content: "";
  width: 8px; height: 8px; border-radius: 50%; background: #22C55E; display: inline-block;
}}
.login-foot {{
  text-align: center;
  font-size: 0.68rem;
  color: #64748B !important;
  margin-top: 1.2rem;
  animation: fadeIn 0.85s 0.78s both;
  letter-spacing: 0.02em;
}}
</style>
<div class="login-shell">
  <div class="login-shell-bg"></div>
  <div class="login-orb login-orb-1"></div>
  <div class="login-orb login-orb-2"></div>

  <div class="float-layer">
    <div class="float-card float-tl">
      <span class="fc-tag qlik">Qlik Sense</span>
      <div class="fc-title">Set Analysis &amp; Aggr</div>
      <p class="fc-body">Expressions Qlik extraites du script et des feuilles — base de la couverture fonctionnelle.</p>
    </div>
    <div class="float-card float-tr">
      <span class="fc-tag pbi">Power BI</span>
      <div class="fc-title">Mesures DAX live</div>
      <p class="fc-body">Valeurs réelles lues depuis Power BI Desktop — pas de saisie manuelle des KPI.</p>
    </div>
    <div class="float-card float-ml">
      <span class="fc-tag both">Qlik → PBI</span>
      <div class="fc-title">Réconciliation KPI</div>
      <p class="fc-body">Comparaison numérique Qlik vs DAX avec tolérance, cause probable et correctif.</p>
    </div>
    <div class="float-card float-mr">
      <span class="fc-tag pbi">DAX · IA</span>
      <div class="fc-title">Correctifs suggérés</div>
      <p class="fc-body">Génération de formules DAX alignées sur l&apos;écart détecté, avec score de confiance.</p>
    </div>
    <div class="float-card float-bl">
      <span class="fc-tag qlik">Migration</span>
      <div class="fc-title">Dette &amp; historique</div>
      <p class="fc-body">Constats persistants sur plusieurs runs — priorisation par criticité et ancienneté.</p>
    </div>
    <div class="float-card float-br">
      <span class="fc-tag both">Audit</span>
      <div class="fc-title">Score de santé</div>
      <p class="fc-body">Indicateur global de la migration : données, structure et couverture fonctionnelle.</p>
    </div>
  </div>

  <div class="login-center">
    {_login_logo_html}
    <div class="login-kicker">Audit de migration · Talan</div>
    <h1 class="login-title">De <span class="grad">Qlik Sense</span> vers Power BI</h1>
    <p class="login-sub">Réconciliation, couverture et plan d&apos;action — pilotez la migration avec des preuves mesurables.</p>
    <div class="login-pills">
      <span class="login-pill">Qlik Sense</span>
      <span class="login-pill">Power BI</span>
      <span class="login-pill">Réconciliation</span>
      <span class="login-pill">DAX · IA</span>
    </div>
    <div class="login-banner">
      <span class="status-badge"><span class="status-dot"></span></span>
      <span class="banner-tx"><strong>Service opérationnel</strong> — extraction live Qlik &amp; Power BI, alertes Gmail actives.</span>
    </div>
    <div class="login-card">
      <div class="login-card-title">Connexion sécurisée</div>
      <div class="login-card-sub">Compte Google professionnel · aucun mot de passe stocké.</div>
      <ul class="login-features">
        <li><span class="check">✓</span> OAuth 2.0 — jeton de session uniquement</li>
        <li><span class="check">✓</span> Alertes Gmail (bloquants, rapports, tendances)</li>
        <li><span class="check">✓</span> Usage interne · données confidentielles</li>
      </ul>
      <div class="login-divider">continuer avec</div>
      <div style="height:3.2rem;"></div>
    </div>
    <div class="login-foot">Talan · Qlik → Power BI · {datetime.date.today().year}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    _l, _c, _r = st.columns([1, 1.25, 1])
    with _c:
        # Un seul bouton réel : appelle st.login() et ressemble au bouton Google officiel
        st.markdown('<div class="google-login-btn-anchor"><div class="gbtn-wrap">', unsafe_allow_html=True)
        if st.button("Continuer avec Google", type="secondary", use_container_width=True, key="google_login_btn"):
            st.login()
        st.markdown(
            '</div></div>'
            '<div class="login-secure">Connexion chiffrée · aucun mot de passe enregistré</div>',
            unsafe_allow_html=True,
        )

    st.stop()

if not st.session_state.get("notify_to"):
    try:
        st.session_state["notify_to"] = st.user.email
    except Exception:
        pass



# ============================================================
# MODE PRÉSENTATION — court-circuite sidebar/header/pages normales
# ============================================================
_ref_for_presentation = f"QA-{datetime.date.today().strftime('%Y%m%d')}"
if st.session_state.get("presentation_mode"):
    render_presentation_mode(_ref_for_presentation)
    st.stop()

# ============================================================
# THÈME DYNAMIQUE — le fond reflète le niveau de risque de l'audit en cours
# ============================================================
_theme_findings = st.session_state.get("findings") or []
_risk_theme = risk_level(_theme_findings) if _theme_findings else None

_THEME_GRADIENTS = {
    "CRITIQUE": """
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(220,38,38,0.11) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(217,119,6,0.08) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(220,38,38,0.05) 0%, transparent 55%),
        linear-gradient(160deg, #FFF9F8 0%, #FEF2F2 40%, #FFF7ED 100%)
    """,
    "ÉLEVÉ": """
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(217,119,6,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(245,158,11,0.09) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(217,119,6,0.05) 0%, transparent 55%),
        linear-gradient(160deg, #FFFBF5 0%, #FEF3C7 35%, #FFF7ED 100%)
    """,
    "MODÉRÉ": """
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(217,119,6,0.08) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(37,99,235,0.08) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(217,119,6,0.04) 0%, transparent 55%),
        linear-gradient(160deg, #FAFBFC 0%, #FEF9EE 35%, #EEF2FF 100%)
    """,
    "FAIBLE": """
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(5,150,105,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(16,185,129,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(5,150,105,0.05) 0%, transparent 55%),
        linear-gradient(160deg, #F8FAFC 0%, #ECFDF5 40%, #F0FDF4 100%)
    """,
    "AUCUN": """
        radial-gradient(ellipse 120% 80% at 10% 20%, rgba(5,150,105,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 100% 70% at 90% 80%, rgba(16,185,129,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 50% 50%, rgba(5,150,105,0.05) 0%, transparent 55%),
        linear-gradient(160deg, #F8FAFC 0%, #ECFDF5 40%, #F0FDF4 100%)
    """,
}

if _risk_theme in _THEME_GRADIENTS:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {_THEME_GRADIENTS[_risk_theme]} !important;
            background-attachment: fixed;
            background-size: 140% 140%, 130% 130%, 110% 110%, 100% 100%;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# SIDEBAR
# ============================================================
today = datetime.date.today().strftime("%d %B %Y")
ref = f"QA-{datetime.date.today().strftime('%Y%m%d')}"

has_a = (
    st.session_state.get("module_a_reconciliation") is not None
    and isinstance(st.session_state.get("module_a_reconciliation"), pd.DataFrame)
    and not st.session_state.get("module_a_reconciliation").empty
)
has_b = bool(st.session_state.get("module_b_coverage"))
has_findings = bool(st.session_state.get("findings"))

progress_pct = 0
if has_a:
    progress_pct += 40
if has_b:
    progress_pct += 30
if has_findings:
    progress_pct += 30

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=150)
    else:
        st.markdown(
            """
            <div style="font-family:'Source Serif 4',serif; font-size:1.5rem; font-weight:700; color:#F8FAFC; letter-spacing:-0.02em; padding:0.3rem 0;">
                TALAN
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div style="padding: 0.4rem 0 0.9rem 0;">
            <div style="font-size: 0.65rem; letter-spacing: 0.14em; text-transform: uppercase; color: #64748B; font-weight: 600;">
                Audit de migration
            </div>
            <div style="font-family: 'Source Serif 4', serif; font-size: 1.15rem; font-weight: 700; color: #F8FAFC; margin-top: 0.15rem; letter-spacing: -0.02em;">
                Qlik → Power BI
            </div>
            <div style="font-size: 0.72rem; color: #64748B; margin-top: 0.3rem;">
                Réf. <strong style="color:#94A3B8;">{ref}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown("**Progression globale**")
    st.markdown(
        f"""
        <div class="progress-track">
            <div class="progress-fill" style="width:{progress_pct}%;"></div>
        </div>
        <div style="font-size:0.72rem; color:#94A3B8; margin-bottom:0.6rem;">{progress_pct}% complété</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="sidebar-status">
            <span class="dot {'dot-ok' if has_a else 'dot-wait'}"></span>
            Réconciliation {'terminée' if has_a else 'en attente'}
        </div>
        <div class="sidebar-status">
            <span class="dot {'dot-ok' if has_b else 'dot-wait'}"></span>
            Couverture {'terminée' if has_b else 'en attente'}
        </div>
        <div class="sidebar-status">
            <span class="dot {'dot-ok' if has_findings else 'dot-wait'}"></span>
            Rapport consolidé {'prêt' if has_findings else 'en attente'}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    if st.button("Mode présentation client", key="enter_presentation_mode", help="Affichage plein écran pour réunion — score de santé et plan d'action, sans sidebar ni détails techniques."):
        st.session_state["presentation_mode"] = True
        st.rerun()

    st.markdown("---")
    st.markdown("**Navigation**")

    pages = {
        "00": "00  Vue d'ensemble",
        "01": "01  Import & Extraction",
        "02": "02  Réconciliation",
        "03": "03  Couverture fonctionnelle",
        "04": "04  Rapport consolidé",
        "05": "05  Suivi historique",
        "06": "06  Assistant Q&A",
        "07": "07  Impact business",
        "08": "08  Plan d'action",
    }

    for key, label in pages.items():
        is_active = st.session_state.current_page == key
        if st.button(label, key=f"nav_{key}", type="primary" if is_active else "secondary"):
            st.session_state.current_page = key
            st.rerun()

    st.markdown("---")
    st.markdown("**Session**")
    st.markdown(
        f"""
        <div class="sidebar-status">
            <span class="dot dot-ok"></span>
            {user_greeting()}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Se déconnecter", key="google_logout_btn"):
        st.logout()

    st.markdown("---")
    st.markdown("**Alertes email**")
    _alert_cfg = st.session_state.get("alert_settings", {"bloquant": True, "rapport": True, "dette": True, "tendance": True})
    _alert_cfg["bloquant"] = st.checkbox(
        "Nouveau constat bloquant", value=_alert_cfg.get("bloquant", True), key="alert_bloquant_cb"
    )
    _alert_cfg["rapport"] = st.checkbox(
        "Rapport généré", value=_alert_cfg.get("rapport", True), key="alert_rapport_cb"
    )
    _alert_cfg["dette"] = st.checkbox(
        "Dette de migration", value=_alert_cfg.get("dette", True), key="alert_dette_cb"
    )
    _alert_cfg["tendance"] = st.checkbox(
        "Tendance négative (score, couverture)", value=_alert_cfg.get("tendance", True), key="alert_tendance_cb",
        help="Chute du score de santé vs le run précédent, ou couverture qui régresse sur 2+ runs consécutifs.",
    )
    st.session_state["alert_settings"] = _alert_cfg
    notify_to_val = st.text_input(
        "Envoyer les alertes à",
        value=st.session_state.get("notify_to") or st.user.email,
        key="notify_to_input",
        help="Par défaut, ton propre compte Gmail connecté.",
    )
    st.session_state["notify_to"] = notify_to_val

    st.markdown("---")
    st.caption(f"Tolérance · {SEUIL_TOLERANCE:.0%}")
    st.caption(today)

# ============================================================
# HEADER
# ============================================================
logo_html = ""
if LOGO_PATH.exists():
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:38px;margin-right:1.1rem;vertical-align:middle;" alt="Talan">'

_greeting = user_greeting()

st.markdown(
    f"""
<div class="doc-header">
  <div class="header-accent"></div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:0.55rem;">
    <div style="display:flex;align-items:center;gap:0.8rem;">
      {logo_html}
      <div>
        <div class="kicker">Audit de migration · Document confidentiel · Talan</div>
        <h1 style="margin:0!important;font-size:1.85rem!important;">Qlik Sense vers Power BI</h1>
      </div>
    </div>
    <div style="text-align:right;padding-left:1rem;">
      <div style="font-size:0.68rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-soft);margin-bottom:0.25rem;">
        Session active
      </div>
      <div style="font-family:'Source Serif 4',serif;font-size:1.25rem;font-weight:600;color:var(--ink);letter-spacing:-0.01em;">
        {_greeting}
      </div>
    </div>
  </div>
  <div class="meta">
    <div>Référence <strong>{ref}</strong></div>
    <div>Date <strong>{today}</strong></div>
    <div>Statut <strong>En cours</strong></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# PAGES
# ============================================================
page = st.session_state.current_page

# ----------------------------------------------------------
# 00 — VUE D'ENSEMBLE
# ----------------------------------------------------------
if page == "00":
    section(
        "00",
        "Vue d'ensemble",
        "Point d'entrée de l'audit — statut de chaque étape, action recommandée, "
        "et aperçu des runs précédents s'il y en a.",
    )

    col_as_l, col_as_r = st.columns([3, 1])
    with col_as_l:
        st.markdown(
            """
            <div style="font-size:0.9rem;color:var(--ink-soft);line-height:1.55;padding-top:0.35rem;">
              Un assistant est disponible pour interroger les constats de l'audit
              en langage naturel — réponses basées uniquement sur tes données.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_as_r:
        if st.button("Ouvrir l'assistant", type="primary", use_container_width=True, key="open_qa_home"):
            st.session_state.current_page = "06"
            st.rerun()

    current_findings = st.session_state.get("findings") or []
    mb_overview = st.session_state.get("module_b_coverage")
    cov_rate_overview = mb_overview.get("coverage_rate") if mb_overview else None
    health_overview = (
        compute_health_score(to_finding_objects(current_findings), cov_rate_overview)
        if compute_health_score is not None and current_findings else {}
    )
    has_extraction_overview = bool(st.session_state.get("qlik_extraction")) and bool(st.session_state.get("pbi_extraction"))

    # --- Pipeline visuel des 4 grandes étapes ---
    stages = [
        ("Extraction", has_extraction_overview),
        ("Réconciliation", has_a),
        ("Couverture", has_b),
        ("Rapport", has_findings),
    ]
    current_idx = next((i for i, (_, done) in enumerate(stages) if not done), len(stages))
    stepper_html = '<div class="stepper">'
    for i, (label, done) in enumerate(stages):
        if done:
            circle_cls, circle_content = "done", "✓"
        elif i == current_idx:
            circle_cls, circle_content = "current", str(i + 1)
        else:
            circle_cls, circle_content = "pending", str(i + 1)
        label_cls = "" if (done or i == current_idx) else "pending"
        stepper_html += (
            f'<div class="step"><div class="step-circle {circle_cls}">{circle_content}</div>'
            f'<div class="step-label {label_cls}">{label}</div></div>'
        )
        if i < len(stages) - 1:
            stepper_html += f'<div class="step-connector {"done" if done else ""}"></div>'
    stepper_html += "</div>"
    st.markdown(stepper_html, unsafe_allow_html=True)

    # --- Action recommandée ---
    if not has_a and not has_b:
        next_title = "Commencer l'audit"
        next_text = "Aucune extraction n'a encore été faite. Importe le rapport Qlik (.qvf) et son équivalent Power BI (.pbix) pour démarrer."
        next_target, next_label = "01", "Aller à l'import & extraction"
    elif has_a and not has_b:
        next_title = "Poursuivre l'audit"
        next_text = "La réconciliation des données est faite. Lance maintenant l'analyse de couverture fonctionnelle pour compléter le diagnostic."
        next_target, next_label = "03", "Aller à la couverture fonctionnelle"
    elif (has_a or has_b) and not has_findings:
        next_title = "Générer le rapport"
        next_text = "Les données sont prêtes. Génère le rapport consolidé pour obtenir le score de santé et la liste priorisée des constats."
        next_target, next_label = "04", "Générer le rapport consolidé"
    else:
        niveau_actuel = risk_level(current_findings)
        next_title = "Audit disponible"
        next_text = f"Le rapport consolidé est prêt — niveau de risque {niveau_actuel}. Consulte le détail, pose une question à l'assistant, ou exporte le livrable client."
        next_target, next_label = "04", "Voir le rapport consolidé"

    st.markdown(
        f"""
        <div class="card">
            <div style="font-size:0.68rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--ink-soft); font-weight:600; margin-bottom:0.3rem;">
                Action recommandée
            </div>
            <div style="font-family:'Source Serif 4',serif; font-size:1.25rem; font-weight:700; color:var(--ink); margin-bottom:0.4rem;">
                {next_title}
            </div>
            <div style="font-size:0.9rem; color:var(--ink-soft); line-height:1.55; max-width:70ch;">
                {next_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(next_label, type="primary", key="nav_next_action"):
        st.session_state.current_page = next_target
        st.rerun()

    # --- Dette de migration (aperçu) ---
    dette_count, dette_bloquant = 0, 0
    if history_detect_stalled is not None:
        stalled_preview = history_detect_stalled(min_runs=3)
        dette_count = len(stalled_preview)
        dette_bloquant = sum(1 for f in stalled_preview if f.get("criticite") == "BLOQUANT")

    # --- Carte hero : score de santé mis en avant ---
    if health_overview.get("score") is not None:
        score_val = health_overview["score"]
        niveau_val = health_overview.get("niveau", "—")
        score_color = "var(--ok)" if score_val >= 70 else "var(--warn)" if score_val >= 40 else "var(--danger)"
        st.markdown(
            f"""
            <div class="impact-hero">
              <div>
                <div class="impact-figure" style="color:{score_color};">{score_val}/100</div>
                <div class="impact-label">Score de santé ({niveau_val})</div>
              </div>
              <div class="impact-sub">
                <strong>{len(current_findings)}</strong> constat(s) au total.
                {f"<strong>{dette_count}</strong> constat(s) en dette de migration (dont <strong>{dette_bloquant}</strong> bloquant(s)), non résolus depuis au moins 3 runs." if dette_count else "Aucun constat en dette détecté sur les runs récents."}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --- Alertes de tendance (en plus des alertes ponctuelles de la section 04) ---
        trend_alerts_overview = detect_trend_alerts(score_val, cov_rate_overview)
        if trend_alerts_overview:
            render_trend_alerts(trend_alerts_overview)

    # --- Statut détaillé ---
    st.markdown("**Statut de l'audit en cours**")
    hist_df_for_count = history_load_df() if history_load_df is not None else None
    n_runs_overview = len(hist_df_for_count) if hist_df_for_count is not None else 0
    st.markdown(stat_grid([
        ("Réconciliation", "faite" if has_a else "en attente", "ok" if has_a else "neutral"),
        ("Couverture", "faite" if has_b else "en attente", "ok" if has_b else "neutral"),
        ("Constats", len(current_findings), "neutral" if not current_findings else "danger" if any(f.get("criticite") == "BLOQUANT" for f in current_findings) else "warn"),
        ("Runs enregistrés", n_runs_overview, "neutral"),
    ]), unsafe_allow_html=True)

    # --- Constats les plus critiques ---
    if current_findings:
        ordre_overview = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
        top_findings = sorted(current_findings, key=lambda x: ordre_overview.get(x.get("criticite"), 3))[:5]
        st.markdown("**Constats les plus critiques**")
        for f in top_findings:
            st.markdown(
                f"{crit_tag(f.get('criticite', 'MINEUR'))} &nbsp; **{f.get('libelle', '')}** "
                f"&nbsp;·&nbsp; <span style='color:var(--ink-soft); font-size:0.85rem;'>{f.get('source_module', '')}</span>",
                unsafe_allow_html=True,
            )
        if len(current_findings) > 5:
            st.caption(f"+ {len(current_findings) - 5} autre(s) constat(s) — voir la section 04 pour le détail complet.")

    # --- Graphiques côte à côte : évolution + répartition ---
    if hist_df_for_count is not None and not hist_df_for_count.empty:
        st.markdown("**Évolution récente**")
        hist_df_overview = hist_df_for_count.copy()
        hist_df_overview["timestamp_dt"] = pd.to_datetime(hist_df_overview["timestamp"])
        chart_df_overview = hist_df_overview.set_index("timestamp_dt")

        gcol1, gcol2 = st.columns(2)
        with gcol1:
            st.caption("Score de santé")
            render_health_score_chart(chart_df_overview)
        with gcol2:
            st.caption("Constats par criticité")
            render_severity_chart(chart_df_overview)

    # --- Raccourcis rapides ---
    st.markdown("**Raccourcis**")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        if st.button("Assistant Q&A", key="shortcut_qa"):
            st.session_state.current_page = "06"
            st.rerun()
    with sc2:
        if st.button("Impact business", key="shortcut_business"):
            st.session_state.current_page = "07"
            st.rerun()
    with sc3:
        if st.button("Suivi historique", key="shortcut_history"):
            st.session_state.current_page = "05"
            st.rerun()
    with sc4:
        if st.button("Présentation", key="shortcut_presentation"):
            st.session_state["presentation_mode"] = True
            st.rerun()

# ----------------------------------------------------------
# 01 — IMPORT & EXTRACTION
# ----------------------------------------------------------
elif page == "01":
    section(
        "01",
        "Import et extraction",
        "Charge le rapport Qlik et son équivalent Power BI. Les valeurs réelles "
        "sont lues directement dans les deux moteurs — aucune saisie manuelle.",
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        qlik_file = st.file_uploader(
            "Rapport Qlik (.qvf)", type=["qvf"], key="qlik_main",
            help="Qlik Sense Desktop doit être ouvert avec ce fichier chargé.",
        )
    with col2:
        pbi_file = st.file_uploader(
            "Rapport Power BI (.pbix)", type=["pbix", "pbit"], key="pbi_main",
            help="Power BI Desktop doit être ouvert avec ce fichier chargé.",
        )
    st.caption(f"Tolérance relative appliquée aux écarts numériques : **{SEUIL_TOLERANCE:.0%}**.")
    st.markdown("</div>", unsafe_allow_html=True)

    if qlik_file and pbi_file:
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        if st.button("Extraire et réconcilier", type="primary"):
            with st.spinner("Extraction en cours..."):
                _t0_extraction = time.time()
                try:
                    qlik_path = temp_dir / qlik_file.name
                    qlik_path.write_bytes(qlik_file.getvalue())
                    qlik_result = QlikExtractor().extract_from_file(str(qlik_path.resolve()))
                    st.session_state["qlik_extraction"] = qlik_result

                    pbi_path = temp_dir / pbi_file.name
                    pbi_path.write_bytes(pbi_file.getvalue())
                    pbi_result = PBIExtractor().extract_from_file(str(pbi_path.resolve()))
                    st.session_state["pbi_extraction"] = pbi_result

                    st.markdown(stat_grid([
                        ("Feuilles Qlik", len(qlik_result.get("sheets", [])), "neutral"),
                        ("KPIs Qlik", len(qlik_result.get("kpis", [])), "neutral"),
                        ("Pages PBI", len(pbi_result.get("pages", [])), "neutral"),
                        ("Mesures DAX", len(pbi_result.get("dax_measures", [])), "neutral"),
                    ]), unsafe_allow_html=True)

                    live = (pbi_result.get("metadata", {}) or {}).get("source", "")
                    if "live" in live:
                        st.success("Extraction en direct réussie — valeurs réelles des mesures DAX.")
                    else:
                        st.warning(
                            "Power BI Desktop n'a pas pu être atteint : structure extraite du "
                            "fichier, sans valeurs réelles. Ouvre le .pbix dans Power BI Desktop "
                            "et relance pour des valeurs exactes."
                        )

                    with st.expander("Détail de l'extraction"):
                        st.write("**KPIs Qlik**")
                        for k in qlik_result.get("kpis", []):
                            st.write(f"- {k.get('name', '')} = `{k.get('value')}` (feuille {k.get('sheet', '')})")
                        st.write("**Mesures Power BI**")
                        for k in pbi_result.get("kpis") or []:
                            err = " — en erreur" if k.get("error") else ""
                            st.write(f"- {k.get('name')} = `{k.get('value')}`{err}")
                            if k.get("error"):
                                st.caption(k["error"])

                    rec_df = reconcile_kpis(qlik_result, pbi_result)
                    st.session_state["module_a_reconciliation"] = rec_df
                    st.session_state["findings"] = findings_from_reconciliation(rec_df)

                    if detect_structural_gaps is not None:
                        structural = detect_structural_gaps(qlik_result, pbi_result)
                        st.session_state["structural_findings"] = structural
                        st.session_state["findings"] = st.session_state["findings"] + structural

                    # --- Impact business : temps réel mesuré (pas une estimation) ---
                    st.session_state["timing_extraction_sec"] = time.time() - _t0_extraction
                    st.session_state["timing_kpis_reconcilies"] = len(rec_df) if rec_df is not None else 0

                    st.success("Extraction terminée. Redirection vers la réconciliation…")
                    st.session_state.current_page = "02"
                    st.rerun()

                except Exception as e:
                    st.error(f"Erreur d'extraction : {e}")
                    st.code(traceback.format_exc())
    else:
        st.info("Chargez un fichier **.qvf** et un fichier **.pbix** pour lancer l'extraction.")

# ----------------------------------------------------------
# 02 — RÉCONCILIATION
# ----------------------------------------------------------
elif page == "02":
    rec_df = st.session_state.get("module_a_reconciliation")
    has_a = rec_df is not None and isinstance(rec_df, pd.DataFrame) and not rec_df.empty
    qlik_result = st.session_state.get("qlik_extraction") or {}
    pbi_result = st.session_state.get("pbi_extraction") or {}

    section(
        "02",
        "Réconciliation des données",
        "Écarts numériques entre KPIs Qlik et mesures Power BI, avec cause "
        "probable et correction suggérée pour chaque écart.",
    )

    if not has_a:
        st.warning("Aucune extraction disponible. Lancez d'abord la section **01 · Import & Extraction**.")
        if st.button("← Aller à l'extraction"):
            st.session_state.current_page = "01"
            st.rerun()
    else:
        n_match = int((rec_df["statut"] == "MATCH_VALUE").sum())
        n_ecart = int((rec_df["statut"] == "ECART_VALEUR").sum())
        n_err = int((rec_df["statut"] == "ERREUR_PBI").sum())
        n_miss_p = int((rec_df["statut"] == "MANQUANT_PBI").sum())
        n_miss_q = int((rec_df["statut"] == "MANQUANT_QLIK").sum())

        st.markdown(stat_grid([
            ("Correspondances", n_match, "ok"),
            ("Écarts de valeur", n_ecart, "danger"),
            ("Mesures en erreur", n_err, "danger"),
            ("Manquants PBI", n_miss_p, "warn"),
            ("Manquants Qlik", n_miss_q, "neutral"),
        ]), unsafe_allow_html=True)

        cols_show = [c for c in ["kpi", "kpi_pbi", "valeur_qlik", "valeur_pbi", "statut", "criticite", "match_type", "match_score"] if c in rec_df.columns]
        st.dataframe(rec_df[cols_show], width="stretch")

        st.markdown("**Écarts et corrections suggérées**")
        show_ecarts(rec_df)

        structural = st.session_state.get("structural_findings") or []
        if structural:
            st.markdown("**Écarts structurels — visuels et dimensions**")
            st.caption(
                "Dimensions Qlik sans colonne Power BI correspondante, pages avec moins de "
                "visuels que leur feuille source, colonnes au nom malformé."
            )
            for f in structural:
                with st.expander(f["libelle"]):
                    st.markdown(crit_tag(f["criticite"]), unsafe_allow_html=True)
                    st.write(f"**Détail :** {f['detail']}")
                    st.write(f"**Diagnostic :** {f['diagnostic']}")
                    st.write(f"**Recommandation :** {f['recommandation']}")

        st.download_button(
            "Télécharger le détail (Excel)",
            data=export_module_a_excel(rec_df, qlik_result, pbi_result),
            file_name=f"reconciliation_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_module_a",
        )

# ----------------------------------------------------------
# 03 — COUVERTURE
# ----------------------------------------------------------
elif page == "03":
    section(
        "03",
        "Couverture fonctionnelle",
        "Fonctionnalités du script Qlik (Set Analysis, ApplyMap, agrégations "
        "imbriquées...) sans équivalent DAX identifié dans le modèle Power BI.",
    )

    qlik_live = st.session_state.get("qlik_extraction")
    pbi_live = st.session_state.get("pbi_extraction")
    has_live = bool(qlik_live) and bool(pbi_live)

    with st.expander("Source des données", expanded=not has_live):
        source = st.radio(
            "Origine du script et des mesures",
            ["Extraction de la section 01", "Fichiers séparés"],
            index=0 if has_live else 1,
            horizontal=True,
            label_visibility="collapsed",
        )

        qlik_content = expr_content = dax_content = None
        dax_measures_struct = None
        power_query_struct = []
        roles_struct = []

        if source.startswith("Extraction"):
            if not has_live:
                st.warning("Aucune extraction en mémoire — lancez d'abord la section 01, ou choisissez « Fichiers séparés ».")
            else:
                qlik_content = qlik_live.get("script", "") or ""
                expr_content = build_qlik_expressions_text(qlik_live)
                dax_measures_struct = pbi_live.get("dax_measures", []) or []
                power_query_struct = pbi_live.get("power_query", []) or []
                roles_struct = pbi_live.get("roles", []) or []
                st.caption(
                    f"Script Qlik : {len(qlik_content.splitlines())} ligne(s) · "
                    f"Mesures DAX : {len(dax_measures_struct)} · "
                    f"Requêtes Power Query : {len(power_query_struct)} · "
                    f"Rôles RLS : {len(roles_struct)}"
                )
        else:
            b1, b2 = st.columns(2)
            with b1:
                qlik_script_file = st.file_uploader("Script Qlik (.qvs)", type=["qvs", "txt"], key="qlik_script")
            with b2:
                qlik_expr_file = st.file_uploader("Expressions visuels (.txt)", type=["txt"], key="qlik_expr")
            dax_measures_file = st.file_uploader(
                "Mesures DAX (.txt, format « # Mesure : Nom »)", type=["txt", "dax"], key="dax_measures"
            )
            if qlik_script_file:
                qlik_content = qlik_script_file.read().decode("utf-8")
            if qlik_expr_file:
                expr_content = qlik_expr_file.read().decode("utf-8")
            if dax_measures_file:
                dax_content = dax_measures_file.read().decode("utf-8")

    if st.button("Lancer l'analyse de couverture", type="primary"):
        if analyze_coverage_quick is None:
            st.error("Module de couverture indisponible.")
        elif not qlik_content:
            st.warning("Aucun script Qlik disponible.")
        elif dax_measures_struct is None and not dax_content:
            st.warning("Aucune mesure DAX disponible.")
        else:
            with st.spinner("Analyse en cours..."):
                _t0_coverage = time.time()
                try:
                    measures_for_analysis = (
                        dax_measures_struct if dax_measures_struct is not None else parse_dax_measures_text(dax_content)
                    )
                    results = analyze_coverage_quick(
                        qlik_content, expr_content or "", measures_for_analysis, power_query_struct, roles_struct
                    )
                    if results.get("error"):
                        st.error(results["error"])
                    else:
                        st.session_state["module_b_coverage"] = results
                        st.session_state["timing_coverage_sec"] = time.time() - _t0_coverage
                        st.success("Analyse terminée.")
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

    module_b_results = st.session_state.get("module_b_coverage")
    if module_b_results:
        st.markdown(stat_grid([
            ("Patterns détectés", module_b_results.get("total_patterns", 0), "neutral"),
            ("Couverts", module_b_results.get("covered", 0), "ok"),
            ("Partiels", module_b_results.get("partially_covered", 0), "warn"),
            ("Non couverts", module_b_results.get("not_covered", 0), "danger"),
            ("Taux", f"{module_b_results.get('coverage_rate', 0):.0f}%", "neutral"),
        ]), unsafe_allow_html=True)

        if module_b_results.get("details"):
            st.dataframe(pd.DataFrame(module_b_results["details"]), width="stretch")

        if module_b_results.get("findings"):
            existing = st.session_state.get("findings") or []
            new_b_findings = module_b_results["findings"]
            already_in = {f.get("libelle") for f in existing if f.get("source_module") == "Module B - Functional Coverage"}
            to_add = [f for f in new_b_findings if f.get("libelle") not in already_in]
            st.session_state["findings"] = existing + to_add
    else:
        st.caption("Aucune analyse de couverture générée pour l'instant.")

# ----------------------------------------------------------
# 04 — RAPPORT CONSOLIDÉ
# ----------------------------------------------------------
elif page == "04":
    section(
        "04",
        "Rapport consolidé",
        "Fusion des écarts de données et des lacunes fonctionnelles en un rapport "
        "unique, trié par criticité, prêt pour la revue d'un consultant.",
    )

    has_a = (
        st.session_state.get("module_a_reconciliation") is not None
        and isinstance(st.session_state.get("module_a_reconciliation"), pd.DataFrame)
        and not st.session_state.get("module_a_reconciliation").empty
    )
    has_b = bool(st.session_state.get("module_b_coverage"))
    findings = st.session_state.get("findings") or []
    rec_df = st.session_state.get("module_a_reconciliation")
    qlik_result = st.session_state.get("qlik_extraction") or {}
    pbi_result = st.session_state.get("pbi_extraction") or {}

    st.markdown(stat_grid([
        ("Réconciliation", "faite" if has_a else "en attente", "ok" if has_a else "neutral"),
        ("Couverture", "faite" if has_b else "en attente", "ok" if has_b else "neutral"),
        ("Constats", len(findings), "neutral"),
    ]), unsafe_allow_html=True)

    if st.button("Générer le rapport consolidé", type="primary", disabled=not (has_a or has_b)):
        findings_a = findings_from_reconciliation(rec_df) if has_a else []
        findings_a = findings_a + (st.session_state.get("structural_findings") or [])
        findings_b = st.session_state["module_b_coverage"].get("findings") or [] if has_b else []

        if orchestrator_merge_findings is not None:
            merged_typed = orchestrator_merge_findings(findings_a, findings_b)
            merged = [
                {
                    "source_module": f.source_module, "libelle": f.libelle, "detail": f.detail,
                    "criticite": f.criticite, "diagnostic": f.diagnostic,
                    "recommandation": f.recommandation, "statut": f.statut,
                }
                for f in merged_typed
            ]
        else:
            merged = findings_a + findings_b

        st.session_state["findings"] = merged
        findings = merged
        st.success(f"Rapport généré — {len(findings)} constat(s).")

        # --- Historique : snapshot automatique de ce run ---
        mb_for_history = st.session_state.get("module_b_coverage")
        coverage_rate_for_history = mb_for_history.get("coverage_rate") if mb_for_history else None
        health_for_history = (
            compute_health_score(to_finding_objects(findings), coverage_rate_for_history)
            if compute_health_score is not None else {}
        )

        # --- Alertes de tendance : comparaison avec l'historique AVANT de
        # sauvegarder ce run (sinon le run courant se comparerait à lui-même) ---
        trend_alerts = detect_trend_alerts(health_for_history.get("score"), coverage_rate_for_history)
        if trend_alerts:
            st.markdown("**Alertes de tendance**")
            render_trend_alerts(trend_alerts)

        if history_save_run is not None:
            try:
                history_save_run(
                    reference=ref,
                    findings=findings,
                    coverage_rate=coverage_rate_for_history,
                    health_score=health_for_history.get("score"),
                    health_niveau=health_for_history.get("niveau"),
                )
                st.caption("Ce run a été ajouté à l'historique — voir section 06.")
            except Exception as e:
                st.caption(f"⚠️ Historique non sauvegardé : {e}")

        # --- Notifications email (Gmail, compte Google connecté) ---
        if getattr(st.user, "is_logged_in", False):
            alert_cfg = st.session_state.get("alert_settings", {})
            bloquant_now = [f for f in findings if f.get("criticite") == "BLOQUANT"]
            majeur_now = [f for f in findings if f.get("criticite") == "MAJEUR"]
            mineur_now = [f for f in findings if f.get("criticite") == "MINEUR"]
            prev_bloquant_libelles = st.session_state.get("last_bloquant_libelles", set())
            new_bloquant = [f for f in bloquant_now if f.get("libelle") not in prev_bloquant_libelles]

            if alert_cfg.get("bloquant") and new_bloquant and email_new_bloquant is not None:
                try:
                    send_notification(
                        f"[{ref}] {len(new_bloquant)} nouveau(x) constat(s) BLOQUANT",
                        email_new_bloquant(ref, new_bloquant),
                    )
                    st.caption(f"Alerte envoyée : {len(new_bloquant)} nouveau(x) constat(s) bloquant(s).")
                except Exception as e:
                    st.caption(f"⚠️ Échec envoi alerte bloquant : {e}")

            if alert_cfg.get("rapport") and email_report_generated is not None:
                try:
                    send_notification(
                        f"[{ref}] Rapport consolidé généré",
                        email_report_generated(
                            ref, len(findings), len(bloquant_now), len(majeur_now), len(mineur_now),
                            health_for_history.get("score"), health_for_history.get("niveau"),
                        ),
                    )
                    st.caption("Notification de rapport envoyée.")
                except Exception as e:
                    st.caption(f"⚠️ Échec envoi notification rapport : {e}")

            if alert_cfg.get("dette") and history_detect_stalled is not None and email_dette_migration is not None:
                stalled_for_alert = history_detect_stalled(min_runs=3)
                if stalled_for_alert:
                    try:
                        send_notification(
                            f"[{ref}] Dette de migration détectée",
                            email_dette_migration(ref, stalled_for_alert),
                        )
                        st.caption(f"Alerte dette envoyée : {len(stalled_for_alert)} constat(s) persistants.")
                    except Exception as e:
                        st.caption(f"⚠️ Échec envoi alerte dette : {e}")

            # --- Alerte de tendance : score qui chute / couverture qui régresse ---
            if alert_cfg.get("tendance") and trend_alerts:
                try:
                    send_notification(
                        f"[{ref}] Alerte de tendance",
                        email_trend_alert_html(ref, trend_alerts),
                    )
                    st.caption(f"Alerte de tendance envoyée : {len(trend_alerts)} signal(aux).")
                except Exception as e:
                    st.caption(f"⚠️ Échec envoi alerte tendance : {e}")

            st.session_state["last_bloquant_libelles"] = {f.get("libelle") for f in bloquant_now}

    if findings:
        niveau = risk_level(findings)
        stamp_style = {
            "CRITIQUE": "var(--danger)", "ÉLEVÉ": "var(--warn)",
            "MODÉRÉ": "var(--warn)", "FAIBLE": "var(--ok)", "AUCUN": "var(--ok)",
        }.get(niveau, "var(--brass)")
        stamp_class = "stamp stamp-critical" if niveau == "CRITIQUE" else "stamp"

        st.markdown(
            f"""
            <div class="stamp-row">
              <div class="{stamp_class}" style="border-color:{stamp_style};">
                <span style="color:{stamp_style};">Risque<br/>{niveau}</span>
              </div>
              <div style="flex:1;">
            """,
            unsafe_allow_html=True,
        )
        if generate_executive_summary is not None:
            st.markdown(generate_executive_summary(to_finding_objects(findings)))
        st.markdown("</div></div>", unsafe_allow_html=True)

        bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
        majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
        mineur = sum(1 for f in findings if f.get("criticite") == "MINEUR")

        stats_row = [
            ("Bloquants", bloquant, "danger"),
            ("Majeurs", majeur, "warn"),
            ("Mineurs", mineur, "neutral"),
        ]
        if compute_health_score is not None:
            mb = st.session_state.get("module_b_coverage")
            coverage_rate_val = mb.get("coverage_rate") if mb else None
            health = compute_health_score(to_finding_objects(findings), coverage_rate_val)
            style = {"EXCELLENT": "ok", "BON": "ok", "MOYEN": "warn", "CRITIQUE": "danger"}.get(health["niveau"], "neutral")
            stats_row.append((f"Score de santé ({health['niveau']})", f"{health['score']}/100", style))

        st.markdown(stat_grid(stats_row), unsafe_allow_html=True)

        st.markdown("**Détail des constats**")
        ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
        for f in sorted(findings, key=lambda x: ordre.get(x.get("criticite"), 3)):
            with st.expander(f["libelle"]):
                st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                st.write(f"**Origine :** {f.get('source_module', '')}")
                st.write(f"**Détail :** {f.get('detail', '')}")
                st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")
                if f.get("recommandation"):
                    st.write(f"**Recommandation :** {f.get('recommandation')}")

        report_data = {
            "date": datetime.datetime.now().isoformat(), "reference": ref,
            "total_findings": len(findings), "bloquant": bloquant, "majeur": majeur,
            "mineur": mineur, "findings": findings,
        }
        dl1, dl2, dl3, dl4 = st.columns(4)
        with dl1:
            st.download_button(
                "Export JSON", data=json.dumps(report_data, indent=2, ensure_ascii=False),
                file_name=f"audit_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json", key="dl_audit_json",
            )
        with dl2:
            if orchestrator_generate_report is not None:
                mb = st.session_state.get("module_b_coverage")
                cov_rate = mb.get("coverage_rate") if mb else None
                markdown_report = orchestrator_generate_report(to_finding_objects(findings), cov_rate)
                st.download_button(
                    "Export Markdown", data=markdown_report,
                    file_name=f"audit_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md",
                    mime="text/markdown", key="dl_audit_md",
                )
        with dl3:
            if has_a:
                st.download_button(
                    "Export Excel", data=export_module_a_excel(rec_df, qlik_result, pbi_result),
                    file_name=f"audit_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_audit_xlsx",
                )
        with dl4:
            if generate_word_report is not None:
                mb = st.session_state.get("module_b_coverage")
                cov_rate = mb.get("coverage_rate") if mb else None
                health_for_word = (
                    compute_health_score(to_finding_objects(findings), cov_rate)
                    if compute_health_score is not None else {}
                )

                # --- Impact business : mêmes hypothèses par défaut que la page 08,
                # calculées ici pour que l'export Word fonctionne même sans être
                # passé par cette page au préalable. ---
                business_impact = None
                timing_extraction = st.session_state.get("timing_extraction_sec")
                if timing_extraction is not None:
                    timing_coverage = st.session_state.get("timing_coverage_sec") or 0
                    n_kpis_bi = st.session_state.get("timing_kpis_reconcilies") or 0
                    temps_auto_min_bi = (timing_extraction + timing_coverage) / 60
                    min_par_kpi_default, min_par_constat_default, taux_horaire_default = 10, 15, 70
                    temps_manuel_min_bi = (n_kpis_bi * min_par_kpi_default) + (len(findings) * min_par_constat_default)
                    gain_min_bi = max(0, temps_manuel_min_bi - temps_auto_min_bi)
                    gain_pct_bi = (gain_min_bi / temps_manuel_min_bi * 100) if temps_manuel_min_bi > 0 else 0
                    business_impact = {
                        "n_kpis": n_kpis_bi,
                        "temps_auto_min": temps_auto_min_bi,
                        "temps_manuel_min": temps_manuel_min_bi,
                        "gain_min": gain_min_bi,
                        "gain_pct": gain_pct_bi,
                        "cout_gagne": (gain_min_bi / 60) * taux_horaire_default,
                        "taux_horaire": taux_horaire_default,
                    }

                word_bytes = generate_word_report(
                    reference=ref,
                    findings=findings,
                    coverage_rate=cov_rate,
                    health_score=health_for_word.get("score"),
                    health_niveau=health_for_word.get("niveau"),
                    logo_path=LOGO_PATH if LOGO_PATH.exists() else None,
                    date_str=today,
                    business_impact=business_impact,
                    qa_history=st.session_state.get("qa_history"),
                )
                st.download_button(
                    "Export Word", data=word_bytes,
                    file_name=f"audit_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_audit_docx",
                )
                if business_impact is None:
                    st.caption("Astuce : lance l'extraction (section 01) pour inclure l'impact business dans le rapport.")
            else:
                st.caption("Module Word indisponible")
    else:
        st.caption("Générez le rapport une fois la réconciliation et/ou la couverture terminées.")

# ----------------------------------------------------------
# 05 — SUIVI HISTORIQUE
# ----------------------------------------------------------
elif page == "05":
    section(
        "05",
        "Suivi historique",
        "Évolution du score de santé et des constats à travers les runs d'audit "
        "successifs — pour piloter une migration Qlik → Power BI dans la durée, "
        "et pas seulement faire un contrôle ponctuel.",
    )

    if history_load_df is None:
        st.error("Module de suivi historique indisponible.")
    else:
        hist_df = history_load_df()

        if hist_df.empty:
            st.info(
                "Aucun run enregistré pour l'instant. Génère un rapport consolidé "
                "(section 04 · **Générer le rapport consolidé**) pour commencer à "
                "alimenter l'historique."
            )
        else:
            latest = hist_df.iloc[-1]
            first = hist_df.iloc[0]
            delta_score = None
            if pd.notna(latest["health_score"]) and pd.notna(first["health_score"]) and len(hist_df) > 1:
                delta_score = int(latest["health_score"]) - int(first["health_score"])

            delta_label = "—"
            delta_style = "neutral"
            if delta_score is not None:
                delta_label = f"{'+' if delta_score > 0 else ''}{delta_score} pts"
                delta_style = "ok" if delta_score > 0 else ("danger" if delta_score < 0 else "neutral")

            st.markdown(stat_grid([
                ("Runs enregistrés", len(hist_df), "neutral"),
                (
                    "Dernier score",
                    f"{int(latest['health_score'])}/100" if pd.notna(latest["health_score"]) else "—",
                    "ok" if pd.notna(latest["health_score"]) and latest["health_score"] >= 70 else "warn",
                ),
                ("Évolution depuis le 1er run", delta_label, delta_style),
                ("Dernier niveau", latest.get("health_niveau") or "—", "neutral"),
            ]), unsafe_allow_html=True)

            hist_df = hist_df.copy()
            hist_df["timestamp_dt"] = pd.to_datetime(hist_df["timestamp"])
            chart_df = hist_df.set_index("timestamp_dt")

            st.markdown("**Score de santé dans le temps**")
            render_health_score_chart(chart_df)

            st.markdown("**Répartition des constats par criticité**")
            render_severity_chart(chart_df)

            st.markdown("**Historique des runs**")
            show_cols = [
                "id", "timestamp", "reference", "health_score", "health_niveau",
                "total_findings", "bloquant", "majeur", "mineur", "coverage_rate",
            ]
            st.dataframe(
                hist_df[show_cols].sort_values("timestamp", ascending=False),
                width="stretch",
                hide_index=True,
            )

            st.markdown("**Revoir le détail d'un run précédent**")
            runs_sorted = hist_df.sort_values("timestamp", ascending=False)
            run_options = {
                f"#{row.id} · {row.timestamp} · {row.reference}": row.id
                for row in runs_sorted.itertuples()
            }
            selected_label = st.selectbox("Choisir un run", list(run_options.keys()), key="hist_run_select")
            if st.button("Afficher les constats de ce run"):
                run_findings = history_load_run_findings(run_options[selected_label])
                if not run_findings:
                    st.warning("Aucun constat détaillé sauvegardé pour ce run.")
                else:
                    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
                    for f in sorted(run_findings, key=lambda x: ordre.get(x.get("criticite"), 3)):
                        with st.expander(f.get("libelle", "Constat")):
                            st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                            st.write(f"**Origine :** {f.get('source_module', '')}")
                            st.write(f"**Détail :** {f.get('detail', '')}")
                            st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")
                            if f.get("recommandation"):
                                st.write(f"**Recommandation :** {f.get('recommandation')}")

            st.markdown("---")
            st.markdown("**Comparer deux runs**")
            st.caption(
                "Identifie ce qui a été résolu, ce qui est nouveau, et ce qui persiste "
                "entre deux points de la migration — pas juste une photo à un instant T."
            )
            if history_diff_runs is not None and len(hist_df) >= 2:
                comp1, comp2 = st.columns(2)
                with comp1:
                    label_old = st.selectbox(
                        "Run de référence (plus ancien)",
                        list(run_options.keys()), index=len(run_options) - 1, key="diff_run_old",
                    )
                with comp2:
                    label_new = st.selectbox(
                        "Run à comparer (plus récent)",
                        list(run_options.keys()), index=0, key="diff_run_new",
                    )

                if st.button("Comparer les deux runs", type="primary"):
                    id_old = run_options[label_old]
                    id_new = run_options[label_new]
                    if id_old == id_new:
                        st.warning("Choisis deux runs différents pour la comparaison.")
                    else:
                        st.session_state["diff_result"] = history_diff_runs(id_old, id_new)

                if "diff_result" in st.session_state:
                    diff = st.session_state["diff_result"]
                    st.markdown(stat_grid([
                        ("Résolus", len(diff["resolved"]), "ok"),
                        ("Nouveaux", len(diff["new"]), "danger"),
                        ("Persistants", len(diff["persistent"]), "warn"),
                    ]), unsafe_allow_html=True)

                    if diff["resolved"]:
                        st.markdown("**Résolus depuis le run de référence**")
                        for f in diff["resolved"]:
                            with st.expander(f.get("libelle", "Constat")):
                                st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                                st.write(f"**Détail :** {f.get('detail', '')}")

                    if diff["new"]:
                        st.markdown("**Nouveaux constats**")
                        for f in diff["new"]:
                            with st.expander(f.get("libelle", "Constat")):
                                st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                                st.write(f"**Détail :** {f.get('detail', '')}")
                                st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")

                    if diff["persistent"]:
                        with st.expander(f"Constats persistants ({len(diff['persistent'])}) — non résolus depuis le run de référence"):
                            for f in diff["persistent"]:
                                st.markdown(
                                    f"{crit_tag(f.get('criticite', 'MINEUR'))} &nbsp; {f.get('libelle', '')}",
                                    unsafe_allow_html=True,
                                )
            elif len(hist_df) < 2:
                st.caption("Il faut au moins 2 runs enregistrés pour comparer.")

            st.markdown("---")
            st.markdown("**Dette de migration**")
            st.caption(
                "Constats qui reviennent identiques sur plusieurs runs consécutifs — "
                "signe qu'ils sont ignorés plutôt que corrigés, à prioriser."
            )
            if history_detect_stalled is not None:
                max_seuil = max(2, len(hist_df))
                seuil_dette = st.slider(
                    "Seuil : nombre de runs consécutifs identiques pour parler de dette",
                    min_value=2, max_value=max_seuil, value=min(3, max_seuil),
                )
                stalled = history_detect_stalled(min_runs=seuil_dette)

                if not stalled:
                    st.success(
                        f"Aucun constat ne persiste depuis {seuil_dette} runs consécutifs ou plus."
                    )
                else:
                    n_bloquant_stalled = sum(1 for f in stalled if f.get("criticite") == "BLOQUANT")
                    st.markdown(stat_grid([
                        ("Constats en dette", len(stalled), "danger" if n_bloquant_stalled else "warn"),
                        ("Dont bloquants", n_bloquant_stalled, "danger"),
                        ("Le plus ancien", f"{max(f['runs_consecutifs'] for f in stalled)} runs", "neutral"),
                    ]), unsafe_allow_html=True)

                    for f in stalled:
                        with st.expander(
                            f"{f.get('libelle', 'Constat')} — {f['runs_consecutifs']} runs consécutifs"
                        ):
                            st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                            st.write(f"**Depuis :** {f.get('premiere_apparition', '—')}")
                            st.write(f"**Détail :** {f.get('detail', '')}")
                            st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")
                            if f.get("recommandation"):
                                st.write(f"**Recommandation :** {f.get('recommandation')}")

            st.markdown("---")
            if history_clear_all is not None:
                if st.button("Effacer tout l'historique", type="secondary"):
                    st.session_state["confirm_clear_history"] = True

                if st.session_state.get("confirm_clear_history"):
                    st.warning("Confirmer la suppression définitive de tout l'historique ? Cette action est irréversible.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Oui, tout effacer", type="primary", key="confirm_clear_yes"):
                            history_clear_all()
                            st.session_state["confirm_clear_history"] = False
                            st.rerun()
                    with cc2:
                        if st.button("Annuler", key="confirm_clear_no"):
                            st.session_state["confirm_clear_history"] = False
                            st.rerun()

# ----------------------------------------------------------
# 06 — ASSISTANT Q&A
# ----------------------------------------------------------
elif page == "06":
    section("06", "Assistant Q&A")

    if answer_question is None:
        st.error(
            "Module d'assistant Q&A indisponible — vérifie que "
            "`src/orchestrator/qa_assistant.py` existe et s'importe sans erreur."
        )
    else:
        findings = st.session_state.get("findings") or []

        if not findings:
            st.info(
                "Aucun constat disponible. Génère d'abord un rapport consolidé "
                "(section 04 · **Générer le rapport consolidé**) pour pouvoir interroger l'audit."
            )
            if st.button("← Aller au rapport consolidé", key="qa_go_04"):
                st.session_state.current_page = "04"
                st.rerun()
        else:
            mb = st.session_state.get("module_b_coverage")
            coverage_rate_val = mb.get("coverage_rate") if mb else None
            health_score_val = None
            health_niveau_val = None
            if compute_health_score is not None:
                health = compute_health_score(to_finding_objects(findings), coverage_rate_val)
                health_score_val = health.get("score")
                health_niveau_val = health.get("niveau")

            st.markdown(
                f"""
                <div class="card" style="padding:1rem 1.25rem;margin-bottom:1rem;">
                  <div style="display:flex;align-items:center;gap:0.85rem;">
                    <div style="font-size:0.75rem;font-weight:700;letter-spacing:0.08em;color:#2563EB;background:rgba(37,99,235,0.1);border-radius:8px;padding:0.45rem 0.6rem;">QA</div>
                    <div>
                      <div style="font-weight:600;color:var(--ink);font-size:0.95rem;">
                        Assistant audit · Talan
                      </div>
                      <div style="font-size:0.78rem;color:var(--ink-soft);">
                        {len(findings)} constat(s) en contexte
                        {f" · Score {health_score_val}/100" if health_score_val is not None else ""}
                      </div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for turn in st.session_state.get("qa_history", []):
                with st.chat_message("user"):
                    st.markdown(turn["question"])
                with st.chat_message("assistant"):
                    st.markdown(turn["answer"])

            question = st.chat_input("Pose ta question sur l'audit…")
            if question:
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant"):
                    with st.spinner("Analyse des constats…"):
                        answer = answer_question(
                            question=question,
                            findings=findings,
                            health_score=health_score_val,
                            health_niveau=health_niveau_val,
                            coverage_rate=coverage_rate_val,
                            history=st.session_state.get("qa_history"),
                        )
                    st.markdown(answer)
                st.session_state.setdefault("qa_history", []).append(
                    {"question": question, "answer": answer}
                )

            if st.session_state.get("qa_history"):
                st.markdown("---")
                if st.button("Nouvelle conversation", key="qa_clear"):
                    st.session_state["qa_history"] = []
                    st.rerun()

# ----------------------------------------------------------
# 07 — IMPACT BUSINESS
# ----------------------------------------------------------
elif page == "07":
    section(
        "07",
        "Impact business",
        "Temps réellement chronométré par l'outil face à un audit manuel équivalent — "
        "économie, accélération et projection annuelle.",
    )

    timing_extraction = st.session_state.get("timing_extraction_sec")
    timing_coverage = st.session_state.get("timing_coverage_sec")
    n_kpis = st.session_state.get("timing_kpis_reconcilies") or 0
    findings = st.session_state.get("findings") or []

    def _fmt_duree(minutes: float) -> str:
        if minutes < 1:
            return f"{minutes * 60:.0f} sec"
        if minutes < 60:
            return f"{minutes:.1f} min"
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h}h{m:02d}"

    def _fmt_euro(amount: float) -> str:
        return f"{amount:,.0f}".replace(",", "\u00a0") + "\u00a0€"

    if timing_extraction is None:
        st.markdown(
            """
            <div class="card" style="text-align:center; padding:2.5rem 1.5rem;">
              <div style="font-family:'Source Serif 4',serif; font-size:1.35rem; font-weight:600; color:var(--ink); margin-bottom:0.5rem;">
                Aucune mesure encore disponible
              </div>
              <div style="font-size:0.9rem; color:var(--ink-soft); max-width:42ch; margin:0 auto 1.25rem auto; line-height:1.55;">
                Lance l'extraction (section 01) pour chronométrer le temps automatisé
                et calculer l'économie par rapport à un audit manuel.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Aller à l'extraction", type="primary", key="go_extract_08"):
            st.session_state.current_page = "01"
            st.rerun()
    else:
        with st.expander("Paramètres d'estimation manuelle", expanded=False):
            st.caption("Ajuste les hypothèses selon le contexte client (complexité, seniority).")
            col1, col2, col3 = st.columns(3)
            with col1:
                min_par_kpi = st.slider(
                    "Min / KPI (manuel)",
                    min_value=2, max_value=30, value=10,
                    help="Ouvrir Qlik + Power BI, comparer valeur et expression.",
                )
            with col2:
                min_par_constat = st.slider(
                    "Min / constat (manuel)",
                    min_value=5, max_value=60, value=15,
                    help="Diagnostiquer, recommander, documenter.",
                )
            with col3:
                taux_horaire = st.number_input(
                    "Taux horaire (€)",
                    min_value=10, max_value=300, value=70, step=5,
                )
            audits_par_an = st.slider(
                "Audits migration similaires / an",
                min_value=1, max_value=50, value=8,
                help="Pour projeter le gain annuel si le même type d'audit se répète.",
            )

        temps_auto_sec = timing_extraction + (timing_coverage or 0)
        temps_auto_min = temps_auto_sec / 60
        temps_manuel_min = (n_kpis * min_par_kpi) + (len(findings) * min_par_constat)
        gain_min = max(0, temps_manuel_min - temps_auto_min)
        gain_pct = (gain_min / temps_manuel_min * 100) if temps_manuel_min > 0 else 0
        cout_gagne = (gain_min / 60) * taux_horaire
        cout_annuel = cout_gagne * audits_par_an
        heures_gagnees = gain_min / 60
        facteur = (temps_manuel_min / temps_auto_min) if temps_auto_min > 0 else 0
        cov_part = f"+ couverture {timing_coverage:.1f}s" if timing_coverage else ""

        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:1.2fr 1fr; gap:1rem; margin:0.5rem 0 1.25rem 0;">
              <div style="background:linear-gradient(145deg, rgba(37,99,235,0.08) 0%, rgba(5,150,105,0.07) 100%);
                   border:1px solid var(--line); border-radius:18px; padding:1.75rem 1.85rem;
                   box-shadow:0 8px 28px rgba(15,23,42,0.06);">
                <div style="font-size:0.68rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:var(--ink-soft); margin-bottom:0.35rem;">
                  Économie sur ce run
                </div>
                <div style="font-family:'Source Serif 4',serif; font-size:3.2rem; font-weight:700; color:var(--accent-2); line-height:1.05; letter-spacing:-0.03em;">
                  {_fmt_euro(cout_gagne)}
                </div>
                <div style="font-size:0.88rem; color:var(--ink-soft); margin-top:0.65rem; line-height:1.5;">
                  <strong style="color:var(--ink);">{heures_gagnees:.1f}&nbsp;h</strong> gagnées ·
                  réduction de <strong style="color:var(--ok);">{gain_pct:.0f}%</strong> du temps de traitement
                </div>
              </div>
              <div style="background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:1.75rem 1.85rem;
                   box-shadow:0 8px 28px rgba(15,23,42,0.05); display:flex; flex-direction:column; justify-content:center;">
                <div style="font-size:0.68rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:var(--ink-soft); margin-bottom:0.35rem;">
                  Projection annuelle
                </div>
                <div style="font-family:'Source Serif 4',serif; font-size:2.4rem; font-weight:700; color:var(--ok); line-height:1.05;">
                  {_fmt_euro(cout_annuel)}
                </div>
                <div style="font-size:0.82rem; color:var(--ink-soft); margin-top:0.55rem; line-height:1.45;">
                  Sur <strong style="color:var(--ink);">{audits_par_an}</strong> audits / an à ce rythme
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.85rem; margin-bottom:1.35rem;">
              <div style="background:rgba(255,255,255,0.9); border:1px solid var(--line); border-radius:14px; padding:1.15rem 1.2rem; border-top:3px solid var(--ok);">
                <div style="font-size:0.62rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-soft);">Automatisé</div>
                <div style="font-family:'Source Serif 4',serif; font-size:1.65rem; font-weight:700; color:var(--ok); margin-top:0.25rem;">{_fmt_duree(temps_auto_min)}</div>
                <div style="font-size:0.72rem; color:var(--ink-soft); margin-top:0.2rem;">mesuré (chrono réel)</div>
              </div>
              <div style="background:rgba(255,255,255,0.9); border:1px solid var(--line); border-radius:14px; padding:1.15rem 1.2rem; border-top:3px solid var(--neutral);">
                <div style="font-size:0.62rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-soft);">Manuel estimé</div>
                <div style="font-family:'Source Serif 4',serif; font-size:1.65rem; font-weight:700; color:var(--ink); margin-top:0.25rem;">{_fmt_duree(temps_manuel_min)}</div>
                <div style="font-size:0.72rem; color:var(--ink-soft); margin-top:0.2rem;">{n_kpis} KPI · {len(findings)} constats</div>
              </div>
              <div style="background:rgba(255,255,255,0.9); border:1px solid var(--line); border-radius:14px; padding:1.15rem 1.2rem; border-top:3px solid var(--accent-2);">
                <div style="font-size:0.62rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-soft);">Accélération</div>
                <div style="font-family:'Source Serif 4',serif; font-size:1.65rem; font-weight:700; color:var(--accent-2); margin-top:0.25rem;">×{facteur:.1f}</div>
                <div style="font-size:0.72rem; color:var(--ink-soft); margin-top:0.2rem;">plus rapide que le manuel</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Temps de traitement — manuel vs automatisé**")
        render_business_impact_chart(temps_manuel_min, temps_auto_min)

        st.markdown(
            f"""
            <div class="card" style="padding:1.2rem 1.4rem; margin-top:0.5rem;">
              <div style="font-size:0.68rem; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:var(--ink-soft); margin-bottom:0.75rem;">
                Détail du calcul
              </div>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem 1.5rem; font-size:0.85rem; line-height:1.55;">
                <div>
                  <div style="color:var(--ink-soft); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.2rem;">Temps automatisé</div>
                  <div style="color:var(--ink);">Extraction {timing_extraction:.1f}s {cov_part} = <strong>{_fmt_duree(temps_auto_min)}</strong></div>
                </div>
                <div>
                  <div style="color:var(--ink-soft); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.2rem;">Temps manuel</div>
                  <div style="color:var(--ink);">{n_kpis} KPI × {min_par_kpi} min + {len(findings)} constats × {min_par_constat} min = <strong>{_fmt_duree(temps_manuel_min)}</strong></div>
                </div>
                <div>
                  <div style="color:var(--ink-soft); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.2rem;">Coût évité (ce run)</div>
                  <div style="color:var(--ink);">{heures_gagnees:.2f} h × {taux_horaire} €/h = <strong>{_fmt_euro(cout_gagne)}</strong></div>
                </div>
                <div>
                  <div style="color:var(--ink-soft); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.2rem;">Projection annuelle</div>
                  <div style="color:var(--ink);">{_fmt_euro(cout_gagne)} × {audits_par_an} audits = <strong>{_fmt_euro(cout_annuel)}</strong></div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="font-size:0.78rem; color:var(--ink-soft); line-height:1.55; margin-top:0.85rem;">
            Le temps automatisé est <strong>mesuré</strong> (chrono autour de l'extraction et de la couverture).
            Le temps manuel est une <strong>hypothèse ajustable</strong> — les paramètres ci-dessus permettent de l'aligner
            sur le contexte (complexité du modèle, expérience du consultant) plutôt qu'un chiffre figé.
            </div>
            """,
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------
# 08 — PLAN D'ACTION PRIORISÉ
# ----------------------------------------------------------
elif page == "08":
    section(
        "08",
        "Plan d'action priorisé",
        "Combine criticité, origine du constat et ancienneté (dette de migration) "
        "en un ordre de traitement recommandé — pas juste un tri par criticité brute.",
    )

    findings_plan = st.session_state.get("findings") or []

    if not findings_plan:
        st.info(
            "Aucun constat disponible. Génère d'abord un rapport consolidé "
            "(section 04 · **Générer le rapport consolidé**) pour obtenir un plan d'action."
        )
    else:
        stalled_by_libelle = {}
        if history_detect_stalled is not None:
            stalled_list = history_detect_stalled(min_runs=2)
            stalled_by_libelle = {f.get("libelle"): f for f in stalled_list}

        scored = []
        for f in findings_plan:
            pr = compute_priority_score(f, stalled_by_libelle)
            scored.append({**f, **pr})
        scored.sort(key=lambda x: -x["score"])

        top3 = scored[:3]
        st.markdown("**À traiter en priorité**")
        for rank, f in enumerate(top3, 1):
            st.markdown(
                f"""
                <div class="card" style="padding:1.1rem 1.3rem; margin-bottom:0.7rem;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
                        <div>
                            <span style="font-family:'JetBrains Mono',monospace; color:var(--brass); font-weight:700; font-size:0.8rem;">#{rank}</span>
                            &nbsp; {crit_tag(f.get('criticite', 'MINEUR'))}
                            &nbsp; <strong style="font-size:1rem;">{f.get('libelle', '')}</strong>
                        </div>
                        <div style="font-family:'Source Serif 4',serif; font-size:1.5rem; font-weight:700; color:var(--accent-2); white-space:nowrap;">
                            {f['score']}
                        </div>
                    </div>
                    <div style="font-size:0.82rem; color:var(--ink-soft); margin-top:0.5rem;">
                        Priorisé pour : {', '.join(f['reasons'])}.
                    </div>
                    <div style="font-size:0.85rem; color:var(--ink); margin-top:0.5rem;">
                        {f.get('recommandation', '')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("**Plan complet, par ordre de priorité**")
        for rank, f in enumerate(scored, 1):
            with st.expander(f"#{rank} · {f.get('libelle', 'Constat')} — score {f['score']}"):
                st.markdown(crit_tag(f.get("criticite", "MINEUR")), unsafe_allow_html=True)
                st.write(f"**Origine :** {f.get('source_module', '')}")
                st.write(f"**Pourquoi cette priorité :** {', '.join(f['reasons'])}")
                st.write(f"**Détail :** {f.get('detail', '')}")
                st.write(f"**Diagnostic :** {f.get('diagnostic', '')}")
                if f.get("recommandation"):
                    st.write(f"**Recommandation :** {f.get('recommandation')}")

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size:0.8rem; color:var(--ink-soft); line-height:1.6;">
            <strong>Méthode de scoring :</strong> score de base selon la criticité
            (Bloquant 100 · Majeur 60 · Mineur 20), pondéré légèrement à la hausse
            pour les écarts de données (impact direct sur les chiffres présentés au
            client), et majoré si le constat revient identique sur plusieurs runs
            consécutifs (signe qu'il est ignoré plutôt que traité). Le détail du
            calcul est affiché pour chaque constat — ce n'est pas un score opaque.
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    f"""
<div class="doc-footer">
  Audit de migration Qlik Sense vers Power BI · Talan · {datetime.date.today().year} · Document confidentiel, usage interne
</div>
""",
    unsafe_allow_html=True,
)