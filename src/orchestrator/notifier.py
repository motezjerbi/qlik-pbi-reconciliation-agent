# orchestrator/notifier.py
"""
Notifications par email pour l'audit de migration Qlik → Power BI.

Contrairement à une intégration SMTP classique (adresse + mot de passe
d'application stockés dans l'app), l'envoi se fait ici via l'API Gmail,
en utilisant le jeton d'accès OAuth du compte Google réellement connecté
par l'utilisateur (st.login(), voir app.py). Aucun mot de passe n'est
jamais stocké : le jeton vit uniquement en mémoire, pour la durée de la
session Streamlit, et est fourni par expose_tokens="access" dans
.streamlit/secrets.toml.

Prérequis côté Google Cloud Console (voir .streamlit/secrets.toml.example
et le README pour le détail pas à pas) :
  - un client OAuth 2.0 (type "Application Web")
  - le scope https://www.googleapis.com/auth/gmail.send demandé à la connexion
  - l'app en mode "Testing" avec l'adresse Gmail utilisée ajoutée comme
    utilisateur de test (pas besoin de vérification Google pour un usage
    de stage/démo)
"""
import base64
import json
from email.mime.text import MIMEText

import requests

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def send_email_via_gmail_api(
    access_token: str,
    sender_email: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    """Envoie un email HTML via l'API Gmail, au nom du compte Google connecté.

    Lève une exception (avec le message d'erreur renvoyé par Google) en cas
    d'échec, pour que l'appelant puisse l'afficher dans l'interface plutôt
    que d'échouer silencieusement.
    """
    msg = MIMEText(html_body, "html", "utf-8")
    msg["to"] = to_email
    msg["from"] = sender_email
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    resp = requests.post(
        GMAIL_SEND_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"raw": raw}),
        timeout=15,
    )
    if resp.status_code >= 300:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Échec de l'envoi via l'API Gmail (HTTP {resp.status_code}) : {detail}")


# ============================================================
# GABARITS D'EMAILS
# ============================================================
def email_new_bloquant(ref: str, new_findings: list) -> str:
    rows = "".join(
        f"<li><strong>{f.get('libelle', '')}</strong> — {f.get('detail', '')}</li>"
        for f in new_findings
    )
    return f"""
    <div style="font-family:Arial,sans-serif; color:#0B1220;">
        <h2 style="color:#DC2626;">⚠️ Nouveau(x) constat(s) BLOQUANT — {ref}</h2>
        <p>{len(new_findings)} nouveau(x) constat(s) critique(s) détecté(s) lors du dernier run d'audit :</p>
        <ul>{rows}</ul>
        <p style="color:#64748B; font-size:0.85rem;">
            Consulte le rapport complet dans l'application pour le détail et les recommandations.
        </p>
    </div>
    """


def email_report_generated(
    ref: str,
    total: int,
    bloquant: int,
    majeur: int,
    mineur: int,
    health_score=None,
    health_niveau=None,
) -> str:
    health_line = (
        f"<p>Score de santé : <strong>{health_score}/100 ({health_niveau})</strong></p>"
        if health_score is not None else ""
    )
    return f"""
    <div style="font-family:Arial,sans-serif; color:#0B1220;">
        <h2 style="color:#2563EB;">📊 Rapport consolidé généré — {ref}</h2>
        <p>{total} constat(s) au total : {bloquant} bloquant(s), {majeur} majeur(s), {mineur} mineur(s).</p>
        {health_line}
        <p style="color:#64748B; font-size:0.85rem;">Consulte le détail complet dans l'application.</p>
    </div>
    """


def email_dette_migration(ref: str, stalled: list) -> str:
    rows = "".join(
        f"<li><strong>{f.get('libelle', '')}</strong> — non résolu depuis "
        f"{f.get('runs_consecutifs')} run(s) consécutif(s)</li>"
        for f in stalled
    )
    return f"""
    <div style="font-family:Arial,sans-serif; color:#0B1220;">
        <h2 style="color:#D97706;">🕒 Dette de migration détectée — {ref}</h2>
        <p>{len(stalled)} constat(s) persistent sur plusieurs runs consécutifs sans être résolus :</p>
        <ul>{rows}</ul>
        <p style="color:#64748B; font-size:0.85rem;">
            Signe qu'ils sont ignorés plutôt que corrigés — à prioriser (voir section « Plan d'action »).
        </p>
    </div>
    """