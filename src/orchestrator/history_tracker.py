"""
Suivi historique des runs d'audit — Module A/B/Orchestrateur.

Stocke un snapshot (score de santé, compteurs de criticité, taux de couverture,
liste complète des constats) à chaque génération de rapport consolidé, dans une
base SQLite locale. Permet de tracer l'évolution d'une migration dans le temps
et de rouvrir le détail d'un run passé.

Emplacement de la base : data/history/audit_history.db (relatif au répertoire
d'exécution, comme data/temp/ utilisé ailleurs dans le projet).
"""
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

DB_PATH = Path("data/history/audit_history.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            reference TEXT,
            health_score INTEGER,
            health_niveau TEXT,
            total_findings INTEGER,
            bloquant INTEGER,
            majeur INTEGER,
            mineur INTEGER,
            coverage_rate REAL,
            findings_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_run(
    reference: str,
    findings: List[Dict],
    coverage_rate: Optional[float] = None,
    health_score: Optional[int] = None,
    health_niveau: Optional[str] = None,
) -> int:
    """Sauvegarde un snapshot de l'audit courant. Retourne l'id du run créé."""
    bloquant = sum(1 for f in findings if f.get("criticite") == "BLOQUANT")
    majeur = sum(1 for f in findings if f.get("criticite") == "MAJEUR")
    mineur = sum(1 for f in findings if f.get("criticite") == "MINEUR")

    conn = _get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO runs (
                timestamp, reference, health_score, health_niveau,
                total_findings, bloquant, majeur, mineur, coverage_rate, findings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(timespec="seconds"),
                reference,
                health_score,
                health_niveau,
                len(findings),
                bloquant,
                majeur,
                mineur,
                coverage_rate,
                json.dumps(findings, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def load_history_df() -> pd.DataFrame:
    """Retourne l'historique des runs, du plus ancien au plus récent."""
    conn = _get_connection()
    try:
        return pd.read_sql_query(
            """
            SELECT id, timestamp, reference, health_score, health_niveau,
                   total_findings, bloquant, majeur, mineur, coverage_rate
            FROM runs
            ORDER BY timestamp ASC
            """,
            conn,
        )
    finally:
        conn.close()


def load_run_findings(run_id: int) -> List[Dict]:
    """Recharge la liste complète des constats d'un run précédent."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT findings_json FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row or not row[0]:
            return []
        return json.loads(row[0])
    finally:
        conn.close()


def detect_stalled_findings(min_runs: int = 3) -> List[Dict]:
    """Identifie les constats qui persistent, identiques, sur au moins `min_runs`
    runs consécutifs les plus récents — signe qu'ils sont ignorés/oubliés plutôt
    que corrigés, plutôt qu'un simple problème ponctuel.

    Chaque constat retourné est enrichi de 'runs_consecutifs' (nombre de runs
    d'affilée où il apparaît, jusqu'au run le plus récent) et
    'premiere_apparition' (timestamp du run le plus ancien de cette série).
    Trié du plus persistant au moins persistant, puis par criticité.
    """
    hist_df = load_history_df()
    if len(hist_df) < min_runs:
        return []

    runs_sorted = hist_df.sort_values("timestamp", ascending=True)
    run_ids = list(runs_sorted["id"])
    timestamps = list(runs_sorted["timestamp"])

    findings_per_run = [
        {f.get("libelle"): f for f in load_run_findings(rid)}
        for rid in run_ids
    ]

    latest_findings = findings_per_run[-1]
    stalled = []

    for libelle, finding in latest_findings.items():
        streak = 0
        first_ts = timestamps[-1]
        for i in range(len(findings_per_run) - 1, -1, -1):
            if libelle in findings_per_run[i]:
                streak += 1
                first_ts = timestamps[i]
            else:
                break
        if streak >= min_runs:
            enriched = dict(finding)
            enriched["runs_consecutifs"] = streak
            enriched["premiere_apparition"] = first_ts
            stalled.append(enriched)

    ordre = {"BLOQUANT": 0, "MAJEUR": 1, "MINEUR": 2}
    stalled.sort(key=lambda f: (-f["runs_consecutifs"], ordre.get(f.get("criticite"), 3)))
    return stalled


def diff_runs(run_id_old: int, run_id_new: int) -> Dict[str, List[Dict]]:
    """Compare deux runs et classe chaque constat en résolu / nouveau / persistant.

    Le matching se fait sur le libellé du constat (ex. « Current Year Sales —
    VALUE MISMATCH »), stable d'un run à l'autre tant que le problème sous-jacent
    n'a pas changé — pas besoin d'un identifiant technique dédié.

    Retourne {'resolved': [...], 'new': [...], 'persistent': [...]}.
    """
    findings_old = load_run_findings(run_id_old)
    findings_new = load_run_findings(run_id_new)

    by_libelle_old = {f.get("libelle"): f for f in findings_old}
    by_libelle_new = {f.get("libelle"): f for f in findings_new}

    resolved = [f for lib, f in by_libelle_old.items() if lib not in by_libelle_new]
    new = [f for lib, f in by_libelle_new.items() if lib not in by_libelle_old]
    persistent = [f for lib, f in by_libelle_new.items() if lib in by_libelle_old]

    return {"resolved": resolved, "new": new, "persistent": persistent}


def delete_run(run_id: int) -> None:
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()


def clear_history() -> None:
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM runs")
        conn.commit()
    finally:
        conn.close()