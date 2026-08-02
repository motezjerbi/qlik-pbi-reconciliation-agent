"""
Client Engine (ADOMD.NET) pour Power BI Desktop - Module A
Équivalent du qlik_engine_client.py, mais pour le moteur Analysis Services
que Power BI Desktop lance en local quand un .pbix est ouvert.
"""
import sys
import os

ADOMD_DIR = r"C:\Program Files\Microsoft.NET\ADOMD.NET\110"
sys.path.append(ADOMD_DIR)
os.environ["PATH"] = ADOMD_DIR + os.pathsep + os.environ["PATH"]

from pathlib import Path
from typing import Dict, List
import psutil
from pyadomd import Pyadomd  # doit venir après les 3 lignes ci-dessus


def find_pbi_port() -> int:
    """Trouve le port local du moteur Power BI (msmdsrv.exe) via psutil."""
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and proc.info["name"].lower() == "msmdsrv.exe":
            pid = proc.pid
            for conn in psutil.Process(pid).connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.ip == "127.0.0.1":
                    return conn.laddr.port
    raise RuntimeError(
        "msmdsrv.exe introuvable — vérifie que Power BI Desktop "
        "est ouvert avec le .pbix chargé."
    )


def _run_dax(conn, query: str) -> List[Dict]:
    with conn.cursor().execute(query) as cur:
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]


def extract_app_structure(pbix_path: str) -> Dict:
    """Extraction complète pour le Module A, via connexion live au moteur."""
    result = {
        "tables": [], "measures": [], "dimensions": [], "kpis": [], "columns": [],
        "metadata": {"source": "adomd_engine", "file": Path(pbix_path).name},
    }

    port = find_pbi_port()
    conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};"

    with Pyadomd(conn_str) as conn:
        print(f"🔌 Connecté au moteur Power BI (port {port})")

        tables = _run_dax(conn, "SELECT [ID], [Name] FROM $SYSTEM.TMSCHEMA_TABLES")
        table_id_to_name = {}
        for t in tables:
            name = t.get("Name")
            if name and not name.startswith("LocalDateTable"):
                result["tables"].append({"name": name})
                table_id_to_name[t.get("ID")] = name
        print(f"  📊 Tables : {len(result['tables'])}")

        # --- Colonnes (pour comparer les dimensions Qlik aux colonnes PBI) ---
        try:
            columns = _run_dax(
                conn,
                "SELECT [TableID], [ExplicitName] FROM $SYSTEM.TMSCHEMA_COLUMNS"
            )
            for c in columns:
                col_name = c.get("ExplicitName")
                table_name = table_id_to_name.get(c.get("TableID"), "")
                if col_name and table_name:
                    result["columns"].append({"table": table_name, "name": col_name})
            print(f"  📐 Colonnes : {len(result['columns'])}")
        except Exception as e:
            print(f"  ⚠️ Colonnes non récupérées : {e}")

        measures = _run_dax(
            conn, "SELECT [Name], [Expression] FROM $SYSTEM.TMSCHEMA_MEASURES"
        )
        for m in measures:
            name = m.get("Name")
            expr = m.get("Expression")
            if not name:
                continue
            result["measures"].append({"name": name, "dax": expr})

            error_msg = None
            try:
                value_rows = _run_dax(conn, f'EVALUATE ROW("v", [{name}])')
                value = list(value_rows[0].values())[0] if value_rows else None
            except Exception as e:
                value = None
                # Première ligne seulement : le reste est une stack trace .NET, pas utile
                # au consultant et inutilisable telle quelle comme "cause probable".
                error_msg = str(e).split("\n")[0].strip()
                print(f"  ⚠️ Impossible d'évaluer {name}: {error_msg}")

            result["kpis"].append({
                "name": name,
                "value": value,
                "expression": expr,
                "error": error_msg,
            })
            if error_msg is None:
                print(f"  ✅ KPI : {name} = {value}")

    print(f"\n✅ Extraction terminée : {len(result['tables'])} tables, "
          f"{len(result['measures'])} mesures, {len(result['kpis'])} KPIs")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage : python pbi_engine_client.py <chemin_fichier.pbix>")
        sys.exit(1)
    result = extract_app_structure(sys.argv[1])